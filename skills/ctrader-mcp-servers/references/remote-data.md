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
| `get_symbols` | both | Symbols with their `symbolId`, `symbolName`, `enabled`, `digits`, `pipPosition`, `baseAssetId` and `quoteAssetId` |
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
4. Call `get_symbols` only when the task needs `digits`, `pipPosition`, the `symbolId` map, a symbol's `baseAssetId` and `quoteAssetId`, the list of symbols the user can trade, or a symbol's `enabled` before a new order or order link in it.

## Symbols and lot size

`create_order`, `create_order_link`, `get_spot_prices` and `get_trendbars` take `symbolName` in place of the numeric `symbolId`, exactly one of the two (`get_spot_prices` takes ids, names or both), and match it exactly, case included; an unknown name fails the whole call with `INVALID_REQUEST`, and the refusal lists the case-insensitive near-matches with their ids. Take symbol names and `digits` from `get_symbols` of the connected server.

Call `get_symbols` only for `digits`, `pipPosition`, the `symbolId` map, the asset ids `baseAssetId` and `quoteAssetId`, the list of symbols the user can trade, or the `enabled` of a symbol before a new order or order link in it, and pass `names` or `symbolIds` for the symbols the task needs, or `enabledOnly` for the list: the full list is 800+ symbols. The answer can hold every symbol of the account also when `names` or `symbolIds` are passed: take the rows of the task by `symbolId` or `symbolName`, never by their position in the answer, read no number of matches from the number of rows, and keep the rows for the session. Matching the rows of a quote read for several symbols needs that map, so such a read calls `get_symbols` once per session. Call `get_assets` with `assetIds` or `names` the same way: its answer can hold every asset of the server as well, so take its rows by `assetId` or `name`, never by their position, keep them for the session, and read both again in a new session.

A `get_symbols` row carries `enabled`, and a row whose `enabled` is false is a symbol not enabled for trading, as the description of `enabledOnly` puts it: "Only symbols enabled for trading." The answer can hold rows whose `enabled` is false also when `enabledOnly` is passed: when the user asks for the symbols they can trade, list the rows whose `enabled` is true, taken by the key. When the user asks for a new order in a symbol whose row has `enabled` false, through `create_order` or `create_order_link`, say that the symbol is not enabled for trading and send neither call for it. A request to close, cancel or change a position or a pending order the account already holds in such a symbol is handled as for any other symbol, and a quote of such a symbol can still be read and reported.

A symbol's quote currency is the `name` of the `get_assets` row whose `assetId` equals the symbol's `quoteAssetId`, and its base currency the `name` of the row whose `assetId` equals its `baseAssetId`. Take both from there for every symbol, also for one whose name does not spell its currencies.

When a symbol's `quoteAssetId` is the `depositAssetId` of `get_balance`, a figure in its quote currency is already in the account currency: nothing is converted, and `conversion_rate.py` is not run. To convert a figure from any other quote currency to the account currency, the `get_assets` name of `depositAssetId`, `conversion_rate.py compute-chain` needs in `--quotes` the quote of a symbol that links the two currencies: a symbol whose `baseAssetId` and `quoteAssetId` are the two currencies' asset ids in either order, or two such symbols through a third currency such as USD. Find it among the `get_symbols` rows kept for the session by its `baseAssetId` and `quoteAssetId`, read it with `get_spot_prices`, turn its `bid` and `ask` into display prices (value / 100000), and pass them as an object under a key made of the `get_assets` names of its base and its quote currency, base first (`EURUSD` for a base of EUR and a quote of USD): the script reads a quote's two currencies from its key. When the script exits with code 4, no chain links the two currencies among the quotes passed: tell the user that the conversion cannot be given, and present the figure in the quote currency, named as such.

A symbol's pip size is 10 to the power of minus its `pipPosition`: `pipPosition` 4 gives a pip size of 0.0001, 2 gives 0.01 and 0 gives 1. It is the `--pip-size` the scripts take on this server. `pipPosition` and `digits` play no part in the scale of quotes, which `SKILL.md` defines.

