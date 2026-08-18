"""Extracao de paginas de prova TOPIK via LlamaParse (LlamaCloud)."""

import os
from pathlib import Path
from time import time

from dotenv import load_dotenv
from llama_cloud import LlamaCloud

load_dotenv()

CUSTOM_PROMPT = "You are a strict document parser transcribing a page from a Korean TOPIK exam PDF into structured Markdown.\nCRITICAL: Do NOT create a single global section for all text blocks or all answers. You must process the page sequentially, item by item. Map each question number to its specific stimulus, reference content, and options.\n\n### EXPECTED OUTPUT FORMAT PER QUESTION BLOCK:\nFor EACH question found on the page, output exactly this structure in sequence:\n## Question [Number]\n### Question Stimulus\n[The instruction/enunciation line that defines the question scope, e.g., ※ [9~12]...]\n### [Reference Image OR Reference Text]\nChoose '### Reference Image' if it's a short banner/sentence with blanks. Choose '### Reference Text' if it's a full block/paragraph of text inside a box OR a short phrase that is not from an image.\n[Verbatim Korean text inside the box]\n### Answers\n① [Option 1 text]\n② [Option 2 text]\n③ [Option 3 text]\n④ [Option 4 text]\n\n### FEW-SHOT EXAMPLES:\n\n--- EXAMPLE 1 (Banner/Image Layout) ---\n<example_input_1>\nLayout elements:\n- General Instruction: ※ [5~8] 다음은 무엇에 대한 글인지 고르십시오. (각 2점)\n- Question Number: 5.\n- Text inside gray banner: 걸을 때 발이 편하게~\n가볍고 디자인도 예뻐요.\n- Line of options: ① 구두    ② 우산    ③ 자전거    ④ 선풍기\n</example_input_1>\n<example_output_1>\n## Question 5\n### Question Stimulus\n※ [5~8] 다음은 무엇에 대한 글인지 고르십시오. (각 2점)\n### Reference Image\n걸을 때 발이 편하게~\n가볍고 디자인도 예뻐요.\n### Answers\n① 구두\n② 우산\n③ 자전거\n④ 선풍기\n</example_output_1>\n\n--- EXAMPLE 2 (Blank Fill-in Layout) ---\n<example_input_2>\nLayout elements:\n- General Instruction: ※ [1~2] (        )에 들어갈 말로 가장 알맞은 것을 고르십시오. (각 2점)\n- Question Number: 1.\n- Sentence with blank: 이 동네로 이사를 (        ) 일 년이 됐다.\n- Line of options: ① 온 지    ② 올 때    ③ 오거나    ④ 오다가\n</example_input_2>\n<example_output_2>\n## Question 1\n### Question Stimulus\n※ [1~2] (        )에 들어갈 말로 가장 알맞은 것을 고르십시오. (각 2점)\n### Reference Text\n이 동네로 이사를 (        ) 일 년이 됐다.\n### Answers\n① 온 지\n② 올 때\n③ 오거나\n④ 오다가\n</example_output_2>\n\n--- EXAMPLE 3 (Paragraph/Text Box Layout) ---\n<example_input_3>\nLayout elements:\n- General Instruction: ※ [9~12] 다음 글 또는 그래프의 내용과 같은 것을 고르십시오. (각 2점)\n- Question Number: 11.\n- Paragraph inside box: 지난달 문을 연 우표 박물관이 시민들에게 사랑을 받고 있다. 박물관 내 역사실에서는 우표의 역사를 한눈에 볼 수 있다. 또 어린이 체험실에서는 향기 나는 우표의 향을 맡거나 나무 우표 등을 만져 볼 수 있다. 자신의 사진이 들어간 우표도 직접 만들 수 있다. 편지를 써서 넣으면 일 년 뒤에 받아 볼 수 있는 박물관의 ‘느린 우체통’도 인기를 끌고 있다.\n- Vertical block of options: ① 이 박물관은 일 년 전부터 운영을 시작했다.\n② 이 박물관에서는 직접 우표를 만들어 볼 수 있다.\n③ 이 박물관의 체험실에 있는 우표는 만질 수 없다.\n④ 이 박물관의 느린 우체통으로는 편지를 보내지 못한다.\n</example_input_3>\n<example_output_3>\n## Question 11\n### Question Stimulus\n※ [9~12] 다음 글 또는 그래프의 내용과 같은 것을 고르십시오. (각 2점)\n### Reference Text\n지난달 문을 연 우표 박물관이 시민들에게 사랑을 받고 있다. 박물관 내 역사실에서는 우표의 역사를 한눈에 볼 수 있다. 또 어린이 체험실에서는 향기 나는 우표의 향을 맡거나 나무 우표 등을 만져 볼 수 있다. 자신의 사진이 들어간 우표도 직접 만들 수 있다. 편지를 써서 넣으면 일 년 뒤에 받아 볼 수 있는 박물관의 ‘느린 우체통’도 인기를 끌고 있다.\n### Answers\n① 이 박물관은 일 년 전부터 운영을 시작했다.\n② 이 박물관은 직접 우표를 만들어 볼 수 있다.\n③ 이 박물관의 체험실에 있는 우표는 만질 수 없다.\n④ 이 박물관의 느린 우체통으로는 편지를 보내지 못한다.\n</example_output_3>\n\n### STRICT CONSTRAINTS:\n- Transcribe all Korean text exactly as written. Never translate or summarize.\n- Keep circled numerals (①②③④) unchanged and place each option on its own line.\n- Do not invent questions or add conversational filler."

