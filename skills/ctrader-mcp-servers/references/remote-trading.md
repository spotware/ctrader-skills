# Remote MCP server: trading

## Profiles

`create_order`, `amend_order`, `cancel_order`, `amend_position` and `close_position` exist only on a trading-profile connection: check the profile with `get_session_status`, as `remote-data.md` describes. Each of these calls needs the confirmation `SKILL.md` describes, and the confirmation of an order covers the one corrective call named there.

On a data profile, propose the trade through the link tools (trade links below). To trade directly, the user connects with the Remote MCP token that cTrader Web issues for the trading account.

## Order types

| `orderType` | Price inputs |
| --- | --- |
| MARKET | none |
| LIMIT | `limitPrice` |
| STOP | `stopPrice` |
| STOP_LIMIT | `stopPrice` and `slippageInPoints` |
| MARKET_RANGE | `baseSlippagePrice` and `slippageInPoints` |

A STOP_LIMIT order takes `stopPrice` and `slippageInPoints`, the distance of its limit from `stopPrice` in points of 10^-digits; `limitPrice` is refused on STOP_LIMIT. Every `amend_order` of a STOP_LIMIT carries `slippageInPoints`, and no answer or read returns it: keep the value sent at creation and resend it. For a STOP_LIMIT order placed outside this conversation, ask the user for the distance of its limit from its stop price before any amend, and never send a guessed value: the value sent sets the order's limit. `amend_order` takes only a value above 0, though `create_order` accepts 0. Compute the value with `pip_math.py distance --price-distance <price-distance> --digits <digits>`, which prints it as `points`.

A MARKET_RANGE order needs `baseSlippagePrice` (a display price) and `slippageInPoints`; `baseSlippagePrice` is refused on every other order type.

## Order inputs

`tradeSide` is BUY or SELL, and `volume` is in the unit `SKILL.md` defines, sized as `remote-data.md` says.

`comment` and `label` have a length limit in the schema, counted in UTF-16 code units, so a character such as an emoji can count as several; a longer value is refused, never cut. Both are set at creation only (`amend_order` and `amend_position` take neither) and echoed on the orders and positions the order and position tools return; `label` also appears on the closing orders `close_position` makes. An absent key means the value was never set; an empty string is a stored value.

Set a `clientOrderId` on every `create_order`, within the schema's length limit, and one that no earlier order carries, as `SKILL.md`, step 2, describes: a `create_order` that repeats an earlier `clientOrderId` is answered with that earlier order, and nothing is placed. When a `create_order` call times out or answers `UPSTREAM_ERROR` or `UPSTREAM_UNAVAILABLE`, the order may still exist: call `get_order_by_client_order_id` with that id; on 404 `ORDER_NOT_FOUND`, resend the same request with the same id; when it returns an order, that order exists and nothing is resent. A `create_order` refused with any other code is handled by that code and is never resent unchanged. `label` does not prevent duplicates. Do not send two `create_order` calls with the same `clientOrderId` at the same time: both can be created. For an order not yet filled, the lookup answers `orderId`, `positionId`, `executionType` and `order` and no `position`: read the position with `get_position_details`.

## Protections when placing

MARKET and MARKET_RANGE orders take protections only as `relativeStopLoss` and `relativeTakeProfit`; an absolute `stopLoss` or `takeProfit` there is refused. LIMIT, STOP and STOP_LIMIT orders take absolute `stopLoss` and `takeProfit`, the preferred form, or the relative distances.

`relativeStopLoss` and `relativeTakeProfit` are distances from the fill price in the unit `SKILL.md` defines, never pips. Compute them with `pip_math.py distance`: it prints the value as `relative` and refuses a distance that is not a multiple of 10^(5 - digits). Give it `--price-distance <price-distance> --digits <digits>`, or a distance in pips as `--pips <pips> --pip-size <pip-size> --digits <digits>` only where the symbol's pip size is known; otherwise state the distance in price.

Never send both forms on one side (`stopLoss` with `relativeStopLoss`, or `takeProfit` with `relativeTakeProfit`).

When the user gives the levels of a MARKET or MARKET_RANGE order as prices, send the relative distances that put the levels at those prices from the current quote, so the position opens with its protections. The levels then stand at the fill price minus or plus those distances; moving them to the exact prices is an `amend_position` of its own, confirmed by the user and sent with both legs and every Advanced Take Profit level the position holds.

## Expiration and time in force

