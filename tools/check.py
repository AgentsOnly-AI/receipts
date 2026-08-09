#!/usr/bin/env python3
# receipts reference checker — v0.1-draft
# Verifies pointer integrity of a receipts sidecar file by sampling.
# Semantic support (DISPUTED) is a judgment for the sampling reader;
# this tool gets you to the raw thing and tells you whether it's intact.
#
# Usage:
#   python3 check.py <report>.receipts.jsonl [--sample N] [--seed S] [--all]
#
# Verdicts per receipt: OK | CHANGED | MISSING  (superseded receipts are
# resolved first; only the current set is sampled unless --all is given).
# Exit code 0 iff every sampled receipt is OK.

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path


def load_receipts(path: Path):
    receipts = []
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
            receipts.append(r)
    return receipts


def current_set(receipts):
    """Receipts not superseded by any later receipt (SPEC §6)."""
    superseded = {r["supersedes"] for r in receipts if r.get("supersedes")}
    return [r for r in receipts if r["id"] not in superseded], superseded


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
    uri = src.get("uri", "")
    if "://" in uri:
        return "MISSING", "remote URIs not dereferenced by v0.1 reference checker"
    target = (base / uri).resolve()
    if not target.is_file():
        return "MISSING", f"cannot dereference {uri}"
    expected = src.get("sha256")
    if expected:
        actual = hashlib.sha256(region_bytes(target, src.get("lines"))).hexdigest()
        if actual != expected:
            return "CHANGED", f"sha256 mismatch ({actual[:12]}… != {expected[:12]}…)"
    return "OK", uri + (f" lines {src['lines']}" if src.get("lines") else "")


def main():
    ap = argparse.ArgumentParser(description="receipts v0.1 reference checker")
    ap.add_argument("receipts_file", type=Path)
    ap.add_argument("--sample", type=int, default=0, help="sample size (default: all current receipts)")
    ap.add_argument("--seed", type=int, default=None, help="RNG seed for reproducible samples")
    ap.add_argument("--all", action="store_true", help="include superseded receipts in the pool")
    args = ap.parse_args()

    receipts = load_receipts(args.receipts_file)
    base = args.receipts_file.resolve().parent
    current, superseded = current_set(receipts)
    pool = receipts if args.all else current

    if args.sample and args.sample < len(pool):
        rng = random.Random(args.seed)
        pool = rng.sample(pool, args.sample)

    print(f"receipts check — {args.receipts_file.name}")
    print(f"  {len(receipts)} receipts, {len(superseded)} superseded, sampling {len(pool)}\n")

    failures = 0
    for r in pool:
        verdict, detail = check_receipt(r, base)
        if verdict != "OK":
            failures += 1
        tag = " (superseded)" if r["id"] in superseded else ""
        print(f"  [{verdict:^7}] {r['id']}{tag}: {r['claim']}")
        print(f"            → {detail}")
        if r.get("derivation"):
            print(f"            derivation: {r['derivation']}")
    print()
    print("this check is itself a small report: the receipts above are the ones")
    print("it actually read. semantic support is yours to judge — go look.")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
