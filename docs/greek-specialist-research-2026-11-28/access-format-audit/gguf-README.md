---
license: llama3.1
language:
- el
- en
pipeline_tag: text-generation
library_name: transformers
tags:
- text-generation-inference
base_model:
- ilsp/Llama-Krikri-8B-Instruct
---

🚨 **PLEASE USE THE OFFICIAL QUANTIZED VERSIONS** 🚨

🚨 *There is no guarantee that you are using the latest improved versions from 3rd party quantizations as the model's weights are getting reuploaded!* 🚨

# Llama-Krikri-8B-Instruct: An Instruction-tuned Large Language Model for the Greek language

<div align="center">
  <img src="https://huggingface.co/ilsp/Llama-Krikri-8B-Instruct/resolve/main/KriKri_Logo-eng_54307d80-ee25-49f9-9204-0ce774499fbc.svg?raw=true" width="60%" alt="Krikri" />
</div>

Following the release of [Meltemi-7B](https://huggingface.co/ilsp/Meltemi-7B-v1) on the 26th March 2024, we are happy to welcome Krikri to the family of ILSP open Greek LLMs.
Krikri is built on top of [Llama-3.1-8B](https://huggingface.co/meta-llama/Llama-3.1-8B), extending its capabilities for Greek through continual pretraining on a large corpus of high-quality and locally relevant Greek texts. We present **Llama-Krikri-8B-Instruct**, along with the base model, [Llama-Krikri-8B-Base](https://huggingface.co/ilsp/Llama-Krikri-8B-Base)

<!-- ![image/png](llama-krikri-image.jpg) -->


# Model Information

## Base Model

- Vocabulary extension of the Llama-3.1 tokenizer with Greek tokens
- 128k context length (approximately 80,000 Greek words)
- We extend the pretraining of Llama-3.1-8B with added proficiency for the Greek language, by utilizing a large training corpus. 
  * This corpus includes 56.7 billion monolingual Greek tokens, constructed from publicly available resources.
  * Additionaly, to mitigate catastrophic forgetting and ensure that the model has bilingual capabilities, we use additional sub-corpora with monolingual English texts (21 billion tokens) and Greek-English parallel data (5.5 billion tokens).
  * The training corpus also contains 7.8 billion math and code tokens.
  * This corpus has been processed, filtered, and deduplicated to ensure data quality and is outlined below:


| Sub-corpus   | # Tokens         | Percentage |
|-----------|------------------|------------|
| Greek     | 56.7 B   | 62.3 %      |
| English   | 21.0 B   | 23.1 %      |
| Parallel  |  5.5 B   | 6.0 %       |
| Math/Code |  7.8 B   | 8.6 %       |
| **Total** | **91 B**   |  **100%**       |


Chosen subsets of the 91 billion corpus were upsampled resulting in a size of **110 billion tokens**.

## Instruct Model

Llama-Krikri-8B-Instruct is the result of post-training Llama-Kriki-8B-Base and features:
- Enhanced chat capabilities and instruction-following in both Greek and English.
- Document translation from Greek to English, French, German, Italian, Portuguese, Spanish and vice versa.
- Great performance on generation, comprehension, and editing tasks, such as summarization, creative content creation, text modification, entity recognition, sentiment analysis, etc.
- Domain-specifc expertise for specialized legal, financial, medical, and scientific applications.
- Retrieval-Augmented Generation (RAG) utilizing multiple documents with 128k context length. 
- Improved coding and agentic capabilities with correct formatting and tool use.
- Conversion or structured extraction (e.g., XML, JSON) in data-to-text & text-to-data settings.
- Analytical thinking and Chain-of-Thought (CoT) reasoning for problem-solving.

## Post-training Methodology

We used a multi-stage process in order to build Llama-Krikri-8B-Instruct which includes:
- 2-stage Supervised Fine-Tuning with a combination of Greek & English instruction-response pairs (& multi-turn conversations)
  - **Stage 1**: **856,946** instruction-response pairs (371,379 Greek + 485,567 English)
  - **Stage 2**: **638,408** instruction-response pairs (279,948 Greek + 358,460 English)
- Alignment with a combination of Greek & English preference triplets (Instruction - Chosen Response - Rejected Response)
  - **Length Normalized DPO**: **92,394** preference triplets (47,132 Greek + 45,262 English)

## Post-training Data Construction

To build the SFT & DPO data, we utilized various methodologies including:
- Collecting existing high-quality datasets such as [Tulu 3](https://huggingface.co/datasets/allenai/tulu-3-sft-mixture), [SmolTalk](https://huggingface.co/datasets/HuggingFaceTB/smoltalk), [MAGPIE Ultra](https://huggingface.co/datasets/argilla/magpie-ultra-v1.0), [Orca Agent Instruct](https://huggingface.co/datasets/microsoft/orca-agentinstruct-1M-v1), [IFEval Like Data](https://huggingface.co/datasets/argilla/ifeval-like-data), [UltraFeedback](https://huggingface.co/datasets/HuggingFaceH4/ultrafeedback_binarized), [NVIDIA HelpSteer2](https://huggingface.co/datasets/nvidia/HelpSteer2), [Intel Orca](https://huggingface.co/datasets/argilla/distilabel-intel-orca-dpo-pairs), [UltraMedical](https://huggingface.co/datasets/TsinghuaC3I/UltraMedical-Preference), and other datasets focused on safety, truthfulness, and instruction-following.
- Translating various data into Greek using an in-house translation tool.
- Regenerating translated data and contrasting the translated with the regenerated responses (i.e., for creating preference triplets).
- Distilling (with the MAGPIE methodology) models which exhibit strong performance in Greek, such as [Gemma 2 27B IT](https://huggingface.co/google/gemma-2-27b-it).
- Scoring data with the [Skywork Reward Gemma 2 27B v0.2](https://huggingface.co/Skywork/Skywork-Reward-Gemma-2-27B-v0.2) Reward Model and filtering using rule-based filters.
- Creating data for sentence and document translation using high-quality parallel corpora mainly from [ELRC-SHARE](https://elrc-share.eu/).
- Synthetically extracting question-answer pairs and multi-turn dialogues from diverse sources such as Wikipedia, EUR-LEX, Greek School Books, and Kallipos.


# How to use

## With Transformers

```python
from transformers import AutoModelForCausalLM, AutoTokenizer

device = "cuda"

model = AutoModelForCausalLM.from_pretrained("ilsp/Llama-Krikri-8B-Instruct")
tokenizer = AutoTokenizer.from_pretrained("ilsp/Llama-Krikri-8B-Instruct")

model.to(device)

system_prompt = "Είσαι το Κρικρί, ένα εξαιρετικά ανεπτυγμένο μοντέλο Τεχνητής Νοημοσύνης για τα ελληνικα και εκπαιδεύτηκες από το ΙΕΛ του Ε.Κ. \"Αθηνά\"."
user_prompt = "Σε τι διαφέρει ένα κρικρί από ένα λάμα;"

messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": user_prompt},
]
prompt = tokenizer.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
input_prompt = tokenizer(prompt, return_tensors='pt').to(device)
outputs = model.generate(input_prompt['input_ids'], max_new_tokens=256, do_sample=True)

print(tokenizer.batch_decode(outputs)[0])
```

## With OpenAI compatible server via vLLM

```bash
vllm serve ilsp/Llama-Krikri-8B-Instruct \
  --enforce-eager \
  --dtype 'bfloat16' \
  --api-key token-abc123
```

Then, the model can be used through Python using:
```python
from openai import OpenAI

api_key = "token-abc123"
base_url = "http://localhost:8000/v1"

client = OpenAI(
    api_key=api_key,
    base_url=base_url,
)

system_prompt = "Είσαι ένα ανεπτυγμένο μεταφραστικό σύστημα που απαντάει με λίστες Python. Δεν γράφεις τίποτα άλλο στις απαντήσεις σου πέρα από τις μεταφρασμένες λίστες."
user_prompt = "Δώσε μου την παρακάτω λίστα με μεταφρασμένο κάθε string της στα ελληνικά: ['Ethics of duty', 'Postmodern ethics', 'Consequentialist ethics', 'Utilitarian ethics', 'Deontological ethics', 'Virtue ethics', 'Relativist ethics']"

messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": user_prompt},
]

response = client.chat.completions.create(model="ilsp/Llama-Krikri-8B-Instruct",
                                          messages=messages,
                                          temperature=0.0,
                                          top_p=0.95,
                                          max_tokens=8192,
                                          stream=False)

print(response.choices[0].message.content)
# ['Ηθική καθήκοντος', 'Μεταμοντέρνα ηθική', 'Συνεπειοκρατική ηθική', 'Ωφελιμιστική ηθική', 'Δεοντολογική ηθική', 'Ηθική αρετών', 'Σχετικιστική ηθική']
```

# Evaluation

In the table below, we report the scores for our chat evaluation suite which includes:
- [Greek IFEval](https://huggingface.co/datasets/ilsp/ifeval_greek) (strict average)
- [English IFEval](https://huggingface.co/datasets/google/IFEval) (strict average)
- [Greek MT-Bench](https://huggingface.co/datasets/ilsp/mt-bench-greek) using gpt-4o-2024-08-06 as the judge model.
- [English MT-Bench](https://huggingface.co/datasets/HuggingFaceH4/mt_bench_prompts) using gpt-4o-2024-08-06 as the judge model.

We can observe that *Llama-Krikri-8B-Instruct exhibits the strongest performance* in instruction following for both Greek and English across all the models we tested. In particular, it surpasses Llama-3.1-8B-Instruct by **+21.7%** and **+7.3%** on the Greek and English IFEval respectively.
It also exhibits **the strongest chat capabilities in the Greek MT-Bench benchmark** (+0.28 compared to Aya Expanse 8B), while also being very competitive in the English variant of the MT-Bench benchmark.

|       | IFEval EL (strict avg) | IFEval EN (strict avg) | MT-Bench EL | MT-Bench EN |
|---------------- |---------------- |----------------- |------------|------------|
| Qwen 2.5 7B Instruct | 46.2% | 74.8% | 5.83 | **7.87** |
| EuroLLM 9B Instruct | 51.3% | 64.5% | 5.98 | 6.27 |
| Aya Expanse 8B | 50.4% | 62.2% | 7.68 | 6.92 |
| Meltemi 7B v1.5 Instruct | 32.7% | 41.2% | 6.25 | 5.46 |
| Llama-3.1-8B Instruct | 45.8% | 75.1% | 6.46 | 7.25 |
| **Llama-Krikri-8B Instruct** | **67.5%** | **82.4%** | **7.96** | 7.21 |


We also used the [Arena-Hard-Auto](https://huggingface.co/datasets/lmarena-ai/arena-hard-auto-v0.1) automatic evaluation tool, as well the translated (and post-edited) version for Greek that is publicly available [here](https://huggingface.co/datasets/ilsp/m-ArenaHard_greek). We report 2 scores for Arena-Hard-Auto:
- No Style Control: The original version of the benchmark.
- With Style Control: The benchmark with style control methods for Markdown elements. You can read more about the methodology and technical background in this [blogspot](https://lmsys.org/blog/2024-08-28-style-control/).

Below, we show the scores for the Greek version of Arena-Hard-Auto for various open and closed chat models that were determined using **gpt-4o-2024-08-06 as the judge model** and **gpt-4o-mini-2024-07-18 as the baseline model** (i.e., by default 50% score).

Llama-Krikri-8B Instruct exhibits very strong chat capabilities by scoring **higher than models over 8 times its size** (such as Llama-3.1-70B Instruct) and is also **competitive with closed-source** (e.g., GPT-4o-Mini) and **highly-performant open-source models** (e.g., Gemma 2 27B IT & Aya Expanse 32B). 
![image/png](arena_hard_el.png)

Below, we show the scores for the original Arena-Hard-Auto dataset for various open and closed chat models. We followed the original methodology by using **gpt-4-1106-preview as the judge model** and **gpt-4-0314 as the baseline model**.

Llama-Krikri-8B Instruct performs very well in the English variant of Arena-Hard-Auto as well, since we can observe that it is **competitive with similarly sized LLMs** and that it **improves upon Llama-3.1-8B Instruct by +24.5% / +16%** (No style control / With style control). 
![image/png](arena_hard_en.png)

***Please note** that judge models are biased towards student models trained on distilled data from them. You can read more [here](https://arxiv.org/pdf/2502.01534?).

🚨 **More information on post-training, methodology, and evaluation coming soon.** 🚨


# Acknowledgements

The ILSP team utilized Amazon's cloud computing services, which were made available via GRNET under the [OCRE Cloud framework](https://www.ocre-project.eu/), providing Amazon Web Services for the Greek Academic and Research Community.

# Citation

```
@misc{roussis2025krikriadvancingopenlarge,
      title={Krikri: Advancing Open Large Language Models for Greek}, 
      author={Dimitris Roussis and Leon Voukoutis and Georgios Paraskevopoulos and Sokratis Sofianopoulos and Prokopis Prokopidis and Vassilis Papavasileiou and Athanasios Katsamanis and Stelios Piperidis and Vassilis Katsouros},
      year={2025},
      eprint={2505.13772},
      archivePrefix={arXiv},
      primaryClass={cs.CL},
      url={https://arxiv.org/abs/2505.13772}, 
}
```