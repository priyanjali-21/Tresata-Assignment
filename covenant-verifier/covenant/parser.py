"""Deterministic retrieval: definitions by name, sections by number, dependencies by longest match.

No LLM here. Everything this module returns is an exact slice of the source text.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

BLOCK_TAGS = ["p", "div", "li", "td", "h1", "h2", "h3", "h4"]
DEF_START = re.compile(
    r'^[“"]([^”"]{1,100})[”"]\s+(?:means|shall mean|has the meaning|have the meanings)\b'
)
PAGE_FOOTER = re.compile(r"^-?\s*\d{1,3}\s*-?$")
SECTION_HEAD = re.compile(r"^Section\s+(\d+\.\d+)\.?\s+([A-Z][^.]{2,80})\.\s")
TOC_LINE = re.compile(r"\.{4,}\s*\d+\s*$")

# Terms that never change the arithmetic. Kept as plain names, not dependencies.
STOP_LIST = {"Person", "GAAP", "Business Day", "Administrative Agent", "Borrower", "Subsidiary"}
# Procedural terms: matter for evidence checks, not for the calculator.
PROCEDURAL = {"Compliance Certificate", "Responsible Officer"}


def normalize(text: str) -> str:
    text = text.replace("\u00a0", " ").replace("\u00ad", "")
    return re.sub(r"\s+", " ", text).strip()


def html_blocks(raw_html: str) -> list[str]:
    """Leaf block texts in document order. Leaf only, so nested divs are not duplicated."""
    soup = BeautifulSoup(raw_html, "html.parser")
    for node in soup(["script", "style", "noscript"]):
        node.decompose()
    out = []
    for el in soup.find_all(BLOCK_TAGS):
        if el.find(BLOCK_TAGS):
            continue
        t = normalize(el.get_text(" "))
        if t and not PAGE_FOOTER.fullmatch(t):
            out.append(t)
    return out


@dataclass
class ParsedAgreement:
    definitions: dict[str, str]
    sections: dict[str, str]
    warnings: list[str] = field(default_factory=list)
    full_text: str = ""


def parse(raw_html: str, require_definitions: bool = True) -> ParsedAgreement:
    blocks = html_blocks(raw_html)
    definitions: dict[str, str] = {}
    sections: dict[str, str] = {}
    warnings: list[str] = []
    current_section: str | None = None
    current_def: str | None = None

    for t in blocks:
        if TOC_LINE.search(t):           # table-of-contents lines never open a section
            continue
        m = SECTION_HEAD.match(t)
        if m:
            current_section, current_def = m.group(1), None
            if current_section in sections:
                warnings.append(f"duplicate section heading: {current_section}")
            sections[current_section] = t
            continue
        if current_section is None:
            continue
        sections[current_section] += " " + t
        if current_section == "1.01":
            d = DEF_START.match(t)
            if d:
                current_def = d.group(1)
                if current_def in definitions:
                    warnings.append(f"duplicate definition: {current_def}")
                definitions[current_def] = t
            elif current_def:             # multi-paragraph definitions: (a), (b), provisos
                definitions[current_def] += " " + t

    if require_definitions and "1.01" not in sections:
        raise ValueError("Section 1.01 not found: refusing to guess where definitions are.")
    if require_definitions and not definitions:
        raise ValueError("Section 1.01 found but no definitions matched; check quote style.")
    return ParsedAgreement(definitions, sections, warnings, normalize(" ".join(blocks)))


def _variants(name: str) -> list[str]:
    v = [name, name + "s", name + "’s", name + "'s"]
    if name.endswith("y"):
        v.append(name[:-1] + "ies")
    return v


def dependencies(term: str, defs: dict[str, str]) -> dict[str, list[str]]:
    """Defined terms used inside `term`'s definition, longest match first, with masking.

    Returns computational, procedural and stop-listed terms separately, plus section cross-references.
    """
    text = defs[term]
    text = DEF_START.sub("", text, count=1)          # drop the term's own heading
    found: list[str] = []
    for name in sorted(defs, key=len, reverse=True):
        if name == term:
            continue
        pattern = r"(?<![A-Za-z])(?:" + "|".join(re.escape(x) for x in sorted(_variants(name), key=len, reverse=True)) + r")(?![A-Za-z])"
        if re.search(pattern, text):
            found.append(name)
            text = re.sub(pattern, " ", text)       # mask so shorter names cannot match inside it
    sections = sorted(set(re.findall(r"Section\s+(\d+\.\d+)", defs[term])))
    return {
        "computational": sorted(n for n in found if n not in STOP_LIST | PROCEDURAL),
        "procedural": sorted(n for n in found if n in PROCEDURAL),
        "stop_listed": sorted(n for n in found if n in STOP_LIST),
        "section_refs": sections,
    }


def quote_in_source(quote: str, source_text: str) -> bool:
    def norm(s: str) -> str:
        s = s.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
        return re.sub(r"\s+", " ", s).strip().lower()
    return norm(quote) in norm(source_text)
