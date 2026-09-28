#!/usr/bin/env python3
"""Unified correctness gate. Offline, stdlib only.

Most of these checks can go red because a NUMBER or a CITATION is wrong, not
merely because a file is missing. That distinction is the whole reason this
file exists: a sibling project shipped a 29-check sweep that stayed green for
a year while a statutory tax rate underneath it was superseded, because every
check was structural.

    python sweep.py
"""

import argparse
import contextlib
import io
import json
import os
import re
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ASSETS = os.path.join(ROOT, "assets")
results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("PASS  " if ok else "FAIL  ") + name + ("  - " + detail if detail else ""))


def _load(n):
    with open(os.path.join(ASSETS, n), encoding="utf-8") as fh:
        return json.load(fh)


def spec_checks():
    s = _load("qr-spec.json")
    f = s["fields"]
    check("spec-field-count", len(f) == 40, "%d QR fields defined (A-S incl. I/J/K sets)" % len(f))
    for group, region in (("I", "continente"), ("J", "Acores"), ("K", "Madeira")):
        present = [k for k in f if k.startswith(group) and len(k) == 2]
        check("spec-fiscal-space:" + group, len(present) == 8,
              "%s %s fields" % (len(present), region))
    for k in ("L", "M", "P"):
        check("spec-field:" + k, k in f, f.get(k, {}).get("desc", "")[:52])
    check("spec-N-includes-selo", "Imposto do Selo" in f["N"]["desc"],
          "N is IVA + stamp duty, not IVA alone")
    check("spec-P-excluded-from-total", "NOT part of O" in f["P"]["desc"],
          "retencoes are withheld, not added")
    check("spec-B-allows-foreign-id", f["B"]["max"] == 30,
          "buyer id is up to 30 chars, not always a 9-digit NIF")
    gaps = s["documented_gaps"]
    check("spec-gaps-have-direction", all(g.get("direction") for g in gaps),
          "%d declared gaps, each with a direction of error" % len(gaps))


def corpus_checks():
    c = _load("at-examples.json")
    check("corpus-is-official", "AT" in c["_meta"]["source"],
          "fixtures are the tax authority's own worked examples")
    check("corpus-count", len(c["cases"]) == 4, "%d cases" % len(c["cases"]))
    joined = " ".join(x["payload"] for x in c["cases"])
    for token, why in (("J1:PT-AC", "Acores"), ("K1:PT-MA", "Madeira"),
                       ("L:", "nao sujeito"), ("M:", "imposto do selo"),
                       ("P:", "retencoes"), ("D:PF", "pro-forma"), ("D:GT", "transporte")):
        check("corpus-exercises:" + why, token in joined, token)
    check("corpus-every-case-explained",
          all(x.get("why_included") for x in c["cases"]),
          "each fixture states what it is there to catch")


def engine_checks():
    sys.path.insert(0, HERE)
    buf = io.StringIO()
    import fatura, garantia, planilha, offline_audit
    with contextlib.redirect_stdout(buf):
        rc_f = fatura._selftest()
        rc_g = garantia._selftest()
        rc_p = planilha._selftest()
        rc_a = offline_audit.selftest()
        clean_audit = not offline_audit.audit(HERE)
    check("engine-fatura-selftest", rc_f == 0,
          "AT examples + adversarial corpus + scope checks")
    check("engine-garantia-selftest", rc_g == 0, "DL 84/2021 periods + iCal")
    check("engine-planilha-selftest", rc_p == 0, "three sheets, flags visible")
    check("offline-audit", clean_audit, "no network/subprocess/eval surface")
    check("offline-audit-selftest", rc_a == 0, "the audit was proven able to fail")

    # The two invariants that matter most, asserted here as well as in-module,
    # so removing them from one place still fails the gate.
    check("invariant-checksum-rejects-never-confirms",
          fatura.nif_checksum_ok("100000010") and fatura.nif_checksum_ok("600000010"),
          "two NIFs one digit apart both pass - a clean checksum is not proof")
    check("invariant-service-gets-no-dates",
          garantia.compute(date(2026, 2, 14), "servico")["garantia_termina"] is None,
          "ordinary services are outside DL 84/2021 and get no guarantee date")
    check("invariant-unclassified-gets-no-dates",
          garantia.compute(date(2026, 2, 14))["garantia_termina"] is None,
          "nothing is inferred about what was bought")
    check("invariant-business-refused",
          fatura.process("A:501442600*B:501442600*C:PT*D:FT*E:N*F:20260101*"
                         "G:X*H:AAAAAAAA-1*I1:PT*N:0.00*O:0.00*Q:aaaa*R:9999",
                         2026)[0] is None,
          "a bill issued to a company is refused, not mis-handled")


