#!/usr/bin/env python3
# receipts reference checker — v0.2-draft
# Verifies pointer integrity of a receipts sidecar file by sampling.
# Semantic support (DISPUTED) is a judgment for the sampling reader;
# this tool gets you to the raw thing and tells you whether it's intact.
#
# Usage:
#   python3 check.py <report>.receipts.jsonl [--sample N] [--seed S] [--all]
#                                            [--today YYYY-MM-DD] [--strict]
#
# Verdicts per receipt: OK | CHANGED | MISSING | UNREADABLE  (superseded
# receipts are resolved first; only the current set is sampled unless --all
# is given). Failing marks: STALE, UNWITNESSED. Exit code 0 iff every sampled
# receipt is OK and carries no failing mark.
#
# What this checker implements of SPEC v0.2-draft (§9 asks a tool to say):
#   §4.1   required fields, including source.uri; ids unique in the file.
#   §5.1   OK / CHANGED / MISSING. DISPUTED is the reader's call, not a tool's.
#   §4.2   canonical form: absent means raw bytes. SPEC v0.2 names no forms,
#          so any declared source.canonical is UNREADABLE, never OK.
#   §6     a receipt supersedes only a receipt on an earlier line ("later"
#          read as later in the append-only file). A supersedes that names no
#          earlier id is flagged and has no effect.
#   §7     review_by: STALE once --today is past the date and no later receipt
#          supersedes it (the only "review recorded" this tool can see).
#   §11.3  UNWITNESSED, partly: a read (a receipt with subject and authorizer)
#          whose subject is not its authorizer, and whose witness is absent or
#          is the reader or the authorizer. The window is not checked.
#   §4.2-§4.5 fields v0.2 requires: warnings by default, errors with
#          --strict. The names are SPEC §4.6's suggestions, not decided ones.
# Not implemented: UNREAD, SELF-READ, UNTESTED, UNBOUNDED, SELF-REPORTED,
# BOUNDED, WITNESSED, UNRECORDED (no field names or class markers in the
# spec), scheduled emission (§5.4), and writing the check-report as a
# receipts file (it goes to stdout).
#
# UNREADABLE is provisional: SPEC v0.2 §4.2 leaves the name open (§12.1).
# It is also used for URLs and URNs, which this checker does not fetch, so
# a checker limitation does not land in the MISSING (source gone) column.
#
# Narrowing: source.lines "A-B" selects lines A..B (1-based, inclusive) of
# the file decoded as UTF-8 (bad bytes replaced), joined with "\n", with no
# trailing newline, re-encoded as UTF-8. SPEC v0.2 does not define this
# (§12.6); it is the v0.1 checker's rule, kept unchanged. source.span has no
# format in the spec, so it is not applied: the whole file (or the lines
# range) is hashed as raw bytes, and the output says so.

import argparse
import hashlib
import json
import random
import sys
from datetime import date
from pathlib import Path

UNREADABLE = "UNREADABLE"

# Fields SPEC v0.2 requires with no decided name. Names are §4.6 suggestions.
V02_FIELDS = [
    (("schema",), "§4.5"),
    (("performer",), "§4.3"),
    (("parties",), "§4.3"),
    (("compellable_by",), "§4.3"),
    (("obligation_date",), "§4.3"),
    (("measures",), "§4.4"),
    (("carried", "pointed"), "§4.2"),
]


def v02_notes(r):
    """What a receipt lacks under SPEC v0.2 §4.2-§4.5 and §7."""
    notes = []
    missing = [f"{'|'.join(names)} ({sec})" for names, sec in V02_FIELDS
               if not any(k in r for k in names)]
    if missing:
        notes.append("lacks v0.2 fields: " + ", ".join(missing))
    parties = r.get("parties")
    if isinstance(parties, list) and not all(
            isinstance(p, dict) and "did" in p and "answers_for" in p for p in parties):
        notes.append("each party needs 'did' and 'answers_for' (§4.3)")
    if "continuity" in r and r["continuity"] not in ("party", "process", "both"):
        notes.append("continuity must be party, process, or both (§4.3)")
    if "review_by" in r and "review_conditions" not in r:
        notes.append("review_by has no review_conditions beside it (§7)")
    return notes


def load_receipts(path: Path):
    receipts, notes, seen = [], [], {}
    with path.open() as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError as e:
                sys.exit(f"error: line {n} is not valid JSON: {e}")
            for field in ("id", "claim", "source", "author", "date"):
                if field not in r:
                    sys.exit(f"error: receipt on line {n} missing required field '{field}'")
            uri = r["source"].get("uri") if isinstance(r["source"], dict) else None
            if not uri or not isinstance(uri, str):
                sys.exit(f"error: receipt on line {n} missing required field 'source.uri'")
            if r["id"] in seen:
                sys.exit(f"error: receipt on line {n} reuses id '{r['id']}' from line {seen[r['id']]}")
            seen[r["id"]] = n
            if "review_by" in r:
                try:
                    date.fromisoformat(r["review_by"])
                except (TypeError, ValueError):
                    sys.exit(f"error: receipt on line {n} has review_by {r['review_by']!r}, not an ISO date")
            notes += [f"{r['id']} (line {n}) {note}" for note in v02_notes(r)]
            receipts.append(r)
    return receipts, notes


