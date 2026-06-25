"""state.json read/write: tracks progress so the user can resume after closing the app (README §4.1)."""
from datetime import datetime, timezone

from core.files import read_json, write_json

DEFAULT_STATE = {
    "project_name": "",
    "source_chapter_count": 0,
    "current_write_chapter": 1,
    "refined_chapters": [],
    "artifacts": {
        "world_bible": False,
        "plot_overall": False,
        "plot_chapters": False,
        "style_guide": False,
        "summaries_built_through": 0,
    },
    "last_modified": None,
}


def load_state(project):
    state = read_json(project.state_json, default=None)
    if state is None:
        state = dict(DEFAULT_STATE)
        state["project_name"] = project.name
    return state


def save_state(project, state):
    state["last_modified"] = datetime.now(timezone.utc).isoformat()
    write_json(project.state_json, state)


def mark_chapter_refined(project, chapter_n):
    state = load_state(project)
    if chapter_n not in state["refined_chapters"]:
        state["refined_chapters"].append(chapter_n)
        state["refined_chapters"].sort()
    save_state(project, state)
    return state


def set_artifact(project, key, value=True):
    state = load_state(project)
    state["artifacts"][key] = value
    save_state(project, state)
    return state
