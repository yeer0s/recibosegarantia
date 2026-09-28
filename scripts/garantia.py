#!/usr/bin/env python3
"""Consumer-guarantee periods under DL 84/2021, and calendar export.

WHY THIS MODULE ASKS INSTEAD OF GUESSING

The invoice QR code carries who, when, how much, and the tax split. It does
NOT carry what was bought. There is no field for it - not in Portaria
195/2020, not anywhere. So nothing here can tell a laptop from a haircut, and
every available proxy fails:

  * IVA rate      - 23% covers most goods AND most services; a book is 6%,
                    a restaurant meal 13%. Not decisive in either direction.
  * Document type - FT/FS/FR are billing formats, not content.
  * Merchant NIF  - a garage sells parts and labour on the same invoice.
  * Line items    - only on the printed face; needs OCR, and "reparacao de
                    maquina" versus "maquina" is still ambiguous after it.

That matters because the periods differ by kind, and inventing one is worse
than offering none. An unconditional three years would tell somebody their
haircut is guaranteed until 2029 - a legal deadline that does not exist.

So `kind` defaults to POR_CLASSIFICAR and NO dates are produced until a human
says what was bought. That is the whole design.

Legal basis, read from the consolidated text of DL 84/2021:
  art. 12.o n.o 1  - bens moveis: 3 years from DELIVERY
  art. 12.o n.o 3  - bens moveis USADOS: reducible to 18 months by agreement
  art. 13.o n.o 1  - defect presumed pre-existing for 2 years (burden on seller)
  art. 13.o n.o 3  - ONE year when a used good's period was cut to 18 months
  art. 23.o n.o 4  - immovables: the presumption covers the WHOLE 10/5-year period
  art. 17.o n.o 1  - rights lapse 2 years after the defect is communicated
  art. 12.o n.o 5  - the defect must be reported by a provable means
  preambulo        - NO deadline to report a defect; the DL removed it
Verbatim text: assets/law/dl-84-2021.md.
  art. 1.o         - scope is goods, immovables, and digital content/services.
                     Ordinary services (repairs, haircuts, consultancy) are OUTSIDE.

Usage:
    python garantia.py --selftest
"""

import argparse
import sys
from datetime import date, timedelta

# Every entry states its own legal basis, and NONE is inferred from the QR.
KINDS = {
    "bem_movel_novo": {
        "label": "Bem movel novo",
        "liability_months": 36,
        "presumption_months": 24,
        "basis": "DL 84/2021 art. 12.o n.o 1 e art. 13.o n.o 1",
    },
    "bem_movel_usado": {
        "label": "Bem movel usado",
        "liability_months": 36,
        "liability_months_if_agreed": 18,
        "presumption_months": 24,
        "presumption_months_if_agreed": 12,
        "basis": "DL 84/2021 art. 12.o n.o 3 - 3 anos, reduzivel a 18 meses "
                 "POR ACORDO EXPRESSO entre as partes. Sem acordo, valem os 3 anos. "
                 "Com acordo, a presuncao passa a 1 ano (art. 13.o n.o 3).",
        "requires_confirmation": "Houve acordo expresso a reduzir o prazo para 18 meses?",
    },
    "bem_movel_recondicionado": {
        "label": "Bem movel recondicionado",
        "liability_months": 36,
        "presumption_months": 24,
        "basis": "DL 84/2021 art. 12.o - bens recondicionados mantem os 3 anos, "
                 "com mencao obrigatoria na fatura.",
    },
    "bem_imovel": {
        "label": "Bem imovel",
        "liability_months": 120,
        "liability_months_non_structural": 60,
        # Art. 23.o n.o 4: the presumption runs for the WHOLE period of n.o 1, not
        # the 2 years of art. 13.o, which governs movable goods. Until v1.0.2 this
        # said 24 and told a home buyer the burden of proof moved to them 8 years
        # early for a structural defect.
        "presumption_months": None,
        "presumption_whole_period": True,
        "basis": "DL 84/2021 art. 23.o n.o 1 - 10 anos elementos estruturais, "
                 "5 anos restantes defeitos; presuncao durante todo o prazo "
                 "(art. 23.o n.o 4).",
    },
    "conteudo_digital": {
        "label": "Conteudo ou servico digital",
        "liability_months": None,
        "presumption_months": 12,
        "basis": "DL 84/2021 - regime proprio para conteudos e servicos digitais. "
                 "O prazo depende de o fornecimento ser pontual ou continuado.",
        "unsupported": "O regime digital distingue fornecimento pontual de continuado "
                       "e esta skill nao modela essa distincao. Consulte a DECO ou um jurista.",
    },
    "servico": {
        "label": "Prestacao de servicos (reparacao, cabeleireiro, consultoria)",
        "liability_months": None,
        "presumption_months": None,
        "basis": "FORA do ambito do DL 84/2021 (art. 1.o). Servicos comuns nao "
                 "tem garantia legal de conformidade nos termos deste diploma.",
        "unsupported": "Servicos comuns nao estao abrangidos. Pode existir "
                       "responsabilidade contratual ou civil, que esta skill nao avalia.",
    },
    "por_classificar": {
        "label": "Por classificar",
        "liability_months": None,
        "presumption_months": None,
        "basis": "O codigo QR nao diz o que foi comprado.",
        "unsupported": "Classifique a compra para obter prazos. Nada e assumido.",
    },
}

