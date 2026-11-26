# Changelog

## 0.2.2 (2026-11-26)


### Changes

* ctrader-cli: the skill no longer pre-approves `printenv`, so reading an environment variable asks the user like any other shell command.
* ctrader-cli: the agent starts `run` so that the shell stays free, reads `cbots` from a second call while the run is going as the read-back of `run`, reports the instances it lists, and takes the id for `stop --instance=<id>` from that list; after `stop` it reads `cbots` again.
* ctrader-mcp-servers: on a Remote data profile the agent changes a position's stop loss or take profit through `close_position_link` and a pending order through `cancel_order_link`, with the id read from `get_positions` or `get_pending_orders`, says which change to make, and reports the link as one that changes nothing until the trader acts in cTrader.
* ctrader-mcp-servers: on a Remote data profile the flatten recipe reads `get_positions` before it builds the cancel and close links, the cancel links first.
* ctrader-mcp-servers: for a MARKET_RANGE order the agent takes `baseSlippagePrice` from the quote read just before the call, the ask for a buy and the bid for a sell, unless the user names the base price, counts `slippageInPoints` from it, and names the base price and the bound in the confirmation.
* ctrader-mcp-servers: for a market link whose slippage bound the user gave as a price distance while the pip size is not known, the agent asks for the range in pips or for the pip size, and builds the link without a bound only when the user agrees, saying that it carries none.
* ctrader-mcp-servers: the agent calls `get_symbols` with `names` or `symbolIds` and `get_assets` with `assetIds` or `names`, as their descriptions ask; since either answer can hold every symbol or asset, the agent takes the rows of the task by id or name, never by their position, reads no number of matches from the number of rows, and keeps the rows for the session.
* ctrader-mcp-servers: on the Remote server the agent takes a symbol's quote and base currency from `get_assets`, the `name` of the row whose `assetId` equals the symbol's `quoteAssetId` or `baseAssetId`, and converts a spread cost, a floating profit and the rate a size needs from that quote currency to the account currency with `conversion_rate.py compute-chain`.
* ctrader-mcp-servers: the agent checks a new order's stop loss against its entry and a new stop loss of an open position against the current quote: a long position's below the bid, a short position's above the ask.
* ctrader-mcp-servers: `trading-math.md` names the data and trading files of each server as the layer files that hold the server's inputs, and the file table of the skill sends pips, sizing, margin, conversion, profit and swap work to them beside `trading-math.md`.
* ctrader-mcp-servers: in the Remote error table, 404 `ORDER_NOT_FOUND` from `get_order_by_client_order_id` means that no order carries the id, and a `create_order` that timed out or answered `UPSTREAM_ERROR` or `UPSTREAM_UNAVAILABLE` is looked up by its `clientOrderId` and resent with the same id on that 404, as `remote-trading.md` says.
* ctrader-mcp-servers: a Remote `create_order` answered 429 is resent unchanged, with the same `clientOrderId`, after the wait `Retry-After` gives.
* ctrader-mcp-servers: the pip distances of a Local pending order count from its `targetPrice`, the stop price of a stop-limit order, or from the new entry price when the same `amend_order` sends `entryPrice`; the agent turns a price the user gives into pips from that reference with `pip_math.py price-to-pips`, after checking that the level lies on its leg's side, and compares the price read back with the user's price.
* ctrader-mcp-servers: `amend_order` on the Local server does not change a stop-limit order and answers `Modify error: slippageInPoints have to be defined`; before any call the agent tells the user and offers to cancel the order and place a new one, each call confirmed, or to change it in cTrader, and says that a new order placed through the Local server has its limit at the stop price again. The new order takes the values the user changes and the rest from the read of the old one, its trigger method from the request kept in the conversation or from the user, and a label of its own.
* ctrader-mcp-servers: a stop-limit order placed through the Local server has its limit at the stop price, a limit range of 0, whatever `limitPrice` the call sends, so the agent sends `limitPrice` equal to `stopPrice` and asks the user for no limit price. Before the confirmation the agent tells the user so and offers to place the order that way, in cTrader where the limit range can be set, or through a Remote trading profile with `slippageInPoints`; a request whose limit differs from its stop price waits for the user's choice among these ways, also when the user's message confirmed its steps in advance. The confirmation names the limit at the stop price and, for an order with a stop loss or take profit, says that a level which does not apply cannot be set through the Local server afterwards; in the recipe for opening a position, such a level of a stop-limit order goes back to the user. The agent never reports the requested `limitPrice` as the order's limit.
* ctrader-mcp-servers: a message that confirms the steps of order-changing calls in advance covers those steps as the user stated them, and the agent asks about a call that differs from them before sending it.
* ctrader-mcp-servers: before `update_indicator_parameters` on the Local server the agent asks the user for the parameter names as the indicator settings in cTrader show them, since no tool lists them, and sends each name exactly as shown, letter case included, one parameter per call, since a call with a known and an unknown name answers `updated`; when a name is refused as an unknown parameter, the agent shows the user the text and asks again, and when a setting chosen from a list refuses the name of a choice, it takes the number of the choice from the user or tells the user to change the setting in cTrader. It says that no tool reads the change back.
* ctrader-mcp-servers: when the user gives the levels of a Local market order as prices, the agent turns them into pips from the quote read before the call is shown, the ask for a buy and the bid for a sell, shows each level in the confirmation as the user's price with the distance that is sent, says that the levels stand at those distances from the fill and can differ from the user's prices, and sends the confirmed distances without computing them again; a level that reads back `null` is set to the user's price, a level at the confirmed distance is not treated as missing, and moving it to the exact price is an `amend_position` the user confirms.
* ctrader-mcp-servers: the agent reads `side` of a Local `get_deals` item as the position's side, not the side of the closing execution, also in the flatten recipe.
* ctrader-mcp-servers: to draw a trade's risk and reward on the Local server, the agent asks the user for the level to draw when the trade's stop loss or take profit is not set, saying that it sets nothing on the trade, sends `side` from the trade on every call, since a call without it draws a buy, and starts the drawing at the position's `openTime` or, for a pending order, at `utcTime` of `get_server_time` unless the user names another start.
* ctrader-mcp-servers: the agent does not present `high`, `low` and `open` of the Local `get_spot_prices` as a day's range or open, since the answer names no period, and takes a range from `get_trendbars`; for a range that reaches the present it adds bars of a shorter timeframe and the current quote, since the bar still forming is not returned.
* ctrader-mcp-servers: `apply_chart_template` on the Local server is among the calls that delete or overwrite: the agent reads the active chart and its indicators first and confirms, since the call replaces the chart's indicators with those saved in the template, and passes the template's name as `templateId`.

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
