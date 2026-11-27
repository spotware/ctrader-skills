# Routing and output

## What selects the route

The list of modes that opens `ctrader-cli --help` has a batch-mode entry that names the commands with a batch route on your build: `periods`, `accounts`, `symbols`, `metadata`, `run` and `backtest`, and on some builds also `create`, `build` and `optimize`. Every other command (`account`, `account-stats`, `symbol`, `sessions`, `price`, `prices`, `candles`, `orders`, `order`, `positions`, `position`, `exposure`, `orders-history`, `deals`, `alerts`, `alert create`, `alert delete`, `indicators`, the `indicator` commands, `cbots` and `stop`) stands only in the interactive command list and always runs through the command shell. `ctrader-cli --commands` prints that command reference on its own, grouped by category, with no credentials, no network call and exit 0.

On `accounts`, `symbols` and `periods`, these options send the call to the interactive route: `--password`, `-q`, `--quick`, `--quit`, `--commands`, `--yes`, `-y`, `--all`, `--order`, `--position`, `--alert`, `--instance`, `--side`, `--volume`, `--volume-type`, `--sl`, `--tp`, `--stop-price`, `--limit-range`, `--indicator`, `--ind-params`, `--symbols`, `--condition`, `--message`, `--from`, `--to`, `--count`. The match ignores letter case. On `run` and `backtest` the same names can move the call to the interactive route. Without them, `--pwd-file`, `--broker` or no credential option keep `accounts`, `symbols`, `metadata`, `run` and `backtest` on the batch route.

A shell-routed call prints the banner first. The header line `[<time> <offset>] <command>` follows once the command runs, and is missing when the call stops before that, such as on a missing required option. On success the payload is camelCase JSON, except for a command whose row of the routing matrix says to read the result as printed; on failure it is a plain-text error line. Check the exit code before you parse, and treat a failed parse of a JSON payload as a failure.

## What the route changes

Moving a batch command to the interactive route changes four things at once:

1. A banner and a header line come before the payload.
2. The JSON casing changes from PascalCase (`Id`, `Number`, `Balance`) to camelCase (`traderLogin`, `balance`, `brokerName`).
3. The payload is wrapped under a key: batch `accounts` prints an array, and `accounts -q` prints `{"accounts": [...]}`.
4. The accepted options change. Batch `accounts` refuses `--account` with `Error: Parameter account is not allowed`, while `accounts -q` accepts it; batch `symbols` needs it.

Batch `symbols` returns `Id`, `Name` and `Description` per entry. `symbols -q` returns `name`, `description`, `category` and `assetClass` instead, with no id in any casing, so neither shape holds the other: use batch `symbols` when you need symbol ids.

## Routing matrix

| Command | Batch route | Call it | Payload |
| --- | --- | --- | --- |
| `periods` | yes, the only route | bare, with no options | the tokens on one line, as plain text; no credentials |
| `accounts` | yes | without `-q` | a PascalCase JSON array |
| `symbols` | yes | without `-q`, with `--account=<account>` | a PascalCase JSON array of `Id`, `Name`, `Description` |
| `metadata` | yes | without `-q`, the `.algo` path as the first argument | a PascalCase JSON object |
| `create` | where the mode list at the top of `--help` names it | named options `--kind=`, `--name=`, `--language=`; it can ask for credentials, depending on the build | a camelCase JSON object |
| `build` | where the mode list at the top of `--help` names it | `--project-path=<path>`; it can ask for credentials, depending on the build | a camelCase JSON object with a `success` flag, or exit 1 and an `Error:` line when the path does not resolve |
| `run` | yes | without `-q`, the `.algo` path first | the cBot's output until it stops |
| `backtest` | yes | without `-q`, the `.algo` path first | log lines, a parameter table and a summary; the `--report-json` file |
| `optimize` | where `--help` lists it | without `-q`, the `.algo` path first | the optimization result |
| `account`, `account-stats`, `symbol`, `sessions` | no | `-q`, named options | camelCase after the banner and the header |
| `price`, `prices`, `candles` | no | `-q`, `--symbol=` or `--symbols=` | camelCase after the banner and the header |
| `orders`, `positions` | no | `-q` | `{"orders": [...]}`, `{"positions": [...]}` |
| `order` | no | `-q`, `--order=<order-id>` | read the field names from the result |
| `position` | no | `-q`, `--position=<position-id>` | one entry of `positions`, without the array |
| `exposure` | no | `-q` | `{"exposures": [...]}`, a plural key for a singular command |
| `deals` | no | `-q`, with `--symbol=`, `--count=`, `--from=`, `--to=` | the `deals` array with `count`, plus `from` and `to` in the range form |
| `orders-history` | no | `-q`, with `--count=` or `--from=` and `--to=` | the array under `orders`: `requested`, `returned`, `lookbackDays` (and `available` when more exist) in the count form; `from`, `to`, `returned`, `available` in the range form |
| `alerts` | no | `-q` | `{"alerts": [...]}` |
| `indicators`, `indicator parameters`, `indicator calculate`, `indicator history` | no | `-q`, `--indicator="<title>"` | camelCase after the banner and the header |
| `cbots` | no | `-q` | read the result as printed |
| `stop` | no | `-q`, `--instance=<id>`, sent only as `references/algo-lifecycle.md` allows | read the result as printed |
| commands that change an order, a position or an alert | no | `-q`, added only after the user's authorization | a JSON object with the id and a `status` word |

