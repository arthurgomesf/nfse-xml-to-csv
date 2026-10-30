"""Consolidação: lê as pastas de cada unidade, aplica as regras e monta a base."""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from .config import Unidade
from .leitor import NFSeInvalida, ler_nfse
from .regras import extrair_pedido_compra, formatar_data, normalizar_numero_nf

log = logging.getLogger(__name__)

# Valores mantidos idênticos aos nomes das pastas: o BI já filtra por eles.
APROVADA = "Aprovadas"
CANCELADA = "Canceladas"

# Ordem das colunas no CSV. É o contrato com o BI: não reordenar nem renomear.
COLUNAS: tuple[str, ...] = (
    "nfse_id",
    "nfse_numero",
    "subst_chave",
    "subst_motivo_codigo",
    "subst_motivo_descricao",
    "nfse_DPS",
    "pedido_compra",
    "data_emissao",
    "emit_cnpj",
    "emit_nome",
    "emit_im",
    "toma_cnpj",
    "toma_nome",
    "valor_servico",
    "base_calculo",
    "aliquota_iss",
    "valor_iss",
    "valor_liquido",
    "codigo_nbs",
    "descricao_servico",
    "unidade",
    "status",
    "Chave",
)


class PastaNaoEncontrada(Exception):
    def __init__(self, pasta: Path, unidade: str) -> None:
        super().__init__(
            f"pasta não encontrada para a unidade '{unidade}': {pasta}\n"
            "Verifique o caminho na configuração e se o OneDrive/SharePoint está sincronizado. "
            "Nenhum arquivo de saída foi gravado."
        )


@dataclass
class Resultado:
    linhas: list[dict[str, str]] = field(default_factory=list)
    ignorados: list[tuple[Path, str]] = field(default_factory=list)

    def contagem(self) -> Counter[tuple[str, str]]:
        """Quantidade de notas por (unidade, status)."""
        return Counter((linha["unidade"], linha["status"]) for linha in self.linhas)


def montar_linha(campos: dict[str, str], unidade: str, status: str) -> dict[str, str]:
    """Aplica as regras de negócio aos campos brutos e devolve a linha final."""
    numero = normalizar_numero_nf(campos["nfse_numero"])
    # O pedido na descrição é a fonte mais confiável; xPed é o plano B.
    pedido = extrair_pedido_compra(campos["descricao_servico"]) or campos["pedido_xped"]
    linha = {
        **campos,
        "nfse_numero": numero,
        "pedido_compra": pedido,
        "data_emissao": formatar_data(campos["data_emissao"]),
        "unidade": unidade,
        "status": status,
        # Chave de conciliação com o SAP B1: CNPJ do prestador + número da nota.
        "Chave": campos["emit_cnpj"] + numero,
    }
    return {coluna: linha[coluna] for coluna in COLUNAS}


def _listar_xmls(pasta: Path, unidade: str) -> list[Path]:
    if not pasta.is_dir():
        raise PastaNaoEncontrada(pasta, unidade)
    return sorted(p for p in pasta.iterdir() if p.is_file() and p.suffix.lower() == ".xml")


def processar_unidade(unidade: Unidade, resultado: Resultado) -> None:
    """Lê as pastas de uma unidade e acrescenta as notas ao resultado.

    Regra de cancelamento: o robô baixa a nota enquanto ela está autorizada e,
    se for cancelada depois, ela aparece também na pasta de canceladas.
    Toda nota presente nas duas pastas (mesmo nome de arquivo ou mesma chave
    de acesso) é considerada **cancelada** e entra uma única vez na base.
    """
    canceladas = _listar_xmls(unidade.canceladas, unidade.nome)
    aprovadas = _listar_xmls(unidade.aprovadas, unidade.nome)
    nomes_cancelados = {arquivo.name for arquivo in canceladas}

    lidas: list[tuple[Path, str, dict[str, str]]] = []
    # Canceladas primeiro: em caso de duplicidade, a versão cancelada prevalece.
    for status, arquivos in ((CANCELADA, canceladas), (APROVADA, aprovadas)):
        for arquivo in arquivos:
            try:
                lidas.append((arquivo, status, ler_nfse(arquivo)))
            except NFSeInvalida as erro:
                log.warning("Ignorado %s: %s", arquivo.name, erro)
                resultado.ignorados.append((arquivo, str(erro)))

    ids_cancelados = {c["nfse_id"] for _, s, c in lidas if s == CANCELADA and c["nfse_id"]}

    vistas: set[str] = set()
    for arquivo, status, campos in lidas:
        identidade = campos["nfse_id"] or arquivo.name
        if identidade in vistas:
            log.debug("Duplicada, já consolidada: %s", arquivo.name)
            continue
        vistas.add(identidade)

        if arquivo.name in nomes_cancelados or campos["nfse_id"] in ids_cancelados:
            status = CANCELADA
        log.debug("[%s] %s -> %s", unidade.nome, arquivo.name, status)
        resultado.linhas.append(montar_linha(campos, unidade.nome, status))

    log.info(
        "%s: %d XML(s) em Aprovadas, %d em Canceladas",
        unidade.nome,
        len(aprovadas),
        len(canceladas),
    )


def processar(unidades: Iterable[Unidade]) -> Resultado:
    resultado = Resultado()
    for unidade in unidades:
        processar_unidade(unidade, resultado)
    return resultado
