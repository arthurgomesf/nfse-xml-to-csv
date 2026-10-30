"""Relatório HTML com o resumo da base extraída, para demonstração.

O produto do projeto é o CSV que alimenta o relatório no Power BI. Este HTML é
um extra para apresentar o resultado sem depender do BI: arquivo único, só
biblioteca padrão e sem recursos externos (abre offline em qualquer navegador).
"""

from __future__ import annotations

import html
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from string import Template

from . import __version__
from .pipeline import APROVADA, CANCELADA, Resultado

_e = html.escape
_ZERO = Decimal(0)


def _decimal(texto: str) -> Decimal:
    try:
        return Decimal(texto)
    except InvalidOperation:
        return _ZERO


def _moeda(valor: Decimal) -> str:
    """Formata no padrão brasileiro.

    >>> _moeda(Decimal("12300.5"))
    'R$ 12.300,50'
    """
    texto = f"{valor:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {texto}"


def _cnpj(cnpj: str) -> str:
    """
    >>> _cnpj("11222333000181")
    '11.222.333/0001-81'
    """
    if len(cnpj) != 14 or not cnpj.isdigit():
        return cnpj
    return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"


def _ordem_data(data: str) -> str:
    """``dd/mm/aaaa`` → ``aaaa-mm-dd``, para ordenar cronologicamente."""
    partes = data.split("/")
    return "-".join(reversed(partes)) if len(partes) == 3 else data


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def _soma(linhas: list[dict[str, str]], coluna: str) -> Decimal:
    return sum((_decimal(linha[coluna]) for linha in linhas), _ZERO)


def _kpis(linhas: list[dict[str, str]]) -> str:
    aprovadas = [linha for linha in linhas if linha["status"] == APROVADA]
    canceladas = [linha for linha in linhas if linha["status"] == CANCELADA]
    sem_pedido = [linha for linha in aprovadas if not linha["pedido_compra"]]

    cartoes = [
        (
            "Notas consolidadas",
            str(len(linhas)),
            f"{_plural(len(aprovadas), 'aprovada', 'aprovadas')} · "
            f"{_plural(len(canceladas), 'cancelada', 'canceladas')}",
            "",
        ),
        ("Valor de serviços", _moeda(_soma(aprovadas, "valor_servico")), "notas aprovadas", ""),
        ("ISS", _moeda(_soma(aprovadas, "valor_iss")), "notas aprovadas", ""),
        (
            "Canceladas",
            str(len(canceladas)),
            f"{_moeda(_soma(canceladas, 'valor_servico'))} fora da base de lançamento",
            "alerta" if canceladas else "",
        ),
        (
            "Sem pedido de compra",
            str(len(sem_pedido)),
            "conferir antes do lançamento" if sem_pedido else "todas com pedido identificado",
            "alerta" if sem_pedido else "ok",
        ),
    ]
    return "\n".join(
        f'<div class="kpi {classe}"><span class="kpi-rotulo">{_e(rotulo)}</span>'
        f'<strong class="kpi-valor">{_e(valor)}</strong>'
        f'<span class="kpi-detalhe">{_e(detalhe)}</span></div>'
        for rotulo, valor, detalhe, classe in cartoes
    )


def _unidades(linhas: list[dict[str, str]]) -> str:
    resumo: dict[str, dict[str, Decimal | int]] = {}
    for linha in linhas:
        u = resumo.setdefault(linha["unidade"], {APROVADA: 0, CANCELADA: 0, "valor": _ZERO})
        u[linha["status"]] += 1
        if linha["status"] == APROVADA:
            u["valor"] += _decimal(linha["valor_servico"])

    maior = max((u["valor"] for u in resumo.values()), default=_ZERO) or Decimal(1)
    return "\n".join(
        f"<tr><td>{_e(nome)}</td><td class='num'>{u[APROVADA]}</td>"
        f"<td class='num'>{u[CANCELADA]}</td><td class='num'>{_moeda(u['valor'])}</td>"
        f"<td class='barra-celula'>"
        f"<span class='barra' style='width:{u['valor'] / maior * 100:.1f}%'></span></td></tr>"
        for nome, u in resumo.items()
    )