This server serves no lot size, volume step or minimum volume and has no symbol-details tool; a `get_symbols` row carries `digits` and `pipPosition` but no volume field. Its served text gives the lot size by instrument class: forex 100000, metals 100 (XAUUSD), indices and crypto 1, as typical values; the broker's value for the symbol decides. Say which lot size a size rests on, and for a symbol outside these classes ask the user for the lot size before sizing.

When the lot size of such a symbol stays in doubt, offer the user a test order of the smallest volume: place it only after the user confirms it like any other order, inspect the position it opens before sizing up, and close it.

## Volume

Volume is in the unit `SKILL.md` defines. Convert a size in lots with `units_encoding.py lots-to-cents --lots <lots> --lot-size <lot-size>`, the lot size taken as the section above says. Turn the `volume` of an order, a position, a deal or an Advanced Take Profit level into units of the base asset, `volume` / 100, and into lots with `units_encoding.py units-to-lots --units <units> --lot-size <lot-size>`, the lot size taken as the section above says, and name the lot size the lots rest on. A deal's `filledVolume` and the `closedVolume` of its `closePositionDetail` are in the same unit as `volume`: divide them by 100 for units of the base asset, and turn units into lots as for `volume`.

A refused volume's message states volumes in base units: multiply them by 100 for the request unit. This server serves no step or minimum, and this skill states no step rule: a volume the server refuses goes to the user, as the errors section says.

## Prices

`get_spot_prices` and `get_trendbars` answer in the quote scale `SKILL.md` defines: convert their values with `units_encoding.py quote-to-price --values <value> [<value> ...]` before showing or reusing them. Order, position and deal prices are display prices, as `SKILL.md` states: use them as returned. Before comparing an order price with the market, divide the quote by 100000.

A price may carry at most the symbol's `digits` decimals (`get_symbols`); more is refused, never rounded, with a message that quotes the price and, except on `amend_position`, the allowed number of digits, but names no field. Round every price to `digits` before sending.

## Money and account

`balance`, `equity` and `freeMargin`, and the commission, swap and profit fields of positions and deals, are integers in minor units of the deposit currency: amount = value / 10^moneyDigits. Convert one with `units_encoding.py display-money --raw <value> --money-digits <money-digits>`.

Responses without `moneyDigits` use the `moneyDigits` of `get_balance`: a deal row of `get_deals` carries none at its top level, while its `closePositionDetail` and the `deal` of a `close_position` answer carry their own. Positions carry their own `moneyDigits` too.

`get_balance` returns `balance`, `equity`, `freeMargin`, `balanceVersion`, `moneyDigits` and `depositAssetId`; `balanceVersion` is a counter, not money, and is never scaled. It carries no used margin as a field, and the used margin follows from one `get_balance` answer as `equity` minus `freeMargin`, both scaled by `moneyDigits`, since free margin is equity minus the margin used, as the glossary of the cTrader Help Centre defines it: present it as a derived value and say that it is derived. No tool serves the hedging mode or the account type; the account number is `login` in `get_session_status`.

## Timestamps

`fromTimestamp` and `toTimestamp` are strings: epoch milliseconds as digits (`"<epoch-ms>"`) or ISO 8601 with a zone (`"<YYYY-MM-DD>T<hh:mm:ss>Z"`). Date-only, zone-less and epoch-second values are refused. Times in answers are epoch milliseconds, except `buildTime` of `get_version`, which is an ISO 8601 string.

This server has no server-time tool, and no answer carries the time of the read. Take the current time from the environment or the user, where either gives it; a date alone shows that a time lies days back. The newest `timestamp` among the `get_spot_prices` rows of a read is a time the read cannot precede, and it is not the time of the read: the row of a closed market carries the time of its last quote, as Quotes says.

## Quotes

Each `get_spot_prices` row carries `symbolId`, `bid`, `ask`, `high`, `low`, `sessionClose` and its own `timestamp` in epoch milliseconds, and no name. Match rows to the requested symbols by `symbolId`, never by position. When several symbols are read, match through the `symbolId` map of `get_symbols` kept for the session. A requested symbol can come back without a price in two forms: with no row, or as a row whose `bid` and `ask` are null and that carries `error`. Check `error` before reading the prices of a row. `SYMBOL_NOT_FOUND`: check the id or pass `symbolName`, and read once more. `PRICE_TIMEOUT`: no quote arrived in time, as when the market is closed; read again later. `SUBSCRIPTION_CONFLICT`: another call for the same symbol ran at the same time; read again, one call at a time. Either way the symbol has no price in this answer: say so.

