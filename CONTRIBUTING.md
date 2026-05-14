# Contributing to cTrader Skills

Thanks for your interest in contributing to cTrader Skills. This document describes how to set up a development environment, the conventions this repository follows, and how to add a new skill. By participating in this project you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

## Repository Scope

This repository contains agent skills for the [cTrader](<https://ctrader.com/>) ecosystem. Each skill lives in its own subdirectory under `skills/` and follows the [Agent Skills specification](<https://skills.sh>). Future skills go in the same place.

A typical skill directory has the following shape:

```text
skills/<skill-name>/
  SKILL.md           # required: YAML frontmatter + skill body
  LICENSE.txt        # required: byte-identical copy of root LICENSE
  references/*.md    # optional: progressive-disclosure reference files
  scripts/*.py       # optional: executable helpers (each MUST expose --self-test)
  assets/*           # optional: data files (e.g. precision tables)
```

## Development Environment

The toolchain is Python 3.12 managed with [`uv`](<https://docs.astral.sh/uv/>).

```bash
git clone https://github.com/spotware/ctrader-skills
cd ctrader-skills
uv sync --all-groups
uv run pre-commit install
```

This installs all runtime and dev dependencies (Ruff, mypy, pytest, pre-commit, commitizen, markdownlint-cli2) and wires up the git pre-commit hooks.

## Quality Gates

Before opening a Pull Request, run the full pre-commit suite locally:

```bash
uv run pre-commit run --all-files
```

The hook chain includes Ruff (lint + autofix), mypy, JSON/YAML validity checks, EOF and trailing-whitespace normalization, markdownlint, `uv lock` consistency, and commitizen. All hooks must pass.

The pytest harness in `tests/test_skill_scripts.py` parameterizes over `sorted(ROOT.glob('skills/*/scripts/*.py'))` and invokes each script with `--self-test`:

```bash
uv run pytest -v tests/
```

New skill scripts are auto-discovered: just drop a script with a `--self-test` flag under `skills/<your-skill>/scripts/` and the harness picks it up.

## Conventional Commits

This repository uses [Conventional Commits](<https://www.conventionalcommits.org/>), enforced via [commitizen](<https://commitizen-tools.github.io/commitizen/>). Common types:

| Type     | Meaning                                    | Version bump (pre-1.0) |
|----------|--------------------------------------------|------------------------|
| `feat:`  | A new user-facing feature or skill         | minor                  |
| `fix:`   | A bug fix                                  | patch                  |
| `chore:` | Maintenance, refactoring, internal cleanup | none (hidden)          |
| `docs:`  | Documentation only                         | none (hidden)          |
| `ci:`    | CI/CD configuration                        | none (hidden)          |
| `test:`  | Test infrastructure                        | none (hidden)          |

During the 0.x phase, the `release-please-config.json` sets both `bump-minor-pre-major: true` and `bump-patch-for-minor-pre-major: true`, so `feat:` bumps the minor version and `fix:` bumps the patch version. After 1.0.0, the standard SemVer rules apply: `feat:` bumps minor, `fix:` bumps patch, and a `BREAKING CHANGE:` footer or `feat!:` syntax bumps major.

[release-please](<https://github.com/googleapis/release-please>) opens release Pull Requests automatically based on the commit log on `main`.

## Skill Authoring Guide

### SKILL.md Frontmatter

Every skill begins with a YAML frontmatter block. Required and recommended fields:

```yaml
---
name: <skill-directory-name>
description: <one-sentence trigger description; start with "Use this skill when ..." or "Use this skill ALWAYS when ...">
allowed-tools: "Read, Grep, Glob, Bash(python *)"
license: Proprietary. LICENSE.txt has complete terms.
metadata:
  author: "Spotware Systems Ltd"
  # additional skill-specific metadata
---
```

- `name` MUST match the skill directory name exactly.
- `description` is what the host agent uses to decide whether to load the skill. Keep it specific.
- `allowed-tools` is the [Claude Code permissions](<https://code.claude.com/docs/en/permissions>) declaration. Use it to pre-authorize the exact tool surface the skill needs (e.g. `Bash(python *)` for skills that invoke Python helper scripts) so end users are not prompted for permission on every invocation.

### Script Convention: `--self-test`

Every script in `skills/<skill>/scripts/` MUST expose a `--self-test` command-line flag that:

- Runs the script's internal test cases (typically embedded in a `_self_test()` function).
- Exits 0 on pass and a non-zero code on failure.
- Writes a final `All self-tests passed` (or equivalent) line to stderr on success.

The `tests/test_skill_scripts.py` harness auto-discovers all scripts and asserts `--self-test` exits 0 for each. No test-list edits are required when adding a new script.

### Per-Skill `LICENSE.txt` Convention

Each skill directory contains a `LICENSE.txt` that is a **byte-identical copy** of the root `LICENSE` file. This intentional duplication exists because `npx skills add` copies only the targeted skill directory; the license file must travel with the skill for proprietary-license compliance. When adding a new skill, copy the root `LICENSE` into the new `skills/<new-skill>/LICENSE.txt` unchanged.

### Documentation Conventions

All Markdown files in this repository follow these rules (enforced by `markdownlint-cli2` per `.markdownlint.json`):

- ATX-style headings (`#`, `##`, `###`) -- no Setext-style underlines.
- All URLs wrapped as autolinks (`<https://example.com/>`) or Markdown links (`[text](https://example.com/)`) -- never bare URLs (MD034).
- All fenced code blocks declare a language (` ```bash `, ` ```python `, ` ```json `, ` ```text `) -- MD040.
- No emoji anywhere in committed files (project-wide policy).
- Underscores inside identifiers in headings or running prose must be wrapped in backticks (e.g. `` `place_*_order` ``) so markdownlint does not interpret them as emphasis (MD049).

## Adding a New Skill

1. Create the directory `skills/<new-skill>/`.
2. Write `SKILL.md` with the required frontmatter (see above).
3. Copy the root `LICENSE` to `skills/<new-skill>/LICENSE.txt` (byte-identical).
4. (Optional) Add `references/*.md` for progressive-disclosure documentation.
5. (Optional) Add `scripts/*.py` for executable helpers; each MUST implement `--self-test`.
6. Update `README.md` -- bump the "Available Skills (N)" count and add an entry.
7. Run `uv run pre-commit run --all-files` and `uv run pytest -v tests/`.
8. Open a Pull Request with `feat: add <new-skill> skill`.

## Branch Protection and PR Process

- All work is submitted via Pull Request; direct pushes to `main` are not permitted.
- CI (`Lint` workflow + `Test` workflow) must pass before merge.
- Squash-merge is the default merge strategy.
- The `release-please-action` workflow opens release Pull Requests automatically after merges to `main`; merging the release PR creates a tagged release.

## Reporting Issues

Use one of the [issue templates](.github/ISSUE_TEMPLATE/) when filing an issue:

- **Bug Report** -- unexpected behavior in a skill or script.
- **Feature Request** -- propose a new skill, reference, or improvement.
- **Documentation Issue** -- inaccurate, missing, unclear, or outdated docs (includes the `Quirk Verify-fixed signal` issue type for reporting that a server-side quirk has been fixed upstream).
- **Question** -- usage questions about the skills themselves. Questions about the **cTrader platform** (charts, accounts, broker behavior) belong in the [cTrader Help Centre](<https://help.ctrader.com/>), not this tracker.

## Security

To report a security vulnerability, follow the process in [SECURITY.md](SECURITY.md). Do **not** open a public GitHub issue for security disclosures.
