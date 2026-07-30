"""Entrypoint legado: delega para o pipeline de Silver."""

from __future__ import annotations

from pipelines.silver_pipeline import main as silver_main


def main() -> None:
    silver_main()


if __name__ == "__main__":
    main()
