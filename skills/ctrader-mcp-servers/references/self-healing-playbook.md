# Self-Healing Playbook — cTrader MCP servers

> **as-of:** rest-proxy 1.0.18 (Remote) + local build observed-on 2026-05-14 (last live re-verification 2026-05-14; named patterns end-to-end exercised on both servers; new pattern P-REMOTE-MARKET-RELATIVE added; error-classification matrix updated to cover the 1.0.18 plain-string vs JSON-envelope split)

This playbook is the **executable counterpart** to the "Self-healing principle" stated in `SKILL.md`. Apply it on every cTrader mutation; consult it when a server returns unexpected output. The playbook is intentionally compact — no schema duplication, no per-quirk Detect content (that lives in `known-quirks.md`). What lives here: the GATES, the MATRIX, the TREE, and the named PATTERNS.

## 1. Pre-flight gates

Apply every applicable gate BEFORE submitting any mutation. A gate failure that triggers STOP means the agent must surface the problem to the user, not retry.

### 1.1 Quote sanity (±20% with `--allow-far-otm` override)

- **When to apply:** every order-placement or amend involving a price (`limitPrice`, `stopPrice`, `stopLoss`, `takeProfit`).
- **How to check:** compare the price to the most recent `get_spot_prices` (Remote) or symbol live quote (Local). If outside ±20% of the bid/ask band, fail the gate.
- **Action on fail:** STOP and surface to user with the last-seen reference price. If the user explicitly invokes `--allow-far-otm` (or a comparable override flag in the workflow), bypass this gate but LOG the override with the reason captured from the user.

### 1.2 Side-direction sanity

- **When to apply:** every order placement, every SL/TP amend.
- **How to check:** BUY-stop above current ask; BUY-limit below current bid; SELL-stop below current bid; SELL-limit above current ask.
- **Action on fail:** STOP and surface; suggest the symmetric tool (e.g., "this looks like a SELL-stop, did you mean STOP_SELL?").

### 1.3 SL/TP sidedness

- **When to apply:** every SL/TP value submitted alongside or atop an entry price.
- **How to check:** for a LONG position, require `stopLoss < entryPrice < takeProfit`; for a SHORT position, require `takeProfit < entryPrice < stopLoss`.
- **Action on fail:** STOP and surface to user with the computed gap; never auto-correct.

### 1.4 `volumeStep` compliance

- **When to apply:** every order placement on the Local server.
- **How to check:** read `get_symbol_details(symbolName).volumeStep`; verify `volume % volumeStep == 0`.
- **Action on fail:** round to the nearest valid step in the direction of the user's intent (typically toward smaller risk). Warn the user with the original and rounded values.

### 1.5 Schema-fields-only enforcement

- **When to apply:** every request, both servers.
- **How to check:** strip any key not declared in the MCP tool's input JSON-Schema before submitting.
- **Action on fail:** drop the offending key and LOG a warning naming the dropped key. Never let an unknown key reach the server (Q-R3 demonstrates the failure mode: `trailingStopLoss` on `create_order` is silently dropped).

### 1.6 Pipettes-vs-display detection (Q-K19)