A row can also come with prices and no `error` while its market is closed, and then carries the `timestamp` of its last quote, which can lie more than a day before the read: a row's `timestamp` is the time of its quote, not of the read. Give each quote with the time of its `timestamp`. When that time lies well before the current time, or well before the newest `timestamp` among the rows of the same read, as hours or days do, say that the price is the market's last quote, given at that time, and not a current price.

## Trend bars

`period` takes the values of its schema enum; when the user asks for a period the enum lacks, offer the nearest valid one.

Each bar carries `timestamp`, `open`, `high`, `low`, `close` and `volume`; `timestamp` is the time the bar opens. A bar's `volume` is the number of ticks of its period, a count, as the cTrader Help Centre gives it: give it as read, and never divide it by 100 or turn it into units or lots. A `D_1` bar opens at the start of the symbol's trading day, which can fall on the evening of the previous calendar date in UTC, for example at 21:00Z or 22:00Z, and the hour can differ between the bars of one answer; a `W_1` bar and an `MN_1` bar can be stamped on such an evening too, and an `MN_1` bar also on an evening when no trading day starts. Take the boundary from the `timestamp` of the bars themselves, and name such a bar by the period it opens, never by the UTC date of its `timestamp`. Name a daily bar by the trading day it opens: a bar stamped in the evening holds the next calendar date. Name a `W_1` bar stamped on a Sunday evening by the week that starts the next day, and an `MN_1` bar stamped on the evening of the last day of a month by the month that starts the next day: the bar stamped on the evening of 31 October is the November bar. A window returns each bar whose period overlaps it, so a window of one UTC calendar day can return two `D_1` bars, of which the bar of that date is the one stamped the evening before.

`get_trendbars` returns at most `count` bars counted back from `toTimestamp` (default and cap in its schema) and no `hasMore`; a window holding more bars comes back with the newest ones. `count` trims the window and never widens it. Without `fromTimestamp` the window is the span before `toTimestamp` that the description of `fromTimestamp` gives as its default, so a call for 100 `D_1` bars brings only the daily bars of that span. Fewer bars than `count` means the window ended, not the history: read older bars with further calls. Over a long range, request `count` at its cap, move `toTimestamp` back to the oldest bar returned (the bound is inclusive), drop the repeated bar, and repeat until the range is covered or a call brings no new bar, as when the range begins in a market closure. Keep each window within the span its schema allows, splitting a longer range into such windows; a wider window is refused with a message that names the limit.

The last bar of an answer can be the bar of the period still in progress: a call with no `toTimestamp`, or with a `toTimestamp` at or after the time that bar opens, can return it, and its `close` and `volume` can differ from one read to the next. Give the last bar with the period it holds, by its opening time or, for a `D_1`, `W_1` or `MN_1` bar, by its name. A last bar is shown finished when its period has ended by the current time or, without a current time, by the newest `timestamp` among the `get_spot_prices` rows read with it, as Timestamps describes: a period shorter than a day has ended one period after the bar's `timestamp`, and the period of a `D_1`, `W_1` or `MN_1` bar once the day, week or month the bar is named by has ended in UTC. Answer a question that names an hour, day, week or month from the bar that holds that period, never from a bar picked by its place in the answer. A last bar that is not shown finished still answers a question about the period it holds or about the latest bar: read the quote of its symbol with the bars, give the bar as the bar at the time of the read, and say that it can still change while its period lasts or, when that quote is the last quote of a closed market, as Quotes describes, that the market has had no quote since the time of that quote. Where the session gives no time of day, add that the current time would show whether that bar is finished. Where the question asks for a period's close or another value that must come from a finished bar, give the bar before that last bar as well, name each of the two by its period, and say that the earlier bar is finished and the last bar is not shown finished; a read with a `toTimestamp` that lies before the opening time of the last bar ends with the earlier bar. A figure computed over several bars names the bar it ends with: it either includes a last bar that is not shown finished, saying that the bar is included as it stood at the read, or leaves that bar out and reads one bar more so that the count holds.

