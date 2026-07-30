"""
Script de web scraping para baixar as provas do TOPIK do site topikguide.com.

Fluxo:
  1. Acessa a página de índice e coleta links das provas, identificando se
     cada uma é de formato novo ("New Format") ou antigo ("Old Format").
  2. Em cada página de prova, extrai os links de download com seus metadados
     (anchor text, nível, seção, tipo de arquivo, ano).
  3. Baixa cada arquivo em subpastas organizadas por prova.
  4. Gera um arquivo index.json com todos os metadados coletados.

Requisitos:
  pip install requests beautifulsoup4
"""

import json
import os
import re
import time
from datetime import date
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# ─── Configurações ──────────────────────────────────────────────────────────────

# Página principal com todos os links das provas anteriores
INDEX_URL = "https://www.topikguide.com/previous-papers/"

# Pasta raiz onde os arquivos serão salvos (camada Bronze)
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "bronze", "topik_papers")

# Pausa entre requisições para não sobrecarregar o servidor (segundos)
DELAY = 1.5

# Tipos de arquivo a baixar
DOWNLOAD_EXTENSIONS = (".pdf", ".mp3")

# Nomes dos meses em inglês (como aparecem nas páginas do site)
MONTH_NAMES = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
]

# Cabeçalho para simular um navegador comum
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# ─── Funções ────────────────────────────────────────────────────────────────────

