# Korean Study — TOPIK Data Pipeline

Pipeline de dados para coletar, processar e estruturar provas do [TOPIK](https://www.topik.go.kr/) (Test of Proficiency in Korean) com objetivo de gerar material de estudo e datasets para fine-tuning de LLMs.

> ⚠️ **Aviso legal**: as provas do TOPIK são propriedade do NIIED / Ministério da Educação da Coreia do Sul. Este projeto apenas organiza dados já publicamente disponibilizados em sites terceiros para fins pessoais de estudo e pesquisa em NLP. Não redistribua os PDFs originais sem autorização.

---

## Visão geral

O projeto segue a arquitetura **Medallion** (Bronze → Silver → Gold) sobre PySpark:

| Camada | Entrada | Saída | Objetivo |
|--------|---------|-------|----------|
| **Bronze** | PDFs, áudios e `metadata.json` das provas | Parquet com texto OCR página a página | Preservar o conteúdo bruto com rastreabilidade |
| **Silver** | Parquet Bronze | Tabelas dimensionais (`dim_exam`, `dim_file`, `dim_question`, `dim_answer`, `fact_download`, `fact_qa`) | Estruturar questões, respostas e metadados |
| **Gold** | Tabelas Silver | `vw_llm_training` e `mart_exam_stats` | Produzir datasets prontos para treino de LLM e análise |

A extração de texto dos PDFs utiliza o modelo **GOT-OCR 2.0** (`stepfun-ai/GOT-OCR2_0`), baixado automaticamente do Hugging Face na primeira execução.

---

## Requisitos

- Python 3.10+
- Windows, Linux ou macOS (o projeto foi desenvolvido e testado principalmente no Windows)
- Para Spark no Windows: `winutils.exe` configurado em `C:\hadoop\bin\winutils.exe` (ou ajuste `HADOOP_HOME`)
- GPU CUDA recomendada para OCR (RTX 3050 6 GB é suficiente)
- [Ollama](https://ollama.com/) rodando localmente para a extração estruturada de questões via `langchain_ollama`

Instale as dependências:

```bash
pip install -r requirements.txt
```

No Windows, o OCR de PDFs precisa do Poppler:

```powershell
winget install oschwartz10612.poppler
```

---

## Como usar

### 1. Baixar as provas

```bash
python src/tools/download_topik.py
```

O script faz scraping do site [topikguide.com/previous-papers](https://www.topikguide.com/previous-papers/) e salva os arquivos em `data/topik_papers/`.

### 2. Executar o pipeline por camada

```bash
# Bronze: OCR dos PDFs
python src/cli/run_pipeline.py bronze

# Silver: gera tabelas dimensionais para todos os exames
python src/cli/run_pipeline.py silver

# Gold: gera datasets analíticos a partir de toda a Silver
python src/cli/run_pipeline.py gold
```

### 3. Visualizar a documentação local

```bash
serve_docs.bat   # Windows
# ou
python docs/serve_docs.py
```

A documentação da modelagem dimensional é servida em `http://127.0.0.1:8000`.

---

## Estrutura do repositório

```
.
├── data/                      # Dados baixados e processados (não versionados)
│   ├── bronze/
│   ├── silver/
│   └── topik_papers/
├── docs/                      # Documentação da modelagem dimensional
├── notebooks/                 # Notebooks de exploração
├── outputs/                   # Resultados gerados (não versionados)
├── src/
│   ├── cli/                   # Entrypoints de linha de comando
│   ├── pipelines/             # Pipelines Bronze, Silver e Gold
│   ├── schemas/               # Schemas PySpark
│   ├── tools/                 # Download e funções LangChain/Ollama
│   ├── transformations/       # Lógicas de transformação por camada
│   └── utils/                 # Utilitários (Spark, Hadoop, OCR, etc.)
├── tests/                     # Testes unitários
├── requirements.txt
└── README.md
```

---

## Status do projeto

- [x] Download automatizado de provas
- [x] Pipeline Bronze com OCR via GOT-OCR 2.0
- [x] Pipeline Silver com tabelas dimensionais
- [x] Extração estruturada de questões via LLM local
- [ ] Testes unitários para limpeza de texto e API generativa
- [ ] Pipeline Gold completo (`vw_llm_training` e `mart_exam_stats` em desenvolvimento)
- [ ] Finetunning de modelo LLM para gerar questões de prova a partir da `vw_llm_training` (em desenvolvimento)
- [ ] Criação de ambiente docker


---

## Licença

Este repositório é distribuído sob a licença MIT. Consulte [LICENSE](LICENSE) para mais detalhes.

O código é aberto para fins de aprendizado. Os dados das provas pertencem aos respectivos detentores dos direitos autorais.
