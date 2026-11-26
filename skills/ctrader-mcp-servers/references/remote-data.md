# Remote MCP server: data

## Session, profile and environment

Start with `get_session_status`: it reports `status`, `plant`, `environment` (demo or live), `profile`, `authMode` (`slug` for a token connection, `oauth` for a sign-in) and `login`. A call refused with `UNAUTHORIZED` and `reauthRequired: true` means the session has ended: relay its message to the user and stop, since a retry cannot succeed. On a token connection the user re-authenticates in cTrader Web and updates the token in the AI client's configuration, as the cTrader Help Centre says.

`create_order`, `amend_order`, `cancel_order`, `amend_position` and `close_position` exist only on a trading-profile connection; `get_session_status` reports the profile. The tool list alone does not show that the connection's token is accepted: call `get_session_status` to check the session; when it answers `UNAUTHORIZED`, relay the message and stop.

On a data profile, propose the trade, or a change to a position or a pending order, through the link tools (`remote-trading.md`). To trade directly, the user connects with the Remote MCP token that cTrader Web issues for the trading account (Settings, Remote MCP; one token per trading account), as the cTrader Help Centre setup page describes.

`get_version` returns `service`, `version` and `buildTime`. Use them in a report, never to choose what to do.

## Tool map

"Both" means the data and the trading profile.

| Tool | Profile | What it does |
| --- | --- | --- |
| `get_session_status` | both | Checks the session: status, plant, environment, profile, auth mode, account number |
| `get_version` | both | Service name, version and build time |
| `get_balance` | both | Balance, equity and free margin in minor units, with `moneyDigits` and `depositAssetId` |
| `get_assets` | both | Assets (currencies) and their ids |
| `get_symbols` | both | Symbols with their `symbolId`, `symbolName`, `digits`, `pipPosition`, `baseAssetId` and `quoteAssetId` |
| `get_spot_prices` | both | Current bid and ask of the symbols requested by id or name |
| `get_trendbars` | both | Price bars of one symbol and `period` |
| `get_positions` | both | Every open position and pending order |
| `get_position_details` | both | One position with its orders and deals |
| `get_pending_orders` | both | Pending orders |
| `get_order_history` | both | Orders of a time window |
| `get_deals` | both | Deals of a time window |
| `get_order_by_client_order_id` | both | The order created with a `clientOrderId` |
| `create_order` | trading | Places an order |
| `amend_order` | trading | Changes a pending order |
| `cancel_order` | trading | Cancels a pending order |
| `amend_position` | trading | Sets a position's stop loss, take profit, Advanced Take Profit levels and trailing stop |
| `close_position` | trading | Closes the volume it is sent of a position |
| `create_order_link` | both | Builds a cTrader link that opens a prefilled new order; places nothing |
| `close_position_link` | both | Builds a cTrader link to an open position; closes nothing |
| `cancel_order_link` | both | Builds a cTrader link to a pending order; cancels nothing |

Order placement, protections, closing and links are described in `remote-trading.md`.

## Session start

1. Confirm from the client's tool list that the server in use is this one, as `SKILL.md` describes.
2. Call `get_session_status`: read `environment` (demo or live), `profile` and `authMode`; the account number is `login`. Handle `UNAUTHORIZED` as the first section says.
3. Call `get_balance`, scale its money as the money section says, and resolve `depositAssetId` to a currency name with `get_assets`, passing it in `assetIds`.
4. Call `get_symbols` only when the task needs `digits`, `pipPosition`, the `symbolId` map or a symbol's `baseAssetId` and `quoteAssetId`.

## Symbols and lot size

`create_order`, `create_order_link`, `get_spot_prices` and `get_trendbars` take `symbolName` in place of the numeric `symbolId`, exactly one of the two (`get_spot_prices` takes ids, names or both), and match it exactly, case included; an unknown name fails the whole call with `INVALID_REQUEST`, and the refusal lists the case-insensitive near-matches with their ids. Take symbol names and `digits` from `get_symbols` of the connected server.

Call `get_symbols` only for `digits`, `pipPosition`, the `symbolId` map or the asset ids `baseAssetId` and `quoteAssetId`, and pass `names` or `symbolIds` for the symbols the task needs: the full list is 800+ symbols. The answer can hold every symbol of the account also when `names` or `symbolIds` are passed: take the rows of the task by `symbolId` or `symbolName`, never by their position in the answer, read no number of matches from the number of rows, and keep the rows for the session. Matching the rows of a quote read for several symbols needs that map, so such a read calls `get_symbols` once per session. Call `get_assets` with `assetIds` or `names` the same way: its answer can hold every asset of the server as well, so take its rows by `assetId` or `name`, never by their position, keep them for the session, and read both again in a new session.

