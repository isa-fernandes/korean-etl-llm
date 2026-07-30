# Visão Geral da Arquitetura de Dados

Este documento funciona como um mapa geral da documentacao de dados do projeto. Em vez de tentar concentrar todos os detalhes fisicos de schema em um unico arquivo, ele resume o papel de cada camada e aponta para a documentacao especifica de Bronze, Silver e Gold.

O objetivo e deixar mais claro como o pipeline evolui da ingestao bruta ate os datasets analiticos finais, sempre em uma visao orientada a PySpark.

---

## Bronze

Antes da Bronze, o projeto possui uma fonte de dados bruta composta por PDFs, audios e `metadata.json`. A Bronze comeca quando esse material e lido e transformado em Parquet pelo pipeline de extracao.

Documento principal:

- [bronze_dimensional_model.md](bronze_dimensional_model.md)

Visualizacao resumida:

| Camada | Estrutura principal | Granularidade | Persistencia |
| --- | --- | --- | --- |
| Bronze | dataset Parquet por edicao | Uma linha por pagina processada | Parquet |

---

## Silver

Na Silver, os dados brutos sao reorganizados em entidades reutilizaveis. E a camada em que exame, arquivo, questao e resposta passam a ter estrutura propria e rastreavel, pronta para joins, enriquecimento e consumo analitico intermediario.

Documento principal:

- [silver_dimensional_model.md](silver_dimensional_model.md)

Visualizacao resumida:

| Camada | Estruturas principais | Granularidade | Persistencia sugerida |
| --- | --- | --- | --- |
| Silver | `DimExam`, `DimFile`, `DimQuestion`, `DimAnswer`, `FatoDownload`, `FatoQA` | Uma linha por entidade ou evento | Parquet por entidade ou dominio |

---

## Gold

Na Gold, o foco deixa de ser organizacao estrutural e passa a ser consumo. E a camada dos datasets consolidados para treino, exploracao analitica, metricas e produtos de dados mais prontos para uso.

Documento principal:

- [gold_dimensional_model.md](gold_dimensional_model.md)

Visualizacao resumida:

| Camada | Estruturas principais | Granularidade | Persistencia sugerida |
| --- | --- | --- | --- |
| Gold | `GoldLLMTraining`, `GoldExamStats` | Uma linha por item de treino ou por exame agregado | Parquet por dataset analitico |

---

## Fluxo de dados

```
Fonte de dados
  PDFs, audios e metadata.json
        │
        ▼  processamento e modelagem em PySpark
Bronze (Parquet por edição)
  uma linha por página extraída
        │
        ▼  modelagem dimensional
Silver (dimensões e fatos)
  DimExam, DimFile, DimQuestion, DimAnswer, FatoDownload, FatoQA
        │
        ▼  consolidação analítica
Gold (datasets analíticos)
  GoldLLMTraining, GoldExamStats
```

## Mapeamento fisico por camada

| Camada | Fonte ou destino principal | Formato | Finalidade |
| --- | --- | --- | --- |
| Fonte | `data/topik_papers/<edition>` | PDFs, audios e JSON | Material bruto de entrada |
| Bronze | `data/bronze/<edition>` | Parquet | Estruturar o texto extraido por pagina com rastreabilidade |
| Silver | datasets por entidade ou fato | Parquet | Estruturar o dado para joins e enriquecimento |
| Gold | datasets analiticos finais | Parquet | Entregar consumo analitico e treino |

---

## Como navegar na documentacao

Se quiser ler a documentacao por camada:

- Bronze: [bronze_dimensional_model.md](bronze_dimensional_model.md)
- Silver: [silver_dimensional_model.md](silver_dimensional_model.md)
- Gold: [gold_dimensional_model.md](gold_dimensional_model.md)

Se quiser visualizar tudo em HTML local, voce pode iniciar o servidor da documentacao e abrir o navegador no endereco local.
