"""Entrypoint unificado para executar pipelines por camada."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


# Adiciona `src/` ao path para permitir imports absolutos quando o script é
# executado diretamente via `python src/cli/run_pipeline.py <layer>`.
_SRC_ROOT = Path(__file__).resolve().parent.parent
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))


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
