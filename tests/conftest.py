from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from nfse_extractor.config import Unidade


def montar_xml(
    *,
    chave: str = "9" * 50,
    numero: str = "2600000000101",
    emit_cnpj: str = "11222333000181",
    descricao: str = "Manutenção preventiva conforme Pedido de Compra Nº 4500123",
    xped: str | None = None,
    subst: bool = False,
    dh_emi: str = "2026-03-02T09:14:00-03:00",
) -> str:
    """XML mínimo de NFS-e no leiaute nacional, com os campos que o extrator usa."""
    bloco_subst = (
        "<subst><chSubstda>CHAVE_ANTIGA</chSubstda><cMotivo>99</cMotivo>"
        "<xMotivo>Correção do valor</xMotivo></subst>"
        if subst
        else ""
    )
    bloco_xped = f"<infoCompl><xPed>{xped}</xPed></infoCompl>" if xped else ""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<NFSe xmlns="http://www.sped.fazenda.gov.br/nfse" versao="1.00">
  <infNFSe Id="NFS{chave}">
    <nNFSe>{numero}</nNFSe>
    <emit><CNPJ>{emit_cnpj}</CNPJ><IM>1234567</IM><xNome>Alfa Manutenção Ltda</xNome></emit>
    <valores>
      <vBC>4850.00</vBC><pAliqAplic>2.00</pAliqAplic><vISSQN>97.00</vISSQN><vLiq>4850.00</vLiq>
    </valores>
    <DPS versao="1.00">
      <infDPS Id="DPS0001">
        <dhEmi>{dh_emi}</dhEmi>
        <nDPS>845</nDPS>
        {bloco_subst}
        <toma><CNPJ>12345678000195</CNPJ><xNome>Indústria Exemplo S.A.</xNome></toma>
        <serv>
          <cServ><cTribNac>140101</cTribNac><xDescServ>{descricao}</xDescServ>
          <cNBS>120013100</cNBS></cServ>
          {bloco_xped}
        </serv>
        <valores><vServPrest><vServ>4850.00</vServ></vServPrest></valores>
      </infDPS>
    </DPS>
  </infNFSe>
</NFSe>
"""


@pytest.fixture
def unidade(tmp_path: Path) -> Unidade:
    """Unidade com as pastas Aprovadas/ e Canceladas/ vazias."""
    u = Unidade("Matriz", tmp_path / "Aprovadas", tmp_path / "Canceladas")
    u.aprovadas.mkdir()
    u.canceladas.mkdir()
    return u


@pytest.fixture
def salvar_xml() -> Callable[..., Path]:
    """Grava um XML de NFS-e em ``pasta/nome`` e devolve o caminho."""

    def _salvar(pasta: Path, nome: str, conteudo: str | None = None, **campos) -> Path:
        arquivo = pasta / nome
        arquivo.write_text(conteudo if conteudo is not None else montar_xml(**campos), "utf-8")
        return arquivo

    return _salvar
