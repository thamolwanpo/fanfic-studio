"""Model registry: each entry carries the model's context-token limit, which the
context budgeter (build_context) reads. Adding a model = one registry entry, no feature
changes (README §6)."""

MODEL_REGISTRY = {
    "gpt-5.1": {"context_tokens": 400_000, "label": "GPT-5.1"},
    "gpt-4.1": {"context_tokens": 1_000_000, "label": "GPT-4.1"},
    "gpt-4o": {"context_tokens": 128_000, "label": "GPT-4o"},
    "gpt-4o-mini": {"context_tokens": 128_000, "label": "GPT-4o mini"},
    "o3": {"context_tokens": 200_000, "label": "o3"},
}

DEFAULT_MODEL = "gpt-4o"


def model_choices():
    return [(info["label"], name) for name, info in MODEL_REGISTRY.items()]


def context_limit(model):
    return MODEL_REGISTRY.get(model, {}).get("context_tokens", 128_000)
