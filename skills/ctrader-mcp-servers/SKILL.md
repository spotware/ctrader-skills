---
name: ctrader-mcp-servers
description: "Use this skill ALWAYS when working with any cTrader MCP server, and load it before the first call to any of its tools: the Remote MCP server, a hosted service that reads and trades a cTrader account, or the Local MCP server inside the running cTrader desktop app. It covers quotes, trend bars, balance, positions, pending orders, deals and order history; placing, changing and closing trades; and, on the Local server, charts, indicators, drawings, watchlists, price alerts, workspaces and cBots. Use it also when the user names cTrader, a cTrader account or a cTrader chart without saying MCP."
allowed-tools: "Read, Grep, Glob, Bash(python3 *conversion_rate.py*), Bash(python *conversion_rate.py*), Bash(py *conversion_rate.py*), Bash(python3 *pip_math.py*), Bash(python *pip_math.py*), Bash(py *pip_math.py*), Bash(python3 *position_sizing.py*), Bash(python *position_sizing.py*), Bash(py *position_sizing.py*), Bash(python3 *tiered_margin.py*), Bash(python *tiered_margin.py*), Bash(py *tiered_margin.py*), Bash(python3 *units_encoding.py*), Bash(python *units_encoding.py*), Bash(py *units_encoding.py*)"
compatibility: "Requires Python 3.11 or later for the bundled scripts in scripts/, standard library only. Run them with python3 on macOS and Linux, and with python on Windows, or py where python is not on the path."
license: Proprietary. LICENSE.txt has complete terms.
metadata:
  author: "Spotware Systems Ltd"
---

## The two servers

- The Remote MCP server is a hosted service with two profiles: the data profile reads an account, and the trading profile also places, changes and closes its orders and positions.
- The Local MCP server runs inside the cTrader desktop app (Windows or Mac) while the app runs and is logged in. It acts on the account the app is logged in to and on the app's screen: charts, indicators, drawings, watchlists, alerts, workspaces and cBots.

## Which server is connected

Tell the servers apart by the tool names only one of them serves:

- Remote only: `get_session_status`, `get_version`, `get_assets`, `get_position_details`, `get_order_by_client_order_id`, `create_order`, `create_order_link`, `close_position_link` and `cancel_order_link`.
- Local only: `get_accounts_list`, `get_symbol_details`, `get_server_time`, `calculate_margin`, `list_charts`, `listPlugins`, `show_notification`, `place_market_order`, `place_limit_order`, `place_stop_order` and `place_stop_limit_order`.
- Both: `get_balance`, `get_symbols`, `get_spot_prices`, `get_trendbars`, `get_positions`, `get_pending_orders`, `get_order_history`, `get_deals`, `amend_order`, `amend_position`, `cancel_order` and `close_position`. These names prove nothing about the server.

No Local tool exists only to test the connection; the first read of a session shows whether the server answers.

When both servers are connected, take each call's server from the client's tool list, and never carry a value from one server's answer into the other server's call without converting it by the table in the next section.

Route the work by what each server can do:

| Work | Server |
| --- | --- |
| Charts, indicators, drawings, watchlists, price alerts, workspaces, cBots, news, app sections and notifications | Local only |
| Margin for a planned order, a symbol's lot size and volume limits, account statistics, server time and trading sessions | Local only |
| Session status, trade links the trader opens in cTrader, the lookup of an order by `clientOrderId`, market-range orders, trailing stop | Remote only |
| Account, quotes, trend bars, positions, pending orders, deals and order history | Either |

## Units on each server