A symbol's quote currency is the `name` of the `get_assets` row whose `assetId` equals the symbol's `quoteAssetId`, and its base currency the `name` of the row whose `assetId` equals its `baseAssetId`. Take both from there for every symbol, also for one whose name does not spell its currencies.

This server serves no lot size, volume step or minimum volume and has no symbol-details tool; a `get_symbols` row carries `digits` and `pipPosition` but no volume field. Its served text gives the lot size by instrument class: forex 100000, metals 100 (XAUUSD), indices and crypto 1, as typical values; the broker's value for the symbol decides. Say which lot size a size rests on, and for a symbol outside these classes ask the user for the lot size before sizing.

When the lot size of such a symbol stays in doubt, offer the user a test order of the smallest volume: place it only after the user confirms it like any other order, inspect the position it opens before sizing up, and close it.

## Volume

Volume is in the unit `SKILL.md` defines. Convert a size in lots with `units_encoding.py lots-to-cents --lots <lots> --lot-size <lot-size>`, the lot size taken as the section above says.

A refused volume's message states volumes in base units: multiply them by 100 for the request unit. This server serves no step or minimum, and this skill states no step rule: a volume the server refuses goes to the user, as the errors section says.

## Prices

`get_spot_prices` and `get_trendbars` answer in the quote scale `SKILL.md` defines: convert their values with `units_encoding.py quote-to-price --values <value> [<value> ...]` before showing or reusing them. Order, position and deal prices are display prices, as `SKILL.md` states: use them as returned. Before comparing an order price with the market, divide the quote by 100000.

A price may carry at most the symbol's `digits` decimals (`get_symbols`); more is refused, never rounded, with a message that quotes the price and, except on `amend_position`, the allowed number of digits, but names no field. Round every price to `digits` before sending.

## Money and account

`balance`, `equity` and `freeMargin`, and the commission, swap and profit fields of positions and deals, are integers in minor units of the deposit currency: amount = value / 10^moneyDigits. Convert one with `units_encoding.py display-money --raw <value> --money-digits <money-digits>`.

Responses without `moneyDigits` use the `moneyDigits` of `get_balance`: a deal row of `get_deals` carries none at its top level, while its `closePositionDetail` and the `deal` of a `close_position` answer carry their own. Positions carry their own `moneyDigits` too.

`get_balance` returns `balance`, `equity`, `freeMargin`, `balanceVersion`, `moneyDigits` and `depositAssetId`; `balanceVersion` is a counter, not money, and is never scaled. No tool serves the hedging mode, used margin or account type; the account number is `login` in `get_session_status`.

## Timestamps

`fromTimestamp` and `toTimestamp` are strings: epoch milliseconds as digits (`"<epoch-ms>"`) or ISO 8601 with a zone (`"<YYYY-MM-DD>T<hh:mm:ss>Z"`). Date-only, zone-less and epoch-second values are refused. Times in answers are epoch milliseconds, except `buildTime` of `get_version`, which is an ISO 8601 string.

This server has no server-time tool; take times from the timestamps in its responses.

## Quotes

Each `get_spot_prices` row carries `symbolId`, `bid`, `ask`, `high`, `low`, `sessionClose` and its own `timestamp` in epoch milliseconds, and no name. Match rows to the requested symbols by `symbolId`, never by position. When several symbols are read, match through the `symbolId` map of `get_symbols` kept for the session. A requested symbol can come back without a price in two forms: with no row, or as a row whose `bid` and `ask` are null and that carries `error`. Check `error` before reading the prices of a row. `SYMBOL_NOT_FOUND`: check the id or pass `symbolName`, and read once more. `PRICE_TIMEOUT`: no quote arrived in time, as when the market is closed; read again later. `SUBSCRIPTION_CONFLICT`: another call for the same symbol ran at the same time; read again, one call at a time. Either way the symbol has no price in this answer: say so.

## Trend bars

`period` takes the values of its schema enum; when the user asks for a period the enum lacks, offer the nearest valid one.

