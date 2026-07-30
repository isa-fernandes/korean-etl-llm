import re 
from typing import Any
import hashlib

def extract_exam_edition(record: dict[str, Any]) -> str | None:
    """Deriva a edicao da prova (ex.: 102nd) a partir de campos disponiveis."""
    folder_name = str(record.get("exam_folder") or "")
    folder_match = re.search(r"(\d+(?:st|nd|rd|th))", folder_name, re.IGNORECASE)
    if folder_match:
        return folder_match.group(1).lower()

    exam_number = str(record.get("exam_number") or "").strip()
    if exam_number.isdigit():
        n = int(exam_number)
        if 10 <= (n % 100) <= 20:
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
        return f"{n}{suffix}"

    return None

def concat_ws_sha256(separador, lista_valores):
    # 1. Replica o comportamento do concat_ws (ignora None e converte para str)
    texto_junto = separador.join(str(x) for x in lista_valores if x is not None)
    
    # 2. Gera o SHA-256 idêntico ao Spark
    return hashlib.sha256(texto_junto.encode('utf-8')).hexdigest()