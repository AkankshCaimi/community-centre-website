# CI

## The rule

**`make ci` must be green before a pull request is pushed.**

A red pull request only ever means one thing: a deliberate checkpoint-2 red, where the failing tests of a feature are pushed before its code (`CLAUDE.md`, rule 2). Any other red on GitHub is a mistake that `make ci` would have shown first.

## What it runs

`make ci` runs `scripts/ci.sh all`, the same script the GitHub Actions workflow runs:

1. `make install`
2. `make lint`
3. `make test`, on a database created from nothing and removed afterwards
4. `docker build`, to prove the image of the site still builds; nothing is pushed or deployed

Lint, test and the image build all run even if an earlier one fails, as the three jobs on GitHub do. The last lines say which passed:

```
lint: passed
test: passed
image: passed
```

One stage can be run alone: `scripts/ci.sh install`, `scripts/ci.sh lint`, `scripts/ci.sh test` or `scripts/ci.sh image`.

## What it needs

- Docker running (`colima start` after a reboot).
- Port 15432 free.

It does not read or change `.env`, and it does not touch the development database: it uses its own Docker Compose project, `community-centre-ci`, with the values of `.env.example`.

## Where it can still differ from GitHub

- GitHub uses Python 3.14 and Node 24; `make ci` uses the versions on your machine.
- `make ci` tests your working tree. A file you have not added to git passes here and is missing on GitHub.

The full rules are in `docs/specs/make-ci.md`.
