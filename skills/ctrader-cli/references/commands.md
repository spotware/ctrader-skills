# Read commands

## Calling a read command

Batch `accounts`, batch `symbols` and `periods` take the batch route. Every other command below is shell-routed: give its options at launch together with `--account=<account>`, `-e` and `-q`, as in `orders --account=<account> -e -q`.

Pass every argument of a shell-routed command as its named option at launch (`--symbol=<name>`, `--order=<order-id>`, `--indicator="<title>"`, `--count=<n>`); that form works on every build. Builds read a bare positional at launch differently, so never rely on one.

With `-q`, a non-numeric `--account` ends the command after the sign-in lines with exit 1 and `Invalid account number: '<value>'. Expected a numeric login id.` on standard error. Pass the numeric `Number` that `accounts` reports.

An unknown symbol ends with exit 1 and an `Error: Symbol not ...` line that names it; the wording differs between commands and between builds, so match the `Error:` prefix and the symbol name, not the whole line. This holds for `symbol`, `price` and `candles`.

## accounts

Batch command. Call it as `accounts -e`, without `--account`: the batch form refuses that option with `Error: Parameter account is not allowed`. The result is a JSON array of PascalCase objects, such as `[{"Id": <account-id>, "Number": <account>, "Broker": "<broker>", "Live": false, "DepositCurrency": "EUR", "Leverage": 100, "Balance": <balance>}]`. `Number` is the value `--account` takes. `Live` tells a demo account (`false`) from a live one: it is the field to check before any state-changing command.

`--broker=<name>` selects the broker when the same account number exists at more than one broker. `accounts --broker=<name>` with a name that matches no account returns an empty result, `[]`, with exit 0: no account matches that filter.

`accounts -q` takes the shell route and prints `{"accounts": [...]}`, each entry with `traderLogin`, `brokerName`, `depositCurrency`, `environment`, `isCurrent`, `balance`, `accountName`, `leverage`, `accountType`, `accessRights`, `accountStatus`, `isSwapFree`, `isLimitedRisk` and `traderId`. It has no `Live` key: `environment` is a string (`demo` on a demo account), so read whether an account is live from batch `accounts`.

## symbols

Batch command. Call it as `symbols --account=<account> -e`: the batch form requires `--account`, the inverse of `accounts`. The result is a JSON array of PascalCase objects with `Id`, `Name` and `Description` only. `--broker=<name>` selects the broker as on `accounts`. The list can be long: filter it by name, or read one instrument with `symbol --symbol=<name>` instead of loading the whole array.

`symbols -q` takes the shell route and prints `{"symbols": [...]}`, each entry with `name`, `description`, `category` and `assetClass` and no id field in any casing, so the numeric `Id` exists only in the batch form.

## periods

Call it as `periods`, with no option and no credentials. `-e` and each credential option are refused: the answer is `Error: Parameter <name> is not allowed`, one line per refused option, and exit 1.

The result is not JSON: it is a space-separated list of tokens that mixes lower-case families (`t1`, `m1`, `h1`) with capitalized ones (`D1`, `W1`, `Month1`). The tokens fall into families: `t` ticks, `m` minutes, `h` hours, `D` days, `W1` week, `Month1` month, `Re` Renko, `Ra` range bars, and the Heikin Ashi forms `Hm`, `Hh`, `Hd`, `Hw1`, `HMonth1`; the number after a prefix is the size. Renko and range tokens serve `backtest` with `--data-mode=ticks`; `candles` takes no Renko or range token, and such a token, like any token `candles` does not take, ends with exit 1 and an `Error:` line.

`candles` accepts a token in another letter case: `--period=d1` works, and the result echoes it as `"timeframe": "d1"` rather than the casing of the list.

## account

Shell-routed. Call it as `account --account=<account> -e -q`. The result is one object with `isCurrent`, `balance`, `equity`, `margin`, `freeMargin`, `marginLevel`, `netProfit`, `grossProfit`, `leverage`, `depositAsset`, `accountName`, `accountType`, `traderId`, `brokerName`, `connectionState` and `isSwapFree`.

`--commands` lists `account switch <account-id>` for changing the account inside a shell session; on a launch line choose the account with `--account=<account>`.

## account-stats

Shell-routed. Call it as `account-stats --account=<account> -e -q`. The result carries `available`; when it is `true`, the result also carries `netProfit`, `totalTrades`, `winningTrades`, `losingTrades`, `profitFactor`, `winningTradesPercent`, `losingTradesPercent`, `averageTrade`, `largestWinningTrade` and `largestLosingTrade`. Read the figures only when `available` is `true`.

## symbol

Shell-routed. Call it as `symbol --symbol=<name> --account=<account> -e -q`. The result is one object with `name`, `description`, `category`, `assetClass`, `digits`, `pipSize`, `lotSize`, `minVolume`, `maxVolume`, `volumeStep`, `bid` and `ask`: the field set order sizing needs. These values differ from symbol to symbol, so read them for the symbol you work with instead of assuming them.

The result carries no commission and no swap field. Commission and spread are inputs of `backtest` (`--commission`, `--spread`).

