# cTrader Skills

> [!WARNING]
> This project is in early development. APIs, skill content, and conventions may change.

Agent skills for working with the [cTrader](<https://ctrader.com/>) platform by [Spotware Systems Ltd](<https://www.spotware.com/>). These skills give AI coding agents the operational knowledge needed to drive cTrader MCP servers correctly: server-by-server semantics, units and encoding conventions, end-to-end trader workflows, a build-stamped reference of runtime behaviors per server, and named operational patterns for safe multi-step server interactions.

## Prerequisites

The skill bundles five Python helper scripts under [`skills/ctrader-mcp-servers/scripts/`](skills/ctrader-mcp-servers/scripts/) that the AI agent invokes via `python <script>` for precision-critical calculations (pip math, position sizing, conversion-rate chains, tiered-margin computation, units encoding). These scripts use only the Python standard library -- no third-party packages required.

- **Python 3.12 or newer** must be installed and available on `PATH` (verify with `python --version`).
- If your system does not have Python 3.12+, install it from <https://www.python.org/downloads/> or use your OS package manager:
  - macOS: `brew install python@3.12`
  - Ubuntu/Debian: `sudo apt install python3.12`
  - Windows: `winget install Python.Python.3.12` or download from python.org
- [`uv`](<https://docs.astral.sh/uv/>) is **NOT required** to run the skill itself. It is recommended only for contributors to this repository (see [CONTRIBUTING.md](CONTRIBUTING.md)).

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

After installation, run your coding agent from the directory where you installed (for local installs) or from anywhere (for global installs). The agent will discover the skills automatically and apply them whenever you work with a cTrader MCP server.

The skills themselves do not require any API keys. For cTrader account setup, MCP server installation, and platform documentation, see the [cTrader Help Centre](<https://help.ctrader.com/>).

## Available Skills (1)

- **ctrader-mcp-servers** -- Always use when working with any cTrader MCP server. Covers Local HTTP server semantics, Remote HTTP server semantics, units and encoding conventions, end-to-end trader workflows, the build-stamped runtime-behavior reference, and named operational patterns the agent applies on every call. Bundles five executable helper scripts (pip math, position sizing, conversion rate, tiered margin, units encoding) that the agent invokes for precision-critical calculations.

## License

This software is proprietary to Spotware Systems Ltd. and forms part of the cTrader platform. Use is governed by the [Spotware End User License Agreement](<https://www.spotware.com/eula/>).

See [LICENSE](LICENSE) and [COPYRIGHT.md](COPYRIGHT.md) for full terms.

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for the development setup, conventional commit convention, skill authoring guide, and PR workflow. By participating, you agree to abide by the [Code of Conduct](CODE_OF_CONDUCT.md).

## Security

To report a security vulnerability, please follow the process in [SECURITY.md](SECURITY.md). Do **not** open a public GitHub issue for security reports.

---

cTrader is a registered trademark of Spotware Systems Ltd.