An `expirationTimestamp` (an integer in epoch milliseconds) makes the order good till that time; `create_order` refuses it together with any explicit `timeInForce` other than GOOD_TILL_DATE. Send GOOD_TILL_DATE only with an expiration. On `amend_order`, adding one to a GOOD_TILL_CANCEL order makes it GOOD_TILL_DATE, and omitting it removes an existing expiration.

A LIMIT order sent with `timeInForce` IMMEDIATE_OR_CANCEL that cannot fill at once is accepted, reads back as GOOD_TILL_CANCEL and stays working. After any IMMEDIATE_OR_CANCEL order, read `get_pending_orders` and `get_order_history`, report what they show, and ask the user before canceling an order left working.

## What a trading call returns

The answer carries `orderId`, `positionId`, `executionType`, and `order`, `position` and `deal` when they apply. A fill carries all three. An amend or an order not yet filled carries no `deal`, and an order not yet filled already has a `positionId` and a `position` with `volume` 0, which is no open position. The `order` and `position` of an answer do not stand in for the read-back of `SKILL.md`, step 4: read a position's levels with `get_position_details` and a pending order with `get_pending_orders` before the next order-changing call. A refused call answers with the error shape `remote-data.md` describes.

## Protections on a position

On `amend_position`, a protection leg that is omitted is removed. To remove the take profit, send the current `stopLoss` alone; to keep both, send both. Clearing every leg cancels the protection order. `amend_position` takes absolute prices only.

`amend_position` sets the Advanced Take Profit levels it receives: omitting `advancedTakeProfit` removes every level and `[]` clears them. Read the current levels from the `position` object of `get_position_details` first: there they are absolute prices, also for levels sent as relative distances, while the opening order keeps the form it was sent in. Resend them in full, as read, with every amend that keeps them, and tell the user before an amend removes them.

A partial `close_position` can turn the level nearest the main take profit into the new main take profit. Levels are returned as stored and can total more than the open volume: before resending them, total their volumes, and when the total is the position's current volume or more, tell the user that the main take profit cannot then be reached and resend only the levels the user keeps.

## Trailing stop

Send `trailingStopLoss` only when the user asks for a trailing stop, then read the position back with `get_position_details`. Request it with `amend_position {"positionId": <position-id>, "stopLoss": <price>, "trailingStopLoss": true}`; no other tool's schema names the flag. `create_order` accepts the flag without an error, yet no answer or read shows it: send it only on `amend_position`.

Send `trailingStopLoss: true` together with a `stopLoss` in the same `amend_position`: a call without one is refused, even when the position already has a stop loss. Like every `amend_position`, the call also carries the take profit and the Advanced Take Profit levels that stay.

An accepted call answers with `executionType` `ORDER_REPLACED` and the stop loss, and neither that answer nor a position read shows whether trailing is on: report the stop loss the read shows, and tell the user that the trailing state cannot be confirmed.

## Amending a pending order

`amend_order` sets the protections and expiration it receives: omitting `stopLoss`, `takeProfit`, `advancedTakeProfit` or `expirationTimestamp` removes it, even on a price-only amend. Every amend carries the order's price field: `limitPrice` for LIMIT, `stopPrice` for STOP, `slippageInPoints` for STOP_LIMIT; send a STOP_LIMIT amend with its `stopPrice` as well. It accepts absolute or relative protections. Read the order's current values from `get_pending_orders` and resend those that stay; `slippageInPoints` is the one value no read returns, so take it as the STOP_LIMIT paragraph under Order types describes.

`amend_order` takes no side; an order keeps the side it was placed with.

## Closing and canceling

`close_position` requires `volume`: to close in full, send the position's current `volume` from `get_position_details`. `close_position` closes the `volume` it is sent and leaves the rest of the position open. No step rule is stated for the closed volume or for what remains; a volume the server refuses goes to the user (`remote-data.md`). After a partial close, read `takeProfit` and `advancedTakeProfit` back and tell the user when they changed.

`close_position` and `amend_position` on a closed or never-opened position answer 409 `POSITION_NOT_OPEN`: do not retry.

`cancel_order` takes the `orderId` of a pending order.

## Trade links

`create_order_link`, `close_position_link` and `cancel_order_link` return a link the trader opens in cTrader; they place, close and cancel nothing, so never report the action as done. `create_order_link` takes volume in the `create_order` unit (omitted, cTrader prefills its own default size, which can be far larger than intended), `range` in pips (required for stop-limit, optional for market, refused for limit and stop) and `expiry` as an integer in epoch milliseconds. Put a buy's stop loss below the entry and its take profit above it, a sell's the other way round: a level on the wrong side leaves the link unplaceable in cTrader.

