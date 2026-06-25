"""Shared LLM pipeline patterns (README §5), reused by every feature.

Every pattern uses separate API calls with fresh context per role; nothing accumulates
into one ever-growing prompt. All context assembly goes through build_context so no
single call can exceed the model's limit.
"""
from llm.models import context_limit

# Decided once here per README §5.3: long chapters are split into scene-sized chunks
# with a fixed overlap so context isn't lost at chunk boundaries.
CHUNK_SIZE_CHARS = 6000
CHUNK_OVERLAP_CHARS = 600

CHARS_PER_TOKEN = 4  # rough heuristic for the budgeter; good enough to stay safely under limits


def chunk_text(text, chunk_size=CHUNK_SIZE_CHARS, overlap=CHUNK_OVERLAP_CHARS):
    """Split text into overlapping chunks, breaking on paragraph boundaries where possible."""
    if len(text) <= chunk_size:
        return [text]
    paragraphs = text.split("\n\n")
    chunks = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) + 2 > chunk_size and current:
            chunks.append(current)
            current = current[-overlap:] if overlap else ""
        current = f"{current}\n\n{para}" if current else para
    if current:
        chunks.append(current)
    return chunks


def _tokens(text):
    return len(text) // CHARS_PER_TOKEN


def build_context(model, primary_text, supporting=None, reserve_for_output_tokens=2000):
    """Decide how the model's token limit is divided between the primary text (chapter/
    draft/chunk) and supporting context blocks, trimming least-critical-first when it
    won't all fit.

    `supporting` is an ordered list of (label, text, priority) tuples, priority ascending
    = trimmed first. README ordering: world bible -> name canon -> style guide -> recent
    summaries, i.e. recent summaries are least critical and trimmed first.
    """
    supporting = supporting or []
    budget_tokens = context_limit(model) - reserve_for_output_tokens
    primary_tokens = _tokens(primary_text)
    remaining = budget_tokens - primary_tokens

    ordered = sorted(supporting, key=lambda item: item[2])
    kept = []
    for label, text, _priority in reversed(ordered):
        cost = _tokens(text)
        if cost <= remaining:
            kept.append((label, text))
            remaining -= cost
        elif remaining > 200:
            truncated_chars = remaining * CHARS_PER_TOKEN
            kept.append((label, text[:truncated_chars] + "\n[...trimmed to fit context...]"))
            remaining = 0
        else:
            break

    kept.reverse()
    context_blocks = "\n\n".join(f"## {label}\n{text}" for label, text in kept)
    return context_blocks, primary_text


def map_reduce_summarize(chapters, summarize_fn, reduce_fn=None):
    """Map: summarize each chapter independently. Reduce: optionally fold all summaries
    into one result via reduce_fn. `chapters` is an iterable of (n, text). `summarize_fn`
    is called as summarize_fn(n, text) -> summary_dict. Generator; yields progress."""
    summaries = []
    total = len(chapters)
    for i, (n, text) in enumerate(chapters, start=1):
        yield {"step": "map", "progress": i, "total": total, "chapter": n}
        summary = summarize_fn(n, text)
        summaries.append(summary)
    if reduce_fn is not None:
        yield {"step": "reduce"}
        result = reduce_fn(summaries)
        yield {"step": "done", "result": result}
    else:
        yield {"step": "done", "result": summaries}


def reflection_loop(draft_fn, critique_fn, revise_fn, max_iters=3, is_done_fn=None):
    """The default pattern for generative tasks (README §5.1). Three separate calls per
    iteration, each with only the context it needs:
      draft_fn() -> str
      critique_fn(draft) -> list[dict]   (small structured fix list, not a rewrite)
      revise_fn(draft, fixes) -> str
      is_done_fn(draft, fixes) -> bool   (optional early stop, e.g. critique returned no fixes)

    Generator; yields a dict per step so the UI can stream progress including a running
    count toward max_iters. The caller is responsible for the human "good enough" gate:
    after each yielded 'iteration_done' step it can stop consuming the generator to accept,
    or keep iterating by calling .send(feedback) — feedback is appended to the next
    critique call's context via critique_fn closing over mutable state if needed.
    """
    draft = draft_fn()
    yield {"step": "draft", "iteration": 0, "max_iters": max_iters, "text": draft}

    for iteration in range(1, max_iters + 1):
        fixes = critique_fn(draft)
        yield {"step": "critique", "iteration": iteration, "max_iters": max_iters, "fixes": fixes}

        if not fixes or (is_done_fn and is_done_fn(draft, fixes)):
            yield {"step": "done", "iteration": iteration, "max_iters": max_iters, "text": draft}
            return

        draft = revise_fn(draft, fixes)
        yield {"step": "revise", "iteration": iteration, "max_iters": max_iters, "text": draft}

    yield {"step": "max_iters_reached", "iteration": max_iters, "max_iters": max_iters, "text": draft}