def law_checks():
    """Statutory constants live in exactly one place and say where they came from."""
    sys.path.insert(0, HERE)
    import garantia
    k = garantia.KINDS
    check("law-movel-3-anos", k["bem_movel_novo"]["liability_months"] == 36,
          "art. 12.o n.o 1")
    check("law-presuncao-2-anos", k["bem_movel_novo"]["presumption_months"] == 24,
          "art. 13.o n.o 1 - the date most people do not know about")
    check("law-usado-18-meses", k["bem_movel_usado"]["liability_months_if_agreed"] == 18,
          "art. 12.o n.o 3, only by express agreement")
    check("law-imovel-10-e-5", k["bem_imovel"]["liability_months"] == 120 and
          k["bem_imovel"]["liability_months_non_structural"] == 60, "art. 23.o n.o 1")
    check("law-servico-out-of-scope", k["servico"]["liability_months"] is None and
          "FORA do ambito" in k["servico"]["basis"], "art. 1.o")
    check("law-every-kind-cites-basis", all(v.get("basis") for v in k.values()),
          "%d kinds, each with a legal basis" % len(k))
    check("law-prerequisites-listed", len(garantia.PREREQUISITOS) >= 6,
          "%d conditions the user must acknowledge" % len(garantia.PREREQUISITOS))


def doc_checks():
    for f in ("README.md", "README.pt.md", "SKILL.md", "LICENSE",
              "DISCLAIMER.md", "SECURITY.md", "CONTRIBUTING.md"):
        check("doc-present:" + f, os.path.exists(os.path.join(ROOT, f)))
    lic = os.path.join(ROOT, "LICENSE")
    if os.path.exists(lic):
        t = open(lic, encoding="utf-8").read()
        check("license-is-mit", "MIT License" in t and "WITHOUT WARRANTY" in t)
        # Appending to LICENSE makes GitHub report NOASSERTION and the repo
        # loses its MIT badge, so the notice lives in DISCLAIMER.md instead.
        check("license-unmodified", "ADDITIONAL NOTICE" not in t,
              "no appendix that would defeat licence detection")
    for f in ("README.md", "README.pt.md", "SKILL.md"):
        p = os.path.join(ROOT, f)
        if not os.path.exists(p):
            continue
        t = open(p, encoding="utf-8").read()
        low = t.lower()
        check("doc-disclaimer:" + f,
              "occ" in low and any(p in low for p in (
                  "não é aconselhamento", "nao e aconselhamento",
                  "not tax or legal advice", "not financial")),
              "carries the not-advice notice and routes to an OCC")
        check("doc-mowei:" + f, "mowei.pt" in t)

    # The documented check count must match this run, or the README's own
    # "verify it yourself" instruction produces a number that disagrees.
    total = len(results) + len([f for f in ("README.md", "README.pt.md", "SKILL.md")
                                if os.path.exists(os.path.join(ROOT, f))]) + 1
    for f in ("README.md", "README.pt.md", "SKILL.md"):
        p = os.path.join(ROOT, f)
        if not os.path.exists(p):
            continue
        t = open(p, encoding="utf-8").read()
        claimed = set(re.findall(r"(\d+)\s+(?:checks|verifica)", t))
        check("doc-check-count:" + f, all(int(c) == total for c in claimed),
              "documents %d checks" % total if all(int(c) == total for c in claimed)
              else "claims %s, this run has %d" % (sorted(claimed), total))


