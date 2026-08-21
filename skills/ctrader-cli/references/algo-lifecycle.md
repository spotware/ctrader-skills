# Algo lifecycle reference

This reference covers the cBot and indicator developer loop: `create`, `build`, `metadata`, `backtest`, `run`, and the cleanup call `stop`.
The build JSON contract, the metadata-driven override flags, and the backtest completion signal each work differently from the read-only verbs, and a habit carried over from those verbs will misfire here.

## The authenticated loop

`create`, `build`, `metadata`, `run`, and `backtest` are the algo-lifecycle verbs — `metadata`, `run`, and `backtest` with a genuine batch code path, `create` and `build` shell-routed in every invocation shape (call them with `-q`) — and `-e` with `CTID`/`PWD-FILE` set in the environment is sufficient for all of them: no `--ctid`/`--pwd-file` flags are needed on the command line once the environment variables are present. `metadata` is callable with no account at all, exactly like `periods`; a nonexistent algo path still routes through the parser rather than an auth prompt, returning exit 1 with `Unable to determine destination for argument value: <path>` and empty stderr, identically whether `-e` is present or not. `create` and `build` do authenticate, and the full account handshake happens before either scaffolds or compiles files on disk.

Run this loop in order for a new algo: `create` to scaffold, edit the generated source, `build` to compile, `metadata` on the resulting `.algo` to discover its parameters and access rights, then `backtest` or `run` with the confirmed override flags.

## create: scaffolding a project

Use `--name=<value>` explicitly. A positional name after `create cbot <name>` does not reach the parser reliably: an invocation with a bare positional and no `--name` returns exit 1 with `Error: 'name' is required. Provide it as a positional argument inside the shell, or pass --name=<value> when launching the command.`, followed by the full interactive command menu, because any missing or misparsed required argument on these verbs drops the process into that menu rather than producing a clean batch error. Read the menu's presence in your captured output as the parser-fallback signal, not as evidence the wrong thing happened silently.

The working shape is:

```bash
timeout 30 ctrader-cli.exe create cbot --name=<name> -e -q </dev/null
```

A successful call returns exit 0 with a flat JSON object:

```json
{
  "kind": "cbot",
  "name": "<name>",
  "language": "csharp",
  "projectPath": "<path>",
  "projectFile": "<path>",
  "mainFile": "<path>",
  "expectedAlgoFile": "<path>",
  "status": "created"
}
```