`orders-history` has no symbol form: a `--symbol=` passed to it is left out, and the call returns every order.

Pass every argument of a shell-routed command as its named option at launch (`--symbol=<name>`, `--order=<order-id>`, `--indicator="<title>"`, `--count=<n>`); that form works on every build. Builds read a bare positional at launch differently, so never rely on one.

Use `-q` on shell-routed reads. Exit 0 alone never proves that the command you meant ran: confirm it from the header line and the payload.

## Output shapes

Standard output can hold more than the result. It takes one of these shapes:

- Log lines before and after the result, where a log line starts with a timestamp followed by `|` (`yyyy-MM-dd HH:mm:ss.ffff|INFO|...`), with the result printed twice, once as the message of a log line whose continuation lines carry no prefix and once as plain lines that a log record can split, and with other JSON in log records.
- A line that repeats the command, then the result.
- The result alone.

The result can stand at a different line from one run to the next. A build can print a line that repeats the command: on standard error, as the first line of standard output, or not at all, depending on the build and the command. It is never the result and never a sign of failure.

A batch result, shown here as one line, looks like this:

```json
[{"Id": <account-id>, "Number": <account>, "Broker": "<broker>", "Live": false, "DepositCurrency": "EUR", "Leverage": 100, "Balance": <balance>}]
```

A shell-routed call prints, in order:

1. A banner whose wording varies with the account state: `cTrader CLI`, `Connecting as <ctid>...`, `Logged in.`, `Using account: #<account> <broker> <currency> <balance> demo`, or `Using your only account: #<account> ...` when the cTrader ID has one linked account and `--account` was left out, and `Connected as <ctid> on #<account> ...`. `Connection failed ... Retrying` lines can come before the banner on an unsteady connection; read past them. The banner carries the cTrader ID, so redact it when you quote captured output.
2. A header line `[yyyy-MM-dd HH:mm:ss <offset>] <command>`. Its time and offset are the clock of the machine or container that runs the CLI; times inside the JSON are UTC with a `Z` suffix.
3. The payload: camelCase JSON, or the result as printed for a command whose row of the routing matrix says so.

## Finding the result

Find the result by content, never by position:

- For a command that returns JSON, search for a key only its result carries: `"Live":` for batch `accounts`, `"accounts":` for `accounts -q`, `"Description":` for batch `symbols`, `"Parameters":` for `metadata`, the wrapper key for a shell-routed list (`"orders":`, `"positions":`, `"exposures":`, `"alerts":`, `"symbols":`, `"deals":`), and for any other read a key its result carries. From a line that holds the key, go up to the nearest line, that line included, that starts with `[` or `{` in the first column, or that is a log line whose message (the text after its third `|`) starts with `[` or `{`. Read one JSON value from that bracket on, continuing over the following lines. It is the result when it parses and holds the key; otherwise go on to the next line that holds the key. JSON without the key, such as connection settings a log record prints, is never the result.
- When no line yields the result and the exit code is 0, a line, or the message of a log line, that is exactly `[]` is an empty result: `accounts --broker=<name>` with a name no account matches returns one.
- `periods` prints its tokens on one line: take the line that holds `m1` and `h1` as separate words and does not start with a timestamp; when no such line exists, the tokens are the message of a log line (the text after its third `|`).
- A message such as `Error: ...`, `Invalid ctid or password` or `Account cannot be found. ...` can stand anywhere: search for a line that starts with that text; the same text can also appear inside a log line.
- The output can run to thousands of lines: run the bundled script on the captured file, as the paragraph below shows, or search it (the Grep tool, or `grep -n`) and read only the lines around the match.
- For backtest figures, read the `--report-json` file, which holds standard JSON; the summary on standard output marks the end of the run. A backtest can also end with a non-zero exit code and no report file, with or without a summary.

