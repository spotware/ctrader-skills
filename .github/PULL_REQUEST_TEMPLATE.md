# Pull Request

<!--
Title hint: use a Conventional Commits prefix in the PR title, e.g.
  feat: add <new-skill> skill
  fix: correct precision rounding in price-pip-decimals
  docs: clarify SKILL.md frontmatter rules
  chore: bump dev dependencies
  ci:   adjust release-please configuration
  test: extend pytest harness for skill scripts
See <https://www.conventionalcommits.org/> for the full specification.
-->

## Summary

<!-- Briefly describe the change and the motivation behind it. -->

## Related Issues

<!-- Link any issues this PR addresses. Use "Closes #<number>" to auto-close on merge. -->

Closes #

## Type of Change

<!-- Tick all that apply. -->

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to change)
- [ ] Documentation update
- [ ] CI/CD configuration change
- [ ] Other (please describe):

## Checklist

- [ ] I have followed the contribution guidelines in `CONTRIBUTING.md`.
- [ ] Tests pass locally (`uv run pytest`).
- [ ] `uv run pre-commit run --all-files` passes.
- [ ] New skill scripts include a `--self-test` flag (if applicable).
- [ ] Documentation has been updated (if applicable).
- [ ] My commit messages follow the Conventional Commits specification.
