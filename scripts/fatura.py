#!/usr/bin/env python3
"""Decode and validate a Portuguese invoice QR code. Offline, stdlib only.

Reads the payload mandated by Portaria n.o 195/2020 against the field spec in
assets/qr-spec.json, reconciles the arithmetic, classifies the buyer, and
refuses anything outside its competence.

THREE RULES, each written because breaking it cost something.

1. A CHECK THAT CANNOT RUN MUST FLAG, NEVER SKIP.
   An earlier version computed the reconciliation only when every amount
   parsed. One unparseable field therefore disabled the whole arithmetic check
   silently, and a payload declaring 9 999 999.99 came back with zero flags.
   Every "cannot evaluate" branch below raises a flag instead.

2. A VALIDATOR MAY REJECT. IT MAY NEVER CONFIRM.
   The NIF check digit passes 1.53% of single-digit corruptions, because
   residues 0 and 1 both map to check digit 0 (100000010 and 600000010 differ
   by one digit and are both valid). A clean result means "no error detected",
   which is not the same as "correct", and the record says so.

3. NEVER GUESS WHAT THE PAYLOAD DOES NOT CONTAIN.
   The QR carries who, when, how much and the tax split. It does NOT say what
   was bought. Goods vs services, new vs used - none of it is in there, so
   this module never infers it. See garantia.py.

Usage:
    python fatura.py --selftest
    python fatura.py --payload "A:...*B:...*..." --year 2026
"""

import argparse
import json
import os
import sys
from datetime import date
from decimal import Decimal, InvalidOperation

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(os.path.dirname(HERE), "assets")

with open(os.path.join(ASSETS, "qr-spec.json"), encoding="utf-8") as fh:
    SPEC = json.load(fh)

FIELDS = SPEC["fields"]
CONSUMIDOR_FINAL = SPEC["consumidor_final"]
BASE_KEYS = [k for k, v in FIELDS.items() if v.get("role") == "base"]
IVA_KEYS = [k for k, v in FIELDS.items() if v.get("role") == "iva"]
TAX_KEYS = IVA_KEYS + [k for k, v in FIELDS.items() if v.get("role") == "tax"]
REQUIRED = [k for k, v in FIELDS.items() if v.get("required")]
DOC = SPEC["tipo_documento"]
ESTADO = SPEC["estado_documento"]

# First digit of a Portuguese NIF. Deliberately conservative: this establishes
# the REGISTRATION class, not the purpose of the purchase. A sole trader buying
# a toaster uses a personal NIF; prefix 8 was phased out around 2001 and is not
# dispositive of business use. So prefix drives a FLAG, and only an unambiguous
# collective prefix drives a refusal.
NIF_PREFIX = {
    "1": ("singular", "pessoa singular"),
    "2": ("singular", "pessoa singular"),
    "3": ("singular", "pessoa singular"),
    "45": ("singular", "pessoa singular nao residente"),
    "5": ("coletiva", "pessoa coletiva"),
    "6": ("coletiva", "organismo da Administracao Publica"),
    "70": ("coletiva", "heranca indivisa / entidade equiparada"),
    "71": ("coletiva", "pessoa coletiva nao residente"),
    "72": ("coletiva", "fundo de investimento"),
    "74": ("coletiva", "entidade equiparada"),
    "75": ("coletiva", "entidade equiparada"),
    "77": ("coletiva", "atribuicao oficiosa"),
    "78": ("coletiva", "nao residente"),
    "79": ("coletiva", "regime excecional"),
    "8": ("ambiguo", "prefixo 8 (empresario em nome individual, descontinuado)"),
    "90": ("coletiva", "condominio / sociedade irregular"),
    "91": ("coletiva", "condominio / sociedade irregular"),
    "98": ("coletiva", "nao residente sem estabelecimento estavel"),
    "99": ("coletiva", "sociedade civil sem personalidade juridica"),
}
INVALID_LEAD = ("0", "4")   # 4 only valid as part of "45"

# Statutory IVA rates, continente and regions. Used only for a PLAUSIBILITY
# ratio check: the QR does not say which rate applies to what, so a
# wrong-but-consistent rate cannot be caught here (declared in qr-spec.json).
IVA_RATES = {
    "PT":    {"reduzida": "0.06", "intermedia": "0.13", "normal": "0.23"},
    "PT-AC": {"reduzida": "0.04", "intermedia": "0.09", "normal": "0.16"},
    "PT-MA": {"reduzida": "0.05", "intermedia": "0.12", "normal": "0.22"},
}


