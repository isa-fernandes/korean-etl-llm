import re

# ---------------------------------------------------------------------------
# Compiled patterns (module-level avoids re-compiling on every call)
# ---------------------------------------------------------------------------

# Hiragana + Katakana: always noise in a Korean exam
# CJK Unified Ideographs: 2+ consecutive chars are almost always OCR garbage
# (single CJK chars sometimes appear as loan-word markers in Korean text — safe to keep)
_NON_KOREAN_NOISE = re.compile(
    r'[\u3040-\u309F\u30A0-\u30FF]+'   # hiragana / katakana runs
    r'|[\u4E00-\u9FFF\u3400-\u4DBF]+'  # 2+ consecutive CJK
)

# Five or more repetitions of a short number (with any surrounding whitespace/newlines)
# Catches: "15 15 15 15 15 ..." and "35\n35\n35\n35\n35\n..."
_REPEATED_NUMBERS = re.compile(r'(?:\b\d{1,3}\b[\s\n]){5,}\d{1,3}\b')

# HTML tags (plus any non-Korean/non-word debris immediately after), long separator
# lines, ＜보기＞ example markers
_ARTIFACTS = re.compile(
    r'<[^>]+>[^\w\uAC00-\uD7A3\s]*'  # HTML tag + trailing OCR junk e.g. <img>={$
    r'|-{10,}'          # 10+ consecutive dashes
    r'|={5,}'           # 5+ consecutive equals signs
    r'|＜보\s*기＞'     # full-width ＜보기＞ section markers
    r'|\*\s*$'          # trailing asterisk lines (section markers)
    , re.MULTILINE
)

# Circled-number answer markers → plain "N." format the LLM expects
_CIRCLED = {'①': '1.', '②': '2.', '③': '3.', '④': '4.'}
_CIRCLED_RE = re.compile('[①②③④]')

# Score annotations like (3점) or (2점)
_POINT_MARKER = re.compile(r'\(\d점\)')

# Lines that are purely a section header or a lone page number:
#   제35회 한국어능력... | TOPIK I ... | a single number like "8" or "17"
_SECTION_HEADER = re.compile(
    r'^(?:제\d+회\S*.*|TOPIK\s+[IⅠ]+.*|\d{1,2})\s*$',
    re.MULTILINE,
)

# Collapse 3+ consecutive blank lines into exactly two (one empty line between blocks)
_EXCESS_BLANKS = re.compile(r'\n{3,}')


# ---------------------------------------------------------------------------
# Private transformation steps
# ---------------------------------------------------------------------------

def _remove_other_languages(text: str) -> str:
    """Remove hiragana, katakana and multi-character CJK runs (OCR noise)."""
    return _NON_KOREAN_NOISE.sub('', text)


def _remove_repeated_numbers(text: str) -> str:
    """Remove blocks of identically repeated short numbers (OCR table artefacts)."""
    return _REPEATED_NUMBERS.sub('', text)


def _remove_artifacts(text: str) -> str:
    """Remove HTML tags, separator lines and section-example markers."""
    return _ARTIFACTS.sub('', text)


def _normalize_structure(text: str) -> str:
    """Normalise answer markers and strip exam metadata noise."""
    # ①②③④ → 1. 2. 3. 4.
    text = _CIRCLED_RE.sub(lambda m: _CIRCLED[m.group()], text)
    # Drop (2점) / (3점) score labels — not useful for the LLM
    text = _POINT_MARKER.sub('', text)
    # Drop pure section-header / page-number lines
    text = _SECTION_HEADER.sub('', text)
    return text


def _collapse_blank_lines(text: str) -> str:
    """Replace 3+ consecutive newlines with exactly two."""
    return _EXCESS_BLANKS.sub('\n\n', text).strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def preprocess_raw_text(raw_text: str) -> str:
    """Clean and normalise raw OCR text from a TOPIK exam page.

    Pipeline (order matters):
    1. Remove non-Korean script noise (hiragana, katakana, CJK blocks)
    2. Remove repeated-number artefacts from OCR tables
    3. Remove HTML tags and separator lines
    4. Normalise circled answer markers and strip metadata labels
    5. Collapse excess blank lines

    Args:
        raw_text: Raw string as extracted by the OCR model.

    Returns:
        Cleaned string ready to be split into question chunks.
    """
    text = raw_text
    text = _remove_other_languages(text)
    text = _remove_repeated_numbers(text)
    text = _remove_artifacts(text)
    text = _normalize_structure(text)
    text = _collapse_blank_lines(text)
    return text