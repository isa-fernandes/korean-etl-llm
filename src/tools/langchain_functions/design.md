# Output Model Design

QuestionObject

- question_text: String, required — the full question
- answer_options: AnswerObject List, required — list of choices
- question_type: Literal, optional — the type of question, can be vocabulary, grammar, reading comprehension, etc
- question_vocabulary_items: String List, required — list of key Korean words in problem statement
- question_grammar_patterns: String List, required — list of grammar structures in problem statement
- topic: String, optional — thematic context
- difficulty_level: Literal, optional — the classification of the question between easy, medium, and hard

AnswerObject

- answer_text: String, required — the full answer
- answer_vocabulary_items: String List, required — list of key Korean words in answer
- answer_grammar_patterns: String List, required — list of grammar structures in answer

# Input Model Design

- exam_text: String, required — text extracted from a PDF full block of text containing multiple questions and answers.

# Examples

- 가을이 되면서 나뭇입 색이 점점 볽게 (        )\
  1. 변해 간다 \
  2. 변할 뻔했다\
  3. 변한 척했다\
  4. 변하면 된다
- 달리기, 지금 바로 시작하세요. 활기찬 내일이 기다립니다.\
  1. 전기 절약 \
  2. 건강 관리 \
  3. 생활 예절 \
  4. 환경 보호 