`get_trendbars` returns at most `count` bars counted back from `toTimestamp` (default and cap in its schema) and no `hasMore`; a window holding more bars comes back with the newest ones. `count` trims the window and never widens it. Without `fromTimestamp` the window is the span before `toTimestamp` that the description of `fromTimestamp` gives as its default, so a call for 100 `D_1` bars brings only the daily bars of that span. Fewer bars than `count` means the window ended, not the history: read older bars with further calls. Over a long range, request `count` at its cap, move `toTimestamp` back to the oldest bar returned (the bound is inclusive), drop the repeated bar, and repeat until the range is covered or a call brings no new bar, as when the range begins in a market closure. Keep each window within the span its schema allows, splitting a longer range into such windows; a wider window is refused with a message that names the limit.

## Positions and orders

`get_positions` takes no input and returns every open position and pending order. Read one position with `get_position_details {"positionId": <position-id>}`. The protection orders of a position appear in neither `get_positions` nor `get_pending_orders`: read its protections from the position.

Read a position's protections from `stopLoss` and `takeProfit` when present: a removed leg is an absent key, not null or zero.

A position whose `positionStatus` is `POSITION_STATUS_CLOSED`, with no `openTimestamp` and no deals, never opened: its order was canceled, rejected or expired before any fill. Do not report it as a closed trade. `positionStatus` `POSITION_STATUS_CREATED` means the position's pending order has not filled: its volume is 0 and there is nothing to close or amend. `POSITION_STATUS_ERROR` means the opening order failed. Report neither as an open position nor as a closed trade.

A position's full commission is `commission + closedCommission` and its full swap `swap + closedSwap`.

Positions carry no `unrealizedPnl`, and no `grossProfit` or `netProfit` before a first close. Estimate the floating profit from the current quote (value / 100000; the bid for a buy, the ask for a sell), `entryPrice` and the volume in base units (volume / 100), convert the result from the quote currency of the symbol, taken from `get_assets` as the symbols section says, to the account currency with `conversion_rate.py compute-chain --from-asset <quote-currency> --to-asset <account-currency> --quotes <quotes>` (`trading-math.md`), and call it an estimate. `grossProfit`, `netProfit`, `closedCommission` and `closedSwap` are realized totals: they appear once any part of the position is closed, so an open position after a partial close carries them too. Report them as the realized result of the closed part, apart from the estimate.

## Deals and order history

Page `get_deals` backwards: after each page, set `toTimestamp` to the smallest `executionTimestamp` in the page (a page is not strictly ordered by it), read again, and drop deals already seen by `dealId`; stop when `hasMore` is false. When a page brings no new `dealId` while `hasMore` is true, repeat with a larger `maxRows` (cap in the schema).

The window does not filter on `executionTimestamp` exactly; a deal executed near a bound can fall on either side, so let windows overlap and dedupe by `dealId`.

Report `dealStatus` as the deal returns it.

`closePositionDetail` holds `entryPrice`, `closedVolume`, `grossProfit`, `swap`, `commission`, `netProfit`, `balance` and `moneyDigits`, and `stopLoss` and `takeProfit` when the position had them. Take a closed trade's result from `closePositionDetail.netProfit` of its closing deals: it is `grossProfit` + `swap` + `commission` of that `closePositionDetail`, with costs as negative numbers, so the deal-level `commission` is not added to it.

Deals carry no closing reason. Look up the closing deal's `orderId` in `get_order_history`: `STOP_LOSS_TAKE_PROFIT` means a protection order made that close; another type names the order that made it.

Deals carry neither `comment` nor `label`: group deals by `positionId`.

Report a change from the call's response and the read-back `SKILL.md` names for it. When the matching deal is not yet in `get_deals`, say so and read again before calling it missing.

`STOP_LOSS_TAKE_PROFIT` orders in `get_order_history` are the protection orders of positions. Read each one's `orderStatus`: a filled one is the order of a closing deal, whose `closePositionDetail` gives the volume it closed. Each Advanced Take Profit level has its own such order, carrying the level's price in `limitPrice` and the level's volume, beside the one for the main stop loss and take profit; read a position's levels from its `advancedTakeProfit`, not from these orders. The history also lists orders still working, and its rows carry no time key. The orders `close_position` makes carry a `clientOrderId` the server generates, never one the agent set.

A protection order can carry the `clientOrderId` of the order that opened its position, so `get_order_by_client_order_id` with that id can return the opening order. Tell protection orders from the orders that opened positions by `orderType`, never by `clientOrderId`, and check the `orderId` and `orderType` the lookup returns before acting on the order.

When `get_order_history` answers `hasMore` true, narrow the window and dedupe by `orderId`; rely on no page order.