## Positions and orders

`get_positions` takes no input and returns every open position and pending order. Read one position with `get_position_details {"positionId": <position-id>}`. The protection orders of a position appear in neither `get_positions` nor `get_pending_orders`: read its protections from the position.

Read a position's protections from `stopLoss` and `takeProfit` when present: a removed leg is an absent key, not null or zero.

A position whose `positionStatus` is `POSITION_STATUS_CLOSED`, with no `openTimestamp` and no deals, never opened: its order was canceled, rejected or expired before any fill. Do not report it as a closed trade. `positionStatus` `POSITION_STATUS_CREATED` means the position's pending order has not filled: its volume is 0 and there is nothing to close or amend. `POSITION_STATUS_ERROR` means the opening order failed. Report neither as an open position nor as a closed trade.

A position's full commission is `commission + closedCommission` and its full swap `swap + closedSwap`.

Positions carry no `unrealizedPnl`, and no `grossProfit` or `netProfit` before a first close. Estimate the floating profit from the current quote (value / 100000; the bid for a buy, the ask for a sell), `entryPrice` and the volume in base units (volume / 100), and call it an estimate. The result is in the quote currency of the symbol, taken from `get_assets` as the symbols section says: when that is the account currency, it needs no conversion; otherwise convert it to the account currency with `conversion_rate.py compute-chain --from-asset <quote-currency> --to-asset <account-currency> --quotes <quotes>` (`trading-math.md`), with the quotes the symbols section names. `grossProfit`, `netProfit`, `closedCommission` and `closedSwap` are realized totals: they appear once any part of the position is closed, so an open position after a partial close carries them too. Report them as the realized result of the closed part, apart from the estimate.

## Deals and order history

Page `get_deals` backwards: after each page, set `toTimestamp` to the smallest `executionTimestamp` in the page (a page is not strictly ordered by it), read again, and drop deals already seen by `dealId`; stop when `hasMore` is false. When a page brings no new `dealId` while `hasMore` is true, repeat with a larger `maxRows` (cap in the schema).

The window does not filter on `executionTimestamp` exactly; a deal executed near a bound can fall on either side, so let windows overlap and dedupe by `dealId`.

Report `dealStatus` as the deal returns it.

`get_deals` lists executions, those that opened positions among them: a deal that closed all or part of a position reads `closing` true and carries `closePositionDetail`, and a deal that opened a position reads `closing` false. Count closed trades and total results from the closing deals. A deal's `tradeSide` is the side of its execution, so the deal that closes a long position reads `SELL`.

`closePositionDetail` holds `entryPrice`, `closedVolume` (in the unit of `volume`, as the volume section says), `grossProfit`, `swap`, `commission`, `netProfit`, `balance` and `moneyDigits`, and `stopLoss` and `takeProfit` when the position had them. Take a closed trade's result from `closePositionDetail.netProfit` of its closing deals: it is `grossProfit` + `swap` + `commission` of that `closePositionDetail`, with costs as negative numbers, so the deal-level `commission` is not added to it.

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
2. When step 1 returned no position and no order, call no `get_symbols` and report that the account holds no position and no pending order. Otherwise call `get_symbols` with `symbolIds` for the `symbolId` of every row, unless the session keeps those rows, and name each position and pending order by the `symbolName` of its `symbolId`: the rows carry `symbolId` and no name.
3. For each position, call `get_position_details` and read its protections from `stopLoss` and `takeProfit` and its Advanced Take Profit levels from `advancedTakeProfit` of the `position` object.
4. Report each position by its `positionStatus`, with its size from `volume` in units and in lots as the volume section says: never report a created, failed or never-opened position as open or as a closed trade.
5. Scale money with the position's own `moneyDigits`, give the floating profit only as an estimate, and give the realized totals of a partly closed position apart from it.
6. Report each pending order from its row of step 1 by its symbol, `tradeSide`, `orderType`, its size from `volume` in units and in lots, as the volume section says, never as the raw `volume` alone, `limitPrice` or `stopPrice`, its protections, its Advanced Take Profit levels from `advancedTakeProfit`, which `get_positions` and `get_pending_orders` return for an order as stored, and its expiry from `expirationTimestamp` and `timeInForce`, shown in the user's time zone. Read the protections a row carries: `stopLoss` and `takeProfit` as prices, and `relativeStopLoss` and `relativeTakeProfit`, when the row carries them, as distances from the fill price in the unit `SKILL.md` defines (value / 100000). For a row with none of the four, say that the read shows no stop loss and no take profit and that an order placed with distances can read back without them; never tell the user that the order has none. Give each level's price from `takeProfit`, or, for an order whose levels were sent as distances, its `relativeTakeProfit` as a distance from the fill price (value / 100000), and its `volume` in units and in lots. For a STOP_LIMIT order, say that its limit cannot be read back, since no answer or read returns `slippageInPoints` (`remote-trading.md`).