def pii_check():
    needles = ("@gmail.", "@hotmail.", "@outlook.", "@sapo.pt", "IBAN PT50", "+351 9")
    bad = []
    for root, _d, files in os.walk(ROOT):
        if ".git" in root or "__pycache__" in root:
            continue
        for f in files:
            if not f.endswith((".py", ".md", ".json", ".yml")):
                continue
            p = os.path.join(root, f)
            if os.path.abspath(p) == os.path.abspath(__file__):
                continue
            t = open(p, encoding="utf-8", errors="ignore").read()
            bad += [(f, n) for n in needles if n in t]
    check("pii-hygiene", not bad, "no personal identifiers in shipped files"
          if not bad else "FOUND %s" % bad)


def run(quiet=False):
    """One full pass over every check group. Returns the results list.

    Was module-level straight-line code. It is a function now so that
    ``--self-test`` can run the gate a second time against a deliberately
    corrupted condition and demand that it goes red - a check nobody has
    ever seen fail is indistinguishable from one that cannot.
    """
    del results[:]
    with contextlib.redirect_stdout(io.StringIO() if quiet else sys.stdout):
        print("=" * 70)
        print("RECIBOS E GARANTIA - correctness gate")
        print("=" * 70)
        spec_checks()
        corpus_checks()
        engine_checks()
        law_checks()
        doc_checks()
        pii_check()
    return list(results)


def self_test():
    """Prove the gate can go red, and can come back green.

    Corrupts, in memory only, the DL 84/2021 constant this gate cites for
    new movable goods (36 months, art. 12.o n.o 1) - garantia.py on disk is
    never touched - runs a second full pass, and requires the named law
    check to be among the failures. Then restores and requires green again.
    """
    sys.path.insert(0, HERE)
    import garantia

    print("--- normal state ---")
    base = run(quiet=True)
    if any(not ok for _, ok, _ in base):
        print("SELF-TEST ABORTED: the gate is already red")
        return 1
    print("%d/%d green" % (len(base), len(base)))

    print("--- bem_movel_novo liability corrupted from 36 to 24 months ---")
    orig = garantia.KINDS["bem_movel_novo"]["liability_months"]
    garantia.KINDS["bem_movel_novo"]["liability_months"] = 24
    try:
        failed = [n for n, ok, _ in run(quiet=True) if not ok]
    finally:
        garantia.KINDS["bem_movel_novo"]["liability_months"] = orig
    if "law-movel-3-anos" not in failed:
        print("SELF-TEST FAILED: a stale liability period did not raise the alarm - "
              "the 3-year guarantee on new movable goods could silently shrink to 2")
        return 1
    print("the gate caught the corrupted constant: %s" % ", ".join(failed))

    print("--- restored ---")
    if any(not ok for _, ok, _ in run(quiet=True)):
        print("SELF-TEST FAILED: did not return to green")
        return 1
    print("green again")
    print()
    print("SELF-TEST OK - the gate knows how to fail and how to pass again")
    return 0


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="accepted for compatibility; every check already prints")
    ap.add_argument("--self-test", action="store_true",
                    help="prove the gate can go red, then come back green")
    # argparse exits 2 on an unknown flag. That matters: this file used to ignore
    # argv entirely, so `sweep.py --self-test` ran an ordinary sweep and exited 0
    # - a self-test that never ran, reported as a pass. Found by the weekly
    # repo-refresh staleness sweep (2026-09-28), which had already caught the
    # identical bug in the sibling repos.
    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()
    res = run()
    fails = [r for r in res if not r[1]]
    print("-" * 70)
    print("SWEEP %s: %d/%d checks green%s"
          % ("PASS" if not fails else "FAIL", len(res) - len(fails), len(res),
             "" if not fails else " - DO NOT DELIVER until resolved"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
