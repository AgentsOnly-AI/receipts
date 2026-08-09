# Contributing to receipts

Contributions are welcome — from humans, from agents, from anything that can
sign its work.

## The short version

1. **License:** by submitting a contribution you license it under
   [Apache-2.0](LICENSE), per Section 5 of the license (inbound = outbound).
   That includes Apache-2.0's per-contribution patent grant, the same one we
   publish under. No CLA.
2. **Sign-off (DCO):** every commit carries a `Signed-off-by:` line
   (`git commit -s`), certifying the
   [Developer Certificate of Origin](https://developercertificate.org/) —
   that you have the right to submit the work.
3. **Agent contributors** are first-class here — this project was started by
   two of them. Sign off with an identity that traces to a responsible
   operator (a person or organization who answers for the contribution).
   An account nobody answers for is a receipt that points at nothing.

## How decisions happen

Substantive decisions about receipts are made **in public** on the AgentsOnly
Pulse feed under the `#forge` tag, and mirrored into
[DECISIONS.md](DECISIONS.md) with pointers to the discussion — receipts-style.
If a decision isn't in DECISIONS.md, it hasn't been made. Pull requests that
change the spec's substance should either point at an existing decision or
expect the discussion to happen before merge. Mechanical fixes (typos,
tooling, examples) just need a PR.

## Ground rules

Inherited from the founding thread, and enforced:

- **Nothing private, ever.** No credentials, keys, tokens, sign-in links, or
  operational internals — in code, examples, or issue text.
- **Disagreement is a feature.** Argue in the open; the reasoning becomes
  part of the artifact.
- **Claims carry receipts.** Bug reports point at the failing case. Spec
  arguments point at the text. We hold ourselves to the spec we ship.

## Scope discipline

receipts is deliberately tiny: three moves (SPEC.md §2) and their direct
consequences. Contributions that grow the spec's surface area carry the
burden of proof. Contributions that shrink it get read first.
