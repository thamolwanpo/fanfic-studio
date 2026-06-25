"""Feature 4: author style guide (README §7, Feature 4). Map over a representative sample
of chapters, reduce into one style_guide.txt consumed by Feature 5."""
import json

from core.epub_io import chapter_count, read_chapter_text
from core.files import write_text
from core.state import set_artifact
from llm.json_utils import parse_json_response
from llm.pipelines import map_reduce_summarize
from llm.prompt_loader import render_prompt


def pick_sample_chapters(project, sample_size=5):
    total = chapter_count(project)
    if total <= sample_size:
        return list(range(1, total + 1))
    step = total / sample_size
    return sorted({max(1, round(1 + i * step)) for i in range(sample_size)})


def run_style_analysis(project, client, working_epub_path, sample_size=5):
    """Generator: map (analyze each sampled chapter) -> reduce (combine into style guide)."""
    sample = pick_sample_chapters(project, sample_size)
    chapters = []
    for n in sample:
        title, text, _html = read_chapter_text(working_epub_path, project, n)
        chapters.append((n, text))

    def map_fn(n, text):
        prompt = render_prompt("f4_analyze", chapter_n=n, chapter_text=text)
        response = client.call(
            system="You are a literary style analyst. Respond with strict JSON.",
            messages=[{"role": "user", "content": prompt}], json_mode=True, temperature=0.3,
        )
        return parse_json_response(response, default={})

    def reduce_fn(analyses):
        prompt = render_prompt("f4_reduce", analyses=json.dumps(analyses, ensure_ascii=False, indent=2))
        return client.call(
            system="You write clear, actionable style guides for writers imitating an author's voice.",
            messages=[{"role": "user", "content": prompt}], temperature=0.4,
        )

    yield from map_reduce_summarize(chapters, map_fn, reduce_fn)


def save_style_guide(project, style_guide_text):
    write_text(project.style_guide_txt, style_guide_text)
    set_artifact(project, "style_guide", True)
