# Trading math

The layer file of the connected server is its data file and its trading file: `remote-data.md` and `remote-trading.md` for the Remote server, `local-data.md` and `local-trading.md` for the Local server.

## Pips, pip size and distances

A distance in pips is a price distance divided by the symbol's pip size. Give pip distances only where the symbol's pip size is known; otherwise state distances in price.

`pip_math.py` works on display prices on both servers:

- `pips-to-price` takes `--reference-price`, `--pips` (decimals allowed), `--pip-size`, `--digits`, `--side` (`buy` or `sell`) and `--direction` (`sl` or `tp`). A buy's take profit and a sell's stop loss lie above the reference price, a buy's stop loss and a sell's take profit below it. It prints `absolute_price` rounded to `--digits`, because a price may carry at most `digits` decimals; `rounded` tells whether rounding moved the level, and when it did, `unrounded_price` gives the exact one.
- `price-to-pips` takes `--reference-price`, `--price` and `--pip-size` and prints `pip_distance`, the exact distance in pips.
- `distance` takes `--pips` with `--pip-size`, or `--price-distance`, together with `--digits`, and prints `price_distance`, `relative` (the distance in 1/100000 of price) and `points` (the distance in units of 10^-digits). Where an order field of the connected server takes a distance in one of these units, its layer file names the field. A `relative` that is not a whole multiple of 10^(5 - digits) is refused with exit code 2, and the refusal names the two nearest valid distances.

Each worked call in this file gives the `python3` form for macOS and Linux, then the `python` form for Windows, then the line the script prints; `<skill folder>` is the folder that holds SKILL.md. The inputs illustrate values read from the connected server, as the layer file describes, and are not the configuration of any symbol.

A sell's stop loss 32.8 pips above a reference price of 3588.25, with pip size 0.01 and `digits` 2:

```text
python3 <skill folder>/scripts/pip_math.py pips-to-price --reference-price 3588.25 --pips 32.8 --pip-size 0.01 --digits 2 --side sell --direction sl
python <skill folder>/scripts/pip_math.py pips-to-price --reference-price 3588.25 --pips 32.8 --pip-size 0.01 --digits 2 --side sell --direction sl
{"absolute_price":3588.58,"pip_size_used":0.01,"rounded_to_digits":2,"rounded":true,"unrounded_price":3588.578}
```

The distance from a reference price of 1.0850 to a price of 1.08172, with pip size 0.0001:

```text
python3 <skill folder>/scripts/pip_math.py price-to-pips --reference-price 1.0850 --price 1.08172 --pip-size 0.0001
python <skill folder>/scripts/pip_math.py price-to-pips --reference-price 1.0850 --price 1.08172 --pip-size 0.0001
{"pip_distance":32.8,"pip_size_used":0.0001}
```

A distance of 30 pips with pip size 0.0001 and `digits` 5:

```text
python3 <skill folder>/scripts/pip_math.py distance --pips 30 --pip-size 0.0001 --digits 5
python <skill folder>/scripts/pip_math.py distance --pips 30 --pip-size 0.0001 --digits 5
{"price_distance":0.003,"relative":300,"points":300}
```

## Position size from risk

Take the lot size from the connected server's rule for the symbol; never fall back to the forex figure. The lot size, the volume unit, the grid and the form of the stop distance come from the layer file of the connected server.

`position_sizing.py` sizes a position from a risk target. `from-risk-percent` takes `--balance` and `--risk-pct`; `from-risk-amount` takes `--risk-amount`. `position_sizing.py --balance` takes the balance in account currency; `--risk-amount` is in account currency as well.

- The stop distance takes one of two forms: `--sl-pips` (decimals allowed) with `--pip-size`, or `--price-distance`, the difference between the entry price and the stop price. Giving both, or `--sl-pips` without `--pip-size`, is refused with exit code 2.
- `--conversion-rate` is required. It is the price of one unit of the quote currency in the account currency, 1 when the two are the same currency; a call without it is refused with exit code 2.
- `--lot-size` is required. It only expresses the size in lots: the size in units is the risk divided by the stop distance in price times the conversion rate, so no lot size enters it.
- The output gives `units` and `lots` exactly; `cents`, the size in 1/100 of the base asset (units times 100, rounded down to a whole number so the risk stays at or below the target, with `cents_rounded_down` true when that rounding changed it); and `risk_currency_amount`, the risk at `units`.
- Where the connected server serves a volume grid, `--min-volume`, `--max-volume` and `--volume-step`, given together in units, add `on_grid`, `within_limits` and the nearest grid sizes `below` and `above`, each with its units, lots and risk, or `null`. Nothing is rounded to the step or clipped: a size off the grid goes to the user.

A balance of 5000 in the account currency, 2 percent risk, a stop 100 pips away with pip size 0.01, the quote currency equal to the account currency, and a lot size of 100:

```text
python3 <skill folder>/scripts/position_sizing.py from-risk-percent --balance 5000 --risk-pct 2 --sl-pips 100 --pip-size 0.01 --conversion-rate 1 --lot-size 100
python <skill folder>/scripts/position_sizing.py from-risk-percent --balance 5000 --risk-pct 2 --sl-pips 100 --pip-size 0.01 --conversion-rate 1 --lot-size 100
{"units":100,"lots":1,"cents":10000,"cents_rounded_down":false,"risk_currency_amount":100}
```

The same stop given as a price distance of 1.00:

