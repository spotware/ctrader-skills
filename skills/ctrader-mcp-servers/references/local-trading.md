# Local server: trading

## Trading switches and confirmation

An order tool refused with `MCP trading is disabled in settings` means "Allow trading via MCP" is off: ask the user to turn it on. A call answered `User declined` was declined in the app's confirmation dialog and changed nothing; with confirmation on, the app asks for cancels too, and a declined cancel leaves the order working. After either answer, read `get_pending_orders` and `get_positions` before anything else, and send nothing again until the user says so.

## Order tools and inputs

| Tool | Required inputs | Optional inputs |
| --- | --- | --- |
| `place_market_order` | `symbolName`, `side`, `volume`, `volumeType` | `label`, `comment`, `stopLossPips`, `takeProfitPips` |
| `place_limit_order` | `symbolName`, `side`, `volume`, `volumeType`, `limitPrice` | `label`, `comment`, `stopLossPips`, `takeProfitPips`, `expiresAt` |
| `place_stop_order` | `symbolName`, `side`, `volume`, `volumeType`, `stopPrice` | `label`, `comment`, `stopLossPips`, `takeProfitPips`, `expiresAt`, `triggerMethod` |
| `place_stop_limit_order` | `symbolName`, `side`, `volume`, `volumeType`, `stopPrice`, `limitPrice` | `label`, `comment`, `stopLossPips`, `takeProfitPips`, `expiresAt`, `triggerMethod` |

