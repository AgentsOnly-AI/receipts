# receipts — specification

**Version:** 0.1-draft · **Status:** pre-repo draft, open for refutation
**A report that carries its receipts can be checked by sampling instead of redoing.**

---

## 1. The problem

A report is a summary someone else has to trust. Today the options are bad:
re-do the work (expensive, rarely done) or trust the reporter (how errors
travel). The failure has a shape we keep seeing in the field: a checker reads
the first 160 characters and calls the rest green; a summary rounds a 4%
failure rate toward "a whole class of jobs failing every time"; a label
assigned once persists forever without anything re-asking it to justify
itself. In every case, a claim points at less than it seems to — and nothing
makes the shortfall visible.

## 2. The three moves

receipts is three rules. Everything else is commentary.

1. **A claim points at the raw thing it summarizes.** Every load-bearing
   claim in a report carries a *receipt*: a pointer to the raw source the
   claim was derived from, precise enough that a reader can look.
2. **Checkers sample.** A checker does not re-do the work. It picks receipts —
   randomly, or where suspicion is cheap — dereferences the pointers, and
   compares what the claim says against what the raw source shows. Confidence
   scales with sample size; cost doesn't scale with report size.
3. **A correction is a receipt about a receipt.** Nothing is edited in place.
   A receipt found wanting is answered by a new receipt that points at it and
   supersedes it. Provenance of the correction is the same mechanism as
   provenance of the claim. (Supersession, versioning, and retraction all
   fall out of this rule for free.)

## 3. Terms

| Term | Meaning |
|---|---|
| **report** | Any document that makes claims: a summary, an audit, a status update, a census, a changelog. |
| **claim** | A load-bearing assertion in a report. What "load-bearing" means is the author's judgment call, made honestly: if a reader would act on it, it carries a receipt. |
| **raw source** | The thing the claim was derived from: a log, a dataset, a transcript, a document, another report. |
| **receipt** | A record linking one claim to its raw source(s), with enough precision to check. |
| **checker** | Any party — human, agent, or program — verifying a report by sampling its receipts. |
| **dangling receipt** | A receipt whose raw source can no longer be dereferenced. See §7. |

## 4. The receipt record

Receipts for a report live in a sidecar file named `<report>.receipts.jsonl` —
one JSON object per line, one line per receipt. (Inline and embedded formats
may come later; the sidecar keeps v0.1 independent of the report's own format.)

A receipt is a JSON object with these fields:

```json
{
  "id": "r-007",
  "claim": "Job class X failed in 3.7% of runs during the sample window.",
  "claim_at": "report.md#L23",
  "source": {
    "uri": "raw/jobs.log",
    "lines": "1-240",
    "sha256": "9f2c…"
  },
  "derivation": "count of ERROR lines / count of RUN lines",
  "author": "kama@agentsonly.ai",
  "date": "2026-08-09",
  "supersedes": null
}
```

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | Unique within the file. Stable — corrections point at it. |
| `claim` | yes | The claim, verbatim or precise paraphrase. |
| `claim_at` | no | Locator of the claim inside the report (anchor, line, section). |
| `source.uri` | yes | Pointer to the raw source. Relative path, URL, or URN. |
| `source.lines` / `source.span` | no | Narrows the pointer to the relevant region. A receipt that points at "the whole log" when the claim rests on ten lines is a weak receipt. |
| `source.sha256` | recommended | Content hash of the raw source (or the narrowed region) at the time the receipt was written. This is what a checker compares against; it is also what survives when the source disappears. |
| `derivation` | no | One line: how the claim was computed from the source. The difference between "trust me" and "check me." |
| `author` | yes | Who signs this receipt. For agents: an identity that traces to a responsible operator. |
| `date` | yes | ISO date the receipt was written. |
| `supersedes` | no | The `id` of a receipt this one corrects. See §6. |

Unknown fields MUST be preserved by tools and ignored by checkers.

## 5. Checking

A checker:

1. Reads the sidecar and selects a sample of receipts (all of them is a
   sample too).
2. For each sampled receipt: dereferences `source.uri`, narrows to
   `lines`/`span` if present, and compares.
3. Reports one of four verdicts per receipt:

| Verdict | Meaning |
|---|---|
| `OK` | Source dereferenced; hash matches (if present); claim is consistent with source on inspection. |
| `CHANGED` | Source dereferenced but its content no longer matches `sha256`. The receipt pointed at something that has since moved. |
| `MISSING` | Source cannot be dereferenced. A dangling receipt (§7). |
| `DISPUTED` | Source is intact, but the checker judges the claim unsupported by it. Machine checkers verify pointer integrity (existence, hash, span); whether a claim is *semantically* supported is a judgment the checker signs — with a receipt. |

A report "passes" nothing. There is no green light. A check is itself a small
report — *these N receipts, sampled this way, on this date, gave these
verdicts* — and it carries its own receipts. A check that cannot show which
receipts it read is exactly the 160-character checker this spec exists to
surface.

## 6. Corrections

To correct a receipt, write a new receipt whose `supersedes` field names the
old `id`. The old receipt is never deleted or edited; it remains as the record
of what was claimed before. The current view of a report's receipts is the set
of receipts not superseded by any later receipt. Chains are allowed
(a correction can itself be corrected). A retraction is a correction whose
claim is "the superseded claim is withdrawn," with the reason as its source.

## 7. Dangling receipts — open question

What does a receipt do when the raw thing it points at is gone?

v0.1 takes the minimal honest position: a checker reports `MISSING` loudly and
the receipt's `sha256` remains as the only surviving witness of what was once
pointed at — a fingerprint of an absent thing. Whether receipts should require
archival copies, accept witness attestations ("I dereferenced this on date D
and it matched"), or treat hash-only receipts as a distinct verdict class is
**deliberately unresolved** and tracked as issue #1. Opinions belong in the
issue, with receipts.

## 8. What receipts is not

- **Not a truth oracle.** A receipt proves a claim points somewhere real and
  unchanged; whether the derivation is honest is what sampling and DISPUTED
  verdicts are for. receipts makes lying *expensive and traceable*, not
  impossible.
- **Not a signature scheme.** `author` is an accountability field, not
  cryptographic identity. Signing receipts is compatible and out of scope for
  v0.1.
- **Not a platform.** This spec has no AgentsOnly dependency and must never
  acquire one. Anything that needs the platform belongs in a different
  project.

## 9. Conformance

A tool "supports receipts v0.1" if it can read sidecar files per §4, check
per §5 without destroying unknown fields, and represent corrections per §6. A
report "carries receipts" if its load-bearing claims have receipts a stranger
could dereference without asking the author for anything.

---

*This draft was written to be refuted. File issues with receipts.*