def _prestadores(linhas: list[dict[str, str]], limite: int = 8) -> str:
    totais: dict[str, Decimal] = defaultdict(lambda: _ZERO)
    quantidade: dict[str, int] = defaultdict(int)
    for linha in linhas:
        if linha["status"] == APROVADA:
            totais[linha["emit_nome"]] += _decimal(linha["valor_servico"])
            quantidade[linha["emit_nome"]] += 1

    ranking = sorted(totais.items(), key=lambda item: item[1], reverse=True)[:limite]
    if not ranking:
        return "<p class='vazio'>Nenhuma nota aprovada.</p>"
    maior = ranking[0][1] or Decimal(1)
    return "\n".join(
        f"<div class='ranking-item'><div class='ranking-texto'><span>{_e(nome)}</span>"
        f"<span class='num'>{_moeda(valor)} · {_plural(quantidade[nome], 'nota', 'notas')}</span>"
        f"</div><span class='barra' style='width:{valor / maior * 100:.1f}%'></span></div>"
        for nome, valor in ranking
    )


def _atencao(resultado: Resultado) -> str:
    itens: list[tuple[str, str, str]] = []
    for linha in resultado.linhas:
        nota = f"NFS-e {linha['nfse_numero']} · {linha['emit_nome']} · {linha['unidade']}"
        if linha["status"] == CANCELADA:
            itens.append(
                (
                    "cancelada",
                    "Cancelada",
                    f"{nota} · {_moeda(_decimal(linha['valor_servico']))}: "
                    "confirmar que não foi lançada no ERP",
                )
            )
        elif not linha["pedido_compra"]:
            itens.append(("alerta", "Sem pedido", f"{nota}: pedido não identificado"))
        if linha["subst_chave"]:
            motivo = linha["subst_motivo_descricao"] or "motivo não informado"
            itens.append(
                (
                    "info",
                    "Substituta",
                    f"{nota}: substitui a nota …{linha['subst_chave'][-12:]} ({motivo})",
                )
            )
    for arquivo, motivo in resultado.ignorados:
        itens.append(
            ("erro", "Não lido", f"{arquivo.parent.parent.name} / {arquivo.name}: {motivo}")
        )

    if not itens:
        return "<p class='vazio'>Nenhum ponto de atenção.</p>"
    return (
        "<ul class='atencao'>"
        + "\n".join(
            f"<li><span class='etiqueta {classe}'>{_e(rotulo)}</span><span>{_e(texto)}</span></li>"
            for classe, rotulo, texto in itens
        )
        + "</ul>"
    )


def _tabela(linhas: list[dict[str, str]]) -> str:
    ordenadas = sorted(linhas, key=lambda linha: _ordem_data(linha["data_emissao"]), reverse=True)
    return "\n".join(
        f"<tr data-status='{_e(linha['status'])}'>"
        f"<td class='num'>{_e(linha['nfse_numero'])}</td>"
        f"<td>{_e(linha['data_emissao'])}</td>"
        f"<td><span class='forte'>{_e(linha['emit_nome'])}</span>"
        f"<span class='sub'>{_e(_cnpj(linha['emit_cnpj']))}</span></td>"
        f"<td>{_e(linha['unidade'])}</td>"
        f"<td class='num'>{_e(linha['pedido_compra']) or '<span class=sub>—</span>'}</td>"
        f"<td class='num'>{_moeda(_decimal(linha['valor_servico']))}</td>"
        f"<td class='num'>{_moeda(_decimal(linha['valor_iss']))}</td>"
        f"<td><span class='etiqueta {'cancelada' if linha['status'] == CANCELADA else 'ok'}'>"
        f"{_e(linha['status'])}</span></td></tr>"
        for linha in ordenadas
    )


