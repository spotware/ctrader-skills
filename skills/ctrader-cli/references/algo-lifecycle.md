# Algo lifecycle reference

## Requirements

cBots run on .NET 8. Recompile an older cBot in the latest cTrader desktop application before running or backtesting it with the CLI.

`--full-access` runs the cBot without access-rights limits. Where `--help` says so, it is required on Windows when the `.algo` declares full access, and on Linux, which has no sandbox, leaving it out prints a warning and delays the start; otherwise it lifts the access-rights sandbox for `run`.

## The loop

Run this loop in order for a new algo: `create` to scaffold, edit the generated source, `build` to compile, `metadata` on the resulting `.algo` to discover its parameters and access rights, then `backtest` with the confirmed override options, or `run` when the user asks for that run.

`metadata` takes no `-e`: it answers it with `Error: Parameter e is not allowed` and exits 1. Call it as `ctrader-cli metadata "<algo>"`; it needs no credentials. A `.algo` path that does not exist returns exit 1 with `Unable to determine destination for argument value: <path>`.

`create` and `build` can ask for credentials, depending on the build: when the answer is a `Missing --ctid in non-interactive mode.` line, pass the credentials; the build's `--help` and its answer decide.

## create

`create` scaffolds a cBot, an indicator or a plugin: `--kind=cbot|indicator|plugin`, `--name=<identifier>`, `--language=csharp|python`. Give the kind with `--kind=`: a kind written as a word before `--name`, as in `create plugin --name=<name>`, can be ignored, and the project is then a cBot.

Use these named options on a launch line, never the positional form `create <kind> <name> [<language>]`, which `--help` serves but which builds read differently at launch: two positionals end `Error: 'name' is required. ...` on one build and make the project on another.

```bash
timeout 30 ctrader-cli create --kind=cbot --name=<name> -e -q </dev/null
```

The answer names the kind it made (`"kind"`) and the project folder; check them.

## build

Point `build` at the project produced by `create`:

```bash
timeout 240 ctrader-cli build --project-path="<csproj-path>" -e -q </dev/null
```

`build` prints a JSON object whose `success` flag tells whether the compile passed, with `errors` (each with `file`, `line`, `column`, `code` and `text`) and `warnings`. Read `success`: a failed compile exits 0 on some builds and 1 with an `Error: Build failed ...` line on others.

When the project path does not resolve, `build` prints its header and one line, `Error: Project not found: '<path>'.` or `Error: No .csproj file found under '<folder>'.`, exits 1 and prints no JSON. Called without credentials, `build` can first answer `Missing --ctid in non-interactive mode.` and stop before it checks the path; pass the credentials then.

## metadata

Run `metadata` on the built `.algo` file before attempting a `run` or `backtest` override:

```bash
timeout 30 ctrader-cli metadata "<algo>" </dev/null
```

This returns exit 0 with an object such as:

```json
{
  "Name": "<name>",
  "Type": "cBot",
  "AccessRights": "None",
  "BuildTime": "<timestamp>",
  "Parameters": [
    { "PropertyName": "TakeProfitInPips", "FriendlyName": "Take Profit (Pips)", "Type": "Double", "DefaultValue": 10.0, "MinValue": 1.0, "MaxValue": 100.0 }
  ]
}
```

Each parameter carries `PropertyName`, `FriendlyName`, `Type` (such as `Double`, `Integer`, `String`), `DefaultValue`, `MinValue` and `MaxValue` where the cBot declares bounds, and `GroupName` for grouped parameters. The top-level `Type` is `cBot` or `Indicator`. Keep an override within `MinValue` and `MaxValue`.

`Parameters[].PropertyName` is not a documentation placeholder; it is the literal identifier you append after `--` to override that parameter on a later `run` or `backtest` call. A parameter named `TakeProfitInPips` becomes `--TakeProfitInPips=<value>` on the command line; the backtest parameter table's source tags show whether an override actually took (see Parameter overrides below). Treat `metadata` as the mandatory discovery step rather than guessing a generic `--CustomParameter1=<value>`-style option from the general help text; the real option name is always the exact `PropertyName` string, case preserved.

## Parameter overrides

A batch `run` or `backtest` sets a cBot parameter with `--<PropertyName>=<value>`. The mode routing of `--help` names the options that send a call to the interactive route: `--password`, `-q`, `--quick`, `--quit`, `--commands`, `--yes`, `-y`, `--all`, `--order`, `--position`, `--alert`, `--instance`, `--side`, `--volume`, `--volume-type`, `--sl`, `--tp`, `--stop-price`, `--limit-range`, `--indicator`, `--ind-params`, `--symbols`, `--condition`, `--message`, `--from`, `--to`, `--count`. When the name equals one of those options in any letter case, such as `Message`, `Volume` or `Count`, that form can move the call to the interactive route; set such a parameter in a `.cbotset` file instead. The comma-separated `--robot-params=k=v,...` form belongs to the interactive shell prompt only; on the batch route each parameter takes its own `--<PropertyName>=<value>` option.

