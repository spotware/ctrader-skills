# Errors and Exit Codes

This is the failure reference for the cTrader CLI: the exit-code table, the distinct message shapes and the stream each arrives on, and the recovery action for each class. Treat the table as a branch key and the message text as the signal you actually act on -- the two are complementary, not interchangeable.

## Exit-code table

| Code | Meaning | Recovery action |
| ------ | --------- | ------------------ |
| 0 | Success | Proceed; a success payload never contains the substring `Error:` |
| 1 | Invalid usage, unrecognized flag, missing required parameter, file not found, an interactive-path validation error, or a pre-routing parse error | Read the printed usage block or the specific validation message and correct the argument; do not retry unchanged |
| 81 | Invalid cTrader ID or password, exact message `Invalid ctid or password` | Re-check the `CTID` value and the `PWD-FILE` path and content; do not retry with the same credentials |
| 82 | Account cannot be found, exact message `Account cannot be found. Use accounts command to list all trading accounts linked to cTrader ID` | Call `accounts` to enumerate the cTrader ID's linked account numbers, then retry with a valid one |
| 124 | The external `timeout` ended the process | Check for a completion signal that already arrived (see the `backtest` section below) before treating this as a failure; on `build`, which exits on its own once the compile finishes, a 124 means the timeout expired before completion — raise the timeout and retry |

Do not expect a distinct nonzero code for an unknown symbol, an unknown period, or an empty data window. `candles` reaches its validation through the interactive pipeline, where invalid symbol and invalid period land on exit 1 with a specific message (see the worked examples below), while an out-of-range date window returns exit 0 with an empty `bars: []` array rather than a distinct "no data" code. For any nonzero exit code not listed in the table, branch on the message text using the message shapes below, not on the number; the CLI's `--help` and `--commands` output documents no exit codes.

## The stream-echo rule

Whether stderr carries a one-line echo of the reconstructed command line is a function of which pipeline the call reached, not of success or failure:

- A call that reaches the batch pipeline (`accounts`, `symbols`, `periods`, and the other batch verbs) always prints that echo to stderr, on exit 0 as well as on exit 1, 81, or 82 -- for example `ctrader-cli.exe accounts -e` produces a 29-byte stderr echo on a successful run, and the same shape of echo appears on an unknown-account exit 82.
- A call that lands in the interactive pipeline never prints that echo, regardless of its own exit code. Both a successful `candles` call and a `candles` call that fails validation leave stderr empty.
- A pre-routing parse failure -- the parser rejects the arguments before a pipeline is even chosen -- also leaves stderr empty. An empty `--pwd-file=` value, for instance, produces the stdout message `Unable to determine destination for argument value: --pwd-file=` at exit 1 with zero stderr bytes.

Use stderr's content, not its mere presence, as the cheap diagnostic for which pipeline you reached: a stderr line that reproduces the invocation's argv means the call reached the batch pipeline (`--version` also echoes its argv this way, though it short-circuits before any pipeline routing); empty stderr means either a pre-routing parse failure or a landing in the interactive pipeline, and the stdout content (an `Error:` line versus the interactive banner and menu) tells you which; any other non-empty stderr content comes from a non-batch path — a quick-mode credential error such as `Missing --ctid in non-interactive mode.`, or the unhandled exception trace of the message shapes below.

## Five message shapes

Five distinct message shapes cover the failure surface. Distinguish them by which stream carries the text and whether the command-line echo is present, not by exit code alone.

**Batch-pipeline `Error:` with stderr echo.** The call reached the batch pipeline, and validation failed there. Stdout carries a message beginning `Error:`, often followed by a full usage block; stderr carries the one-line command echo.

```text
$ ctrader-cli.exe accounts --this-flag-does-not-exist=1 -e </dev/null
stdout: Error: Parameter this-flag-does-not-exist is not allowed
        [usage block follows]
stderr: ctrader-cli.exe accounts --this-flag-does-not-exist=1 -e
exit:   1
```

The same shape carries the auth and account-lookup failures: `Invalid ctid or password` at exit 81, and `Account cannot be found. Use accounts command to list all trading accounts linked to cTrader ID` at exit 82, both on stdout with the matching stderr echo.

**Interactive-pipeline `Error:` without stderr echo.** The call reached the interactive pipeline, and validation failed inside it. Stdout carries an `Error:` message (sometimes after a banner and header line); stderr is empty.

```text
$ ctrader-cli.exe candles --account=5816091 --symbol=NOTAREALSYMBOL --period=D1 --count=10 -q -e </dev/null
stdout: [interactive banner]
        Error: Symbol not available: NOTAREALSYMBOL
stderr: (empty)
exit:   1
```

An invalid timeframe on the same command produces the analogous shape: stdout `Error: Invalid timeframe: 'zz9'.`, empty stderr, exit 1.

**Pre-routing parser message without echo.** The argument parser rejects the invocation before any pipeline is chosen. Stdout carries a message that does not begin with `Error:`; stderr is empty.

```text
$ ctrader-cli.exe accounts --ctid="<id>" --pwd-file="" </dev/null
stdout: Unable to determine destination for argument value: --pwd-file=
stderr: (empty)
exit:   1
```

The same shape appears when a positional argument itself cannot be resolved -- for example a nonexistent path passed to `metadata` produces `Unable to determine destination for argument value: <path>` on stdout with empty stderr, at exit 1, whether or not `-e` is present. Because this shape carries no `Error:` prefix, detect it by checking whether stdout is non-JSON and lacks that prefix, rather than by string-matching `Error:`.