# Presented before any guarantee row is written, and recorded as acknowledged.
PREREQUISITOS = [
    "Guardar a fatura ou talao. E a prova de compra e da data - sem ela o prazo "
    "nao se demonstra.",
    "O comprador tem de ser CONSUMIDOR (pessoa singular, fora da atividade "
    "profissional). Compras empresariais seguem o regime comercial, nao este.",
    "O defeito nao pode resultar de mau uso, desgaste normal, acidente ou "
    "reparacao por terceiros nao autorizados.",
    "A comunicacao do defeito ao vendedor deve ser feita por meio suscetivel de "
    "prova - carta, email, formulario com comprovativo (art. 12.o n.o 5). Dentro "
    "do prazo de garantia nao existe prazo para denunciar - o DL 84/2021 "
    "eliminou-o (preambulo) -, mas a prova de o ter feito e essencial.",
    "Feita a comunicacao, os direitos caducam 2 anos depois (art. 17.o n.o 1). "
    "Comunicar cedo nao basta: e preciso agir dentro desses 2 anos.",
    "Nos primeiros 2 anos presume-se que o defeito ja existia na entrega e cabe "
    "ao VENDEDOR provar o contrario (art. 13.o n.o 1). Depois disso, a prova passa "
    "a ser sua. Excecoes: 1 ano num bem usado cujo prazo foi reduzido por acordo "
    "(art. 13.o n.o 3); todo o prazo de garantia num imovel (art. 23.o n.o 4).",
    "O prazo conta da ENTREGA do bem, nao da data da fatura. Se comprou online "
    "ou por encomenda, use a data de entrega efetiva.",
]


def _plus_months(d, months):
    """Add whole months, clamping to the last valid day.

    Codigo Civil art. 279.o al. c) via art. 296.o: a term ending on a day the
    final month does not have ends on that month's last day. So 29 Feb + 3
    years is 28 Feb, NOT 1 March.
    """
    y, m = d.year + (d.month - 1 + months) // 12, (d.month - 1 + months) % 12 + 1
    day = d.day
    while day > 0:
        try:
            return date(y, m, day)
        except ValueError:
            day -= 1
    raise ValueError("unreachable")


