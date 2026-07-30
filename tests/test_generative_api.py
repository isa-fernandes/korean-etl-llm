import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import pytest
from tools.langchain_functions.generative_api import (
    AnswerObject,
    QuestionObject,
    WrapperQuestions,
    _korean_ratio,
    is_reliable,
    filter_reliable,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_answer(text: str) -> AnswerObject:
    return AnswerObject(answer_text=text, answer_vocabulary_items=[], answer_grammar_patterns=[])


def _make_question(
    question_text: str = "가을이 되면서 나뭇잎 색이 점점 붉게 (        )",
    answers: list[str] | None = None,
    confidence: float = 0.9,
) -> QuestionObject:
    if answers is None:
        answers = ["변해 간다", "변할 뻔했다", "변한 척했다", "변하면 된다"]
    return QuestionObject(
        question_text=question_text,
        answer_options=[_make_answer(a) for a in answers],
        question_vocabulary_items=[],
        question_grammar_patterns=[],
        confidence=confidence,
    )


# ---------------------------------------------------------------------------
# _korean_ratio
# ---------------------------------------------------------------------------

class TestKoreanRatio:
    def test_pure_korean_is_one(self):
        assert _korean_ratio("가나다라") == 1.0

    def test_empty_string_is_zero(self):
        assert _korean_ratio("") == 0.0

    def test_mixed_text_between_zero_and_one(self):
        ratio = _korean_ratio("hello가나다")
        assert 0 < ratio < 1

    def test_pure_latin_is_zero(self):
        assert _korean_ratio("hello world") == 0.0


# ---------------------------------------------------------------------------
# is_reliable
# ---------------------------------------------------------------------------

class TestIsReliable:
    def test_valid_question_passes(self):
        assert is_reliable(_make_question()) is True

    def test_empty_question_text_fails(self):
        q = _make_question(question_text="")
        assert is_reliable(q) is False

    def test_short_question_text_fails(self):
        q = _make_question(question_text="짧다")
        assert is_reliable(q) is False

    def test_wrong_answer_count_fails(self):
        q = _make_question(answers=["변해 간다", "변할 뻔했다", "변한 척했다"])  # only 3
        assert is_reliable(q) is False

    def test_empty_answer_text_fails(self):
        q = _make_question(answers=["변해 간다", "", "변한 척했다", "변하면 된다"])
        assert is_reliable(q) is False

    def test_non_korean_question_fails(self):
        q = _make_question(question_text="This is entirely in English text.")
        assert is_reliable(q) is False

    def test_low_confidence_fails(self):
        q = _make_question(confidence=0.3)
        assert is_reliable(q, min_confidence=0.6) is False

    def test_zero_confidence_is_ignored(self):
        # confidence=0.0 means the model did not fill it in — should not disqualify
        q = _make_question(confidence=0.0)
        assert is_reliable(q, min_confidence=0.6) is True

    def test_high_confidence_passes(self):
        q = _make_question(confidence=0.95)
        assert is_reliable(q, min_confidence=0.6) is True


# ---------------------------------------------------------------------------
# filter_reliable
# ---------------------------------------------------------------------------

class TestFilterReliable:
    def test_all_reliable_returns_all(self):
        wrapper = WrapperQuestions(questions=[_make_question(), _make_question()])
        result = filter_reliable(wrapper)
        assert len(result) == 2

    def test_unreliable_questions_removed(self):
        good = _make_question()
        bad = _make_question(question_text="bad")   # too short
        wrapper = WrapperQuestions(questions=[good, bad, good])
        result = filter_reliable(wrapper)
        assert len(result) == 2

    def test_empty_wrapper_returns_empty(self):
        wrapper = WrapperQuestions(questions=[])
        assert filter_reliable(wrapper) == []

    def test_returns_question_objects(self):
        wrapper = WrapperQuestions(questions=[_make_question()])
        result = filter_reliable(wrapper)
        assert all(isinstance(q, QuestionObject) for q in result)

    def test_custom_min_confidence(self):
        high = _make_question(confidence=0.9)
        low = _make_question(confidence=0.5)
        wrapper = WrapperQuestions(questions=[high, low])
        result = filter_reliable(wrapper, min_confidence=0.8)
        assert len(result) == 1
        assert result[0].confidence == 0.9