def get_page(url: str) -> BeautifulSoup | None:
    """Faz GET em uma URL e retorna o objeto BeautifulSoup, ou None em erro."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except requests.RequestException as e:
        print(f"  [ERRO] Falha ao acessar {url}: {e}")
        return None


def sanitize_folder_name(page_url: str) -> str:
    """
    Converte a URL da página de prova num nome de pasta legível.
    Exemplo: '.../download-102nd-topik-test-papers/' → '102nd-topik-test-papers'
    """
    path = urlparse(page_url).path.strip("/")
    folder = re.sub(r"^download-", "", path.split("/")[-1])
    # Substitui caracteres inválidos para nomes de pasta no Windows
    folder = re.sub(r'[<>:"/\\|?*]', "_", folder)
    return folder or "unknown"


def parse_exam_number(text: str) -> str | None:
    """Extrai o número ordinal da prova de um texto. Ex: '102nd' → '102'."""
    m = re.search(r"(\d+)(?:st|nd|rd|th)", text, re.IGNORECASE)
    return m.group(1) if m else None


def parse_exam_year(soup: BeautifulSoup) -> str | None:
    """
    Extrai o ano da prova do título da página.
    Ex: 'Download 102nd (Year 2025) TOPIK Test Papers' → '2025'
    """
    h1 = soup.find("h1")
    if h1:
        m = re.search(r"Year\s+(\d{4})", h1.get_text(), re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def parse_exam_month(soup: BeautifulSoup) -> tuple[str | None, int | None]:
    """
    Extrai o mês da prova buscando nomes de meses no h1, h2 e primeiros
    parágrafos da página.
    Retorna (nome_do_mes, numero_do_mes) ou (None, None).
    """
    # Coleta texto dos elementos mais relevantes da página
    candidates = []
    for tag in ("h1", "h2", "title"):
        el = soup.find(tag)
        if el:
            candidates.append(el.get_text())
    for p in soup.find_all("p")[:8]:
        candidates.append(p.get_text())

    text = " ".join(candidates).lower()

    for i, month in enumerate(MONTH_NAMES, start=1):
        if month in text:
            return month.capitalize(), i
    return None, None


def get_exam_session(month_num: int | None) -> str | None:
    """
    Deriva a sessão do TOPIK a partir do número do mês.
      Meses 3–6  → 'Spring'  (aplicações de abril/maio)
      Meses 9–12 → 'Fall'    (aplicações de outubro/novembro)
    """
    if month_num is None:
        return None
    if 3 <= month_num <= 6:
        return "Spring"
    if 9 <= month_num <= 12:
        return "Fall"
    return "Other"


def parse_file_metadata(label: str) -> dict:
    """
    Extrai metadados estruturados do anchor text de um link de arquivo.

    Exemplos de labels:
      '102nd TOPIK I - TEST PAPER - READING'
      '102nd TOPIK I - READING ANSWER KEYS'
      '102nd TOPIK I - LISTENING AUDIO FILE'
      '102nd TOPIK II - WRITING ANSWER KEYS'
      '102nd TOPIK II - LISTENING TRANSCRIPT'
    """
    label_upper = label.strip().upper()

    # Nível: TOPIK I ou TOPIK II
    level = None
    if "TOPIK II" in label_upper:
        level = "TOPIK II"
    elif "TOPIK I" in label_upper:
        level = "TOPIK I"

    # Seção: READING / LISTENING / WRITING
    section = None
    for s in ("READING", "LISTENING", "WRITING"):
        if s in label_upper:
            section = s.capitalize()
            break

    # Tipo de arquivo
    file_type = None
    for ft in ("TEST PAPER", "ANSWER KEYS", "AUDIO FILE", "TRANSCRIPT"):
        if ft in label_upper:
            file_type = ft.title()
            break

    return {"level": level, "section": section, "file_type": file_type}


# ─── Funções de scraping ────────────────────────────────────────────────────────

def get_paper_page_links(index_url: str) -> list[dict]:
    """
    Extrai da página de índice os links para cada página de prova individual,
    identificando se pertencem ao formato Novo ou Antigo.

    Retorna lista de dicts: {url, format}
    """
    soup = get_page(index_url)
    if not soup:
        return []

    results = []
    seen_urls = set()

    # Texto dos headings que marcam a mudança de seção na página
    FORMAT_MARKERS = {
        "new format": "New Format",
        "old format": "Old Format",
    }

    current_format = "New Format"  # A primeira seção da página é "New Format"

    # Percorre todos os elementos em ordem do documento para rastrear
    # em qual seção (novo/antigo) cada link se encontra
    for element in soup.find_all(["h2", "h3", "h4", "p", "a"]):
        tag = element.name

        # Atualiza o formato corrente ao encontrar um heading de seção
        if tag in ("h2", "h3", "h4"):
            text = element.get_text(strip=True).lower()
            for marker, fmt in FORMAT_MARKERS.items():
                if marker in text:
                    current_format = fmt
                    break

        # Coleta links que apontam para páginas de prova
        if tag == "a":
            href = element.get("href", "")
            is_paper_page = re.search(r"topikguide\.com/(?:download-)?\d+", href)
            if is_paper_page:
                full_url = urljoin(index_url, href).split("?")[0].split("#")[0]
                if full_url not in seen_urls:
                    seen_urls.add(full_url)
                    results.append({"url": full_url, "format": current_format})

    print(f"[INFO] {len(results)} páginas de prova encontradas.")
    return results


def get_file_links(page_url: str) -> list[dict]:
    """
    Extrai de uma página de prova todos os links de arquivos (PDF/MP3)
    com seus metadados (label, nível, seção, tipo, ano).

    Retorna lista de dicts com os metadados de cada arquivo.
    """
    soup = get_page(page_url)
    if not soup:
        return []

    exam_year = parse_exam_year(soup)
    exam_month, month_num = parse_exam_month(soup)
    exam_session = get_exam_session(month_num)
    seen_urls = set()
    file_entries = []

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.lower().endswith(DOWNLOAD_EXTENSIONS):
            continue

        full_url = urljoin(page_url, href)
        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)

        label = a.get_text(strip=True)
        filename = os.path.basename(urlparse(full_url).path)
        exam_number = parse_exam_number(label) or parse_exam_number(filename)

        meta = parse_file_metadata(label)

        file_entries.append({
            "filename":    filename,
            "label":       label,
            "exam_number": exam_number,
            "exam_year":   exam_year,
            "exam_month":  exam_month,
            "exam_session": exam_session,
            "level":       meta["level"],
            "section":     meta["section"],
            "file_type":   meta["file_type"],
            "source_url":  full_url,
            "page_url":    page_url,
        })

    return file_entries


def download_file(url: str, dest_folder: str) -> dict:
    """
    Faz o download de um arquivo e salva em dest_folder.
    Retorna um dict com status ('ok', 'skip', 'error') e tamanho em KB.
    """
    filename = os.path.basename(urlparse(url).path)
    filepath = os.path.join(dest_folder, filename)

    if os.path.exists(filepath):
        print(f"    [SKIP] Já existe: {filename}")
        return {"status": "skip", "size_kb": round(os.path.getsize(filepath) / 1024, 1)}

    try:
        resp = requests.get(url, headers=HEADERS, timeout=60, stream=True)
        resp.raise_for_status()

        os.makedirs(dest_folder, exist_ok=True)
        with open(filepath, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        size_kb = os.path.getsize(filepath) / 1024
        print(f"    [OK] {filename}  ({size_kb:.0f} KB)")
        return {"status": "ok", "size_kb": round(size_kb, 1)}

    except requests.RequestException as e:
        print(f"    [ERRO] Falha ao baixar {url}: {e}")
        return {"status": "error", "size_kb": 0}


# ─── Execução principal ──────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  TOPIK Paper Downloader — topikguide.com")
    print("=" * 60)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Passo 1: Obtém todos os links de páginas de prova com seus formatos
    paper_pages = get_paper_page_links(INDEX_URL)
    if not paper_pages:
        print("[ERRO] Nenhuma página de prova encontrada. Encerrando.")
        return

    total_files = 0

    # Passo 2: Para cada página de prova, coleta metadados e baixa os arquivos
    for i, page in enumerate(paper_pages, start=1):
        page_url = page["url"]
        paper_format = page["format"]
        folder_name = sanitize_folder_name(page_url)
        dest_folder = os.path.join(OUTPUT_DIR, folder_name)

        print(f"\n[{i}/{len(paper_pages)}] {folder_name}  [{paper_format}]")
        print(f"  URL: {page_url}")

        # Passo 3: Coleta links e metadados dos arquivos na página
        time.sleep(DELAY)
        file_entries = get_file_links(page_url)

        if not file_entries:
            print("  [AVISO] Nenhum arquivo encontrado nesta página.")
            continue

        print(f"  {len(file_entries)} arquivo(s) encontrado(s).")

        exam_records = []

        # Passo 4: Baixa cada arquivo e acumula os metadados da prova
        for entry in file_entries:
            time.sleep(DELAY)
            result = download_file(entry["source_url"], dest_folder)
            total_files += 1

            exam_records.append({
                "filename":        entry["filename"],
                "label":           entry["label"],
                "exam_number":     entry["exam_number"],
                "exam_year":       entry["exam_year"],
                "exam_month":      entry["exam_month"],
                "exam_session":    entry["exam_session"],
                "topik_format":    paper_format,          # "New Format" ou "Old Format"
                "level":           entry["level"],
                "section":         entry["section"],
                "file_type":       entry["file_type"],
                "source_url":      entry["source_url"],
                "page_url":        entry["page_url"],
                "download_date":   str(date.today()),
                "size_kb":         result["size_kb"],
                "download_status": result["status"],
            })

        # Passo 5: Salva metadata.json dentro da pasta de cada prova
        os.makedirs(dest_folder, exist_ok=True)
        meta_path = os.path.join(dest_folder, "metadata.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(exam_records, f, ensure_ascii=False, indent=2)
        print(f"  [JSON] metadata.json salvo ({len(exam_records)} registro(s))")

    print("\n" + "=" * 60)
    print(f"  Concluído! {total_files} arquivo(s) processado(s).")
    print(f"  Arquivos salvos em: {os.path.abspath(OUTPUT_DIR)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
