"""Regras de negócio aplicadas aos campos brutos extraídos do XML.

Funções puras (sem I/O): fáceis de testar e de reaproveitar em outro pipeline.
"""

from __future__ import annotations

import re
from datetime import datetime

# Ordem importa: dos padrões mais específicos para os mais genéricos.
# O texto é convertido para maiúsculas antes da busca.
_N = r"\s*N?[°º\.\:]?\s*"
PADROES_PEDIDO: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p)
    for p in (
        rf"PEDIDO\s+DE\s+COMPRAS?{_N}(\d+)",
        rf"PEDIDO\s+COMPRA{_N}(\d+)",
        rf"ORDEM\s+DE\s+COMPRA{_N}(\d+)",
        rf"N[ÚU]MERO\s+DO\s+PEDIDO{_N}(\d+)",
        rf"REFERENTE\s+AO\s+PEDIDO{_N}(\d+)",
        rf"CONFORME\s+PEDIDO\s+DE\s+COMPRA{_N}(\d+)",
        r"PEDIDO\s*N[°º\.\:]?\s*(\d+)",
        r"PEDIDO\s*:\s*(\d+)",
        r"PEDIDO\s+(\d{5,})",
        # Último recurso: qualquer número isolado com 5+ dígitos.
        r"\b(\d{5,})\b",
    )
)


def extrair_pedido_compra(texto: str) -> str:
    """Encontra o número do pedido de compra em um texto livre.

    Fornecedores raramente preenchem o campo estruturado ``xPed``; o pedido
    costuma vir escrito na descrição do serviço, em formatos variados
    ("Pedido de Compra Nº 4500123", "OC: 4500123", "ref. pedido 4500123"...).

    >>> extrair_pedido_compra("Manutenção conforme pedido de compra nº 4500123")
    '4500123'
    >>> extrair_pedido_compra("Serviço avulso")
    ''
    """
    if not texto:
        return ""
    texto = texto.upper()
    for padrao in PADROES_PEDIDO:
        if achado := padrao.search(texto):
            return achado.group(1)
    return ""


_PREFIXO_ANO = re.compile(r"^\d{2}0+(?=\d)")


def normalizar_numero_nf(numero: str) -> str:
    """Normaliza o número da NFS-e para o formato usado no ERP.

    Alguns municípios devolvem o número com prefixo de ano e zeros à esquerda
    (ex.: ``2600000000123`` → ``123``). Números com mais de 10 dígitos têm o
    prefixo ``AA + zeros`` removido; em seguida, os zeros restantes à esquerda.

    >>> normalizar_numero_nf("2600000000123")
    '123'
    >>> normalizar_numero_nf("000456")
    '456'
    """
    numero = str(numero).strip()
    if len(numero) > 10:
        numero = _PREFIXO_ANO.sub("", numero)
    return numero.lstrip("0")


def formatar_data(data_iso: str) -> str:
    """Converte data ISO 8601 (com fuso) para ``dd/mm/aaaa``.

    Valores fora do padrão são devolvidos sem alteração, para não perder a
    informação.

    >>> formatar_data("2026-03-10T14:32:00-03:00")
    '10/03/2026'
    """
    if not data_iso:
        return ""
    try:
        return datetime.fromisoformat(data_iso).strftime("%d/%m/%Y")
    except ValueError:
        return data_iso
