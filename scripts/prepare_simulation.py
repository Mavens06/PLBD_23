from __future__ import annotations

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from backend.chatbot_language_training import build_chatbot_training_corpus
from ml_model.inference.predict import predict
from ml_model.train import train_and_select


def train_ml_model() -> None:
    print('[pipeline] Training ML model...')
    best_name, _, results = train_and_select()
    print(f'[pipeline] Best model: {best_name}')
    print(results.head(3).to_string())


def prepare_chatbot_corpus() -> None:
    output = os.path.join(PROJECT_ROOT, 'backend', 'data', 'chatbot_multilang_train.jsonl')
    total = build_chatbot_training_corpus(output)
    print(f'[pipeline] Chatbot corpus ready: {output} ({total} samples)')


def smoke_test_inference() -> None:
    print('[pipeline] Running inference smoke test...')
    sample = {'humidity': 43.5, 'ph': 6.4, 'ec': 1.6, 'temp': 22.1, 'rainfall': 0.0}
    result = predict(sample)
    source = result.get('source')
    top = result.get('top_crops', [])[:3]
    names = [item.get('name') if isinstance(item, dict) else str(item) for item in top]
    print(f'[pipeline] Inference source: {source}')
    print(f"[pipeline] Top crops: {', '.join(names) if names else 'n/a'}")


def main() -> None:
    train_ml_model()
    prepare_chatbot_corpus()
    smoke_test_inference()
    print('\n[pipeline] Simulation assets are ready.')


if __name__ == '__main__':
    main()
