# Routing and Output

The pipeline a call lands in — batch or shell-routed — determines the payload casing, the wrapper key, and the accepted flag set. Below: the authoritative verb-by-verb routing matrix, the exact payload anatomy of each pipeline, an extraction recipe that holds up against banner variance, and the piped-stdin technique for folding several read-only calls into one process.

## The batch verb list, authoritative

`ctrader-cli.exe --help` carries a dedicated `BATCH MODE` section that is the primary source for which verbs have a genuine non-interactive code path. Its intro names six: `periods`, `accounts`, `symbols`, `metadata`, `run`, `backtest`. Two more verbs, `create` and `build`, are listed in the same section, but they execute through the command shell in every invocation shape; call them with `-q` (see the matrix below). Every other verb — including `account`, `account-stats`, `symbol`, `sessions`, `price`, `prices`, `candles`, `orders`, `order`, `positions`, `position`, `exposure`, `orders-history`, `deals`, `alerts`, `alert`, `indicators`, `indicator` — is absent from that section and appears only under the interactive command list, which means it is shell-routed by design rather than by an accidental flag combination. `ctrader-cli.exe --commands` prints that same interactive command reference on its own, grouped by category, at zero cost: no credentials, no network call, and a clean exit 0.

Two verb families are worth distinguishing carefully because they are easy to conflate:

- **Dual-mode verbs** (`accounts`, `symbols`, `periods`, and by the same BATCH MODE listing `metadata`, `run`, `backtest`) have a real batch code path and can also be pushed into the shell pipeline by adding `-q`. These are the verbs where "routing" is a live choice you make per call. `create` and `build` are not dual-mode despite their BATCH MODE listing: they route through the command shell in every invocation shape.
- **Shell-only verbs** (everything else) have no batch code path at all. Flags cannot select a batch shape for them because none exists; every invocation routes to the shell pipeline regardless of what you pass. The banner always appears; the `[timestamp] <command>` header appears once the command actually executes (it is absent when a pre-execution validation error fires, such as a missing required flag); and the payload is camelCase JSON on success but plain-text error lines on failure — so never JSON-parse shell-routed stdout unconditionally; check the exit code first, or treat a JSON parse failure as the error signal.

## What rerouting actually changes

Adding `-q` to a dual-mode batch verb does not just suppress a prompt. It moves the entire invocation onto a different code path, and that one flag changes four things simultaneously:

1. **A banner and header appear.** Batch output starts at byte zero with `[` or `{`; shell-routed output is preceded by login lines and a `[timestamp] <command>` echo line.
2. **JSON casing flips.** Batch payloads are flat PascalCase (`Id`, `Number`, `Balance`); shell-routed payloads are camelCase (`traderLogin`, `balance`, `brokerName`).
3. **The payload gets wrapped.** Batch `accounts` returns a bare array; shell-routed `accounts -q` wraps the same concept under a command-name key: `{"accounts": [...]}`.
4. **The accepted flag set can change.** Batch `accounts` rejects `--account` outright (`Error: Parameter account is not allowed`); the same verb shell-routed via `-q` accepts `--account` to preselect an account. Batch `symbols` returns only `Id`, `Name`, `Description` per entry; shell-routed `symbols -q` swaps the schema rather than extending it — it gains `category` and `assetClass` but drops the numeric `Id` entirely, so neither shape is a superset of the other, and an agent that needs symbol ids must use the batch form.

`periods` is the sharpest illustration of consequence four: its batch form takes zero flags, and passing even `-e` to it is itself a validation error (`Error: Parameter e is not allowed`). Passing `-q` to `periods` reroutes it into the shell, where it then demands credentials it never needed in batch form (`Missing --ctid in non-interactive mode.` when `-e` is also absent), and even with `-e -q` supplied it prints the full interactive menu rather than period data, because "periods" does not match any interactive command title.

## The complete routing matrix

