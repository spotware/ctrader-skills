# Remote HTTP server (`ctrader-remote-mcp`): behavior, encoding, and capabilities

as-of: rest-proxy 1.0.18 (last live re-verification 2026-05-14; quirks first documented on rest-proxy 1.0.13 remain ACTIVE on 1.0.18; Q-R4 and Q-R7 error envelopes refreshed to plain-string with actionable hint; Q-R11 Verify-fixed PASSED session 1/5, entry retained)

This document covers the BEHAVIORS, ENCODINGS, and CAPABILITY AREAS specific to the cTrader Remote HTTP server (`ctrader-remote-mcp`). The cross-server units / pip / margin / conversion / hedging / stop-out / swap mechanics live in `SKILL.md`; this file adds the Remote-only details that compose with them.

## Surface map

The Remote HTTP server exposes a smaller, headless tool surface focused on data and trading. The table below names the capability areas.

| Capability area                     | What lives here                                                                                                                                                               |
|-------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Version & diagnostics               | `get_version` (build identification).                                                                                                                                         |
| Account state                       | `get_balance` (balance / equity / freeMargin / moneyDigits / depositAssetId), `get_assets` (asset id → currency name resolution).                                             |
| Symbols & static metadata           | `get_symbols` (symbolId / symbolName / enabled / baseAssetId / quoteAssetId / symbolCategoryId / description).                                                                |
| Live and historical market data     | `get_spot_prices` (batched live quotes for an array of `symbolId`), `get_trendbars` (OHLCV by `period` over a timestamp window).                                              |
| Positions, orders, deals            | `get_positions` (open positions + pending orders), `get_position_details` (single position + related orders + deals), `get_pending_orders`, `get_order_history`, `get_deals`. |
| Trading mutations (trading profile) | `create_order`, `amend_order`, `cancel_order`, `amend_position`, `close_position`.                                                                                            |

Remote-only capabilities (trailing SL, `MARKET_RANGE`, batched `get_spot_prices`, 9-value `period`, explicit `timeInForce`, `dealStatus` enum, profile distinction) are described in their own sections below.

## Volume encoding on Remote

Every `volume` field on the Remote server is an integer count of **cents** of the base asset (this is the wire encoding; not pennies of money). For forex 1 lot = **10 000 000 cents**; this is **100× the Local server's `units` for the same lot** — the conversion is critical. The Bean Validation constraint `@Positive` rejects non-positive values.

Invoke `scripts/units_encoding.py lots-to-cents` to convert from a user-stated lot size; output shape `{"cents": <int>}`. Cross-reference: `SKILL.md` "Units conventions across the two servers" Volume row for the units-vs-cents comparison.

## Price encoding on Remote

