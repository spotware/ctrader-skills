---
name: ctrader-cli
description: "Use this skill whenever you drive the cTrader CLI (`ctrader-cli`; `ctrader-cli.exe` on Windows; also its container image) from a shell: listing accounts and symbols; reading prices, candles, sessions, orders, positions, deals, order history and exposure; placing market, limit, stop and stop-limit orders, modifying or cancelling them, and closing positions; creating and deleting price alerts; calculating indicator values; scaffolding cBots, indicators and plugins; building, backtesting, optimizing, running, listing and stopping cBots."
allowed-tools: "Read, Grep, Glob, Bash(ctrader-cli.exe *), Bash(timeout 30 ctrader-cli.exe *), Bash(timeout 60 ctrader-cli.exe *), Bash(timeout 240 ctrader-cli.exe *), Bash(ctrader-cli *), Bash(timeout 30 ctrader-cli *), Bash(timeout 60 ctrader-cli *), Bash(timeout 240 ctrader-cli *), Bash(command -v *), Bash(python3 *extract_result.py*), Bash(python *extract_result.py*), Bash(py *extract_result.py*)"
compatibility: "Requires the cTrader CLI, installed with winget or as the copy bundled with the cTrader desktop application on Windows, from the Homebrew tap on macOS and Linux, or as the container image on any OS with Docker. Commands are written as ctrader-cli; on Windows the executable is ctrader-cli.exe. scripts/extract_result.py needs Python 3.11 or newer and the standard library only, run as python3 (macOS, Linux) or python or py (Windows); the written rule it implements works without Python."
license: Proprietary. LICENSE.txt has complete terms.
metadata:
  author: "Spotware Systems Ltd"
---

## Overview

The cTrader CLI is a headless client for the cTrader platform: accounts and symbols, market data, orders and positions, history, price alerts, and the cBot lifecycle, all without the desktop application.

It reaches its commands by two routes. Batch commands return a payload for scripting. Shell-routed commands run through the interactive command shell, which reaches the full command set. The route a call lands on decides the JSON casing, the payload wrapper and the options the call accepts, so choose it on purpose.

On Windows the CLI installs with `winget install Spotware.cTrader.CLI`, and the cTrader desktop application ships a copy of its own. On macOS and Linux it installs from the Spotware Homebrew tap. A container image runs it on any OS with Docker. `references/setup.md` covers each route.

This skill writes the executable as `ctrader-cli`. On Windows the executable is `ctrader-cli.exe`: type that name where `ctrader-cli` stands.

`ctrader-cli --version` prints the build; `--help` lists the options and `--commands` the commands that build accepts. Builds differ in their options and in some commands; where this skill and `--help` differ, follow `--help`.

## Invocation discipline

Use this template for every call except `periods`, `metadata`, `orders-history` and `deals`, adjusting only the timeout as the first rule below says:

```bash
timeout 30 ctrader-cli <command> [options] -e </dev/null 1>out.txt 2>err.txt; echo "EXIT:$?"
```

- `timeout` bounds every call but `run`. Use 30 seconds for data commands and 240 for `build` and `backtest`. For `optimize`, where `--help` lists it, agree the time limit with the user before the run: each pass runs a backtest, so an optimization takes longer the more passes it runs. `run` takes a `timeout` only when the user names how long the cBot is to work, because `run` blocks until the cBot exits or its process is ended, and a time limit around it ends the cBot's run when it expires.
- `</dev/null` guarantees termination: with standard input redirected, the process never waits for a prompt.
- Separate `1>` and `2>` captures, with a unique file name per call, keep the two streams apart. Concurrent sessions on one machine can otherwise overwrite fixed names.
- Read `$?` directly. A pipe reports the exit status of its last stage, so piping into `head` or `grep` loses the CLI's own code.

A build can print a line that repeats the command: on standard error, as the first line of standard output, or not at all, depending on the build and the command. It is never the result and never a sign of failure.

`periods` and `metadata` take no `-e`: both answer it with `Error: Parameter e is not allowed` and exit 1. Call them as `ctrader-cli periods` and `ctrader-cli metadata "<algo>"`; neither needs credentials. Called with `--ctid`, `--pwd-file` and `--account` and no route option, `periods` refuses them: it answers `Error: Parameter <name> is not allowed`, names each refused option, and exits 1.

`orders-history` and `deals` use the session form that `references/commands.md` describes instead of this template: the same command sent three times on standard input of one shell session, and the last result read.

On Windows, bash consumes backslashes in unquoted arguments, so always double-quote Windows paths: `--report-json="C:\reports\run.json"`.

## Choosing the route

| Commands | Call them | Payload |
| --- | --- | --- |
| `accounts`, `symbols`, `metadata` | without `-q` | PascalCase JSON |
| `run`, `backtest`, and `optimize` where `--help` lists it | without `-q` | text; `references/algo-lifecycle.md` describes each |
| `periods` | bare, with no options | the period tokens as plain text |
| `create`, `build` | with their named options | a camelCase JSON object |
| `account`, `account-stats`, `symbol`, `sessions`, `price`, `prices`, `candles`, `orders`, `order`, `positions`, `position`, `exposure`, `alerts`, `indicators`, `indicator`, and every command that changes an order, a position or an alert | with `-q` | camelCase JSON after a banner and a header |
| `orders-history`, `deals` | in one shell session, as `references/commands.md` describes | camelCase JSON after a banner, one result per command sent, each after its header |
| `cbots`, `stop` | with `-q` | the result as printed; `references/algo-lifecycle.md` describes both |