| Verb | Batch code path exists | Call it | Payload shape |
| ------ | ------------------------ | --------- | --------------- |
| `periods` | yes, and it is the only route | bare, no flags at all | plain text, space-separated tokens, no credentials |
| `accounts` | yes | without `-q` | flat PascalCase JSON array |
| `symbols` | yes | without `-q`, with `--account=<n>` | flat PascalCase JSON array, `Id`/`Name`/`Description` only |
| `metadata` | yes | without `-q`, positional `.algo` path | PascalCase JSON object (`Name`, `Type`, `AccessRights`, `BuildTime`, plus a nested `Parameters` array whose entries carry `PropertyName`, `FriendlyName`, `Type`, `DefaultValue`) |
| `create` | no — listed under BATCH MODE, but it routes through the command shell and requires full account authentication | `create cbot --name=<name> -e -q` (a positional name at launch is not parsed and drops into the interactive menu) | banner + header, then a camelCase JSON object (`{kind, name, language, projectPath, projectFile, mainFile, expectedAlgoFile, status}`) |
| `build` | no — same BATCH MODE listing, same shell routing and authentication | `build --project-path=<path> -e -q` | banner + header, then a camelCase JSON object (`{projectPath, success, errorCode, errors, warnings}`); exit 0 on success and failure alike — read the `success` boolean |
| `run` | yes | without `-q` | plain-text streamed cBot output until the bot exits or the process is terminated; no final JSON summary — confirm the exact output shape on first use |
| `backtest` | yes | without `-q` | plain-text progress log plus a final compact PascalCase JSON summary; `--report-json` file is camelCase |
| `account`, `account-stats`, `symbol`, `sessions` | no | `-q` recommended | camelCase, banner + header, wrapped or bare object depending on verb |
| `price`, `prices`, `candles` | no | `-q` recommended, named `--symbol=`/`--symbols=` flag required | camelCase, banner + header |
| `orders`, `positions` | no | `-q` recommended | camelCase, wrapped under the command name (`{"orders": [...]}`, `{"positions": [...]}`) |
| `order`, `position` | no | `-q` recommended, `--order=`/`--position=` flag required | camelCase, bare unwrapped object for a known id (same field set as one array element from the list form) |
| `exposure` | no | `-q` recommended | camelCase, wrapped under the plural key `exposures` even though the command is singular (`{"exposures": [...]}`) — an agent must not assume the wrapper key mirrors the command name |
| `deals` | no | `-q` recommended, `--symbol=`/`--count=`/`--from=`/`--to=` flags | camelCase envelope: the array under `deals` plus `count`, with `from`/`to` echo keys in range form |
| `orders-history` | no | `-q` recommended, `--count=` or `--from=`/`--to=` flags only — no symbol form exists, and a `--symbol=` passed anyway is silently discarded (exit 0, results unfiltered) | camelCase envelope with the array under `orders`, not the command name: `{requested, returned, lookbackDays, orders}` in count form (plus `available` when results were truncated), `{from, to, returned, available, orders}` in range form |
| `alerts`, `alert` | no | `-q` recommended | camelCase, `{"alerts": [...]}` or the single-entity response |
| `indicators`, `indicator parameters` | no | `-q` recommended | camelCase |

For most "no batch code path" rows, the bare positional form that would feel natural (`price EURUSD`, `order 312753167`) drops into the interactive shell and fails with a message that names the fix — `price`, `symbol`, `order`, `alert`, and `indicator parameters` all fail this way, for example: `'symbol' is required. Provide it as a positional argument inside the shell, or pass --symbol=<value> when launching the command.` The named flag form at launch time is the one that works outside the live REPL. A few rows diverge from that failure pattern and exit 0 instead: `account <n>` appears to accept its bare positional, but the number is silently discarded and the payload is the default account's — a bogus number returns the same output — while `deals` and `orders-history` silently drop a trailing positional (`deals 50` returns the same payload as bare `deals`; `orders-history 50` returns the default `"requested": 100`). Exit 0 on those rows never proves the positional was applied; pass the named flags at launch instead.

