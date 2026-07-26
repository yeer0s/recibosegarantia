# Contributing

Thank you. This project reads documents that decide whether somebody recovers money or
loses a guarantee, so the bar is "prove it", not "looks right".

## The one rule

**Every PR keeps all gates at exit `0`:**

```bash
python scripts/fatura.py --selftest
python scripts/garantia.py --selftest
python scripts/planilha.py --selftest
python scripts/offline_audit.py --selftest && python scripts/offline_audit.py
python scripts/sweep.py
```

Nothing to install. If a gate is red, the PR is not ready — including when it went red for
a reason you believe is unrelated.

## Changing a legal constant or a field semantic

1. **Cite it.** Article and diploma, in the constant's own `basis`/`source` field. "I saw
   it online" is not a citation.
2. **Use the primary source.** The fixtures in `assets/at-examples.json` come from the AT's
   own specification. An earlier draft was built from a practitioner blog and consequently
   omitted the `J*`, `K*`, `L`, `M` and `P` fields — which mis-reconciled every Azores,
   Madeira, stamp-duty and withholding invoice. Do not repeat that.
3. **Never edit an expected value to make a test pass.** If the corpus goes red after a
   constant change, that is the corpus doing its job.

## Adding something the engine does not model

Either implement it **or** declare it — never leave it silent.

Every entry in `assets/qr-spec.json → documented_gaps` carries a **direction of error**:
does omitting this over- or under-state? `sweep.py` fails if one lacks it. If you cannot
state the direction, you do not yet understand the gap well enough to ship it.

## Adding a check

A check only ever seen green is not evidence. If you add one, add the mutation that proves
it can go red.

## What will get a PR rejected

- A networking, `subprocess` or `ctypes` import, or a builtin `eval`/`exec`. The offline
  guarantee is why this can be trusted with photos of receipts. No exceptions, not even to
  "quickly fetch" a value.
- A mandatory dependency. Standard library only, deliberately.
- A constant without a citation.
- Real personal data in a fixture. Invent the numbers.
- Weakening or removing the disclaimer.
- **Inferring what was purchased.** If you add a heuristic guessing goods-vs-service from
  the IVA rate, the merchant or the document type, it will be rejected. That information is
  not in the QR code, and guessing it invents legal deadlines that do not exist.

## Reporting an error

A wrong period, a mis-cited article, a swapped field semantic — that is the most valuable
contribution to this project, and you need write no code at all to make it.
