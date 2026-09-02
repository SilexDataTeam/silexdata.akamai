"""Generate docs/docsite/rst/coverage-report.rst from a coverage.py HTML report's index page.

Parses the file table's rows (name, href, statements, missing, coverage %) directly out of
index.html, rather than coverage.xml, since coverage.xml has no per-file HTML page names to
link to. Each file's link is rewritten relative to the docsite page this generates, which
build.sh places one directory level below the docsite root - matching /coverage/'s own depth
once docs.yml's deploy job combines both reports into a single GitHub Pages deployment.

Usage: generate_coverage_summary.py <path/to/coverage/index.html> <output.rst>
"""

from __future__ import annotations

import sys
from html.parser import HTMLParser


class _IndexTableParser(HTMLParser):
    """Collects (text, href) pairs for each <td> in the <tbody> of coverage.py's index.html."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[tuple[str, str | None]]] = []
        self._row: list[tuple[str, str | None]] | None = None
        self._cell: list[str] | None = None
        self._href: str | None = None
        self._in_tbody = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "tbody":
            self._in_tbody = True
        elif tag == "tr" and self._in_tbody:
            self._row = []
        elif tag == "td" and self._row is not None:
            self._cell = []
        elif tag == "a" and self._cell is not None:
            self._href = attrs_dict.get("href")

    def handle_endtag(self, tag: str) -> None:
        if tag == "tbody":
            self._in_tbody = False
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None
        elif tag == "td" and self._cell is not None:
            assert self._row is not None
            self._row.append(("".join(self._cell).strip(), self._href))
            self._cell = None
            self._href = None

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)


def main(index_html_path: str, output_rst_path: str) -> None:
    with open(index_html_path, encoding="utf-8") as f:
        html = f.read()

    parser = _IndexTableParser()
    parser.feed(html)

    lines = [
        "Coverage Summary",
        "=================",
        "",
        "Per-file line coverage from the latest test run. View the `full interactive",
        "coverage report <../coverage/index.html>`_ for line-by-line annotated detail,",
        "or click a file below to jump straight to its page.",
        "",
        ".. list-table::",
        "   :header-rows: 1",
        "",
        "   * - File",
        "     - Statements",
        "     - Missing",
        "     - Coverage",
    ]
    for row in parser.rows:
        name, href = row[0]
        statements = row[2][0]
        missing = row[3][0]
        coverage = row[6][0]
        name_cell = f"`{name} <../coverage/{href}>`_" if href else f"**{name}**"
        lines += [
            f"   * - {name_cell}",
            f"     - {statements}",
            f"     - {missing}",
            f"     - {coverage}",
        ]

    with open(output_rst_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
