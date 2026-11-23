# citegate

Refuse any answer that cannot be traced word for word to a valid source. No dependencies, one file.

It is the generic version of the gates of Riposte (French tax case law): there, a quote had to sit in
the right version of the decision. Here, any answer made of sentences, each citing passages of sources.

| Gate | Refuses when |
|---|---|
| `cited` | a sentence (or the whole answer) cites nothing |
| `known` | the cited source or passage does not exist |
| `verbatim` | the quote is not found word for word in the passage, or is shorter than 20 characters |
| `version` | the quote was taken from an older version of the source |
| `valid` | the source has expired |
| `mode` | the source is `contact_only` (its author did not allow automatic answers) |
| `figures` | the sentence contains a number (rate, amount, date) absent from its quotes |

**What it does not do:** check that a sentence is a correct reading of its quote. The gates only
stop unproven answers. A refused answer goes to a human with the list of reasons.

```bash
uv run pytest -q                                   # traps
uv run python -m citegate answer.json sources.json # exit 0 accepted, 1 refused
```

```python
from citegate import Source, Sentence, Citation, check
v = check([Sentence("A 10% withholding applies.", [Citation("m1", "p1", "subject to a 10% withholding")])],
          {"m1": Source("m1", {"p1": "... are subject to a 10% withholding."})})
v.accepted, v.failures
```