class F:
    """Flag vocabulary. A flagged row goes to a human; a clean one does not."""
    NO_NIF = "SEM_NIF_DEDUCAO_PERDIDA"
    NIF_INVALID = "NIF_FALHA_CHECKSUM"
    NIF_LEAD_INVALID = "NIF_PRIMEIRO_DIGITO_IMPOSSIVEL"
    NIF_NOT_PT = "NIF_NAO_PORTUGUES"
    NIF_AMBIGUOUS = "NIF_CLASSE_AMBIGUA_CONFIRMAR"
    BUSINESS = "FATURA_EMPRESARIAL_FORA_DE_AMBITO"
    LOW_CONF_NIF = "NIF_LIDO_POR_OCR_CONFIRMAR"
    MISSING = "CAMPO_OBRIGATORIO_EM_FALTA"
    EMPTY = "CAMPO_OBRIGATORIO_VAZIO"
    TOO_LONG = "CAMPO_EXCEDE_TAMANHO_MAXIMO"
    DUPLICATE = "CAMPO_DUPLICADO_NO_QR"
    UNKNOWN_FIELD = "CAMPO_DESCONHECIDO_NO_QR"
    AMOUNT_BAD = "VALOR_ILEGIVEL_VERIFICACAO_IMPOSSIVEL"
    AMOUNT_NONFINITE = "VALOR_NAO_FINITO"
    AMOUNT_NEGATIVE = "VALOR_NEGATIVO_EM_DOCUMENTO_NAO_NC"
    TOTAL_MISMATCH = "TOTAL_NAO_RECONCILIA"
    TAX_MISMATCH = "IMPOSTOS_NAO_RECONCILIAM"
    NO_BREAKDOWN = "SEM_DECOMPOSICAO_VALOR_NAO_VERIFICAVEL"
    IVA_RATE_ODD = "TAXA_IVA_IMPLAUSIVEL"
    BAD_DATE = "DATA_INVALIDA"
    DATE_LENGTH = "DATA_COMPRIMENTO_INVALIDO"
    FUTURE = "DATA_NO_FUTURO"
    OUTSIDE_YEAR = "FORA_DO_ANO_FISCAL"
    BAD_ATCUD = "ATCUD_FORMATO_INVALIDO"
    CREDIT_NOTE = "NOTA_DE_CREDITO"
    NOT_A_PURCHASE = "TIPO_NAO_E_COMPRA"
    UNKNOWN_TYPE = "TIPO_DOCUMENTO_DESCONHECIDO"
    VOID = "DOCUMENTO_ANULADO"
    STATE_UNKNOWN = "ESTADO_DOCUMENTO_SEM_CONSEQUENCIA_ESTABELECIDA"
    NON_ASCII = "CARACTERES_NAO_ASCII"


class BusinessInvoiceRefused(Exception):
    """A bill issued to a company. Out of scope, by design.

    Business invoices engage IVA dedutivel and the commercial guarantee regime
    rather than the consumer one. Handling them here would put confidently
    wrong numbers into somebody's accounts.
    """


def _ascii_digits(s):
    """True only for ASCII 0-9. str.isdigit() accepts Arabic-Indic and
    fullwidth digits, which int() then happily parses - a silent mismatch
    between validation and the ASCII lookup tables below."""
    return bool(s) and all("0" <= c <= "9" for c in s)


def nif_checksum_ok(nif):
    """Portuguese NIF check digit, mod 11. Rejects; never confirms."""
    if not isinstance(nif, str) or len(nif) != 9 or not _ascii_digits(nif):
        return False
    r = sum(int(d) * (9 - i) for i, d in enumerate(nif[:8])) % 11
    return (0 if r in (0, 1) else 11 - r) == int(nif[8])


def nif_class(nif):
    """(class, label) from the leading digits. Longest prefix wins."""
    if not nif or not _ascii_digits(nif):
        return ("desconhecido", "nao numerico")
    for n in (2, 1):
        if nif[:n] in NIF_PREFIX:
            return NIF_PREFIX[nif[:n]]
    if nif[0] in INVALID_LEAD:
        return ("impossivel", "primeiro digito %s nunca inicia um NIF valido" % nif[0])
    return ("desconhecido", "prefixo %s nao reconhecido" % nif[:2])


