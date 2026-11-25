# Contributing to cTrader Skills

Thanks for your interest in improving cTrader Skills. This guide explains how Spotware publishes this repository, how to report an issue, and how to propose a change. By participating in this project you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

## How Spotware Publishes This Repository

Spotware develops the skills outside this repository and publishes each release here. Each release is one commit on `main`, tagged `v<version>`, and `main` changes only at a release. [CHANGELOG.md](CHANGELOG.md) lists what each release changed.

`npx skills`, the Claude Code marketplace and `install.sh` all read `main`, so a new installation always receives the latest release.

## Repository Layout

Each skill lives in its own folder under `skills/` and follows the [Agent Skills specification](<https://skills.sh>):

```text
skills/<skill-name>/
  SKILL.md           # the skill: YAML frontmatter and instructions
  LICENSE.txt        # the license, the same text as the root LICENSE
  references/*.md    # reference files the skill reads when it needs them
  scripts/*.py       # helper scripts, each with a --self-test flag
```

Skill installers copy only the skill folder, so every skill carries its own copy of the license. The `.claude-plugin/` folder holds the Claude Code plugin and marketplace manifests, and `install.sh` installs the skills for Claude Code or Deep Agents CLI.

## Reporting Issues

Use one of the [issue templates](.github/ISSUE_TEMPLATE/) when filing an issue:

- **Bug Report**: unexpected behavior of a skill or a bundled script.
- **Feature Request**: a new skill, reference, or improvement.
- **Documentation Issue**: inaccurate, missing, unclear, or outdated documentation.
- **Question**: how to use the skills. Questions about the **cTrader platform** itself (charts, accounts, broker behavior) belong in the [cTrader Help Centre](<https://help.ctrader.com/>).

## Proposing a Change

Open an issue that describes the change and the reason for it. For a change to a skill or a script, quote the passage it concerns or paste the text you propose.

You can also open a pull request to show the change in full. A release replaces the content of `main`, so Spotware does not merge pull requests. When Spotware accepts a change, it ships the change in the next release, credits the contributor in the changelog entry of that release, and closes the pull request with a link to that release. A pull request that Spotware does not accept is closed with the reason.

Before you propose a change to a script, run its self-test with Python 3.11 or newer, as `python3` on macOS and Linux and as `python` on Windows:

```bash
python3 skills/ctrader-mcp-servers/scripts/pip_math.py --self-test
python skills/ctrader-mcp-servers/scripts/pip_math.py --self-test
```

Every script under `skills/*/scripts/` takes `--self-test`, runs its built-in checks, and exits with status 0 when they pass.

## Security

To report a security vulnerability, follow the process in [SECURITY.md](SECURITY.md). Do **not** open a public GitHub issue for security disclosures.
