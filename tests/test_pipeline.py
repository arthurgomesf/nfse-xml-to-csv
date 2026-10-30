import pytest

from nfse_extractor.config import Unidade
from nfse_extractor.pipeline import (
    APROVADA,
    CANCELADA,
    COLUNAS,
    PastaNaoEncontrada,
    processar,
)

CHAVE_A = "1" * 50
CHAVE_B = "2" * 50


def test_nota_somente_em_aprovadas(unidade, salvar_xml):
    salvar_xml(unidade.aprovadas, "a.xml", chave=CHAVE_A)

    resultado = processar([unidade])

    [linha] = resultado.linhas
    assert linha["status"] == APROVADA
    assert linha["unidade"] == "Matriz"


def test_nota_nas_duas_pastas_e_cancelada_e_aparece_uma_vez(unidade, salvar_xml):
    salvar_xml(unidade.aprovadas, "a.xml", chave=CHAVE_A)
    salvar_xml(unidade.canceladas, "a.xml", chave=CHAVE_A)

    resultado = processar([unidade])

    [linha] = resultado.linhas
    assert linha["status"] == CANCELADA


def test_cancelamento_pela_chave_mesmo_com_nome_de_arquivo_diferente(unidade, salvar_xml):
    salvar_xml(unidade.aprovadas, "download_1.xml", chave=CHAVE_A)
    salvar_xml(unidade.canceladas, "download_2.xml", chave=CHAVE_A)

    [linha] = processar([unidade]).linhas
    assert linha["status"] == CANCELADA


def test_cancelamento_pelo_nome_quando_xml_cancelado_esta_ilegivel(unidade, salvar_xml):
    salvar_xml(unidade.aprovadas, "a.xml", chave=CHAVE_A)
    salvar_xml(unidade.canceladas, "a.xml", conteudo="<corrompido")

    resultado = processar([unidade])

    [linha] = resultado.linhas
    assert linha["status"] == CANCELADA
    assert len(resultado.ignorados) == 1


def test_mesma_nota_baixada_duas_vezes_nao_duplica(unidade, salvar_xml):
    salvar_xml(unidade.aprovadas, "nota.xml", chave=CHAVE_A)
    salvar_xml(unidade.aprovadas, "nota (1).xml", chave=CHAVE_A)

    assert len(processar([unidade]).linhas) == 1


def test_cancelamento_nao_vaza_entre_unidades(tmp_path, salvar_xml):
    matriz = Unidade("Matriz", tmp_path / "m" / "Aprovadas", tmp_path / "m" / "Canceladas")
    filial = Unidade("Filial", tmp_path / "f" / "Aprovadas", tmp_path / "f" / "Canceladas")
    for pasta in (matriz.aprovadas, matriz.canceladas, filial.aprovadas, filial.canceladas):
        pasta.mkdir(parents=True)
    salvar_xml(matriz.canceladas, "x.xml", chave=CHAVE_A)
    salvar_xml(filial.aprovadas, "x.xml", chave=CHAVE_B)

    resultado = processar([matriz, filial])

    status = {linha["unidade"]: linha["status"] for linha in resultado.linhas}
    assert status == {"Matriz": CANCELADA, "Filial": APROVADA}


def test_xml_invalido_e_ignorado_sem_interromper(unidade, salvar_xml):
    salvar_xml(unidade.aprovadas, "ok.xml", chave=CHAVE_A)
    salvar_xml(unidade.aprovadas, "quebrado.xml", conteudo="<NFSe>")

    resultado = processar([unidade])

    assert len(resultado.linhas) == 1
    [(arquivo, motivo)] = resultado.ignorados
    assert arquivo.name == "quebrado.xml"
    assert "malformado" in motivo


def test_arquivos_que_nao_sao_xml_sao_ignorados(unidade, salvar_xml):
    salvar_xml(unidade.aprovadas, "nota.XML", chave=CHAVE_A)
    (unidade.aprovadas / "leia-me.txt").write_text("não sou nota", "utf-8")

    assert len(processar([unidade]).linhas) == 1


def test_pasta_inexistente_interrompe_com_mensagem_clara(tmp_path):
    fantasma = Unidade("Matriz", tmp_path / "nao_existe", tmp_path / "tambem_nao")

    with pytest.raises(PastaNaoEncontrada, match="Matriz"):
        processar([fantasma])


def test_regras_aplicadas_na_linha_final(unidade, salvar_xml):
    salvar_xml(
        unidade.aprovadas,
        "a.xml",
        chave=CHAVE_A,
        numero="2600000000101",
        dh_emi="2026-03-02T09:14:00-03:00",
        descricao="Serviço avulso sem referência",
        xped="4500777",
    )

    [linha] = processar([unidade]).linhas

    assert list(linha) == list(COLUNAS)
    assert linha["nfse_numero"] == "101"
    assert linha["data_emissao"] == "02/03/2026"
    assert linha["pedido_compra"] == "4500777"  # fallback para o campo xPed
    assert linha["Chave"] == "11222333000181" + "101"
