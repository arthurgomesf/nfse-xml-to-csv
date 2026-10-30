from pathlib import Path

from nfse_extractor.pipeline import COLUNAS, Resultado
from nfse_extractor.relatorio import gerar_relatorio


def _linha(**valores):
    return {coluna: valores.get(coluna, "") for coluna in COLUNAS}


def test_relatorio_resume_valores_e_pontos_de_atencao(tmp_path):
    resultado = Resultado(
        linhas=[
            _linha(
                nfse_numero="101",
                emit_nome="Alfa Ltda",
                unidade="Matriz",
                status="Aprovadas",
                valor_servico="4850.00",
                valor_iss="97.00",
                pedido_compra="4500123",
                data_emissao="02/03/2026",
            ),
            _linha(
                nfse_numero="57",
                emit_nome="Beta Ltda",
                unidade="Matriz",
                status="Aprovadas",
                valor_servico="12300.00",
                valor_iss="356.70",
                data_emissao="05/03/2026",
            ),
            _linha(
                nfse_numero="12",
                emit_nome="Delta Ltda",
                unidade="Filial",
                status="Canceladas",
                valor_servico="2380.50",
                data_emissao="12/03/2026",
            ),
        ],
        ignorados=[(Path("notas/Filial/Aprovadas/quebrado.xml"), "XML malformado")],
    )

    html = gerar_relatorio(resultado, tmp_path / "relatorio.html").read_text("utf-8")

    assert "R$ 17.150,00" in html  # serviços das aprovadas
    assert "R$ 453,70" in html  # ISS das aprovadas
    assert "pedido não identificado" in html  # NFS-e 57 sem pedido
    assert "confirmar que não foi lançada" in html  # NFS-e 12 cancelada
    assert "quebrado.xml" in html  # arquivo ignorado aparece
    tabela = html[html.index('id="notas"') :]
    # mais recentes primeiro
    assert tabela.index("Delta Ltda") < tabela.index("Beta Ltda") < tabela.index("Alfa Ltda")


def test_relatorio_escapa_html_dos_dados(tmp_path):
    resultado = Resultado(
        linhas=[_linha(emit_nome="<script>alert(1)</script>", status="Aprovadas")]
    )

    html = gerar_relatorio(resultado, tmp_path / "r.html").read_text("utf-8")

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_relatorio_vazio(tmp_path):
    html = gerar_relatorio(Resultado(), tmp_path / "r.html").read_text("utf-8")

    assert "Nenhum ponto de atenção" in html
    assert "0 notas" in html