def compute(delivery, kind="por_classificar", reduced_agreed=False,
            date_is_invoice_date=False):
    """Guarantee milestones. Returns a dict that is honest about what it lacks.

    `delivery` should be the DELIVERY date. If only the invoice date is known,
    pass it with date_is_invoice_date=True and the result says so - for an
    online order those differ and the difference is the consumer's, not ours,
    to absorb silently.
    """
    spec = KINDS.get(kind)
    if spec is None:
        raise ValueError("unknown kind %r; expected one of %s" % (kind, sorted(KINDS)))

    out = {
        "tipo": kind,
        "tipo_label": spec["label"],
        "base_legal": spec["basis"],
        "data_referencia": delivery.isoformat(),
        "data_e_estimada": bool(date_is_invoice_date),
        "avisos": [],
        "presuncao_termina": None,
        "garantia_termina": None,
    }
    if date_is_invoice_date:
        out["avisos"].append(
            "Prazos calculados a partir da DATA DA FATURA porque a data de "
            "entrega nao foi indicada. O DL 84/2021 conta da entrega; se o bem "
            "chegou mais tarde, os prazos reais terminam mais tarde.")

    if spec.get("unsupported"):
        out["avisos"].append(spec["unsupported"])
        return out

    months = spec["liability_months"]
    presumption, presumption_basis = spec["presumption_months"], "art. 13.o n.o 1"
    if kind == "bem_movel_usado" and reduced_agreed:
        months = spec["liability_months_if_agreed"]
        # Art. 13.o n.o 3. Until v1.0.2 the 24 months of n.o 1 applied here too,
        # so the "burden of proof moves" date fell AFTER the guarantee itself
        # had ended (2028-02-14 vs 2027-08-14 for a 2026-02-14 delivery).
        presumption, presumption_basis = (spec["presumption_months_if_agreed"],
                                          "art. 13.o n.o 3")
        out["avisos"].append(
            "Prazo reduzido a 18 meses por acordo expresso (art. 12.o n.o 3). "
            "Sem esse acordo seriam 3 anos. Com o acordo, a presuncao de que o "
            "defeito ja existia dura 1 ano, nao 2 (art. 13.o n.o 3). Se o bem foi "
            "anunciado como RECONDICIONADO, a reducao nao vale e mantem-se 3 anos "
            "e 2 anos - classifique-o como recondicionado.")
    if kind == "bem_imovel":
        out["garantia_termina_estrutural"] = _plus_months(delivery, 120).isoformat()
        out["garantia_termina_outros"] = _plus_months(delivery, 60).isoformat()
        out["presuncao_termina_estrutural"] = out["garantia_termina_estrutural"]
        out["presuncao_termina_outros"] = out["garantia_termina_outros"]
        out["avisos"].append(
            "Imoveis tem dois prazos: 10 anos para elementos estruturais, "
            "5 anos para os restantes defeitos (art. 23.o n.o 1). Durante TODO "
            "esse prazo presume-se que o defeito ja existia na entrega - a prova "
            "nao passa para si ao fim de 2 anos (art. 23.o n.o 4).")

    if months:
        out["garantia_termina"] = _plus_months(delivery, months).isoformat()
    if presumption:
        out["presuncao_termina"] = _plus_months(delivery, presumption).isoformat()
        out["avisos"].append(
            "Ate %s o VENDEDOR tem de provar que o defeito nao existia na entrega, "
            "salvo se isso for incompativel com a natureza do bem ou do defeito. "
            "Depois dessa data continua a ter direitos, mas a prova passa a ser sua "
            "(%s)." % (out["presuncao_termina"], presumption_basis))
    return out


def _ical_escape(t):
    return (t.replace("\\", "\\\\").replace(";", r"\;")
             .replace(",", r"\,").replace("\n", r"\n"))