## Errors and rate limits

Every failed call returns `{"error":{"code":"<code>","message":"<text>","httpStatus":<status>}}`, sometimes with `field` or `retryAfter`; act on `code` and `message`.

| Code | What to do |
| --- | --- |
| `INVALID_REQUEST` | Correct the request as the message says (for example split a window it names as too wide, or add a field it names as missing) and resend. An order-changing call whose correction changes a value the user confirmed, such as a price, a distance, a volume or a protection, is a new call: show it and get a yes as `SKILL.md` describes before sending it. |
| 400 `TRADING_BAD_VOLUME` | The volume was refused, and the message gives its figures in base units: put the size to the user instead of rounding it. |
| 404 `UNKNOWN_SYMBOL`, `POSITION_NOT_FOUND`, `ORDER_NOT_FOUND` | Correct the symbol or id. On `get_order_by_client_order_id`, 404 `ORDER_NOT_FOUND` means that no order carries the id: before a `create_order` the id is free (`SKILL.md`, step 2), and after a `create_order` that timed out or answered `UPSTREAM_ERROR` or `UPSTREAM_UNAVAILABLE`, the same request is resent with the same id (`remote-trading.md`). |
| 409 `POSITION_NOT_OPEN` | Do not retry. |
| `UPSTREAM_ERROR`, `UPSTREAM_UNAVAILABLE`, `INTERNAL_ERROR` | Do not rewrite the request; report to the user. When a `create_order` timed out or answered `UPSTREAM_ERROR` or `UPSTREAM_UNAVAILABLE`, call `get_order_by_client_order_id` with its `clientOrderId` first: on 404 `ORDER_NOT_FOUND`, resend the same request with the same id; when an order comes back, report that order and resend nothing (`remote-trading.md`). |
| `UNAUTHORIZED` | Relay the message and stop, as the first section says. |
| 429 | Wait for `Retry-After` (or `retryAfter`), then resend the same request, a `create_order` with the same `clientOrderId`. |

## Recipe: book snapshot

1. Call `get_positions`: it returns every open position and pending order.
2. For each position, call `get_position_details` and read its protections from `stopLoss` and `takeProfit` and its Advanced Take Profit levels from `advancedTakeProfit` of the `position` object.
3. Report each position by its `positionStatus`: never report a created, failed or never-opened position as open or as a closed trade.
4. Scale money with the position's own `moneyDigits`, give the floating profit only as an estimate, and give the realized totals of a partly closed position apart from it.

## Recipe: history and bars over a long window

1. Split the range into windows within the span each tool's schema allows.
2. For bars, page each window back from `toTimestamp` with `count` at its cap, as the trend bars section says, and drop repeated bars.
3. For deals, page each window backwards by `executionTimestamp`, let windows overlap, and dedupe by `dealId`, as the deals section says.
4. For orders, read `get_order_history` per window; when it answers `hasMore` true, narrow the window and dedupe by `orderId`.
5. Group deals by `positionId`. A round trip's result is the sum of `closePositionDetail.netProfit` of its closing deals, scaled by their `moneyDigits`.

## Recipe: pre-trade snapshot

1. Call `get_session_status` and report the environment (demo or live) and the profile.
2. Call `get_balance`, scale the balance by `moneyDigits`, and name the currency through `get_assets`.
3. Call `get_spot_prices` by `symbolName`, match rows by `symbolId`, divide each value of a row without `error` by 100000, and report a requested symbol without a row, or with `error`, as without a price.
4. Call `get_trendbars` with `count` for the recent bars. Fewer bars than `count` means the default window ended; older bars take further calls, as Trend bars describes.
5. Call `get_positions` for the open positions and orders, and read each position's levels from `get_position_details`.
6. Call `get_symbols` for `digits` only when a price will be sent.
7. Say that the snapshot holds no commission or swap rate, because no tool serves one.

## Recipe: cost comparison by spread

1. Call `get_spot_prices` once for the symbols compared; match rows by `symbolId`, and name a symbol without a row, or with `error`, as without a price.
2. Take each spread as (ask - bid) / 100000.
3. Take the spread cost of a size as spread x volume / 100, in the quote currency of the symbol, the `get_assets` name of its `quoteAssetId` as the symbols section says, and convert it to the account currency with `conversion_rate.py compute-chain --from-asset <quote-currency> --to-asset <account-currency> --quotes <quotes>` (`trading-math.md`).
4. Leave commission and swap out of the comparison and say so: no tool serves their rates.
