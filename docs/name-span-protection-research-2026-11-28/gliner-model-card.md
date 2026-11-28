---
license: apache-2.0
language:
  - multilingual
library_name: gliner
datasets:
  - urchade/pile-mistral-v0.1
pipeline_tag: token-classification
---

# About

GLiNER is a Named Entity Recognition (NER) model capable of identifying any entity type using a bidirectional transformer encoder (BERT-like). It provides a practical alternative to traditional NER models, which are limited to predefined entities, and Large Language Models (LLMs) that, despite their flexibility, are costly and large for resource-constrained scenarios.


## Links

* Paper: https://arxiv.org/abs/2311.08526
* Repository: https://github.com/urchade/GLiNER

## Available models

| Release | Model Name | # of Parameters | Language | License |
| - | - | - | - | - |
| v0 | [urchade/gliner_base](https://huggingface.co/urchade/gliner_base)<br>[urchade/gliner_multi](https://huggingface.co/urchade/gliner_multi) | 209M<br>209M | English<br>Multilingual | cc-by-nc-4.0 |
| v1 | [urchade/gliner_small-v1](https://huggingface.co/urchade/gliner_small-v1)<br>[urchade/gliner_medium-v1](https://huggingface.co/urchade/gliner_medium-v1)<br>[urchade/gliner_large-v1](https://huggingface.co/urchade/gliner_large-v1) | 166M<br>209M<br>459M | English <br> English <br> English | cc-by-nc-4.0 |
| v2 | [urchade/gliner_small-v2](https://huggingface.co/urchade/gliner_small-v2)<br>[urchade/gliner_medium-v2](https://huggingface.co/urchade/gliner_medium-v2)<br>[urchade/gliner_large-v2](https://huggingface.co/urchade/gliner_large-v2) | 166M<br>209M<br>459M |  English <br> English <br> English | apache-2.0 |
| v2.1 | [urchade/gliner_small-v2.1](https://huggingface.co/urchade/gliner_small-v2.1)<br>[urchade/gliner_medium-v2.1](https://huggingface.co/urchade/gliner_medium-v2.1)<br>[urchade/gliner_large-v2.1](https://huggingface.co/urchade/gliner_large-v2.1) <br>[urchade/gliner_multi-v2.1](https://huggingface.co/urchade/gliner_multi-v2.1) | 166M<br>209M<br>459M<br>209M | English <br> English <br> English <br> Multilingual | apache-2.0 |

## Installation
To use this model, you must install the GLiNER Python library:
```
!pip install gliner
```

## Usage
Once you've downloaded the GLiNER library, you can import the GLiNER class. You can then load this model using `GLiNER.from_pretrained` and predict entities with `predict_entities`.

```python
from gliner import GLiNER

model = GLiNER.from_pretrained("urchade/gliner_multi-v2.1")

text = """
Cristiano Ronaldo dos Santos Aveiro (Portuguese pronunciation: [kɾiʃˈtjɐnu ʁɔˈnaldu]; born 5 February 1985) is a Portuguese professional footballer who plays as a forward for and captains both Saudi Pro League club Al Nassr and the Portugal national team. Widely regarded as one of the greatest players of all time, Ronaldo has won five Ballon d'Or awards,[note 3] a record three UEFA Men's Player of the Year Awards, and four European Golden Shoes, the most by a European player. He has won 33 trophies in his career, including seven league titles, five UEFA Champions Leagues, the UEFA European Championship and the UEFA Nations League. Ronaldo holds the records for most appearances (183), goals (140) and assists (42) in the Champions League, goals in the European Championship (14), international goals (128) and international appearances (205). He is one of the few players to have made over 1,200 professional career appearances, the most by an outfield player, and has scored over 850 official senior career goals for club and country, making him the top goalscorer of all time.
"""

labels = ["person", "award", "date", "competitions", "teams"]

entities = model.predict_entities(text, labels)

for entity in entities:
    print(entity["text"], "=>", entity["label"])
```

```
Cristiano Ronaldo dos Santos Aveiro => person
5 February 1985 => date
Al Nassr => teams
Portugal national team => teams
Ballon d'Or => award
UEFA Men's Player of the Year Awards => award
European Golden Shoes => award
UEFA Champions Leagues => competitions
UEFA European Championship => competitions
UEFA Nations League => competitions
Champions League => competitions
European Championship => competitions
```

## Named Entity Recognition benchmark result

![image/png](https://cdn-uploads.huggingface.co/production/uploads/6317233cc92fd6fee317e030/Y5f7tK8lonGqeeO6L6bVI.png)

## Model Authors
The model authors are:
* [Urchade Zaratiana](https://huggingface.co/urchade)
* Nadi Tomeh
* Pierre Holat
* Thierry Charnois

## Citation
```bibtex
@misc{zaratiana2023gliner,
      title={GLiNER: Generalist Model for Named Entity Recognition using Bidirectional Transformer}, 
      author={Urchade Zaratiana and Nadi Tomeh and Pierre Holat and Thierry Charnois},
      year={2023},
      eprint={2311.08526},
      archivePrefix={arXiv},
      primaryClass={cs.CL}
}
```