def to_ical(rows, reminder_days=30, prodid="-//recibosegarantia//PT//EN"):
    """RFC 5545 VCALENDAR. Two events per purchase, because there are two dates.

    The presumption expiry is the one nobody knows about and the one worth a
    reminder: rights do not end there, but the burden of proof moves.
    """
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:" + prodid,
             "CALSCALE:GREGORIAN", "METHOD:PUBLISH"]
    n = 0
    for r in rows:
        g, desc = r.get("garantia") or {}, r.get("descricao", "compra")
        if g.get("tipo") == "bem_imovel":
            # Two guarantee ends, and the 10-year one covers ONLY structural
            # elements (art. 23.o n.o 1). Until v1.0.2 only the 10-year date was
            # exported, labelled "no guarantee after this date" - which told a
            # buyer a non-structural defect in years 5-10 was still covered.
            events = (
                ("garantia_termina_outros",
                 "Fim da garantia legal - defeitos NAO estruturais",
                 "Termina a responsabilidade do vendedor pelas faltas de "
                 "conformidade que nao sejam de elementos construtivos "
                 "estruturais (DL 84/2021 art. 23.o n.o 1 b)). Ate aqui "
                 "presume-se que o defeito ja existia na entrega (art. 23.o n.o 4)."),
                ("garantia_termina_estrutural",
                 "Fim da garantia legal - elementos estruturais",
                 "Termina a responsabilidade do vendedor por faltas de conformidade "
                 "de elementos construtivos estruturais (DL 84/2021 art. 23.o "
                 "n.o 1 a)). Depois desta data nao ha garantia legal."),
            )
        else:
            events = (
                ("presuncao_termina", "Fim da presuncao (prova passa a ser sua)",
                 "Ate esta data o vendedor tinha de provar que o defeito nao existia "
                 "na entrega. A partir de agora a prova e sua. Se o bem tem defeito, "
                 "comunique JA, por escrito e com comprovativo."),
                ("garantia_termina", "Fim da garantia legal",
                 "Termina a responsabilidade do vendedor por falta de conformidade "
                 "(DL 84/2021 art. 12.o). Depois desta data nao ha garantia legal."),
            )
        for key, title, body in events:
            when = g.get(key)
            if not when:
                continue
            n += 1
            due = date.fromisoformat(when)
            start = due - timedelta(days=reminder_days)
            uid = "%s-%s-%s@recibosegarantia" % (
                r.get("atcud", "sem-atcud").replace(" ", ""), key, when)
            lines += [
                "BEGIN:VEVENT",
                "UID:" + _ical_escape(uid),
                "DTSTAMP:%sT090000Z" % date.today().strftime("%Y%m%d"),
                "DTSTART;VALUE=DATE:" + start.strftime("%Y%m%d"),
                "DTEND;VALUE=DATE:" + (start + timedelta(days=1)).strftime("%Y%m%d"),
                "SUMMARY:" + _ical_escape("%s - %s" % (title, desc)),
                "DESCRIPTION:" + _ical_escape(
                    "%s\nData limite: %s\nCompra: %s\nFatura: %s\n\n%s"
                    % (body, when, r.get("data", "?"), r.get("numero_documento", "?"),
                       "Prova de compra necessaria. Guarde a fatura.")),
                "CATEGORIES:GARANTIA",
                "BEGIN:VALARM", "TRIGGER:-P1D", "ACTION:DISPLAY",
                "DESCRIPTION:" + _ical_escape(title), "END:VALARM",
                "END:VEVENT",
            ]
    lines.append("END:VCALENDAR")
    # RFC 5545 line folding at 75 octets.
    folded = []
    for ln in lines:
        b = ln.encode("utf-8")
        while len(b) > 75:
            cut = 75
            while cut > 1 and (b[cut] & 0xC0) == 0x80:
                cut -= 1
            folded.append(b[:cut].decode("utf-8"))
            b = b" " + b[cut:]
        folded.append(b.decode("utf-8"))
    return "\r\n".join(folded) + "\r\n", n


def _imovel_ical_ok(d):
    ics, n = to_ical([{"descricao": "Apartamento", "atcud": "BBBB2222-1",
                       "garantia": compute(d, "bem_imovel")}])
    # Reminders fire 30 days before each end: 2031-01-15 (5 years) and 2036-01-15.
    return (n == 2 and "20310115" in ics and "20360115" in ics
            and "NAO estruturais" in ics and "elementos estruturais" in ics)


