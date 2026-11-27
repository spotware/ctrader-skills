# Security policy

## Reporting a vulnerability

If you discover a security vulnerability in the cTrader skills, do not open a public GitHub issue. Report it privately through one of these channels:

- **GitHub Security Advisories** (preferred): [Report a vulnerability](<https://github.com/spotware/ctrader-skills/security/advisories/new>).
- **Email**: send the report to `support@ctrader.com` with the subject line `Security report: ctrader-skills`.

We acknowledge receipt within 5 business days and give an estimated remediation timeline after triage.

## Scope

This policy covers the contents of the [`spotware/ctrader-skills`](<https://github.com/spotware/ctrader-skills>) repository: the skills with their references and scripts, the Claude Code plugin and marketplace manifests, and the install script.

Vulnerabilities in cTrader platform components, including the cTrader MCP servers, the cTrader CLI, cTrader Desktop, the cTrader mobile apps and the cTrader web platform, are out of scope for this repository. Report those through the official cTrader support channel at [spotware.com](<https://www.spotware.com/>).

## Supported versions

Only the latest release, the content of the `main` branch, receives security updates. [CHANGELOG.md](CHANGELOG.md) lists the releases.

## Disclosure policy

We follow coordinated disclosure. Once a fix is available, we agree on a public disclosure timeline with the reporter, typically 30 to 90 days. We credit reporters in the changelog unless they prefer to stay anonymous.