`-q` is recommended rather than mandatory for these shell-only reads: a call without `-q` but with stdin redirected from `/dev/null` still terminates cleanly. It runs the requested command, falls through to the interactive menu once, hits end of stream, prints `Bye.`, and exits 0. The only cost of omitting `-q` here is the noise of that trailing menu dump landing in your captured stdout; `-q` skips the menu entirely and keeps stdout minimal for parsing.

An unrecognized verb token follows the same fall-through path: it does not produce an invalid-usage error, it silently routes to the interactive menu and exits 0 once stdin closes. Exit 0 on its own is therefore never proof that the verb you intended actually ran; confirm from the payload shape or the header echo line, not from the exit code alone.

## Batch payload anatomy

A true batch call has no preamble of any kind. Stdout begins at byte zero with the JSON structure itself:

```json
[{"Id":47246474,"Number":5816091,"Broker":"Spotware","Live":false,"DepositCurrency":"EUR","Leverage":100,"Balance":1000.0}]
```

There is no timestamp header line, no banner, no trailing menu. Stderr, in this pipeline, carries exactly one thing: the CLI's own echo of the invoked command line, present on success and on failure alike, for example `ctrader-cli.exe accounts -e`. That echo's presence is itself a signal that you reached the batch pipeline, not a diagnostic to react to.

## Shell-routed payload anatomy

A shell-routed call carries four layers in this order, and the exact wording of the first layer is not fixed:

1. **Banner and login lines.** Wording varies by account state: `Connecting as <id>...`, `Logged in`, `Using account: #5816091 Spotware EUR 1000 demo`, or, when the cTID has exactly one linked account and `--account` was omitted, `Using your only account: #5816091 Spotware EUR 1000 demo`. `Connected as <id>...` can also appear. Transient `Connection failed ... Retrying` lines may precede the banner on a flaky connection; treat any such line as wording variance to scan past, not as a signal about payload success. Redact the cTrader ID (shown here as an email/login, distinct from the account number that follows it in the same sentence) when quoting captured banner text into a report or any shared artifact.
2. **A timestamp header line**, of the form `[yyyy-MM-dd HH:mm:ss <local numeric offset>]` followed by the command as invoked, for example `[2026-08-03 16:12:44 +03:00] price EURUSD`. This is local wall-clock time carrying the machine's own zone offset; it is not the format used for timestamps inside the JSON body, which are UTC with a `Z` suffix (`2026-07-01T21:00:00.000Z`). Treat the header as machine-local and the body's timestamps as UTC; do not assume they share an epoch reference.
3. **The camelCase JSON payload**, wrapped under a key that matches the command name, for example `{"orders": [...]}`, `{"accounts": [...]}`, `{"alerts": []}`. A handful of single-entity shell-routed commands (`account`, `symbol --symbol=<name>`, `order --order=<id>`, `position --position=<id>`) return the object bare rather than wrapped, and `exposure` wraps under the plural key `exposures` rather than the singular verb name, while `orders-history` wraps its array under `orders` — the same key the `orders` command uses — inside a count-based or range-based envelope, so discriminate a history payload from an open-orders payload by the envelope keys or the header echo line, never by the wrapper key alone. Check the verb's own documented shape rather than assuming the wrapper key mirrors the command name.
4. **The interactive menu and `Bye.`**, present only when `-q` was omitted. This is a full listing of every interactive command and exits the process at end of stdin; it is not an error state and should simply be excluded from parsing, which `-q` avoids by not printing it at all.

Because banner wording varies and can include retry lines, never locate the payload by a fixed line count or byte offset. Scan structurally instead.

## A robust payload-extraction recipe

Locate the payload by content, not position, so that banner wording variance, retry lines, or an unexpectedly long login sequence never break the extraction:

```bash
timeout 30 ctrader-cli.exe orders -e -q --account=<n> </dev/null 1>out.txt 2>err.txt
echo "EXIT:$?"
```

Then extract with one of these approaches, in order of preference:

