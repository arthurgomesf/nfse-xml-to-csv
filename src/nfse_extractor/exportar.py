"""Gravação da base consolidada em CSV (padrão) e SQLite (opcional)."""

from __future__ import annotations

import csv
import os
import sqlite3
from collections.abc import Iterable
from contextlib import closing
from pathlib import Path

from .pipeline import COLUNAS

TABELA_SQLITE = "notas_servico"


def exportar_csv(linhas: Iterable[dict[str, str]], destino: Path) -> None:
    """Grava o CSV de forma atômica.

    O arquivo é escrito em um temporário e só então substitui o anterior, então
    o BI nunca lê uma base pela metade. ``utf-8-sig`` (com BOM) garante que
    Excel e ferramentas de BI reconheçam os acentos.
    """
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_name(destino.name + ".tmp")
    try:
        with temporario.open("w", encoding="utf-8-sig", newline="") as arquivo:
            escritor = csv.DictWriter(arquivo, fieldnames=COLUNAS)
            escritor.writeheader()
            escritor.writerows(linhas)
        os.replace(temporario, destino)
    finally:
        temporario.unlink(missing_ok=True)


def exportar_sqlite(
    linhas: Iterable[dict[str, str]], destino: Path, tabela: str = TABELA_SQLITE
) -> None:
    """Recria a tabela no banco SQLite com a base consolidada."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    definicao = ", ".join(f'"{coluna}" TEXT' for coluna in COLUNAS)
    marcadores = ", ".join("?" for _ in COLUNAS)

    # closing() fecha a conexão; o segundo contexto abre a transação (commit ou rollback).
    with closing(sqlite3.connect(destino)) as conexao, conexao:
        conexao.execute(f'DROP TABLE IF EXISTS "{tabela}"')
        conexao.execute(f'CREATE TABLE "{tabela}" ({definicao})')
        conexao.executemany(
            f'INSERT INTO "{tabela}" VALUES ({marcadores})',
            ([linha[coluna] for coluna in COLUNAS] for linha in linhas),
        )
