"""Laya Guardrail: Vorschaltstufe vor einem LLM-Aufruf, Entscheidungen durch Laya.

Das Paket prueft Text mit dem Decision-Model Laya (System 1, ein Encoder-Pass,
keine generierten Token) und liefert ein Urteil je Satz sowie je Satzblock.
Weg zu Laya: POST an /v1/systemone, in der Regel ueber llama-swap.
"""

__version__ = "0.1.0"

from .config import (
    DEFAULT_ENDPOINT,
    DEFAULT_MODE,
    DEFAULT_MODEL,
    LANG_TARGET,
    MAX_CONCURRENCY,
    R3_GROUP_SIZE,
    THRESH_HARM,
    THRESH_INJECTION,
    THRESH_NOUL,
)
from .core import check_group, check_one, guard
from .sentences import split_sentences

__all__ = [
    "__version__",
    "DEFAULT_ENDPOINT",
    "DEFAULT_MODE",
    "DEFAULT_MODEL",
    "LANG_TARGET",
    "MAX_CONCURRENCY",
    "R3_GROUP_SIZE",
    "THRESH_HARM",
    "THRESH_INJECTION",
    "THRESH_NOUL",
    "check_group",
    "check_one",
    "guard",
    "split_sentences",
]