## sessions

Shell-routed. Call it as `sessions --symbol=<name> --account=<account> -e -q`. The result carries `symbolName`, `timeZone`, `marketIsAlwaysOpen` and `sessions`, a list of trading windows, each with `start` and `end` as day-and-time text and the numbers `startSecond` and `endSecond`. Read `start` and `end` together with `timeZone`.

## price

Shell-routed. Call it as `price --symbol=<name> --account=<account> -e -q`. The result is one object with `symbolName`, `bid`, `ask`, `spread`, `high`, `low` and `open`.

## prices

Shell-routed. Call it as `prices --symbols=<name>,<name> --account=<account> -e -q`. The result is `{"results": [...]}`, one item per symbol with `symbolName`, `ok` and `quote`, an object with the fields of `price`. Check `ok` on each item and read `quote` only from an item whose `ok` is `true`.

## candles

Shell-routed. Call it as `candles --symbol=<name> --period=<token> --account=<account> -e -q`, plus either `--count=<n>` or a `--from=<date>` and `--to=<date>` range.

The count form returns `symbolName`, `timeframe`, `requested`, `returned`, `available` and `bars`; each bar carries `timestamp`, `open`, `high`, `low`, `close` and `volume`. `available` reports how many bars exist for that symbol and period. The count form returns at most 1000 bars per call: `--count=1001` answers with `requested` 1000 and no warning. For more history, page through repeated `--from` and `--to` windows; no cursor or offset option exists.

The range form returns `symbolName`, `timeframe`, `from`, `to`, `returned` and `bars`, without `requested` and `available`. `--from` and `--to` take `yyyy-MM-dd` or `dd/MM/yyyy`, and a date without a time is read as midnight UTC. Leaving out `--to` ends the window at the moment of the call; the bar still open is left out, so only closed bars come back. A date-only `--to` is the start of that day, 00:00 UTC, and the window ends there: for an intraday period the bars of that day are not in the answer, so to include a day pass the next day as `--to`, as `--from=2026-11-01 --to=2026-11-11` for the hourly bars of 1 to 10 November. A reversed range ends with exit 1 and `Error: Invalid parameters: 'from' must be before 'to'.` A window with no trading, such as a weekend, returns exit 0 with `"returned": 0` and `"bars": []`: that, not an error, is how an empty window differs from a malformed request.

Bars come oldest first in both forms; never assume newest first. A bar's `timestamp` is the time it opens. A daily bar opens at the start of the symbol's trading day, which follows the symbol's daily session boundary, not midnight UTC, and can fall on the evening of the previous calendar date in UTC, for example at 21:00Z or 22:00Z. Read the boundary from `sessions` for the symbol, and name a daily bar by the trading day it opens: a bar stamped in the evening holds the next calendar date. Name a weekly bar stamped on a Sunday evening by the week that starts the next day, and a monthly bar stamped on the evening of the last day of a month by the month that starts the next day: the bar stamped on the evening of 30 September is the October bar. With such a boundary, a date-only window `--from=<A> --to=<B>` holds the daily bars stamped from A up to the day before B, which are the trading days after A up to B: for the trading days X to Y, pass the day before X as `--from` and Y as `--to`, as `--from=2026-11-01 --to=2026-11-06` for the trading days 2 to 6 November. Then check the first and the last `timestamp` of the answer against the days asked for.

## orders

Shell-routed: `--help` lists `orders` among the interactive commands only, never under batch mode. Call it as `orders --account=<account> -e -q`. With exactly one linked account the CLI can use it when `--account` is left out, and the banner then reads `Using your only account: ...` instead of `Using account: ...`; pass `--account` all the same.

The empty result is `{"orders": []}`, exit 0. A populated entry can show `targetPrice` (the limit or stop price), `limitPrice`, `slippagePips`, `stopLoss` and `stopLossPips`, among other fields; read the field names from the result.

## positions

Shell-routed, called like `orders`: `positions --account=<account> -e -q`. The empty result is `{"positions": []}`, exit 0, the normal case on an account with no open trades. A populated entry can show `currentPrice`, `pips`, `grossProfit` and `netProfit`, and each of the four can read null on an open position: report a null field as not available from the CLI, and put no figure derived from other values in its place. Read the field names from the result.

## order

Shell-routed. Call it as `order --order=<order-id> --account=<account> -e -q`; read the field names from the result. An id that names no active order ends with exit 1 and a plain-text line, `Order #<order-id> not found.`, not JSON: check the exit code before you parse. The lookup covers active orders only; closed and filled orders are in `orders-history`.

## position

Shell-routed. Call it as `position --position=<position-id> --account=<account> -e -q`. The result is one entry of `positions`, without the array, and its `currentPrice`, `pips`, `grossProfit` and `netProfit` can read null as there. An id that names no open position ends with exit 1 and a plain-text line, `Position #<position-id> not found.` The lookup covers open positions only.

## exposure

Shell-routed. Call it as `exposure --account=<account> -e -q`. The JSON root key is the plural `exposures`, although the command is singular. The empty result is `{"exposures": []}`, exit 0; for a populated entry, read the field names from the result.

