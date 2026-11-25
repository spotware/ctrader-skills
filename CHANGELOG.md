# Changelog

## 0.2.1 (2026-11-25)


### Changes

* The README closes with the same sections, in the same order and wording, as the README of the cTrader plugin for AI agents: Releases, Contributing, License, Security.

## 0.2.0 (2026-11-25)


### Features

* ctrader-mcp-servers: the skill opens with how to tell the Remote and the Local server apart by the tools only one of them serves, a side-by-side table of the units each server uses (symbols, volume, quote and order prices, protections, money, timestamps, demo or live), and the checks before and after every order-changing call: read whether the account is demo or live, confirm the exact call with the user, check the quote, the side, the protections, the price digits and the volume, then read the result back.
* ctrader-mcp-servers: six references, one per server and kind of task plus one shared: `references/remote-data.md`, `references/remote-trading.md`, `references/local-data.md`, `references/local-trading.md`, `references/local-app.md` and `references/trading-math.md`.
* ctrader-mcp-servers: recipes for a book snapshot, history and bars over a long window, a pre-trade snapshot, a cost comparison by spread, opening a position, changing protections, closing all or part of a position or flattening the book, sizing a position from risk and, on the Local server, drawing a trade's risk and reward on a chart.
* ctrader-mcp-servers: `units_encoding.py quote-to-price` turns Remote quote integers into display prices, dividing by 100000 for every symbol; `units_encoding.py check-volume` reports whether a size lies on the Local volume grid and within its limits, with the nearest valid sizes below and above, and changes nothing.
* ctrader-mcp-servers: `pip_math.py distance` gives a distance as `relative` (1/100000 of the price, the unit of `relativeStopLoss` and `relativeTakeProfit`) and as `points` (1/10^digits, the unit of `slippageInPoints`), and refuses with exit code 2 a relative distance that is not a multiple of 10^(5 - digits), naming the two nearest valid ones.
* ctrader-cli: the bundled script `scripts/extract_result.py` finds the result in the captured standard output of a CLI command by a key only the result carries (`--key`), prints the period tokens (`--periods`) or a message line (`--message`), and checks itself with `--self-test`. The written rule it implements works without Python.
* ctrader-cli: the skill covers each install route: winget and the copy bundled with the cTrader desktop application on Windows, the Homebrew tap on macOS and Linux, and the container image on any OS with Docker. Where builds differ, the agent follows the build's own `--help`.
* ctrader-cli: `optimize`, the backtest options for cached data, real conversion rates, the equity chart axis, Monte Carlo simulation and `--exit-on-stop`, and `--reconnect-timeout` of `run`, each where the build's `--help` lists it.
* ctrader-cli: `create` scaffolds plugins as well as cBots and indicators, with the kind given as `--kind=`.

### Changes