def _selftest():
    failed = 0
    print("guarantee periods (DL 84/2021)")
    print("-" * 68)
    d = date(2026, 2, 14)
    cases = [
        ("bem_movel_novo", False, "2028-02-14", "2029-02-14"),
        ("bem_movel_usado", False, "2028-02-14", "2029-02-14"),
        ("bem_movel_usado", True, "2027-02-14", "2027-08-14"),
        ("bem_movel_recondicionado", False, "2028-02-14", "2029-02-14"),
        ("servico", False, None, None),
        ("por_classificar", False, None, None),
        ("conteudo_digital", False, None, None),
    ]
    for kind, red, exp_p, exp_g in cases:
        g = compute(d, kind, reduced_agreed=red)
        ok = g["presuncao_termina"] == exp_p and g["garantia_termina"] == exp_g
        failed += 0 if ok else 1
        print("%-4s %-28s%s presuncao=%s fim=%s" %
              ("PASS" if ok else "FAIL", kind, " (acordo)" if red else "",
               g["presuncao_termina"], g["garantia_termina"]))

    print("\nrefusals and honesty")
    print("-" * 68)
    checks = [
        ("service produces NO dates",
         compute(d, "servico")["garantia_termina"] is None),
        ("service says why",
         "FORA do ambito" in compute(d, "servico")["base_legal"]),
        ("unclassified produces NO dates",
         compute(d, "por_classificar")["garantia_termina"] is None),
        ("default kind is por_classificar", compute(d)["tipo"] == "por_classificar"),
        ("invoice-date substitution is disclosed",
         any("DATA DA FATURA" in a for a in
             compute(d, "bem_movel_novo", date_is_invoice_date=True)["avisos"])),
        ("presumption warning names the shift",
         any("prova passa a ser sua" in a for a in
             compute(d, "bem_movel_novo")["avisos"])),
        ("imovel gives both periods",
         compute(d, "bem_imovel")["garantia_termina_estrutural"] == "2036-02-14"),
        ("imovel presumption covers the whole period (art. 23.o n.o 4)",
         compute(d, "bem_imovel")["presuncao_termina_estrutural"] == "2036-02-14"
         and compute(d, "bem_imovel")["presuncao_termina_outros"] == "2031-02-14"
         and compute(d, "bem_imovel")["presuncao_termina"] is None),
        ("presumption never outlives the guarantee",
         all(compute(d, k, reduced_agreed=r)["presuncao_termina"] is None
             or compute(d, k, reduced_agreed=r)["garantia_termina"] is None
             or compute(d, k, reduced_agreed=r)["presuncao_termina"]
             <= compute(d, k, reduced_agreed=r)["garantia_termina"]
             for k in KINDS for r in (False, True))),
        ("unknown kind raises", _raises(lambda: compute(d, "gelado"))),
        ("29 Feb -> 28 Feb, not 1 Mar (CC art. 279)",
         compute(date(2024, 2, 29), "bem_movel_novo")["garantia_termina"] == "2027-02-28"),
        ("31 Jan + 1 month clamps to 28/29 Feb",
         _plus_months(date(2026, 1, 31), 1) == date(2026, 2, 28)),
        ("7 prerequisites presented", len(PREREQUISITOS) == 7),
    ]
    for name, ok in checks:
        failed += 0 if ok else 1
        print("%-4s %s" % ("PASS" if ok else "FAIL", name))

    print("\nical export")
    print("-" * 68)
    rows = [{"descricao": "Portatil", "atcud": "JFHF6T5J-117", "data": "2026-02-14",
             "numero_documento": "FT 2026/117",
             "garantia": compute(d, "bem_movel_novo")},
            {"descricao": "Corte de cabelo", "atcud": "AAAA1111-9",
             "garantia": compute(d, "servico")}]
    ics, n = to_ical(rows)
    ical_checks = [
        ("two events for the good, none for the service", n == 2),
        ("valid envelope", ics.startswith("BEGIN:VCALENDAR") and
         ics.rstrip().endswith("END:VCALENDAR")),
        ("CRLF line endings", "\r\n" in ics and "\n\n" not in ics),
        ("no line exceeds 75 octets",
         all(len(l.encode("utf-8")) <= 75 for l in ics.split("\r\n"))),
        ("both milestone dates present",
         "20280115" in ics and "20290115" in ics),
        ("uid is unique per event",
         len({l for l in ics.split("\r\n") if l.startswith("UID:")}) == 2),
        ("alarm attached", ics.count("BEGIN:VALARM") == 2),
        ("imovel exports BOTH guarantee ends, the 10-year one labelled structural",
         _imovel_ical_ok(d)),
    ]
    for name, ok in ical_checks:
        failed += 0 if ok else 1
        print("%-4s %s" % ("PASS" if ok else "FAIL", name))

    print("-" * 68)
    print("SELFTEST: %s" % ("PASS" if not failed else "FAIL (%d)" % failed))
    return 1 if failed else 0


def _raises(fn):
    try:
        fn()
        return False
    except Exception:
        return True


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Consumer-guarantee periods + iCal.")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(_selftest())
    ap.print_help()
    sys.exit(2)
