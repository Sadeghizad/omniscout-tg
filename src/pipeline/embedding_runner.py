"""
OmniScout-TG: Standalone EmbeddingGemma 2 Inference Runner
Runs inside the embeddinggemma2 virtual environment with PyTorch CUDA acceleration.
Accepts input JSON via argument file or stdin, outputs cosine similarity scores as JSON.
"""

import json
import os
import sys

# Ensure UTF-8 IO
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")

# Prevent huggingface hub from trying to connect online
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

import torch
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


def get_local_model_path() -> str:
    snapshot_path = r"C:\Users\Asus\.cache\huggingface\hub\models--google--embeddinggemma-2\snapshots\914f7f89142e33e77833254d9c9b90c3cef7303b"
    if os.path.isdir(snapshot_path):
        return snapshot_path
    return "google/embeddinggemma-2"


def main():
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
        with open(input_file, encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = json.load(sys.stdin)

    query = data.get("query", "")
    documents = data.get("documents", [])

    if not documents:
        print(json.dumps([]))
        return

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model_path = get_local_model_path()

    model = SentenceTransformer(
        model_path,
        config_kwargs={"vision_config": None, "audio_config": None},
        device=device,
    )

    # Note: Pass raw text strings to model.encode, NOT tokenized lists!
    q_emb = model.encode([query], show_progress_bar=False)
    d_emb = model.encode(documents, show_progress_bar=False)

    sims = cosine_similarity(q_emb, d_emb)[0]
    scores = [round(float(s), 4) for s in sims]

    print(json.dumps(scores))


if __name__ == "__main__":
    main()
