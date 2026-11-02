"""Каталог моделей OpenAI-совместимого шлюза для AI4Science: алиасы, окна контекста.

Общий модуль для bin/ai4science.py (запуск Goose) и src/token_proxy.py
(подстановка полного id модели, если в запросе короткий алиас; так работает
`/model <алиас>` внутри сессии). Только стандартная библиотека.
"""
from __future__ import annotations

DEFAULT_MODEL = "ai-pro"
DEFAULT_PLANNER = "off"
DEFAULT_CONTEXT = 1_048_576

# (алиас, id модели у шлюза, окно контекста в токенах, назначение).
CATALOG: list[tuple[str, str, int, str]] = [
    ("ai-pro", "ai-pro", 1_048_576, "модель по умолчанию"),
    ("local-agent", "samcs-gpu/local-agent", 1_048_576, "альтернатива для сравнения"),
]

MODEL_ALIASES: dict[str, str] = {alias: slug for alias, slug, _, _ in CATALOG}
MODEL_CONTEXT: dict[str, int] = {slug: ctx for _, slug, ctx, _ in CATALOG}

# После `/model` Goose не пересчитывает окно контекста, поэтому точка сжатия
# истории одна для всех моделей каталога: история вместе с ответом модели
# помещается в самое короткое окно.
MAX_OUTPUT_TOKENS = 16_000
COMPACT_AT_TOKENS = min(100_000, min(MODEL_CONTEXT.values()) - MAX_OUTPUT_TOKENS - 4_000)


def resolve_model(raw: str) -> str:
    """Алиас или id модели → id модели; пусто → модель по умолчанию."""
    raw = (raw or "").strip()
    if not raw:
        return DEFAULT_MODEL
    return MODEL_ALIASES.get(raw, raw)


def context_for(model_slug: str) -> int:
    return MODEL_CONTEXT.get(model_slug, DEFAULT_CONTEXT)


def format_context(tokens: int) -> str:
    """262144 → '256k', 1048576 → '1M'."""
    if tokens >= 1_048_576:
        return f"{tokens // 1_048_576}M"
    return f"{tokens // 1024}k"
