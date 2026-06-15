"""Render the 'Sources used' block as a readable table for the Neo CLI."""
from __future__ import annotations

from typing import Any

from rich import box
from rich.console import Group
from rich.table import Table
from rich.text import Text


def _authors_short(authors: list[str] | None) -> str:
    surnames = [str(a).strip().split()[-1] for a in (authors or []) if str(a).strip()]
    if not surnames:
        return "-"
    return surnames[0] if len(surnames) == 1 else f"{surnames[0]} et al."


def _source_cell(evidence: dict[str, Any]) -> Group:
    """Title (clickable -> DOI), the supporting quote, then the ids (dim)."""
    title = (evidence.get("source_title") or "Untitled source").strip()
    url = evidence.get("url")
    quote = (evidence.get("text") or "").strip()
    evidence_id = evidence.get("evidence_id") or ""
    source_id = evidence.get("source_id") or ""

    title_text = Text(title, style="bold")
    if url:
        title_text.stylize(f"link {url}")  # OSC 8 hyperlink -> opens the DOI

    parts = [title_text]
    if quote:
        parts.append(Text(f"\u201c{quote}\u201d", style="italic dim"))
    ids = " \u00b7 ".join(p for p in (evidence_id, source_id) if p)
    if ids:
        parts.append(Text(ids, style="dim"))
    return Group(*parts)


def build_sources_table(evidence_items: list[dict[str, Any]]) -> Table:
    table = Table(
        box=box.SIMPLE_HEAD,
        show_lines=True,
        expand=True,
        pad_edge=False,
        title="Sources used",
        title_justify="left",
        title_style="bold",
        header_style="dim",
    )
    table.add_column("#", justify="right", style="dim", width=2, no_wrap=True)
    table.add_column("Source", ratio=6, overflow="fold")
    table.add_column("Authors", ratio=2, overflow="fold")
    table.add_column("Year", justify="center", width=4, no_wrap=True)
    table.add_column("Section", ratio=3, min_width=14, overflow="fold")
    table.add_column("Page", justify="center", width=4, no_wrap=True)
    table.add_column("\u00b6", justify="center", width=8, overflow="fold")

    for index, ev in enumerate(evidence_items, start=1):
        page = ev.get("page")
        table.add_row(
            str(index),
            _source_cell(ev),
            _authors_short(ev.get("authors")),
            str(ev.get("year") or "-"),
            ev.get("section") or "-",
            str(page) if page not in (None, "") else "-",
            str(ev.get("paragraph") or "-"),
        )
    return table