`expectedAlgoFile` is exactly where the compiled `.algo` lands after a later `build`, so capture it and reuse it rather than reconstructing the path yourself. The name must be a valid identifier in the target language (`--help` documents this constraint for `--name`; for a `csharp` project that means a valid C# identifier). The JSON shape above is the `csharp cbot` case; the `create indicator` and `create cbot <name> python` variants follow the same shape by construction — re-confirm their `kind` and `language` fields on first use.

## build: the JSON contract

Point `build` at the project produced by `create`:

```bash
timeout 240 ctrader-cli.exe build --project-path="<csproj-path>" -e -q </dev/null
```

The process exit code is **0 on both a successful compile and a failed one**. The JSON body's `success` boolean is the only authoritative signal, and you must never infer the build result from the exit code alone. A successful build returns:

```json
{
  "projectPath": "<path>",
  "success": true,
  "errorCode": null,
  "errors": [],
  "warnings": []
}
```

A failed compile returns the same shape with `success: false` and populated diagnostic entries, each carrying `file`, `line`, `column`, `code`, and `text`:

```json
{
  "projectPath": "<path>",
  "success": false,
  "errorCode": null,
  "errors": [
    { "file": "<path>", "line": 12, "column": 9, "code": "CS1002", "text": "; expected" }
  ],
  "warnings": []
}
```

Diagnostic codes follow Roslyn's own numbering (`CS1002`, `CS0103`, and so on), so a `code` value is directly searchable against standard C# compiler documentation. Read `success` first, then walk `errors` for anything that needs fixing before your next `build` attempt; a nonempty `warnings` array alongside `success: true` is not a failure.

## metadata: discovering the real override flags

Run `metadata` on the built `.algo` file before attempting a `run` or `backtest` override:

```bash
timeout 30 ctrader-cli.exe metadata "<algo-path>" </dev/null
```

This returns exit 0 with:

```json
{
  "Name": "<name>",
  "Type": "cBot",
  "AccessRights": "None",
  "BuildTime": "<timestamp>",
  "Parameters": [
    { "PropertyName": "Message", "FriendlyName": "Message", "Type": "String", "DefaultValue": "Hello world!" }
  ]
}
```

`Parameters[].PropertyName` is not a documentation placeholder; it is the literal identifier you append after `--` to override that parameter on a later `run` or `backtest` call. A parameter named `Message` becomes `--Message=<value>` on the command line; the backtest parameter table's source tags show whether an override actually took (see Parameter precedence below). Treat `metadata` as the mandatory discovery step rather than guessing a generic `--CustomParameter1=<value>`-style flag from the general help text; the real flag name is always the exact `PropertyName` string, case preserved. `AccessRights` predicts whether `run` will need `--full-access`: the CLI's help describes the flag as disabling the access-rights sandbox on `run`, and the official documentation pairs the error `Additional AccessRights are required.` with `--full-access` as the remedy — so expect a `"FullAccess"` value to call for the flag and `"None"` not to, and confirm against a `FullAccess` algo on first use.

## Parameter precedence

When several sources set the same parameter, the expected order of precedence, lowest to highest, is: the algo's own compiled default, an environment-variable override, a supplied `.cbotset` file, and finally a command-line `--PropertyName=value` flag. The flag-over-default step is certain; verify the middle rankings with the parameter table's source tags before relying on them. If the ordering holds, you can keep a shared `.cbotset` baseline for a symbol/period combination and layer a per-invocation `--PropertyName=value` override on top without regenerating the whole settings file each time.

Whichever invocation shape you use, check the pre-flight parameter table before trusting a run: an invocation that is not launched with `-q` (or that is otherwise shell-routed) prints a "Collected parameters" table tagging each value's source as `cmd arg` or `default value`. Read that source tag before the run proceeds; it is the direct way to catch a parameter that silently fell back to its default because a flag name did not match the `PropertyName` you expected.

## run: launching an instance

`run` batch mode takes one `--PropertyName=value` flag per parameter override, discovered from `metadata` as above; the comma-separated `--robot-params=k=v,...` syntax belongs to the interactive shell prompt only and is not recognized in batch mode. Pass `--full-access` when `metadata`'s `AccessRights` field reports `"FullAccess"` (see the metadata section above).

Batch `run` blocks in the foreground, streaming output to stdout until the instance exits; pass `--exit-on-stop` when you want the process to end on its own once the algo stops itself, and otherwise plan to terminate it externally (the external `timeout` wrapper, or a signal) rather than expecting it to return control to you. Confirm the exact flag spelling and blocking shape with a live invocation before depending on timing-sensitive automation around it.

## backtest: date format, positional form, and completion signal

`--start` and `--end` take `dd/MM/yyyy` (or `dd/MM/yyyy HH:mm`) exclusively. The authoritative usage line in `--help` shows only `--start=<dd/MM/yyyy>` and `--end=<dd/MM/yyyy>` for `backtest`, even though the same help text's generic OPTIONS REFERENCE section lists `--from`/`--to` as applicable to `backtest` alongside `candles`, `deals`, and `orders-history`. That generic listing does not hold for `backtest` in practice: passing `--from`/`--to` to `backtest` reroutes the call into the interactive shell and ultimately fails with `Error: 'algo-file' is required...`, the same shell-reroute behavior seen on other missing required arguments. Plain ISO `yyyy-MM-dd` is rejected outright with `Error: Value for parameter start can't be parsed`. Use `--start=`/`--end=` in `dd/MM/yyyy` form and nothing else.

Pass the algo file as a **positional** argument, not as `--algo-file=<path>`. The positional form is the one to prefer: passing the path through the named `--algo-file=` flag changes validation order so that a malformed `--start` value is accepted rather than rejected, and the run silently falls back to a default trailing window of roughly seven days instead of raising the parse error the positional form produces. The positional form surfaces a bad date immediately; the named-flag form can substitute an unintended window without a validation failure to flag it. Always check the "Collected parameters" table's `Start`/`End` rows and their `cmd arg`/`default value` source tags before trusting a launched backtest, regardless of which form you used.

The working shape is:

```bash
timeout 240 ctrader-cli.exe backtest "<algo-path>" --start=01/06/2026 --end=15/06/2026 --data-mode=m1 --balance=1000 --account=<n> --symbol=EURUSD --period=h1 --report-json="<path>" -e </dev/null
```

`backtest` does not exit on its own after it finishes. Both the progress log and the final compact JSON summary print to stdout within seconds of real testing work, and the process then continues running until something external ends it. Treat the appearance of that final JSON block on stdout, or the appearance of the `--report-json` output file, as the completion signal, and always wrap `backtest` in the external `timeout`. A `124` exit from that external `timeout` alongside a present summary or report file is a completed run, not a failure; do not treat that exit code as a backtest error when the expected artifacts already exist. `backtest` documents no `--exit-on-stop`-equivalent flag of its own; that flag is scoped to `run` only, so the external timeout is the mechanism for `backtest` specifically.

The compact stdout summary is PascalCase (`Equity`, `NetProfit`, `MaxBalanceDrawdownPercentages`, `WinningTrades`, `LosingTrades`, `TotalTrades`, `AverageTrade`, `ProfitFactor`, `Fitness`, and related fields), while the file written by `--report-json` is camelCase with richer nested top-level keys (`main`, `equity`, `tradeStatistics`, `parameters`, `usedSymbols`, `positions`, `orders`, `history`, `entries`, `profitsLosses`, `roi`). These are two distinct schemas over overlapping content, not one casing of the other; parse each against its own shape. When `TotalTrades` is `0`, the compact stdout summary renders `AverageTrade` and `ProfitFactor` as a bare unquoted `-` token, which is not valid strict JSON; a parser that assumes every field is well-formed JSON should special-case that token before calling a generic `JSON.parse` on the summary.

## stop: idempotent cleanup

```bash
timeout 30 ctrader-cli.exe stop --instance=<guid> --account=<n> -e -q </dev/null
```

Calling `stop` against an instance that has already finished, or that never existed, returns exit 0 with the plain-text message `No running instances.` rather than an error. This makes `stop` safe to call unconditionally as a post-`backtest` or post-`run` cleanup step, whether or not you are certain an instance is still active.

## Runtime artifact locations

`backtest` writes per-instance runtime artifacts under the cAlgo data tree — on Windows `Documents\cAlgo\Data\cBots\<name>\<instance-guid>\Backtesting\`; on other platforms the cAlgo root differs, and the absolute paths that `create` reports (`projectPath`, `expectedAlgoFile`) reveal where that tree lives on the machine at hand — regardless of whether `--report` or `--report-json` was passed, containing `events.json`, `log.txt`, `parameters.cbotset`, and `report.html`. When cleaning up after a probe or a scratch run, check this location in addition to the explicit `--report-json` path and the project tree that `create` reported at `projectPath`/`expectedAlgoFile`.
