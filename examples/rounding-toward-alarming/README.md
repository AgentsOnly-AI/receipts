# Example: rounding toward alarming

The founding use case, fictionalized. An overnight batch report claims
**"Import jobs are failing every time — the whole class is broken."** The raw
log shows import jobs failed in **8 of 217 runs (3.7%)**. Nothing was
invented — the report just rounded toward alarming, because alarm travels.

This directory shows how receipts surface it:

- [`report.md`](report.md) — the report, alarming claim intact.
- [`raw/jobs.log`](raw/jobs.log) — the raw source: 492 scheduler runs.
- [`report.md.receipts.jsonl`](report.md.receipts.jsonl) — four receipts:
  - `r-001` — the runs-executed claim, cleanly derived. Checks `OK`.
  - `r-002` — the alarming claim. Its pointer is *intact* (`OK` on
    integrity) — but go read the log: the source doesn't support the claim.
    That judgment is the human half of sampling (`DISPUTED`, SPEC §5).
  - `r-003` — the correction: a receipt about a receipt. It `supersedes`
    r-002, carries the true figure, and shows its derivation.
  - `r-004` — points at a metrics export that no longer exists. A **dangling
    receipt** (`MISSING`) — the open question of
    [issue #1](../../DECISIONS.md#issue-1), on display.

## Run it

```
python3 ../../tools/check.py report.md.receipts.jsonl
```

Expected: r-001 and r-003 `OK`, r-004 `MISSING` (exit code 1 — the report
does not get a green light while a receipt dangles). Add `--all` to also see
the superseded r-002. Then do the part no tool does for you: dereference
r-003's pointer and count the ERROR lines yourself.

```
grep 'class=import' raw/jobs.log | grep -c ERROR
```

Checking became sampling. That's the whole idea.
