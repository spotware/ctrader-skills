# Local HTTP server (`ctrader-local-mcp`): behavior, encoding, and capabilities

as-of: local build observed-on 2026-05-14 (last live re-verification 2026-05-14; quirks first documented on 2026-05-13 remain ACTIVE; Local server was not directly probed during the 2026-05-14 Remote 1.0.18 re-audit, so this date reflects the previous full Local audit)

This document covers the BEHAVIORS, ENCODINGS, and CAPABILITY AREAS specific to the cTrader Local HTTP server (`ctrader-local-mcp`), which is bound to the cTrader Desktop application via a local HTTP transport. The cross-server units / pip / margin / conversion / hedging / stop-out / swap mechanics live in `SKILL.md`; this file adds the Local-only details that compose with them.

## Surface map

The Local HTTP server exposes capability categories rooted in the cTrader Desktop application. The table below names the categories and the dominant capability area each one covers.

| Category                        | Capability area                                                                                                                                                  |
|---------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Connection & diagnostics        | Liveness, server-time alignment, top-level app focus and switching.                                                                                              |
| Accounts & balance              | Account enumeration, current balance / equity / margin / margin level snapshot, lifetime account statistics.                                                     |
| Symbols & market data           | Symbol universe enumeration, per-symbol static metadata + live quote, trading sessions, spot prices, historical OHLCV, forecast margin, market news.             |
| Watchlists                      | User watchlist enumeration, creation, renaming, deletion, and symbol membership editing.                                                                         |
| Trading — positions             | Open-position snapshot, market entry, position SL/TP amendment, full close, partial close, bulk-close.                                                           |
| Trading — pending orders        | Pending order enumeration, limit / stop / stop-limit placement, in-place amendment, single cancel, bulk cancel.                                                  |
| Trade history                   | Most-recent deals (executions) and closed-trade history loaded by the client.                                                                                    |
| Charts — lifecycle & navigation | Chart tab enumeration, open / close / focus, symbol and timeframe changes on the focused chart, viewport scroll and zoom.                                        |
| Charts — drawing objects        | Add / read / update / delete / clear-all drawing annotations on the focused chart with named object types and anchor requirements.                               |
| Charts — indicators             | Indicator catalog and currently attached indicators on the focused chart, add / remove, parameter mutation, output-value retrieval.                              |
| Chart templates                 | Save the focused chart's styling / indicator setup as a named template; list / apply / delete templates.                                                         |
| Workspaces                      | Save / load / delete the full UI layout snapshot.                                                                                                                |
| UI — layout, panels, tabs       | Adjust layout mode, ASP panel and tabs, market-watch panel mode, trade-watch tab, surface notifications.                                                         |
| Price alerts                    | List / create / delete price-trigger alerts (`above` / `below`, `bid` / `ask`).                                                                                  |
| cBot plugins                    | Enumerate available cBots, start, stop.                                                                                                                          |
| Conventions & gotchas           | Cross-cutting conventions exposed in this file: units, ISO+Z time, side casing, pip-vs-absolute split, pagination caps, identifier types, destructive-op safety. |

Capability categories above identify WHAT lives on this server; the sections below describe HOW to work with each behavior class correctly.

## Volume encoding on Local

