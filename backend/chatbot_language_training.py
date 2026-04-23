from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Iterable

SYSTEM_PROMPT = (
    'Tu es AgriBot, assistant agricole pour un robot Raspberry Pi. '
    'Tu ne dois utiliser que humidity, ph, ec, temp.'
)


@dataclass
class LanguageSample:
    language: str
    user: str
    assistant: str


def _samples() -> Iterable[LanguageSample]:
    return [
        LanguageSample(
            language='fr',
            user='Le sol est sec et le pH est a 6.2, que faire ?',
            assistant='Arrosez la zone en priorite et maintenez le pH entre 6.0 et 7.2.',
        ),
        LanguageSample(
            language='fr',
            user='La conductivite monte a 2.6 mS/cm.',
            assistant='Lancez un lessivage court et reduisez les apports salins.',
        ),
        LanguageSample(
            language='ar',
            user='الرطوبة ضعيفة ودرجة الحرارة مرتفعة. ماذا أفعل؟',
            assistant='زد الري بشكل تدريجي وفضل القياس في الصباح أو المساء.',
        ),
        LanguageSample(
            language='ar',
            user='الحموضة 5.7 والموصلية 1.9.',
            assistant='صحح الحموضة تدريجيا وراقب الملوحة في النقاط نفسها.',
        ),
        LanguageSample(
            language='da',
            user='الرطوبة هابطة والحرارة طالعة، آش ندير؟',
            assistant='زيد السقي بشوية، وقيس بكري ولا لعشية باش النتائج تكون مضبوطة.',
        ),
        LanguageSample(
            language='da',
            user='الكوندوكتيڤيتي 2.7، واش كاين خطر؟',
            assistant='ايه، دير lessivage خفيف وراقب EC فالجولة الجاية.',
        ),
    ]


def build_chatbot_training_corpus(output_path: str) -> int:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    count = 0
    with open(output_path, 'w', encoding='utf-8') as fh:
        for sample in _samples():
            record = {
                'messages': [
                    {'role': 'system', 'content': SYSTEM_PROMPT + f' Reponds en {sample.language}.'},
                    {'role': 'user', 'content': sample.user},
                    {'role': 'assistant', 'content': sample.assistant},
                ]
            }
            fh.write(json.dumps(record, ensure_ascii=False) + '\n')
            count += 1
    return count


if __name__ == '__main__':
    default_path = os.path.join(os.path.dirname(__file__), 'data', 'chatbot_multilang_train.jsonl')
    total = build_chatbot_training_corpus(default_path)
    print(f'[chatbot-training] Corpus generated: {default_path} ({total} samples)')