| Value | Remote | Local |
| --- | --- | --- |
| Symbol identifier | `create_order`, `create_order_link`, `get_spot_prices` and `get_trendbars` take `symbolName` in place of the numeric `symbolId`, exactly one of the two (`get_spot_prices` takes ids, names or both), and match the name exactly, case included. | `symbolName`, the exact name `get_symbols` lists, case included. |
| Volume | `volume` = lots x lot size x 100, in 1/100 of the base asset. At the class lot sizes the server's text gives, one forex lot is 10000000, one XAUUSD lot 10000, one index or crypto lot 100. These class values are typical; the broker's value for the symbol decides. | `volume` is a decimal in the unit `volumeType` names, `lots` or `units`; `minVolume`, `maxVolume` and `volumeStep` are in units. |
| Quote prices | Quotes from `get_spot_prices` and `get_trendbars` are integers in 1/100000 of price for every symbol: display price = value / 100000 (a USDJPY bid of 15731000 is 157.31). The symbol's `digits` and `pipPosition` play no part in this scale. | The prices of `get_spot_prices` and `get_trendbars` are decimal prices as the trader sees them; `spread` is in pips. |
| Order, position and deal prices | Order, position and deal prices (`limitPrice`, `stopPrice`, `stopLoss`, `takeProfit`, `baseSlippagePrice`, `entryPrice`, `executionPrice`) are display prices: send and read them as the trader sees them. | Order, position and deal prices are decimal prices as the trader sees them. |
| Protections when placing | `relativeStopLoss` and `relativeTakeProfit` are distances in 1/100000 of price, whatever the symbol's digits: value = price distance x 100000, a multiple of 10^(5 - digits). A 30-pip stop on EURUSD is 300; a 5.00 stop on XAUUSD is 500000. MARKET and MARKET_RANGE take relative distances only; pending orders take absolute prices, the preferred form, or relative distances; `amend_order` takes either form. | `stopLossPips` and `takeProfitPips`, distances in pips of the symbol's `pipSize`, on the placement tools and on `amend_order`. |
| Protections on a position amend | `amend_position` takes absolute prices. A protection leg that is omitted is removed, and omitting `advancedTakeProfit` removes every Advanced Take Profit level. | `amend_position` takes absolute prices; an omitted leg stays as it is. |
| Money | `balance`, `equity` and `freeMargin`, and the commission, swap and profit fields of positions and deals, are integers in minor units of the deposit currency: amount = value / 10^`moneyDigits`. | Money values are decimals in the account currency. |
| Request timestamps | `fromTimestamp` and `toTimestamp` are strings: epoch milliseconds as digits or ISO 8601 with a zone. Date-only, zone-less and epoch-second values are refused. `expirationTimestamp` is an integer in epoch milliseconds. A period that ends now, such as the last 30 days, ends at the current time: a `toTimestamp` at 00:00 of the current date leaves out that day. | ISO 8601 UTC with `Z`. |
| Demo or live | `environment` of `get_session_status`. | `isLive` of the account's item in `get_accounts_list`. |

## Reference files

Read the files the task needs before the first call of that kind:

| Task | Files |
| --- | --- |
| Remote quotes, trend bars, account, positions, orders and history | `references/remote-data.md` |
| Remote trading, or a trade proposed through a link | `references/remote-data.md`, `references/remote-trading.md`, and `references/trading-math.md` when sizing |
| Local quotes, trend bars, account, positions, orders and history | `references/local-data.md` |
| Local trading | `references/local-data.md`, `references/local-trading.md`, and `references/trading-math.md` when sizing |
| Local chart or app work | `references/local-data.md`, `references/local-app.md` |
| A Local trade drawn on a chart | `references/local-data.md`, `references/local-trading.md`, `references/local-app.md` |
| Pips, sizing, margin, conversion, profit and loss, swap on either server | `references/trading-math.md`, and the data and trading files of the connected server: `references/remote-data.md` and `references/remote-trading.md` on Remote, `references/local-data.md` and `references/local-trading.md` on Local |
| Both servers connected | The files of each server the task touches |

Each recipe is a heading in the file of its server:

