import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import pytest
from question_splitter import split_into_question_chunks, QuestionChunk

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SECTION_GROUP = """\
※ [27～28] 다음을 듣고 물음에 담하십시오.
27.
1. 소포를 빨리 보내는 방법
2. 소포를 싸게 보내는 방법
3. 소포를 잘 포장하는 방법
4. 소포를 집에서 보내는 방법
28.
1. 여자는 부산에서 소포를 보냅니다.
2. 여자는 빨리 소포를 받고 싶어 합니다.
3. 여자는 소포를 특급으로 보냅니다.
4. 여자는 내일 오전에 소포를 받을 겁니다.
"""

TWO_INDIVIDUAL = """\
38.
1. 자주
2. 제일
3. 아주
4. 아까
39.
1. 자르고
2. 나오고
3. 가지고
4. 마시고
"""

MIXED = SECTION_GROUP + "\n" + TWO_INDIVIDUAL


# ---------------------------------------------------------------------------
# Basic splitting
# ---------------------------------------------------------------------------

class TestSplitIndividualQuestions:
    def test_returns_list(self):
        result = split_into_question_chunks(TWO_INDIVIDUAL)
        assert isinstance(result, list)

    def test_two_questions_produce_two_chunks(self):
        result = split_into_question_chunks(TWO_INDIVIDUAL)
        assert len(result) == 2

    def test_chunk_contains_question_text(self):
        result = split_into_question_chunks(TWO_INDIVIDUAL)
        assert any("38." in c.text for c in result)
        assert any("39." in c.text for c in result)

    def test_individual_chunks_are_not_groups(self):
        result = split_into_question_chunks(TWO_INDIVIDUAL)
        assert all(not c.is_group for c in result)

    def test_question_numbers_extracted(self):
        result = split_into_question_chunks(TWO_INDIVIDUAL)
        all_numbers = [n for c in result for n in c.question_numbers]
        assert 38 in all_numbers
        assert 39 in all_numbers


class TestSplitSectionGroup:
    def test_section_produces_one_chunk(self):
        result = split_into_question_chunks(SECTION_GROUP)
        assert len(result) == 1

    def test_section_chunk_is_group(self):
        result = split_into_question_chunks(SECTION_GROUP)
        assert result[0].is_group is True

    def test_section_question_numbers_correct(self):
        result = split_into_question_chunks(SECTION_GROUP)
        assert result[0].question_numbers == [27, 28]

    def test_section_chunk_contains_both_questions(self):
        chunk = split_into_question_chunks(SECTION_GROUP)[0]
        assert "27." in chunk.text
        assert "28." in chunk.text


class TestSplitMixed:
    def test_mixed_produces_three_chunks(self):
        # 1 group (27-28) + 2 individual (38, 39)
        result = split_into_question_chunks(MIXED)
        assert len(result) == 3

    def test_first_chunk_is_group(self):
        result = split_into_question_chunks(MIXED)
        groups = [c for c in result if c.is_group]
        assert len(groups) == 1

    def test_individual_chunks_after_group(self):
        result = split_into_question_chunks(MIXED)
        individuals = [c for c in result if not c.is_group]
        assert len(individuals) == 2


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_string_returns_empty_list(self):
        assert split_into_question_chunks("") == []

    def test_whitespace_only_returns_empty_list(self):
        assert split_into_question_chunks("   \n\n  ") == []

    def test_no_questions_returns_empty_list(self):
        assert split_into_question_chunks("이것은 질문이 아닙니다.") == []

    def test_single_question(self):
        text = "40.\n1. 이 광고는 맞습니다.\n2. 이 광고는 틀립니다.\n3. 모르겠습니다.\n4. 없습니다."
        result = split_into_question_chunks(text)
        assert len(result) == 1
        assert result[0].question_numbers == [40]

    def test_chunk_text_is_non_empty(self):
        result = split_into_question_chunks(TWO_INDIVIDUAL)
        assert all(c.text.strip() for c in result)
