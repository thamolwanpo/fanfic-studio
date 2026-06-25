"""Loads prompt templates from prompts/*.txt and fills them in with str.format()."""
import os

PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts")


def render_prompt(name, **kwargs):
    path = os.path.join(PROMPTS_DIR, f"{name}.txt")
    with open(path, "r", encoding="utf-8") as f:
        template = f.read()
    return template.format(**kwargs)