- **Batch payloads:** the file already is the payload; parse it directly as JSON from byte zero.
- **Shell-routed payloads:** find the first line that starts with `{` or `[` and treat everything from there to the matching closing brace or bracket as the JSON body. In practice the timestamp header line is the reliable anchor: the payload begins on the next non-blank line after the `[yyyy-MM-dd HH:mm:ss <offset>] <command>` line.

```bash
awk '/^\[[0-9]{4}-[0-9]{2}-[0-9]{2} /{found=1; next} found && NF{print; exit}' out.txt
```

That prints the first non-blank line after the header, which is where the JSON body starts; feed the remainder of the file from that point into your JSON parser rather than assuming a fixed number of preceding lines. Never assume the banner is a fixed number of lines: it varies with account count, connection retries, and which login-state messages the CLI chose to print for that session.

## The piped-stdin multi-command technique

Every fresh process costs roughly 1.5 to 2 seconds of start-up. When you need several shell-capable reads in the same turn, fold them into a single process by piping multiple command lines to one launch instead of paying that start-up cost per call:

```bash
printf 'accounts\nsymbols\nq\n' | timeout 60 ctrader-cli.exe -e --account=<n>
```

This authenticates once, then runs each line as a command in turn, and `q` ends the session cleanly. Two commands folded into one piped session complete in 4.1 to 4.4 seconds, versus 5.1 to 5.8 seconds for the same two commands issued as separate cold-start batch calls — a saving of roughly 1.0 to 1.7 seconds (20 to 25 percent) for the second command, consistent with the stated per-process start-up budget. Blank lines and lines beginning with `#` inside the piped script are ignored, so a multi-line script can carry comments for readability.

The shell-shape caveat is the detail most worth internalizing: a piped session is a shell session end to end. Its output arrives in shell-routed shape — one banner and login sequence at the top, then camelCase JSON wrapped under each command's own key, one payload per line you fed in — never in batch PascalCase, even for verbs like `accounts` and `symbols` that would be flat PascalCase if called individually without `-q`. Parse every payload from a piped session as camelCase and expect the command-name wrapper, and expect exactly one banner regardless of how many commands you folded in, not one banner per command.

## Casing and field-shape differences worth checking before you parse

Casing follows the pipeline, not the verb, so the same conceptual field can appear under two different names depending on how you called it:

- Batch `accounts` returns `Id`, `Number`, `Broker`, `Live`, `DepositCurrency`, `Leverage`, `Balance`. Shell-routed `accounts -q` returns `traderLogin`, `brokerName`, `depositCurrency`, `environment`, `isCurrent`, `balance`, `accountName`, `leverage`, `accountType`, `accessRights`, `accountStatus`, `isSwapFree`, `isLimitedRisk`, `traderId` — more fields, not just renamed ones.
- Batch `symbols` returns `Id`, `Name`, `Description` per entry — hundreds of entries, tens of kilobytes, on a typical broker. Shell-routed `symbols -q` swaps the field set per entry — `name`, `description`, `category`, `assetClass`, with no id field in any casing — and is correspondingly larger; the numeric `Id` exists only in the batch shape. Filter by name or use the single-symbol detail command rather than loading the full array into context.
- `backtest` is the one verb where the split runs the other direction within a single call: its own compact stdout summary prints PascalCase (`Equity`, `NetProfit`, `ProfitFactor`), while the file it writes for `--report-json` is camelCase (`main`, `equity`, `tradeStatistics`). Read whichever one you need directly; do not assume the two share a casing convention just because they come from the same invocation. `build` has no report flags at all, and its stdout JSON (`projectPath`, `success`, `errors`, `warnings`) is camelCase.

Numbers throughout are plain JSON numbers with no locale-dependent thousands separators — shell-routed payloads arrive already rounded by the CLI's own formatting (money to 2 decimal places, pips to 1, ratios and percentages to 2) — with one exception: a backtest that closes zero trades renders `AverageTrade` and `ProfitFactor` in its compact stdout summary as a bare unquoted `-` token, which is not valid strict JSON; special-case that token before parsing. Line endings on Windows are CRLF; account for that when splitting captured output into lines.
