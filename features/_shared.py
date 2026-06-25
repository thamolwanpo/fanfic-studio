"""Helpers shared across feature modules (not a tab itself). Keeps the "ensure summaries
are built" logic in one place since F1, F2, F3, and F5 all depend on the summary cache."""
from core.epub_io import chapter_count, read_chapter_text
from core.summaries import load_summaries, missing_chapters, upsert_chapter_summary
from llm.json_utils import parse_json_response
from llm.pipelines import map_reduce_summarize
from llm.prompt_loader import render_prompt

SUMMARY_SYSTEM = "You summarize fanfiction chapters precisely. Always respond with strict JSON."
SUMMARY_PROMPT = (
    "Summarize this chapter in 3-5 sentences, list characters present, and list any open "
    "plot threads it raises or leaves unresolved.\n\nChapter {n} - {title}:\n{text}\n\n"
    'Return strict JSON: {{"summary": "...", "characters_present": ["..."], "open_threads": ["..."]}}'
)


def ensure_summaries(project, working_epub_path, client, model_name):
    """Generator: builds summaries for any chapter missing from the cache. Yields progress
    dicts so the UI can stream it. Reuses map_reduce_summarize's map step."""
    total_chapters = chapter_count(project)
    to_build = missing_chapters(project, through_chapter=total_chapters)
    if not to_build:
        yield {"step": "done", "built": []}
        return

    chapters = []
    for n in to_build:
        title, text, _html = read_chapter_text(working_epub_path, project, n)
        chapters.append((n, (title, text)))

    def summarize_fn(n, payload):
        title, text = payload
        prompt = SUMMARY_PROMPT.format(n=n, title=title, text=text)
        response = client.call(system=SUMMARY_SYSTEM, messages=[{"role": "user", "content": prompt}],
                                json_mode=True, temperature=0.2)
        parsed = parse_json_response(response, default={})
        upsert_chapter_summary(
            project, n, title,
            parsed.get("summary", ""),
            parsed.get("characters_present", []),
            parsed.get("open_threads", []),
            model_name,
        )
        return parsed

    for progress in map_reduce_summarize(chapters, summarize_fn):
        yield progress


def get_summaries_text(project, last_n=None):
    from core.summaries import render_summaries_for_prompt
    data = load_summaries(project)
    return render_summaries_for_prompt(data, last_n=last_n)
