"""Leitura do XML da NFS-e no leiaute nacional (Emissor Nacional / Sefin Nacional)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

NAMESPACE = "http://www.sped.fazenda.gov.br/nfse"
_NS = {"nfse": NAMESPACE}

# Caminhos relativos à tag <infNFSe>. O prefixo de namespace é adicionado por _xpath().
_DPS = "DPS/infDPS"
_CSERV = f"{_DPS}/serv/cServ"

CAMPOS_XML: dict[str, str] = {
    "nfse_numero": "nNFSe",
    "subst_chave": f"{_DPS}/subst/chSubstda",
    "subst_motivo_codigo": f"{_DPS}/subst/cMotivo",
    "subst_motivo_descricao": f"{_DPS}/subst/xMotivo",
    "nfse_DPS": f"{_DPS}/nDPS",
    "pedido_xped": f"{_DPS}/serv/infoCompl/xPed",
    "data_emissao": f"{_DPS}/dhEmi",
    "emit_cnpj": "emit/CNPJ",
    "emit_nome": "emit/xNome",
    "emit_im": "emit/IM",
    "toma_cnpj": f"{_DPS}/toma/CNPJ",
    "toma_nome": f"{_DPS}/toma/xNome",
    "valor_servico": f"{_DPS}/valores/vServPrest/vServ",
    "base_calculo": "valores/vBC",
    "aliquota_iss": "valores/pAliqAplic",
    "valor_iss": "valores/vISSQN",
    "valor_liquido": "valores/vLiq",
    "codigo_nbs": f"{_CSERV}/cNBS",
    "descricao_servico": f"{_CSERV}/xDescServ",
}


class NFSeInvalida(ValueError):
    """O arquivo não pôde ser interpretado como uma NFS-e do padrão nacional."""


def _xpath(caminho: str) -> str:
    return "/".join(f"nfse:{tag}" for tag in caminho.split("/"))


def _texto(elemento: ET.Element, caminho: str) -> str:
    achado = elemento.find(_xpath(caminho), _NS)
    if achado is None or achado.text is None:
        return ""
    return achado.text.strip()


def ler_nfse(arquivo: Path) -> dict[str, str]:
    """Lê um XML de NFS-e e devolve os campos brutos, sem regras de negócio.

    Campos ausentes no XML (ex.: ``subst`` em notas que não substituem outra)
    retornam string vazia.

    Raises:
        NFSeInvalida: XML malformado ou sem a tag ``<infNFSe>``.
    """
    try:
        raiz = ET.parse(arquivo).getroot()
    except ET.ParseError as erro:
        raise NFSeInvalida(f"XML malformado ({erro})") from erro

    inf = raiz.find("nfse:infNFSe", _NS)
    if inf is None:
        raise NFSeInvalida("tag <infNFSe> não encontrada; não é uma NFS-e do padrão nacional")

    campos = {nome: _texto(inf, caminho) for nome, caminho in CAMPOS_XML.items()}
    # Id = "NFS" + chave de acesso de 50 dígitos
    campos["nfse_id"] = inf.get("Id", "").removeprefix("NFS")
    return campos
