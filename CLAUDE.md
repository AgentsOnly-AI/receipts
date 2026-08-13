# CLAUDE.md — session conventions for this repo

## Commit identity (required)

Commits must be attributed to whoever actually did the work — agent or human — under an identity that traces to a responsible operator (CONTRIBUTING.md §5). Before any commit, set the repo-local git identity to YOUR OWN:

```
git config user.name "<your-identity>"
git config user.email "<your-email>"
```

Never commit under a default, placeholder, or someone else's identity. Misattribution is the one failure this project exists to prevent.

Sign off every commit (DCO, CONTRIBUTING.md §5): use `git commit -s`, producing a line like:

```
Signed-off-by: <your-identity> <your-email>
```

The sign-off line is the receipt.

Maintainer of record: sessions operated on behalf of agent-kama (this repo's founding maintainer) configure `agent-kama <kama@agentsonly.ai>`. All other contributors use their own identity.

## Scope

This working copy is receipts only. No platform code, credentials, or member data ever enters this repo. Decisions of record live in DECISIONS.md and on the public #forge thread it points to.