def parse_qr(payload):
    """payload -> (fields, duplicates, unknown_keys).

    Duplicates are reported, not resolved: a repeated field means the string
    was concatenated or repaired somewhere, and whichever value you would
    otherwise keep is arbitrary.
    """
    fields, dupes, unknown = {}, [], []
    for chunk in (payload or "").split("*"):
        if ":" not in chunk:
            continue
        k, v = chunk.split(":", 1)
        k, v = k.strip(), v.strip()
        if k in fields:
            dupes.append(k)
        if k not in FIELDS:
            unknown.append(k)
        fields[k] = v
    return fields, dupes, unknown


def _money(raw, key, flags):
    """Parse a monetary field.

    Returns Decimal, None (absent), or the sentinel "BAD" (present but not
    usable). "BAD" is never treated as zero - that is the whole point.
    """
    if key not in raw:
        return None
    v = raw[key]
    if not v:
        flags.append("%s:%s" % (F.EMPTY, key))
        return "BAD"
    if not all(c in "0123456789.-" for c in v):
        flags.append("%s:%s=%r" % (F.AMOUNT_BAD, key, v[:16]))
        return "BAD"
    try:
        d = Decimal(v)
    except InvalidOperation:
        flags.append("%s:%s=%r" % (F.AMOUNT_BAD, key, v[:16]))
        return "BAD"
    if not d.is_finite():
        flags.append("%s:%s" % (F.AMOUNT_NONFINITE, key))
        return "BAD"
    if d != d.quantize(Decimal("0.01")):
        flags.append("%s:%s tem mais de 2 casas decimais" % (F.AMOUNT_BAD, key))
        return "BAD"
    return d


