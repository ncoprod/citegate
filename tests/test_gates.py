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


def test_negation_flip_is_refused():
    src = {"m": Source("m", {"p1": "The exemption does not apply to SaaS sold to consumers."})}
    flip = [Sentence("The exemption applies to SaaS.", [Citation("m", "p1", "The exemption does not apply to SaaS")])]
    same = [Sentence("L'exonération ne s'applique pas au SaaS.",
                     [Citation("m", "p1", "The exemption does not apply to SaaS")])]
    assert not check(flip, src, date(2026, 1, 1)).accepted
    assert check(same, src, date(2026, 1, 1)).accepted


def test_numbers_in_words_are_figures():
    src = {"m": Source("m", {"p1": "Since 2024 the rate is 20% for all digital services."})}
    wrong = [Sentence("The rate is twenty-five percent.", [Citation("m", "p1", "Since 2024 the rate is 20%")])]
    right = [Sentence("The rate is twenty percent.", [Citation("m", "p1", "Since 2024 the rate is 20%")])]
    assert not check(wrong, src, date(2026, 1, 1)).accepted
    assert check(right, src, date(2026, 1, 1)).accepted


def test_strict_mode_refuses_a_clipped_quote():
    from citegate import STRICT_GATES
    src = {"m": Source("m", {"p1": "Before 2024, the reduced rate was 10% for e-books. Since 2024 the rate is 20%."})}
    clipped = [Sentence("The rate is 10%.", [Citation("m", "p1", "the reduced rate was 10% for e-books")])]
    whole = [Sentence("Before 2024 the rate was 10%.",
                      [Citation("m", "p1", "Before 2024, the reduced rate was 10% for e-books.")])]
    assert check(clipped, src, date(2026, 1, 1)).accepted  # default gates: provenance only
    assert not check(clipped, src, date(2026, 1, 1), STRICT_GATES).accepted
    assert check(whole, src, date(2026, 1, 1), STRICT_GATES).accepted


def test_negation_is_read_in_the_corpus_languages():
    src = {"m": Source("m", {"p1": "Het enkele feit dat een werknemer thuis werkt, is niet voldoende.",
                             "p2": "Interest paid to an affiliate is deductible only if the recipient is taxed enough."})}
    nl = [Sentence("Working from home is not enough by itself.",
                   [Citation("m", "p1", "Het enkele feit dat een werknemer thuis werkt, is niet voldoende")])]
    only_if = [Sentence("Interest to an affiliate is not deductible unless the recipient is taxed enough.",
                        [Citation("m", "p2", "deductible only if the recipient is taxed enough")])]
    assert check(nl, src, date(2026, 1, 1)).accepted
    assert check(only_if, src, date(2026, 1, 1)).accepted


def test_negation_gate_fails_closed_on_scripts_it_cannot_read():
    src = {"m": Source("m", {"p1": "外国企業は日本で消費税の登録が必要です。登録番号を請求書に記載します。"})}
    jp = Citation("m", "p1", "外国企業は日本で消費税の登録が必要です。登録番号")
    assert not check([Sentence("A foreign company does not need to wait.", [jp])], src, date(2026, 1, 1)).accepted
    src["e"] = Source("e", {"p1": "Registration is required before the first sale to a consumer."})
    mixed = [Sentence("Registration is not required.", [jp, Citation("e", "p1", "Registration is required before")])]
    assert not check(mixed, src, date(2026, 1, 1)).accepted  # an unreadable quote cannot mask the readable one
