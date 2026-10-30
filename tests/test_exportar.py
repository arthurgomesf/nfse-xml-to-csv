import csv
import sqlite3
from contextlib import closing

from nfse_extractor.exportar import TABELA_SQLITE, exportar_csv, exportar_sqlite
from nfse_extractor.pipeline import COLUNAS


def _linha(**valores):
    return {coluna: valores.get(coluna, "") for coluna in COLUNAS}


LINHAS = [
    _linha(nfse_numero="101", emit_nome="Alfa Manutenção Ltda", status="Aprovadas"),
    _linha(nfse_numero="12", emit_nome="Delta, Transportes", status="Canceladas"),
]


def test_csv_tem_bom_cabecalho_na_ordem_e_acentos(tmp_path):
    destino = tmp_path / "saida" / "notas.csv"

    exportar_csv(LINHAS, destino)

    bruto = destino.read_bytes()
    assert bruto.startswith(b"\xef\xbb\xbf")  # BOM: Excel/Power BI leem os acentos
    with destino.open(encoding="utf-8-sig", newline="") as f:
        leitor = csv.DictReader(f)
        assert tuple(leitor.fieldnames) == COLUNAS
        lidas = list(leitor)
    assert lidas[0]["emit_nome"] == "Alfa Manutenção Ltda"
    assert lidas[1]["emit_nome"] == "Delta, Transportes"  # vírgula no valor é escapada


def test_csv_substitui_arquivo_anterior_sem_deixar_temporario(tmp_path):
    destino = tmp_path / "notas.csv"
    destino.write_text("conteúdo antigo", "utf-8")

    exportar_csv(LINHAS[:1], destino)

    assert "conteúdo antigo" not in destino.read_text("utf-8-sig")
    assert list(tmp_path.iterdir()) == [destino]


def test_sqlite_recria_tabela_a_cada_execucao(tmp_path):
    banco = tmp_path / "notas.db"

    exportar_sqlite(LINHAS, banco)
    exportar_sqlite(LINHAS[:1], banco)

    with closing(sqlite3.connect(banco)) as conexao:
        linhas = conexao.execute(f"SELECT nfse_numero, status FROM {TABELA_SQLITE}").fetchall()
    assert linhas == [("101", "Aprovadas")]