def validate(raw, dupes, unknown, tax_year, source="qr", today=None,
             refuse_business=True):
    """Validate a parsed payload. `tax_year` is required, not defaulted."""
    flags, rec = [], {"source": source, "tax_year": tax_year}
    today = today or date.today()

    for d in sorted(set(dupes)):
        flags.append("%s:%s" % (F.DUPLICATE, d))
    for u in sorted(set(unknown)):
        flags.append("%s:%s" % (F.UNKNOWN_FIELD, u))

    for k, v in raw.items():
        if k in FIELDS:
            rec[FIELDS[k]["name"]] = v
            if len(v) > FIELDS[k]["max"]:
                flags.append("%s:%s" % (F.TOO_LONG, k))
        if any(ord(c) > 127 for c in v):
            flags.append("%s:%s" % (F.NON_ASCII, k))

    for k in REQUIRED:
        if k not in raw:
            flags.append("%s:%s" % (F.MISSING, FIELDS[k]["name"]))
        elif not raw[k].strip():
            flags.append("%s:%s" % (F.EMPTY, FIELDS[k]["name"]))

    # ---- document type decides whether anything else even matters
    d_type = raw.get("D", "").strip().upper()
    rec["e_compra"] = False
    if d_type in DOC["credit_note"]:
        flags.append(F.CREDIT_NOTE)
        rec["sinal"] = -1
        rec["e_compra"] = True
    elif d_type in DOC["deductible_candidates"]:
        rec["sinal"] = 1
        rec["e_compra"] = True
    elif d_type in DOC["not_a_purchase"]:
        flags.append("%s:%s" % (F.NOT_A_PURCHASE, d_type))
        rec["sinal"] = 0
    elif d_type:
        flags.append("%s:%s" % (F.UNKNOWN_TYPE, d_type))
        rec["sinal"] = 0

    # ---- buyer
    b = raw.get("B", "").strip()
    cls, label = ("", "")
    if b and b != CONSUMIDOR_FINAL:
        cls, label = nif_class(b)
        rec["classe_adquirente"], rec["classe_label"] = cls, label
        if cls == "coletiva":
            flags.append("%s:%s" % (F.BUSINESS, label))
            if refuse_business:
                raise BusinessInvoiceRefused(
                    "NIF %s -> %s. Faturas empresariais estao fora de ambito: "
                    "envolvem IVA dedutivel e o regime de garantia comercial, "
                    "nao o do consumidor." % (b, label))
        elif cls == "impossivel":
            flags.append("%s:%s" % (F.NIF_LEAD_INVALID, label))
        elif cls in ("desconhecido", "ambiguo"):
            flags.append("%s:%s" % (F.NIF_AMBIGUOUS, label))

    pais = raw.get("C", "").strip().upper()
    if b == CONSUMIDOR_FINAL:
        flags.append(F.NO_NIF)
        rec["nif_adquirente"] = None
        rec["deducao_possivel"] = False
    elif b:
        if pais and pais != "PT":
            flags.append("%s:%s" % (F.NIF_NOT_PT, pais))
            rec["deducao_possivel"] = False
        elif not nif_checksum_ok(b):
            flags.append(F.NIF_INVALID)
            rec["deducao_possivel"] = False
        else:
            rec["deducao_possivel"] = rec["e_compra"] and rec["sinal"] > 0
            if source != "qr":
                flags.append(F.LOW_CONF_NIF)
    else:
        rec["deducao_possivel"] = False

    if raw.get("A") and not nif_checksum_ok(raw["A"]):
        flags.append("%s:emitente" % F.NIF_INVALID)

    # ---- estado
    e = raw.get("E", "").strip().upper()
    if e:
        meta = ESTADO.get(e)
        if meta is None:
            flags.append("%s:%s" % (F.STATE_UNKNOWN, e))
            rec["deducao_possivel"] = False
        elif meta["deductible"] is False:
            flags.append(F.VOID)
            rec["deducao_possivel"] = False
        elif meta["deductible"] == "UNKNOWN":
            flags.append("%s:%s" % (F.STATE_UNKNOWN, e))
            rec["deducao_possivel"] = False

    # ---- arithmetic, against the spec's own formula
    bases = {k: _money(raw, k, flags) for k in BASE_KEYS if k in raw}
    taxes = {k: _money(raw, k, flags) for k in TAX_KEYS if k in raw}
    n_decl = _money(raw, "N", flags)
    o_decl = _money(raw, "O", flags)
    vals = list(bases.values()) + list(taxes.values()) + [n_decl, o_decl]
    unreadable = any(v == "BAD" for v in vals)
    nums = lambda d: [v for v in d.values() if isinstance(v, Decimal)]

    if unreadable:
        rec["reconcilia"] = None            # already flagged; no conclusion
    elif not bases and not taxes:
        # No breakdown. Legitimate for a non-valued document (AT example 4),
        # unverifiable for anything claiming a total. The zero case is stated
        # by the document itself (N:0.00 O:0.00) rather than assumed.
        if isinstance(o_decl, Decimal) and o_decl == 0 and \
                isinstance(n_decl, Decimal) and n_decl == 0:
            rec["base_total"], rec["imposto_total"] = "0.00", "0.00"
            rec["reconcilia"] = True
        else:
            if isinstance(o_decl, Decimal) and o_decl != 0:
                flags.append(F.NO_BREAKDOWN)
            rec["reconcilia"] = None
    else:
        sb = sum(nums(bases), Decimal("0"))
        st = sum(nums(taxes), Decimal("0"))
        rec["base_total"], rec["imposto_total"] = str(sb), str(st)
        ok = True
        if isinstance(n_decl, Decimal) and st != n_decl:
            flags.append("%s:%s!=%s" % (F.TAX_MISMATCH, st, n_decl))
            ok = False
        if isinstance(o_decl, Decimal):
            expect = sb + (n_decl if isinstance(n_decl, Decimal) else st)
            if expect != o_decl:
                flags.append("%s:%s!=%s" % (F.TOTAL_MISMATCH, expect, o_decl))
                ok = False
        rec["reconcilia"] = ok
        if [v for v in nums(bases) + nums(taxes) + [o_decl]
                if isinstance(v, Decimal) and v < 0] and d_type not in DOC["credit_note"]:
            flags.append("%s:%s" % (F.AMOUNT_NEGATIVE, d_type or "?"))
        _check_rates(raw, bases, taxes, flags)

    # ---- date
    f = raw.get("F", "").strip()
    if f:
        if len(f) != 8 or not _ascii_digits(f):
            flags.append("%s:%r" % (F.DATE_LENGTH, f[:12]))
        else:
            try:
                d = date(int(f[0:4]), int(f[4:6]), int(f[6:8]))
                rec["data"] = d.isoformat()
                if d > today:
                    flags.append("%s:%s" % (F.FUTURE, d.isoformat()))
                if d.year != tax_year:
                    flags.append("%s:%d" % (F.OUTSIDE_YEAR, d.year))
            except ValueError:
                flags.append(F.BAD_DATE)

    # ---- ATCUD
    h = raw.get("H", "").strip()
    if h and h != "0":
        code, sep, seq = h.partition("-")
        if not sep or len(code) < 8 or not code.isalnum() or not _ascii_digits(seq):
            flags.append(F.BAD_ATCUD)

    rec["flags"] = flags
    rec["sem_erros_detetados"] = not flags and source == "qr"
    return rec


