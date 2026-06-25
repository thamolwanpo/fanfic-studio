"""EPUB I/O: spine inspector, resolved chapter<->spine map, and chapter read/replace/append/export.

The spine (not file order) is the authoritative sequence (README §8). AO3 exports include
front matter / endnotes as spine items, so we build a chapter<->spine map once at import and
every feature reads chapters through it instead of raw spine index.
"""
import re

import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

from core.files import read_json, write_json

FRONT_MATTER_HINTS = re.compile(
    r"\b(title page|summary|notes?|preface|foreword|acknowledg|tags?|table of contents|toc)\b",
    re.IGNORECASE,
)


def inspect_spine(epub_path):
    """Return a list of dicts describing every spine item: index, file id, title guess, preview."""
    book = epub.read_epub(epub_path, options={"ignore_ncx": True})
    items = []
    for idx, (item_id, _linear) in enumerate(book.spine):
        item = book.get_item_with_id(item_id)
        if item is None or item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue
        soup = BeautifulSoup(item.get_content(), "lxml")
        title_tag = soup.find(["h1", "h2", "h3", "title"])
        title = title_tag.get_text(strip=True) if title_tag else ""
        text = soup.get_text(" ", strip=True)
        looks_like_front_matter = bool(FRONT_MATTER_HINTS.search(title)) or len(text) < 200
        items.append({
            "spine_index": idx,
            "item_id": item_id,
            "file_name": item.get_name(),
            "title_guess": title,
            "preview": text[:100],
            "likely_chapter": not looks_like_front_matter,
        })
    return items


def build_chapter_map(epub_path, chapter_spine_indices):
    """Given the user-confirmed list of spine indices that are real chapters (in order),
    build the resolved chapter number -> spine index map. Chapter numbers are 1-based,
    in the order the spine indices were given."""
    return {str(n + 1): spine_index for n, spine_index in enumerate(chapter_spine_indices)}


def save_chapter_map(project, chapter_map):
    write_json(project.chapter_map_json, chapter_map)


def load_chapter_map(project):
    return read_json(project.chapter_map_json, default={})


def chapter_count(project):
    return len(load_chapter_map(project))


def _get_book(epub_path):
    return epub.read_epub(epub_path, options={"ignore_ncx": True})


def _spine_index_for_chapter(project, chapter_n):
    chapter_map = load_chapter_map(project)
    key = str(chapter_n)
    if key not in chapter_map:
        raise ValueError(f"Chapter {chapter_n} is not in the chapter map.")
    return chapter_map[key]


def _item_for_spine_index(book, spine_index):
    item_id, _linear = book.spine[spine_index]
    return book.get_item_with_id(item_id)


def read_chapter_text(epub_path, project, chapter_n):
    """Return (title, plain_text, html) for a chapter, resolved through the chapter map."""
    spine_index = _spine_index_for_chapter(project, chapter_n)
    book = _get_book(epub_path)
    item = _item_for_spine_index(book, spine_index)
    soup = BeautifulSoup(item.get_content(), "lxml")
    title_tag = soup.find(["h1", "h2", "h3"])
    title = title_tag.get_text(strip=True) if title_tag else f"Chapter {chapter_n}"
    body = soup.find("body") or soup
    text = body.get_text("\n", strip=True)
    return title, text, str(soup)


def _paragraphs_to_html(title, paragraphs):
    safe_title = BeautifulSoup(f"<div>{title}</div>", "lxml").get_text()
    body_html = "".join(f"<p>{BeautifulSoup(p, 'lxml').get_text()}</p>" for p in paragraphs if p.strip())
    return (
        "<?xml version='1.0' encoding='utf-8'?>\n"
        "<html xmlns=\"http://www.w3.org/1999/xhtml\">\n<head><title>{t}</title></head>\n"
        "<body><h2>{t}</h2>\n{b}\n</body>\n</html>"
    ).format(t=safe_title, b=body_html)


def replace_chapter(working_epub_path, project, chapter_n, title, new_text):
    """Replace the chapter's content in working.epub in place. new_text is treated as
    plain text with paragraphs separated by blank lines; dialogue-on-its-own-line formatting
    should already be applied to new_text before calling this."""
    spine_index = _spine_index_for_chapter(project, chapter_n)
    book = _get_book(working_epub_path)
    item = _item_for_spine_index(book, spine_index)
    paragraphs = [p for p in re.split(r"\n\s*\n", new_text) if p.strip()]
    html = _paragraphs_to_html(title, paragraphs)
    item.set_content(html.encode("utf-8"))
    epub.write_epub(working_epub_path, book)


def append_chapter(working_epub_path, project, title, new_text):
    """Append a brand-new chapter to working.epub, add it to the spine, and extend the
    chapter map with the next chapter number. Returns the new chapter number."""
    book = _get_book(working_epub_path)
    paragraphs = [p for p in re.split(r"\n\s*\n", new_text) if p.strip()]
    html = _paragraphs_to_html(title, paragraphs)

    chapter_map = load_chapter_map(project)
    next_chapter_n = max((int(k) for k in chapter_map.keys()), default=0) + 1
    file_name = f"chapter_{next_chapter_n:04d}.xhtml"
    item_id = f"chap_{next_chapter_n:04d}"

    new_item = epub.EpubHtml(title=title, file_name=file_name, uid=item_id)
    new_item.set_content(html.encode("utf-8"))
    book.add_item(new_item)
    book.spine.append((item_id, "yes"))
    new_spine_index = len(book.spine) - 1

    epub.write_epub(working_epub_path, book)

    chapter_map[str(next_chapter_n)] = new_spine_index
    save_chapter_map(project, chapter_map)
    return next_chapter_n


def export_path(project):
    return project.working_epub
