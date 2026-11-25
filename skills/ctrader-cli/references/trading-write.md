# Orders, positions and alerts that change state

## The authorization gate

These order, position and alert commands change the account: `order place-market`, `order place-limit`, `order place-stop`, `order place-stop-limit`, `order modify`, `order cancel`, `position close`, `position close-partial`, `position modify`, `alert create` and `alert delete`. Run one only when both of the following hold:

- The user has authorized this exact action. Authorization to trade in general does not count, and neither does authorization given earlier for a different order, position or symbol.
- The target account reads `"Live": false` in batch `accounts`, read just before the command and not taken from an earlier read. State-changing commands go only to such an account, never to a live one.

`--yes` and `-y` skip confirmations; `-q` (`--quick`, `--quit`) exits after the first command; `--all` targets every applicable entity of `stop`, `order cancel`, `position close`, `alert delete`. With `-q` a command that asks for confirmation can run without asking, and can then print the line `Confirmed automatically in quick mode (-q).`; the read-back after the command shows whether it ran. On a launch line never add a trailing `yes`: builds read it differently, and it can end the command with exit 1 or confirm it.

Never run a state-changing command to discover how it behaves. To learn an option's form or a result's fields, read `--commands`, `--help`, this file or a read command instead of a trial change on the account.

## Before and after every state-changing command

Before:

1. Run `ctrader-cli --help` before the first state-changing command of the session, and `ctrader-cli --commands` with it: `--help` prints the named options of your build and `--commands` its command words. Build the command line from those command words and named options, spelled exactly as printed; on an order, position or alert command give every argument as its named option, while `run` takes the `.algo` path, and a `.cbotset` file when one is used, as its first arguments; never build the line from memory or from another command.
2. Check each option on the line against the options `--help` printed: name, hyphens, letter case. Correct or remove any option that listing does not hold before the command runs. For `run`, a `--<PropertyName>=` override is checked against the `PropertyName` values `metadata` reports instead (case kept).
3. Put `--account=<account>` on the line, with the number whose `accounts` entry you have just read as `"Live": false`. Read it with batch `accounts` (without `-q`): `accounts -q` carries no `Live` key.
4. Read the instrument with `symbol --symbol=<name>` and the state you are about to change with `orders`, `positions` or `alerts`, each with `-q` like every read on the shell route. Before a placement that is the list the new order, position or alert will join, so that the read-back shows what the command added. Write down the values you expect afterwards: side, volume, prices, stop loss, take profit, alert level and message.
5. On the state-changing command, add `-q`, `--quick`, `--quit`, `--yes`, `-y`, `all` or `--all` only after the user has authorized this exact action. Any of them can let the command run. Never add a trailing `yes` on a launch line: builds read it differently. Before each state-changing command, tell the user what it does: for a placement the symbol, side, volume, prices and levels; for a modify, what it sets and what it keeps; for a cancel or a close, which order or position it is: an order by symbol, side and price, a position by symbol, side and entry price; for a delete, which alert. Do it also when the user's message already authorized the exact action and nothing is asked again. For an order with a stop loss or a take profit, say there that a level which does not apply is set to the authorized value at once (step 8).

After:

6. Find the output line that names the account the command used (`Using account: #<account> ...` or `Using your only account: #<account> ...`) and check that it is the number you passed. The line can be missing, as on a command that ends in invalid usage; read back all the same.
7. Read the entity back on the same account, with the read of step 4, and compare every value you set with what you wrote down. A value that reads back empty, at its default, or different means an option did not apply.
8. When a stop loss or take profit the user authorized did not apply, set exactly that level at once with the matching modify command and tell the user, with the read-back before and after. Any other value that differs from what you wrote down, such as the volume, the price, the side or an alert level, waits for the user: report it and change nothing. Do not repeat the original command: it would open a second order or position. The modify call follows the same steps; the section on protection levels says what `0` or an omitted level does on modify.

Steps 1 and 2 prevent a dropped option; steps 6 and 7 detect one that slipped through, because under `-q` the command itself gives no sign.

For a market order, step 7 checks that each level the user authorized is present and on the expected side, because the CLI sends market-order levels as distances in pips (see "Order types and their options").

Never run a state-changing command without `--account`. If one ran without it, read the account line (step 6), read back on that account, and tell the user which account the action reached.