Options such as `-q`, `--quick`, `--yes` or `--count` send `accounts`, `symbols` and `periods` to the interactive route; `references/routing-and-output.md` lists them all, with the payload of each route.

`alerts` lists the alerts; `alert create` and `alert delete` change them. No command reads a single alert.

`ctrader-cli --commands` prints the full shell command reference, with the positional form of every argument, and needs no credentials and no network. The named options of a launch line are in `ctrader-cli --help`.

## Finding the result

Standard output can hold more than the result: log lines before and after it, a line that repeats the command, a banner and a header, and the result printed twice. The result can stand at a different line from one run to the next. Find it by content, never by position: search for a key only the result carries, such as `"Live":` for batch `accounts`, and read the JSON value that holds it. `references/routing-and-output.md` gives the full rule for every shape.

The bundled script `scripts/extract_result.py` applies that rule to a captured file. Its path is relative to the skill's own folder, the one that holds this file:

```bash
python3 <skill folder>/scripts/extract_result.py --file=out.txt --key=Live
python <skill folder>/scripts/extract_result.py --file=out.txt --key=Live
```

Use `python3` on macOS and Linux and `python` on Windows, or `py` where `python` is not on `PATH`. `--key=<name>` prints `{"result": <value>, "line": <n>}`. `--last`, given with `--key`, prints the last value that holds the key instead of the first, as for the last of several results of one command in a shell session. `--periods` prints the period tokens, and `--message=<text>` prints the first line that starts with the text, such as `Error:`. When no JSON value holds the key and a line is exactly `[]`, the script prints that empty result; it is an empty result only when the command exited 0. When it finds nothing, it prints `{"error": <reason>}` and exits 4. `--help` lists the options, and `--self-test` checks the script on the interpreter at hand. Without Python, apply the written rule.

Backtest figures come from the `--report-json` file. The summary on standard output can print a bare `-` where it has no value.

## Credentials

Two credential forms work without prompts. Prefer the first, which keeps the credentials out of the process arguments.

```bash
# CTID and PWD-FILE are set in the environment.
timeout 30 ctrader-cli accounts -e </dev/null

# Explicit credentials.
timeout 30 ctrader-cli accounts --ctid="<ctid>" --pwd-file="<path>" </dev/null
```

With `-e` (long form `--environment-variables`), an environment variable supplies an option when its name equals the long option name, hyphens kept, in any letter case: `CTID`, `PWD-FILE` and `ACCOUNT` are read. A name with an underscore in place of the hyphen is not read. An option on the command line wins over the matching variable.

In the container image, pass the credentials as options after the image name, with the password file mounted: `--ctid=<ctid> --pwd-file=<path inside the container>`. `references/setup.md` shows the full command.

`--ctid` identifies the user by the cTrader ID or email the user signs in with; `--account` selects the trading account. When batch `accounts` lists more than one account and the user has not named the account to use, ask the user which one before the first command that takes `--account`, and use that account until the user names another. The first line of the password file is the password, and `--pwd-file` has no short alias. `--password` belongs to interactive use and has no place in a scripted call.

Never read or print the value of `CTID` or `PWD-FILE`; check presence and length only. A POSIX shell cannot expand a hyphenated name with `$`, so read it with `printenv`:

```bash
val="$(printenv 'PWD-FILE')"; echo "PWD-FILE length: ${#val}"
```

The shell banner prints the cTrader ID on standard output as `Connecting as <ctid>...`. Redact it when you quote captured output.

## State-changing commands

These commands change state: `order place-market`, `order place-limit`, `order place-stop`, `order place-stop-limit`, `order modify`, `order cancel`, `position close`, `position close-partial`, `position modify`, `alert create`, `alert delete`, `run` and `stop`.

Send them only to an account that batch `accounts` reports as `"Live": false`, and only after the user has authorized that exact action. `-q`, `--quick`, `--quit`, `--yes`, `-y` and `--all=true` can each let a command run without asking, so add them only after that authorization. Write `--all=true` to target every order, position, alert or instance: a bare `--all` is ignored and the command fails asking for one id, as `order cancel` and `position close` do with exit 1, changing nothing. Never add a trailing `yes` or the positional `all` on a launch line: builds read them differently, and they can end the command with exit 1 or confirm it.

Start `run` only when the user asks for that run. The cTrader CLI documentation asks that an AI agent not start `run` on its own: a running cBot acts on the account until it stops. Stopping an instance you started at the user's request is cleanup; any other `stop`, and `stop --all=true`, needs the user's authorization.

Before the run, agree with the user how long the cBot is to work and how it ends: until the user asks to stop it, started without `timeout` and stopped with `stop --instance=<id>`; for a time the user names, under a `timeout` of that length; or until the cBot stops itself, started with `--exit-on-stop` and without `timeout`. This skill pre-approves `timeout` only at 30, 60 and 240 seconds, so a call with another length can wait for the user's approval. `references/algo-lifecycle.md` describes each.