def current_set(receipts):
    """Receipts not superseded by any later receipt (SPEC §6)."""
    ids = {r["id"] for r in receipts}
    earlier, superseded, notes = set(), set(), []
    for r in receipts:
        target = r.get("supersedes")
        if target is None:
            pass
        elif not isinstance(target, str):
            sys.exit(f"error: {r['id']} supersedes {target!r}; expected one id or null")
        elif target in earlier:
            superseded.add(target)
        elif target == r["id"]:
            notes.append(f"{r['id']} supersedes itself; ignored")
        elif target in ids:
            notes.append(f"{r['id']} supersedes {target}, which comes later in the file; ignored")
        else:
            notes.append(f"{r['id']} supersedes {target}, which is not in this file (dangling supersedes)")
        earlier.add(r["id"])
    return [r for r in receipts if r["id"] not in superseded], superseded, notes


def region_bytes(path: Path, lines_spec):
    data = path.read_bytes()
    if not lines_spec:
        return data
    start, _, end = str(lines_spec).partition("-")
    start, end = int(start), int(end or start)
    selected = data.decode("utf-8", errors="replace").splitlines()[start - 1 : end]
    return "\n".join(selected).encode("utf-8")


def check_receipt(r, base: Path):
    src = r["source"]
    uri = src["uri"]
    if "://" in uri or uri.lower().startswith("urn:"):
        return UNREADABLE, "remote URI (URL or URN): this checker does not fetch it, so it did not check it"
    target = (base / uri).resolve()
    if not target.is_file():
        return "MISSING", f"cannot dereference {uri}"
    if src.get("canonical"):
        return UNREADABLE, (f"declared canonical form {src['canonical']!r} is not one this checker "
                            "can reproduce (it has raw bytes only)")
    where = uri + (f" lines {src['lines']}" if src.get("lines") else "")
    if "span" in src:
        where += f" (span {src['span']!r} not applied: no span format in SPEC v0.2; raw bytes hashed)"
    expected = src.get("sha256")
    if expected:
        actual = hashlib.sha256(region_bytes(target, src.get("lines"))).hexdigest()
        if actual != expected:
            return "CHANGED", f"sha256 mismatch ({actual[:12]}… != {expected[:12]}…) over {where}"
    return "OK", where


def derived_marks(r, today, superseded):
    """Failing marks (SPEC §5.5) this checker can compute, each with its reason."""
    marks, notes = [], []
    review_by = r.get("review_by")
    if review_by and r["id"] not in superseded and date.fromisoformat(review_by) < today:
        marks.append(("STALE", f"review_by {review_by} has passed as of {today}; no review recorded"))
    if "subject" in r and "authorizer" in r and r["subject"] != r["authorizer"]:
        witness = r.get("witness")
        if not witness:
            marks.append(("UNWITNESSED", "read has no witness (§11.3)"))
        elif witness == r["authorizer"]:
            marks.append(("UNWITNESSED", "the authorizer cannot be the witness (§11.3)"))
        elif witness == r.get("reader"):
            marks.append(("UNWITNESSED", "the reader cannot be the witness (§11.3)"))
        else:
            notes.append("witness window not checked (no window format in SPEC v0.2)")
    return marks, notes


def main():
    ap = argparse.ArgumentParser(description="receipts v0.2-draft reference checker")
    ap.add_argument("receipts_file", type=Path)
    ap.add_argument("--sample", type=int, default=0, help="sample size (default: all current receipts)")
    ap.add_argument("--seed", type=int, default=None, help="RNG seed for reproducible samples (one is picked and printed if omitted)")
    ap.add_argument("--all", action="store_true", help="include superseded receipts in the pool")
    ap.add_argument("--today", type=date.fromisoformat, default=date.today(),
                    help="date to check review_by against, YYYY-MM-DD (default: system date)")
    ap.add_argument("--strict", action="store_true", help="make v0.2 schema warnings errors")
    args = ap.parse_args()

    receipts, notes = load_receipts(args.receipts_file)
    base = args.receipts_file.resolve().parent
    current, superseded, supersede_notes = current_set(receipts)
    notes += supersede_notes
    for note in notes:
        print(f"{'error' if args.strict else 'warning'}: {note}", file=sys.stderr)
    if notes and args.strict:
        sys.exit(f"error: {len(notes)} schema problem(s) under --strict")
    if notes:
        print("warning: field names are SPEC v0.2 §4.6 suggestions; --strict makes these errors", file=sys.stderr)

    pool = receipts if args.all else current
    kind = "" if args.all else "current "
    seed = args.seed
    if args.sample and args.sample < len(pool):
        if seed is None:
            seed = random.SystemRandom().randrange(2**32)
        how = f"random.Random({seed}).sample of {args.sample} from {len(pool)} {kind}receipts in file order"
        pool = random.Random(seed).sample(pool, args.sample)
    else:
        how = f"all {len(pool)} {kind}receipts, no random draw"

    sidecar = hashlib.sha256(args.receipts_file.read_bytes()).hexdigest()
    print(f"receipts check — {args.receipts_file.name}")
    print(f"  {len(receipts)} receipts, {len(superseded)} superseded, sampling {len(pool)}")
    print(f"  sample: {how}")
    print(f"  from: sidecar sha256 {sidecar}")
    print(f"  checked: {args.today}, by tools/check.py (SPEC v0.2-draft subset; see its header)\n")

    failures = 0
    for r in pool:
        verdict, detail = check_receipt(r, base)
        marks, mark_notes = derived_marks(r, args.today, superseded)
        if verdict != "OK" or marks:
            failures += 1
        tag = " (superseded)" if r["id"] in superseded else ""
        print(f"  [{verdict:^7}] {r['id']}{tag}: {r['claim']}")
        print(f"            → {detail}")
        if r.get("derivation"):
            print(f"            derivation: {r['derivation']}")
        for mark, why in marks:
            print(f"  [{mark:^7}] {r['id']}: {why}")
        for note in mark_notes:
            print(f"            note: {note}")
    print()
    print("this check is itself a small report: the receipts above are the ones")
    print("it actually read. semantic support is yours to judge — go look.")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
