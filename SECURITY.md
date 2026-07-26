# Security & privacy

## The threat this is designed against

A photo of a receipt is among the most sensitive material a person holds: name, address,
where they were treated, what they bought. The design assumption is that **none of it
should leave the user's machine** — including to us.

## Guarantees, and how they are enforced

| Guarantee | Enforcement |
|---|---|
| No network calls | `scripts/offline_audit.py` parses every shipped file and fails on any networking/`subprocess`/`ctypes` import. Wired into `sweep.py` and CI |
| No dynamic execution | The same audit fails on builtin `eval`/`exec`/`__import__` |
| No shell-out | Fails on `os.system`, `os.popen`, `os.exec*`, `importlib.import_module` |
| Offline at runtime, not just in theory | CI re-runs **every gate with the socket layer disabled**. Any attempted connection crashes the build |
| No mandatory dependencies | Standard library only. `openpyxl` is optional and **both** paths are tested in CI |
| No telemetry | There is no analytics and no code that could add it without failing the audit |

Verify all of it:

```bash
python scripts/offline_audit.py --selftest   # prove the audit can fail
python scripts/offline_audit.py              # then trust that it didn't
```

## What the audit does NOT prove

It is a **static check, not a sandbox** — stated plainly, because an overreaching security
claim is worse than none.

- It catches networking imports, shell-outs, dynamic imports and `eval`/`exec`.
- It cannot catch every conceivable exfiltration path. `os` cannot be forbidden outright —
  the project needs `os.path` — so the dangerous *members* are enumerated, and an
  enumeration is never complete.
- The socket-disabling CI job patches **this** interpreter. A network client launched as a
  separate process would evade it.

**Neither mechanism defends against a determined malicious contributor.** That risk is
managed the ordinary way: this is a small project where every pull request is read. The
audit exists to make an *accidental* regression impossible to merge quietly, and to let a
stranger verify the offline claim without reading all the code.

## Your own data

`.gitignore` excludes `*.local.json`, `scratch/` and generated output, so an absent-minded
`git add -A` cannot publish your receipts. **Check before committing anyway.**

Never paste a real NIF, IBAN, address or full name into an issue. The engine needs none of
them — a QR payload with the digits changed reproduces any bug.

## Reporting a vulnerability

Anything that would let this project transmit data, execute arbitrary code, or read outside
its own folder: please open a **private security advisory** via the Security tab rather
than a public issue.

Reading errors, wrong periods and wrong citations are not vulnerabilities — those go in a
public issue where they can be discussed.
