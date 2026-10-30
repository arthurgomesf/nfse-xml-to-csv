import csv
from pathlib import Path

from nfse_extractor.cli import main
from nfse_extractor.config import carregar_config

EXEMPLOS = Path(__file__).resolve().parent.parent / "exemplos"


def _ler_csv(caminho: Path) -> list[dict[str, str]]:
    with caminho.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def test_demo_de_ponta_a_ponta(tmp_path):
    saida = tmp_path / "notas.csv"
    banco = tmp_path / "notas.db"

    codigo = main(["-c", str(EXEMPLOS / "config.toml"), "-o", str(saida), "--sqlite", str(banco)])

    assert codigo == 0
    linhas = _ler_csv(saida)
    assert len(linhas) == 6  # 7 XMLs válidos, 1 duplicado (cancelado) → 6 notas
    status = {(linha["unidade"], linha["nfse_numero"]): linha["status"] for linha in linhas}
    assert status[("Matriz", "12")] == "Canceladas"
    assert status[("Matriz", "101")] == "Aprovadas"
    assert banco.exists()


def test_opcao_relatorio_gera_html_e_abre_no_navegador(tmp_path, monkeypatch):
    abertos = []
    monkeypatch.setattr("webbrowser.open", abertos.append)
    saida = tmp_path / "notas.csv"

    assert main(["-c", str(EXEMPLOS / "config.toml"), "-o", str(saida), "--relatorio"]) == 0

    relatorio = tmp_path / "notas.html"
    assert relatorio.exists()
    assert abertos == [relatorio.resolve().as_uri()]


def test_sem_opcao_relatorio_nada_abre(tmp_path, monkeypatch):
    abertos = []
    monkeypatch.setattr("webbrowser.open", abertos.append)

    main(["-c", str(EXEMPLOS / "config.toml"), "-o", str(tmp_path / "notas.csv")])

    assert abertos == []
    assert not (tmp_path / "notas.html").exists()


def test_config_inexistente_retorna_erro(tmp_path, caplog):
    assert main(["-c", str(tmp_path / "nao_existe.toml")]) == 1
    assert "não encontrado" in caplog.text


def test_pasta_inexistente_nao_sobrescreve_saida(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(
        '[saida]\ncsv = "notas.csv"\n[[unidades]]\nnome = "X"\npasta = "sumiu"\n', "utf-8"
    )
    saida = tmp_path / "notas.csv"
    saida.write_text("base de ontem", "utf-8")

    assert main(["-c", str(config)]) == 1
    assert saida.read_text("utf-8") == "base de ontem"


def test_config_resolve_caminhos_relativos_a_partir_do_arquivo():
    config = carregar_config(EXEMPLOS / "config.toml")

    matriz = config.unidades[0]
    assert matriz.aprovadas == EXEMPLOS / "notas" / "Matriz" / "Aprovadas"
    assert matriz.canceladas == EXEMPLOS / "notas" / "Matriz" / "Canceladas"
    assert config.saida_csv == EXEMPLOS / "saida" / "notas_servico.csv"
    assert config.saida_sqlite is None