Before the run, batch `backtest` prints a table headed `Backtesting cBot with parameters:`: the run settings (`Symbol`, `Period`, `Start`, `End`, `Balance`, `DataMode`, `Commission`, `Spread`), then the cBot parameters, each with its source, `cmd arg`, `cbotset` or `default value`. Long values are shortened. Check the `Start`, `End` and parameter rows before relying on the run.

`run` and `backtest` take a `.cbotset` file as the second argument, after the `.algo` path. Its values override the compiled defaults and show as `cbotset` in the parameter table; a `--<PropertyName>=` option can override a value from the file, and the table then shows that parameter as `cmd arg`. The cTrader desktop application exports `.cbotset` files.

Write a file as a JSON object `{"Chart": {"Symbol": "<name>", "Period": "<token>"}, "Parameters": {"<PropertyName>": "<value>"}}`, with every value a string and the names as `metadata` reports them in `PropertyName`; the `parameters.cbotset` file a backtest writes can have this form and can then be passed as it is. When the answer is `Invalid cbotset file format`, the run did not start: write the file in the form above and send the command again. Check in the parameter table that each value shows the source you expect: `cbotset` for a value from the file, `cmd arg` for an option.

## backtest

On the batch route (without `-q`), pass the `.algo` path as the first argument after the command. Run `backtest` without `-q`: with `-q` it can refuse the positional path with `Error: 'algo-file' is required. ...` and exit 1. `metadata` with `--algo-file=<algo>` can answer `Error: Specified algo file does not exist` and exit 1 although the file exists; give it the path as the first argument.

```bash
timeout 240 ctrader-cli backtest "<algo>" --start=01/06/2026 --end=15/06/2026 --data-mode=m1 --balance=1000 --account=<account> --symbol=EURUSD --period=h1 --report-json="<path>" -e </dev/null
```

`--start` and `--end` are written `dd/MM/yyyy` or `"dd/MM/yyyy HH:mm"` with a 24-hour time, in UTC as `--help` gives them. Plain ISO `yyyy-MM-dd` is rejected outright with `Error: Value for parameter start can't be parsed`. Check the `Start` and `End` rows of the parameter table before relying on the run. `--from` and `--to` are route options and can move `backtest` to the interactive route; use `--start` and `--end`.

`--data-mode` is required: `ticks`, `m1`, `m1-csv` or `open`, and `tick-csv` on a build whose `--help` lists it. Tick, Renko and range periods need `ticks`. `m1-csv` reads bars and `tick-csv` ticks from the CSV file named by `--data-file`. `--report=<path>` writes an HTML report, `--report-json=<path>` a JSON report. `--spread` is in pips. When `--help` lists `--commission-type`, `--commission` is an amount whose unit `--commission-type` sets (one of `UsdPerMillionUsdVolume`, the default, `UsdPerOneLot`, `PercentageOfTradingVolume`, `QuoteCurrencyPerOneLot`), and `--commission-auto` takes the symbol's own commission and ignores both; otherwise `--commission` is the commission per million. Pass a data mode or option only when your build's `--help` lists it.

Where `--help` lists them: `--data-dir=<folder>` reads and writes cached historical data in a folder that must already exist; keep it between runs to reuse the downloaded data, and in a container map it to a host folder. `--redownload-data` deletes the cached data of every symbol and timeframe the run requests and downloads it again, once per run; it does not apply to the CSV data modes. `--precise-conversion` downloads real historical exchange rates to convert profit and margin to the deposit currency, instead of approximated rates, at the cost of run time and download.

`--equity-x-axis=Time|Trades` sets the initial X axis of the report's equity chart, `Time` by default, where `--help` lists it.