| The user asks for | Recipe | Remote | Local |
| --- | --- | --- | --- |
| The positions and pending orders of the account | Book snapshot | `references/remote-data.md` | `references/local-data.md` |
| More bars or history than one call returns | History and bars over a long window | `references/remote-data.md` | `references/local-data.md` |
| A look at a symbol and the account before a trade | Pre-trade snapshot | `references/remote-data.md` | `references/local-data.md` |
| Which symbol is cheaper to trade | Cost comparison by spread | `references/remote-data.md` | `references/local-data.md` |
| A new position | Open a position | `references/remote-trading.md` | `references/local-trading.md` |
| A new stop loss or take profit | Change protections | `references/remote-trading.md` | `references/local-trading.md` |
| Closing everything, a part, or the whole book | Close all or part, flatten | `references/remote-trading.md` | `references/local-trading.md` |
| A size for a given risk | Position size from risk | `references/trading-math.md` | `references/trading-math.md` |
| A trade's risk and reward on a chart | Draw a trade's risk and reward | none | `references/local-app.md` |

## Rules for every call

- The tool's served description and input schema decide its names, required fields, enum values, defaults and caps. Read a tool's schema before its first call in a session; where it differs from this skill, follow the schema and tell the user.
- Take every id from the server's answers, never from an example. Examples in this skill show placeholders such as `<position-id>` and `<order-id>`.
- When an answer differs from what this skill describes, stop: show the user the request and the answer, follow the served text, and do not retry in a loop.
- On any build of either server, also after a server update, the served tool list and schemas decide which tools exist and how each is called.

## Before and after an order-changing call

The order-changing tools are `create_order`, `amend_order`, `cancel_order`, `amend_position` and `close_position` on Remote, and `place_market_order`, `place_limit_order`, `place_stop_order`, `place_stop_limit_order`, `amend_order`, `amend_position`, `close_position`, `close_position_partial`, `close_all_positions`, `cancel_order` and `cancel_all_pending_orders` on Local. The Remote link tools `create_order_link`, `close_position_link` and `cancel_order_link` execute nothing and need no confirmation; never report their action as done.

Every order-changing call goes through the steps below. Step 3 ends the reply with a question unless the user's message already states that the exact steps are confirmed, so the first order-changing call of a request usually waits for the user's next message.

Before the call:

1. Read whether the account is demo or live, from the source the units table names.
   - On Remote, `get_session_status` also reports the profile: the order tools exist only on a trading-profile connection, and on a data profile, propose the trade through the link tools (`references/remote-trading.md`).
   - On Local, when `get_accounts_list` lists more than one account, or its one account differs from `get_balance`, ask the user which account the app is on before trading (`references/local-data.md`).
2. Check the request:
   - Current state: read what the call changes first, the position or the pending order it amends, closes or cancels, with the reads step 4 names.
   - Quote sanity: read the current quote right before the call and compare every price of the request with it. Before comparing an order price with the market, divide a Remote quote by 100000; Local quotes are already display prices. A price far from the quote goes back to the user, with the quote, before anything is sent.
   - Side against the market: a buy limit sits below the current ask and a buy stop above it; a sell limit sits above the current bid and a sell stop below it. A price on the other side means the order type or the side differs from what the user wants: ask, and never change the type or the side yourself.
   - Protections on the right side: a buy's take profit above its entry, a sell's below it. A new order's stop loss is checked against its entry, below it for a buy and above it for a sell, and a new stop loss of an open position against the current quote, not the entry: a long position's below the current bid, a short position's above the current ask. Show the user a level on the wrong side; never correct it yourself.
   - Price digits: every price carries at most the symbol's `digits` decimals (`get_symbols` on Remote, `get_symbol_details` on Local). Round it before sending; the Remote server refuses more decimals and rounds nothing.
   - Volume: on Local, check the size in units against `minVolume`, `maxVolume` and `volumeStep` with `units_encoding.py check-volume`; the Remote server serves no volume step or minimum. A size off the grid or outside the limits, and a volume a server refuses, goes back to the user; never round or change it yourself.
   - Fields the order type needs: read the trading file of the server, `references/remote-trading.md` or `references/local-trading.md`, when this session has not read it yet. Every field it and the tool's schema require for this order type is present; ask the user for a missing one.
   - An id of the agent's own on a placement: on a Remote `create_order` a `clientOrderId` that no earlier order carries, a `label` of its own on a Local placement. With it, a placement whose answer never arrives is looked up before anything is sent again. Put the `timestamp` of the quote just read into the `clientOrderId` and call `get_order_by_client_order_id` with it before the call is shown: 404 `ORDER_NOT_FOUND` means the id is free. When an order comes back, the id is taken: add `-2`, then `-3`, and look each up until one is free. The Remote server answers a `create_order` that repeats an earlier `clientOrderId` with that earlier order and places nothing, and a short name, a date, or the `timestamp` of a quote that has not changed is repeated by a later request.
   - Schema keys only: send no key the tool's schema does not declare.