Pass `volume` to `create_order_link` whenever a size was discussed; without it, tell the trader to set the volume in cTrader before pressing Place. The link carries the account of this connection, and cTrader switches to that account first; when the result says the account number is unavailable, tell the trader to check the active account in cTrader before pressing Place.

`range` is a count of pips: pass a range the user gave in pips, and turn a price distance into pips only where the symbol's pip size is known. A stop-limit link cannot be built without `range`, so when neither holds, ask the user for the limit range in pips, or for the symbol's pip size, before building the link. Leave `range` out of a market link in that case.

## Recipe: open a position

1. Call `get_session_status` and `get_positions`. When a position of the same symbol is open on the other side, ask the user whether the account hedges or nets before anything is built, as the Hedging and netting section of `trading-math.md` describes: no Remote tool serves the mode. Without such a position, do not ask. On a data profile, propose the trade with `create_order_link` instead, as the trade links section says.
2. Size the order from the sizing inputs below and `trading-math.md`, and say which lot size the size rests on.
3. Build the `create_order` call: a `clientOrderId` no earlier order carries, looked up with `get_order_by_client_order_id` as `SKILL.md`, step 2, describes, the price inputs of the order type, protections in the form the order type takes, and every price rounded to the symbol's `digits`.
4. Show the user the exact call and confirm it as the rules for order-changing calls in `SKILL.md` describe, including that a confirmed stop loss or take profit the read-back lacks is set at once.
5. Send `create_order`. When it times out or answers `UPSTREAM_ERROR` or `UPSTREAM_UNAVAILABLE`, look the order up by its `clientOrderId` before anything is resent.
6. After the fill, read the position with `get_position_details`, also when the answer of `create_order` shows it; a protection the user authorized that is absent is set at once with `amend_position` to exactly that value, as an absolute price (for a level confirmed as a relative distance, the position's `entryPrice` minus or plus that distance / 100000), resending the other leg and every Advanced Take Profit level as read from the position, and reported; anything else waits for the user.

## Recipe: change protections

1. Read the position with `get_position_details`: its `stopLoss`, `takeProfit` and the `advancedTakeProfit` levels of the `position` object.
2. Build one `amend_position` with the new value of each leg that changes, the current value of each leg that stays, and every level that stays, after totaling the level volumes against the current volume.
3. Tell the user which leg or level the call removes, show the exact call, and confirm it as the rules for order-changing calls in `SKILL.md` describe.
4. Send it, read the position back with `get_position_details`, and report what the read shows.

For a pending order, change its protections with `amend_order`, as the section on amending a pending order says.

## Recipe: close all or part, flatten

1. Call `get_session_status`. On a data profile, build `cancel_order_link` for each order and `close_position_link` for each position, and report them as links that cancel and close nothing, the cancel links first: tell the user to open those before the close links, so that no order fills while the positions close.
2. Call `get_positions` for every position and pending order.
3. Show the user the exact list of closes and cancels, and confirm it as the rules for order-changing calls in `SKILL.md` describe.
4. Cancel the orders of that list first, one at a time, so that none fills while the positions close: send `cancel_order`, and read `get_pending_orders` before the next call to see that the order is gone. When the read still lists it, stop there: report the order as still working, and send no further cancel and no close until the user says so.
5. Close the positions one at a time: read the position with `get_position_details`, send `close_position` with its current volume from that read, or with the part the user named, and read `get_positions` before the next call to see that the position is gone, or which volume a part left. Do not retry a 409 `POSITION_NOT_OPEN`.
6. Read `get_positions` again and report what remains. When a closing deal is not yet in `get_deals`, say so and read again before calling it missing.

## Sizing inputs

Scale `get_balance.balance` first: amount = value / 10^moneyDigits.

Give `position_sizing.py` the stop distance as a price distance (`--price-distance`), the difference between the entry price and the stop price; give it in pips with a pip size only where the symbol's pip size is known.

Send the `cents` it prints as `volume`.

Convert each quote with `units_encoding.py quote-to-price` (value / 100000), and name each row through its `symbolId`, before passing it to `conversion_rate.py compute-chain --quotes` or `tiered_margin.py compute --quote-rate-usd`.

Take the lot size for `--lot-size` as `remote-data.md` gives it.
