"""Per-chapter summary cache build/read (README §4.4). This is the backbone every
"read the whole fic" feature (F2, F3, F5) relies on so they never need full chapter text."""
from core.epub_io import chapter_count, read_chapter_text
from core.files import read_json, write_json

DEFAULT_SUMMARIES = {
    "built_through_chapter": 0,
    "model_used": None,
    "chapters": [],
}


def load_summaries(project):
    return read_json(project.summaries_json, default=None) or dict(DEFAULT_SUMMARIES)


def save_summaries(project, data):
    write_json(project.summaries_json, data)


def missing_chapters(project, through_chapter=None):
    """Chapters that exist in the chapter map but have no summary entry yet."""
    data = load_summaries(project)
    have = {c["n"] for c in data["chapters"]}
    total = through_chapter or chapter_count(project)
    return [n for n in range(1, total + 1) if n not in have]


def upsert_chapter_summary(project, n, title, summary, characters_present, open_threads, model_used):
    data = load_summaries(project)
    data["chapters"] = [c for c in data["chapters"] if c["n"] != n]
    data["chapters"].append({
        "n": n,
        "title": title,
        "summary": summary,
        "characters_present": characters_present,
        "open_threads": open_threads,
    })
    data["chapters"].sort(key=lambda c: c["n"])
    data["built_through_chapter"] = max(c["n"] for c in data["chapters"])
    data["model_used"] = model_used
    save_summaries(project, data)
    return data


def get_chapter_text_for_summary(epub_path, project, n):
    _title, text, _html = read_chapter_text(epub_path, project, n)
    return text


def render_summaries_for_prompt(data, last_n=None):
    """Flatten cached summaries into compact text for context injection. If last_n is given,
    only the most recent N chapter summaries are included (used to keep prompts small)."""
    chapters = data.get("chapters", [])
    if last_n is not None:
        chapters = chapters[-last_n:]
    lines = []
    for c in chapters:
        lines.append(f"Chapter {c['n']} - {c['title']}: {c['summary']}")
        if c.get("open_threads"):
            lines.append(f"  Open threads: {', '.join(c['open_threads'])}")
    return "\n".join(lines)