Before the first order, position or alert command of a session, read `references/trading-write.md` when this session has not read it yet. It holds the steps below in full, with the order types, the volume units, the protection levels and alerts.

With `-q`, a command skips an option it does not recognize, without a message, and runs with the options it recognizes: an order placed with `--stoploss=` instead of `--sl=` opens without a stop loss. Nothing in the output shows the dropped option, so check the line before it runs and read the entity back after:

1. Run `ctrader-cli --help` before the first state-changing command of the session, and `ctrader-cli --commands` with it: `--help` prints the named options of your build and `--commands` its command words. Build the command from those words and options, spelled exactly as printed.
2. Check each option against the options `--help` printed: name, hyphens, letter case. Correct or remove any option that listing does not hold before the command runs. For `run`, check each `--<PropertyName>=` override against the `PropertyName` values `metadata` reports instead, case kept.
3. Put `--account=<account>` on the line, with the number of the account the user named or chose, whose batch `accounts` entry you have just read as `"Live": false`. When the user has named no account and more than one entry reads `"Live": false`, ask the user which account to use and never choose among them. Never run a state-changing command without `--account`.
4. Read the instrument with `symbol --symbol=<name>` and the state you are about to change with `orders`, `positions` or `alerts`. Before a placement that is the list the new order or position will join, so that the read-back shows what the command added. Before `order place-market`, when `positions` shows an open position of the symbol on the other side, read `accountType` with `account`. Write down the values you expect afterwards.
5. Before each state-changing command, tell the user what it does and on which account: for every command, the account by its `Number` and `Broker` in batch `accounts`; for a placement the symbol, side, volume, prices and levels, and what the user asked for that the CLI cannot set (`references/trading-write.md`, "What the CLI sets on an order"); for a modify, what it sets and what it keeps; for a cancel or a close, which order or position it is: an order by symbol, side and price, a position by symbol, side and entry price; for a delete or a stop, which alert or instance; for a stop, also that the positions the cBot opened stay open; for `run`, the cBot, its parameters, and how long it works and how it ends. Do it also when the user's message already authorized the exact action and nothing is asked again. For an order with a stop loss or a take profit, say there that a level which does not apply is set to the authorized value at once; for an `order place-market` against such a position on an account whose `accountType` is not `Hedged`, say there instead that the levels go back to the user after the read-back.
6. After the command, find the line that names the account (`Using account: #<account> ...` or `Using your only account: #<account> ...`) and check that it shows the number you passed. The line can be missing, as on a command that ends in invalid usage; read back all the same. Batch `run` prints no such line: check the number in its line `Login to <account>...`, or in the `--account=` value of the line that repeats the command where the build prints one, and confirm the account when the instance shows in the `cbots --account=<account>` read of step 7.
7. Read the entity back on the same account and compare every value you set with what you wrote down. After `run`, read `cbots` from a second call while the run is going, and after `stop`, read `cbots` again: `references/algo-lifecycle.md` describes both. After `stop`, also read `positions` on the account and report the positions still open.
8. When a stop loss or take profit the user authorized did not apply, set exactly that level at once with the matching modify command and tell the user, with the read-back before and after. After an `order place-market` against an open position of the same symbol on the other side, on an account whose `accountType` is not `Hedged`, set no level at once: report what `positions` shows, and when a position of the symbol remains, ask the user which levels it is to carry. Any other difference waits for the user: report it and change nothing. Never repeat the original command: it would open a second order or position.

## Exit codes

Read the exit code directly, then the message. Exit 0 alone never proves that the command you meant ran. `references/errors-and-exit-codes.md` lists the codes, the message shapes and the recovery for each.

## Session preflight

Before the first authenticated call in a session, and whenever an authenticated call fails in a way that looks related to credentials rather than to usage, run the four-step preflight in `references/setup.md`: the executable answers, `CTID` and `PWD-FILE` are present (length only), the password file has a first line, and one `accounts` call answers. Its outcomes are exit 0 with the account list, whose entries carry `"Live":` (ready); exit 81 with `Invalid ctid or password` (credentials rejected); and exit 1 with a message that names the missing option or file. That reference also carries the wording for a user whose setup needs fixing.

## Reference files

| Task | File |
| --- | --- |
| Installing per OS and per route, credentials, the preflight, wording for a user whose setup needs fixing | `references/setup.md` |
| Which route a call takes, output shapes, finding the result, piped sessions | `references/routing-and-output.md` |
| Exit codes, message shapes and recovery, except `build`, `backtest` and `optimize` results | `references/errors-and-exit-codes.md` |
| Every read command, its options and its result | `references/commands.md` |
| Orders, positions and alerts that change state; checks before and after | `references/trading-write.md` |
| `create`, `build`, `metadata`, `backtest`, `optimize`, `run`, `cbots`, `stop`, and judging build, backtest and optimization results | `references/algo-lifecycle.md` |
| Finding the result in a captured standard output | `scripts/extract_result.py` |
