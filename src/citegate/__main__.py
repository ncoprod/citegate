"""python -m citegate answer.json sources.json [--today YYYY-MM-DD]

answer.json : [{"text": ..., "citations": [{"source_id", "passage_id", "quote", "version"?}]}]
sources.json: [{"id", "passages": {"p1": "..."}, "valid_until"?, "mode"?}]
Prints the verdict as JSON. Exit code 0 if accepted, 1 otherwise.
"""
import argparse
import json
import sys
from dataclasses import asdict
from datetime import date

from . import Citation, Sentence, Source, check


def main(argv=None):
    ap = argparse.ArgumentParser(prog="citegate")
    ap.add_argument("answer")
    ap.add_argument("sources")
    ap.add_argument("--today", type=date.fromisoformat)
    a = ap.parse_args(argv)
    with open(a.answer, encoding="utf-8") as f:
        answer = [Sentence(s["text"], [Citation(**c) for c in s.get("citations", [])]) for s in json.load(f)]
    with open(a.sources, encoding="utf-8") as f:
        sources = {}
        for s in json.load(f):
            vu = s.get("valid_until")
            sources[s["id"]] = Source(s["id"], s["passages"], date.fromisoformat(vu) if vu else None, s.get("mode", "auto"))
    v = check(answer, sources, a.today)
    print(json.dumps(asdict(v), ensure_ascii=False, indent=2))
    return 0 if v.accepted else 1


if __name__ == "__main__":
    sys.exit(main())