## Spelling options

With `-q`, commands that use a trading account (`price`, `alerts`, `positions`, `order` and the other trading and data commands) skip an option they do not recognize, without a message, and run with the options they recognize. A misspelled optional option is left out: an order placed with `--stoploss=` instead of `--sl=` opens without a stop loss, and `--volume-typ=lots` leaves the volume in units. A misspelled required option still stops the command with a message naming it, such as `Error: 'order' is required. ...` for `--order-id=`. On the batch route an unknown option stops the call with exit 1 and an `Error:` line that names it, such as `Error: Parameter <name> is not allowed` or `Error: Unknown command line parameters found: <name>`; match the `Error:` prefix and the name, not the whole line.

The options that name the target are `--order=<order-id>` for `order modify` and `order cancel`, `--position=<position-id>` for `position close`, `position close-partial` and `position modify`, and `--alert=<alert-id>` for `alert delete`.

## Order types and their options

`order place-market` takes `--symbol`, `--side=buy|sell` and `--volume`. `order place-limit` adds `--price=<limit price>`; `order place-stop` adds `--stop-price=<stop price>`; `order place-stop-limit` adds `--stop-price` and `--limit-range=<pips>`, the slippage in pips allowed once the stop triggers (`0` fills at market on the trigger). `--sl` and `--tp` are optional on every type. `--limit-range` is a distance in pips; every other price option is a price. In the `orders` read-back, a stop or stop-limit order can show the stop price as `targetPrice` and the range as `slippagePips`, with `limitPrice` the price the range allows; compare by the field names your result carries.

`order modify` moves the entry of a pending order with `--price=<price>`: the limit price of a limit order, the stop price of a stop or stop-limit order. Read the order back to see that the entry moved.

A full line takes this form, with every value read and authorized first:

```text
order place-limit --symbol=<name> --side=buy --volume=<units> --price=<limit price> --sl=<price> --tp=<price> --account=<account> -e -q
```

For `order place-market`, `--sl` and `--tp` are prices as on every other type, and the CLI turns them into distances in pips when it submits the order. The command can print a `Warning:` line about this conversion before the order summary; the order is still placed, so read it back.

## Volume

`--volume` is interpreted in units unless you say otherwise: `--volume-type=lots` reads it in lots, and `--volume-type=units` or no `--volume-type` at all reads it in units. Before choosing a volume, read `lotSize`, `minVolume`, `maxVolume` and `volumeStep` with `symbol --symbol=<name>`. They are per-symbol values that the connected server returns, not fixed constants, and they are what you check a volume against.

In `position close-partial --position=<position-id> --volume=<value>`, `<value>` is in units unless `--volume-type=lots` is added. The summary line can state the amount in units and in lots: check it. Closing the whole remainder this way can still answer `partially_closed`, so read `positions` to see what is left.

## Protection levels

On `order modify` and `position modify`, an option you leave out keeps its current value. On `order modify`, `--sl=0` can remove the stop loss; the summary line then shows `SL=remove`. Read the order back to confirm both.

`order modify` can refuse a stop loss on the wrong side of the order's price: it prints a `Warning:` line and `Error: SL/TP is on the wrong side of the reference price. ...`, exits 1, and the order keeps its levels. Read the order back either way, and tell the user which level was refused.

## What the commands return

A state-changing command can print a line restating the command and a summary line, and, when it ran, a JSON object with the id of the entity and a `status` word, such as `{"orderId": <order-id>, "status": "placed"}`, `{"id": <alert-id>, "status": "created"}` or `{"positionId": <position-id>, "status": "opened"}`. Take the id from that object, and confirm the change by reading the entity back, not with the `status` word.

The `status` words and keys above are examples, not a list to match. The empty reads are `{"alerts": []}`, `{"orders": []}` and `{"positions": []}`.

## Alerts

`alert create` takes `--symbol`, `--price`, `--condition=above|below` and an optional `--message=<text>` that labels the alert. An alert compares the symbol's Bid price with its level.

`alert delete` takes `--alert=<alert-id>` for one alert; `--all` targets every alert, an action the user authorizes as such. Follow the steps above for alerts exactly as for orders: read `alerts` before the change, and read it again afterwards to confirm that the new entry carries the level, condition and message you intended, or that a deleted entry is gone.
