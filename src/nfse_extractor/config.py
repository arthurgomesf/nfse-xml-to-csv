"""Carregamento e validação do arquivo de configuração (TOML)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ConfigInvalida(ValueError):
    """Arquivo de configuração ausente ou com conteúdo inválido."""


@dataclass(frozen=True)
class Unidade:
    """Uma unidade/empresa emissora, com suas pastas de XMLs."""

    nome: str
    aprovadas: Path
    canceladas: Path


@dataclass(frozen=True)
class Config:
    unidades: tuple[Unidade, ...]
    saida_csv: Path
    saida_sqlite: Path | None = None


def carregar_config(arquivo: Path) -> Config:
    """Lê o TOML de configuração.

    Caminhos relativos são resolvidos a partir da pasta do próprio arquivo,
    então a configuração funciona independente do diretório de execução
    (importante quando roda pelo Agendador de Tarefas).
    """
    try:
        dados = tomllib.loads(arquivo.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfigInvalida(f"arquivo de configuração não encontrado: {arquivo}") from None
    except tomllib.TOMLDecodeError as erro:
        raise ConfigInvalida(f"{arquivo}: TOML inválido ({erro})") from None

    base = arquivo.resolve().parent

    def caminho(valor: Any, campo: str) -> Path:
        if not isinstance(valor, str) or not valor.strip():
            raise ConfigInvalida(f"'{campo}' deve ser um caminho (texto não vazio)")
        p = Path(valor).expanduser()
        return p if p.is_absolute() else base / p

    saida = dados.get("saida", {})
    saida_csv = caminho(saida.get("csv"), "saida.csv")
    saida_sqlite = caminho(saida["sqlite"], "saida.sqlite") if "sqlite" in saida else None

    brutas = dados.get("unidades")
    if not brutas:
        raise ConfigInvalida("declare ao menos uma unidade em [[unidades]]")

    unidades: list[Unidade] = []
    for i, u in enumerate(brutas, start=1):
        nome = u.get("nome")
        if not isinstance(nome, str) or not nome.strip():
            raise ConfigInvalida(f"unidade #{i}: campo 'nome' obrigatório")
        if any(existente.nome == nome for existente in unidades):
            raise ConfigInvalida(f"unidade '{nome}' declarada mais de uma vez")

        # Atalho: 'pasta' aponta para um diretório com as subpastas Aprovadas/ e Canceladas/.
        pasta = caminho(u["pasta"], f"{nome}.pasta") if "pasta" in u else None
        aprovadas = u.get("aprovadas") or (pasta and str(pasta / "Aprovadas"))
        canceladas = u.get("canceladas") or (pasta and str(pasta / "Canceladas"))

        unidades.append(
            Unidade(
                nome=nome,
                aprovadas=caminho(aprovadas, f"{nome}.aprovadas"),
                canceladas=caminho(canceladas, f"{nome}.canceladas"),
            )
        )

    return Config(unidades=tuple(unidades), saida_csv=saida_csv, saida_sqlite=saida_sqlite)
