# cTrader skills for AI agents

Agent skills for [cTrader](<https://ctrader.com/>) by [Spotware Systems Ltd](<https://www.spotware.com/>). The skills give your AI agent the knowledge it needs to drive the cTrader MCP servers and the cTrader CLI: how to tell the Remote and the Local MCP server apart, the units each server uses, the checks before and after every order-changing call, recipes for common trading tasks, and the routes, output and exit codes of the CLI.

The skills hold instructions and helper scripts only. They do not set up a server or the CLI, so connect your agent to the Remote or the Local cTrader MCP server, or install the cTrader CLI, before you use them.

## Prerequisites

Both skills bundle Python helper scripts. `ctrader-mcp-servers` bundles five under [`skills/ctrader-mcp-servers/scripts/`](skills/ctrader-mcp-servers/scripts/) for precision-critical calculations (pip math, position sizing, conversion-rate chains, tiered-margin computation, units encoding). `ctrader-cli` bundles one under [`skills/ctrader-cli/scripts/`](skills/ctrader-cli/scripts/) that finds the result in the captured output of a cTrader CLI command; the written rule it implements works without Python. The AI agent invokes a script as `python3 <script>` on macOS and Linux and as `python <script>` on Windows, or `py <script>` where `python` is not on `PATH`. These scripts use only the Python standard library, so they need no third-party packages.

- **Python 3.11 or newer** must be installed and available on `PATH` (verify with `python3 --version` on macOS and Linux, or `python --version` on Windows).
- If your system does not have Python 3.11+, install it from <https://www.python.org/downloads/> or use your OS package manager:
  - macOS: `brew install python@3.12`
  - Debian and Ubuntu: `sudo apt install python3` installs the distribution's Python 3. Use it when `python3 --version` reports 3.11 or newer; otherwise install Python from python.org.
  - Windows: `winget install Python.Python.3.12` or download from python.org
- **Node.js** for the `npx skills` installation below. The [skills CLI](<https://github.com/vercel-labs/skills>) states the Node.js version it requires.

The AI agent invokes the bundled scripts on your behalf. You do not need to run them by hand.

## Supported agents

The skills follow the [Agent Skills](<https://agentskills.io/>) format. You can install them with [`npx skills`](<https://github.com/vercel-labs/skills>) in any agent it supports, including Claude Code, Cursor, Windsurf, Codex, Cline and OpenCode. Claude Code can also install them as a plugin.

## Install

### Agents that read Agent Skills

Install with [`npx skills`](<https://github.com/vercel-labs/skills>) for the current project:

```bash
npx skills add spotware/ctrader-skills --skill '*' --yes
```

For all projects:

```bash
npx skills add spotware/ctrader-skills --skill '*' --yes --global
```

To install for one agent only, name it with `--agent`, for example Claude Code:

```bash
npx skills add spotware/ctrader-skills --agent claude-code --skill '*' --yes --global
```

### Claude Code

Install the skills as a [Claude Code plugin](<https://code.claude.com/docs/en/plugins>):

```bash
claude plugin marketplace add spotware/ctrader-skills
claude plugin install ctrader-skills@ctrader-skills
```

### Install script (Claude Code and Deep Agents Code)

Clone the repository and run the bundled install script:

```bash
# Install for Claude Code in current directory (default)
./install.sh

# Install for Claude Code in a specific project directory
./install.sh ~/my-project

# Install for Claude Code globally
./install.sh --global

# Install for Deep Agents Code in a specific project directory
./install.sh --deepagents ~/my-project

# Install for Deep Agents Code globally
./install.sh --deepagents --global
```

| Flag / Argument | Description |
| --------------- | ----------- |
| `DIRECTORY` | Target project directory (default: current directory, ignored with `--global`) |
| `--claude` | Install for Claude Code (default) |
| `--deepagents` | Install for Deep Agents Code |
| `--global`, `-g` | Install globally instead of current directory |
| `--force`, `-f` | Overwrite skills with same names as this package |
| `--yes`, `-y` | Skip confirmation prompts |

## Usage

After the installation, start your agent in the directory where you installed the skills, or in any directory after a global installation. The agent finds the skills and applies them when you work with a cTrader MCP server or the cTrader CLI.

For Deep Agents Code, `install.sh --deepagents --global` installs the skills for the default agent, in `~/.deepagents/agent/skills/`, so a `dcode` run finds them. After an installation in a project directory, an agent of any name that you start inside that project finds the skills when that directory is the root of a git repository, which is where Deep Agents Code looks for a project's skills.

The skills need no API key. The MCP servers and the cTrader CLI connect to your cTrader account as the cTrader Help Centre describes.

## Skills

- **ctrader-cli**: Use whenever driving the cTrader CLI (`ctrader-cli`, or `ctrader-cli.exe` on Windows, and its container image) from a shell. Covers each install route, the batch and shell routes and how the choice changes the payload casing and the accepted options, environment-variable credentials that keep secrets out of the command line, how to find a command's result in its output, exit codes and messages for failure detection, the read commands with their field names, a guarded sequence for state-changing commands, and the cBot loop from `create`, `build` and `metadata` to `backtest`, `optimize`, `run` and `stop`. Includes a session preflight the agent runs before its first authenticated call, with the wording for a user whose setup needs fixing, and one helper script that finds the result in captured output.
- **ctrader-mcp-servers**: Use whenever working with a cTrader MCP server, Remote or Local. Covers how to tell the two servers apart, the units each one uses, account and market data reads, placing, changing and closing trades with checks before and after every order-changing call, recipes for common trading tasks, the Local server's charts, indicators, drawings, watchlists, price alerts, workspaces and cBots, and the trading math. Bundles five helper scripts (pip math, position sizing, conversion rate, tiered margin, units encoding) that the agent invokes for precision-critical calculations.

## Learn more

For cTrader accounts, the cTrader MCP servers and these skills, see [cTrader MCP servers](<https://help.ctrader.com/ctrader-ai-agent-connect/>) and [Skills for cTrader MCP servers](<https://help.ctrader.com/ctrader-ai-agent-connect/skills/>) in the cTrader Help Centre.

## Support

The [Troubleshoot](<https://help.ctrader.com/ctrader/miscellaneous/troubleshoot/>) page of the cTrader Help Centre lists the support channels.

## Releases

Each release is one commit on `main`, tagged `v<version>`, and `main` changes only at a release. The [tags](<https://github.com/spotware/ctrader-skills/tags>) list the releases, and [CHANGELOG.md](CHANGELOG.md) lists what each release changed.

## Contributing

Issues and pull requests are welcome as proposals. See [CONTRIBUTING.md](CONTRIBUTING.md) for how Spotware publishes this repository, how to report an issue, and how to propose a change. By participating, you agree to abide by the [Code of Conduct](CODE_OF_CONDUCT.md).

## Disclaimer

The cTrader MCP servers and the cTrader CLI are tools for AI-assisted trading and do not provide financial, investment, legal or tax advice. AI-generated actions may trigger real trades and result in losses. You are solely responsible for verifying outputs, supervising strategies, securing credentials and using these skills at your own risk.

## License

These skills are proprietary to Spotware Systems Ltd and form part of the cTrader platform. The [Spotware End User License Agreement](<https://www.spotware.com/eula/>) governs their use. See [LICENSE](LICENSE) and [COPYRIGHT.md](COPYRIGHT.md) for the full terms.

## Security

To report a security vulnerability, follow [SECURITY.md](SECURITY.md). Do not open a public issue for a security report.

---

cTrader is a registered trademark of Spotware Systems Ltd.
