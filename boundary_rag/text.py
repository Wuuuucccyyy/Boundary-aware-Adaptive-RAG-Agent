"""Deterministic Chinese/English lexical features and transparent token proxies."""
import math
import re
from collections import Counter


def terms(text: str) -> list[str]:
    result = re.findall(r"[a-z0-9_]+", text.lower())
    for run in re.findall(r"[\u4e00-\u9fff]+", text):
        result.extend(run)
        result.extend(run[i:i + 2] for i in range(len(run) - 1))
    return result


def token_proxy(text: str) -> int:
    """UTF-8 bytes / 4, NOT a model tokenizer or a billed token count."""
    return math.ceil(len(text.encode('utf-8')) / 4)


def similarity(a: str, b: str) -> float:
    x, y = Counter(terms(a)), Counter(terms(b))
    denominator = math.sqrt(sum(v*v for v in x.values()) * sum(v*v for v in y.values()))
    return sum(v*y[k] for k, v in x.items()) / denominator if denominator else 0.0