* ctrader-mcp-servers: digits, pip size and lot size come from the connected server: `get_symbol_details` on the Local server, and on the Remote server `get_symbols` for digits and the lot size by instrument class, with a test order of the smallest volume offered, after the user confirms it, when the class does not settle the lot size.
* ctrader-mcp-servers: a stop loss or take profit the user confirmed that is missing after the call is set at once to exactly that value and reported, and the confirmation before the order says so.
* ctrader-mcp-servers: before a close or a cancel the agent names the position by symbol, side and entry price, or the order by symbol, side and price, in the message that shows the call.
* ctrader-mcp-servers: on the Remote server a new order gets a `clientOrderId` that no earlier order carries, looked up with `get_order_by_client_order_id` before the call is shown.
* ctrader-mcp-servers: on the Local server the agent starts a cBot only when the user asks for that start. Before `startPlugin` it shows the cBot, says whether the account is demo or live and gets a yes; after it, it reads the cBot's state back.
* ctrader-mcp-servers: on the Remote server, a call answered with 429 is sent again after the wait `Retry-After` gives, in place of fixed rate figures.
* ctrader-mcp-servers: examples carry placeholders such as `<position-id>` and `<order-id>` in place of identifiers.
* ctrader-mcp-servers: `units_encoding.py lots-to-units` and `lots-to-cents` print the exact product instead of rounding it down, and `units-to-lots` takes decimal units.
* ctrader-mcp-servers: `pip_math.py pips-to-price` takes decimal pips and prints `rounded`, with `unrounded_price` when rounding to `--digits` moved the level; `pip_math.py price-to-pips` prints the exact `pip_distance`, decimals included, and its `--digits` is optional.
* ctrader-mcp-servers: `position_sizing.py` sizes from the stop distance, given as `--sl-pips` with `--pip-size` or as `--price-distance`, and `--conversion-rate` and `--lot-size` are required, a call without either is refused with exit code 2 (a missing conversion rate was taken as 1), and the lot size only expresses the size in lots. It prints exact `units` and `lots`, `cents` (the Remote volume, rounded down so the risk stays at or below the target) with `cents_rounded_down`, and `risk_currency_amount`. `--min-volume`, `--max-volume` and `--volume-step`, given together in units, add `on_grid`, `within_limits`, `below` and `above`; nothing is rounded to the step or clipped to the limits.
* ctrader-mcp-servers: `conversion_rate.py` refuses a missing chain with exit code 4 and prints no `rate`, where it printed a rate of 0 with exit code 0.
* ctrader-mcp-servers: `tiered_margin.py` takes a decimal `--volume-base-units`, and refuses with exit code 2 an account currency other than USD given without `--account-currency-rate-vs-usd`, where it printed the USD figure as the margin in the account currency, and a USD account given an `--account-currency-rate-vs-usd` other than 1, where it printed the figure scaled by that rate as the margin in USD.
* ctrader-mcp-servers: every script keeps `--self-test`, with its cases matched to the behavior above.
* ctrader-cli: the result of a command is found by its content, never by its position, because standard output can carry log lines, a line that repeats the command and the result printed twice.
* ctrader-cli: `run` and `stop` join the commands that change state. The agent starts `run` only when the user asks for that run, and stops without asking again only an instance it started for the user.
* ctrader-cli: before and after every state-changing command the agent checks each option against `--help`, passes `--account`, reads the entity back and compares it with what it expected; a stop loss or take profit the user authorized that did not apply is set at once to the authorized value.
* ctrader-cli: before each state-changing command the agent tells the user what it does, and for a cancel or a close names the order by symbol, side and price, or the position by symbol, side and entry price.
* ctrader-cli: examples carry placeholders such as `<account>`, `<order-id>` and `<position-id>` in place of numbers.
* The bundled scripts of both skills need Python 3.11 or newer and run as `python3` on macOS and Linux and as `python` on Windows, or `py` where `python` is not on the path. The README states the same.
* Each skill pre-approves a Python command only when the command names one of the skill's own bundled scripts, under `python3`, `python` and `py`; a Python command that names none of them asks the user. The ctrader-mcp-servers skill pre-approved every `python` command before.
* `install.sh`: wrong arguments, such as an unknown option or a second directory, end it with a non-zero exit status and the usage text on standard error, before anything is installed.
* `install.sh`: `--force` replaces only the skill folders of this package and leaves the other skills and files of the install folder as they are.

### Removed

* ctrader-mcp-servers: the five references of 0.1.1; the six references above replace them.
* ctrader-mcp-servers: the asset `assets/symbol_precision_table.json` and `pip_math.py lookup-precision`; digits, pip size and lot size come from the connected server.
* ctrader-mcp-servers: the `units_encoding.py` subcommands `pipettes-to-price` and `price-to-pipettes` (use `quote-to-price`), and `cents-to-units`, `units-to-cents`, `parse-money` and `money-to-units` (use `display-money` for Remote money; Local money needs no conversion).
* ctrader-mcp-servers: the `position_sizing.py` inputs `--pip-value-per-lot` and `--min-volume-step` and its output `warnings`, and the `pip_math.py price-to-pips` output `pip_distance_raw`.

## [0.1.1](https://github.com/spotware/ctrader-skills/compare/v0.1.0...v0.1.1) (2026-08-21)


### Features

* add ctrader-cli skill ([1e2a6a0](https://github.com/spotware/ctrader-skills/commit/1e2a6a062462ff1238728afb7d7167ae34806f75))
* add ctrader-cli skill ([8185484](https://github.com/spotware/ctrader-skills/commit/818548455eca1fae6ed78ec4cc17322d61c38064))

## 0.1.0 (2026-05-15)


### Features

* initial public release of ctrader-skills ([881c235](https://github.com/spotware/ctrader-skills/commit/881c235eaf5f1837cdb8ce48a466195c31bb6857))

## Changelog
