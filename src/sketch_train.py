import ray
from ray.train.torch import TorchTrainer
from ray.train import ScalingConfig
from datasets import Dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import LoraConfig
from trl import SFTTrainer, SFTConfig
import torch
from pyspark.sql import SparkSession

# 1. Preparar os dados (Roda no nó principal/Driver)
df_silver = SparkSession.spark.read.parquet("dbfs:/mnt/silver/dados_provas/")
hf_dataset = Dataset.from_spark(df_silver)


# 2. Definir a função que será executada de forma distribuída em cada GPU
def train_loop_per_worker(config):
    # Cada worker carrega sua fatia do modelo
    model_id = "naver-hyperclovax/HyperCLOVAX-SEED-Text-Instruct-1.5B"
    tokenizer = AutoTokenizer.from_pretrained(model_id)

    # Configuração de quantização (Se as GPUs forem menores)
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
    )

    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        quantization_config=bnb_config,
        device_map={
            "": ray.train.torch.get_device()
        },  # Mapeia para a GPU correta do worker
    )

    peft_config = LoraConfig(
        r=8,
        lora_alpha=16,
        lora_dropout=0.05,
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
    )

    training_args = SFTConfig(
        output_dir="/dbfs/mnt/models/resultado_naver",  # Salvando direto no storage compartilhado
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        num_train_epochs=3,
        bf16=True,
        max_seq_length=1024,
        # Importante para treino distribuído:
        ddp_find_unused_parameters=False,
        report_to="none",
    )

    # O Ray injeta automaticamente o dataset correto para este worker
    local_dataset = ray.train.get_dataset_shard("train")
    # Convertendo o shard do Ray de volta para Hugging Face Dataset dentro do worker
    hf_local_dataset = local_dataset.to_hf()

    trainer = SFTTrainer(
        model=model,
        train_dataset=hf_local_dataset,
        peft_config=peft_config,
        tokenizer=tokenizer,
        args=training_args,
    )

    trainer.train()


# 3. Configurar a escala do treino no Databricks
# Supondo que seu cluster tenha 4 GPUs no total
scaling_config = ScalingConfig(
    num_workers=4,  # Quantidade total de GPUs no cluster
    use_gpu=True,  # Garante o uso de aceleração por hardware
)

# Convertendo o dataset para o formato do Ray
ray_dataset = ray.data.from_huggingface(hf_dataset)

trainer = TorchTrainer(
    train_loop_per_worker,
    datasets={"train": ray_dataset},
    scaling_config=scaling_config,
)

# Inicia o treino distribuído em todo o cluster do Databricks
results = trainer.fit()