**Unhandled exception trace without echo.** An argument combination the parser cannot resolve at all -- most notably mixing a bare trailing positional (`yes`) with `--flag=value` syntax on a direct launch line -- ends the process with an unhandled exception trace instead of a clean message. Stdout is typically empty; the trace, naming `ConsoleInvalidUsageException` and the parser's own call path, arrives on stderr; exit is 1.

```text
$ ctrader-cli.exe order cancel --order=312753167 yes --account=5816091 -e </dev/null
stdout: (empty)
stderr: Interactive shell crashed: ConsoleInvalidUsageException ...
        [stack trace through the CLI's own parser classes]
exit:   1
```

Pass confirmation with `-q` at launch instead of a trailing `yes` token to stay inside the first or second message shape rather than this one.

**Shell-routed credential failure with banner-only stdout.** An invocation that routes into the shell pipeline without credentials — a dual-mode verb called with `-q` but without `-e` or explicit `--ctid`/`--pwd-file`, or a subcommand `--help` on a shell-routed verb — fails before any command validation. Stdout carries only the `cTrader CLI` banner line; stderr carries the plain-English message `Missing --ctid in non-interactive mode.` with no command echo, no `Error:` prefix, and no stack trace; exit is 1 (`periods -q`, `symbols -q`, `metadata <path> -q`, and `deals --help` all fail this way). Recover by supplying credentials (`-e` with `CTID`/`PWD-FILE` set, or explicit `--ctid`/`--pwd-file`), by dropping `-q` for a verb whose batch form needs no credentials (`periods`), or by using the top-level `ctrader-cli.exe --help`, the only help form that works without credentials.

A non-numeric value supplied for a numeric flag stays inside the interactive-pipeline `Error:` shape rather than this exception-trace shape: `candles --account=<n> --symbol=EURUSD --period=D1 --count=notanumber -q -e` returns the message `Error: Option --count has invalid number: notanumber` on stdout, with stderr empty and exit 1. Validate numeric flag values before invoking, and read the named flag out of the message text to correct the call.

## Build: exit code is not the completion signal

`build` returns exit 0 for both a successful compile and a failed one. The process exit code carries no pass/fail information for this verb at all. The JSON body's `success` boolean is the only authoritative signal, with diagnostics in `errors: [{file, line, column, code, text}]` using Roslyn-style codes such as `CS1002` and `CS0103` when `success` is `false`. Read `success` from the JSON body on every `build` call regardless of exit code.

## Backtest: exit code is not the completion signal

`backtest` continues running after it has already printed its own completion output. A run prints a full progress log followed by a compact JSON summary on stdout -- keys such as `Equity`, `NetProfit`, `WinningTrades`, `LosingTrades`, `TotalTrades` -- within seconds of real work, and then keeps the process alive until the external `timeout` ends it at exit 124. When `--report-json` is supplied, that file is written correctly and completely even though the process itself has not yet been terminated. Treat the appearance of the final compact JSON summary on stdout, or the appearance of the `--report-json` file, as the completion signal for `backtest`; a 124 exit alongside either artifact is a completed run, not a failure. Always wrap `backtest` in an external `timeout` so the process is reliably ended once that signal has arrived.

## Wrapper shells and reported exit codes

A wrapper shell sitting between you and the CLI process can report a different exit code than the CLI itself produced -- for example a PowerShell call-operator invocation can surface the underlying failure through its own error-wrapping rather than passing the CLI's numeric code through untouched. When the message text and the exit code you observe disagree, trust the message text: it is the primary detection signal, and the exit code is the branch key you use only after the message has told you which branch you are on.

## Recovery actions by class

- **Exit 0, `success: false` or empty result payload (`build`, `candles` no-data window):** read the JSON body's own status field or content; this is not a process failure.
- **Exit 1, `Error:` on stdout, stderr echo present:** the batch pipeline rejected the arguments or a batch-routed lookup failed; correct the flag or value named in the message and retry.
- **Exit 1, `Error:` on stdout, stderr empty:** the interactive pipeline rejected the arguments; the message names the specific symbol, timeframe, or value at fault.
- **Exit 1, non-`Error:`-prefixed message, stderr empty:** a pre-routing parse failure; the message names the argument value the parser could not resolve.
- **Exit 1, empty stdout, exception trace on stderr:** an unhandled parser exception, typically from mixing a trailing bare positional with flag-style arguments; relaunch using `-q` for confirmation instead.
- **Exit 1, stdout `cTrader CLI` banner only, `Missing --ctid in non-interactive mode.` on stderr:** the call shell-routed without credentials; add `-e` or explicit credential flags, or drop `-q` where the batch form needs no credentials.
- **Exit 81:** re-check `CTID` and `PWD-FILE` before retrying.
- **Exit 82:** call `accounts` to get a valid account number before retrying.
- **Exit 124 on `backtest`:** check for the completion artifact (the final compact JSON summary on stdout or the `--report-json` file) before treating this as a failure; `backtest` keeps the process alive after completing its work, so a 124 with the artifact present is a completed run.
- **Exit 124 on `build`:** the timeout expired before the compile finished — `build` exits on its own (exit 0) once done, so no completion artifact will be present; raise the timeout and retry.
