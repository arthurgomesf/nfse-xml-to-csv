import pytest

from nfse_extractor.leitor import NFSeInvalida, ler_nfse


def test_le_campos_principais(tmp_path, salvar_xml):
    arquivo = salvar_xml(tmp_path, "nota.xml", chave="1" * 50)

    campos = ler_nfse(arquivo)

    assert campos["nfse_id"] == "1" * 50  # prefixo "NFS" removido
    assert campos["nfse_numero"] == "2600000000101"
    assert campos["emit_cnpj"] == "11222333000181"
    assert campos["emit_nome"] == "Alfa Manutenção Ltda"
    assert campos["toma_nome"] == "Indústria Exemplo S.A."
    assert campos["valor_servico"] == "4850.00"
    assert campos["valor_iss"] == "97.00"
    assert campos["codigo_nbs"] == "120013100"
    assert campos["nfse_DPS"] == "845"


def test_campos_opcionais_ausentes_viram_texto_vazio(tmp_path, salvar_xml):
    campos = ler_nfse(salvar_xml(tmp_path, "nota.xml"))

    assert campos["subst_chave"] == ""
    assert campos["subst_motivo_codigo"] == ""
    assert campos["pedido_xped"] == ""


def test_le_substituicao_e_xped(tmp_path, salvar_xml):
    campos = ler_nfse(salvar_xml(tmp_path, "nota.xml", subst=True, xped="4500999"))

    assert campos["subst_chave"] == "CHAVE_ANTIGA"
    assert campos["subst_motivo_codigo"] == "99"
    assert campos["pedido_xped"] == "4500999"


def test_xml_malformado(tmp_path, salvar_xml):
    arquivo = salvar_xml(tmp_path, "quebrado.xml", conteudo="<NFSe><infNFSe>")
    with pytest.raises(NFSeInvalida, match="malformado"):
        ler_nfse(arquivo)


def test_xml_que_nao_e_nfse(tmp_path, salvar_xml):
    arquivo = salvar_xml(tmp_path, "evento.xml", conteudo="<evento><id>1</id></evento>")
    with pytest.raises(NFSeInvalida, match="infNFSe"):
        ler_nfse(arquivo)