> **QUIRK:** see [Q-K19](known-quirks.md#q-k19)

Every price field (`limitPrice`, `stopPrice`, `stopLoss`, `takeProfit`, `entryPrice`, `executionPrice`, `bid`, `ask`, `high`, `low`, `sessionClose`, trendbar `open` / `high` / `low` / `close`) is an **integer in pipettes**, where display price = `price / 10^pipDigits`. `pipDigits` is part of each symbol's static metadata (resolve via `get_symbols`; cache once per session).

Invoke `scripts/pip_math.py` when converting pip distances to / from absolute prices on the Remote server; pass `--pip-size <float> --digits <int> --reference-price <float> --pips <int>`. The script operates on display values; convert pipettes returned by Remote endpoints to display BEFORE passing to the script.

## Money encoding on Remote

Every money field (`balance`, `equity`, `freeMargin`, `unrealizedPnl`, `commission`, `swap`) is an integer in `10^moneyDigits` units. The `moneyDigits` value is returned on the `get_balance` response (typically `2`, but agent reads, does not assume). To display a money figure: `display = raw / 10^moneyDigits`. The `balanceVersion` monotonic counter on `get_balance` increments with every balance-affecting event — useful to detect that the account state has changed between two snapshots.

Invoke `scripts/units_encoding.py display-money --raw <int> --money-digits <int>` to convert from wire to display; `parse-money --display <float> --money-digits <int>` for the reverse.

## Time encoding on Remote

> **QUIRK:** see [Q-R2](known-quirks.md#q-r2)

Timestamp inputs and outputs come in two forms depending on the field. The Remote server's acceptance of input forms is asymmetric — see the table below.

| Field                                                                               | Encoding                                                                                                                                                                                   |
|-------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `fromTimestamp` / `toTimestamp` (`get_trendbars`, `get_order_history`, `get_deals`) | **Accept either** epoch milliseconds (int) or ISO 8601 string (`"2026-05-12T14:30:00Z"`).                                                                                                  |
| `expirationTimestamp` (`create_order`, `amend_order`)                               | **Integer epoch milliseconds ONLY** as of rest-proxy 1.0.13. ISO 8601 strings are rejected by Zod validation.                                                                              |
| `prices[].timestamp` (`get_spot_prices` response)                                   | Epoch milliseconds.                                                                                                                                                                        |
| `trendbars[].timestamp` (`get_trendbars` response)                                  | Epoch milliseconds.                                                                                                                                                                        |
| `deals[].executionTimestamp` (`get_deals` response)                                 | Epoch milliseconds.                                                                                                                                                                        |
| `buildTime` (`get_version` response)                                                | ISO 8601 string (or `"N/A"` if missing).                                                                                                                                                   |
| All other response time fields                                                      | Generally epoch milliseconds.                                                                                                                                                              |
| Request choice rule                                                                 | When sending, prefer ISO 8601 for log readability **on history-window endpoints**; the server normalizes to epoch internally. **For `expirationTimestamp`, integer epoch ms is required.** |

Passed through unchanged — no script needed.

## Symbol identifiers on Remote

> **QUIRK:** see [Q-R8](known-quirks.md#q-r8)

Every symbol parameter is a **numeric integer `symbolId`** (not a string ticker). The agent resolves the user's spoken ticker to a `symbolId` via `get_symbols` (returns `symbolId` ↔ `symbolName` mapping; `symbolName` is the human ticker like `EURUSD`). The result is stable for the session — cache it.

Cross-reference `SKILL.md` "Units conventions across the two servers" Symbol identifier row for the Local-vs-Remote comparison.

## Side enum casing on Remote

The Remote server's response always returns uppercase. Input on `tradeSide` is accepted in uppercase form (`BUY` / `SELL`) on `create_order`, `amend_order`, and every response that echoes a position or deal (`positions[].tradeSide`, `orders[].tradeSide`, `deals[].tradeSide`). Lowercase input handling is build-dependent and SHOULD NOT be relied upon — always send uppercase.

## Order type enum

> **QUIRK:** see [Q-R4](known-quirks.md#q-r4) and [Q-R4-RANGE](known-quirks.md#q-r4-range)

`orderType` on `create_order` accepts five values: `MARKET`, `LIMIT`, `STOP`, `MARKET_RANGE`, `STOP_LIMIT`. The conditional-required price fields are tabulated below.

| Order type     | Required price fields                                  | Behavior                                                                                                                  |
|----------------|--------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------|
| `MARKET`       | (none)                                                 | Fill immediately at the current bid / ask.                                                                                |
| `LIMIT`        | `limitPrice`                                           | Fill only at `limitPrice` or better. Buy-limit below ask; sell-limit above bid.                                           |
| `STOP`         | `stopPrice`                                            | Trigger as a market order when price crosses `stopPrice`. Buy-stop above market; sell-stop below.                         |
| `MARKET_RANGE` | (none directly — see `slippageInPoints`)               | Fill at market within an acceptable slippage band; see `MARKET_RANGE` and slippage section.                               |
| `STOP_LIMIT`   | `stopPrice` + `limitPrice`                             | Trigger at `stopPrice`, then submit a limit at `limitPrice`. Breakout entry with price protection.                        |

**Critical:** As of rest-proxy 1.0.13 (still active on 1.0.18), `create_order` with `orderType: MARKET` REJECTS absolute `stopLoss` / `takeProfit`. The rejection error format changed in 1.0.18 (now a plain-string hint pointing to `relativeStopLoss`; previously a JSON `{"error":{"code":"INVALID_REQUEST",...}}` envelope) — see [Q-R4](known-quirks.md#q-r4) for dual-format Detect. **PREFERRED workaround (single call):** use the schema fields `relativeStopLoss` / `relativeTakeProfit` (positive integer offset in points from fill price, direction implicit from `tradeSide`) on the same `create_order` request. Example: `create_order(orderType="MARKET", tradeSide="BUY", volume=<cents>, relativeStopLoss=300, relativeTakeProfit=600)` → SL = fill − 300 points, TP = fill + 600 points; mutually exclusive with absolute `stopLoss`/`takeProfit`; same pattern works with `MARKET_RANGE`. **FALLBACK workaround (two-step)**, only when the user has stated ABSOLUTE prices that cannot be cleanly converted to point offsets: place MARKET WITHOUT SL/TP, then `amend_position(positionId, stopLoss=..., takeProfit=...)` per P-AMEND-SAFE. Prefer `LIMIT` / `STOP` / `STOP_LIMIT` when the user accepts a non-immediate fill; those order types DO accept absolute SL/TP at creation. `MARKET_RANGE` may accept absolute SL/TP at creation depending on rest-proxy build — verify with a live probe ([Q-R4-RANGE](known-quirks.md#q-r4-range)) before relying on it.

## `timeInForce` enum

> **QUIRK:** see [Q-R5](known-quirks.md#q-r5)

`timeInForce` on `create_order` accepts three values: `GOOD_TILL_CANCEL` (default-shaped), `GOOD_TILL_DATE` (requires `expirationTimestamp`), `IMMEDIATE_OR_CANCEL` (cancel-remainder-on-partial-fill). The Remote server exposes this explicitly; the Local server does not.

## `dealStatus` enum

Every deal record on `get_deals` carries a `dealStatus`. The meanings drive follow-up workflow decisions.

| Status                | Meaning and follow-up                                                                                                                                                 |
|-----------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `FILLED`              | Fully filled at `executionPrice` for `filledVolume`. Proceed.                                                                                                         |
| `PARTIALLY_FILLED`    | Some of the requested volume filled; the remainder either still working (for orders that allow it) or cancelled. `volume` vs `filledVolume` differ — surface the gap. |
| `REJECTED`            | Broker rejected before any fill. Read the response context for the reason; do not retry blindly.                                                                      |
| `INTERNALLY_REJECTED` | Server-side rejection before reaching the broker (e.g., validation, profile mismatch). Treat like `REJECTED` for user-facing messaging.                               |
| `ERROR`               | Execution attempt errored out. Treat like `REJECTED`; the position state may or may not have moved — read `get_position_details` before further action.               |
| `MISSED`              | The execution opportunity was missed (e.g., market gapped past a stop-limit window). No fill occurred.                                                                |

Cross-reference `SKILL.md` "Post-order validation loop" — that section names the action to take per status class; this table names the meanings.

## Stop loss and take profit semantics on Remote

> **QUIRK:** see [Q-R10](known-quirks.md#q-r10)

On the Remote server, **every SL / TP field is an absolute price** — `create_order.stopLoss`, `create_order.takeProfit`, `amend_order.stopLoss`, `amend_order.takeProfit`, `amend_position.stopLoss`, `amend_position.takeProfit`. There is no pip-distance form anywhere on this server. This is the cleanest difference from the Local server's pip / absolute split.

Invoke `scripts/pip_math.py pips-to-price --pip-size <float> --digits <int> --reference-price <float> --pips <int>` to translate a user-stated pip distance into the absolute price the Remote tools expect.

## Trailing stop loss

> **QUIRK:** see [Q-R3](known-quirks.md#q-r3)

As of rest-proxy 1.0.13, `trailingStopLoss: true` is silently IGNORED if passed to `create_order` or `amend_order` (Zod schema drops unknown keys). The flag is ONLY honored on `amend_position(positionId, trailingStopLoss: true)`, applied AFTER the position has been opened. The trail anchor is the SL level, so a `stopLoss` value must be present (set either at order creation or via the same `amend_position` call). There is no trailing SL on the Local server.

## `MARKET_RANGE` and slippage

> **QUIRK:** see [Q-R4-RANGE](known-quirks.md#q-r4-range)

`MARKET_RANGE` and `STOP_LIMIT` accept `slippageInPoints` (positive integer in price points) plus `baseSlippagePrice` (reference price for slippage calculation). The order will not fill outside the slippage band around `baseSlippagePrice`. The agent reaches for this combination on a market entry during volatile periods to bound execution price; on `MARKET`, slippage is not bounded.

`MARKET_RANGE` is Remote-only; the Local equivalent of bounded market entry is achieved via `place_stop_limit_order` with `triggerMethod="opposite"` (described in `references/local-http-server.md`).

## `period` enum: 9 values

> **QUIRK:** see [Q-R1](known-quirks.md#q-r1)

The `get_trendbars` `period` parameter accepts **9 values** as of rest-proxy 1.0.13:

```text
M_1, M_5, M_15, M_30, H_1, H_4, D_1, W_1, MN_1
```

Earlier skill versions claimed 26 values (purportedly the Swagger advertised an 18-value subset but the request accepted all 26). This is a counterfactual reading: a live `get_trendbars(period="M_2", symbolId=1, count=1)` returns MCP `-32602: Input validation error` (Zod enum mismatch). If the user requests M_2, M_3, H_3, etc., propose M_1 / M_5 / H_1 / H_4 alternatives. The Local server's 9-timeframe set is equivalent in granularity.

## Server-side validations

The Remote server enforces structural constraints at the request boundary; violations return `400 Bad Request` with an `IllegalArgumentException` message. The agent prevents these by validating before sending.

| Field / endpoint                                        | Constraint                                                                                                                       |
|---------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------|
| `volume` (every endpoint accepting it)                  | `@Positive` — integer > 0; non-positive values rejected.                                                                         |
| `slippageInPoints` (`amend_order`)                      | `@Positive` — integer > 0.                                                                                                       |
| `comment` (`create_order`)                              | ≤ 256 characters.                                                                                                                |
| `label` (`create_order`)                                | ≤ 100 characters.                                                                                                                |
| `get_trendbars` window                                  | `fromTimestamp < toTimestamp`, interval ≤ server's `maxInterval`, `count` ≤ server's `limit`.                                    |
| `LIMIT` / `STOP` / `STOP_LIMIT` orders                  | Corresponding `limitPrice` / `stopPrice` field MUST be present; otherwise the upstream gateway rejects.                          |

`trailingStopLoss: true` requires `stopLoss` (or `stopPrice` on stop orders) to be present — see Trailing stop loss section.

## Profile distinction: data vs trading

The Remote server exposes two profiles. The `data` profile contains every read-only tool (`get_version`, `get_balance`, `get_assets`, `get_symbols`, `get_spot_prices`, `get_trendbars`, `get_positions`, `get_position_details`, `get_pending_orders`, `get_order_history`, `get_deals`) and is safe to call without confirmation. The `trading` profile contains everything in `data` PLUS the mutations (`create_order`, `amend_order`, `cancel_order`, `amend_position`, `close_position`); mutating tools require explicit user confirmation before invocation.

The bound tool surface tells the agent which profile is active — if no mutating tools are visible in `tools/list`, the connection is `data`-only and trade workflows cannot execute the mutation step. The agent surfaces this to the user before attempting a trade workflow.

## Symbol cache discipline

The `get_symbols` result (the full mapping `symbolId` ↔ `symbolName` plus per-symbol `enabled`, `baseAssetId`, `quoteAssetId`, `symbolCategoryId`, `description`) is **stable for the session**. Cache it on first use; do not re-fetch per tool call. The same discipline applies to `get_assets` (returns `assetId` ↔ asset name mapping; also stable per session).

## `close_position` requires volume

`close_position` on the Remote server **requires** a `volume` parameter (integer cents). To fully close, pass the position's current open `volume` (read from `get_positions` first). To partially close, pass any positive cents value ≤ current open `volume`, respecting the symbol's volume step. There is no "close all" without a volume argument; the Local server's `close_position` takes no volume and closes the full remainder by default — this asymmetry is a frequent integration pitfall.

## `amend_position` omit-removes SL/TP (CRITICAL)

> **QUIRK:** see [Q-R10](known-quirks.md#q-r10)

As of rest-proxy 1.0.13, on `amend_position`, **OMITTING** the `stopLoss` field REMOVES the SL (and omitting `takeProfit` removes the TP). This is the OPPOSITE of intuition and the OPPOSITE of what earlier skill versions claimed (they said omitting leaves unchanged and `null` removes — both wrong). Passing `stopLoss: null` is REJECTED by the schema (the field is declared non-nullable).

Safe pattern: on every `amend_position` call, ALWAYS pass BOTH `stopLoss` AND `takeProfit`. To preserve a leg, re-pass its current value (read via `get_positions` first). To remove a leg, the action is to NOT call `amend_position` for that purpose — surface to the user that explicit removal of a leg is not directly supported and propose an alternative (e.g., close the position, or re-issue it without the leg). The Local server uses a separate convention — see `references/local-http-server.md` for details.

## Pagination via `hasMore`

> **QUIRK:** see [Q-R7](known-quirks.md#q-r7)
> **QUIRK:** see [Q-R11](known-quirks.md#q-r11) (history-propagation lag — just-closed deals do NOT appear immediately)

List-returning tools (`get_pending_orders`, `get_order_history`, `get_deals`) return `hasMore: boolean` on the response. When `hasMore: true`, the result is a truncated page; advance the window or invoke the next page. For `get_deals`, the `maxRows` parameter (default 50) caps page size; the agent loops with progressively advanced `fromTimestamp` until `hasMore: false`.

There is no offset / cursor token — the loop advances by timestamp boundary, so the de-duplication key is `dealId` / `orderId`.

**Propagation lag on history endpoints (Q-R11):** `get_deals` and `get_order_history` are eventually-consistent with respect to mutation responses. A deal that was just produced by `close_position` or `create_order` may not appear in these endpoints for N seconds to minutes. For IMMEDIATE post-mutation verification, ALWAYS use the `deal` / `order` / `position` objects returned in the mutation response itself; only fall back to history endpoints when the agent does not have the mutation response in hand (audit / reconciliation workflows). When relying on history endpoints near "now", poll with backoff (e.g., 5 s, 15 s, 60 s).

## Rate limits

The Remote server enforces two rate-limit classes — **general** (most read tools and mutations) and **historical** (history-bearing tools). The headline rates are:

- General: **50 requests / second**.
- Historical (`get_trendbars`, `get_order_history`, `get_deals`): **5 requests / second**.

The agent paces multi-window backfills to stay under the historical limit (e.g., insert a small interval between successive `get_trendbars` calls; for a 5 r/s cap, a ~250 ms spacing is sufficient).

## Demo vs live distinction

The slug encodes the account environment (`environment` field). The Remote surface itself does not distinguish demo from live — the same tools work against either — but a live account may require an additional explicit `ASK` (user acknowledgement) before any mutation. The agent surfaces "this is a LIVE account" to the user before issuing the first mutation in a session against a live environment, and again for any out-of-policy size.
