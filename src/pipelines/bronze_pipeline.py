"""Pipeline da camada Bronze: extrai texto de PDFs e persiste Parquet."""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from typing import Any

from pdf2image import convert_from_path
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType

from utils.parquet_io import write_parquet_data
from schemas.bronze.pages_raw_schema import build_pages_raw_schema
from utils.got_model import get_got_model
from utils.hadoop_config import configure_windows_hadoop
from utils.spark_utils import initialize_spark
from utils.text_utils import extract_exam_edition

# Modelo GOT-OCR 2.0 carregado uma vez e reusado para todos os PDFs
_GOT_MODEL = None
_GOT_TOKENIZER = None

SOURCE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "topik_papers")
BRONZE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "bronze")


def extract_pdf_data(filepath: str) -> dict[str, Any]:
    """Extrai texto de cada página via GOT-OCR 2.0.

    Returns:
        Dict com ``page_count`` e ``pages`` (lista de strings, uma por página).
    """
    try:
        global _GOT_MODEL, _GOT_TOKENIZER
        _GOT_MODEL, _GOT_TOKENIZER = get_got_model(_GOT_MODEL, _GOT_TOKENIZER)
        images = convert_from_path(filepath, dpi=150)
        pages: list[str] = []
        with tempfile.TemporaryDirectory() as tmp_dir:
            for i, img in enumerate(images):
                tmp_path = os.path.join(tmp_dir, f"page_{i}.png")
                img.save(tmp_path)
                text = _GOT_MODEL.chat(_GOT_TOKENIZER, tmp_path, ocr_type="ocr")
                pages.append(text or "")
        return {"page_count": len(images), "pages": pages}
    except Exception as exc:
        print(f"  [ERRO] {os.path.basename(filepath)}: {exc}")
        return {"page_count": None, "pages": []}


def get_exam_folders() -> list[str]:
    """Retorna as pastas de prova disponíveis na fonte."""
    if not os.path.isdir(SOURCE_DIR):
        print(f"[ERRO] Pasta de dados não encontrada: {os.path.abspath(SOURCE_DIR)}")
        return []

    return [
        os.path.join(SOURCE_DIR, name)
        for name in os.listdir(SOURCE_DIR)
        if os.path.isdir(os.path.join(SOURCE_DIR, name))
    ]


def build_rows_for_exam_folder(
    folder: str, processed_at: str
) -> tuple[str | None, list[dict[str, Any]]]:
    """Processa uma única edição e retorna (edição, linhas)."""
    folder_name = os.path.basename(folder)
    meta_path = os.path.join(folder, "metadata.json")
    if not os.path.exists(meta_path):
        return None, []

    with open(meta_path, encoding="utf-8") as handle:
        records = json.load(handle)

    rows: list[dict[str, Any]] = []
    edition: str | None = None

    for record in records:
        filename = record.get("filename", "")
        if not filename.lower().endswith(".pdf"):
            continue

        source_pdf_path = os.path.join(folder, filename)
        if not os.path.exists(source_pdf_path):
            continue

        filetype = record.get("file_type", "")
        if filetype.lower() != "test paper":
            continue

        print(f"  Processando: {folder_name}/{filename}")
        pdf_data = extract_pdf_data(source_pdf_path)

        record_edition = extract_exam_edition(
            {"exam_folder": folder_name, "exam_number": record.get("exam_number")}
        )
        if not edition:
            edition = record_edition

        base_row = {
            "exam_id": str(uuid.uuid4()),
            "exam_folder": folder_name,
            "exam_edition": record_edition,
            "filename": filename,
            "label": record.get("label"),
            "exam_number": record.get("exam_number"),
            "exam_year": record.get("exam_year"),
            "exam_month": record.get("exam_month"),
            "exam_session": record.get("exam_session"),
            "topik_format": record.get("topik_format"),
            "level": record.get("level"),
            "section": record.get("section"),
            "file_type": filetype,
            "source_url": record.get("source_url"),
            "page_url": record.get("page_url"),
            "download_date": record.get("download_date"),
            "size_kb": record.get("size_kb"),
            "download_status": record.get("download_status"),
            "source_pdf_path": os.path.abspath(source_pdf_path),
            "processed_at": processed_at,
            "page_count": pdf_data["page_count"],
        }

        for page_num, page_text in enumerate(pdf_data["pages"], start=1):
            rows.append(
                {
                    **base_row,
                    "page_number": page_num,
                    "word_count": len(page_text.split()),
                    "char_count": len(page_text),
                    "raw_text": page_text,
                }
            )

    return edition, rows


def write_exam_parquet(
    spark: SparkSession, schema: StructType, edition: str, rows: list[dict[str, Any]]
) -> None:
    """Salva uma edição por vez em Parquet via Spark."""
    df = spark.createDataFrame(rows, schema=schema)
    output_path = os.path.join(BRONZE_DIR, str(edition))
    write_parquet_data(df, output_path)

    part_files = [
        name
        for name in os.listdir(output_path)
        if name.startswith("part-") and name.endswith(".parquet")
    ]
    if not part_files:
        raise RuntimeError("Spark não gerou part file parquet para a edição.")

    print(f"  [OK] Parquet salvo ({edition}) via Spark: {os.path.abspath(output_path)}")


def run_bronze_pipeline() -> None:
    """Executa o pipeline completo da camada Bronze."""
    print("=" * 60)
    print("  Processando Camada Bronze")
    print("=" * 60)

    exam_folders = sorted(get_exam_folders())
    if not exam_folders:
        return

    print(f"[INFO] {len(exam_folders)} pasta(s) de prova encontrada(s).")

    configure_windows_hadoop()
    spark = initialize_spark("topik-bronze-builder")

    interrupted = False
    try:
        schema = build_pages_raw_schema()
        total_rows = 0
        processed_editions = 0
        failed_editions: list[str] = []

        for folder in exam_folders:
            folder_name = os.path.basename(folder)
            processed_at = datetime.now(timezone.utc).isoformat()
            print(f"\n[EDICAO] {folder_name}")

            edition, rows = build_rows_for_exam_folder(folder, processed_at)
            if not rows:
                print("  [AVISO] Nenhum PDF válido encontrado nesta edição.")
                continue

            edition_name = edition or folder_name
            try:
                write_exam_parquet(spark, schema, edition_name, rows)
                processed_editions += 1
                total_rows += len(rows)
            except KeyboardInterrupt:
                interrupted = True
                print(
                    "\n[AVISO] Execução interrompida pelo usuário. Progresso parcial foi mantido."
                )
                break
            except Exception as exc:
                failed_editions.append(edition_name)
                print(f"  [ERRO] Falha ao salvar {edition_name}: {exc}")

        if processed_editions == 0:
            print("[AVISO] Nenhuma edição gerou Parquet.")
        else:
            print(f"[OK] {processed_editions} edição(ões) salva(s) em Parquet.")
            print(f"[OK] {total_rows} registro(s) escritos no total.")
        if failed_editions:
            print(f"[AVISO] Edições com falha: {', '.join(failed_editions)}")
        if interrupted:
            print("[AVISO] Pipeline interrompido antes de concluir todas as edições.")
    except KeyboardInterrupt:
        print(
            "\n[AVISO] Execução interrompida pelo usuário. Progresso parcial foi mantido."
        )
    finally:
        try:
            spark.stop()
        except Exception as exc:
            print(f"[AVISO] Falha ao encerrar Spark de forma limpa: {exc}")

    print("=" * 60)
    print("  Concluído!")
    print("=" * 60)


def main() -> None:
    run_bronze_pipeline()


if __name__ == "__main__":
    main()