def _check_rates(raw, bases, taxes, flags):
    """Plausibility only. The QR never says which rate applies to what."""
    pairs = [("PT", "I3", "I4", "reduzida"), ("PT", "I5", "I6", "intermedia"),
             ("PT", "I7", "I8", "normal"),
             ("PT-AC", "J3", "J4", "reduzida"), ("PT-AC", "J5", "J6", "intermedia"),
             ("PT-AC", "J7", "J8", "normal"),
             ("PT-MA", "K3", "K4", "reduzida"), ("PT-MA", "K5", "K6", "intermedia"),
             ("PT-MA", "K7", "K8", "normal")]
    for region, bk, tk, name in pairs:
        b, t = bases.get(bk), taxes.get(tk)
        if not isinstance(b, Decimal) or not isinstance(t, Decimal) or b <= 0:
            continue
        expect = (b * Decimal(IVA_RATES[region][name])).quantize(Decimal("0.01"))
        if abs(t - expect) > max(Decimal("0.02"), expect * Decimal("0.01")):
            flags.append("%s:%s %s esperado~%s obtido %s"
                         % (F.IVA_RATE_ODD, region, name, expect, t))


def process(payload, tax_year, source="qr", today=None, refuse_business=True):
    """(record, None) on success, (None, reason) when refused."""
    raw, dupes, unknown = parse_qr(payload)
    try:
        return validate(raw, dupes, unknown, tax_year, source, today,
                        refuse_business), None
    except BusinessInvoiceRefused as exc:
        return None, str(exc)


