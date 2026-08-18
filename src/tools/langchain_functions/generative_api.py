import logging
import re
import time
from typing import Literal, Optional

import json_repair
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_ollama import OllamaLLM
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class AnswerObject(BaseModel):
    answer_text: str = Field(description="the full answer")
    answer_vocabulary_items: list[str] = Field(
        description="list of key Korean vocabulary that is only found in the answer text, return empty if answer text does not contain relevant vocabulary"
    )
    answer_grammar_patterns: list[str] = Field(
        description="list of grammar structures that is only found in the answer text, return empty if answer text does not contain relevant grammar"
    )


class QuestionObject(BaseModel):
    question_text: str = Field(description="the full question")
    question_stimulus: Optional[str] = Field(
        default=None,
        description="a single text or stimulus applies to two or more consecutive questions.",
    )
    answer_options: list[AnswerObject] = Field(description="list of choices")
    question_type: Optional[
        Literal["vocabulary", "grammar", "reading comprehension", "image dependent"]
    ] = Field(
        default=None,
        description="the type of question, can be vocabulary, grammar, reading comprehension, etc",
    )
    question_vocabulary_items: list[str] = Field(
        description="list of key Korean words in problem statement"
    )
    question_grammar_patterns: list[str] = Field(
        description="list of grammar structures in problem statement"
    )
    topic: Optional[str] = Field(
        default=None, max_length=30, description="thematic context"
    )
    difficulty_level: Optional[Literal["easy", "medium", "hard"]] = Field(
        default=None,
        description="the classification of the question between easy, medium, and hard",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="0 to 1 score of how complete and well-formed this question is",
    )