When `--help` lists `--mc-method`, a backtest can add a Monte Carlo simulation: `--mc-method=reshuffle|bootstrap|block|stationary|synthetic` switches it on and selects the resampling method, and `--mc-output=<path>` is then required and receives the result as JSON. `--mc-iterations` sets the number of simulated runs, `--mc-seed` the seed (the same seed gives the same numbers), `--mc-starting-equity` the equity the runs start from (the backtest's starting balance by default), `--mc-ruin-floor` the equity counted as ruin, `--mc-block-size` the trades per block of the `block` and `stationary` methods. The `--mc-*` values are checked even without `--mc-method`, and a value out of range fails the command: take the ranges and defaults from `--help`.

Run without `--exit-on-stop`, `backtest` does not exit on its own after it finishes. Its log lines and its JSON summary print to standard output, the `--report-json` file is written in full, and the process then continues running until something external ends it. Keep the external `timeout` around `backtest` on every build, and read the summary or the `--report-json` file as the end of the run. A `124` exit from that external `timeout` alongside a present summary or report file is a completed run, not a failure. A backtest can also end with a non-zero exit code and no report file, with or without a summary. Where `--help` lists `--exit-on-stop` for `backtest` or `optimize`, it ends the process when the cBot stops itself. `backtest` and `optimize` take `--broker` and `--full-access` where `--help` lists them.

The summary on standard output is PascalCase (`Equity`, `NetProfit`, `MaxBalanceDrawdownPercentages`, `WinningTrades`, `LosingTrades`, `TotalTrades`, `AverageTrade`, `ProfitFactor`, `Fitness`, and related fields), while the file written by `--report-json` is camelCase with richer nested top-level keys (`main`, `equity`, `tradeStatistics`, `parameters`, `usedSymbols`, `positions`, `orders`, `history`, `entries`, `profitsLosses`, `roi`). These are two distinct schemas over overlapping content, not one casing of the other; parse each against its own shape.

In the backtest summary on standard output, a value the run cannot compute prints as a bare `-`, which is not JSON: read it as no value. `ProfitFactor` can print `-` when the run has no losing trade, and `AverageTrade` and `ProfitFactor` both when it has no trade. Take the figures from the `--report-json` file, which can hold a number where the summary prints `-`. A run that ends in an error can print a key with no value at all, such as `"Equity":,`, and write no report.

## optimize

When `--help` lists `optimize`, it sweeps cBot parameters over a date range and writes the optimization result: `ctrader-cli optimize "<algo>" ["<cbotset>"] --params=<file> --start=<dd/MM/yyyy> --end=<dd/MM/yyyy> --data-mode=<mode> --account=<account> --symbol=<name> -e`. `--params` names a JSON file with the parameter optimization settings, an object with a `parameters` array, the shape the cTrader desktop application exports from its optimization interface. `optimize` takes `--timeframe` (`-t`), never `--period`: one value pins the main timeframe, several comma-separated values sweep it, and without the option the timeframe comes from the `--params` file. `--method=genetic|grid` (genetic by default) and `--cores=<count>` set the search; `--criteria=<Index:max|min,...>` (for example `NetProfit:max,MaxEquityDrawdownPercentages:min`) or `--fitness` (the cBot's own `GetFitness`) rank the passes; `--auto-select-best` prints only the best pass; `--skip-empty-passes` drops passes that opened no trade; `--optres=<path>` writes the result as JSON and `--passes-dir=<folder>` a report per pass. The data, commission and runtime options apply as `--help` lists them for `optimize`; `--report` and `--report-json` do not. Set fixed parameter values in the `.cbotset` file.

## run

Start `run` only when the user asks for that run. The cTrader CLI documentation asks that an AI agent not start `run` on its own: a running cBot acts on the account until it stops.

The form is `ctrader-cli run "<algo>" ["<cbotset>"] --account=<account> --symbol=<name> --period=<token> -e`, with `--full-access` to lift the access-rights sandbox and `--exit-on-stop` to end the process when the cBot stops itself. `--account`, `--symbol` and `--period` are required.

Batch `run` blocks in the foreground, streaming output to standard output until the instance exits; pass `--exit-on-stop` when you want the process to end on its own once the algo stops itself, and otherwise plan to terminate it externally (the external `timeout` wrapper, or a signal) rather than expecting it to return control to you.

Start `run` so that the shell stays free for other calls, such as in the background with its standard output and standard error captured to files. While the run is going, read `cbots` from a second call: that read is the read-back of `run`. Report the instances `cbots` lists, and take the id for `stop --instance=<id>` from that list.

`--reconnect-timeout=<sec>`, where `--help` lists it, ends `run` with a non-zero exit code when the trading account session cannot be restored within that many seconds; without it, `run` keeps reconnecting.

## Running instances

`cbots` lists the cBot instances currently running on the account; `stop --instance=<id>` stops one instance, by an id from that list. Both run through the command shell, so call them with `-q` like every shell-routed command. To stop every instance, `--commands` lists the shell form `stop all` and `--help` the option `--all`; both change state. Stopping an instance you started at the user's request is cleanup; any other `stop`, and `stop all`, needs the user's authorization.

```bash
timeout 30 ctrader-cli cbots --account=<account> -e -q </dev/null
timeout 30 ctrader-cli stop --instance=<id> --account=<account> -e -q </dev/null
```

`stop` with an id that names no running instance can still exit 0, with `No running instances.`, so the exit code alone does not confirm a stop: read `cbots` after any `stop` and report the instances it lists.

## Files a backtest writes

`backtest` writes per-instance runtime artifacts under the cAlgo data tree, also when no `--report` was passed: on Windows `Documents\cAlgo\Data\cBots\<name>\<instance-guid>\Backtesting\`, containing `events.json`, `log.txt`, `parameters.cbotset` and `report.html`. On other platforms the cAlgo root differs, and the absolute paths that `create` reports (`projectPath`, `expectedAlgoFile`) reveal where that tree lives on the machine at hand. When cleaning up after a scratch run, check this location in addition to the explicit `--report-json` path and the project tree that `create` reported at `projectPath`.