3. Show the user the call before it is sent, and get a yes to it:
   - What to show: the call in the user's terms as well as the tool's. For a placement, the symbol, side, volume, prices and protections; for an amend, the values it sets and the ones it keeps; for a close or a cancel, which position or order it is: a position by symbol, side and entry price, an order by symbol, side and price. Name them again in the message that shows the call, also when an earlier message did: an id alone does not tell the user which position or order is about to go. Say whether the account is demo or live. For an order that carries a stop loss or take profit, add one sentence: a confirmed level that the read-back lacks is set at once to exactly that value. That sentence is what makes the yes cover the one corrective call, which is reported after it: without it, the correction would need a question of its own while the order stands without its protection. For a Local stop-limit placement, name its limit at the stop price, and when the order carries a stop loss or take profit, say in place of that sentence that a level the read-back lacks cannot be set through the Local server afterwards and goes back to the user, as `references/local-trading.md` describes.
   - When to ask: before every order-changing call, unless the user's message states that these exact steps are confirmed and that no further question is wanted. A request alone is not that statement, however complete it is: the call is built from what the user had not seen when asking, such as the account's kind, the current quote and the size in the server's unit, and the yes is the user's check of it. To ask, end the reply with the call shown and the question, and make no order-changing call until the user's next message says yes. When the message did confirm in advance, do not ask again, and still show each call this way just before sending it. That confirmation covers the steps as the user stated them, and a call that differs from them is asked about first.

After the call:

4. Read the changed order or position back with a read tool before the next order-changing call and before the report, and compare the symbol, side, volume, entry price, stop loss and take profit with what the user confirmed. Do it also when the call's answer already shows the order or position, and after each step when the user confirmed several at once: this read is the state the next call starts from, the source of its ids, of the volume a close sends and of the levels an amend resends.
   - On Remote: an open position with `get_position_details`, a pending order with `get_pending_orders`.
   - On Local: a position with `get_positions`, a pending order with `get_pending_orders`.
   - After a close in full or a cancel, on either server: the list that held it, `get_positions` for a position and `get_pending_orders` for an order, to see that it is gone.
5. Report a change from the call's response and the re-read, and only what they show. On Remote, when the matching deal is not yet in `get_deals`, say so and read again before calling it missing.
6. After a partial close, check that the volume left on the position equals the volume before less the volume closed.
7. A stop loss or take profit the user confirmed that the re-read lacks is set at once to exactly that value, and reported: on a position with `amend_position`, as an absolute price, and on a pending order with `amend_order`. The call carries what the server needs to keep the rest: a Remote `amend_position` resends the other leg and every Advanced Take Profit level, and a Remote `amend_order` resends the order's price field, every protection that stays and its expiration, since an omitted one is removed; a Local `amend_order` takes the level as a pip distance and leaves an omitted field as it is, and does not change a stop-limit order, which goes back to the user as `references/local-trading.md` describes. Anything else that differs waits for the user.

## Scripts

The scripts compute from values the agent has read; none of them calls a server.

