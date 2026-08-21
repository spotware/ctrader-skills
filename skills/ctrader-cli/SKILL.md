---
name: ctrader-cli
description: Use this skill whenever you drive the cTrader CLI executable (ctrader-cli.exe) from a shell - querying accounts, symbols, prices, candles, orders, positions, deals or exposure; placing, modifying or cancelling orders; managing price alerts; scaffolding, building, backtesting or running cBots and indicators.
allowed-tools: "Read, Grep, Glob, Bash(ctrader-cli.exe *), Bash(timeout 30 ctrader-cli.exe *), Bash(timeout 60 ctrader-cli.exe *), Bash(timeout 240 ctrader-cli.exe *), Bash(ctrader-cli *), Bash(timeout 30 ctrader-cli *), Bash(timeout 60 ctrader-cli *), Bash(timeout 240 ctrader-cli *), Bash(command -v *), Bash(printenv *)"
compatibility: "Requires the cTrader CLI on any OS: Windows installs it with `winget install Spotware.cTrader.CLI` (executable ctrader-cli.exe); macOS and Linux install it with Homebrew from the Spotware tap (executable ctrader-cli). Command shapes are written for bash (Git Bash on Windows or any POSIX shell) using the Windows executable name; on macOS and Linux drop the .exe suffix."
license: Proprietary. LICENSE.txt has complete terms.
metadata:
  author: "Spotware Systems Ltd"
  cli_build_observed: "5.9.0.38"
  last_full_audit_date: "2026-08-03"
---

## Overview

The cTrader CLI is a headless client for the cTrader platform: accounts and symbols, market data, orders and positions, history, price alerts, and the full cBot lifecycle, all without the desktop UI.

It offers two invocation pipelines, and choosing the right one is the single most valuable thing to internalize. **Batch** verbs return compact machine-readable payloads for scripting. **Shell-routed** verbs run through the interactive command shell, which reaches a much larger command surface and returns a richer payload. The same verb can be served by either pipeline, and the pipeline you land in determines the JSON casing, the payload wrapper, and which flags are accepted. Everything below exists to make that choice deliberate rather than accidental.

The CLI runs natively on every platform. On Windows it installs with `winget install Spotware.cTrader.CLI` as `ctrader-cli.exe`; on macOS and Linux it installs from the Spotware Homebrew tap (`brew tap spotware/tap https://github.com/spotware/homebrew-tap`, then `brew install spotware/tap/ctrader-cli`) as `ctrader-cli` — the same CLI with identical verbs, flags, and environment variables. Command shapes throughout this skill use the Windows executable name; on macOS or Linux drop the `.exe` suffix and everything else carries over unchanged (`references/setup.md` covers the per-OS credential setup).

Behavior described here matches build `5.9.0.38`; re-confirm details that matter on a newer build.

## Invocation discipline

Use this template for every call, adjusting only the timeout:

```bash
timeout 30 ctrader-cli.exe <verb> [flags] -e </dev/null 1>out.txt 2>err.txt; echo "EXIT:$?"
```

Each element earns its place:

- `timeout` bounds every call. Use 30 seconds for data commands and 240 for `build`, `backtest`, and `run`.
- `</dev/null` guarantees termination. With stdin redirected the process never waits for a prompt; it completes the requested work, reaches end of stream, and exits.
- Separate `1>` and `2>` captures, with **unique file names per invocation**, keep the payload away from the command echo. Concurrent sessions on a shared machine can otherwise clobber fixed names.
- Read `$?` directly. A pipe reports the exit status of the last stage, so piping into `head` or `grep` discards the CLI's own code.

Budget roughly 1.5 to 2 seconds of process start-up per call. When you need several read-only results, fold them into one process through piped stdin, which amortizes that cost:

```bash
printf 'accounts\nsymbols\nq\n' | timeout 60 ctrader-cli.exe -e --account=<n>
```

Two commands run in 4.1 to 4.4 seconds this way versus 5.1 to 5.8 seconds as separate calls. Blank lines and lines beginning with `#` are ignored, so a piped script may carry comments. Note that a piped session is a shell session: its output arrives in **shell-routed shape** (camelCase, wrapped objects), not batch shape.

On Windows, bash consumes backslashes in unquoted arguments, so always double-quote Windows paths: `--report-json="C:\reports\run.json"`.

## Routing: batch verbs and shell-routed verbs

Six verbs have a genuine batch code path: `periods`, `accounts`, `symbols`, `metadata`, `run`, `backtest` — the six that `--help` itself names for BATCH mode. `create` and `build` appear in `--help`'s BATCH MODE reference section, but they execute through the command shell in every invocation shape — banner first, then a camelCase JSON payload, and without `-q` a fall-through into the interactive menu — so call them with `-q`. Everything else is reached only through the command shell.

`-q` / `--quick` is a **routing flag**, not a quiet flag. Adding it to one of the six batch verbs moves the whole invocation into the shell pipeline, which changes the payload casing, wraps it under a command-name key, prepends a banner and a timestamp header, and can change which flags are accepted.