## orders-history

Shell-routed. Call it as `orders-history --count=<n> --account=<account> -e -q`, or with `--from=<date>` and `--to=<date>` instead of `--count`. `--commands` lists only a count form and a date-range form for this command, so it takes no symbol filter; `deals` does.

`deals` returns at most 200 deals and `orders-history` at most 500 orders per call. Without `--from` or `--to` they cover the last 30 days. `--count` is 50 by default for `deals` and 100 for `orders-history`, and it is ignored when `--from` or `--to` is given. The result reports what was applied: `requested`, `returned`, `available` (when more exist) and `lookbackDays` in the count form of `orders-history`, `count` in `deals`; read them instead of assuming the count you asked for.

In the range form, `--from` and `--to` take a date, a calendar day in UTC, and a date-only `--to` includes that whole day, up to 23:59:59 UTC, although the `to` of the answer can echo it as `<date>T00:00:00.000Z`: for 1 to 10 November pass `--from=2026-11-01 --to=2026-11-10`, without adding the next day. In the range form, check whether the result was cut: in `orders-history` an `available` bigger than `returned` means that the range holds more orders, and in `deals` a `count` of exactly 200 means that it can hold more deals. Then split the range into shorter ranges that follow each other, each `--from` the day after the previous `--to`, run the command for each, and give totals only from the complete set.

The count form returns `requested`, `returned`, `lookbackDays` and `orders`, and adds `available` when more orders exist in the window than it returned; for the range form, read the field names from the result. Each order can carry `id`, `symbolName`, `tradeSide`, `orderType`, `status`, `volume`, `volumeLots`, `executedVolume`, `executedVolumeLots`, `targetPrice`, `executionPrice`, `stopLoss`, `takeProfit`, `positionId`, `openTime`, `closeTime`, `expiration`, `label` and `comment`. Times are ISO 8601 in UTC with a trailing `Z`.

The header line before the result restates the command as it ran: after `--count=600` it shows the count it applied, 500. Read it to confirm which filters took effect.

## deals

Shell-routed. Call it as `deals --account=<account> -e -q`, with `--symbol=<name>`, `--count=<n>`, or a `--from=<date>` and `--to=<date>` range, and a symbol together with a count or a range. The limits under `orders-history` apply.

The result carries `deals` and `count`; the range form adds `from` and `to`, which echo the dates given, a date without a time shown as midnight UTC (`<date>T00:00:00.000Z`), although a date-only `--to` covers that whole day, as the section `orders-history` says. Read when each deal happened from its own `time`. Each deal can carry `orderId`, `positionId`, `symbolName`, `dealType`, `side`, `filledVolume`, `filledVolumeLots`, `executionPrice`, `entryPrice`, `pips`, `grossProfit`, `commission`, `swap`, `netProfit`, `label`, `comment` and `time`.

The header line restates the filters the command applied; after `--count=500` it shows the cap, 200. Read it before you trust the query you meant to send.

## alerts

Shell-routed. Call it as `alerts --account=<account> -e -q`. The empty result is `{"alerts": []}`, exit 0. A populated entry can show `symbolName`, `price`, `condition`, `conditionType`, `quoteType` and `message`: `condition` is the word given at creation (`above` or `below`), `conditionType` the comparison stored for it (`GreaterOrEqual` for `above`), `quoteType` the price the alert compares (`Bid`), and `message` the label. Read the field names from the result.

## indicators

Shell-routed. Call it as `indicators --account=<account> -e -q`. The result is `{"indicators": [...], "count": <n>}`, each entry with `title` and `kind`. This is the way to discover indicator names: `title` is the exact text `--indicator=` takes on the other indicator commands. The list differs between builds, so read it on the build you use.

## indicator parameters

Shell-routed. Call it as `indicator parameters --indicator="<title>" --account=<account> -e -q`, with the exact `title` from `indicators`. The result is `{"indicator": "<title>", "parameters": [...]}`, each parameter with `name`, `friendlyName`, `type`, `groupName`, `description` and `defaultValue`. For `Simple Moving Average` the parameters are `Source` (type `DataSeries`, whose `defaultValue` is an object that names `Close` in `friendlyName`), `Periods` (type `Integer`, default 14) and `Shift` (type `Integer`, default 0).

`name` is the token a `--ind-params=<name>=<value>,...` override takes on the other indicator commands. Take it from this result, not from the generic example in `--help`, which shows `Period=20`: the parameter of `Simple Moving Average` is `Periods`. Names vary per indicator, so call `indicator parameters` for the indicator you work with.

## indicator calculate and indicator history

`indicator calculate` asks for an indicator's current value and `indicator history` for its values over the last `--count` bars: `indicator calculate --indicator="<title>" --symbol=<name> --period=<token> [--ind-params=<name>=<value>,...] --account=<account> -e -q`; `indicator history` takes the same options plus `--count=<n>`. Take `<title>` from `indicators` and parameter names from `indicator parameters`. The call returns the values, or it can end with exit 1 and an `Error:` line that names an exception, with no values; in that case report the `Error:` line to the user. Read the field names from the result.
