"""Entrypoint unificado para executar pipelines por camada."""

from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Executa pipelines de Bronze, Silver ou Gold."
    )
    parser.add_argument(
        "layer",
        choices=["bronze", "silver", "gold"],
        help="Camada do pipeline a ser executada.",
    )
    args = parser.parse_args()

    if args.layer == "bronze":
        from pipelines.bronze_pipeline import run_bronze_pipeline

        run_bronze_pipeline()
    elif args.layer == "silver":
        from pipelines.silver_pipeline import run_silver_pipeline

        run_silver_pipeline()
    elif args.layer == "gold":
        from pipelines.gold_pipeline import run_gold_pipeline

        run_gold_pipeline()


if __name__ == "__main__":
    main()