> **QUIRK:** see [Q-L1](known-quirks.md#q-l1)

On the Local server, every volume parameter is broker-defined: `get_symbol_details(symbolName)` returns the authoritative `lotSize`, `minVolume`, and `volumeStep`. Earlier skill versions claimed forex 1 lot = 100 000 units universally; the audit (2026-05-13) found this is BROKER-DEPENDENT. Observed example: ICMarkets Local returns `lotSize: 1` for `EURUSD` and accepts `volume: 0.01` directly. Mental shortcuts like "1 standard lot = 100 000 units" are unreliable — always read `get_symbol_details` before calling any volume-bearing tool. Symbol classes that historically diverged from the 100 000-units convention include metals (`XAUUSD`, `XAGUSD`), indices (cash indices such as `US30`, `GER40`), and crypto (`BTCUSD`, `ETHUSD`) — but per-broker behavior on FX itself is also broker-dependent.

Invoke `scripts/units_encoding.py lots-to-units` to convert from a user-stated lot size; output shape `{"units": <int>}`. Cross-reference `SKILL.md` "Units conventions across the two servers" Volume row for the Local-vs-Remote comparison.

## Price encoding on Local

Prices are **display floats** (e.g., `1.21345`). Precision is determined by the symbol's `digits` field returned by `get_symbol_details`. Pass and parse prices as-is — no scaling, no pipette conversion. Pip size (`pipSize`) is exposed by `get_symbol_details`; do not assume `0.0001` (FX majors typically `0.0001`; JPY pairs `0.01`; `XAUUSD` `0.01`; indices may differ).

Invoke `scripts/pip_math.py` when converting pip distances to / from absolute prices on the Local server; pass `--pip-size <float> --digits <int>` plus the conversion-direction subcommand.

## Time encoding on Local

> **QUIRK:** see [Q-L8](known-quirks.md#q-l8)

Every time-typed parameter (e.g., `from` / `to` on `get_trendbars`, `time1` / `time2` / `time3` on drawing objects, `expiresAt` on pending orders) requires **ISO 8601 with the explicit `Z` suffix** (`2026-05-12T14:30:00Z`). Strings without `Z` are interpreted as local time by the underlying client and have produced incorrect ranges in practice. Always derive the reference time from `get_server_time` rather than the agent's local clock to avoid drift.

Pass timestamps through unchanged — no script needed.

## Symbol identifiers on Local

Every symbol parameter is the **string ticker** (`"EURUSD"`, `"GBPJPY"`, `"XAUUSD"`). There is no numeric symbol id on this server. The case is exactly as the broker advertises (typically uppercase). The agent resolves symbol names from user phrasing by calling `get_symbols(filter="…")` when the ticker is ambiguous (e.g., "gold" → search for "XAU", "oil" → search for "WTI" or "BRENT" depending on broker).

## Side enum casing on Local

> **QUIRK:** see [Q-L3](known-quirks.md#q-l3)

Input `side` is **case-INSENSITIVE** on the Local server as of the 2026-05-13 audit — both `buy` / `BUY` are accepted on `place_market_order`, `place_limit_order`, `place_stop_order`, `place_stop_limit_order`, and the `risk_reward` drawing object's `side` field. Response field naming uses PascalCase: `tradeSide: "Buy"` / `"Sell"`, `orderType: "Limit"` / `"Stop"` / `"StopLimit"`. Earlier skill versions claimed lowercase-only input — this was a misreading of the JSON Schema description. Casing on output uses PascalCase regardless of input.

## Stop loss and take profit semantics on Local

> **QUIRK:** see [Q-L2](known-quirks.md#q-l2)

The Local server splits SL / TP semantics between order PLACEMENT tools (which take **pip distance from entry**) and the position-AMENDMENT tool (which takes **absolute price**). This split is Local-specific; the Remote server uses absolute price everywhere.

| Tool                                                                                       | SL/TP form         | Field names                          |
|--------------------------------------------------------------------------------------------|--------------------|--------------------------------------|
| `place_market_order`                                                                       | Pip distance       | `stopLossPips`, `takeProfitPips`     |
| `place_limit_order` / `place_stop_order` / `place_stop_limit_order`                        | Pip distance       | `stopLossPips`, `takeProfitPips`     |
| `amend_order` (pending)                                                                    | Pip distance       | `stopLossPips`, `takeProfitPips`     |
| `amend_position` (open position)                                                           | **Absolute price** | `stopLoss`, `takeProfit`             |
| `close_position`, `close_position_partial`, `close_all_positions`                          | N/A                | (no SL/TP parameter)                 |

When the user says "tighten SL to 1.0825" on an open position, the absolute-price form is required and `amend_position` is the correct tool. When the user says "30 pips SL on the new entry", the pip-distance form is required and `place_*_order` / `amend_order` are the correct tools. Mixing the two silently produces wrong levels: passing a pip integer to `amend_position` interprets `30` as the absolute price `30`, which the broker either rejects or accepts as a destructive change.

**Response-shape asymmetry (CRITICAL):** As of 2026-05-13, `get_pending_orders` returns `stopLoss` as an ABSOLUTE PRICE but `takeProfit` as RAW PIPS — the response fields are NOT symmetric with each other. When reading `get_pending_orders`, treat `stopLoss` as a price comparable to `entryPrice`, and treat `takeProfit` as a pip distance from `entryPrice`. Do NOT round-trip values without normalization. This is a known server-side behavior documented in [Q-L2](known-quirks.md#q-l2).

Invoke `scripts/pip_math.py pips-to-price` to convert a pip distance into an absolute price for `amend_position`, or `price-to-pips` for the reverse direction. Input: `--pip-size <float> --digits <int> --reference-price <float> --pips <int>`. Output: `{"absolute_price": <float>, "pip_size_used": <float>}`.

## Pagination caps

> **QUIRK:** see [Q-L4](known-quirks.md#q-l4) and [Q-L9](known-quirks.md#q-l9)

Every list-returning tool on the Local server has a hard cap; reading more than the cap requires multiple windowed requests with client-side de-duplication.

| Tool                 | Per-request cap                                                                                             | Pagination strategy                                                                                                                                                                                    |
|----------------------|-------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `get_trendbars`      | **1000 bars** (silently truncated when more requested; flagged via `truncated: true` field on the response) | Loop over rolling `from` / `to` windows; window size in minutes = `1000 × timeframe-minutes`; dedupe by bar open timestamp.                                                                            |
| `get_deals`          | **200 deals**                                                                                               | Issue successive calls with `count=200` and use the returned timestamps to advance the window; dedupe by `dealId`.                                                                                     |
| `getIndicatorValues` | **1000 values**                                                                                             | Values are returned OLDEST-first as of 2026-05-13 (audit confirmed). Reverse the array before charting or downstream consumption. Iterate `outputIndex` 0..N-1 for multi-line indicators (e.g., MACD). |

`scripts/` does not perform windowed pagination — that is a workflow-level loop described in `references/trader-workflows.md` workflow W6 (history).

## Stop-order `triggerMethod`

`place_stop_order` and `place_stop_limit_order` accept `triggerMethod` with two values: `trade` (default) and `opposite`. `trade` triggers on the actual trade-side quote; `opposite` triggers on the opposite-side quote (ask for sells, bid for buys), which reduces premature triggers from spread spikes during news or low-liquidity sessions. This parameter does **not** exist on the Remote server.

When placing a stop order at a level close to the current quote during a session with widening spreads (news release, session changeover), prefer `triggerMethod="opposite"`.

## Active chart focus model

Chart-targeting tools (`change_chart_symbol`, `change_chart_timeframe`, `get_chart_viewport`, `scroll_chart`, `zoom_chart`, `add_chart_object`, `get_chart_objects`, `update_chart_object`, `delete_chart_object`, `clear_chart_objects`, `listChartIndicators`, `addChartIndicator`, `removeChartIndicator`, `update_indicator_parameters`, `getIndicatorValues`, `save_chart_template`, `apply_chart_template`) ALL act on the **focused chart**, not on a chart identified by parameter. The agent never passes `chartId` to these tools; instead the agent manages focus deterministically: call `list_charts` to enumerate, then `focus_chart(chartId)` to switch focus, then issue chart-targeting tools.

Forgetting to focus is the most common cause of "tool executed but I see nothing on my chart" — the operation went to a different focused chart. Before ANY chart-mutating sequence, the agent records the intended `chartId` and re-confirms focus with `get_active_chart`.

## Hedging vs netting on Local

> **QUIRK:** see [Q-L15](known-quirks.md#q-l15) and [Q-L18](known-quirks.md#q-l18)

This server's positions reflect the **account-level** hedging vs netting mode that the broker configures. The mode is visible via `get_balance` (account-info shape) and via account metadata in `get_accounts_list`. The cross-server semantic difference between hedging and netting is described in `SKILL.md` "Hedging vs netting accounts"; this section names the Local-specific WAY to detect the mode (read `get_balance` for the active account; check `get_accounts_list` for multi-account context where mode may vary per account). On Local, the active account may not appear in `get_accounts_list` — resolve the active `traderId` via `get_balance.traderId` instead, and read `get_balance.accountType` to check for `"Hedged"`. `marginLevel: null` on `get_balance` is normal when no positions are open.

## State-verification before mutation

Every mutating operation on the Local server should be preceded by a read of the affected entity's current state. The pattern is: read → confirm intent → mutate → re-read to verify. The read tools and their target mutations are mapped in the table below.

| Mutation                                                                                   | Pre-read tool                               |
|--------------------------------------------------------------------------------------------|---------------------------------------------|
| `place_*_order` / `amend_order` / `cancel_order` / `cancel_all_pending_orders`             | `get_pending_orders`                        |
| `amend_position` / `close_position` / `close_position_partial` / `close_all_positions`     | `get_positions`                             |
| `add_chart_object` / `update_chart_object` / `delete_chart_object` / `clear_chart_objects` | `get_chart_objects` (after `focus_chart`)   |
| `addChartIndicator` / `removeChartIndicator` / `update_indicator_parameters`               | `listChartIndicators` (after `focus_chart`) |
| `delete_watchlist` / `remove_symbol_from_watchlist`                                        | `get_watchlists`                            |
| `startPlugin` / `stopPlugin`                                                               | `listPlugins`                               |

The post-mutation re-read pattern is in `SKILL.md` "Post-order validation loop"; this section only specifies the pre-mutation read.

## Drawing object anchor requirements

> **QUIRK:** see [Q-L10](known-quirks.md#q-l10)

`add_chart_object` requires a different combination of price anchors and time anchors per `object_type`. Passing only a price for a two-anchor object leaves it ill-positioned or rejected.

| Anchor pattern                                                                                                                                            | Object types                                                                                                                                                                                                | Extra options                                |
|-----------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------|
| One-point (price1 + time1)                                                                                                                                | `horizontal_line`, `text`, `static_text`, markers (`up_arrow`, `down_arrow`, `circle`, `square`, `diamond`, `star`, `up_triangle`, `down_triangle`)                                                         | — (markers are visual only)                  |
| Time-only (time1)                                                                                                                                         | `vertical_line`                                                                                                                                                                                             | —                                            |
| Two-point (price1+time1, price2+time2)                                                                                                                    | `trend_line`, `ray`, `arrow_line`                                                                                                                                                                           | `extend` (boolean)                           |
| Two-point geometry (price1+time1, price2+time2)                                                                                                           | `equidistant_channel`, `rectangle`, `ellipse`, `fibonacci_retracement`, `fibonacci_fan`, `fibonacci_arcs`, `fibonacci_timezones`, `gann_fan`, `gann_box`, `gann_square`, `gann_square_fixed`                | `fill` (boolean) on rectangle / ellipse only |
| Three-point (p1+t1, p2+t2, p3+t3)                                                                                                                         | `triangle`, `fibonacci_expansion`, `andrews_pitchfork`                                                                                                                                                      | `fill` on triangle only                      |
| Trade visualization (`risk_reward`)                                                                                                                       | `side` ∈ {`buy`, `sell`}, p1=entry, p2=SL, p3=TP, t1=block_start, t2=block_end (t2 optional; defaults to t1)                                                                                                | —                                            |

A successful `add_chart_object` returns an `objectId` — capture it for later `update_chart_object` / `delete_chart_object` calls.

## Destructive operations

The Local server happily performs irreversible actions — these tools have no undo on this server, so always read current state first and confirm intent with the user.

- `close_all_positions` — closes every open position (optionally per symbol).
- `cancel_all_pending_orders` — cancels every working order on the account.
- `clear_chart_objects` — deletes every drawing on the focused chart.
- `delete_workspace` — removes a saved layout snapshot.
- `delete_watchlist` — removes a watchlist (including its symbol membership).
- `delete_chart_template` — removes a saved styling template.
- `delete_price_alert` — removes a single alert by id.
- `stopPlugin` — stops a running cBot mid-execution.

Before invoking any of the above, read the current state with the pre-read tool from the State-verification before mutation section, and present the affected items to the user for confirmation.

## Response shapes (`place_*_order`, `amend_*`)

> **QUIRK:** see [Q-L5](known-quirks.md#q-l5) and [Q-L6](known-quirks.md#q-l6)

The Local order-placement tools (`place_market_order`, `place_limit_order`, `place_stop_order`, `place_stop_limit_order`) return only `{orderId, status}` — no echoed `volume`, `price`, `stopLoss`, or `takeProfit`. After placement, ALWAYS re-read via `get_pending_orders` (pending) or `get_positions` (filled) to verify the placement matched intent.

Input vs response field-name asymmetries exist across endpoints — agents reading responses must remap names:

| Input field name | Response field name                        |
|------------------|--------------------------------------------|
| `limitPrice`     | `targetPrice`                              |
| `orderId`        | `id`                                       |
| `expiresAt`      | `expiration`                               |
| `side`           | `tradeSide`                                |
| `entryPrice`     | `entryPrice` (preserved on amend response) |

These asymmetries are server-side; the agent normalizes both directions explicitly.

## Error envelopes (plain text)

> **QUIRK:** see [Q-L11](known-quirks.md#q-l11)

The Local server returns errors as plain-text strings, NOT structured JSON envelopes. Example: `"Order error: Not enough funds to open this Position"`. Agents must regex-parse the message to classify the error (validation / broker-rejection / resource-absent). There is no structured `error.code` / `error.message` field.

## `get_order_history` returns the `trades` key

> **QUIRK:** see [Q-L7](known-quirks.md#q-l7)

The `get_order_history` response stores executed trades under the `trades` key (not `orders`). When reading the history page, key off `trades[]` and dedupe by `dealId` / `orderId`. Earlier skill versions and naive integrations assume `orders[]`; this is incorrect on Local.

## `get_account_statistics` may be unavailable

> **QUIRK:** see [Q-L12](known-quirks.md#q-l12)

`get_account_statistics` can return `{"available": false}` instead of statistics. Workflows depending on these statistics (drawdown / peak-equity tracking) must check the `available` flag and fall back to deriving the required metric from in-session reads.
