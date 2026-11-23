"""Traps: each test builds an answer that looks plausible and must be refused for one precise reason."""
from datetime import date

from citegate import Citation, Sentence, Source, check

TODAY = date(2026, 11, 23)
P1 = "Under this fictitious rule, services supplied to a foreign company are subject to a 10% withholding."
P2 = "The fictitious exemption applies only when the recipient holds a residence certificate."
SRC = {"m1": Source("m1", {"p1": P1, "p2": P2}, valid_until=date(2027, 6, 30))}


def cite(quote, pid="p1", sid="m1", version=None):
    return Citation(sid, pid, quote, version)


def gates_failed(sentences, sources=SRC):
    return {f["gate"] for f in check(sentences, sources, TODAY).failures}


def test_accepts_exact_quote():
    v = check([Sentence("A 10% withholding applies.", [cite("subject to a 10% withholding")])], SRC, TODAY)
    assert v.accepted, v.failures


def test_whitespace_does_not_matter():
    assert check([Sentence("Exemption needs a certificate.", [cite("holds a  residence\ncertificate", "p2")])], SRC, TODAY).accepted


def test_empty_answer_refused():
    assert not check([], SRC, TODAY).accepted


def test_uncited_sentence_refused():
    assert "cited" in gates_failed([Sentence("A 10% withholding applies.")])


def test_altered_quote_refused():
    assert "verbatim" in gates_failed([Sentence("A 10% withholding applies.", [cite("subject to a 15% withholding")])])


def test_too_short_quote_refused():
    assert "verbatim" in gates_failed([Sentence("It applies.", [cite("10%")])])


def test_unknown_passage_refused():
    assert "known" in gates_failed([Sentence("Applies.", [cite("subject to a 10% withholding", pid="p9")])])


def test_unknown_source_refused():
    assert "known" in gates_failed([Sentence("Applies.", [cite("subject to a 10% withholding", sid="m404")])])


def test_old_version_refused():
    assert "version" in gates_failed([Sentence("A 10% withholding applies.", [cite("subject to a 10% withholding", version="deadbeef00000000")])])


def test_current_version_accepted():
    v = SRC["m1"].version
    assert check([Sentence("A 10% withholding applies.", [cite("subject to a 10% withholding", version=v)])], SRC, TODAY).accepted


def test_edit_changes_version():
    edited = Source("m1", {"p1": P1.replace("10%", "12%"), "p2": P2})
    assert edited.version != SRC["m1"].version


def test_expired_source_refused():
    old = {"m1": Source("m1", {"p1": P1}, valid_until=date(2026, 1, 1))}
    assert "valid" in gates_failed([Sentence("A 10% withholding applies.", [cite("subject to a 10% withholding")])], old)


def test_contact_only_refused():
    private = {"m1": Source("m1", {"p1": P1}, mode="contact_only")}
    assert "mode" in gates_failed([Sentence("A 10% withholding applies.", [cite("subject to a 10% withholding")])], private)


def test_invented_figure_refused():
    # the quote is real, but the sentence adds a figure the quote does not contain
    assert "figures" in gates_failed([Sentence("A 10% withholding applies from 2027.", [cite("subject to a 10% withholding")])])


def test_one_bad_sentence_refuses_the_answer():
    good = Sentence("A 10% withholding applies.", [cite("subject to a 10% withholding")])
    bad = Sentence("No certificate is needed.", [])
    assert not check([good, bad], SRC, TODAY).accepted


def test_codes_like_b2c_are_not_figures():
    src = {"m": Source("m", {"p1": "Supplies of software to consumers are taxed where the customer lives."})}
    ok = check([Sentence("B2C software supplies are taxed where the customer lives.",
                         [Citation("m", "p1", "Supplies of software to consumers are taxed where the customer lives")])],
               src, date(2026, 1, 1))
    assert ok.accepted, ok.failures
    bad = check([Sentence("Form 10F is required.",
                          [Citation("m", "p1", "Supplies of software to consumers are taxed where the customer lives")])],
                src, date(2026, 1, 1))
    assert not bad.accepted