| Verb class | Call it | Payload |
| ------------ | --------- | --------- |
| Batch data (`accounts`, `symbols`, `metadata`) | **without** `-q` | PascalCase JSON, no banner |
| Batch streaming (`run`, `backtest`) | **without** `-q` | `backtest`: plain-text progress log, then a final compact PascalCase JSON summary; `run`: streams the algo's output until stopped |
| Scaffolding (`create`, `build`) | **with** `-q` | camelCase JSON after the banner and timestamp header |
| Shell-routed (`account`, `account-stats`, `symbol`, `sessions`, `price`, `prices`, `candles`, `orders`, `positions`, `order`, `position`, `exposure`, `orders-history`, `deals`, `alerts`, `alert`, `indicators`, `indicator`) | **with** `-q` | camelCase wrapped under the command name, after a banner |
| `periods` | bare, **no flags at all** | plain text, no credentials needed |

Concrete consequences worth knowing before your first call:

- `accounts -e` does not accept `--account`; `symbols -e` requires it. The two batch verbs differ deliberately.
- Batch `symbols` returns `Id`, `Name`, `Description` per entry. The same verb with `-q` returns `name`, `description`, `category`, `assetClass` — it swaps the numeric `Id` for classification fields rather than extending the batch schema, so use batch `symbols` whenever you need symbol ids.
- `periods` takes no flags whatsoever; passing `-e` to it returns `Error: Parameter e is not allowed`.
- Shell-routed verbs take their arguments as explicit flags at launch time. `symbol --symbol=EURUSD` works; a bare `EURUSD` positional does not.
- `-q` is recommended rather than required for shell-routed reads: it skips the command menu that otherwise prints after the payload, keeping stdout minimal for parsing. Without it the call still terminates cleanly under redirected stdin, printing the menu once and then `Bye.` at exit 0.
- An unrecognized verb routes to the shell menu and exits 0 under closed stdin, so never treat "exit 0" alone as proof the verb you intended actually ran.

`ctrader-cli.exe --commands` prints the full shell command reference, needs no credentials and no network, and is the zero-cost way to confirm a verb's exact argument forms.

## Credentials

Two credential shapes work non-interactively. Prefer the first, which keeps secrets out of the process arguments entirely.

```bash
# Environment-variable credentials: CTID and PWD-FILE are set in the environment.
timeout 30 ctrader-cli.exe accounts -e </dev/null

# Explicit credentials.
timeout 30 ctrader-cli.exe accounts --ctid="<id>" --pwd-file="<path>" </dev/null
```

The mapping rule for `-e` is exact: an environment variable is consulted only when its name matches the long option name verbatim, hyphens preserved, compared case-insensitively, and only when `-e` is on the command line. So `CTID`, `PWD-FILE`, and `ACCOUNT` are read; `account` also works; `PWD_FILE` with an underscore is not consulted, and `ACCOUNT_ID` yields `Error: Option account does not exist`. An explicit flag always wins over the matching variable. `--environment-variables` is the long form of `-e`.

`--ctid` identifies the user (the cTrader ID, an email address) in every path; the trading account is selected separately with `--account`. The password file's first line is the password. `--pwd-file` is the flag name; there is no short alias. `--password` belongs to interactive use and should not appear in a scripted invocation.

Never read or print the value of `CTID` or `PWD-FILE`. Check presence and length only, and remember that `PWD-FILE` contains a hyphen, so `$PWD-FILE` does not interpolate it:

```bash
val="$(printenv 'PWD-FILE')"; echo "PWD-FILE length: ${#val}"
```

The shell banner prints the cTrader ID on stdout as `Connecting as <id>...`. Redact it when quoting captured output into reports or anything shared.

## Reading the output

Locate the payload structurally, never by a fixed line count or byte offset. Scan for the timestamp header line or the first balanced `{` or `[`; transient connection-retry lines can precede a payload that still arrives successfully.

Batch payloads begin at byte zero: no banner, no header, flat PascalCase JSON. Shell-routed payloads carry a banner of several lines whose wording varies, then a header line of the form `[yyyy-MM-dd HH:mm:ss <local numeric offset>]` echoing the command, then camelCase JSON wrapped under the command name such as `{"orders": [...]}`. That header is local wall-clock time with the machine's own zone offset, which is distinct from timestamps inside the JSON body: those are UTC with a `Z` suffix.

Casing therefore follows the pipeline, not the verb. `accounts` returns `Id` and `Balance`; `orders` returns `id` and `volumeLots`. `backtest` is worth singling out: its compact stdout summary is PascalCase (`Equity`, `NetProfit`) while the file it writes for `--report-json` is camelCase (`main`, `equity`, `tradeStatistics`). `build` takes no report flags; its stdout payload is camelCase (`projectPath`, `success`, `errors`).

Stderr carries the CLI's own echo of the command line on batch-routed calls, on success as well as failure, so its mere presence never signals an error. Shell-routed calls typically leave stderr empty. Because of that split, treat stderr as a hint about which pipeline you reached, and never as a pass/fail signal.

Plain-text rather than JSON output comes from `periods`, `--help`, `--commands`, `--version`, confirmation and refusal messages, and not-found messages such as `Order #N not found.`. The timestamp-header rule applies to shell-routed JSON commands only.