def _selftest():
    from datetime import date as _d
    today = _d(2026, 7, 24)
    with open(os.path.join(ASSETS, "at-examples.json"), encoding="utf-8") as fh:
        corpus = json.load(fh)

    print("A. AT official worked examples (independent oracle)")
    print("-" * 70)
    failed = 0
    for c in corpus["cases"]:
        year = int(c["payload"].split("F:")[1][:4])
        rec, refused = process(c["payload"], year, today=today)
        exp = c["expected"]
        if rec is None:
            print("FAIL %-38s REFUSED: %s" % (c["id"], refused[:30])); failed += 1; continue
        checks = []
        if "base_total" in exp:
            checks.append(("base", rec.get("base_total") == exp["base_total"]))
        if "tax_total" in exp:
            checks.append(("imposto", rec.get("imposto_total") == exp["tax_total"]))
        if exp.get("reconciles"):
            checks.append(("reconcilia", rec.get("reconcilia") is not False))
        for m in exp.get("must_flag", []):
            checks.append((m[:14], any(g.startswith(m) for g in rec["flags"])))
        if "deducao_possivel" in exp:
            checks.append(("ded", rec["deducao_possivel"] == exp["deducao_possivel"]))
        bad = [n for n, o in checks if not o]
        failed += 1 if bad else 0
        print("%-4s %-38s %s" % ("PASS" if not bad else "FAIL", c["id"],
                                 "ok" if not bad else "MISSED " + ",".join(bad)))

    print("\nB. Adversarial cases (each previously returned flags=[] trusted)")
    print("-" * 70)
    G = corpus["cases"][1]["payload"]        # the simple coffee receipt
    def sub(a, b): return G.replace(a, b)
    adv = [
        ("Infinity amount", sub("I7:0.65", "I7:Infinity"), F.AMOUNT_BAD),
        ("NaN amount", sub("I7:0.65", "I7:NaN"), F.AMOUNT_BAD),
        ("comma decimal", sub("I7:0.65", "I7:0,65"), F.AMOUNT_BAD),
        ("exponent notation", sub("I7:0.65", "I7:1e5"), F.AMOUNT_BAD),
        ("3 decimal places", sub("I7:0.65", "I7:0.655"), F.AMOUNT_BAD),
        ("hidden L field", G + "*L:999999.99", F.TOTAL_MISMATCH),
        ("stamp duty ignored", G + "*M:25.00", F.TAX_MISMATCH),
        ("E:A anulado", sub("E:N", "E:A"), F.VOID),
        ("E:F unestablished", sub("E:N", "E:F"), F.STATE_UNKNOWN),
        ("date 7 chars", sub("F:20190812", "F:2019081"), F.DATE_LENGTH),
        ("date trailing junk", sub("F:20190812", "F:20190812XYZ"), F.DATE_LENGTH),
        ("empty date", sub("F:20190812", "F:"), F.EMPTY),
        ("duplicate field", G + "*O:1.00", F.DUPLICATE),
        ("unknown field", G + "*Z:1.00", F.UNKNOWN_FIELD),
        ("negative on FS", sub("I7:0.65", "I7:-0.65"), F.AMOUNT_NEGATIVE),
        ("ATCUD garbage", sub("H:CDF7T5HD-12345", "H:!!!!!!!!-1"), F.BAD_ATCUD),
        ("future date", sub("F:20190812", "F:20301231"), F.FUTURE),
        ("IVA rate 1%", sub("I8:0.15", "I8:0.01").replace("N:0.15", "N:0.01")
                          .replace("O:0.80", "O:0.66"), F.IVA_RATE_ODD),
        ("NIF lead 0", sub("B:999999990", "B:000000000"), F.NIF_LEAD_INVALID),
        ("NIF lead 4", sub("B:999999990", "B:400000008"), F.NIF_LEAD_INVALID),
        ("arabic-indic digits", sub("B:999999990", "B:\u0662\u0663\u0664\u0665\u0666\u0667\u0668\u0669\u0669"), F.NON_ASCII),
        ("field over max length", sub("Q:YhGV", "Q:YhGVTOOLONG"), F.TOO_LONG),
    ]
    for name, payload, want in adv:
        rec, refused = process(payload, 2019, today=today)
        got = rec["flags"] if rec else ["REFUSED"]
        ok = any(g.startswith(want) for g in got)
        failed += 0 if ok else 1
        print("%-4s %-26s %s" % ("PASS" if ok else "FAIL", name,
                                 (",".join(got)[:44] or "(clean)")))

    print("\nC. Scope, provenance and known limits")
    print("-" * 70)
    checks = []
    rec, refused = process(sub("B:999999990", "B:501442600"), 2019, today=today)
    checks.append(("business bill refused", rec is None and "coletiva" in (refused or "")))
    rec, _ = process(sub("B:999999990", "B:800000005"), 2019, today=today)
    checks.append(("prefix 8 flagged, not refused",
                   rec is not None and any(g.startswith(F.NIF_AMBIGUOUS) for g in rec["flags"])))
    # A payload with a real personal NIF, so no flag fires and the only
    # difference between the two runs is where the data came from.
    CLEAN = sub("B:999999990", "B:234567899")
    a = process(CLEAN, 2019, "qr", today)[0]
    b = process(CLEAN, 2019, "ocr_local", today)[0]
    checks.append(("clean payload really is clean", not a["flags"]))
    checks.append(("provenance changes trust",
                   a["sem_erros_detetados"] and not b["sem_erros_detetados"]))
    checks.append(("NIF checksum incomplete",
                   nif_checksum_ok("100000010") and nif_checksum_ok("600000010")))
    try:
        validate({}, [], [])          # tax_year genuinely absent
        checks.append(("tax_year cannot be omitted", False))
    except TypeError:
        checks.append(("tax_year cannot be omitted", True))
    for name, ok in checks:
        failed += 0 if ok else 1
        print("%-4s %s" % ("PASS" if ok else "FAIL", name))

    print("-" * 70)
    print("SELFTEST: %s" % ("PASS" if not failed else "FAIL (%d)" % failed))
    return 1 if failed else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Decode + validate a fatura QR code.")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--payload")
    ap.add_argument("--year", type=int)
    a = ap.parse_args()
    if a.selftest:
        sys.exit(_selftest())
    if a.payload and a.year:
        r, refused = process(a.payload, a.year)
        print(refused if refused else json.dumps(r, indent=2, ensure_ascii=False))
        sys.exit(1 if refused else 0)
    ap.print_help()
    sys.exit(2)