def gerar_relatorio(resultado: Resultado, destino: Path, origem: Path | None = None) -> Path:
    """Grava o relatório HTML em ``destino`` e devolve o caminho."""
    conteudo = _MODELO.substitute(
        gerado_em=datetime.now().strftime("%d/%m/%Y às %H:%M"),
        origem=_e(str(origem)) if origem else "—",
        versao=__version__,
        kpis=_kpis(resultado.linhas),
        unidades=_unidades(resultado.linhas),
        prestadores=_prestadores(resultado.linhas),
        atencao=_atencao(resultado),
        tabela=_tabela(resultado.linhas),
        total=len(resultado.linhas),
    )
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(conteudo, encoding="utf-8")
    return destino


_MODELO = Template("""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Relatório de NFS-e</title>
<style>
:root {
  --fundo: #f5f6f8; --superficie: #ffffff; --borda: #e3e6eb; --texto: #1c2430;
  --suave: #5f6b7a; --destaque: #2563eb; --destaque-fundo: #e8efff;
  --ok: #15803d; --ok-fundo: #e7f6ec; --alerta: #b45309; --alerta-fundo: #fdf3e2;
  --erro: #b91c1c; --erro-fundo: #fdeaea; --info: #6d28d9; --info-fundo: #f1ebff;
}
@media (prefers-color-scheme: dark) {
  :root {
    --fundo: #0f141b; --superficie: #171e27; --borda: #2a3441; --texto: #e6eaf0;
    --suave: #98a4b3; --destaque: #6b9bff; --destaque-fundo: #1d2a44;
    --ok: #4ade80; --ok-fundo: #14301f; --alerta: #fbbf24; --alerta-fundo: #3a2c10;
    --erro: #f87171; --erro-fundo: #3b1818; --info: #b79cff; --info-fundo: #2a2145;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--fundo); color: var(--texto);
  font: 15px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}
main { max-width: 1180px; margin: 0 auto; padding: 32px 16px 48px; }
header { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 8px 24px;
  align-items: flex-end; margin-bottom: 24px; }
h1 { margin: 0; font-size: 26px; letter-spacing: -0.02em; }
h2 { margin: 0 0 14px; font-size: 16px; }
.meta { color: var(--suave); font-size: 13px; text-align: right; }
.meta code { font-size: 12px; overflow-wrap: anywhere; }
.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 12px; margin-bottom: 16px; }
.kpi, .painel { background: var(--superficie); border: 1px solid var(--borda);
  border-radius: 12px; }
.kpi { padding: 16px 18px; display: flex; flex-direction: column; gap: 2px;
  border-top: 3px solid var(--destaque); }
.kpi.alerta { border-top-color: var(--alerta); }
.kpi.ok { border-top-color: var(--ok); }
.kpi-rotulo { color: var(--suave); font-size: 13px; }
.kpi-valor { font-size: 24px; font-variant-numeric: tabular-nums; letter-spacing: -0.01em; }
.kpi-detalhe { color: var(--suave); font-size: 12px; }
.grade { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
  gap: 16px; margin-bottom: 16px; }
.painel { padding: 18px 20px; min-width: 0; }
.rolagem { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th { text-align: left; color: var(--suave); font-weight: 600; font-size: 12px;
  text-transform: uppercase; letter-spacing: 0.04em; padding: 8px 10px;
  border-bottom: 1px solid var(--borda); white-space: nowrap; }
td { padding: 10px; border-bottom: 1px solid var(--borda); vertical-align: top; }
tr:last-child td { border-bottom: 0; }
.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
th.num { text-align: right; }
.barra-celula { width: 30%; vertical-align: middle; }
.barra { display: block; height: 8px; min-width: 2px; border-radius: 4px;
  background: var(--destaque); }
.ranking-item { margin-bottom: 12px; }
.ranking-texto { display: flex; justify-content: space-between; gap: 12px; font-size: 14px;
  margin-bottom: 4px; }
.ranking-texto .num { color: var(--suave); }
.atencao { list-style: none; margin: 0; padding: 0; }
.atencao li { display: flex; gap: 10px; align-items: baseline; padding: 8px 0;
  border-bottom: 1px solid var(--borda); font-size: 14px; }
.atencao li:last-child { border-bottom: 0; }
.etiqueta { flex: none; display: inline-block; padding: 1px 8px; border-radius: 999px;
  font-size: 12px; font-weight: 600; background: var(--destaque-fundo); color: var(--destaque); }
.etiqueta.ok { background: var(--ok-fundo); color: var(--ok); }
.etiqueta.alerta { background: var(--alerta-fundo); color: var(--alerta); }
.etiqueta.cancelada, .etiqueta.erro { background: var(--erro-fundo); color: var(--erro); }
.etiqueta.info { background: var(--info-fundo); color: var(--info); }
.forte { display: block; }
.sub { display: block; color: var(--suave); font-size: 12px; }
.filtros { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 12px; }
.filtros h2 { margin: 0 auto 0 0; }
input, select { font: inherit; font-size: 14px; color: var(--texto); background: var(--fundo);
  border: 1px solid var(--borda); border-radius: 8px; padding: 6px 10px; }
input { width: min(260px, 100%); }
.contador { color: var(--suave); font-size: 13px; margin-top: 10px; }
.vazio { color: var(--suave); margin: 0; }
footer { color: var(--suave); font-size: 12px; margin-top: 24px; text-align: center; }
@media (max-width: 420px) { .grade { grid-template-columns: 1fr; } }
</style>
</head>
<body>
<main>
  <header>
    <div>
      <h1>Relatório de NFS-e</h1>
      <span class="sub">Notas de serviço consolidadas a partir dos XMLs</span>
    </div>
    <div class="meta">Gerado em $gerado_em<br>Base: <code>$origem</code></div>
  </header>

  <section class="kpis">
$kpis
  </section>

  <div class="grade">
    <section class="painel">
      <h2>Por unidade</h2>
      <div class="rolagem">
        <table>
          <thead><tr><th>Unidade</th><th class="num">Aprovadas</th><th class="num">Canceladas</th>
          <th class="num">Valor aprovado</th><th></th></tr></thead>
          <tbody>
$unidades
          </tbody>
        </table>
      </div>
    </section>
    <section class="painel">
      <h2>Maiores prestadores</h2>
$prestadores
    </section>
  </div>

  <section class="painel" style="margin-bottom:16px">
    <h2>Pontos de atenção</h2>
$atencao
  </section>

  <section class="painel">
    <div class="filtros">
      <h2>Notas</h2>
      <input id="busca" type="search" placeholder="Buscar prestador, nº, pedido…">
      <select id="status">
        <option value="">Todos os status</option>
        <option value="Aprovadas">Aprovadas</option>
        <option value="Canceladas">Canceladas</option>
      </select>
    </div>
    <div class="rolagem">
      <table id="notas">
        <thead><tr><th class="num">Nº</th><th>Emissão</th><th>Prestador</th><th>Unidade</th>
        <th class="num">Pedido</th><th class="num">Valor</th><th class="num">ISS</th>
        <th>Status</th></tr></thead>
        <tbody>
$tabela
        </tbody>
      </table>
    </div>
    <div class="contador" id="contador">$total notas</div>
  </section>

  <footer>
    nfse-extractor $versao · gerado a partir da mesma base CSV que alimenta o Power BI
  </footer>
</main>
<script>
(function () {
  var busca = document.getElementById("busca");
  var status = document.getElementById("status");
  var linhas = Array.prototype.slice.call(document.querySelectorAll("#notas tbody tr"));
  function filtrar() {
    var termo = busca.value.trim().toLowerCase();
    var visiveis = 0;
    linhas.forEach(function (tr) {
      var ok = tr.textContent.toLowerCase().indexOf(termo) !== -1 &&
        (!status.value || tr.getAttribute("data-status") === status.value);
      tr.hidden = !ok;
      if (ok) { visiveis++; }
    });
    document.getElementById("contador").textContent = visiveis + " de " + linhas.length + " notas";
  }
  busca.addEventListener("input", filtrar);
  status.addEventListener("change", filtrar);
})();
</script>
</body>
</html>
""")