_client: LlamaCloud | None = None


def _get_client() -> LlamaCloud:
    global _client
    if _client is None:
        _client = LlamaCloud(api_key=os.getenv("LLAMA_PARSE"))
    return _client


def parse_pdf_with_llamaparse(pdf_path: str | Path, page_range: str | None = None) -> dict[int, str]:
    """Extrai markdown estruturado de um PDF de prova TOPIK via LlamaParse.

    Args:
        pdf_path: caminho do PDF a processar.
        page_range: string tipo "5-5" para limitar paginas; None processa o documento inteiro.

    Returns:
        Dict mapeando page_number (1-based) -> markdown extraido da pagina.
    """
    client = _get_client()
    file_obj = client.files.create(file=str(pdf_path), purpose="parse")

    result = client.parsing.parse(
        file_id=file_obj.id,
        tier="agentic",
        version="latest",
        agentic_options={"custom_prompt": CUSTOM_PROMPT},
        page_ranges={"target_pages": page_range} if page_range else {},
        output_options={
            "markdown": {"inline_images": True},
            "images_to_save": ["layout", "embedded"],
        },
        processing_options={
            "cost_optimizer": {"enable": True},
            "ocr_parameters": {"languages": ["ko", "en"]},
        },
        expand=["markdown", "images_content_metadata"],
    )

    pages: dict[int, str] = {}
    for page in result.markdown.pages if result.markdown else []:
        if getattr(page, "success", True):
            pages[page.page_number] = page.markdown or ""
        else:
            print(f"  [AVISO] LlamaParse falhou na pagina {page.page_number}: {getattr(page, 'error', '')}")
            pages[page.page_number] = ""
    return pages


if __name__ == "__main__":
    PDF_PATH = os.path.join("..", "..", "data", "topik_papers", "102nd-topik-test-papers", "102nd-TOPIK-II-Reading-Test-Paper.pdf")
    OUTPUT_PATH = os.path.join("..", "..", "outputs", "llamaparser")

    start = time()
    pages_by_number = parse_pdf_with_llamaparse(PDF_PATH, page_range="5-5")
    elapsed = time() - start

    os.makedirs(OUTPUT_PATH, exist_ok=True)
    markdown_out = "\n\n".join(pages_by_number[k] for k in sorted(pages_by_number))
    Path(os.path.join(OUTPUT_PATH, "output.md")).write_text(markdown_out, encoding="utf-8")
    print(f"Wrote {len(markdown_out)} chars of markdown across {len(pages_by_number)} page(s)")
    print(f"Parsing took {elapsed:.2f} seconds")
