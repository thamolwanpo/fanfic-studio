"""characters.json model + deterministic name application (README §4.2).

The LLM only ever proposes additions/edits to canonical_names and au_canon_swaps.
Application to text is a deterministic find/replace pass triggered by the user.
"""
import re

from core.files import read_json, write_json

DEFAULT_CHARACTERS = {
    "canonical_names": {},
    "au_canon_swaps": [],
    "arcs": {},
}


def load_characters(project):
    return read_json(project.characters_json, default=None) or dict(DEFAULT_CHARACTERS)


def save_characters(project, data):
    write_json(project.characters_json, data)


def propose_name_additions(data, proposals):
    """Merge a proposal dict {"canonical_names": {...}, "au_canon_swaps": [...]} into the
    existing data WITHOUT applying anything to text. Caller still owns saving + review."""
    merged = {
        "canonical_names": dict(data.get("canonical_names", {})),
        "au_canon_swaps": list(data.get("au_canon_swaps", [])),
        "arcs": dict(data.get("arcs", {})),
    }
    merged["canonical_names"].update(proposals.get("canonical_names", {}))
    existing_au_names = {swap["au_name"] for swap in merged["au_canon_swaps"]}
    for swap in proposals.get("au_canon_swaps", []):
        if swap["au_name"] not in existing_au_names:
            merged["au_canon_swaps"].append(swap)
    return merged


def _active_swaps_for_chapter(au_canon_swaps, chapter_n):
    return [s for s in au_canon_swaps if chapter_n >= s.get("effective_from_chapter", 0)]


def apply_name_canon(text, characters_data, chapter_n=None):
    """Deterministic find/replace pass. Longer aliases are replaced first so that, e.g.,
    'Xiao Ming' doesn't get partially clobbered by a shorter alias."""
    canonical_names = characters_data.get("canonical_names", {})
    aliases = sorted(canonical_names.keys(), key=len, reverse=True)
    for alias in aliases:
        canonical = canonical_names[alias]
        if alias == canonical:
            continue
        text = re.sub(re.escape(alias), canonical, text)

    if chapter_n is not None:
        active_swaps = _active_swaps_for_chapter(characters_data.get("au_canon_swaps", []), chapter_n)
        for swap in active_swaps:
            text = re.sub(re.escape(swap["au_name"]), swap["replaced_by_canon"], text)

    return text