The bundled script applies this rule to a capture. Run it with the interpreter and its path under the skill's folder, as `SKILL.md` shows: `python3 <skill folder>/scripts/extract_result.py --file=<path> --key=<name>` (`python` or `py` on Windows). It takes the capture as `--file=<path>` or as `--text=<captured text>`, in one of three modes:

- `--key=<name>` takes the bare key name, as in `--key=Live`, and prints `{"result": <value>, "line": <n>}`, the value and the line of its opening bracket. When no value holds the key and a line, or the message of a log line, is exactly `[]`, it prints `{"result": [], "line": <n>}`; that is an empty result only when the command exited 0, which the script is not given.
- `--periods` prints the tokens in the order printed, from the plain line when one exists and from the message of a log line otherwise.
- `--message=<text>` prints `{"text": <line>, "line": <n>}` for the first plain line that starts with the text, or else for the message of the first log line that starts with it.

The line numbers count from 1. When it finds nothing, the script writes `error: <reason>` on standard error, prints `{"error": <reason>}` and exits 4; a call it cannot read exits 2.

## Piped sessions

Blank and `#` lines are ignored; `q` leaves the shell. A session fed on standard input prints the banner and the command menu once, then for each command a prompt `>` with the header and the result; an ignored line prints only the prompt, and `q` prints `Bye.` and ends with exit 0.

```bash
printf 'accounts\nsymbols\nq\n' | timeout 60 ctrader-cli -e --account=<account> 1>out.txt 2>err.txt; echo "EXIT:$?"
```

A piped session is a shell session from start to end: each JSON result is camelCase and wrapped under its command's key, such as `{"accounts": [...]}`, even for `accounts` and `symbols`, which print PascalCase on the batch route. Find each result by the rule above.

## Casing and numbers

Casing follows the route, not the command:

- Batch `accounts` returns `Id`, `Number`, `Broker`, `Live`, `DepositCurrency`, `Leverage` and `Balance`. `accounts -q` returns `traderLogin`, `brokerName`, `depositCurrency`, `environment`, `isCurrent`, `balance`, `accountName`, `leverage`, `accountType`, `accessRights`, `accountStatus`, `isSwapFree`, `isLimitedRisk` and `traderId`. Its `environment` is a string, such as `demo`, and it has no `Live` key, so read whether an account is live from batch `accounts`.
- Batch `symbols` returns `Id`, `Name` and `Description`; `symbols -q` returns `name`, `description`, `category` and `assetClass`. On a typical account the list runs to hundreds of entries: filter it by name, or read one symbol with `symbol --symbol=<name>`.
- `backtest` prints its summary on standard output in PascalCase (`Equity`, `NetProfit`, `ProfitFactor`), while the file it writes for `--report-json` is camelCase (`main`, `equity`, `tradeStatistics`). `build` prints camelCase (`projectPath`, `success`, `errors`, `warnings`).

Numbers are plain JSON numbers with no locale-dependent separators. In the backtest summary on standard output, a value the run cannot compute prints as a bare `-`, which is not JSON: read it as no value. `ProfitFactor` can print `-` when the run has no losing trade, and `AverageTrade` and `ProfitFactor` both when it has no trade. Take the figures from the `--report-json` file, which can hold a number where the summary prints `-`. A run that ends in an error can print a key with no value at all, such as `"Equity":,`, and write no report.

Line endings are CRLF on Windows; split captured output so that a trailing `\r` does not stay on a line.
