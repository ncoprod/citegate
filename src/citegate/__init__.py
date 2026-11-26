"""citegate: refuse any answer that cannot be traced word for word to a valid source.

A gate never fixes an answer; it only accepts it or says why it must go to a human.
The gates check provenance (the quote exists, in this version, in a usable source), and that
every figure in a sentence appears in what it quotes (digits or words), and that a sentence is not negative
when its quotes are positive or the reverse. They do not prove that the sentence is a correct reading of the
quote: that is the human reviewer's job.
"""
from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

__all__ = ["DEFAULT_GATES", "STRICT_GATES", "Citation", "Sentence", "Source", "Verdict", "check", "version_of"]

MIN_QUOTE_CHARS = 20
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


_CODE = re.compile(r"(?<![^\W_])[A-Z]\d[A-Z](?![^\W_])")  # whole-word B2B, B2C, P2P, B2G


def _figures(text: str) -> list[str]:
    """Numbers in a text. Only whole-word codes of one capital, one digit, one capital (B2B, B2C, P2P) are
    left out; anything else with a digit (Form 10F, G20, EUR 750m) is a figure that must be in the quote."""
    return _NUMBER.findall(_CODE.sub(" ", text))


_UNITS = {
    # English
    "zero": 0, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90, "hundred": 100, "thousand": 1000, "million": 1000000,
    # French ("un/une/one" are left out: they are mostly articles)
    "zéro": 0, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "sept": 7, "huit": 8, "neuf": 9, "dix": 10,
    "onze": 11, "douze": 12, "treize": 13, "quatorze": 14, "quinze": 15, "seize": 16, "vingt": 20, "trente": 30,
    "quarante": 40, "cinquante": 50, "soixante": 60, "cent": 100, "mille": 1000,
}
_TENS = {k for k, v in _UNITS.items() if v in (20, 30, 40, 50, 60, 70, 80, 90)}
_WORD = re.compile(r"[^\W\d_]+(?:-[^\W\d_]+)*")


def _number_words(text: str) -> list[str]:
    """Numbers written in words ("twenty", "forty-five", "quinze"), as digits, so they are checked like figures."""
    out = []
    for w in _WORD.findall(text.lower()):
        parts = w.split("-")
        if all(p in _UNITS for p in parts):
            if len(parts) == 2 and parts[0] in _TENS and _UNITS[parts[1]] < 10:
                out.append(str(_UNITS[parts[0]] + _UNITS[parts[1]]))
            else:
                out += [str(_UNITS[p]) for p in parts]
    return out


_NEGATION = re.compile(
    r"\b(not|no|never|none|nor|cannot|can't|isn't|aren't|doesn't|don't|won't|without|except|unless"
    r"|only (?:if|when|where)"                                        # "only if" = "not ... unless"
    r"|ne|n'|pas|jamais|aucun|aucune|ni|sans|sauf|seulement si|uniquement si|que si"
    r"|nicht|kein|keine|keinen|keiner|nie|ohne|außer|nur,? wenn|nur,? falls"
    r"|nunca|ningún|ninguna|sin|salvo|solo si|sólo si|excepto"
    r"|non|mai|nessun|nessuna|senza|tranne|solo se"
    r"|niet|geen|nooit|zonder|tenzij|pas als|alleen als|enkel als"
    r"|não|nem|nenhum|nenhuma|sem|exceto|apenas se|só se"
    r"|inte|ej|ingen|inget|aldrig|utan|förutom|endast om"
    r"|nie|bez|żaden|żadna|tylko jeśli"
    r"|değil|yok|hiç|olmadan|sadece"
    r"|tidak|bukan|tanpa|kecuali|hanya jika)\b",
    re.IGNORECASE)
_UNREAD_SCRIPT = re.compile(r"[\u0600-\u06FF\u3040-\u30FF\u3400-\u9FFF\uAC00-\uD7AF]")  # Arabic, kana, CJK, Hangul


