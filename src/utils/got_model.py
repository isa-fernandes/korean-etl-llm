import torch
from transformers import AutoModel, AutoTokenizer
from transformers import logging as transformers_logging

transformers_logging.set_verbosity_error()


def get_got_model(GOT_MODEL, GOT_TOKENIZER):
    """Carrega o modelo GOT-OCR 2.0 na GPU."""
    if GOT_MODEL is None:
        print(
            "[INFO] Carregando GOT-OCR 2.0 (primeira execucao faz download ~1.5GB)..."
        )
        GOT_TOKENIZER = AutoTokenizer.from_pretrained(
            "stepfun-ai/GOT-OCR2_0", trust_remote_code=True, resume_download=None
        )
        GOT_MODEL = AutoModel.from_pretrained(
            "stepfun-ai/GOT-OCR2_0",
            trust_remote_code=True,
            low_cpu_mem_usage=True,
            device_map="cuda",
            use_safetensors=True,
            torch_dtype=torch.bfloat16,
            pad_token_id=GOT_TOKENIZER.eos_token_id,
            resume_download=None,
        ).eval()
    return GOT_MODEL, GOT_TOKENIZER
