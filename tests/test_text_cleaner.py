import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import pytest
from text_cleaner import (
    _remove_other_languages,
    _remove_repeated_numbers,
    _remove_artifacts,
    _normalize_structure,
    preprocess_raw_text,
)


# ---------------------------------------------------------------------------
# _remove_other_languages
# ---------------------------------------------------------------------------

class TestRemoveOtherLanguages:
    def test_removes_hiragana_run(self):
        assert _remove_other_languages("안녕けけけ하세요") == "안녕하세요"

    def test_removes_katakana_run(self):
        assert _remove_other_languages("문제アイウ입니다") == "문제입니다"

    def test_removes_multiple_cjk(self):
        # 量和 are 2 consecutive CJK chars → removed; 질 is Hangul → kept
        assert _remove_other_languages("질量和") == "질"

    def test_keeps_single_cjk(self):
        # A lone CJK char (rare but valid marker) must NOT be stripped
        result = _remove_other_languages("제35회 한국어능력一 B형")
        assert "一" in result

    def test_keeps_pure_korean(self):
        text = "가을이 되면서 나뭇잎 색이 점점 붉게"
        assert _remove_other_languages(text) == text

    def test_removes_mixed_block_from_sample(self):
        # Excerpt from the real OCR sample
        noisy = "大楼\n底下\nけけけうううらら"
        result = _remove_other_languages(noisy)
        assert "け" not in result
        assert "う" not in result
        assert "ら" not in result


# ---------------------------------------------------------------------------
# _remove_repeated_numbers
# ---------------------------------------------------------------------------

class TestRemoveRepeatedNumbers:
    def test_removes_space_separated_repetition(self):
        noisy = "15 15 15 15 15 15 15"
        assert _remove_repeated_numbers(noisy).strip() == ""

    def test_removes_newline_separated_repetition(self):
        noisy = "35\n35\n35\n35\n35\n35"
        assert _remove_repeated_numbers(noisy).strip() == ""

    def test_keeps_short_repetition(self):
        # Only 4 repetitions — should NOT be stripped (could be a question range)
        text = "15 15 15 15"
        assert "15" in _remove_repeated_numbers(text)

    def test_keeps_normal_numbers_in_text(self):
        text = "27. 소포를 빨리 보내는 방법"
        assert "27" in _remove_repeated_numbers(text)

    def test_removes_long_number_block_from_sample(self):
        # Simulates the garbage block seen in the real OCR
        noisy = " ".join(["45"] * 20)
        assert _remove_repeated_numbers(noisy).strip() == ""


# ---------------------------------------------------------------------------
# _remove_artifacts
# ---------------------------------------------------------------------------

class TestRemoveArtifacts:
    def test_removes_html_tag(self):
        # Tag AND the trailing OCR junk (={$) should both be removed
        assert _remove_artifacts("고마<img>={$습니다") == "고마습니다"

    def test_removes_long_dash_line(self):
        line = "-" * 30
        assert _remove_artifacts(line).strip() == ""

    def test_removes_equals_line(self):
        line = "=" * 10
        assert _remove_artifacts(line).strip() == ""

    def test_removes_example_marker(self):
        assert _remove_artifacts("＜보　기＞").strip() == ""

    def test_keeps_range_marker(self):
        # ～ (full-width tilde, U+FF5E) used in question ranges must survive
        assert "～" in _remove_artifacts("27～28번")

    def test_keeps_normal_text(self):
        text = "소포를 빨리 보내는 방법"
        assert _remove_artifacts(text) == text


# ---------------------------------------------------------------------------
# _normalize_structure
# ---------------------------------------------------------------------------

class TestNormalizeStructure:
    def test_replaces_circled_numbers(self):
        text = "① 전기 절약\n② 건강 관리\n③ 생활 예절\n④ 환경 보호"
        result = _normalize_structure(text)
        assert "1. 전기 절약" in result
        assert "2. 건강 관리" in result
        assert "3. 생활 예절" in result
        assert "4. 환경 보호" in result

    def test_removes_point_markers(self):
        result = _normalize_structure("27. (3점)\n① 소포를 빨리 보내는 방법")
        assert "(3점)" not in result
        assert "(2점)" not in result

    def test_removes_topik_header_line(self):
        text = "TOPIK I  읽기（31冊～70冊）\n27. 소포를 빨리 보내는 방법"
        result = _normalize_structure(text)
        assert "TOPIK I" not in result
        assert "27." in result

    def test_removes_lone_page_number(self):
        text = "27. 소포를 빨리 보내는 방법\n8\n28. 다음을 읽고"
        result = _normalize_structure(text)
        lines = [l.strip() for l in result.splitlines() if l.strip()]
        assert "8" not in lines

    def test_keeps_numbers_inside_sentences(self):
        text = "① 10시까지 와야 합니다"
        result = _normalize_structure(text)
        assert "10시" in result


# ---------------------------------------------------------------------------
# preprocess_raw_text (integration)
# ---------------------------------------------------------------------------

class TestPreprocessRawText:
    def test_full_pipeline_on_sample_excerpt(self):
        raw = """※ [27～28] 다음을 듣고 물음에 담하십시오.
27. (3점)
① 소포를 빨리 보내는 방법
② 소포를 싸게 보내는 방법
③ 소포를 잘 포장하는 방법
④ 소포를 집에서 보내는 방법
8
TOPIK I  읽기（31冊～70冊）
大楼底下けけけうううらら
15 15 15 15 15 15 15 15 15
<img>={$
-------------------------------------------
"""
        result = preprocess_raw_text(raw)
        assert "1. 소포를 빨리 보내는 방법" in result
        assert "け" not in result
        assert "う" not in result
        assert "(3점)" not in result
        assert "<img>" not in result
        assert "---" not in result
        # No more than two consecutive newlines
        assert "\n\n\n" not in result

    def test_returns_string(self):
        assert isinstance(preprocess_raw_text("테스트"), str)

    def test_empty_input(self):
        assert preprocess_raw_text("") == ""
