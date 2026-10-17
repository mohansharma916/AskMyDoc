from functools import lru_cache

import yaml

from .config import get_settings


@lru_cache
def load_prompts() -> dict:
    with open(get_settings().prompts_file, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_prompt(name: str) -> dict:
    prompts = load_prompts()
    if name not in prompts:
        raise KeyError(f"Prompt '{name}' not found in {get_settings().prompts_file}")
    return prompts[name]


def render(name: str, **values: str) -> tuple[str, str, str]:
    """Return (system, user, version) for the named prompt."""
    prompt = get_prompt(name)
    return prompt["system"].strip(), prompt["user"].format(**values).strip(), str(prompt["version"])


def format_context(chunks: list[dict]) -> str:
    """Number passages so the model can cite them as [1], [2], ..."""
    parts = []
    for i, chunk in enumerate(chunks, start=1):
        location = chunk["source"]
        if chunk.get("page"):
            location += f", page {chunk['page']}"
        parts.append(f"[{i}] (source: {location})\n{chunk['text']}")
    return "\n\n".join(parts)
