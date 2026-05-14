# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in cTrader Skills, please **do not** open a public GitHub issue. Instead, report it privately via one of the following channels:

- **GitHub Security Advisories** (preferred): [Report a vulnerability](<https://github.com/spotware/ctrader-skills/security/advisories/new>).
- **Email**: send the report to `support@ctrader.com` with the subject line `Security report: ctrader-skills`.

We will acknowledge receipt within 5 business days and provide an estimated remediation timeline after triage.

## Scope

This security policy covers:

- The contents of the [`spotware/ctrader-skills`](<https://github.com/spotware/ctrader-skills>) repository (skill manifests, references, scripts, configuration, CI workflows).
- The published Claude Code plugin and the `npx skills` package distribution that ship from this repository.

Vulnerabilities in **cTrader platform components** -- including the Local HTTP MCP server, the Remote HTTP MCP server, the REST proxy, cTrader Desktop, cTrader iOS / Android apps, and the cTrader.com web platform -- are out of scope for this repository. Report those through the official cTrader support channel at [spotware.com](<https://www.spotware.com/>).

## Supported Versions

Only the **latest released version** of `ctrader-skills`, as listed on the [GitHub Releases](<https://github.com/spotware/ctrader-skills/releases>) page, receives security updates.

## Disclosure Policy

We follow coordinated disclosure. After a fix is available, we will work with the reporter to determine an appropriate public disclosure timeline -- typically 30 to 90 days. Credit will be given to reporters in the release notes unless they prefer anonymity.