# A condition or a time limit changes what a rule says: "10% if the recipient holds a certificate", "before 2024".
# A condition, or a limit in time that ends a rule, changes what it says: "10% if the recipient holds a certificate",
# "before 2024". A start ("since 2024", "from April") describes the rule in force and is not required. Words that
# are also common in other senses ("subject to", "after", "voor") are left out: when unsure, this gate accepts, and
# the other gates and the model's instructions still apply.
_CONDITION = re.compile(
    r"\b(if|unless|only|provided that|on condition|except|before|until"
    r"|si|s'il|s'ils|sauf|seulement|uniquement|à condition|sous réserve|excepté|avant|jusqu"
    r"|wenn|falls|nur|sofern|soweit|außer|ausgenommen|bis"
    r"|sólo|salvo|excepto|siempre que|antes de|hasta"
    r"|purché|tranne|prima|fino a"
    r"|alleen|tenzij|vóór"
    r"|apenas|só|desde que|exceto|até)\b",
    re.IGNORECASE)


def _conditional(text: str) -> bool:
    return bool(_CONDITION.search(text.replace("\u2019", "'")))


def _negative(text: str) -> bool:
    return bool(_NEGATION.search(text.replace("\u2019", "'")))


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
    have |= set(_number_words(quoted))
    missing = [n for n in _figures(s.text) + _number_words(s.text) if n not in have]
    return [f"figure {n} is not in the quoted text" for n in dict.fromkeys(missing)]


def gate_negation(i, s, sources, today):
    """A sentence cannot say the opposite of what it quotes: if one is negative (not, ne...pas, nicht, sin...),
    the other must be too. Coarse on purpose: a false refusal sends the question to a human, never the reverse."""
    if not s.citations:
        return []
    readable = [c for c in s.citations if not _UNREAD_SCRIPT.search(c.quote)]
    if not readable:  # fail closed: this gate cannot read the quotes' language, so a human checks the sentence
        return ["negation cannot be checked in the language of the quotes"]
    quotes_negative = any(_negative(c.quote) for c in readable)
    if _negative(s.text) and not quotes_negative:
        return ["the sentence is negative but none of its quotes is"]
    if quotes_negative and not _negative(s.text) and all(_negative(c.quote) for c in readable):
        return ["every quote is negative but the sentence is not"]
    return []


def gate_conditions(i, s, sources, today):
    """A sentence cannot drop the condition or the time limit its quotes carry: if every quote it relies on has one
    ("if", "unless", "only", "before", "until"...), the sentence must keep one too. Coarse like the negation gate,
    and fails the same way: a refusal sends the sentence back for a repair, then to a human, never the reverse."""
    readable = [c for c in s.citations if not _UNREAD_SCRIPT.search(c.quote)]
    if readable and all(_conditional(c.quote) for c in readable) and not _conditional(s.text):
        return ["every quote carries a condition or a time limit that the sentence drops"]
    return []


_END = ".!?;:"


def gate_whole_sentence(i, s, sources, today):
    """Optional, stricter: each quote must start and end on a sentence boundary of the passage, so a quote
    cannot drop the condition or the date that changes its meaning ("Before 2024, the rate was 10%")."""
    out = []
    for c in s.citations:
        src = sources.get(c.source_id)
        text = _norm(src.passages.get(c.passage_id, "")) if src else ""
        q = _norm(c.quote).rstrip(_END + " ")
        at = text.find(q)
        if at < 0:
            continue  # the verbatim gate reports it
        before = text[:at].rstrip()
        after = text[at + len(q):].lstrip()
        if (before and before[-1] not in _END) or (after and after[0] not in _END):
            out.append(f"quote from {c.source_id}/{c.passage_id} is not a whole sentence")
    return out


DEFAULT_GATES: dict[str, Gate] = {
    "cited": gate_cited,
    "known": gate_known,
    "verbatim": gate_verbatim,
    "version": gate_version,
    "valid": gate_valid,
    "mode": gate_mode,
    "figures": gate_figures,
    "negation": gate_negation,
    "conditions": gate_conditions,
}
STRICT_GATES: dict[str, Gate] = DEFAULT_GATES | {"whole_sentence": gate_whole_sentence}


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
