import pytest

from nfse_extractor.regras import extrair_pedido_compra, formatar_data, normalizar_numero_nf


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("Manutenção conforme Pedido de Compra Nº 4500123", "4500123"),
        ("PEDIDO DE COMPRAS 4500124", "4500124"),
        ("pedido compra n. 4500125", "4500125"),
        ("Ordem de Compra nº 4500126", "4500126"),
        ("Número do pedido: 4500127", "4500127"),
        ("Numero do pedido 4500128", "4500128"),
        ("Serviço referente ao pedido 4500129", "4500129"),
        ("Frete - pedido nº 4500130", "4500130"),
        ("PEDIDO: 777", "777"),
        ("Ref. pedido 4500131", "4500131"),
        # Sem palavra-chave: cai no fallback de número com 5+ dígitos
        ("Suporte mensal OC 4500132", "4500132"),
        # Números curtos sem contexto não são pedido
        ("Competência 03/2026, item 12", ""),
        ("", ""),
    ],
)
def test_extrair_pedido_compra(texto, esperado):
    assert extrair_pedido_compra(texto) == esperado


def test_pedido_explicito_tem_prioridade_sobre_numero_solto():
    texto = "Contrato 998877 - conforme pedido de compra nº 4500200"
    assert extrair_pedido_compra(texto) == "4500200"


@pytest.mark.parametrize(
    ("numero", "esperado"),
    [
        ("2600000000123", "123"),  # prefixo de ano + zeros
        ("2700000000123", "123"),  # funciona em qualquer ano, não só 2026
        ("26000000001020", "1020"),  # zeros no meio do sequencial são preservados
        ("000456", "456"),  # curto: só remove zeros à esquerda
        ("2600123", "2600123"),  # curto: não tem prefixo de ano
        (" 0000000789 ", "789"),
        ("", ""),
    ],
)
def test_normalizar_numero_nf(numero, esperado):
    assert normalizar_numero_nf(numero) == esperado


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("2026-03-10T14:32:00-03:00", "10/03/2026"),
        ("2026-12-31T23:59:59", "31/12/2026"),
        ("2026-01-05", "05/01/2026"),
        ("data inválida", "data inválida"),
        ("", ""),
    ],
)
def test_formatar_data(entrada, esperado):
    assert formatar_data(entrada) == esperado