## Recipe: history and bars over a long window

1. Split the range into windows within the span each tool's schema allows.
2. For bars, page each window back from `toTimestamp` with `count` at its cap, as the trend bars section says, and drop repeated bars.
3. For deals, page each window backwards by `executionTimestamp`, let windows overlap, and dedupe by `dealId`, as the deals section says.
4. For orders, read `get_order_history` per window; when it answers `hasMore` true, narrow the window and dedupe by `orderId`.
5. Group deals by `positionId`. Each closing deal carries the volume of its own part in `closePositionDetail.closedVolume`. When the deals read hold the opening deal or deals of a `positionId`, those reading `closing` false, and the `closedVolume` of its closing deals adds up to the `filledVolume` of those opening deals, the sum of `closePositionDetail.netProfit` of its closing deals, scaled by their `moneyDigits`, is the result of its round trip. When the closed volume is smaller, the position is still open in part or closes after the range: present the sum as the result of the closes so far and say so. When the deals read do not hold the opening deal, read further back until they do, or present the sum as the result of the closes inside the range and say so.

## Recipe: pre-trade snapshot

1. Call `get_session_status` and report the environment (demo or live) and the profile.
2. Call `get_balance`, scale the balance by `moneyDigits`, and name the currency through `get_assets`.
3. Call `get_symbols` with `names` for the symbols of the task, unless the session keeps their rows, for the `symbolId` map, `digits` and `enabled`, each symbol's row taken by its `symbolName`; then call `get_spot_prices` by `symbolName`, match its rows through that map by `symbolId`, divide each value of a row without `error` by 100000, give each quote with the time of its `timestamp` as Quotes describes, and report a requested symbol without a row, or with `error`, as without a price, and a symbol whose row has `enabled` false as not enabled for trading.
4. Call `get_trendbars` with `count` for the recent bars; the last of them can be the bar still in progress: present it as Trend bars describes. Fewer bars than `count` means the default window ended; older bars take further calls, as Trend bars describes.
5. Call `get_positions` for the open positions and orders, and read each position's levels from `get_position_details`.
6. Say that the snapshot holds no commission or swap rate, because no tool serves one.

## Recipe: cost comparison by spread

1. Call `get_symbols` with `names` for the symbols compared, unless the session keeps their rows, for the `symbolId` map and each symbol's `quoteAssetId`, each symbol's row taken by its `symbolName`; then call `get_spot_prices` once for those symbols, match its rows through that map by `symbolId`, and name a symbol without a row, or with `error`, as without a price.
2. Take each spread as (ask - bid) / 100000, the spread at the row's `timestamp`, and say beside the figures that the spreads are those of the quotes read, each at its `timestamp`, never the symbols' usual costs. A row whose `timestamp` lies well before the current time or the newest `timestamp` among the rows read, as Quotes describes, gives the spread of the market's last quote: say so beside its figure, with that time, and do not present it as a cost of trading now.
3. Take the spread cost of a size as spread x volume / 100, in the quote currency of the symbol, the `get_assets` name of its `quoteAssetId` as the symbols section says. When that is the account currency, the cost needs no conversion; otherwise convert it to the account currency with `conversion_rate.py compute-chain --from-asset <quote-currency> --to-asset <account-currency> --quotes <quotes>` (`trading-math.md`). Read the linking quote the symbols section names in the call of step 1, or in a call of its own, and pass it in `--quotes`; when the script exits with code 4, give the cost in the quote currency, named as such.
4. Leave commission and swap out of the comparison and say so: no tool serves their rates.
