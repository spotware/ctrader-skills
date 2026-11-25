# Errors and exit codes

Read the exit code directly, then the message. The code tells you which branch to take, and the message tells you what to correct. Exit 0 alone never proves that the command you meant ran.

## Exit codes

| Code | Meaning | Recovery |
| --- | --- | --- |
| 0 | Success | Proceed, after you have found the result in the output |
| 1 | Invalid usage, an unknown option outside quick mode, a missing required parameter, a file or project path that does not exist, a validation error, or a parse error before any route is chosen | Read the message, such as an `Error:` line or a usage block, correct the argument it names, and do not retry unchanged |
| 81 | `Invalid ctid or password` | Check the cTrader ID and the password file; do not retry with the same credentials |
| 82 | `Account cannot be found. Use accounts command to list all trading accounts linked to cTrader ID` | Read `accounts` and retry with the `Number` and `Broker` it reports |
| 124 | The external `timeout` ended the process | Raise the timeout, or check whether the work finished before the process was ended |

Exit 82 has two causes: the account number is not linked to the cTrader ID, or `--broker` names a broker the account does not belong to. `--broker=<name>` selects the broker when the same account number exists at more than one broker. `accounts --broker=<name>` with a name that matches no account returns an empty result with exit 0.

With `-q`, a command that uses a trading account skips an option it does not recognize, without a message, so exit 0 does not show a misspelled option; a misspelled required option still stops the command with a message naming it, such as `Error: 'order' is required. ...`. On the batch route an unknown option stops the call with exit 1 and an `Error:` line that names it, such as `Error: Parameter <name> is not allowed` or `Error: Unknown command line parameters found: <name>`; match the `Error:` prefix and the name, not the whole line.

An unknown symbol, an unknown period or an empty data window has no exit code of its own. `candles` with an unknown symbol or period ends with exit 1 and a message, and a date window with no bars returns exit 0 with an empty `bars` array. The CLI's `--help` and `--commands` output documents no exit codes. Other nonzero codes exist; for a code this table does not list, act on the message text, not the number.

## Which stream carries what

Standard error never carries a result. It can carry, among other text, the line that repeats the command, a `Missing ... in non-interactive mode.` message, an exception trace and an `Invalid account number: ...` message; treat it as diagnostic text, never as a pass or fail signal.

Standard output carries every result and every `Error:` line. An exception trace can stand there too, alone or beside its copy on standard error. The banner `cTrader CLI` stands on standard output.

Batch output can also carry log lines before and after the result or the message, where a log line starts with a timestamp followed by `|`. A message such as `Error: ...`, `Invalid ctid or password` or `Account cannot be found. ...` can stand anywhere: search for a line that starts with that text; the same text can also appear inside a log line.

A build can print a line that repeats the command: on standard error, as the first line of standard output, or not at all, depending on the build and the command. It is never the result and never a sign of failure.

## Message shapes

The common shapes are:

**An `Error:` line on the batch route.** Validation failed on the batch route. Standard output carries a line that starts with `Error:`, often followed by a usage block:

```text
$ ctrader-cli symbols --account=<account> --no-such-flag=1 -e </dev/null
stdout: Error: Parameter no-such-flag is not allowed
        [usage block follows]
exit:   1
```

The sign-in and account failures take the same place: `Invalid ctid or password` with exit 81, and `Account cannot be found. Use accounts command to list all trading accounts linked to cTrader ID` with exit 82, both on standard output.

**An `Error:` line on the shell route.** Validation failed inside the command shell. Standard output carries an `Error:` line, sometimes after the banner and the header. An unknown symbol ends with exit 1 and an `Error: Symbol not ...` line that names it; the wording differs between commands and between builds, so match the `Error:` prefix and the symbol name, not the whole line:

```text
$ ctrader-cli candles --account=<account> --symbol=NOTAREALSYMBOL --period=D1 --count=10 -q -e </dev/null
stdout: [banner and header]
        Error: Symbol not available: NOTAREALSYMBOL
exit:   1
```

Another build or command can print `Error: Symbol not found: NOTAREALSYMBOL` for the same call.

An invalid timeframe on the same command gives the same shape, `Error: Invalid timeframe: 'zz9'.`, and so does a value that is no number for a numeric option: `Error: Option --count has invalid number: notanumber`. Read the named option out of the message and correct the call.

**A message from the argument parser.** The parser rejects the call before any route is chosen. The message does not start with `Error:`:

```text
$ ctrader-cli accounts --ctid="<ctid>" --pwd-file="" </dev/null
output: Unable to determine destination for argument value: --pwd-file=
exit:   1
```

A positional argument that cannot be resolved gives the same shape, for example a `.algo` path that does not exist passed to `metadata` or `backtest`: `Unable to determine destination for argument value: <path>`, exit 1. This shape carries no `Error:` prefix, so search for the `Unable to determine destination` text instead.

**An exception trace.** A batch call can also end with an exception trace, with exit 1 and no `Error:` line; depending on the build the trace stands on standard error, on standard output or on both. A non-numeric `--account` does this on batch `symbols`; the trace names `System.FormatException`. Pass the numeric `Number` that `accounts` reports.

**A non-numeric account on the shell route.** With `-q`, a non-numeric `--account` ends the command after the sign-in lines with exit 1 and `Invalid account number: '<value>'. Expected a numeric login id.` on standard error. Pass the numeric `Number` that `accounts` reports.

**Missing credentials.** A call that needs credentials and has none ends with exit 1: standard output carries the `cTrader CLI` banner, and standard error carries `Missing --ctid in non-interactive mode.` or `Missing --password or --pwd-file in non-interactive mode.`, with no `Error:` prefix. Supply the credentials with `-e` and the `CTID` and `PWD-FILE` variables, or with `--ctid` and `--pwd-file`; for `periods`, whose batch form needs no credentials, drop the option that moved it to the shell route. The top-level `ctrader-cli --help` works without credentials.

## Wrapper shells and reported exit codes

A wrapper shell between you and the CLI process can report a different exit code than the CLI produced: a PowerShell call-operator invocation, for example, can report the failure through its own error handling instead of passing the CLI's code through. When the message text and the exit code disagree, trust the message text, then branch on the code.

## Recovery by class

- **Exit 0 with an empty result** (an empty `bars` array, `[]` from `accounts --broker=<name>`): the call worked and found nothing; it is no process failure.
- **Exit 1 with an `Error:` line:** correct the option or value the line names and retry.
- **Exit 1 with `Unable to determine destination for argument value: <value>`:** the parser could not place that value; correct it, or pass it as its named option.
- **Exit 1 with an exception trace and no `Error:` line:** read the exception name; for `System.FormatException` on `--account`, pass the numeric `Number` that `accounts` reports.
- **Exit 1 with `Invalid account number: ...` on standard error:** pass the numeric `Number` that `accounts` reports.
- **Exit 1 with a `Missing ... in non-interactive mode.` line:** add the credentials, or drop the route option where the batch form needs none.
- **Exit 81:** check `CTID` and the password file before any retry.
- **Exit 82:** read `accounts`, then retry with the `Number` and `Broker` it reports.
- **Exit 124:** the external `timeout` ended the process; raise the timeout or check whether the work finished first.