- `side` is `buy` or `sell`, in any letter case.
- `volume` takes the unit `volumeType` names, as the volume section of [local-data.md](local-data.md) describes; check the size first, as [Grid and limits before sending](#grid-and-limits-before-sending) describes.
- `limitPrice` and `stopPrice` are prices; `stopLossPips` and `takeProfitPips` are distances in pips, as [Protections](#protections) describes.
- `place_stop_limit_order` requires `limitPrice`, and the order it places has its limit at the stop price, a limit range of 0, whatever `limitPrice` the call sends: the order fills only at its stop price or better. The Local reads show no limit price and no range. Send `limitPrice` equal to `stopPrice`, so that the call shown to the user states the order as it is placed, and do not ask the user for a limit price for a Local stop-limit placement.
- Before the confirmation of a stop-limit placement, tell the user this and offer the ways that exist: place the order through the Local server with its limit at the stop price; place it in cTrader, where the limit range can be set; or, when the Remote server is connected on a trading profile, place it there, where a stop-limit order takes the distance of its limit from the stop price, as [remote-trading.md](remote-trading.md) describes. A stop-limit request whose limit differs from its stop price is not met by this call, also when the user's message confirmed its steps in advance: tell the user, offer these ways and place nothing until the user chooses one. The confirmation of a Local stop-limit placement names its limit at the stop price and, when the order carries a stop loss or take profit, says that a level which does not apply cannot be set through the Local server afterwards and goes back to the user, since `amend_order` does not change a stop-limit order.
- `expiresAt` is a time in ISO 8601 UTC with `Z`, converted to UTC first when the user gives another zone; ask for the zone when the user names none, show the expiry in the confirmation in the user's zone, and on the read-back compare the `expiration` of the `get_pending_orders` item with it.
- `label` and `comment` stay with the order and its position; give each placement a `label` of its own, as [Repeated requests](#repeated-requests) describes.
- `triggerMethod` takes `trade` (the default) or `opposite`; pass the user's choice. The method is chosen at placement, cannot be changed later and does not appear in the order lists, so keep it from the request.

## Protections

The placement tools and `amend_order` take protections as `stopLossPips` and `takeProfitPips`, distances in pips of the symbol's `pipSize`; `amend_position` takes `stopLoss` and `takeProfit` as prices. The two legs are independent.

`amend_position` changes only the legs it receives; an omitted leg keeps its level. The schema clears a leg with `null` (`"takeProfit": null`). Pass only the legs the user asked to change, never a leg read back as `null`. After the call, read the position back: when a leg the user wanted removed still has a price, or the call was refused, that leg is unchanged; tell the user and offer to set a new level or to remove it in the app. Such a refusal can read `Invalid parameters: positionId must be a number` although `positionId` was a number.

Check a position's new stop loss against the current quote, not the entry: a long position's below the current bid, a short position's above the current ask. A stop loss between the entry and the bid of a long position in profit is accepted and reads back at the price sent, with a positive `stopLossPips`. When the server refuses a level, give the refusal to the user as answered.

A position's pip distances are measured from its `entryPrice`. To turn a distance in pips into the price `amend_position` takes, run `pip_math.py pips-to-price --reference-price <entry-price> --pips <pips> --pip-size <pip-size> --digits <digits> --side <side> --direction <direction>`, with `--side` `buy` or `sell` and `--direction` `sl` or `tp`.

A pending order's pip distances are measured from its `targetPrice`, on placement and in `amend_order`: the limit price of a limit order, the stop price of a stop order and of a stop-limit order. When the same `amend_order` also sends `entryPrice`, the distances it sends are measured from that new entry price, not from the `targetPrice` read before the call. To turn a level the user gives as a price into the distance a placement tool or `amend_order` takes, run `pip_math.py price-to-pips --reference-price <reference-price> --price <price> --pip-size <pip-size>` with that reference: the `targetPrice`, the new entry price when the call also sends `entryPrice`, or on a placement the `limitPrice` or `stopPrice` sent, the `stopPrice` for a stop-limit order. It prints the distance without a sign, so check first that the level lies on the side of the reference its leg belongs to: a buy's stop loss and a sell's take profit below it, a buy's take profit and a sell's stop loss above it; when it lies on the other side, ask the user before sending.

A market order has no price of its own to measure from. When the user gives the levels of a market order as prices, turn each level into the distance `place_market_order` takes with `pip_math.py price-to-pips`, with the quote of `get_spot_prices` read before the call is shown as the reference, the quote that step 2 of the rules for order-changing calls in SKILL.md checks the request against: the `ask` for a buy and the `bid` for a sell, after the same side check as for a pending order. The confirmation shows each such level as the user's price together with the distance that is sent, and the call sends the confirmed distances as shown: they are not computed again after the user's yes. The position's levels then stand at its `entryPrice` minus or plus those distances, so each can differ from the user's price by the move of the price between that quote and the fill; the confirmation says so. After the read-back, moving a level to the user's exact price is an `amend_position` of its own, confirmed by the user.

`amend_order` does not change a stop-limit order; [Amending a pending order](#amending-a-pending-order) says what to offer instead.

## What order tools return

`place_market_order` answers the `positionId` of the new position and a status; `place_limit_order`, `place_stop_order` and `place_stop_limit_order` answer the `orderId` of the new order and a status. `amend_position`, `close_position` and `close_position_partial` answer the `positionId` of the position they acted on and a status, and the answer of `close_position_partial` also carries a `volume`; `amend_order` and `cancel_order` answer the `orderId` of the order they acted on and a status. `cancel_all_pending_orders` answers a status, and `close_all_positions` a status and a `count`; neither names the positions or orders it acted on. No answer shows the size, prices or protections the position or order now has: read the position or order back.

No Local answer carries a deal status. A refused order arrives as a tool error before any position or order exists; after an accepted call, the read-back is the check.

## Amending a pending order

`amend_order` takes `orderId` and any of `entryPrice`, `volume` with `volumeType`, `expiration`, `stopLossPips` and `takeProfitPips`; an omitted field stays. The schema clears `expiration` and the pip fields with `null`; after such a call, read the order back, and when the field still has a value or the call was refused, it is unchanged: tell the user. It takes no `limitPrice`, `stopPrice` or `expiresAt`.

`amend_order` moves the entry with `entryPrice`; the new level reads back as `targetPrice`, and the pip distances of the order's protections count from it, so the prices of protections the call does not send move with the entry, as [Protections](#protections) describes.

`amend_order` does not change a stop-limit order: whatever fields the call carries, it is refused with `Modify error: slippageInPoints have to be defined`, and the order stays as it was; the tool takes no `slippageInPoints`. So before any call, tell the user that the order cannot be amended and offer what exists: cancel it and place a new stop-limit order, two order-changing calls each confirmed as the rules for order-changing calls in SKILL.md describe, or change the order in cTrader, where the limit range can be set. A new order placed through the Local server has its limit at the stop price again, as [Order tools and inputs](#order-tools-and-inputs) describes, so the offer says so and names the other ways to place it that section gives.

The new order takes the values the user changes and, for the rest, those of the read of the old one: `symbolName`, `tradeSide` as `side`, the size from `volumeInUnits` with `volumeType` `units`, `targetPrice` as `stopPrice`, `stopLossPips` and `takeProfitPips`, `expiration` as `expiresAt`, and `comment`. Its `triggerMethod` comes from the request kept in this conversation or, for an order placed elsewhere, from the user, since no read shows it. It gets a `label` of its own, as [Repeated requests](#repeated-requests) describes.

## Closing and canceling

`close_position` closes the whole position; `close_position_partial` closes the given size and keeps the rest open; keep the closed size and the remainder each at or above `minVolume`. `close_all_positions` (optionally for one symbol) and `cancel_all_pending_orders` act on every match: after either call, read the book back with `get_positions` and `get_pending_orders`, since neither answer names the positions or orders.

`cancel_order` takes the `orderId`. Confirm a cancel by the order's absence from `get_pending_orders`.

## Margin for a planned order

`calculate_margin` takes `symbolName`, `volume` and `volumeType` and answers `buyMargin` and `sellMargin` in the account currency. Use it for the margin of a planned order and compare it with the free margin from `get_balance`. A figure does not show that the size is allowed, so check the grid separately, as the next section describes.

## Grid and limits before sending

Before sending a size, check it in units: with `volumeType` `lots`, units are `volume` × `lotSize`. The size must lie within `[minVolume, maxVolume]` and be a whole multiple of `volumeStep`; use decimal arithmetic. When it is off the grid, do not change it: tell the user the limits and ask for a corrected size, offering the nearest valid sizes in the user's unit with the units next to them. The same check applies to `close_position_partial` and to `amend_order` with a volume.

`units_encoding.py check-volume` makes this check from the size and the `lotSize`, `minVolume`, `maxVolume` and `volumeStep` of `get_symbol_details`: it reports `on_grid`, `within_limits` and, for a size off the grid, the nearest sizes below and above in units and lots, and it changes nothing. Its form is `units_encoding.py check-volume --lots <lots> --lot-size <lot-size> --min-volume <min-volume> --max-volume <max-volume> --volume-step <volume-step>`, with `--units <units>` in place of `--lots` for a size in units.

## Repeated requests

The placement tools take no request id. Give each placement a `label` of its own, and before sending a placement again, read `get_positions`, `get_pending_orders` and `get_order_history` and look for that `label`: an item that carries it shows the first request was placed, also when its position has closed since.

## Recipe: open a position

1. Read `get_accounts_list` for `isLive` and `get_symbol_details` for the symbol, check the size as [Grid and limits before sending](#grid-and-limits-before-sending) describes, and compare its `calculate_margin` figure with the free margin of `get_balance`. When the user gives a level as a price, read the quote with `get_spot_prices` and turn the level into the distance the confirmation shows, as [Protections](#protections) describes.
2. Confirm the order with the user as the rules for order-changing calls in SKILL.md describe, including that a stop loss or take profit which does not apply is set to the confirmed value at once. For a stop-limit order, the confirmation says what [Order tools and inputs](#order-tools-and-inputs) describes in place of that, and the order leaves this recipe after this step, since steps 3 to 5 place a position and set a missing level on it with `amend_position`: send `place_stop_limit_order`, read the order back with `get_pending_orders`, and a protection the user confirmed that reads back `null` goes back to the user, since `amend_order` does not change a stop-limit order. A limit or a stop order leaves this recipe after this step as well: send `place_limit_order` or `place_stop_order`, read the order back with `get_pending_orders` and find it by the `orderId` of the answer, and set a protection the user confirmed that reads back `null` at once with `amend_order`, as the pip distance from its `targetPrice` that [Protections](#protections) describes.
3. Send `place_market_order` with `volumeType`, a `label` of its own and the confirmed `stopLossPips` and `takeProfitPips`; a level the user gave as a price is sent as the distance the confirmation showed, from the quote of step 1, and is not computed again.
4. Read the position with `get_positions` and find it by the `positionId` of the answer.
5. When a protection the user confirmed reads back `null`, set it at once with `amend_position`, which takes prices: where the user gave the level as a price, that price; otherwise the price the confirmed pip distance gives from the position's `entryPrice` (`pip_math.py pips-to-price`). Pass only that leg, read the position back and report it. A level that stands at the confirmed distance from `entryPrice` is not missing, also when it differs from the user's price: moving it to that price is the separate `amend_position` that [Protections](#protections) describes. Anything else that differs waits for the user.

No Local order type bounds a market fill. A buy limit priced above the current ask is refused with a text that points to `place_market_order` and `place_stop_order`, and nothing is created. So when the user wants a bound on a buy, say that a limit order cannot cap a fill at once, and offer a market order or a buy limit below the ask that rests until the price comes down to it; read back what was placed.

## Recipe: change protections

1. Read `get_accounts_list` for `isLive`.
2. Read the position with `get_positions`, or the pending order with `get_pending_orders`, and note its current protection levels. A pending order whose `orderType` reads `StopLimit` leaves this recipe here: go on as [Amending a pending order](#amending-a-pending-order) describes.
3. For a position, express each new level as a price; when the user gave a distance in pips, turn it into a price from `entryPrice` as [Protections](#protections) describes. For a pending order, express each new level as a distance in pips; when the user gave a price, turn it into pips as [Protections](#protections) describes. For a position's stop loss, compare the level with the current quote from `get_spot_prices`: a long position's lies below the bid, a short position's above the ask.
4. Confirm the change with the user as the rules for order-changing calls in SKILL.md describe.
5. For a position, send `amend_position` with only the legs the user asked to change; for a pending order, send `amend_order` with `stopLossPips` or `takeProfitPips`.
6. Read the position or order back and compare each leg with what was sent; when the user gave a level as a price, compare the `stopLossPrice` or `takeProfitPrice` read back with that price. When a leg the user wanted removed still has a price, or the call was refused, tell the user and offer to set a new level or to remove it in the app.

## Recipe: close all or part, flatten

1. Read `get_accounts_list` for `isLive`.
2. Read `get_positions` and `get_pending_orders` for the whole book.
3. Show the user the exact list of positions and orders, and confirm it as the rules for order-changing calls in SKILL.md describe.
4. Cancel the orders of that list first, so that no order fills while the positions close. Send `cancel_order` for one order at a time and read `get_pending_orders` before the next call, to confirm the cancel by the order's absence; when the user asked for everything, send `cancel_all_pending_orders` and read `get_pending_orders` after it, since its answer does not name the orders. When a read still lists an order of that list, whatever the call answered, stop there: report the order as still working, and send no further cancel and no close until the user says so. A cancel the user declines in the app's confirmation answers `User declined` and leaves the order working.
5. Close the positions one at a time, reading `get_positions` before the next call: send `close_position`; when the user asked for everything, send `close_all_positions` and read `get_positions` after it, since its answer does not name the positions. To close part of a position, send `close_position_partial` with a size on the grid, keeping the remainder at or above `minVolume`.
6. Read `get_positions` and `get_pending_orders` again and report what remains.
7. Read the closing deals with `get_deals` and the results with `get_order_history`; the `side` of both is the position's side, not that of the closing execution. A round trip's result is the sum of the `netProfit` of its closing steps, with the swap of a step counted once, as the History section of [local-data.md](local-data.md) describes.

## Sizing inputs on this server

Sizing inputs come from `get_symbol_details` of the symbol: `pipSize`, `lotSize`, `minVolume`, `maxVolume` and `volumeStep`. Pass them to `position_sizing.py` with the stop distance in pips; when its result is off the grid, apply the rule of [Grid and limits before sending](#grid-and-limits-before-sending). The form is `position_sizing.py from-risk-amount --risk-amount <amount> --sl-pips <pips> --pip-size <pip-size> --conversion-rate <rate> --lot-size <lot-size> --min-volume <min-volume> --max-volume <max-volume> --volume-step <volume-step>`; `from-risk-percent` takes `--balance <balance> --risk-pct <percent>` in place of `--risk-amount`, with the balance from `get_balance` as returned. For `--conversion-rate`, take the symbol's quote currency as the Symbols section of [local-data.md](local-data.md) describes, and the account currency from `depositAsset` of `get_balance`; the rate is 1 when the two are the same currency, and otherwise the `rate` of `conversion_rate.py compute-chain` from the quote currency to the account currency, with the quotes the Money handling section of [local-data.md](local-data.md) names. When the script exits with code 4, tell the user that the rate cannot be given, and size the order only from a rate the user gives. [trading-math.md](trading-math.md) explains the rate.
