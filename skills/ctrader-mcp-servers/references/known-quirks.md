# Known Quirks Ledger — cTrader MCP servers

> **as-of:** rest-proxy 1.0.18 (Remote) + local build observed-on 2026-05-14
> **last_full_audit_date:** 2026-05-14 (Q-R1, Q-R2, Q-R3, Q-R4, Q-R5, Q-R7, Q-R8, Q-R10 re-verified on rest-proxy 1.0.18 — all still ACTIVE; Q-R4 and Q-R7 error-format refreshed to plain-string with actionable hint; Q-R11 Verify-fixed PASSED on 1.0.18 session 1/5 — entry retained pending 4 more PASS sessions per Removal criteria)

This ledger is the **single canonical source of truth** on build-specific observed runtime behaviors of the `ctrader-remote-mcp` and `ctrader-local-mcp` servers as of the audit date above.

Every entry follows the canonical template (ID, Observed-on, Detect, Workaround, Verify-fixed, Removal criteria). When a server is fixed (verified by re-running the entry's `Verify-fixed` probe), DELETE that entry — this is the entire cleanup cost. The Workaround section names the recovery pattern (one of the P-* patterns in `self-healing-playbook.md`); update the playbook only if the pattern itself becomes obsolete.

## Conventions

- **Q-R<n>** — Remote (`ctrader-remote-mcp`) quirk.
- **Q-L<n>** — Local (`ctrader-local-mcp`) quirk.
- **Q-K<n>** — Cross-cutting (both servers, or encoding-layer concern).
- **Q-B<n>** — Reserved for future per-broker overlay (no entries in this iteration).

The anchor for each entry is the lowercased ID (`#q-r1`, `#q-r4-range`, `#q-l2`, `#q-k19`). External cross-references (from `SKILL.md`, `remote-http-server.md`, `local-http-server.md`, `trader-workflows.md`) use the form `[Q-R10](known-quirks.md#q-r10)`.

Each entry uses an explicit `<a id="q-..."></a>` HTML anchor immediately under the `###` heading so cross-references remain stable even if heading text evolves.

## Remote server quirks (Q-R&lt;n&gt;)

### Q-R1 — `period` enum is 9 values, NOT 26

<a id="q-r1"></a>

- **Observed-on:** rest-proxy 1.0.13
- **Detect:** Live call `get_trendbars(period="M_2", symbolId=1, count=1)` returns MCP `-32602: Input validation error` (Zod enum mismatch). The accepted set is `M_1, M_5, M_15, M_30, H_1, H_4, D_1, W_1, MN_1`.
- **Workaround:** When the user requests an unsupported granularity (M_2, M_3, H_3, etc.), propose the nearest supported alternative (e.g., M_2 → M_1 or M_5; H_3 → H_1 or H_4). Never assert the legacy 26-value claim.
- **Verify-fixed:** `get_trendbars(period="M_2", symbolId=<valid>, count=1)` returns a successful response.
- **Removal criteria:** Verify-fixed probe passes on a current-build session; delete this entry.

### Q-R2 — `expirationTimestamp` integer epoch milliseconds ONLY

<a id="q-r2"></a>

- **Observed-on:** rest-proxy 1.0.13
- **Detect:** `create_order(..., expirationTimestamp="2026-05-13T14:30:00Z")` returns MCP `-32602` Zod validation error; the schema declares `type: integer`. History-window endpoints (`fromTimestamp` / `toTimestamp`) DO accept both forms — this quirk is `expirationTimestamp`-specific.
- **Workaround:** Always pass integer epoch milliseconds (UTC) for `expirationTimestamp` on `create_order` and `amend_order`. Convert any ISO string client-side before sending.
- **Verify-fixed:** `create_order(..., expirationTimestamp="2026-05-13T14:30:00Z")` succeeds and the position carries the expected expiry.
- **Removal criteria:** Verify-fixed probe passes; delete this entry.

### Q-R3 — `trailingStopLoss` silently dropped by `create_order` / `amend_order`

<a id="q-r3"></a>

- **Observed-on:** rest-proxy 1.0.13
- **Detect:** Place an order with `trailingStopLoss: true` on `create_order` (or `amend_order`); re-read via `get_positions` and observe that the flag is NOT set. The Zod schema strips unknown keys silently.
- **Workaround:** Apply `trailingStopLoss: true` only via `amend_position(positionId, trailingStopLoss: true, stopLoss=<anchor>)` AFTER the position exists. The trail anchor is the SL level, so a `stopLoss` value must be present. Combine with P-AMEND-SAFE so the TP leg is preserved.
- **Verify-fixed:** `create_order(..., trailingStopLoss=true, stopLoss=<price>)` returns a position whose subsequent `get_positions` read reports `trailingStopLoss: true`.
- **Removal criteria:** Verify-fixed probe passes; delete this entry.

### Q-R4 — `create_order` with `orderType: MARKET` REJECTS absolute SL/TP

<a id="q-r4"></a>

- **Observed-on:** rest-proxy 1.0.13; behavior unchanged on rest-proxy 1.0.18 (error message reformatted).
- **Detect (dual format):** `create_order(orderType="MARKET", stopLoss=<price>)` returns an error. **Pre-1.0.18 envelope:** `HTTP 400 {"error":{"code":"INVALID_REQUEST","message":"SL/TP in absolute values are allowed only for order types: [LIMIT, STOP, STOP_LIMIT]",...}}`. **1.0.18+ envelope (no JSON wrapper):** plain string starting with `"create_order: Absolute stopLoss is not supported for MARKET orders (fill price is unknown at send time). Use relativeStopLoss (offset in points from fill price) instead, ..."`. Both formats indicate the same underlying constraint.
- **Workaround (PREFERRED — single call):** Use the `relativeStopLoss` / `relativeTakeProfit` integer-points fields on `create_order` directly with `MARKET` (and `MARKET_RANGE`). Direction is implicit from `tradeSide`: BUY → SL = fill − relativeStopLoss; SELL → SL = fill + relativeStopLoss; mirrored for TP. Mutually exclusive with absolute `stopLoss`/`takeProfit`. The schema declares these fields as `exclusiveMinimum: 0`, integer points (1 point = 1 / 10^pipDigits). Use **P-REMOTE-MARKET-RELATIVE** (`self-healing-playbook.md` §5.6). Example: `create_order(orderType="MARKET", tradeSide="BUY", volume=100000, relativeStopLoss=300, relativeTakeProfit=600)` on EURUSD entry 1.1709 → SL=1.1679, TP=1.1769 in one round-trip with no race window.
- **Workaround (FALLBACK — two-step):** Apply **P-REMOTE-MARKET-2STEP** (`self-healing-playbook.md` §5.2) ONLY when the user has stated ABSOLUTE SL/TP prices that cannot be cleanly converted to point offsets (e.g., "SL exactly at 1.16500", and the agent does NOT want to compute 1.16500 − fill price at send time): (1) `create_order(orderType="MARKET", ...)` WITHOUT SL/TP; (2) await fill; (3) `amend_position(positionId, stopLoss=..., takeProfit=...)` applying BOTH legs per P-AMEND-SAFE. Accept the small window where the position has no SL/TP between fill and amend.
- **Verify-fixed:** `create_order(orderType="MARKET", stopLoss=<price>, takeProfit=<price>)` succeeds and the response echoes both legs as absolute prices. (Note: relative-points path is NOT a Verify-fixed signal — it is an always-available alternative path, not a quirk fix.)
- **Removal criteria:** Absolute SL/TP succeed on MARKET in the Verify-fixed probe; delete this entry. The `relativeStopLoss`/`relativeTakeProfit` schema fields stay regardless.

### Q-R4-RANGE — `MARKET_RANGE` SL/TP acceptance unverified (gated)

<a id="q-r4-range"></a>

- **Observed-on:** rest-proxy 1.0.13 (UNVERIFIED — requires live probe)
- **Detect:** `create_order(orderType="MARKET_RANGE", slippageInPoints=..., stopLoss=<price>)` either succeeds (build accepts absolute SL/TP at creation) or returns HTTP `400 INVALID_REQUEST` (build behaves like Q-R4 on MARKET_RANGE).
- **Workaround:** Run the Verify-fixed probe at session bootstrap (W0). On PASS, use **P-REMOTE-MARKET-RANGE** (`self-healing-playbook.md` §5.3) with absolute SL/TP at creation. On FAIL, fall back to **P-REMOTE-MARKET-2STEP**.
- **Verify-fixed:** `create_order(orderType="MARKET_RANGE", slippageInPoints=10, stopLoss=<price>, takeProfit=<price>)` on a low-impact symbol succeeds and the response echoes both legs.
- **Removal criteria:** Verify-fixed probe passes on the live build; delete this entry (Q-R4 may remain).

### Q-R5 — `IMMEDIATE_OR_CANCEL` (IOC) behaves like pending LIMIT

<a id="q-r5"></a>

- **Observed-on:** rest-proxy 1.0.13
- **Detect:** Place a LIMIT with `timeInForce="IMMEDIATE_OR_CANCEL"` whose volume exceeds available liquidity at the limit price; observe that the unfilled remainder PERSISTS as a working order rather than being cancelled.
- **Workaround:** Do NOT rely on IOC for cancel-remainder semantics. Use `timeInForce="GOOD_TILL_CANCEL"` with a tight cancel timer in the workflow, or `MARKET_RANGE` for slippage-bounded immediate intent. If IOC is contractually required (e.g., user explicitly requests "cancel anything not filled immediately"), post-flight cancel any residual via `cancel_order`.
- **Verify-fixed:** IOC with insufficient liquidity returns the partial fill AND cancels the remainder (no working order persists).
- **Removal criteria:** Verify-fixed probe passes; delete this entry.

### Q-R7 — 720h window cap on history endpoints

<a id="q-r7"></a>

- **Observed-on:** rest-proxy 1.0.13; behavior unchanged on rest-proxy 1.0.18 (error message reformatted with actionable hint).
- **Detect (dual format):** A history request (`get_trendbars`, `get_order_history`, `get_deals`) whose `(toTimestamp - fromTimestamp)` exceeds 720 hours returns an error. **Pre-1.0.18 envelope:** `HTTP 400 {"error":{"code":"INVALID_REQUEST","message":"Interval between fromTimestamp and toTimestamp must not exceed PT720H",...}}`. **1.0.18+ envelope:** plain string `"Time range exceeds upstream cap of 720h (PT720H = 30 days). Requested <X>h. Split into 720h-or-smaller windows and call this tool multiple times (the calls can run in parallel)."` (includes the actual requested duration). Truncated pages within an allowed window also surface via `hasMore: true`.
- **Workaround:** Apply **P-REMOTE-HISTORY-CHUNK** (`self-healing-playbook.md` §5.5): chunk into ≤ 720h windows, loop with `hasMore` advancement, dedupe results by `dealId` / `orderId` / bar-open timestamp. Per the 1.0.18 hint, the per-window calls CAN run in parallel.
- **Verify-fixed:** A single request spanning > 720h returns a full result without an error and without `hasMore: true`.
- **Removal criteria:** Verify-fixed probe passes; delete this entry.

### Q-R8 — Unknown-symbol asymmetry (`get_spot_prices` vs `get_trendbars`)

<a id="q-r8"></a>

- **Observed-on:** rest-proxy 1.0.13
- **Detect:** `get_spot_prices(symbolId=[999999])` returns an EMPTY `prices[]` array silently (no error). **Batch-poisoning (live on rest-proxy 1.0.14): a SINGLE unknown id in the batch returns EMPTY `prices[]` for the ENTIRE request — valid ids in the same batch are NOT partially returned, they are hidden too.** By contrast, `get_trendbars(symbolId=999999, ...)` returns HTTP `502 Bad Gateway` with body `"uProxy error: UNKNOWN_SYMBOL"`.
- **Workaround:** Always validate EVERY `symbolId` in a batch against the session-cached `get_symbols` map BEFORE calling `get_spot_prices`. If even one id is unknown, drop it from the batch (or surface a "symbol not in broker catalog" error) — never send a mixed batch and assume partial success. Surface a clear error message to the user when validation fails; never retry blindly.
- **Verify-fixed:** Both endpoints return a uniform error envelope (or both succeed gracefully) for the same unknown `symbolId`.
- **Removal criteria:** Verify-fixed probe passes; delete this entry.

### Q-R10 — `amend_position` OMIT-removes the omitted SL/TP leg (CRITICAL)

<a id="q-r10"></a>

- **Observed-on:** rest-proxy 1.0.13
- **Detect:** A position currently has BOTH `stopLoss` and `takeProfit` set. Call `amend_position(positionId, stopLoss=<new>)` (TP omitted). Re-read via `get_positions(positionId)` and observe that `takeProfit` is now MISSING — the omitted leg was REMOVED rather than preserved. Passing `stopLoss: null` is REJECTED outright (schema declares non-nullable).
- **Workaround:** Apply **P-AMEND-SAFE** (`self-healing-playbook.md` §5.1): on every `amend_position` call, ALWAYS pass BOTH `stopLoss` AND `takeProfit`. To preserve a leg, re-pass its CURRENT value (read via `get_positions` first). Post-flight verify BOTH legs survived.
- **Verify-fixed:** Calling `amend_position(positionId, stopLoss=<new>)` with TP omitted preserves the prior TP value.
- **Removal criteria:** Verify-fixed probe passes; delete this entry.

### Q-R11 — `get_deals` / `get_order_history` have propagation lag after position close

<a id="q-r11"></a>

- **Observed-on:** rest-proxy 1.0.14 (first observed). **Verify-fixed status on rest-proxy 1.0.18: PASSED on session 1 of 5** (just-closed deal pair `dealId 461185/461186` appeared in `get_deals` immediately within the same-second window 2026-05-14). Entry retained pending 4 more consecutive PASS sessions per Removal criteria.
- **Detect:** Close a position via `close_position(positionId, volume=<v>)` and observe `executionType: ORDER_CANCELLED` (or `ORDER_FILLED` for the closing deal) in the response. Then IMMEDIATELY call `get_deals(fromTimestamp=<just-before-close>, toTimestamp=<now>, maxRows=50)` and `get_order_history(...)` for the same window. On lagged builds (≤ 1.0.14), the just-closed deal/order is NOT present in either response (`deals: []` / `orders: []` / `trades: []`), even though the mutation response confirmed completion seconds earlier. On builds with the fix (≥ 1.0.18, pending 5-session confirmation), the deal pair appears immediately.
- **Workaround:** PRIMARY — always prefer the `deal` / `order` / `position` objects in the mutation response itself (e.g., `close_position` returns the closing `deal` and updated `position` directly) — this works regardless of build. SECONDARY (only when the mutation response is unavailable, e.g., audit/reconciliation): poll `get_deals` with backoff (e.g., 5 s, 15 s, 60 s) until the expected `dealId` appears. Workflow W6 chunked-history loops should still treat the trailing tail of the window as eventually-consistent until the 5-session Verify-fixed gate clears.
- **Verify-fixed:** Close a position; within 1 second call `get_deals(...)` for the same window; the closing deal IS present in the response. **Sessions PASSED so far: 1 of 5** (2026-05-14 on rest-proxy 1.0.18).
- **Removal criteria:** Verify-fixed probe passes consistently across 5 successive sessions; delete this entry and the corresponding breadcrumbs in `references/remote-http-server.md` (Pagination section) and `references/trader-workflows.md` (W6 propagation-lag note).

## Local server quirks (Q-L&lt;n&gt;)

### Q-L1 — Volume is broker-defined; `lotSize` may be 1

<a id="q-l1"></a>

- **Observed-on:** local build observed-on 2026-05-13
- **Detect:** `get_symbol_details("EURUSD")` returns `lotSize: 1`, `minVolume: 0.01`, and `place_*_order` accepts `volume: 0.01` directly (ICMarkets Local example). The legacy "1 lot = 100 000 units" mental shortcut fails on this broker.
- **Workaround:** ALWAYS read `get_symbol_details(symbolName)` at session start and cache `lotSize`, `minVolume`, `volumeStep`. Encode volumes via `scripts/units_encoding.py lots-to-units --lots <user-lots> --lot-size <symbol-lotSize>` (`--lot-size` REQUIRED). Cross-reference `assets/symbol_precision_table.json` for a baseline only — verify against the live response.
- **Verify-fixed:** This quirk is a server CONVENTION, not an anomaly; it does not get fixed. Remove this entry only if the Local server publishes a fixed lot-size standard across all brokers.
- **Removal criteria:** Server documentation confirms a fixed lot-size convention across brokers; delete this entry.

### Q-L2 — Response-shape asymmetry on `get_pending_orders` (SL absolute / TP raw pips)

<a id="q-l2"></a>

- **Observed-on:** local build observed-on 2026-05-13
- **Detect:** `get_pending_orders()` returns each order with `stopLoss` as an ABSOLUTE PRICE (comparable to `entryPrice`) but `takeProfit` as a RAW PIP DISTANCE (offset from `entryPrice`). The two response fields are NOT symmetric.
- **Workaround:** When parsing `get_pending_orders[]`, treat `stopLoss` as a price and `takeProfit` as a pip integer. Normalize before comparing or displaying: `tp_price = entryPrice ± (takeProfit × pipSize)` (sign per `tradeSide`). Do NOT round-trip values back to the server without re-encoding into the correct input form (`stopLossPips` / `takeProfitPips` on `amend_order`).
- **Verify-fixed:** `get_pending_orders[]` returns symmetric SL/TP shapes (either both absolute or both pip distances).
- **Removal criteria:** Verify-fixed probe passes; delete this entry.

### Q-L3 — `side` input is case-INSENSITIVE; responses are PascalCase

<a id="q-l3"></a>

- **Observed-on:** local build observed-on 2026-05-13
- **Detect:** `place_market_order(side="BUY")` and `place_market_order(side="buy")` BOTH succeed identically. Response fields use PascalCase: `tradeSide: "Buy"` / `"Sell"`, `orderType: "Limit"` / `"Stop"` / `"StopLimit"`.
- **Workaround:** Accept any user casing on input. When parsing responses, expect PascalCase and normalize to the agent's internal convention before comparison. Earlier skill versions claimed lowercase-only input — that claim was wrong.
- **Verify-fixed:** This is a server CONVENTION, not an anomaly; do not remove unless the input casing rule changes.
- **Removal criteria:** Server documentation declares a strict input casing; delete this entry.

### Q-L4 — `get_trendbars` silently truncates above 1000 bars (`truncated: true`)

<a id="q-l4"></a>

- **Observed-on:** local build observed-on 2026-05-13
- **Detect:** `get_trendbars(symbolName=..., period=..., count=2000)` returns at most 1000 bars and sets `truncated: true` on the response envelope.
- **Workaround:** Loop with windowed `from` / `to` parameters; window size in minutes = `1000 × timeframe-minutes`. Dedupe by bar-open timestamp. Continue while `truncated: true`. (No Local equivalent of P-REMOTE-HISTORY-CHUNK is needed — local pagination is simpler.)
- **Verify-fixed:** A request with `count: 2000` returns 2000 bars and `truncated: false`.
- **Removal criteria:** Verify-fixed probe passes; delete this entry.

### Q-L5 — `place_*_order` response is only `{orderId, status}`

<a id="q-l5"></a>

- **Observed-on:** local build observed-on 2026-05-13
- **Detect:** Calling `place_market_order` / `place_limit_order` / `place_stop_order` / `place_stop_limit_order` returns a payload with only `orderId` and `status` — no echoed `volume`, `price`, `stopLoss`, or `takeProfit`.
- **Workaround:** After every placement, RE-READ via `get_pending_orders` (pending) or `get_positions` (filled) to verify the placement matched intent. Treat the placement response as a receipt, not as ground truth on contents.
- **Verify-fixed:** `place_*_order` responses echo all submitted fields.
- **Removal criteria:** Verify-fixed probe passes; delete this entry.

### Q-L6 — Input vs response field-name asymmetry

<a id="q-l6"></a>

- **Observed-on:** local build observed-on 2026-05-13
- **Detect:** Submitted input field names differ from response field names: `limitPrice` ↔ `targetPrice`, `orderId` ↔ `id`, `expiresAt` ↔ `expiration`, `side` ↔ `tradeSide`.
- **Workaround:** Maintain an explicit input-to-response field-name map in the agent's normalization layer. Never assume round-trip identity.
- **Verify-fixed:** Input and response field names match for the same logical field.
- **Removal criteria:** Verify-fixed probe passes; delete this entry.

### Q-L7 — `get_order_history` returns the `trades` key (not `orders`)

<a id="q-l7"></a>

- **Observed-on:** local build observed-on 2026-05-13
- **Detect:** `get_order_history()` returns the executed trades under `response.trades[]`; the field `response.orders` does NOT exist.
- **Workaround:** Read `response.trades[]`. Dedupe by `dealId` / `orderId` when paginating.
- **Verify-fixed:** The response key is `orders[]` (or both `orders[]` and `trades[]` are present with `orders[]` authoritative).
- **Removal criteria:** Verify-fixed probe passes; delete this entry.

### Q-L8 — `expiresAt` without `Z` coerced to local time

<a id="q-l8"></a>

- **Observed-on:** local build observed-on 2026-05-13
- **Detect:** Submit `place_limit_order(..., expiresAt="2026-05-13T14:30:00")` (no `Z` suffix); observe that the resulting `expiration` field on the response or on `get_pending_orders` is offset from the intended UTC moment by the client's local-time offset.
- **Workaround:** ALWAYS append `Z` to every ISO 8601 timestamp on Local input (`expiresAt`, drawing-object `time1` / `time2` / `time3`, `get_trendbars` `from` / `to`). Derive reference time from `get_server_time` rather than the agent's local clock.
- **Verify-fixed:** A timestamp without `Z` is rejected (preferred) or unambiguously interpreted as UTC.
- **Removal criteria:** Verify-fixed probe passes; delete this entry.

### Q-L9 — `getIndicatorValues` returns OLDEST-first

<a id="q-l9"></a>

- **Observed-on:** local build observed-on 2026-05-13
- **Detect:** `getIndicatorValues(...)` returns `values[]` where `values[0]` corresponds to the EARLIEST bar in the window, not the most recent. Earlier skill versions asserted newest-first.
- **Workaround:** Apply **P-LOCAL-OLDEST-FIRST** (`self-healing-playbook.md` §5.4): REVERSE the `values[]` array before charting, signal generation, or downstream consumption that expects newest-first.
- **Verify-fixed:** `values[0]` corresponds to the newest bar.
- **Removal criteria:** Verify-fixed probe passes; delete this entry.

### Q-L10 — `add_chart_object` accepts `trend_line` without time anchors

<a id="q-l10"></a>

- **Observed-on:** local build observed-on 2026-05-13
- **Detect:** `add_chart_object(object_type="trend_line", price1=<float>, price2=<float>)` succeeds with no `time1` / `time2` despite the JSON Schema requiring both time anchors for two-point objects. The resulting line is ill-positioned (anchored to default times) but the call does not error.
- **Workaround:** Always pass BOTH price AND time anchors for any two-point object (`trend_line`, `ray`, `arrow_line`, `equidistant_channel`, `rectangle`, `ellipse`, Fibonacci variants, Gann variants). Read `get_chart_objects` after placement to verify the visual position.
- **Verify-fixed:** Submitting `trend_line` without time anchors is rejected with a schema validation error.
- **Removal criteria:** Verify-fixed probe passes; delete this entry.

### Q-L11 — Errors as plain-text strings

<a id="q-l11"></a>

- **Observed-on:** local build observed-on 2026-05-13
- **Detect:** A failed mutation returns the error as a PLAIN-TEXT string (e.g., `"Order error: Not enough funds to open this Position"`) rather than a structured `{error: {code, message}}` JSON envelope.
- **Workaround:** Regex-parse the message to classify (validation / broker-rejection / resource-absent / fund-shortage / position-not-found). Apply the error-classification matrix in `self-healing-playbook.md` §3 for the retry / fallback decision.
- **Verify-fixed:** Errors are returned as structured JSON envelopes.
- **Removal criteria:** Verify-fixed probe passes; delete this entry.

### Q-L12 — `get_account_statistics` may be unavailable

<a id="q-l12"></a>

- **Observed-on:** local build observed-on 2026-05-13
- **Detect:** `get_account_statistics()` returns `{"available": false}` instead of populated statistics. The unavailability can be intermittent or persistent depending on broker configuration.
- **Workaround:** Always check `response.available` before consuming statistics. On `false`, fall back to deriving the required metrics (peak equity, max drawdown) from in-session reads (`get_balance` snapshots + accumulated P&L from `get_positions` / `get_order_history`).
- **Verify-fixed:** `get_account_statistics()` always returns populated statistics on a healthy account.
- **Removal criteria:** Verify-fixed probe passes; delete this entry.

### Q-L13 — Response enum value-name divergence

<a id="q-l13"></a>

- **Observed-on:** local build observed-on 2026-05-13
- **Detect:** Response enums use PascalCase names that DIFFER from the input enum names. Example: a price alert created with `condition: "above"` is returned with `conditionType: "GreaterOrEqual"`. The mapping is not 1:1 textual.
- **Workaround:** Maintain explicit input-enum → response-enum mapping tables in the agent's normalization layer. Never compare response enum values directly to user-supplied input strings.
- **Verify-fixed:** Input and response enum value-names match (or a unified enum vocabulary is documented).
- **Removal criteria:** Verify-fixed probe passes; delete this entry.

### Q-L15 — Active account hidden from `get_accounts_list`

<a id="q-l15"></a>

- **Observed-on:** local build observed-on 2026-05-13
- **Detect:** `get_accounts_list()` returns one or more accounts, but the CURRENTLY active account is not in the returned list. Calling `get_balance()` succeeds and returns `traderId: <X>` where `<X>` is not in the prior `get_accounts_list` response.
- **Workaround:** Resolve the active `traderId` via `get_balance.traderId`. Treat `get_accounts_list` as a discovery aid, not as an authoritative active-account source. Hedging mode is visible via `get_balance.accountType: "Hedged"`.
- **Verify-fixed:** The active account is always present in `get_accounts_list`.
- **Removal criteria:** Verify-fixed probe passes; delete this entry.

### Q-L18 — `marginLevel: null` is normal when no positions are open

<a id="q-l18"></a>

- **Observed-on:** local build observed-on 2026-05-13
- **Detect:** `get_balance()` returns `marginLevel: null` (or omits the field) when the account has zero open positions. This is correct accounting (margin level = equity / used_margin × 100, and used_margin is 0) but consumers expecting a numeric value fail.
- **Workaround:** Treat `marginLevel: null` (or absent) as "no positions / unconstrained"; do NOT raise an error. W5 (drawdown / margin safety) must short-circuit the stop-out check when `used_margin == 0`.
- **Verify-fixed:** This is a CORRECT accounting behavior; do not remove unless the server adopts a sentinel value (e.g., `Infinity`).
- **Removal criteria:** Server adopts an unambiguous sentinel (e.g., a documented `null` semantic) AND the skill captures the new convention; delete this entry.

## Cross-cutting quirks (Q-K&lt;n&gt;)

### Q-K19 — Pipettes vs display foot-gun (silent market fills)

<a id="q-k19"></a>

- **Observed-on:** rest-proxy 1.0.13 (Remote-primary; both servers applicable when crossing encoding boundaries)
- **Detect:** Any 5+ digit INTEGER appearing in an order-DTO price field (`limitPrice`, `stopPrice`, `stopLoss`, `takeProfit`) is a probable pipettes-leak — Remote market-data fields (`get_spot_prices`, `get_trendbars`) are pipettes (integer), but order/position DTO fields are DISPLAY FLOATS. Mixing produces silently wrong fills (e.g., `limitPrice=105000` interpreted literally as price 105 000).
- **Workaround:** Pre-flight gate 1.6 (`self-healing-playbook.md` §1.6) flags any 5+ digit integer in a price DTO field. Always decode pipettes to display via `scripts/units_encoding.py pipettes-to-price --pipettes <int> --pip-digits <int>` (or equivalent inline math `display = pipettes / 10^pipDigits`) BEFORE submitting any mutation. Local server prices are display floats throughout, so Q-K19 does not apply to Local price fields directly; the foot-gun is on the Remote side and in any cross-server pipeline.
- **Verify-fixed:** Remote order DTO fields accept pipettes uniformly (or display uniformly) with the encoding documented and validated; the foot-gun scope shrinks to zero.
- **Removal criteria:** Server documentation declares a unified encoding for market-data AND order DTO price fields; delete this entry.

## Broker-overlay quirks (Q-B&lt;n&gt;) — reserved

Reserved for future per-broker overrides applied via `assets/broker_overrides.example.json` (NOT shipped this iteration; see `SKILL.md` extension-point note). No `Q-B<n>` entries are populated in this iteration.

---

*If you observe a server behavior that deviates from BOTH the MCP JSON-Schema and this ledger, follow the unknown-quirk decision tree in `self-healing-playbook.md`. Provisional entries during a session are tagged `status: provisional` until corroborated by a second observation.*
