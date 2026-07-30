"""Entrypoint unificado para executar pipelines por camada."""

from __future__ import annotations

import argparse

from pipelines.bronze_pipeline import run_bronze_pipeline
from pipelines.silver_pipeline import run_silver_pipeline
from pipelines.gold_pipeline import run_gold_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Executa pipelines de Bronze, Silver ou Gold."
    )
    parser.add_argument(
        "layer",
        choices=["bronze", "silver", "gold"],
        help="Camada do pipeline a ser executada.",
    )
    parser.add_argument(
        "--exam",
        type=str,
        default=None,
        help="Edição do exame (obrigatória para silver e gold).",
    )
    args = parser.parse_args()

    if args.layer == "bronze":
        run_bronze_pipeline()
    elif args.layer == "silver":
        if args.exam is None:
            parser.error("--exam é obrigatório para a camada silver.")
        run_silver_pipeline(args.exam)
    elif args.layer == "gold":
        if args.exam is None:
            parser.error("--exam é obrigatório para a camada gold.")
        run_gold_pipeline(args.exam)


if __name__ == "__main__":
    main()