```text
python3 <skill folder>/scripts/position_sizing.py from-risk-percent --balance 5000 --risk-pct 2 --price-distance 1.00 --conversion-rate 1 --lot-size 100
python <skill folder>/scripts/position_sizing.py from-risk-percent --balance 5000 --risk-pct 2 --price-distance 1.00 --conversion-rate 1 --lot-size 100
{"units":100,"lots":1,"cents":10000,"cents_rounded_down":false,"risk_currency_amount":100}
```

## Margin and tiers

A margin the connected server calculates outranks the formula below. Where a tool of the connected server calculates the margin of a planned order, its layer file names that tool: compare the estimate with the server's figure, and report the server's figure.

`tiered_margin.py compute` estimates margin under dynamic leverage from tiers the user supplies, since no tool of either server serves them; they come from the broker's leverage table. The estimate follows the script's tier model, which is not the server's own calculation:

- `--volume-base-units` is the size in units of the base asset (decimals allowed), and `--quote-rate-usd` the display price of one base unit in USD; their product is the notional in USD.
- `--tiers` is a JSON list of tiers in ascending order, each with `upper` (the notional in USD up to which the tier applies, `null` for the last tier) and `leverage`.
- The script fills the tiers in order with the notional, divides the part in each tier by that tier's leverage and adds the parts. It prints `margin_usd`, `margin_account_ccy`, `account_currency`, `account_currency_rate_vs_usd`, `per_tier_breakdown` and `notional_usd`; `--account-currency` and `--account-currency-rate-vs-usd` (the amount of account currency one USD buys) set the account-currency figure. The rate is required when the account currency is not USD, and for a USD account, given or by default, it is 1: any other rate is refused with exit code 2.

A size of 1,000,000 base units at 1.21345 USD each makes a notional of 1,213,450 USD. With an illustrative curve of 1:500 up to 1,000,000 USD, 1:200 up to 5,000,000 USD and 1:100 above, the margin is 1,000,000 / 500 + 213,450 / 200 = 3,067.25 USD:

```text
python3 <skill folder>/scripts/tiered_margin.py compute --volume-base-units 1000000 --quote-rate-usd 1.21345 --tiers '[{"upper":1000000,"leverage":500},{"upper":5000000,"leverage":200},{"upper":null,"leverage":100}]'
python <skill folder>/scripts/tiered_margin.py compute --volume-base-units 1000000 --quote-rate-usd 1.21345 --tiers '[{"upper":1000000,"leverage":500},{"upper":5000000,"leverage":200},{"upper":null,"leverage":100}]'
{"margin_usd":3067.25,"margin_account_ccy":3067.25,"account_currency":"USD","account_currency_rate_vs_usd":1.0,"per_tier_breakdown":[{"upper":1000000,"leverage":500,"absorbed_usd":1000000.0,"tier_margin_usd":2000.0},{"upper":5000000,"leverage":200,"absorbed_usd":213450.0,"tier_margin_usd":1067.25}],"notional_usd":1213450.0}
```

## Currency conversion

Money a server returns (balance, equity, free margin, commission, swap, profit) is already in the account currency; convert only figures computed from quotes, such as a pip value or a notional.

`conversion_rate.py compute-chain --quotes` takes a map of display prices keyed by symbol name; `tiered_margin.py compute --quote-rate-usd` takes one display price. The layer file of the connected server says how to read display prices from its quotes.

- `compute-chain` takes `--from-asset` and `--to-asset`, and `--quotes` with each value a price or an object with `bid` and `ask`; `--side` picks `bid`, `ask` or `mid` (the default) of such an object.
- It finds the shortest chain of quotes from one currency to the other, within `--max-hops`, and prints `rate`, `chain`, `hops` and `warnings`.
- When no chain links the two currencies, the script refuses with exit code 4 and prints no `rate`: a missing chain is never a rate of 0.

Converting EUR to GBP with a quote given as bid and ask:

```text
python3 <skill folder>/scripts/conversion_rate.py compute-chain --from-asset EUR --to-asset GBP --quotes '{"EURGBP":{"bid":0.83785,"ask":0.83785}}'
python <skill folder>/scripts/conversion_rate.py compute-chain --from-asset EUR --to-asset GBP --quotes '{"EURGBP":{"bid":0.83785,"ask":0.83785}}'
{"rate":0.83785,"chain":["EURGBP"],"hops":1,"warnings":[]}
```

## P&L of a closed trade

A closed trade's net figure already contains its commission; the layer file says whether it contains the swap as well. The result of a round trip is the sum of the net figures of its closing steps, read as the layer file describes; add no commission back.

## Hedging and netting

Before an order opposite an open position, ask the user whether the account hedges or nets, unless a tool of the connected server states it. After the first opposite order on an account that does not hedge, read `get_positions` and report what it shows.

## Margin level and stop-out

Margin level is equity minus the estimated closing commission, divided by the used margin, as a percentage. Take the used margin a margin level needs from a tool of the connected server; where no tool serves it, say that the margin level cannot be given.

The broker alone sets the stop-out level, and no tool serves it: name no level. The cTrader Help Centre documents two stop-out types: fair closes the position with the largest margin in full, and smart closes part of that position, rounded up to the symbol's volume step.

## Swap

Read swap from the positions and closed trades the server returns; the layer file names the fields. The broker applies swap rates and sets, per symbol, the weekday that charges three days of swap at once, covering the weekend. Name no rollover time and no weekday.
