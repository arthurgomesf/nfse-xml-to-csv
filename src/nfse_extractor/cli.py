"""Interface de linha de comando."""

from __future__ import annotations

import argparse
import logging
import time
import webbrowser
from pathlib import Path

from . import __version__
from .config import ConfigInvalida, carregar_config
from .exportar import exportar_csv, exportar_sqlite
from .pipeline import APROVADA, CANCELADA, PastaNaoEncontrada, Resultado, processar
from .relatorio import gerar_relatorio

log = logging.getLogger("nfse_extractor")


def _criar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nfse-extractor",
        description="Consolida XMLs de NFS-e (padrão nacional) em uma base CSV para BI.",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=Path("config.toml"),
        help="arquivo de configuração TOML (padrão: ./config.toml)",
    )
    parser.add_argument(
        "-o", "--saida", type=Path, help="caminho do CSV de saída (sobrepõe a configuração)"
    )
    parser.add_argument(
        "--sqlite", type=Path, help="também grava a base em um banco SQLite neste caminho"
    )
    parser.add_argument(
        "--relatorio",
        action="store_true",
        help="ao final, gera um relatório HTML ao lado do CSV e abre no navegador",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="mostra o processamento arquivo a arquivo"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _registrar_resumo(resultado: Resultado) -> None:
    contagem = resultado.contagem()
    unidades = dict.fromkeys(linha["unidade"] for linha in resultado.linhas)

    log.info("%-14s %10s %11s %7s", "Unidade", APROVADA, CANCELADA, "Total")
    for unidade in unidades:
        aprovadas, canceladas = contagem[(unidade, APROVADA)], contagem[(unidade, CANCELADA)]
        log.info("%-14s %10d %11d %7d", unidade, aprovadas, canceladas, aprovadas + canceladas)
    log.info("%-14s %10s %11s %7d", "TOTAL", "", "", len(resultado.linhas))

    if resultado.ignorados:
        log.warning("%d arquivo(s) ignorado(s) por erro de leitura.", len(resultado.ignorados))


def main(argv: list[str] | None = None) -> int:
    args = _criar_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )

    inicio = time.perf_counter()
    try:
        config = carregar_config(args.config)
        resultado = processar(config.unidades)

        saida_csv = args.saida or config.saida_csv
        exportar_csv(resultado.linhas, saida_csv)
        log.info("CSV gravado em %s", saida_csv)

        saida_sqlite = args.sqlite or config.saida_sqlite
        if saida_sqlite:
            exportar_sqlite(resultado.linhas, saida_sqlite)
            log.info("SQLite gravado em %s", saida_sqlite)

        relatorio = None
        if args.relatorio:
            relatorio = gerar_relatorio(resultado, saida_csv.with_suffix(".html"), saida_csv)
            log.info("Relatório gravado em %s", relatorio)
    except (ConfigInvalida, PastaNaoEncontrada) as erro:
        log.error("%s", erro)
        return 1
    except OSError as erro:
        # Ex.: CSV aberto no Excel durante a gravação (arquivo bloqueado no Windows).
        log.error("Falha ao gravar a saída: %s", erro)
        return 1

    _registrar_resumo(resultado)
    log.info("Concluído em %.2fs.", time.perf_counter() - inicio)
    if relatorio:
        webbrowser.open(relatorio.resolve().as_uri())
    return 0