Line endings are CRLF on Windows. Numbers are plain JSON numbers, already rounded by the CLI's own formatting, with no locale-dependent separators; the one exception is a zero-trade backtest summary, which renders `AverageTrade` and `ProfitFactor` as a bare `-` token that strict JSON parsers reject.

## Exit codes and failure detection

| Code | Meaning |
| ------ | --------- |
| 0 | Success |
| 1 | Invalid usage, unrecognized flag, missing required parameter, or a validation error |
| 81 | Invalid cTrader ID or password |
| 82 | Account cannot be found |
| 124 | The external `timeout` ended the process |

Message text is the primary detection signal and the exit code is the branch key. Nonzero codes outside this table exist for further error conditions but are not publicly documented, so read the message rather than assuming a numbered meaning. A wrapper shell can report a different code than a direct invocation, so prefer the message when the two disagree.

Never infer failure from the exit code alone. `build` exits 0 for a successful compile **and** for a failed one: the JSON body's `success` boolean is the authoritative signal, with diagnostics in `errors: [{file, line, column, code, text}]`. `backtest` continues running after printing its summary, so the completion signal is the final JSON summary or the `--report-json` file appearing; a 124 with those artifacts present is a completed run, not a failure.

A non-numeric value for a numeric flag exits 1, but the message shape depends on the flag and the pipeline: `candles --count=abc` returns a clean `Error: Option --count has invalid number: abc` line on stdout, `--account=abc` on batch-routed `symbols` surfaces a `System.FormatException` trace, and `--account=abc` on shell-routed verbs such as `orders` prints `Invalid account number: 'abc'. Expected a numeric login id.` on stderr with no `Error:` prefix. No single stream or prefix covers this class, so validate numeric flag values before invoking.

## Mutating commands

The state-changing verbs are `order place-market`, `order place-limit`, `order place-stop`, `order place-stop-limit`, `order modify`, `order cancel`, `position close`, `position close-partial`, `position modify`, `alert create`, `alert delete`, and `stop`.

**Authorization gate.** On a mutating verb, `-q` *is* the confirmation: it answers the confirmation prompt automatically and the command executes. Because `-q` is also the routine flag for shell-routed reads, it is easy to carry over by habit. Add `-q` to a mutating command only after the user has explicitly authorized that specific action, and only after you have confirmed the target account is a demo account by checking that `accounts` reports `"Live": false`. Never run a mutating command to discover how it behaves.

At a flag-style launch line, `-q` is the confirmation form that applies. `--yes` and `-y` return `Refused: confirmation required` and exit 1. A trailing bare `yes` is shell-prompt syntax; mixing it into a flag-style line ends the process with a `ConsoleInvalidUsageException` usage trace at exit 1. The `all` keyword likewise belongs to the shell prompt; `--help` documents a separate `--all` launch flag — verify it before relying on it.

**Volume is expressed in units by default.** On EURUSD, `--volume=1000` with no `--volume-type`, `--volume=1000 --volume-type=units`, and `--volume=0.01 --volume-type=lots` all resolve to the identical stored order of `volume: 1000, volumeLots: 0.01`. Read the instrument's own limits first with `symbol --symbol=<name>`, which returns `lotSize`, `minVolume`, `maxVolume`, `volumeStep`, `digits`, and `pipSize`.

**Stop loss and take profit are three-state on modify.** A value replaces, `0` removes, and omitting the flag preserves the current value. Supply prices as absolute values. A price on the wrong side of the reference is rejected before submission with a two-line `Warning:` then `Error:` message at exit 1, leaving server state untouched.

Use the exact flag names `--order=<id>`, `--position=<id>`, and `--alert=<id>`. Response keys differ per command: `order place-limit` returns `orderId` with `status: "placed"` (pending placements share this shape; expect `positionId` with `status: "opened"` from a market order that fills immediately), `alert create` returns `id` with `status: "created"`, and `alert delete` returns `alertId` with `status: "deleted"`. Read the key that the command you called returns.

After every mutation, re-read the affected entity with `orders`, `positions`, or `orders-history` and confirm the applied state before reporting success.

## Session preflight

Before the first authenticated call, run the four-step preflight in `references/setup.md`: executable reachability, presence-and-length-only checks of `CTID` and `PWD-FILE`, password-file sanity, and a single go/no-go probe with `accounts -e`. The three outcomes are exit 0 with a JSON account array (ready), exit 81 (credentials rejected), and exit 1 with a missing-parameter message (a fast, clear failure, never a hang). That reference also carries the exact wording to give a user whose configuration needs fixing.

## Reference files

- `references/setup.md` - the preflight sequence and the user-facing setup instructions for each failure mode.
- `references/routing-and-output.md` - the full routing matrix, payload anatomy, and parsing recipes.
- `references/commands.md` - per-verb flags and payload shapes for the read-only surface.
- `references/trading-write.md` - the guarded mutation sequence, volume and protection semantics, and response shapes.
- `references/algo-lifecycle.md` - create, build, metadata, backtest, and run for cBots and indicators.
- `references/errors-and-exit-codes.md` - the failure table, message shapes, and recovery actions.