- **When to apply:** every order DTO submission on the Remote server.
- **How to check:** flag any 5+ digit INTEGER value in a price DTO field (`limitPrice`, `stopPrice`, `stopLoss`, `takeProfit`) as a probable pipettes-leak.
- **Action on fail:** STOP and decode pipettes to display via `scripts/units_encoding.py pipettes-to-price --pipettes <int> --pip-digits <int>` BEFORE re-submitting. See [Q-K19](known-quirks.md#q-k19).

### 1.7 Required runtime fields present

- **When to apply:** every request.
- **How to check:** verify all conditionally-required fields are populated (e.g., for `create_order` with `orderType=LIMIT`, `limitPrice` is present; for `STOP_LIMIT`, both `stopPrice` and `limitPrice` are present; for `GOOD_TILL_DATE` `timeInForce`, `expirationTimestamp` is present as integer epoch ms per Q-R2).
- **Action on fail:** STOP and surface to user with the missing-field list.

## 2. Post-flight verification

Every mutation requires a post-flight read of the affected entity. Treat the mutation response as a receipt, not as ground truth on contents.

### 2.1 Re-read after every mutation

After any `place_*_order`, `create_order`, `amend_order`, `amend_position`, `close_position`, `close_position_partial`, `cancel_order`, `cancel_all_pending_orders`: re-fetch via `get_positions` (open positions), `get_pending_orders` (working orders), `get_position_details` (single-position deep read), or `get_order_history` (closed/cancelled). Verify volume, side, entry price, SL, TP, and status match the user's stated intent.

### 2.2 `amend_position` post-flight (Q-R10): always re-read to confirm BOTH legs survived

After any Remote `amend_position`, ALWAYS re-read via `get_positions(positionId)` or `get_position_details(positionId)` and verify that BOTH `stopLoss` AND `takeProfit` are present and match intent. The omit-removes quirk ([Q-R10](known-quirks.md#q-r10)) is silent at the wire level — only the post-flight read catches it. If either leg is missing, treat as a P-AMEND-SAFE violation and reissue the amend with the correct values.

### 2.3 `place_*_order` post-flight on Local (Q-L5): re-read because response carries no echo

Local placement responses carry only `{orderId, status}` ([Q-L5](known-quirks.md#q-l5)). Re-read via `get_pending_orders` (pending) or `get_positions` (filled) to confirm volume, price, SL, and TP match intent.

### 2.4 Partial close post-flight: confirm remaining volume matches expected

After `close_position_partial` (Local) or `close_position` with partial volume (Remote): re-read the position and verify `volume_remaining == volume_before - volume_closed` to within the symbol's `volumeStep`.

## 3. Error-classification matrix

Classify the error envelope first; then apply the retry / fallback / surface decision.

| Error envelope                                                                                                                                                                                                                                     | Class                      | Retry?                                                 |
|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------|--------------------------------------------------------|
| MCP `-32602: Input validation error` (Zod schema mismatch)                                                                                                                                                                                         | Caller schema mismatch     | NO (caller schema mismatch — fix caller)               |
| Remote `400` `{"error":{"code":"INVALID_REQUEST", ...}}` (rest-proxy ≤ 1.0.14 envelope for pre-upstream validation)                                                                                                                                | Server rejection (legacy)  | NO (raise to user with reason)                         |
| Remote plain-text starting with the offending tool name + actionable hint (rest-proxy 1.0.18+ envelope for pre-upstream validation, e.g., `"create_order: Absolute stopLoss is not supported..."`, `"Time range exceeds upstream cap of 720h..."`) | Server rejection (1.0.18+) | NO (raise to user, surface the embedded hint verbatim) |
| Remote `502` `{"error":{"code":"502 BAD_GATEWAY","message":"uProxy error: <CODE> — <description>", ...}}` (unchanged on 1.0.18)                                                                                                                    | Upstream broker            | NO (single retry max; suggest direct)                  |
| Local plain-text `"Order error: ..."` ([Q-L11](known-quirks.md#q-l11))                                                                                                                                                                             | Local fault                | Regex-parse, classify, retry if idempotent             |
| `{"available": false}` (e.g., `get_account_statistics` — [Q-L12](known-quirks.md#q-l12))                                                                                                                                                           | Resource absent            | Fallback path (see workflow guidance)                  |
| `truncated: true` (Local `get_trendbars` — [Q-L4](known-quirks.md#q-l4))                                                                                                                                                                           | Pagination                 | Continue with windowed loop                            |
| `hasMore: true` (Remote pagination — [Q-R7](known-quirks.md#q-r7))                                                                                                                                                                                 | Pagination                 | Continue with `hasMore` loop                           |

**Remote envelope-shape decision tree (rest-proxy 1.0.18 split):**
1. Try-parse response as JSON. If it parses AND contains an `error` object with `code` + `httpStatus` keys → JSON envelope branch (legacy `INVALID_REQUEST` 400 OR upstream `502 BAD_GATEWAY` `uProxy error:` 502).
2. Else, treat the body as plain string. Pre-upstream validation errors on rest-proxy 1.0.18+ begin with the offending tool name (e.g., `"create_order:"`) or a topic label (e.g., `"Time range exceeds upstream cap..."`) and embed an actionable workaround hint. Surface the message verbatim to the user; do NOT regex-strip it.
3. The agent should treat BOTH formats as equivalent semantically — both indicate the server REJECTED the request before reaching the broker, and the request must be corrected (not retried as-is).

## 4. Unknown-quirk decision tree

If observed behavior deviates from BOTH the MCP JSON-Schema AND `known-quirks.md`:

1. **STOP** the operation; do not assume a safe retry.
2. **CAPTURE** the exact request, the exact response, the server build identifier (`get_version` for Remote; observed-on date for Local), and the local timestamp.
3. **SURFACE to user** with the captured evidence; recommend reporting upstream to Spotware.
4. **PROVISIONAL ENTRY** — if the agent has a high-confidence workaround, add a provisional `Q-?<n>` row to `known-quirks.md` for the duration of the session (tag `status: provisional`, `confidence: low`). Promote to a numbered entry only after a second independent corroboration in a later session or by a different agent.

## 5. Named patterns (DRY recovery)

Each pattern is the canonical recovery routine for a specific quirk class. Patterns are named so workflows and reference docs can refer to them without restating the body.

### 5.1 P-AMEND-SAFE — read-then-amend with BOTH SL+TP always present

- **When to use:** every `amend_position` call on the Remote server.
- **Triggering quirk:** [Q-R10](known-quirks.md#q-r10) (omit-removes).
- **How to detect:** server family = Remote AND tool = `amend_position`.
- **Steps:**
  1. `get_positions(positionId)` — capture current `stopLoss` + `takeProfit`.
  2. Build the amend payload with the NEW value for the leg being changed AND the existing value for the leg being preserved.
  3. Call `amend_position(positionId, stopLoss=..., takeProfit=...)` with BOTH legs always populated.
  4. Re-read via `get_positions` (or `get_position_details`).
- **Post-flight check:** BOTH legs present and match intent. If either leg is missing, treat as a P-AMEND-SAFE violation and reissue the amend with the correct values.

### 5.2 P-REMOTE-MARKET-2STEP — place MARKET without SL/TP, then `amend_position` (FALLBACK)

- **When to use:** any `create_order(orderType="MARKET")` that needs SL/TP **AND** the user has stated SL/TP as ABSOLUTE PRICES that cannot be cleanly converted to point offsets at send time. For the common case where the user states SL/TP as a pip-distance or accepts conversion to points, use **P-REMOTE-MARKET-RELATIVE** (§5.6) instead — it lands both legs atomically in one call with no race window.
- **Triggering quirk:** [Q-R4](known-quirks.md#q-r4).
- **How to detect:** server family = Remote AND `orderType = "MARKET"` AND SL/TP requested AND user requires ABSOLUTE prices (e.g., "SL exactly at 1.16500 regardless of fill").
- **Steps:**
  1. `create_order(orderType="MARKET", ...)` WITHOUT `stopLoss` / `takeProfit`.
  2. Await fill; capture the resulting `positionId` from the response or via `get_positions` polling.
  3. `amend_position(positionId, stopLoss=..., takeProfit=...)` applying BOTH legs (per P-AMEND-SAFE).
  4. Re-read.
- **Post-flight check:** position exists; BOTH legs match intent.
- **Caveat:** between step 1 (fill) and step 3 (amend) the position is UNPROTECTED. For high-volatility instruments or large size, prefer P-REMOTE-MARKET-RELATIVE.

### 5.3 P-REMOTE-MARKET-RANGE — preferred slippage-bounded entry (gated)

- **When to use:** slippage-bounded immediate entry when the Q-R4-RANGE Verify-fixed gate passes at session bootstrap.
- **Triggering quirk:** [Q-R4](known-quirks.md#q-r4) + [Q-R4-RANGE](known-quirks.md#q-r4-range).
- **How to detect:** server family = Remote AND user requires slippage bound AND Q-R4-RANGE gate = PASS.
- **Gate:** run the Q-R4-RANGE Verify-fixed probe in session bootstrap; on PASS use `create_order(orderType="MARKET_RANGE", slippageInPoints=..., stopLoss=..., takeProfit=...)`; on FAIL fall back to P-REMOTE-MARKET-2STEP.
- **Steps (gate PASS):**
  1. `create_order(orderType="MARKET_RANGE", slippageInPoints=..., baseSlippagePrice=..., stopLoss=..., takeProfit=...)`.
  2. Re-read via `get_positions`.
- **Post-flight check:** fill price inside the slippage band; BOTH legs match intent.

### 5.4 P-LOCAL-OLDEST-FIRST — reverse `getIndicatorValues` array

- **When to use:** every `getIndicatorValues` consumption that expects newest-first ordering (charts, signal generation, alerts).
- **Triggering quirk:** [Q-L9](known-quirks.md#q-l9).
- **How to detect:** server family = Local AND tool = `getIndicatorValues`.
- **Steps:**
  1. Consume `response.values[]`.
  2. **REVERSE** the array before charting or downstream use.
- **Post-flight check:** `values[0]` after reversal corresponds to the most recent bar.

### 5.5 P-REMOTE-HISTORY-CHUNK — 720h windowed loop with `hasMore` + dedupe

- **When to use:** any Remote history fetch (`get_trendbars`, `get_order_history`, `get_deals`) covering a span > 720 hours.
- **Triggering quirk:** [Q-R7](known-quirks.md#q-r7).
- **How to detect:** server family = Remote AND tool ∈ {`get_trendbars`, `get_order_history`, `get_deals`} AND `(toTimestamp - fromTimestamp) > 720h`.
- **Steps:**
  1. Compute window starts of size ≤ 720h covering the requested span.
  2. Loop calling each window in chronological order (or in parallel — the rest-proxy 1.0.18 error hint explicitly states "the calls can run in parallel").
  3. On each response, if `hasMore: true`, advance the window by the last record's timestamp and continue.
  4. Dedupe accumulated results by `dealId` / `orderId` / bar-open timestamp.
- **Post-flight check:** result count matches expectation for the requested span; no duplicates by primary key.

### 5.6 P-REMOTE-MARKET-RELATIVE — single-call MARKET with `relativeStopLoss` / `relativeTakeProfit` (PREFERRED)

- **When to use:** any `create_order(orderType="MARKET")` (or `MARKET_RANGE`) on Remote that needs SL/TP, where the SL/TP is expressible as an integer POINT offset from fill price. This is the PREFERRED single-call replacement for P-REMOTE-MARKET-2STEP — there is no race window between fill and SL/TP application.
- **Triggering quirk:** [Q-R4](known-quirks.md#q-r4) (workaround, not a fix — absolute SL/TP on MARKET remain rejected; the schema's `relativeStopLoss`/`relativeTakeProfit` fields are the broker-supported alternative).
- **How to detect:** server family = Remote AND `orderType ∈ {"MARKET", "MARKET_RANGE"}` AND SL/TP can be expressed as integer points (1 point = 1 / 10^pipDigits; e.g., 30 pips on 5-digit EURUSD = 300 points).
- **Steps:**
  1. Convert the user-stated SL distance (in pips or in absolute price) to integer POINTS:
     - From pip distance: `points = pips * (10 ^ pipDigits / 10000)` (typically `points = pips * 10` for 5-digit FX pairs; the conversion is identity for 4-digit pairs; use `scripts/pip_math.py` when uncertain).
     - From absolute price: NOT directly supported by this pattern (use P-REMOTE-MARKET-2STEP instead — see §5.2 caveat).
  2. Submit `create_order(symbolId=..., orderType="MARKET", tradeSide="BUY"|"SELL", volume=..., relativeStopLoss=<positive int points>, relativeTakeProfit=<positive int points>, label=..., comment=...)`.
  3. Direction is implicit from `tradeSide`: BUY → SL = fill − relativeStopLoss; TP = fill + relativeTakeProfit. SELL → mirrored.
  4. The response carries the resolved absolute `stopLoss` / `takeProfit` in `position.stopLoss` / `position.takeProfit` plus an auto-generated `STOP_LOSS_TAKE_PROFIT` order. Capture `positionId` for downstream W2 (amend) / W3 (close) workflows.
  5. (Optional) Re-read via `get_positions(positionId)` to confirm; the values land atomically at fill so the re-read mainly serves as a sanity check, not a recovery step.
- **Post-flight check:** position exists with both `stopLoss` and `takeProfit` populated as absolute prices that match the computed offsets from the fill price (`entryPrice`). No follow-up `amend_position` call is needed.
- **Mutual exclusion:** `relativeStopLoss` is mutually exclusive with `stopLoss`; `relativeTakeProfit` is mutually exclusive with `takeProfit`. Passing the absolute form alongside the relative form on a MARKET order will be rejected with the Q-R4 error (which itself recommends `relativeStopLoss`).
- **Live confirmed:** rest-proxy 1.0.18 audit on 2026-05-14 executed `create_order(MARKET, BUY, vol=100000, relativeStopLoss=300, relativeTakeProfit=600)` on EURUSD — position 109335 opened at 1.1709 with SL=1.1679, TP=1.1769 in one round-trip.
