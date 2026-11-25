# cTrader Skills

> [!WARNING]
> This project is in early development. APIs, skill content, and conventions may change.

Agent skills for working with the [cTrader](<https://ctrader.com/>) platform by [Spotware Systems Ltd](<https://www.spotware.com/>). These skills give AI coding agents the operational knowledge needed to drive the cTrader MCP servers and the cTrader CLI correctly: how to tell the Remote and the Local MCP server apart, the units each server uses, the checks before and after every order-changing call, recipes for common trading tasks, and the CLI's routes, output and exit codes.

## Prerequisites

Both skills bundle Python helper scripts. `ctrader-mcp-servers` bundles five under [`skills/ctrader-mcp-servers/scripts/`](skills/ctrader-mcp-servers/scripts/) for precision-critical calculations (pip math, position sizing, conversion-rate chains, tiered-margin computation, units encoding). `ctrader-cli` bundles one under [`skills/ctrader-cli/scripts/`](skills/ctrader-cli/scripts/) that finds the result in the captured output of a cTrader CLI command; the written rule it implements works without Python. The AI agent invokes a script as `python3 <script>` on macOS and Linux and as `python <script>` on Windows, or `py <script>` where `python` is not on `PATH`. These scripts use only the Python standard library, so they need no third-party packages.

- **Python 3.11 or newer** must be installed and available on `PATH` (verify with `python3 --version` on macOS and Linux, or `python --version` on Windows).
- If your system does not have Python 3.11+, install it from <https://www.python.org/downloads/> or use your OS package manager:
  - macOS: `brew install python@3.12`
  - Debian and Ubuntu: `sudo apt install python3` installs the distribution's Python 3. Use it when `python3 --version` reports 3.11 or newer; otherwise install Python from python.org.
  - Windows: `winget install Python.Python.3.12` or download from python.org

The AI agent invokes the bundled scripts on your behalf; you do not need to run them by hand.

## Supported Coding Agents

These skills can be installed via [`npx skills`](<https://github.com/vercel-labs/skills>) for any agent that supports the [Agent Skills specification](<https://skills.sh>), including Claude Code, Cursor, Windsurf, Codex, Cline, and OpenCode. A native Claude Code plugin installation is also provided.

## Installation

### Quick Install (recommended for any agent)

Using [`npx skills`](<https://github.com/vercel-labs/skills>):

**Local** (current project):

```bash
npx skills add spotware/ctrader-skills --skill '*' --yes
```

**Global** (all projects):

```bash
npx skills add spotware/ctrader-skills --skill '*' --yes --global
```

To link skills to a specific agent (e.g. Claude Code):

```bash
npx skills add spotware/ctrader-skills --agent claude-code --skill '*' --yes --global
```

---

### Claude Code Plugin

Install directly as a [Claude Code plugin](<https://code.claude.com/docs/en/plugins>):

```bash
/plugin marketplace add spotware/ctrader-skills
/plugin install ctrader-skills@ctrader-skills
```

---

### Install Script (Claude Code & Deep Agents CLI, optional)

Alternatively, clone the repository and use the bundled install script:

```bash
# Install for Claude Code in current directory (default)
./install.sh

# Install for Claude Code in a specific project directory
./install.sh ~/my-project

# Install for Claude Code globally
./install.sh --global

# Install for Deep Agents CLI in a specific project directory
./install.sh --deepagents ~/my-project

# Install for Deep Agents CLI globally
./install.sh --deepagents --global
```

| Flag / Argument | Description |
| --------------- | ----------- |
| `DIRECTORY` | Target project directory (default: current directory, ignored with `--global`) |
| `--claude` | Install for Claude Code (default) |
| `--deepagents` | Install for Deep Agents CLI |
| `--global`, `-g` | Install globally instead of current directory |
| `--force`, `-f` | Overwrite skills with same names as this package |
| `--yes`, `-y` | Skip confirmation prompts |

## Usage

After installation, run your coding agent from the directory where you installed (for local installs) or from anywhere (for global installs). The agent will discover the skills automatically and apply them whenever you work with a cTrader MCP server or the cTrader CLI.

The skills themselves do not require any API keys. For cTrader account setup, MCP server installation, and platform documentation, see the [cTrader Help Centre](<https://help.ctrader.com/>).

## Available Skills (2)

- **ctrader-cli**: Use whenever driving the cTrader CLI (`ctrader-cli`; `ctrader-cli.exe` on Windows; also its container image) from a shell. Covers each install route, the batch and shell routes and how the choice changes the payload casing and the accepted options, environment-variable credentials that keep secrets out of the command line, how to find a command's result in its output, exit codes and messages for failure detection, the read commands with their field names, a guarded sequence for state-changing commands, and the cBot loop from `create`, `build` and `metadata` to `backtest`, `optimize`, `run` and `stop`. Includes a session preflight the agent runs before its first authenticated call, with the wording for a user whose setup needs fixing, and one helper script that finds the result in captured output.
- **ctrader-mcp-servers**: Use whenever working with a cTrader MCP server, Remote or Local. Covers how to tell the two servers apart, the units each one uses, account and market data reads, placing, changing and closing trades with checks before and after every order-changing call, recipes for common trading tasks, the Local server's charts, indicators, drawings, watchlists, price alerts, workspaces and cBots, and the trading math. Bundles five helper scripts (pip math, position sizing, conversion rate, tiered margin, units encoding) that the agent invokes for precision-critical calculations.

## Releases

Each release is one commit on `main`, tagged `v<version>`, and `main` changes only at a release. [CHANGELOG.md](CHANGELOG.md) lists what each release changed.

## License

This software is proprietary to Spotware Systems Ltd. and forms part of the cTrader platform. Use is governed by the [Spotware End User License Agreement](<https://www.spotware.com/eula/>).

See [LICENSE](LICENSE) and [COPYRIGHT.md](COPYRIGHT.md) for full terms.

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for how Spotware publishes this repository, how to report an issue, and how to propose a change. By participating, you agree to abide by the [Code of Conduct](CODE_OF_CONDUCT.md).

## Security

To report a security vulnerability, please follow the process in [SECURITY.md](SECURITY.md). Do **not** open a public GitHub issue for security reports.

---

cTrader is a registered trademark of Spotware Systems Ltd.
