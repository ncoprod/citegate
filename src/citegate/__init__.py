"""citegate: refuse any answer that cannot be traced word for word to a valid source.

A gate never fixes an answer; it only accepts it or says why it must go to a human.
The gates check provenance (the quote exists, in this version, in a usable source), and that
every figure in a sentence appears in what it quotes. They do not prove that the sentence is a
correct reading of the quote: that is the human reviewer's job.
"""
from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

__all__ = ["DEFAULT_GATES", "Citation", "Sentence", "Source", "Verdict", "check", "version_of"]

MIN_QUOTE_CHARS = 20
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


_CODE = re.compile(r"(?<![^\W_])[A-Z]\d[A-Z](?![^\W_])")  # whole-word B2B, B2C, P2P, B2G


def _figures(text: str) -> list[str]:
    """Numbers in a text. Only whole-word codes of one capital, one digit, one capital (B2B, B2C, P2P) are
    left out; anything else with a digit (Form 10F, G20, EUR 750m) is a figure that must be in the quote."""
    return _NUMBER.findall(_CODE.sub(" ", text))


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def version_of(passages: dict[str, str]) -> str:
    """Short hash of a source's passages: any edit changes it."""
    blob = "\n".join(f"{k}\t{_norm(v)}" for k, v in sorted(passages.items()))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


@dataclass
class Source:
    id: str
    passages: dict[str, str]
    valid_until: date | None = None
    mode: str = "auto"  # "auto" or "contact_only"
    version: str = ""

    def __post_init__(self):
        if not self.version:
            self.version = version_of(self.passages)


@dataclass(frozen=True)
class Citation:
    source_id: str
    passage_id: str
    quote: str
    version: str | None = None


@dataclass
class Sentence:
    text: str
    citations: list[Citation] = field(default_factory=list)


@dataclass
class Verdict:
    accepted: bool
    failures: list[dict] = field(default_factory=list)  # {"gate", "sentence", "reason"}


Gate = Callable[[int, Sentence, dict[str, Source], date], list[str]]


def gate_cited(i, s, sources, today):
    return [] if s.citations else ["sentence has no citation"]


def gate_known(i, s, sources, today):
    out = []
    for c in s.citations:
        src = sources.get(c.source_id)
        if src is None:
            out.append(f"unknown source {c.source_id}")
        elif c.passage_id not in src.passages:
            out.append(f"unknown passage {c.source_id}/{c.passage_id}")
    return out


def gate_verbatim(i, s, sources, today):
    out = []
    for c in s.citations:
        src = sources.get(c.source_id)
        if src is None or c.passage_id not in src.passages:
            continue
        q = _norm(c.quote)
        if len(q) < MIN_QUOTE_CHARS:
            out.append(f"quote shorter than {MIN_QUOTE_CHARS} characters in {c.source_id}/{c.passage_id}")
        elif q not in _norm(src.passages[c.passage_id]):
            out.append(f"quote not found word for word in {c.source_id}/{c.passage_id}")
    return out


def gate_version(i, s, sources, today):
    return [f"{c.source_id} cited in version {c.version}, current is {sources[c.source_id].version}"
            for c in s.citations
            if c.version and c.source_id in sources and c.version != sources[c.source_id].version]


def gate_valid(i, s, sources, today):
    return [f"{c.source_id} expired on {sources[c.source_id].valid_until}"
            for c in s.citations
            if c.source_id in sources and sources[c.source_id].valid_until and sources[c.source_id].valid_until < today]


def gate_mode(i, s, sources, today):
    return [f"{c.source_id} is contact_only: its content cannot be used in an automatic answer"
            for c in s.citations if c.source_id in sources and sources[c.source_id].mode != "auto"]


def gate_figures(i, s, sources, today):
    """Every number in the sentence (rate, amount, date, article) must appear in one of its quotes."""
    quoted = " ".join(c.quote for c in s.citations)
    have = set(_figures(quoted))
    missing = [n for n in _figures(s.text) if n not in have]
    return [f"figure {n} is not in the quoted text" for n in missing]


DEFAULT_GATES: dict[str, Gate] = {
    "cited": gate_cited,
    "known": gate_known,
    "verbatim": gate_verbatim,
    "version": gate_version,
    "valid": gate_valid,
    "mode": gate_mode,
    "figures": gate_figures,
}


def check(sentences: list[Sentence], sources: dict[str, Source], today: date | None = None,
          gates: dict[str, Gate] | None = None) -> Verdict:
    """Run every gate on every sentence. Accepted only if nothing failed and there is an answer."""
    today = today or date.today()
    gates = gates or DEFAULT_GATES
    failures = []
    if not sentences:
        failures.append({"gate": "cited", "sentence": None, "reason": "empty answer"})
    for i, s in enumerate(sentences):
        for name, gate in gates.items():
            for reason in gate(i, s, sources, today):
                failures.append({"gate": name, "sentence": i, "reason": reason})
    return Verdict(accepted=not failures, failures=failures)
