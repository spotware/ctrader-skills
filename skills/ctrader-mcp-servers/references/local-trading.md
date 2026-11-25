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
- `expiresAt` is a time in ISO 8601 UTC with `Z`, converted to UTC first when the user gives another zone.
- `label` and `comment` stay with the order and its position; give each placement a `label` of its own, as [Repeated requests](#repeated-requests) describes.
- `triggerMethod` takes `trade` (the default) or `opposite`; pass the user's choice. The method is chosen at placement, cannot be changed later and does not appear in the order lists, so keep it from the request.

## Protections

The placement tools and `amend_order` take protections as `stopLossPips` and `takeProfitPips`, distances in pips of the symbol's `pipSize`; `amend_position` takes `stopLoss` and `takeProfit` as prices. The two legs are independent.

`amend_position` changes only the legs it receives; an omitted leg keeps its level. The schema clears a leg with `null` (`"takeProfit": null`). Pass only the legs the user asked to change, never a leg read back as `null`. After the call, read the position back: when a leg the user wanted removed still has a price, or the call was refused, that leg is unchanged; tell the user and offer to set a new level or to remove it in the app. Such a refusal can read `Invalid parameters: positionId must be a number` although `positionId` was a number.

Check a long position's new stop loss against the current bid, not the entry. A stop loss between the entry and the bid of a long position in profit is accepted and reads back at the price sent, with a positive `stopLossPips`. When the server refuses a level, give the refusal to the user as answered.

A position's pip distances are measured from its `entryPrice`. To turn a distance in pips into the price `amend_position` takes, run `pip_math.py pips-to-price --reference-price <entry-price> --pips <pips> --pip-size <pip-size> --digits <digits> --side <side> --direction <direction>`, with `--side` `buy` or `sell` and `--direction` `sl` or `tp`.

## What order tools return

`place_market_order` answers the `positionId` of the new position and a status; `place_limit_order`, `place_stop_order` and `place_stop_limit_order` answer the `orderId` of the new order and a status. No answer repeats the size, prices or protections: read the position or order back. Each write answer names the position or order it acted on and a status.

No Local answer carries a deal status. A refused order arrives as a tool error before any position or order exists; after an accepted call, the read-back is the check.

## Amending a pending order

`amend_order` takes `orderId` and any of `entryPrice`, `volume` with `volumeType`, `expiration`, `stopLossPips` and `takeProfitPips`; an omitted field stays. The schema clears `expiration` and the pip fields with `null`; after such a call, read the order back, and when the field still has a value or the call was refused, it is unchanged: tell the user. It takes no `limitPrice`, `stopPrice` or `expiresAt`.

`amend_order` moves the entry with `entryPrice`; the new level reads back as `targetPrice`, and the order's protections keep their pip distances, so their prices move with the entry.

## Closing and canceling

`close_position` closes the whole position; `close_position_partial` closes the given size and keeps the rest open; keep the closed size and the remainder each at or above `minVolume`. `close_all_positions` (optionally for one symbol) and `cancel_all_pending_orders` act on every match and answer a status or a count, not the items: read the book back.

`cancel_order` takes the `orderId`. Confirm a cancel by the order's absence from `get_pending_orders`.

## Margin for a planned order

`calculate_margin` takes `symbolName`, `volume` and `volumeType` and answers `buyMargin` and `sellMargin` in the account currency. Use it for the margin of a planned order and compare it with the free margin from `get_balance`. A figure does not show that the size is allowed, so check the grid separately, as the next section describes.

## Grid and limits before sending

Before sending a size, check it in units: with `volumeType` `lots`, units are `volume` × `lotSize`. The size must lie within `[minVolume, maxVolume]` and be a whole multiple of `volumeStep`; use decimal arithmetic. When it is off the grid, do not change it: tell the user the limits and ask for a corrected size, offering the nearest valid sizes in the user's unit with the units next to them. The same check applies to `close_position_partial` and to `amend_order` with a volume.

`units_encoding.py check-volume` makes this check from the size and the `lotSize`, `minVolume`, `maxVolume` and `volumeStep` of `get_symbol_details`: it reports `on_grid`, `within_limits` and, for a size off the grid, the nearest sizes below and above in units and lots, and it changes nothing. Its form is `units_encoding.py check-volume --lots <lots> --lot-size <lot-size> --min-volume <min-volume> --max-volume <max-volume> --volume-step <volume-step>`, with `--units <units>` in place of `--lots` for a size in units.

## Repeated requests

The placement tools take no request id. Give each placement a `label` of its own, and before sending a placement again, read `get_positions`, `get_pending_orders` and `get_order_history` and look for that `label`: an item that carries it shows the first request was placed, also when its position has closed since.

## Recipe: open a position

1. Read `get_accounts_list` for `isLive` and `get_symbol_details` for the symbol, check the size as [Grid and limits before sending](#grid-and-limits-before-sending) describes, and compare its `calculate_margin` figure with the free margin of `get_balance`.
2. Confirm the order with the user as the rules for order-changing calls in SKILL.md describe, including that a stop loss or take profit which does not apply is set to the confirmed value at once.
3. Send `place_market_order` with `volumeType`, a `label` of its own and the confirmed `stopLossPips` and `takeProfitPips`.
4. Read the position with `get_positions` and find it by the `positionId` of the answer.
5. When a protection the user confirmed reads back `null`, set it at once with `amend_position`, which takes prices: the price the confirmed pip distance gives from the position's `entryPrice` (`pip_math.py pips-to-price`), or the confirmed price where the user gave one. Pass only that leg, read the position back and report it. Anything else that differs waits for the user.

No Local order type bounds a market fill. A buy limit priced above the current ask is refused with a text that points to `place_market_order` and `place_stop_order`, and nothing is created. So when the user wants a bound on a buy, say that a limit order cannot cap a fill at once, and offer a market order or a buy limit below the ask that rests until the price comes down to it; read back what was placed.

## Recipe: change protections

1. Read `get_accounts_list` for `isLive`.
2. Read the position with `get_positions`, or the pending order with `get_pending_orders`, and note its current protection levels.
3. For a position, express each new level as a price; when the user gave a distance in pips, turn it into a price from `entryPrice` as [Protections](#protections) describes. For a long position's stop loss, compare the level with the current bid from `get_spot_prices`.
4. Confirm the change with the user as the rules for order-changing calls in SKILL.md describe.
5. For a position, send `amend_position` with only the legs the user asked to change; for a pending order, send `amend_order` with `stopLossPips` or `takeProfitPips`.
6. Read the position or order back and compare each leg with what was sent; when a leg the user wanted removed still has a price, or the call was refused, tell the user and offer to set a new level or to remove it in the app.

## Recipe: close all or part, flatten

1. Read `get_accounts_list` for `isLive`.
2. Read `get_positions` and `get_pending_orders` for the whole book.
3. Show the user the exact list of positions and orders, and confirm it as the rules for order-changing calls in SKILL.md describe.
4. Cancel the orders of that list first, so that no order fills while the positions close. Send `cancel_order` for one order at a time and read `get_pending_orders` before the next call, to confirm the cancel by the order's absence; `cancel_all_pending_orders`, when the user asked for everything, answers a status or a count, not the items, so read `get_pending_orders` after it. When a read still lists an order of that list, whatever the call answered, stop there: report the order as still working, and send no further cancel and no close until the user says so. A cancel the user declines in the app's confirmation answers `User declined` and leaves the order working.
5. Close the positions one at a time, reading `get_positions` before the next call: send `close_position`, or `close_all_positions` when the user asked for everything, which answers a status or a count, not the items. To close part of a position, send `close_position_partial` with a size on the grid, keeping the remainder at or above `minVolume`.
6. Read `get_positions` and `get_pending_orders` again and report what remains.
7. Read the closing deals with `get_deals` and the results with `get_order_history`; a round trip's result is the sum of the `netProfit` of its closing steps, with the swap of a step counted once, as the History section of [local-data.md](local-data.md) describes.

## Sizing inputs on this server

Sizing inputs come from `get_symbol_details` of the symbol: `pipSize`, `lotSize`, `minVolume`, `maxVolume` and `volumeStep`. Pass them to `position_sizing.py` with the stop distance in pips; when its result is off the grid, apply the rule of [Grid and limits before sending](#grid-and-limits-before-sending). The form is `position_sizing.py from-risk-amount --risk-amount <amount> --sl-pips <pips> --pip-size <pip-size> --conversion-rate <rate> --lot-size <lot-size> --min-volume <min-volume> --max-volume <max-volume> --volume-step <volume-step>`; `from-risk-percent` takes `--balance <balance> --risk-pct <percent>` in place of `--risk-amount`, with the balance from `get_balance` as returned. [trading-math.md](trading-math.md) explains the conversion rate.