| Script | Subcommand: what it computes | Inputs and their source |
| --- | --- | --- |
| `units_encoding.py` | `quote-to-price`: Remote quote integers as display prices | `--values` from Remote `get_spot_prices` or `get_trendbars` |
| `units_encoding.py` | `lots-to-cents`: lots as the Remote `volume` | `--lots`, `--lot-size`; the Remote server serves no lot size, and `references/remote-data.md` says where it comes from |
| `units_encoding.py` | `lots-to-units`, `units-to-lots`: lots and Local units | `--lots` or `--units`, `--lot-size` from Local `get_symbol_details` |
| `units_encoding.py` | `check-volume`: whether a size lies on the volume grid and within the limits; it reports and changes nothing | `--lots` or `--units`, `--lot-size`, `--min-volume`, `--max-volume`, `--volume-step` from Local `get_symbol_details` |
| `units_encoding.py` | `display-money`: a Remote money integer as an amount | `--raw`, `--money-digits`: the object's own `moneyDigits`, else that of `get_balance` |
| `pip_math.py` | `pips-to-price`, `price-to-pips`: a level from a pip distance, and a pip distance from a level | `--reference-price`, `--pip-size`, `--digits`: on Local, `--pip-size` and `--digits` from `get_symbol_details`; on Remote, `--digits` from `get_symbols`; use pips only where the symbol's pip size is known, and otherwise give the distance in price |
| `pip_math.py` | `distance`: a distance in the unit of `relativeStopLoss` and `relativeTakeProfit` and in the points of `slippageInPoints` | `--pips` with `--pip-size`, or `--price-distance`; `--digits` |
| `position_sizing.py` | `from-risk-percent`, `from-risk-amount`: a size from a risk target, with an optional grid check | `--balance` or `--risk-amount` in the account currency; the stop distance as `--sl-pips` with `--pip-size`, or as `--price-distance`; `--conversion-rate` and `--lot-size`, both required; optionally `--min-volume`, `--max-volume` and `--volume-step` together |
| `conversion_rate.py` | `compute-chain`: the rate between two currencies through a chain of quotes | `--from-asset`, `--to-asset`, `--quotes` with display prices keyed by symbol name |
| `tiered_margin.py` | `compute`: a margin estimate over a leverage tier curve | `--volume-base-units`, `--quote-rate-usd` as a display price, `--tiers` |

Run a script by its path in this skill's folder, the folder that holds this SKILL.md, not in the working directory: `python3 <skill folder>/scripts/<name>.py` on macOS and Linux, and `python <skill folder>/scripts/<name>.py` on Windows, or `py <skill folder>/scripts/<name>.py` where python is not on the path. A script prints one line of JSON. Its `--help` lists the flags, and `--self-test` runs the script's own cases and exits 0 when they pass, which checks the script on the interpreter at hand.

The Remote `volume` of 0.01 lot of a symbol whose lot size is 100, the class value the server's text gives for metals:

```text
python3 <skill folder>/scripts/units_encoding.py lots-to-cents --lots 0.01 --lot-size 100
python <skill folder>/scripts/units_encoding.py lots-to-cents --lots 0.01 --lot-size 100
{"cents":100}
```

A Local size for a risk of 1 percent of a balance of 10000 in the account currency and a stop 32 pips away, with the values `get_symbol_details` gives for the symbol passed as read (here `pipSize` 0.0001, `lotSize` 100000, `minVolume` 1000, `maxVolume` 10000000 and `volumeStep` 1000) and a conversion rate of 1 for an account in the quote currency:

```text
python3 <skill folder>/scripts/position_sizing.py from-risk-percent --balance 10000 --risk-pct 1 --sl-pips 32 --pip-size 0.0001 --conversion-rate 1 --lot-size 100000 --min-volume 1000 --max-volume 10000000 --volume-step 1000
python <skill folder>/scripts/position_sizing.py from-risk-percent --balance 10000 --risk-pct 1 --sl-pips 32 --pip-size 0.0001 --conversion-rate 1 --lot-size 100000 --min-volume 1000 --max-volume 10000000 --volume-step 1000
{"units":31250,"lots":0.3125,"cents":3125000,"cents_rounded_down":false,"risk_currency_amount":100,"on_grid":false,"within_limits":true,"below":{"units":31000,"lots":0.31,"risk_currency_amount":99.2},"above":{"units":32000,"lots":0.32,"risk_currency_amount":102.4}}
```

The size lies off the volume step, so the agent changes nothing and offers the user the nearest sizes below and above it, each with the risk it carries.