class WrapperQuestions(BaseModel):
    questions: list[QuestionObject] = Field(
        description="list of questions extracted from PDF"
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _korean_ratio(text: str) -> float:
    """Fraction of non-whitespace characters that are Hangul syllables.

    Whitespace is excluded from the denominator so that fill-in-the-blank
    questions (e.g. "붉게 (        )") are not penalised by the blank spaces.
    """
    non_space = [c for c in text if not c.isspace()]
    korean = sum(1 for c in non_space if "\uac00" <= c <= "\ud7a3")
    return korean / max(len(non_space), 1)


def is_reliable(q: QuestionObject, min_confidence: float = 0.6) -> bool:
    """Return True if *q* passes all structural quality checks.

    Checks (all must pass):
    - question_text is non-empty and longer than 5 chars
    - exactly 4 answer options present
    - every answer has non-empty text
    - question text is at least 50 % Korean characters
    - LLM-reported confidence >= min_confidence (when the model filled it in)
    """
    if not (q.question_text and len(q.question_text) > 5):
        return False
    if len(q.answer_options) != 4:
        return False
    if not all(a.answer_text for a in q.answer_options):
        return False
    if _korean_ratio(q.question_text) <= 0.5:
        return False
    # Only gate on model confidence when the model actually set it (> 0)
    if q.confidence > 0 and q.confidence < min_confidence:
        return False
    return True


def filter_reliable(
    wrapper: WrapperQuestions,
    min_confidence: float = 0.6,
) -> list[QuestionObject]:
    """Return only the questions from *wrapper* that pass :func:`is_reliable`."""
    return [q for q in wrapper.questions if is_reliable(q, min_confidence)]


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

prompt_template_str = """
You are a Korean language expert and TOPIK exam analyst.

Your task is to extract structured information from a TOPIK exam text.
The input normally arrives as semi-structured Markdown, where each question is delimited by a
"## Question <N>" heading and contains up to three sub-sections:
- "### Question Stimulus": the general instruction/prompt for the question (may be identical across a
  consecutive range of questions, e.g. [9~12], since they share one instruction).
- "### Reference Image" or "### Reference Text": the passage, notice, poster, or table/graph data the
  question is based on.
- "### Answers": the 4 answer choices, labeled either with arabic numerals (1. 2. 3. 4.) or circled
  numerals (①②③④).
Occasionally the input may instead arrive as continuous text without any Markdown headers; the same
question/stimulus/answers structure still applies in that case, just without explicit section markers.
The input text may still contain OCR spelling mistakes; if you are certain that it is a spelling mistake, correct it.

Rules:
- Treat each "## Question <N>" block as a separate question. Consecutive blocks may repeat the exact same
  "### Question Stimulus" text because they share one instruction across a range — still extract each block
  as its own independent QuestionObject.
- Map the "### Question Stimulus" section content to question_stimulus.
- Map the "### Reference Image" / "### Reference Text" section content to question_text. Transcribe it into
  clear, coherent Korean prose that preserves every fact, label, and number, but strip Markdown/HTML syntax
  (e.g. "#", "*", "**", table tags) from the extracted text. If the section contains a table or flattened
  chart data, restate it as a plain-language comparison sentence (e.g. "가격 48%, 여행 상품의 다양성 25%...").
- Extract EVERY numbered or circled answer choice as a separate AnswerObject with its full text (excluding the numeral/circle marker itself).
- For question_type: use "grammar" if the options contain different grammar patterns, "vocabulary" if asking about word meaning or options contain different vocabulary to be used to complete the sentence, "reading comprehension" if asking about a passage, "image dependent" if they refer to an image, poster, table, or graph.
- For difficulty_level: "easy" for basic sentences, "medium" for intermediate grammar/vocab, "hard" for complex structures.
- For topic: infer a short thematic label from the question content (e.g., "계절 변화", "건강", "광고").
- For question_vocabulary_items: list important nouns/verbs/adjectives from the question statement only (not from answers).
- For question_grammar_patterns: list grammar endings or patterns from the question (e.g., "-면서", "-게").
- For answer_vocabulary_items: list important words found ONLY in that specific answer text.
- For answer_grammar_patterns: list grammar patterns found ONLY in that specific answer text (e.g., "-아/어 가다", "-(으)ㄹ 뻔했다").
- For confidence scoring, lower the confidence according to the number of spelling mistakes or if the questions/answers do not make sense.
- Return ONLY valid JSON. No explanation, no extra text.

Output format:
{format_instructions}

<examples>
<example_1>
<input>
## Question 1
### Reference Text

가을이 되면서 나뭇잎 색이 점점 붉게 (        )
### Answers

1. 변해 간다
2. 변할 뻔했다
3. 변한 척했다
4. 변하면 된다

## Question 2
### Reference Text

달리기, 지금 바로 시작하세요. 활기찬 내일이 기다립니다.
### Answers

1. 전기 절약
2. 건강 관리
3. 생활 예절
4. 환경 보호
</input>

<output>
{{
  "questions": [
    {{
      "question_text": "가을이 되면서 나뭇잎 색이 점점 붉게 (        )",
      "question_stimulus": None,
      "answer_options": [
        {{"answer_text": "변해 간다", "answer_vocabulary_items": [], "answer_grammar_patterns": ["-아/어 가다"]}},
        {{"answer_text": "변할 뻔했다", "answer_vocabulary_items": [], "answer_grammar_patterns": ["-(으)ㄹ 뻔했다"]}},
        {{"answer_text": "변한 척했다", "answer_vocabulary_items": [], "answer_grammar_patterns": ["-은/는 척하다"]}},
        {{"answer_text": "변하면 된다", "answer_vocabulary_items": [], "answer_grammar_patterns": ["-(으)면 되다"]}}
      ],
      "question_type": "grammar",
      "question_vocabulary_items": ["가을", "나뭇잎", "붉다"],
      "question_grammar_patterns": ["-면서", "-게"],
      "topic": "계절 변화",
      "difficulty_level": "medium",
      "confidence": 0.95
    }},
    {{
      "question_text": "달리기, 지금 바로 시작하세요. 활기찬 내일이 기다립니다.",
      "question_stimulus": None,
      "answer_options": [
        {{"answer_text": "전기 절약", "answer_vocabulary_items": ["전기", "절약"], "answer_grammar_patterns": []}},
        {{"answer_text": "건강 관리", "answer_vocabulary_items": ["건강", "관리"], "answer_grammar_patterns": []}},
        {{"answer_text": "생활 예절", "answer_vocabulary_items": ["생활", "예절"], "answer_grammar_patterns": []}},
        {{"answer_text": "환경 보호", "answer_vocabulary_items": ["환경", "보호"], "answer_grammar_patterns": []}}
      ],
      "question_type": "reading comprehension",
      "question_vocabulary_items": ["달리기", "활기차다"],
      "question_grammar_patterns": [],
      "topic": "건강",
      "difficulty_level": "easy",
      "confidence": 0.9
    }}
  ]
}}
</output>
</example_1>

<example_2>
<input>
## Question 1
### Question Stimulus

※
【1～2】
（        ）에 들어갈 말로 가장 알맞은 것을 고르십시오.
（각 2점）
### Reference Text

이 동내로 이사를（        ）일 년이 했다.
### Answers

1. 은 지
2. 올 때
3. 오거나
4. 오

## Question 2
### Question Stimulus

※
【1～2】
（        ）에 들어갈 말로 가장 알맞은 것을 고르십시오.
（각 2점）
### Reference Text

가음이 되면서 나 외이 점점 봬게（        ）.
### Answers

1. 변해 간다
2. 변할 변했다
3. 변한 적했다
4. 변하면 된다
</input>

<output>
{{
  "questions": [
    {{
      "question_text": "이 동내로 이사를（   ）일 년이 됐다.",
      "question_stimulus": "【1~2 (   ）에 들어갈 말로 가장 알맞은 것을 고르십시오.（각 2점) ",
      "answer_options": [
        {{"answer_text": "은 지", "answer_vocabulary_items": [], "answer_grammar_patterns": ["-은/는 지"]}},
        {{"answer_text": "올 때", "answer_vocabulary_items": [], "answer_grammar_patterns": ["-(으)ㄹ 때"]}},
        {{"answer_text": "오거나", "answer_vocabulary_items": [], "answer_grammar_patterns": ["-거나"]}},
        {{"answer_text": "오다가", "answer_vocabulary_items": [], "answer_grammar_patterns": ["-다가"]}}
      ],
      "question_type": "grammar",
      "question_vocabulary_items": ["동네", "이사"],
      "question_grammar_patterns": [],
      "topic": "일상생활",
      "difficulty_level": "medium",
      "confidence": 0.85
    }},
    {{
      "question_text": "가음이 되면서 나뭇잎 색이 점점 붉게（  ).",
      "question_stimulus": "【1~2 (   ）에 들어갈 말로 가장 알맞은 것을 고르십시오.（각 2점) ",
      "answer_options": [
        {{"answer_text": "변해 간다", "answer_vocabulary_items": [], "answer_grammar_patterns": ["-아/어 가다"]}},
        {{"answer_text": "변할 뻔했다", "answer_vocabulary_items": [], "answer_grammar_patterns": ["-(으)ㄹ 뻔했다"]}},
        {{"answer_text": "변한 척했다", "answer_vocabulary_items": [], "answer_grammar_patterns": ["-은/는 척하다"]}},
        {{"answer_text": "변하면 된다", "answer_vocabulary_items": [], "answer_grammar_patterns": ["-(으)면 되다"]}}
      ],
      "question_type": "grammar",
      "question_vocabulary_items": ["가을", "나뭇잎", "붉다"],
      "question_grammar_patterns": ["-면서", "-게"],
      "topic": "계절 변화",
      "difficulty_level": "medium",
      "confidence": 0.9
    }}
  ]
}}
</output>
</example_2>

<example_3>
<input>
## Question 9
### Question Stimulus

※
[9~12] 다음 글 또는 그래프의 내용과 같은 것을 고르십시오. (각 2점)
### Answers

1. 봉사 활동은 두 달 동안 하게 된다.
2. 아이들에게 책을 읽어 줄 봉사자를 찾고 있다.
3. 봉사자 신청은 도서관에 직접 가서 해야 한다.
4. 학생이 아닌 사람들도 이 봉사에 잠여할 수 있다.

## Question 10
### Question Stimulus

※
[9~12] 다음 글 또는 그래프의 내용과 같은 것을 고르십시오. (각 2점)
### Answers

1. 회사의 규모가 중요한다고 응답한 비율이 가장 낮다.
2. 가격을 중요하게 생각하는 사람이 전체의 받을 달는다.
3. 이용 후기가 여행 상품의 다양한보다 중요하다는 응답이 두 때 이상 달다.
4. 여행 상품의 다양한보다 회사의 규모를 중요하게 생각하는 사람이 더 적다.
</input>

<output>
{{
  "questions": [
    {{
      "question_text": "9.",
      "question_stimulus": "[9~12] 다음 글 또는 그래프의 내용과 같은 것을 고르십시오. (각 2점)",
      "answer_options": [
        {{"answer_text": "봉사 활동은 두 달 동안 하게 된다.", "answer_vocabulary_items": ["봉사 활동", "두 달"], "answer_grammar_patterns": ["-게 되다"]}},
        {{"answer_text": "아이들에게 책을 읽어 줄 봉사자를 찾고 있다.", "answer_vocabulary_items": ["아이들", "봉사자"], "answer_grammar_patterns": ["-아/어 주다", "-고 있다"]}},
        {{"answer_text": "봉사자 신청은 도서관에 직접 가서 해야 한다.", "answer_vocabulary_items": ["봉사자", "신청", "도서관"], "answer_grammar_patterns": ["-아/어서", "-아/어야 하다"]}},
        {{"answer_text": "학생이 아닌 사람들도 이 봉사에 참여할 수 있다.", "answer_vocabulary_items": ["학생", "봉사"], "answer_grammar_patterns": ["-이/가 아니다", "-(으)ㄹ 수 있다"]}}
      ],
      "question_type": "image dependent",
      "question_vocabulary_items": [],
      "question_grammar_patterns": [],
      "topic": "봉사 활동",
      "difficulty_level": "medium",
      "confidence": 0.7
    }},
    {{
      "question_text": "10.",
      "question_stimulus": "[9~12] 다음 글 또는 그래프의 내용과 같은 것을 고르십시오. (각 2점)",
      "answer_options": [
        {{"answer_text": "회사의 규모가 중요한다고 응답한 비율이 가장 낮다.", "answer_vocabulary_items": ["회사", "규모", "비율"], "answer_grammar_patterns": ["-다고"]}},
        {{"answer_text": "가격을 중요하게 생각하는 사람이 전체의 반을 넘는다.", "answer_vocabulary_items": ["가격", "전체"], "answer_grammar_patterns": ["-게", "-는"]}},
        {{"answer_text": "이용 후기가 여행 상품의 다양성보다 중요하다는 응답이 두 배 이상 많다.", "answer_vocabulary_items": ["이용 후기", "여행 상품"], "answer_grammar_patterns": ["-보다", "-다는"]}},
        {{"answer_text": "여행 상품의 다양성보다 회사의 규모를 중요하게 생각하는 사람이 더 적다.", "answer_vocabulary_items": ["여행 상품", "회사", "규모"], "answer_grammar_patterns": ["-보다", "-게"]}}
      ],
      "question_type": "image dependent",
      "question_vocabulary_items": [],
      "question_grammar_patterns": [],
      "topic": "여행 상품",
      "difficulty_level": "medium",
      "confidence": 0.7
    }}
  ]
}}
</output>
</example_3>

<example_4>
<input>
## Question 11
### Question Stimulus

※
[9～12] 다음
를
또는
그레프의
내용과
같은
것을
고르십시오.
(각 2점)
### Reference Text

지난달
문을
연
우표
박물관이
시민들에게
사령을
받고
있다.
박물관
내
역사실에서는
우표의
역사를
한논에
불
수
있다.
또
어린이
체험실에서는
향기
나는
우표의
향을
말거나
나무
우표
등을
만저
불
수
있다.
자신의
사진이
들어간
우표도
직접
만들
수
있다.
편지를
써
생으면
일
년
위에
받아
불
수
있는
박물관의
‘_title
우체통’도
인기를
 disin
다.
### Answers

1.
이
박물관은
일
년
전부터
운영을
시작했다.
2.
이
박물관에서는
직접
우표를
만들어
불
수
있다.
3.
이
박물관의
체험실에
있는
우표는
만질
수
없다.
4.
이
박물관의
린
우체통으로
편지를
보내지
 못한다.

## Question 12
### Question Stimulus

※
[9～12] 다음
를
또는
그레프의
내용과
같은
것을
고르십시오.
(각 2점)
### Reference Text

후일에
산을
오르면
경찰이
등산각을
구조했다.
지난
1일
검민수
경위는
인주산
정상에서
한
여성이
쓰려져
있는
것을
발경했다.
김
경위는
바로
여성의
체온이
필어지지
일게
검egen을
냯어서
어
주고
119에
신고했다.
이후
김
경위는
구조대
치량이
을
수
있는
산
중력
대파소까지
여성을
업고
위어
내려었다.
병원으로
이충된
여성은
치료를
받고
건강을
되
### Answers

1.
한
등산각이
산
정상에
쓰려져
있었다.
2.
김
경위는
대파소까지
차량으로
이동했다.
3.
구조대가
등산작을
업고
병원으로
위어었다.
4.
김
경위는
등산각의
신고를
받고
산에
을라
</input>

<output>
{{
  "questions": [
    {{
      "question_text": "지난달 문을 연 우표 박물관이 시민들에게 사랑을 받고 있다. 박물관 내 역사실에서는 우표의 역사를 한눈에 볼 수 있다. 또 어린이 체험실에서는 향기 나는 우표의 향을 맡거나 나무 우표 등을 만져 볼 수 있다. 자신의 사진이 들어간 우표도 직접 만들 수 있다. 편지를 써서 넣으면 일 년 뒤에 받아 볼 수 있는 박물관의 느린 우체통도 인기를 끌고 있다.",
      "question_stimulus": "[9~12] 다음 글 또는 그래프의 내용과 같은 것을 고르십시오. (각 2점)",
      "answer_options": [
        {{"answer_text": "이 박물관은 일 년 전부터 운영을 시작했다.", "answer_vocabulary_items": ["박물관", "운영"], "answer_grammar_patterns": ["-부터"]}},
        {{"answer_text": "이 박물관에서는 직접 우표를 만들어 볼 수 있다.", "answer_vocabulary_items": ["우표"], "answer_grammar_patterns": ["-아/어 보다", "-(으)ㄹ 수 있다"]}},
        {{"answer_text": "이 박물관의 체험실에 있는 우표는 만질 수 없다.", "answer_vocabulary_items": ["체험실", "우표"], "answer_grammar_patterns": ["-(으)ㄹ 수 없다"]}},
        {{"answer_text": "이 박물관의 린 우체통으로 편지를 보내지 못한다.", "answer_vocabulary_items": ["우체통", "편지"], "answer_grammar_patterns": ["-지 못하다"]}}
      ],
      "question_type": "reading comprehension",
      "question_vocabulary_items": ["우표", "박물관", "역사실", "체험실", "우체통"],
      "question_grammar_patterns": ["-(으)ㄹ 수 있다", "-거나"],
      "topic": "박물관",
      "difficulty_level": "medium",
      "confidence": 0.65
    }},
    {{
      "question_text": "휴일에 산을 오르던 경찰이 등산객을 구조했다. 지난 1일 김민수 경위는 인주산 정상에서 한 여성이 쓰러져 있는 것을 발견했다. 김 경위는 바로 여성의 체온이 떨어지지 않게 겉옷을 벗어서 덮어 주고 119에 신고했다. 이후 김 경위는 구조대 치량이 을 수 있는 산 중턱 대피소까지 여성을 업고 뛰어 내려갔다. 병원으로 이송된 여성은 치료를 받고 건강을 되찾았다.",
      "question_stimulus": "[9~12] 다음 글 또는 그래프의 내용과 같은 것을 고르십시오. (각 2점)",
      "answer_options": [
        {{"answer_text": "한 등산객이 산 정상에 쓰러져 있었다.", "answer_vocabulary_items": ["등산객", "정상"], "answer_grammar_patterns": ["-아/어 있다"]}},
        {{"answer_text": "김 경위는 대피소까지 차량으로 이동했다.", "answer_vocabulary_items": ["대피소", "차량"], "answer_grammar_patterns": []}},
        {{"answer_text": "구조대가 등산객을 업고 병원으로 뛰어갔다.", "answer_vocabulary_items": ["구조대", "병원"], "answer_grammar_patterns": ["-고"]}},
        {{"answer_text": "김 경위는 등산객의 신고를 받고 산에 을라갔다", "answer_vocabulary_items": ["신고"], "answer_grammar_patterns": ["-고"]}}
      ],
      "question_type": "reading comprehension",
      "question_vocabulary_items": ["경찰", "등산객", "구조", "정상", "대피소"],
      "question_grammar_patterns": ["-(으)면", "-고 있다"],
      "topic": "구조 활동",
      "difficulty_level": "hard",
      "confidence": 0.5
    }}
  ]
}}
</output>
</example_4>

<example_5>
<input>
## Question 13
### Question Stimulus

※
【13~15】다음을 순서에 맞게 배열한 것을 고르십시오. (각 2점)
### Reference Text

(가) 그래서 꺑질제 먹기도 편하고 맀락하지 않아서 식감도 좋다.
(나) 신비 복승하는 2017년에 한국에 처음 소개된 여름 과일이다.
(다) 다른 복승여에 비해 이른 시기에 먹을 수 있다는 것도 장점이다.
(라) Cyc이 없은 복승여와 속이 부드러운 복승여의 장점을 결합해 만들었다.
### Answers

(나) (- (라) - (가) - (다)
(2) (나) - (가) - (다) - (라)
(3) (라) - (나) - (다) - (가)
(4) (라) - (다) - (가) - (나)

## Question 14
### Question Stimulus

※
【13~15】다음을 순서에 맞게 배열한 것을 고르십시오. (각 2점)
### Reference Text

(가) 아이가 감기에 걸려 탈재 큰 소리로 올었다.
(나) 아주머니는 아이가 많이 아나며 오히려 격정해 주었다.
(다) 아침에 아이와 병원에 가려고 집을 나서다 열집 아주머니를 만났다.
(라) 나는 우는 아이를 달래면서도 올음소리에 이ße들이 캠퀬와 격정했다.
### Answers

(가) - (나) - (라) - (다)
(2) (가) - (라) - (다) - (나)
(3) (- (가) - (다) - (라)
(4) (- (나) - (라) - (가)

## Question 15
### Question Stimulus

※
【13~15】다음을 순서에 맞게 배열한 것을 고르십시오. (각 2점)
### Reference Text

(가) 죄근 온라인 가구 구매가 늘면서 반품 사례가 많아지고 있다.
(나) 그런데 비 뉘용으로 인해 피해를 보는 소비자가 늘고 있다.
(다) 막라서 소비자는 구매 전에 반품 비용과 조건을 잘 확인해야 한다.
(라) 입체가로 온건을 내세워 반품을 거절하는 경우까지 발생한다.
### Answers

(가) - (나) - (라) - (다)
(2) (- (라) - (다) - (나)
(3) (라) - (가) - (나) - (다)
(4) (라) - (다) - (가) - (나)
</input>

<output>
{{
  "questions": [
    {{
      "question_text": "(가) 그래서 껍질째 먹기도 편하고 딱딱하지 않아서 식감도 좋다.\n(나) 신비 복숭아는 2017년에 한국에 처음 소개된 여름 과일이다.\n(다) 다른 복숭아에 비해 이른 시기에 먹을 수 있다는 것도 장점이다.\n(라) 껍질이 얇은 복숭아와 속이 부드러운 복숭아의 장점을 결합해 만들었다.",
      "question_stimulus": "【13~15】다음을 순서에 맞게 배열한 것을 고르십시오. (각 2점)",
      "answer_options": [
        {{"answer_text": "(나) - (라) - (가) - (다)", "answer_vocabulary_items": [], "answer_grammar_patterns": []}},
        {{"answer_text": "(나) - (가) - (다) - (라)", "answer_vocabulary_items": [], "answer_grammar_patterns": []}},
        {{"answer_text": "(라) - (나) - (다) - (가)", "answer_vocabulary_items": [], "answer_grammar_patterns": []}},
        {{"answer_text": "(라) - (다) - (가) - (나)", "answer_vocabulary_items": [], "answer_grammar_patterns": []}}
      ],
      "question_type": "reading comprehension",
      "question_vocabulary_items": ["복숭아", "과일", "식감", "장점"],
      "question_grammar_patterns": ["-아/어서", "-(으)ㄹ 수 있다"],
      "topic": "음식/과일",
      "difficulty_level": "medium",
      "confidence": 0.6
    }},
    {{
      "question_text": "(가) 아이가 감기에 걸려 밤새 큰 소리로 올었다.\n(나) 아주머니는 아이가 많이 아팠냐며 오히려 걱정해 주셨다.\n(다) 아침에 아이와 병원에 가려고 집을 나서다 옆집 아주머니를 만났다.\n(라) 나는 우는 아이를 달래면서도 울음소리에 이웃들이 깰까 봐 걱정했다.",
      "question_stimulus": "【13~15】다음을 순서에 맞게 배열한 것을 고르십시오. (각 2점)",
      "answer_options": [
        {{"answer_text": "(가) - (나) - (라) - (다)", "answer_vocabulary_items": [], "answer_grammar_patterns": []}},
        {{"answer_text": "(가) - (라) - (다) - (나)", "answer_vocabulary_items": [], "answer_grammar_patterns": []}},
        {{"answer_text": "(나)- (가) - (다) - (라)", "answer_vocabulary_items": [], "answer_grammar_patterns": []}},
        {{"answer_text": "(나) - (다) - (라) - (가)", "answer_vocabulary_items": [], "answer_grammar_patterns": []}}
      ],
      "question_type": "reading comprehension",
      "question_vocabulary_items": ["아이", "감기", "병원", "아주머니"],
      "question_grammar_patterns": ["-아/어 주다", "-면서도", "-(으)려고"],
      "topic": "일상생활",
      "difficulty_level": "medium",
      "confidence": 0.6
    }},
    {{
      "question_text": "(가) 최근 온라인 가구 구매가 늘면서 반품 사례가 많아지고 있다.\n(나) 그런데 비싼 반품 비용으로 인해 피해를 보는 소비자가 늘고 있다.\n(다) 따라서 소비자는 구매 전에 반품 비용과 조건을 잘 확인해야 한다.\n(라) 입체가 까다로운 조건을 내세워 반품을 거절하는 경우까지 발생한다.",
      "question_stimulus": "【13~15】다음을 순서에 맞게 배열한 것을 고르십시오. (각 2점)",
      "answer_options": [
        {{"answer_text": "(가) - (나) - (라) - (다)", "answer_vocabulary_items": [], "answer_grammar_patterns": []}},
        {{"answer_text": "(가) - (라) - (다) - (나)", "answer_vocabulary_items": [], "answer_grammar_patterns": []}},
        {{"answer_text": "(라) - (가) - (나) - (다)", "answer_vocabulary_items": [], "answer_grammar_patterns": []}},
        {{"answer_text": "(라) - (다) - (가) - (나)", "answer_vocabulary_items": [], "answer_grammar_patterns": []}}
      ],
      "question_type": "reading comprehension",
      "question_vocabulary_items": ["온라인", "가구", "반품", "소비자", "비용"],
      "question_grammar_patterns": ["-면서", "-고 있다", "-아/어야 하다"],
      "topic": "소비/쇼핑",
      "difficulty_level": "medium",
      "confidence": 0.6
    }}
  ]
}}
</output>
</example_5>

<example_6>
<input>
## Question 9
### Question Stimulus

[9~12] 다음 글 또는 그래프의 내용과 같은 것을 고르십시오. (각 2점)
### Reference Image

**그림책 읽어 주는 자원봉사자 모집**

"어린이들에게 꿈과 희망을 선물하세요."

* 자격: 고등학생 또는 대학생(※ 한국어를 잘하는 외국인 학생도 가능)
* 모집 기간: 11월 10일(월) ~ 11월 21일(금)
* 신청 방법: 인주어린이도서관 홈페이지(www.injulibrary.or.kr)
* 활동 기간: 2025년 12월 1일(월) ~ 2026년 2월 28일(토)
### Answers

1. 봉사 활동은 두 달 동안 하게 된다.
2. 아이들에게 책을 읽어 줄 봉사자를 찾고 있다.
3. 봉사자 신청은 도서관에 직접 가서 해야 한다.
4. 학생이 아닌 사람들도 이 봉사에 참여할 수 있다.

## Question 10
### Question Stimulus

[9~12] 다음 글 또는 그래프의 내용과 같은 것을 고르십시오. (각 2점)
### Reference Image

여행사를 선택할 때 중요하게 생각하는 것

항목 비율(%)
가격 48
여행 상품의 다양성 25
회사의 규모 16
이용 후기 9
기타 2
### Answers

1. 회사의 규모가 중요하다고 응답한 비율이 가장 낮다.
2. 가격을 중요하게 생각하는 사람이 전체의 반을 넘는다.
3. 이용 후기가 여행 상품의 다양성보다 중요하다는 응답이 두 배 이상 많다.
4. 여행 상품의 다양성보다 회사의 규모를 중요하게 생각하는 사람이 더 적다.
</input>

<output>
{{
  "questions": [
    {{
      "question_text": "그림책 읽어 주는 자원봉사자 모집. 어린이들에게 꿈과 희망을 선물하세요. 자격: 고등학생 또는 대학생(한국어를 잘하는 외국인 학생도 가능). 모집 기간: 11월 10일(월)부터 11월 21일(금)까지. 신청 방법: 인주어린이도서관 홈페이지(www.injulibrary.or.kr). 활동 기간: 2025년 12월 1일(월)부터 2026년 2월 28일(토)까지.",
      "question_stimulus": "[9~12] 다음 글 또는 그래프의 내용과 같은 것을 고르십시오. (각 2점)",
      "answer_options": [
        {{"answer_text": "봉사 활동은 두 달 동안 하게 된다.", "answer_vocabulary_items": ["봉사 활동", "두 달"], "answer_grammar_patterns": ["-게 되다"]}},
        {{"answer_text": "아이들에게 책을 읽어 줄 봉사자를 찾고 있다.", "answer_vocabulary_items": ["아이들", "봉사자"], "answer_grammar_patterns": ["-아/어 주다", "-고 있다"]}},
        {{"answer_text": "봉사자 신청은 도서관에 직접 가서 해야 한다.", "answer_vocabulary_items": ["봉사자", "신청", "도서관"], "answer_grammar_patterns": ["-아/어서", "-아/어야 하다"]}},
        {{"answer_text": "학생이 아닌 사람들도 이 봉사에 참여할 수 있다.", "answer_vocabulary_items": ["학생", "봉사"], "answer_grammar_patterns": ["-이/가 아니다", "-(으)ㄹ 수 있다"]}}
      ],
      "question_type": "image dependent",
      "question_vocabulary_items": ["자원봉사자", "모집", "신청 방법", "활동 기간"],
      "question_grammar_patterns": [],
      "topic": "봉사 활동",
      "difficulty_level": "medium",
      "confidence": 0.9
    }},
    {{
      "question_text": "여행사를 선택할 때 중요하게 생각하는 것에 대한 설문 결과이다. 가격 48%, 여행 상품의 다양성 25%, 회사의 규모 16%, 이용 후기 9%, 기타 2%이다.",
      "question_stimulus": "[9~12] 다음 글 또는 그래프의 내용과 같은 것을 고르십시오. (각 2점)",
      "answer_options": [
        {{"answer_text": "회사의 규모가 중요하다고 응답한 비율이 가장 낮다.", "answer_vocabulary_items": ["회사", "규모", "비율"], "answer_grammar_patterns": ["-다고"]}},
        {{"answer_text": "가격을 중요하게 생각하는 사람이 전체의 반을 넘는다.", "answer_vocabulary_items": ["가격", "전체"], "answer_grammar_patterns": ["-게", "-는"]}},
        {{"answer_text": "이용 후기가 여행 상품의 다양성보다 중요하다는 응답이 두 배 이상 많다.", "answer_vocabulary_items": ["이용 후기", "여행 상품"], "answer_grammar_patterns": ["-보다", "-다는"]}},
        {{"answer_text": "여행 상품의 다양성보다 회사의 규모를 중요하게 생각하는 사람이 더 적다.", "answer_vocabulary_items": ["여행 상품", "회사", "규모"], "answer_grammar_patterns": ["-보다", "-게"]}}
      ],
      "question_type": "image dependent",
      "question_vocabulary_items": ["여행사", "설문", "비율"],
      "question_grammar_patterns": [],
      "topic": "여행 상품",
      "difficulty_level": "medium",
      "confidence": 0.9
    }}
  ]
}}
</output>
</example_6>
</examples>

Now extract from the following text:
{input}
"""

# ---------------------------------------------------------------------------
# Chain builder
# ---------------------------------------------------------------------------

_parser = PydanticOutputParser(pydantic_object=WrapperQuestions)
_prompt = PromptTemplate.from_template(prompt_template_str)
_chain_cache: dict[str, object] = {}


def _clean_json_keys(obj: object) -> object:
    """Recursively strip whitespace from all JSON object keys."""
    if isinstance(obj, dict):
        return {k.strip(): _clean_json_keys(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean_json_keys(i) for i in obj]
    return obj


_QUESTION_FIELDS = frozenset({"question_text", "answer_options"})


def _fix_raw(text: str) -> str:
    r"""Pre-process raw LLM text before JSON repair.

    Removes invalid \\uXXXX escape sequences whose suffix is not 4 hex
    digits, which cause both json.loads and json_repair to hard-fail.
    """
    return re.sub(r"\\u(?![0-9a-fA-F]{4})", "", text)


def _extract_questions(obj: object) -> list | None:
    """Recursively search *obj* for a list of question-like dicts.

    Handles three LLM output shapes:
    - ``{"questions": [...]}``               — standard wrapper
    - ``{"question_text": ..., ...}``        — single QuestionObject at root
    - ``{"text": ..., "output": {...}, ...}`` — questions buried in a value
    """
    if isinstance(obj, dict):
        if "questions" in obj:
            return obj["questions"]
        if _QUESTION_FIELDS.issubset(obj.keys()):
            return [obj]  # single QuestionObject returned at root
        for v in obj.values():
            found = _extract_questions(v)
            if found is not None:
                return found
    if isinstance(obj, list) and obj and isinstance(obj[0], dict):
        if _QUESTION_FIELDS.issubset(obj[0].keys()):
            return obj  # bare list of QuestionObjects
    return None


def _repair_and_parse(raw: str) -> WrapperQuestions:
    """Parse raw LLM text into WrapperQuestions with multi-stage fallback repair.

    Handles common LLM output issues:
    - Valid JSON that parses cleanly (fast path)
    - Whitespace in JSON keys (e.g. " questions" → "questions")
    - Invalid \\uXXXX escape sequences (non-hex suffix)
    - JSON block buried inside prose
    - Single QuestionObject returned at root instead of a wrapper
    - questions buried inside unexpected keys (text, output, paragraphs, …)
    """
    # 1. Happy path: parser works on raw output as-is
    try:
        return _parser.parse(raw)
    except Exception:
        pass

    # 2. Extract the first {...} block in case the model added prose, then
    #    pre-process to remove invalid unicode escapes before repair.
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in LLM output")

    cleaned = _fix_raw(match.group())

    try:
        obj = json_repair.repair_json(cleaned, return_objects=True)
    except Exception as exc:
        raise ValueError(f"Could not repair JSON in LLM output: {exc}") from exc

    if not isinstance(obj, dict):
        raise ValueError(
            f"Expected a JSON object from repair, got {type(obj).__name__}"
        )

    # 3. Normalize keys (strip accidental leading/trailing whitespace)
    obj = _clean_json_keys(obj)

    # 4. Find questions regardless of nesting structure
    questions = _extract_questions(obj)
    if questions is None:
        raise ValueError(
            f"Could not locate questions in LLM output. Top-level keys: {list(obj.keys())}"
        )

    return WrapperQuestions.model_validate({"questions": questions})


def build_chain(model_name: str = "qwen2.5:7b") -> object:
    """Return a LangChain LLM chain (without parser) for the given Ollama model.

    The chain is cached per model name so the OllamaLLM client is
    only instantiated once regardless of how many pages are processed.
    Parsing is done separately via :func:`_repair_and_parse` to allow
    JSON cleanup before validation.
    """
    if model_name not in _chain_cache:
        model = OllamaLLM(model=model_name)
        _chain_cache[model_name] = _prompt | model
    return _chain_cache[model_name]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_questions(
    text: str,
    model_name: str = "qwen2.5:7b",
    max_retries: int = 3,
    retry_delay: float = 1.0,
) -> WrapperQuestions:
    """Extract structured TOPIK questions from raw exam text.

    Retries up to *max_retries* times on parse failures, since local LLMs
    occasionally produce malformed JSON that succeeds on a second attempt.

    Args:
        text: Raw exam text containing questions and numbered answer choices.
        model_name: Ollama model to use for extraction.
        max_retries: Maximum number of attempts before raising.
        retry_delay: Seconds to wait between attempts.

    Returns:
        WrapperQuestions with all extracted questions and answers.

    Raises:
        RuntimeError: If all attempts fail.
    """
    chain = build_chain(model_name)
    payload = {
        "input": text,
        "format_instructions": _parser.get_format_instructions(),
    }

    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            raw = chain.invoke(payload)
            result = _repair_and_parse(raw)
            logger.info("Extraction succeeded on attempt %d/%d", attempt, max_retries)
            return result
        except Exception as exc:
            last_error = exc
            logger.warning("Attempt %d/%d failed: %s", attempt, max_retries, exc)
            if attempt < max_retries:
                time.sleep(retry_delay)

    raise RuntimeError(
        f"extract_questions failed after {max_retries} attempts"
    ) from last_error


# ---------------------------------------------------------------------------
# Entry point (for manual testing only)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    _SAMPLE = """
        가을이 되면서 나뭇입 색이 점점 볽게 (        )
        1. 변해 간다 
        2. 변할 뻔했다
        3. 변한 척했다
        4. 변하면 된다
        달리기, 지금 바로 시작하세요. 활기찬 내일이 기다립니다.
        1. 전기 절약 
        2. 건강 관리 
        3. 생활 예절 
        4. 환경 보호 
    """
    result = extract_questions(
        _SAMPLE, model_name="joonoh/HyperCLOVAX-SEED-Text-Instruct-1.5B"
    )
    print(result)
