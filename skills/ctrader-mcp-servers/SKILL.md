---
name: ctrader-mcp-servers
description: Use this skill ALWAYS when working with any cTrader MCP server.
allowed-tools: "Read, Grep, Glob, Bash(python *)"
compatibility: "Requires Python 3.12+ on PATH for the bundled scripts in scripts/. Scripts use the Python standard library only; no third-party packages are required."
license: Proprietary. LICENSE.txt has complete terms.
metadata:
  author: "Spotware Systems Ltd"
  quirks_registry_min_build_remote: "rest-proxy 1.0.18"
  quirks_registry_min_build_local: "local build observed-on 2026-05-14"
  last_full_audit_date: "2026-05-14"
---

## Top-5 critical quirks (inline teaser)

The following 5 quirks are the most consequential as of the audit date. Full Detect / Workaround / Verify-fixed / Removal-criteria content lives in `references/known-quirks.md`; the rows below are link-only teasers. See also `references/self-healing-playbook.md` for the named recovery patterns.

| Quirk | Server | One-liner                                                                                                                     | Link                                      |
|-------|--------|-------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------|
| Q-R10 | remote | `amend_position` omitting a leg REMOVES it (not preserves it)                                                                 | [Q-R10](references/known-quirks.md#q-r10) |
| Q-R4  | remote | MARKET REJECTS absolute SL/TP — use `relativeStopLoss`/`relativeTakeProfit` (single call) or P-REMOTE-MARKET-2STEP (fallback) | [Q-R4](references/known-quirks.md#q-r4)   |
| Q-R1  | remote | `period` enum is 9 values, NOT 26 (delete granular claims)                                                                    | [Q-R1](references/known-quirks.md#q-r1)   |
| Q-L2  | local  | SL is absolute price, TP is raw pips (asymmetric `get_pending_orders`)                                                        | [Q-L2](references/known-quirks.md#q-l2)   |
| Q-K19 | both   | Pipettes vs display foot-gun — silent market fills                                                                            | [Q-K19](references/known-quirks.md#q-k19) |

## Self-healing principle

Both `ctrader-remote-mcp` and `ctrader-local-mcp` ship as-is with documented runtime behaviors last re-verified on 2026-05-14 against `rest-proxy 1.0.18` (Remote) and local build observed-on 2026-05-14 (Local). Six Remote quirks remain ACTIVE on 1.0.18 (Q-R1, Q-R2, Q-R3, Q-R5, Q-R8, Q-R10). Two quirks had their error-message format refined (Q-R4 and Q-R7 now return plain-string error envelopes with actionable hints instead of JSON envelopes — both DETECT signatures cover both formats). One quirk is likely fixed (Q-R11 — `get_deals` propagation lag — passed Verify-fixed on session 1 of 5; not yet removed pending 4 more confirmations). This skill describes SEMANTICS, GOTCHAS, and RECOVERY; the MCP JSON-Schema is the source of truth on SHAPE. Never duplicate schema content in this skill. Every claim about runtime behavior in this skill carries a build-stamp — either an `as-of:` header on a reference file, or an `Observed-on:` line on a quirk in `references/known-quirks.md`.

Every quirk in the ledger is self-deprecating: it carries a `Verify-fixed` probe (a session-local check the agent can run) and a `Removal criteria` condition (the explicit signal that the server has been fixed and the entry should be deleted). When the server is fixed, delete the matching entry from `references/known-quirks.md` — that is the entire cleanup cost. Optional follow-up: `grep` for any stale QUIRK breadcrumbs across the reference files and remove them.

On unexpected server behavior (anything deviating from BOTH the MCP JSON-Schema AND the ledger), do NOT improvise — follow `references/self-healing-playbook.md`. The playbook names the pre-flight gates (quote sanity, side-direction, SL/TP sidedness, volume-step, schema-fields-only, pipettes-vs-display detection, required-fields), the post-flight verification rules (re-read after every mutation; for Remote `amend_position`, always re-read to confirm BOTH SL and TP legs survived per Q-R10), the error-classification matrix (Zod / INVALID_REQUEST / 502 uProxy / plain-text Local / available:false / truncated / hasMore), the unknown-quirk decision tree (4 steps from STOP to provisional ledger entry), and the named patterns (P-AMEND-SAFE, P-REMOTE-MARKET-RELATIVE (preferred for MARKET+SL/TP), P-REMOTE-MARKET-2STEP (fallback for absolute-price SL/TP on MARKET), P-REMOTE-MARKET-RANGE, P-LOCAL-OLDEST-FIRST, P-REMOTE-HISTORY-CHUNK).

## Per-broker overlay extension point

The skill's quirks ledger uses the `Q-B<n>` prefix as a reserved slot for future per-broker overrides (lotSize divergences, symbol-naming variants, broker-specific SL/TP behaviors). A future `assets/broker_overrides.example.json` overlay would carry these per-broker values without restructuring this skill. **NOT shipped this iteration** — added on demand when broker-specific divergences become a blocking class.

## Tool-surface routing: Local HTTP (`ctrader-local-mcp`) vs Remote HTTP (`ctrader-remote-mcp`)

The bound tool surface determines which cTrader MCP server is in front of you. Inspect tool names and response DTO shape to identify the family. Apply the routing rule below at the start of every cTrader-related interaction; cache the result for the session.

| Server family                      | Fingerprint to detect it                                                                                                                                                                                                                                                                      | What it does best                                                                                     | Default routing rule                                                                                                                                    |
|------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------|
| Local HTTP (`ctrader-local-mcp`)   | `ping`, `get_accounts_list`, `list_charts`, `listChartIndicators`, `listPlugins`, `show_notification`, `get_server_time`; volume in units; ISO 8601 with mandatory `Z`; symbol identified by string name (`"EURUSD"`). HTTP transport bound to the cTrader Desktop application.               | Charts, drawings, indicators, watchlists, alerts, news, cBots, UI notifications, multi-account work.  | Route here for any UI / visualization / cBot / chart-bound workflow.                                                                                    |
| Remote HTTP (`ctrader-remote-mcp`) | `get_version`, `get_assets`, integer `symbolId`-keyed tools (`get_spot_prices(symbolId)`, `get_trendbars(symbolId)`); `moneyDigits` field in money responses; volume in cents (1 lot of forex = 10 000 000); prices in pipettes. HTTP transport against the remote REST proxy (`rest-proxy`). | Headless trading, broad symbol scans, trailing stop loss, `MARKET_RANGE`, granular timeframe history. | Route here when no chart / UI need exists.                                                                                                              |
| Both surfaces bound                | Both fingerprints visible.                                                                                                                                                                                                                                                                    | Depends on the action.                                                                                | Pick by capability: drawings / cBots / charts go to Local; trailing SL / `MARKET_RANGE` / multi-symbol batch quotes / granular timeframes go to Remote. |

## Units conventions across the two servers

The two servers encode the same trading concepts in **different units and identifier types**; passing Local values to Remote (or the reverse) silently produces wrong sizes, wrong prices, or schema rejections.

| Dimension                                                  | Local HTTP encoding                                                                                                          | Remote HTTP encoding                                                                                                           | Conversion script                                                |
|------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------|
| Volume                                                     | Units (integer; for forex typically 1 lot = 100 000 units, but broker-dependent — always read `get_symbol_details.lotSize`). | Cents (integer; 1 lot of forex = 10 000 000 cents).                                                                            | `scripts/units_encoding.py lots-to-units` / `lots-to-cents`      |
| Price                                                      | Display value (e.g., `1.21345`).                                                                                             | Pipettes (integer; divide by `10^pipDigits` to display).                                                                       | `scripts/pip_math.py` (handles both directions)                  |
| Money (balance, commission, swap, P&L)                     | Display value (e.g., `12345.67`).                                                                                            | Integer in `10^moneyDigits` units (`moneyDigits` field on the response; typically 2).                                          | `scripts/units_encoding.py display-money` / `parse-money`        |
| Timestamp                                                  | ISO 8601 with mandatory `Z` suffix (`2026-01-15T14:30:00Z`).                                                                 | Epoch milliseconds for `expirationTimestamp` (integer-only as of rest-proxy 1.0.13); either form for history window endpoints. | Passed through unchanged for Local; check field type for Remote. |
| Symbol identifier                                          | String name (`"EURUSD"`, `"XAUUSD"`).                                                                                        | Integer `symbolId` (resolve via `get_symbols`, cache for the session).                                                         | N/A (look up by ID)                                              |
| Stop loss / take profit on `place_*_order` / `amend_order` | Pip distance integer (`stopLossPips`, `takeProfitPips`).                                                                     | Absolute price (`stopLoss`, `takeProfit`).                                                                                     | `scripts/pip_math.py pips-to-price` / `price-to-pips`            |

## Stop loss and take profit: pip distance vs absolute price

Order-placement tools take SL / TP as **pip distance from entry**; position-amendment tools take SL / TP as **absolute price**. The convention depends on which TOOL is called, not which server.

| Tool                                                                                    | Server | SL / TP form                                                                                                                                |
|-----------------------------------------------------------------------------------------|--------|---------------------------------------------------------------------------------------------------------------------------------------------|
| `place_market_order`, `place_limit_order`, `place_stop_order`, `place_stop_limit_order` | Local  | Pip distance (`stopLossPips`, `takeProfitPips`).                                                                                            |
| `amend_order` (pending order)                                                           | Local  | Pip distance (`stopLossPips`, `takeProfitPips`).                                                                                            |
| `amend_position` (open position)                                                        | Local  | Absolute price (`stopLoss`, `takeProfit`).                                                                                                  |
| `create_order`                                                                          | Remote | Absolute price (`stopLoss`, `takeProfit`). See `references/remote-http-server.md` for MARKET-order SL/TP rejection (P-REMOTE-MARKET-2STEP). |
| `amend_order`                                                                           | Remote | Absolute price (`stopLoss`, `takeProfit`).                                                                                                  |
| `amend_position`                                                                        | Remote | Absolute price (`stopLoss`, `takeProfit`).                                                                                                  |
| `close_position`                                                                        | Both   | N/A (no SL / TP parameter).                                                                                                                 |

When the user says "SL 30 pips below entry", convert to the form the target tool needs by running `scripts/pip_math.py`. Input: `--pip-size <float> --digits <int> --reference-price <float> --pips <int>`. Output: `{"absolute_price": <float>, "pip_size_used": <float>}`. The script handles both directions.

## Dynamic-leverage margin calculation

Brokers apply **dynamic-leverage tiers**: leverage falls as the exposure grows past tier upper bounds. Required margin is computed PER TIER and summed. Tier exposure volumes are stated in **USD** regardless of the traded symbol; the resulting margin in USD is then converted to the account currency.

> **Example.** Account currency USD. Order: 1 000 000 EURUSD long @ 1.21345. Notional in USD = 1 000 000 × 1.21345 = 1 213 450 USD. Tier curve: 1:500 up to 1 000 000 USD, 1:200 from 1 000 000 to 5 000 000 USD, 1:100 above 5 000 000 USD. Margin = (1 000 000 / 500) + (213 450 / 200) = 2 000 + 1 067.25 = **3 067.25 USD**.

Invoke `scripts/tiered_margin.py compute` to compute this for arbitrary tier curves. Input: `--volume-base-units <int> --quote-rate-usd <float> --tiers '[{"upper":1000000,"leverage":500},{"upper":5000000,"leverage":200},{"upper":null,"leverage":100}]'`. Output: `{"margin_usd": <float>, "per_tier_breakdown": [...]}`. Convert the USD margin to the account currency with `scripts/conversion_rate.py compute-chain`.

## Currency conversion: quote currency vs account currency

When a symbol's quote currency differs from the account currency, every money figure returned by the server (commission, swap, realized P&L, pip value, margin) requires conversion through a **chain of spot rates**. Example chains: P&L on USDJPY for a EUR account requires JPY -> USD -> EUR (using USDJPY and EURUSD); P&L on AUDCAD for an NZD account requires CAD -> USD -> NZD or a direct AUD -> NZD chain. The cTrader backend builds the shortest available chain; replicate that logic locally with `scripts/conversion_rate.py`.

Invoke `scripts/conversion_rate.py compute-chain` to derive the rate. Input: `--from-asset <CCY> --to-asset <CCY> --quotes '{"EURUSD":1.0850,"USDJPY":150.3,...}'`. Output: `{"rate": <float>, "chain": ["EURUSD","USDJPY",...], "warnings": [...]}`. Fetch the quote map up front via `get_spot_prices` for Local (one symbol per call) or `get_spot_prices(symbolId:[...])` for Remote (batched).

## Hedging vs netting accounts

**Hedging accounts** allow simultaneous long AND short positions on the same symbol (each gets its own `positionId`). **Netting accounts** collapse them: opening the opposite side automatically closes (or partially closes) the existing position to the net delta. Before placing the second leg of a hedge, read the existing position and the account's hedging mode (visible in `get_balance` and account-info responses); if the account is netting, "opening a hedge" is impossible — surface this to the user and propose either a stop-loss adjustment or a full close instead.

## Stop-out and margin level

Brokers force-close positions when **margin level = (equity / used margin) × 100%** falls to or below the stop-out level (commonly 50% or 30%, broker-set). Two policies exist: **fair** (closes the single position consuming the most margin) and **smart** (closes the smallest set of positions sufficient to restore margin level above the stop-out). Before sizing additional risk, read current equity and used margin; if `(equity − required_new_margin) / used_margin_after_open × 100%` drops below 2× the stop-out level, warn the user before proceeding.

## Swap accrual timing

Swap (overnight financing) accrues at **broker server time** rollover (commonly 23:59:59 server time). Many brokers **triple-charge** swap on Wednesday (the Wed -> Thu rollover absorbs the weekend value date for T+2 instruments like forex). When projecting swap over a holding period, multiply by 3 for any Wednesday in the window. Read swap and commission values directly from `get_positions` and `get_deals` responses (they are server-computed); do not re-derive them from rate tables.

## Composable trader workflows

Seven end-to-end trader workflows are described step-by-step in `references/trader-workflows.md`. W0 (session bootstrap) auto-runs once at session start; W1–W6 are dispatched by user-intent triggers. When the user request matches any trigger, read `references/trader-workflows.md` and follow the corresponding recipe — do not improvise from scratch.

0. **W0 — Session bootstrap** — auto-runs at session start; identifies server family, probes live build, caches symbol precision baseline from `assets/symbol_precision_table.json`, resolves active account, and sets the idempotency-key prefix. No user trigger needed.
1. **Position sizing by risk %** — select this recipe when the user asks "how much to buy / sell", "size for N pips SL", "risk X% of my account on this trade", or any sentence combining a risk fraction with a stop-loss distance.
2. **Pre-trade briefing** — select this recipe when the user asks "should I trade X", "give me a snapshot of X before I enter", "what does X look like right now", or combines symbol-details + price + recent history requests into one ask.
3. **Cost-of-trading comparison** — select this recipe when the user asks "which is cheaper to trade, A or B", "compare spreads / commissions / swap across symbols", or ranks tradeable instruments by cost.
4. **Place + visualize a trade with risk/reward annotation** — select this recipe when the user asks "place the trade and show it on the chart", "draw the R:R on EURUSD", and the Local HTTP server is bound (this workflow requires drawings).
5. **Multi-window historical backfill** — select this recipe when the user asks for more bars than a single `get_trendbars` call returns (1000 cap on Local), e.g., "give me 5000 H1 candles of XAUUSD" or "show me the last year of D1".
6. **Safe flatten** — select this recipe when the user asks "close everything", "cancel all my orders", "flatten my book", or any request to bulk-close pending orders and open positions on one or more symbols.

## Server-specific reference files

When the bound tool surface includes Local HTTP tools (`ping`, `get_accounts_list`, `list_charts`, `listChartIndicators`, `listPlugins`, `show_notification`, `get_server_time`), read `references/local-http-server.md` for the Local capability map, encoding rules, pagination caps, identifier types, active-chart targeting, drawing-object anchor requirements, and the destructive-operations checklist.

When the bound tool surface includes Remote HTTP tools (`get_version`, `get_assets`, integer `symbolId`-keyed tools, `moneyDigits` in responses), read `references/remote-http-server.md` for the Remote capability map, encoding rules, the 9-value `period` enum, server-side validations, `timeInForce` semantics, `dealStatus` enum, and the cache-discipline rules for `get_symbols`.

When both surfaces are bound, read both files.

## Bundled scripts

Non-trivial computation lives in `scripts/`. Invoke a script whenever the math goes beyond a single multiplication or addition. Every script accepts CLI flags only (non-interactive), prints JSON to stdout, prints diagnostics to stderr, and documents itself via `--help`.

| Script                       | Purpose                                                                                                                                       | Invocation pattern                                                                                                                                                                                         | Output shape                                                                        |
|------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------|
| `scripts/pip_math.py`        | Convert between pip distance and absolute price (display values; operates on both servers' encoding once pipettes are decoded).               | `python scripts/pip_math.py pips-to-price --pip-size 0.0001 --digits 5 --reference-price 1.0850 --pips 30`                                                                                                 | `{"absolute_price": 1.08800, "pip_size_used": 0.0001}`                              |
| `scripts/position_sizing.py` | Compute order size from a risk-percent or risk-amount target, accounting for pip value and quote -> account-currency conversion.              | `python scripts/position_sizing.py from-risk-percent --balance 10000 --risk-pct 1 --sl-pips 30 --pip-value-per-lot 10 --conversion-rate 1.0`                                                               | `{"units": 33333, "cents": 3333333, "risk_currency_amount": 100.0, "warnings": []}` |
| `scripts/tiered_margin.py`   | Reproduce cTrader's dynamic-leverage margin formula across a tier curve.                                                                      | `python scripts/tiered_margin.py compute --volume-base-units 1000000 --quote-rate-usd 1.21345 --tiers '[{"upper":1000000,"leverage":500},{"upper":5000000,"leverage":200},{"upper":null,"leverage":100}]'` | `{"margin_usd": 3067.25, "per_tier_breakdown": [...]}`                              |
| `scripts/conversion_rate.py` | Build the shortest spot-rate chain to convert between two currencies.                                                                         | `python scripts/conversion_rate.py compute-chain --from-asset JPY --to-asset USD --quotes '{"USDJPY":150.3}'`                                                                                              | `{"rate": 0.006653, "chain": ["USDJPY"], "warnings": []}`                           |
| `scripts/units_encoding.py`  | Convert between display lots and the wire encoding for each server (units / cents); convert between display money and `moneyDigits` integers. | `python scripts/units_encoding.py lots-to-cents --lots 0.1 --lot-size 100000`                                                                                                                              | `{"cents": 1000000}`                                                                |

## Post-order validation loop

After any mutating call (`place_*_order`, `create_order`, `amend_order`, `amend_position`, `close_position`, `cancel_order`), re-fetch the affected entity (`get_positions`, `get_pending_orders`, or `get_position_details`) and verify that volume, side, entry price (for fills), SL, TP, and `dealStatus` match the user's stated intent. If any value mismatches, identify the mismatch class:

- Encoding error -> re-run `scripts/units_encoding.py` or `scripts/pip_math.py` and retry with corrected inputs.
- Broker rejection (`dealStatus: REJECTED` / `INTERNALLY_REJECTED` / `ERROR`) -> surface the rejection reason from the server response to the user and stop.

Do not assume the order is filled just because the call returned without an exception.
