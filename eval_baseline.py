import open_flamingo
from open_flamingo import create_model_and_transforms
from huggingface_hub import hf_hub_download
import torch
from PIL import Image
import requests
import tqdm
import os
import json
from transformers import AutoModelForCausalLM
from transformers import AutoTokenizer
from scr.model_util import Llava
model = Llava()


from scr.evaluate_util import GSM8K
dataset = GSM8K()
output_dir = "/scratch/t.tovi/results/"
device = 0
precision = torch.bfloat16
predictions = []
references = []

counter = 0
for idx in tqdm.tqdm(range(dataset)):
    data = dataset.val_dataset[idx]

    context = data["context"]
    question = data["question"]

    context_text = dataset.make_in_context(dataset.train_dataset, shots=4)

    # Encode text
    prompt = context_text + dataset.qa_prompt(context, question)
    text_token = tokenizer(prompt)

    answer_len = max([len(answer.split()) for answer in data["answers"]["text"]])
    if os.environ.get("MAX_LEN") != None:
        answer_len = int(os.environ["MAX_LEN"])

    answer_len = 20

    # Inference
    output = model.generate(
        input_ids=torch.tensor([text_token["input_ids"]]).to(device),
        attention_mask=torch.tensor([text_token["attention_mask"]]).to(
            device=0, dtype=torch.bfloat16
        ),
        max_new_tokens=answer_len,
        pad_token_id=50277,
    )
    output = tokenizer.decode(output[0])
    output = output[len(prompt) :]
    output = output.replace("<|endofchunk|>", "")
    output = dataset.postprocess_vqa_generation(output)
    output = dataset.normalize(output)

    # Put together predictions
    predictions.append({"prediction_text": output, "id": data["id"]})
    references.append({"answers": data["answers"], "id": data["id"]})

with open(output_dir + "GSM8K_LLaVA_results.json", "w") as f:
    f.write(json.dumps(predictions, indent=4))
with open(output_dir + "GSM8K_LLaVA_references.json", "w") as f:
    f.write(json.dumps(references, indent=4))
