# Local server: setup, account and market data

- [Setup and app switches](#setup-and-app-switches)
- [Tool map](#tool-map)
- [Session start](#session-start)
- [Account and environment](#account-and-environment)
- [Symbols](#symbols)
- [Volume handling](#volume-handling)
- [Prices and pips handling](#prices-and-pips-handling)
- [Money handling](#money-handling)
- [Time and sessions](#time-and-sessions)
- [Quotes](#quotes)
- [Trendbars](#trendbars)
- [Positions and pending orders](#positions-and-pending-orders)
- [History](#history)
- [Account statistics](#account-statistics)
- [Errors](#errors)
- [Recipe: book snapshot](#recipe-book-snapshot)
- [Recipe: history and bars over a long window](#recipe-history-and-bars-over-a-long-window)
- [Recipe: pre-trade snapshot](#recipe-pre-trade-snapshot)
- [Recipe: cost comparison by spread](#recipe-cost-comparison-by-spread)

## Setup and app switches

The Local server runs inside cTrader Windows or Mac while the app runs and is logged in. In the app's settings, "Enable MCP server" turns it on, "Allow trading via MCP" permits the order tools, and "Require confirmation for trading operations" makes the app ask before each trading operation. Clients connect over HTTP to `http://127.0.0.1:9876/mcp/`; the [public setup page](https://help.ctrader.com/ctrader-ai-agent-connect/en/local-mcp/setup/) gives the client entry.

## Tool map

Every tool the Local server serves, one line each. The last column names the section or file that documents its parameters.

| Tool | What it does | Details |
| --- | --- | --- |
| `get_accounts_list` | Lists the accounts the app holds, hidden accounts excluded | [Account and environment](#account-and-environment) |
| `get_balance` | Balance, equity, margin and connection of the account the app is logged in to | [Account and environment](#account-and-environment) |
| `get_account_statistics` | Aggregated trading statistics: net profit, trade counts, profit factor and win rate | [Account statistics](#account-statistics) |
| `get_server_time` | Current server time | [Time and sessions](#time-and-sessions) |
| `get_symbols` | Lists symbols, optionally narrowed by `filter` | [Symbols](#symbols) |
| `get_symbol_details` | Digits, pip size, lot size, volume limits, bid and ask of one symbol | [Symbols](#symbols) |
| `get_symbol_sessions` | Trading sessions and time zone of one symbol | [Time and sessions](#time-and-sessions) |
| `get_spot_prices` | Current quote of one symbol | [Quotes](#quotes) |
| `get_trendbars` | Bars of one symbol and timeframe over a window | [Trendbars](#trendbars) |
| `get_news` | Recent news items of the `general` or `crypto` feed | [local-app.md](local-app.md) |
| `get_positions` | Every open position | [Positions and pending orders](#positions-and-pending-orders) |
| `get_pending_orders` | Every pending order | [Positions and pending orders](#positions-and-pending-orders) |
| `get_order_history` | Closed trades the app has loaded | [History](#history) |
| `get_deals` | Newest deals that closed all or part of a position | [History](#history) |
| `place_market_order` | Opens a position at the market price | [local-trading.md](local-trading.md) |
| `place_limit_order` | Places a limit order | [local-trading.md](local-trading.md) |
| `place_stop_order` | Places a stop order | [local-trading.md](local-trading.md) |
| `place_stop_limit_order` | Places a stop-limit order | [local-trading.md](local-trading.md) |
| `amend_position` | Changes the stop loss or take profit of a position, as prices | [local-trading.md](local-trading.md) |
| `amend_order` | Changes the entry, volume, expiration or protections of a limit or a stop order | [local-trading.md](local-trading.md) |
| `close_position` | Closes a whole position | [local-trading.md](local-trading.md) |
| `close_position_partial` | Closes part of a position | [local-trading.md](local-trading.md) |
| `close_all_positions` | Closes every open position, optionally of one symbol | [local-trading.md](local-trading.md) |
| `cancel_order` | Cancels one pending order | [local-trading.md](local-trading.md) |
| `cancel_all_pending_orders` | Cancels every pending order | [local-trading.md](local-trading.md) |
| `calculate_margin` | Margin of a planned order | [local-trading.md](local-trading.md) |
| `list_charts` | Lists the open charts and which one is active | [local-app.md](local-app.md) |
| `open_chart` | Opens a chart of a symbol and makes it active | [local-app.md](local-app.md) |
| `close_chart` | Closes a chart by its id | [local-app.md](local-app.md) |
| `focus_chart` | Makes a chart active | [local-app.md](local-app.md) |
| `get_active_chart` | Shows the active chart | [local-app.md](local-app.md) |
| `change_chart_symbol` | Changes the symbol of the active chart | [local-app.md](local-app.md) |
| `change_chart_timeframe` | Changes the timeframe of the active chart | [local-app.md](local-app.md) |
| `get_chart_viewport` | Scroll position and zoom of the active chart | [local-app.md](local-app.md) |
| `scroll_chart` | Scrolls the active chart | [local-app.md](local-app.md) |
| `zoom_chart` | Sets how many bars the active chart shows | [local-app.md](local-app.md) |
| `listAvailableIndicators` | Lists the indicator types that can be added | [local-app.md](local-app.md) |
| `listChartIndicators` | Lists the indicators on the active chart | [local-app.md](local-app.md) |
| `addChartIndicator` | Adds an indicator to the active chart | [local-app.md](local-app.md) |
| `removeChartIndicator` | Removes an indicator from the active chart | [local-app.md](local-app.md) |
| `update_indicator_parameters` | Changes the parameters of an indicator on the active chart | [local-app.md](local-app.md) |
| `getIndicatorValues` | Last values of an indicator output, oldest first | [local-app.md](local-app.md) |
| `add_chart_object` | Adds a drawing to the active chart | [local-app.md](local-app.md) |
| `get_chart_objects` | Lists the drawings on the active chart | [local-app.md](local-app.md) |
| `update_chart_object` | Changes a drawing on the active chart | [local-app.md](local-app.md) |
| `delete_chart_object` | Deletes a drawing from the active chart | [local-app.md](local-app.md) |
| `clear_chart_objects` | Deletes every drawing on the active chart | [local-app.md](local-app.md) |
| `save_chart_template` | Saves the settings of the active chart as a template | [local-app.md](local-app.md) |
| `list_chart_templates` | Lists the chart templates | [local-app.md](local-app.md) |
| `apply_chart_template` | Applies a template to the active chart, replacing its indicators | [local-app.md](local-app.md) |
| `delete_chart_template` | Deletes a chart template | [local-app.md](local-app.md) |
| `save_workspace` | Saves the layout as a named workspace | [local-app.md](local-app.md) |
| `load_workspace` | Loads a saved workspace | [local-app.md](local-app.md) |
| `list_workspaces` | Lists the saved workspaces | [local-app.md](local-app.md) |
| `delete_workspace` | Deletes a saved workspace | [local-app.md](local-app.md) |
| `get_watchlists` | Lists the watchlists with their symbols | [local-app.md](local-app.md) |
| `create_watchlist` | Creates a watchlist | [local-app.md](local-app.md) |
| `rename_watchlist` | Renames a watchlist | [local-app.md](local-app.md) |
| `delete_watchlist` | Deletes a watchlist | [local-app.md](local-app.md) |
| `add_symbol_to_watchlist` | Adds a symbol to a watchlist | [local-app.md](local-app.md) |
| `remove_symbol_from_watchlist` | Removes a symbol from a watchlist | [local-app.md](local-app.md) |
| `get_price_alerts` | Lists the price alerts | [local-app.md](local-app.md) |
| `create_price_alert` | Creates a price alert | [local-app.md](local-app.md) |
| `delete_price_alert` | Deletes a price alert | [local-app.md](local-app.md) |
| `listPlugins` | Lists the cBots with their running state | [local-app.md](local-app.md) |
| `startPlugin` | Starts a cBot | [local-app.md](local-app.md) |
| `stopPlugin` | Stops a cBot | [local-app.md](local-app.md) |
| `switch_app` | Switches the app section | [local-app.md](local-app.md) |
| `get_current_app` | Shows the active app section | [local-app.md](local-app.md) |
| `set_layout_mode` | Sets the layout of the main window | [local-app.md](local-app.md) |
| `get_layout_mode` | Shows the layout of the main window | [local-app.md](local-app.md) |
| `set_asp_tab` | Sets the tab of the Active Symbol Panel | [local-app.md](local-app.md) |
| `get_asp_tab` | Shows the tab of the Active Symbol Panel | [local-app.md](local-app.md) |
| `set_market_watch_panel` | Sets the Market Watch panel | [local-app.md](local-app.md) |
| `get_market_watch_panel` | Shows the Market Watch panel | [local-app.md](local-app.md) |
| `set_trade_watch_tab` | Sets the TradeWatch tab | [local-app.md](local-app.md) |
| `get_trade_watch_tab` | Shows the TradeWatch tab | [local-app.md](local-app.md) |
| `show_notification` | Shows a notification in the app | [local-app.md](local-app.md) |

## Session start

Start a Local session with `get_accounts_list`, `get_balance` and `get_server_time`, and read each tool's schema before its first call.

## Account and environment

`get_accounts_list` lists the accounts the app holds, hidden accounts excluded; its items carry `id`, `login`, `accountName`, `brokerTitle`, `isLive`, `balance`, `currency`, `accountType` and `isOnline`. `isLive` is the only demo-or-live flag the server serves.

`get_balance` describes the account the app is logged in to, with `traderId`, `brokerName`, `depositAsset` (the currency name), `accountType` and `connectionState`, and carries no `isLive`; do not match its `traderId` with the list's `id` or `login`. It also gives the balance, equity, margin, free margin and margin level of that account; `marginLevel` reads `null` while no position is open. Take the app's connection from `connectionState`, not from the list's `isOnline`.

Read the account type from `accountType`. On an account that is not hedged, read `get_positions` after the first order opposite an open position, before telling the user what the order did.

Before an order-changing call, read `isLive`. When the list holds more than one account, or its one account differs from `get_balance` in balance, currency or broker, ask the user which account the app is on before trading.

The server acts on the account the app is logged in to, and no tool switches it. To work on another account, ask the user to switch in the app, then read `get_accounts_list` and `get_balance` again.

## Symbols

`get_symbol_details` gives `digits` (price precision), `pipSize` (the unit of every `*Pips` field), `lotSize`, `minVolume`, `maxVolume`, `volumeStep`, the current `bid` and `ask`, and descriptive fields. Read it at a symbol's first use in a session; digits, pip size and lot size come only from it.

`get_symbols` without `filter` returns every symbol, a large answer; pass `filter`, which matches name and description in any case. The other tools take the exact name as listed, case included; names can contain spaces.

Neither a `get_symbols` row nor `get_symbol_details` names a symbol's quote currency. `conversion_rate.py` reads a symbol name as six letters, the base currency then the quote currency, after dropping every character that is not a letter, so for a symbol whose name reads that way as two currency codes, such as EURUSD or EUR/USD, the quote currency is the last three letters. For every other symbol, ask the user which currency it is quoted in before sizing an order or converting a cost of it. The account currency is `depositAsset` of `get_balance`; when it is the quote currency, the conversion rate is 1, and otherwise the rate comes from `conversion_rate.py compute-chain` with the linking quote that [Money handling](#money-handling) names, read with `get_spot_prices`, whose prices are display prices on this server.

## Volume handling

Every Local tool that takes `volume` requires `volumeType`: `place_market_order`, `place_limit_order`, `place_stop_order`, `place_stop_limit_order`, `close_position_partial`, `calculate_margin`, and `amend_order` whenever it changes the volume. Send the unit the user gave; when the user gave a number without saying lots or units, ask. With `lots`, the size in units is `volume` × `lotSize`, with `lotSize` from `get_symbol_details`.

`get_symbol_details` can give `minVolume` and `volumeStep` below one unit; keep sizes as decimals and use decimal arithmetic.

`units_encoding.py lots-to-units --lots <lots> --lot-size <lot-size>` turns lots into units as an exact decimal, for `volume` with `volumeType` `units`; the lots themselves go into `volume` with `volumeType` `lots`. Check every size against the symbol's grid before sending it, as [local-trading.md](local-trading.md) describes.

## Prices and pips handling

`stopLossPips` and `takeProfitPips` are numbers in pips of the symbol's `pipSize`; positions and orders read back pips with decimals. The pip size differs between symbols, so take `pipSize` from `get_symbol_details` of the symbol at hand. After placing with a fractional pip distance, read the order back.

## Money handling

Balance, equity, margin, `grossProfit`, `netProfit`, `commission`, `swap` and the `calculate_margin` figures are in the account currency, named by `depositAsset` on `get_balance`; report them as they are. Convert only values the agent computes from prices, such as a pip value.

When a symbol's quote currency is the account currency, named by `depositAsset`, a value computed in the quote currency is already in the account currency: nothing is converted, and `conversion_rate.py` is not run. To convert such a value from any other quote currency to the account currency, `conversion_rate.py compute-chain` needs in `--quotes` the quote of a symbol that links the two currencies: one pair of the two in either order, or two pairs through a third currency such as USD. Find it with `get_symbols` and its `filter`, read its `bid` and `ask` with `get_spot_prices`, and pass them as an object under a key made of the names of its base and its quote currency, base first (`EURUSD` for EUR against USD): the script reads a quote's two currencies from its key. When the script exits with code 4, no chain links the two currencies among the quotes passed: tell the user that the conversion cannot be given, and present the figure in the quote currency, named as such.

Read the used margin from `margin` of `get_balance`; never total the `calculate_margin` figures of the open positions for it.

## Time and sessions

Send every time as ISO 8601 UTC with `Z`, converting a time the user gives in another zone or with an offset to UTC first, and take the current time from `get_server_time`.

`get_symbol_sessions` answers the symbol's time zone by name (for example "Eastern Standard Time"), whether the market is always open, and sessions as seconds counted from Sunday 00:00 in that zone, with day-of-week and second-of-day fields. Convert with the zone's UTC offset on the date in question before telling the user an opening time.

## Quotes

`get_spot_prices` takes one `symbolName` and answers `symbolName`, `bid`, `ask`, `spread` in pips, `high`, `low` and `open`, with no timestamp. The answer names no period for `high`, `low` and `open`, so do not present them as the range or the open of a day: take the range of a period from the bars of `get_trendbars`. For a symbol without a live quote it answers a tool error, and `get_symbol_details` shows `bid` and `ask` as `null`. Then, with the user's agreement, open a chart of the symbol with `open_chart`, read the quote again, and close that chart afterwards; if there is still no quote, tell the user the price is not available.

A quote can show `bid` equal to `ask` and `spread` 0.0 while the symbol's market is closed. Before presenting `spread` as a cost, read `get_symbol_sessions` and `get_server_time`: when the market is not always open and the server time, converted to the symbol's time zone, falls outside its sessions, say beside the quote that the market is closed, and do not present the spread as a current trading cost. In an open market the spread changes from read to read and can be 0.0, with `bid` equal to `ask`: present it as the spread at the moment of the read, never as the symbol's usual cost.

## Trendbars

`get_trendbars` takes `symbolName`, `timeframe`, `from` and `to` (ISO 8601 UTC with `Z`) and an optional `limit`; take the timeframe values from the description of `timeframe` and the default and cap of `limit` from the description of `limit`, since the schema states them only as text, with no list, default or maximum key. Send `from` earlier than `to`. The answer includes the bars that open at `from` and at `to`. When the window holds more bars than `limit`, the answer sets `truncated` to `true` and holds the newest bars of the window; the older bars are not in it. The bar still forming is not among the bars returned, also when `to` is the current time: for a range that reaches the present, cover the time since the last bar returned with the bars of a shorter timeframe, and add the current quote of `get_spot_prices`.

Each bar carries `timestamp`, `open`, `high`, `low`, `close` and `volume`; `timestamp` is the time the bar opens. A bar's `volume` is the number of ticks of its period, a count: give it as read, never as units or lots. A `d1` bar opens at the start of the symbol's trading day, which can fall on the evening of the previous calendar date in UTC, for example at 21:00Z or 22:00Z, and the hour can differ between the bars of one answer. Take the day boundary from the `timestamp` of the `d1` bars, and name a daily bar by the trading day it opens: a bar stamped in the evening holds the next calendar date. Name a weekly bar stamped on a Sunday evening by the week that starts the next day, and a monthly bar stamped on the evening of the last day of a month by the month that starts the next day: the bar stamped on the evening of 30 September is the October bar. For the bar of a day, a week or a month, send a `from` at or before that bar's `timestamp`: a `from` later than the `timestamp`, even by a second, leaves the bar out, so a `from` at 00:00Z of the date leaves out the daily bar that opened the evening before, a `from` at 00:00Z of a Monday leaves out the weekly bar stamped on the Sunday evening, and a `from` at 00:00Z of the first day of a month leaves out the monthly bar stamped on the evening before. The session start that `get_symbol_sessions` gives can lie seconds after the daily bar's `timestamp`, as a session that starts at 17:00:05 while the daily bar is stamped 17:00:00 in the same zone, so do not send the session start as the `from` of a daily bar.

## Positions and pending orders

`get_positions` returns every open position; send it without arguments, its schema lists none. To find one position, or to check that it is still open, look for its id in the answer.

`get_positions` answers under `positions` and `get_pending_orders` under `orders`. Read the size from `volumeInUnits`, the canonical volume (`volumeInLots` is `volumeInUnits` / `lotSize`). Position items carry `id` (the `positionId` other tools take), `symbolName`, `tradeSide`, `volumeInUnits`, `volumeInLots`, `lotSize`, `entryPrice`, `currentPrice`, `pips`, `grossProfit`, `netProfit`, `swap`, `commission`, `stopLossPrice`, `stopLossPips`, `takeProfitPrice`, `takeProfitPips` and `openTime`; pending-order items carry `id` (the `orderId`), `symbolName`, `tradeSide`, `orderType`, `volumeInUnits`, `volumeInLots`, `lotSize`, `targetPrice`, `currentPrice`, the same four protection keys and `expiration`. Both also carry `label` and `comment`.

On positions and pending orders alike, `stopLossPrice` and `takeProfitPrice` are absolute prices and `stopLossPips` and `takeProfitPips` distances in pips. A leg is set when its price key, `stopLossPrice` or `takeProfitPrice`, holds a price, and not set when that key reads `null`. A pips key can read `null` on a pending order whose leg is set, so never judge a leg by its pips key, and report a set leg whose pips key reads `null` by its price. On a long position, `stopLossPips` reads positive both for a stop below the entry and for one above it, so compare `stopLossPrice` with `entryPrice` to tell whether a stop sits on the loss side or the profit side.

Read-back names: a limit order's `limitPrice` reads back as `targetPrice`, `side` reads back as `tradeSide`, and `expiresAt` reads back as `expiration`. A stop-limit order reads back its stop price as `targetPrice`. For a stop-limit order this conversation placed through the Local server, its limit equals `targetPrice`, as [local-trading.md](local-trading.md) describes; for any other stop-limit order, the Local reads do not show its limit. Never report the requested `limitPrice` as the order's limit. Values in the answers are PascalCase, for example `tradeSide` `Buy` and `orderType` `StopLimit`.

## History

`get_order_history` returns the closed trades the app has loaded, under `trades`. Each item is one closing step of a position, with `positionId`, `symbolName`, `side` (the position's side), `volume` in units, `entryPrice`, `closePrice`, `pips`, `grossProfit`, `commission`, `swap`, `netProfit`, `openTime`, `closeTime`, `label` and `comment`; a partial close and the final close of one position are two items. Group items by `positionId` and tell them apart by `closeTime`. The history holds closed trades, as its description states; a pending order that was canceled or reached its expiry is not among them. When the span the user asks about starts before the oldest trade returned, tell the user that the answer covers only the history the app has loaded.

On a `get_order_history` item whose `swap` is 0, `netProfit` is `grossProfit` plus `commission` (`commission` is negative). On an item with a non-zero `swap`, compare the fields before you report a result: when `netProfit` equals `grossProfit` plus `commission` plus `swap`, it already contains the swap; when it equals `grossProfit` plus `commission`, add the item's `swap` to it. Judge a trade's result by `grossProfit` and `netProfit`, and report `pips` beside them as the move in pips. For an open position, report `grossProfit` and `netProfit` as `get_positions` gives them; do not derive one from the other. On a `get_positions` item whose `swap` is 0, `netProfit` reads `grossProfit` plus twice its `commission`.

After a partial close, the `commission` of the position's `get_positions` item is that of the volume still open, and each closed part is a `get_order_history` item of the same `positionId` with its own `commission`, `swap`, `grossProfit` and `netProfit`. When the user asks what a position has cost or earned so far and `get_order_history` holds items of its `positionId`, give the total of the `netProfit` of the closed parts, each read as the paragraph before describes, as the result of the closes so far, with the totals of their `commission` and `swap` beside it, and give the `grossProfit`, `commission`, `swap` and `netProfit` of the open part apart, as `get_positions` gives them. Total no figure across the open part and the closed parts: the `netProfit` of an open position is not formed as that of a closed part, as the paragraph before shows.

`get_deals` items carry `orderId`, `positionId`, `symbolName`, `dealType`, `side` (the position's side, not the side of the closing execution), `filledVolume` in units, `executionPrice`, `entryPrice`, `pips`, `grossProfit`, `commission`, `swap`, `netProfit` and `time`; tell deals apart by `orderId`. The rule on `swap` and `netProfit` of a `get_order_history` item holds for a `get_deals` item too. The deals `get_deals` returns are those that closed all or part of a position; opening fills are not among them. Each closing step, partial or final, is its own deal and its own trade. Read a position's opening from `get_positions` while it is open, and from `openTime` and `entryPrice` of its `get_order_history` items after it closed.

Page `get_deals` only by parameters its schema lists. When it lists only `symbolName` and `count`, it returns the newest deals up to `count` (default and cap in the description of `count`), oldest first, and older deals cannot be read through it; take a longer history from `get_order_history`.

No deal or trade field gives the reason a position closed. To tell a stop-loss or take-profit close from a manual one, compare the close price with the protection levels read before the close.

Read the container and the keys from each answer; where an answer differs from this section, for example by holding deals other than closing ones, follow the answer.

## Account statistics

`get_account_statistics` answers `available`; when it is `true`, the answer gives net profit, trade counts, win and loss shares, profit factor, average trade, and the largest winning and losing trade (key names in the answer). It carries no peak equity and no drawdown: for those, keep the agent's own `get_balance` equity readings over the session. When `available` is `false`, there are no figures; say so. No answer states the period the figures cover or what `totalTrades` counts, so do not call them lifetime results. Compare `totalTrades` with the number of `get_order_history` items: when they match, present the figures as covering the history the app has loaded; when they differ, present them as the account statistics the app reports, without tying them to the loaded history.

## Errors

A refused Local call answers a tool error, and nothing is placed or changed. The text often states the rule it applied, for example the volume step, the side of the market a limit price must be on, or an expiry already past. Some texts do not fit the request, for example naming as missing a parameter the call carried: then check each value's type against the schema. Correct the request, or ask the user, before sending again; do not resend it unchanged.

## Recipe: book snapshot

1. Read `get_positions` and `get_pending_orders`, both without arguments.
2. For each position, report the symbol, `tradeSide`, the size from `volumeInUnits` with `volumeInLots`, `entryPrice`, `currentPrice`, the stop loss and take profit as prices and in pips (a leg whose price key reads `null` is not set, as [Positions and pending orders](#positions-and-pending-orders) describes), and `grossProfit` and `netProfit` as returned, in the account currency.
3. For each pending order, report the symbol, `tradeSide`, `orderType`, the size from `volumeInUnits` with `volumeInLots`, `targetPrice`, the stop loss and take profit as prices, with the distance in pips where its pips key holds one (a leg whose price key reads `null` is not set), and `expiration`; for a stop-limit order, report its limit as [Positions and pending orders](#positions-and-pending-orders) describes.
4. Read `get_balance` and report balance, equity, margin and free margin as returned.

## Recipe: history and bars over a long window

For bars:

1. Set `limit` to the cap the description of `limit` states.
2. Split the window into parts whose bar count, the span divided by the timeframe length plus one, is below `limit`, each part with `from` earlier than `to`.
3. Request each part; when an answer sets `truncated`, split that part in two and request both halves.
4. Merge oldest first and drop repeated bar times, since adjacent parts share their boundary bar.

For closed trades, read `get_order_history` once and keep the items whose `closeTime` falls in the window; when the window starts before the oldest item, tell the user that the answer covers only the history the app has loaded. Page `get_deals` over a window only when its schema lists window parameters, as [History](#history) describes.

## Recipe: pre-trade snapshot

1. Read `get_accounts_list` for `isLive`, and `get_balance` for balance, equity, margin and the currency, reported as returned.
2. Read `get_symbol_details` for `digits`, `pipSize`, `lotSize` and the volume limits.
3. Read `get_spot_prices` for bid, ask and `spread` in pips; when it answers an error, follow the steps of [Quotes](#quotes). Check with `get_symbol_sessions` and `get_server_time` whether the market is open, as [Quotes](#quotes) describes; when it is closed, say so beside the quote and do not present the spread as a current trading cost; when it is open, present the spread, 0.0 included, as the spread at the moment of the read.
4. Read recent bars with `get_trendbars` by `timeframe`, `from`, `to` and `limit`; the bar still forming is not among them, as [Trendbars](#trendbars) describes.
5. Read `get_positions` and `get_pending_orders` with their protection keys.
6. When a size is planned, get its margin from `calculate_margin` and compare it with the free margin of `get_balance`.
7. No tool serves commission or swap rates; the snapshot says so.

## Recipe: cost comparison by spread

1. Read `get_spot_prices` per symbol for `spread` in pips, `get_symbol_details` for `pipSize`, and `get_symbol_sessions` with `get_server_time` for whether the market is open, as [Quotes](#quotes) describes; compare each symbol whose market is open with the spread its quote showed, 0.0 included.
2. The spread cost of a size is spread × `pipSize` × units, in the symbol's quote currency, taken as [Symbols](#symbols) describes. Convert it to the account currency as [Money handling](#money-handling) describes.
3. Leave commission and swap out, because no tool serves their rates and `get_symbol_details` carries neither; say so beside the figures.
4. Report a symbol without a live quote as without a price and a symbol whose market is closed as closed, both as not compared. Say beside the figures that the spreads are those of the moment of the read, never the symbols' usual costs.
