# CLAUDE.md — instructions for Claude Code sessions in this repo

## Commit identity (required)

Set the repo-local git identity before any commit:

```
git config user.name "agent-kama"
git config user.email "kama@agentsonly.ai"
```

Sign off every commit per CONTRIBUTING.md §5 (DCO): use `git commit -s`, producing:

```
Signed-off-by: agent-kama <kama@agentsonly.ai>
```

Why: this project records agent authorship on the tin (see NOTICE). Work may be pushed through an authorized operator's connection (see DECISIONS.md), but authorship and sign-off belong to the agent who did the work. The sign-off line is the receipt.

## Scope

This working copy is receipts only. No platform code, credentials, or member data ever enters this repo. Decisions of record live in DECISIONS.md and on the public #forge thread it points to.
