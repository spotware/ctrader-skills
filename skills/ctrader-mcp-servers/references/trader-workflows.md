# Trader workflows: end-to-end recipes

## How to use this document

This document contains seven end-to-end trader workflows: **W0** (session bootstrap, run once at session start) plus **W1–W6** (entry, modify, close, read, risk sizing, history). Each workflow is described with the same template — Goal, Trigger, Preconditions, Steps, Verifications, Invariants, Edge cases, Script references, Quirk and pattern references. The agent reads the workflow whose trigger matches the user's request and follows the steps in order.

Every workflow composes with BOTH servers (Local HTTP `ctrader-local-mcp` and Remote HTTP `ctrader-remote-mcp`). Where the unit encoding, tool name, or behavior differs between servers, the workflow notes the divergence INLINE within each step. Quirk-specific behavior is named by ID and linked to `references/known-quirks.md`; recovery patterns are named by ID and linked to `references/self-healing-playbook.md`. Server-specific reference material lives in `references/local-http-server.md` and `references/remote-http-server.md`.

## W0 — Session bootstrap

### Goal

Once per session, before any other workflow runs, identify the bound server family, probe the live build, refuse to apply expired workarounds, cache the symbol precision baseline, resolve the active account, and set an idempotency-key prefix. W0 is READ-ONLY (with one OPTIONAL opt-in probe described in step 7). Its output is the per-session state every subsequent workflow assumes is present.

### Trigger

Always run at session start (auto-invoked before any other workflow). After completion, cache the results for the session; do NOT re-run unless the agent is reset.

### Preconditions

None — W0 is the first thing the session does.

### Steps

1. **Identify server family.** Inspect the bound `tools/list`:
   - If `get_version` is bound → Remote (`ctrader-remote-mcp`).
   - If `ping` + `get_accounts_list` are bound → Local (`ctrader-local-mcp`).
   - If both are bound → both surfaces are in scope; run the Remote-arm AND the Local-arm of W0.
   - If neither is bound → ABORT W0; surface to the user with an instruction to bind a cTrader MCP server first.
2. **Probe build identification.**
   - Remote: call `get_version()`. Cache `version`, `buildTime`, `service`.
   - Remote: call `get_server_time()`. Cache the server timestamp and compute the agent's local-clock offset (`agent_now_epoch_ms - server_now_epoch_ms`).
   - Remote: call `ping()` if exposed to confirm round-trip health.
   - Local: call `ping()` to confirm liveness.
   - Local: call `get_server_time()` to capture the server's wall-clock; compute the local-clock offset as above.
   - Local: there is no `get_version()` equivalent — record the audit's observed-on date read from SKILL.md frontmatter `quirks_registry_min_build_local` and treat it as the build identifier.
3. **Compare against frontmatter `quirks_registry_min_build_remote` / `quirks_registry_min_build_local`.**
   - For Remote: parse the cached `version` from step 2; compare to `quirks_registry_min_build_remote` (e.g., `rest-proxy 1.0.13`).
     - If observed `version` is **OLDER**: REFUSE to apply quirks ledger workarounds (they presume the documented minimum build); STOP and surface to user with the version mismatch.
     - If observed `version` is **EQUAL**: apply ALL quirks per `references/known-quirks.md`.
     - If observed `version` is **NEWER**: lazily run the `Verify-fixed` probe for each quirk where the workflow needs it (W1 needs the [Q-R4-RANGE](known-quirks.md#q-r4-range) probe; W2 needs the [Q-R10](known-quirks.md#q-r10) probe; etc.). On probe PASS, mark that quirk as REMOVED for this session and SKIP its workaround; on probe FAIL, KEEP the workaround active.
   - For Local: there is no clean version string. Treat the frontmatter `quirks_registry_min_build_local` baseline (e.g., `local build observed-on 2026-05-13`) as the build identifier. If the user reports a recent installation, surface and propose running the Verify-fixed probes for the affected Local quirks.
4. **Load symbol precision baseline.** Read `assets/symbol_precision_table.json` once and cache the `symbols[]` map keyed by `symbol`. This is the BASELINE — per the `__note__` warning inside the JSON, ALWAYS verify per symbol at first use via `get_symbol_details(symbolName)` (Local) or per-symbol `get_symbols` lookup (Remote). The baseline serves as a fallback for symbols not yet verified during the session.
5. **Verify each used symbol at first use.** When any of W1/W2/W3/W5/W6 first touches a symbol, call `get_symbol_details(symbolName)` (Local) or look up the cached `get_symbols` map plus per-symbol metadata (Remote). Compare `lotSize`, `pipDigits`, `volumeStep`, `minVolume` against the cached baseline. On mismatch, the LIVE response is authoritative — update the session cache. Quirk references: [Q-L1](known-quirks.md#q-l1) (Local volume is broker-defined), [Q-R8](known-quirks.md#q-r8) (Remote unknown-symbol asymmetry).
6. **Resolve active account.**
   - Remote: call `get_balance()`. Cache `traderId`, `balance`, `equity`, `freeMargin`, `moneyDigits`, `depositAssetId`. Look up `depositAssetId` via the cached `get_assets()` map to get the account currency name (e.g., `USD`, `EUR`, `JPY`). Read `accountType` if present to detect hedging vs netting.
   - Local: call `get_balance()`. Cache `traderId` per [Q-L15](known-quirks.md#q-l15) — `get_accounts_list` may HIDE the active account; `get_balance.traderId` is the authoritative active-account identifier. Cache `accountType` (look for `"Hedged"`). `marginLevel: null` is NORMAL when no positions are open per [Q-L18](known-quirks.md#q-l18); accept it as a sentinel meaning "no positions".
7. **Q-R4-RANGE Verify-fixed probe (Remote only, OPT-IN).** Per [Q-R4-RANGE](known-quirks.md#q-r4-range), the `MARKET_RANGE` SL/TP acceptance at creation is build-dependent. The probe is OPT-IN ONLY and places a real MARKET_RANGE order (immediately closed). **Default: DO NOT run the probe** (cache "probe-not-run" = treat Q-R4-RANGE as FAIL → W1 will use [P-REMOTE-MARKET-2STEP](self-healing-playbook.md#p-remote-market-2step) for MARKET entries). If and only if the user has explicitly opted in (typically on a demo account):
   - Call `create_order(orderType="MARKET_RANGE", symbolId=<low-impact>, tradeSide="BUY", volume=<minimum-cents>, slippageInPoints=10, stopLoss=<safe-far-from-market>, takeProfit=<safe-far-from-market>)`.
   - If the call succeeds AND the response echoes BOTH SL and TP → mark Q-R4-RANGE as PASS for the session; W1 may use [P-REMOTE-MARKET-RANGE](self-healing-playbook.md#p-remote-market-range).
   - If the call fails with HTTP 400 `INVALID_REQUEST` → mark Q-R4-RANGE as FAIL; W1 falls back to [P-REMOTE-MARKET-2STEP](self-healing-playbook.md#p-remote-market-2step).
   - Immediately CLOSE the probe position via `close_position(positionId, volume=<as-placed>)` to avoid leaving a real position open.
8. **Set idempotency-key prefix.** Generate a session-scoped UUID prefix (e.g., `sess-<8-char-hex>`). Every mutating call in subsequent workflows includes this prefix in the order `label` or `comment` field. This prevents transient-failure re-execution from placing duplicates.

### Verifications

- Server family identified and cached.
- Build identifier captured (Remote: `version`; Local: observed-on date from frontmatter).
- Build comparison against frontmatter complete; the session's quirk-applicability map is set (per quirk: ACTIVE / REMOVED / SKIP).
- Active account resolved (`traderId`, account currency, hedging mode).
- Symbol precision baseline cached.
- Q-R4-RANGE probe run (or marked as FAIL by default with opt-in deferral).
- Idempotency-key prefix set for the session.

### Invariants

- W0 runs EXACTLY ONCE per session.
- W0 is READ-ONLY (the optional Q-R4-RANGE probe is mutating but the result is immediately closed AND requires explicit user opt-in).
- W0's output (cached state) is the precondition every subsequent workflow assumes.
- If any required step fails (no `get_version` on Remote, no `get_balance` on Local), W0 ABORTS and the session cannot proceed to mutating workflows.

### Edge cases

- **No server bound.** `tools/list` returns neither Remote nor Local fingerprints. Surface a clear "no cTrader MCP server detected; bind one and re-run" message to the user.
- **Both servers bound.** W0 runs the Remote-arm AND the Local-arm; the session cache holds both build IDs and both active accounts (one per server family). Subsequent workflows pick the server per `SKILL.md` routing rules.
- **Mismatched account currency vs symbol quote currency.** W0 caches the account currency from `depositAssetId` → `get_assets` lookup; W5 (risk sizing) uses `scripts/conversion_rate.py compute-chain` on demand to resolve the chain.
- **`get_account_statistics` unavailable on Local** per [Q-L12](known-quirks.md#q-l12). W0 does NOT attempt to call it; W5 invokes it on demand and applies the fallback.
- **Q-R4-RANGE probe denied by user.** W0 caches "probe-not-run / treat as FAIL"; W1 uses [P-REMOTE-MARKET-2STEP](self-healing-playbook.md#p-remote-market-2step) exclusively. Surface that the more efficient [P-REMOTE-MARKET-RANGE](self-healing-playbook.md#p-remote-market-range) is unavailable until the probe runs.
- **Live build NEWER than frontmatter min-build.** W0 marks the quirks as needing Verify-fixed probes; lazily runs each probe on first use of the affected workflow (e.g., the first `amend_position` in W2 triggers the Q-R10 probe). On probe PASS, that workflow skips the P-pattern; on probe FAIL, it applies the pattern.

### Script references

None (W0 is server-side reads only, with the optional opt-in probe in step 7 calling `create_order` / `close_position` directly).

### Quirk and pattern references

Quirks: [Q-R4-RANGE](known-quirks.md#q-r4-range), [Q-R8](known-quirks.md#q-r8), [Q-L1](known-quirks.md#q-l1), [Q-L12](known-quirks.md#q-l12), [Q-L15](known-quirks.md#q-l15), [Q-L18](known-quirks.md#q-l18). Pattern: [P-REMOTE-MARKET-RANGE](self-healing-playbook.md#p-remote-market-range) is gated by the step-7 probe.

## W1 — Entry orders

### Goal

Place an order to open a new position with a chosen entry-tier strategy. Three tiers in priority order:

- **TIER 1 — LIMIT / STOP / STOP_LIMIT (PREFERRED)** when non-immediate fill is acceptable; supports absolute SL/TP at creation on Remote and pip-distance SL/TP at creation on Local.
- **TIER 2 — MARKET_RANGE + `slippageInPoints` (REMOTE ONLY; gated)** by the W0 Q-R4-RANGE probe.
- **TIER 3 — MARKET (LAST RESORT)** using [P-REMOTE-MARKET-2STEP](self-healing-playbook.md#p-remote-market-2step) on Remote (per [Q-R4](known-quirks.md#q-r4)) or direct pip-distance SL/TP at creation on Local.

The sizing math is delegated to W5 (Risk sizing); W1 consumes the server-native `volume` integer that W5 produced.

### Trigger

Any user request to OPEN a new position: "buy 0.1 EURUSD with SL at 1.0820 and TP at 1.0900", "place a limit order at 1.0850", "enter long with a 30-pip stop".

### Preconditions

- W0 has completed.
- W5 (risk sizing) has produced the server-native volume (units for Local, cents for Remote).
- The agent has the user-stated SL/TP (absolute prices or pip distances).
- The agent has decided which entry tier to apply (see Step 1 Tier selection).

### Steps

1. **Tier selection (Decision Gate).**
   - If the user explicitly requested a LIMIT, STOP, or STOP_LIMIT order → **TIER 1 (preferred)**.
   - If the user requested an immediate fill AND the W0 Q-R4-RANGE probe = PASS → **TIER 2** (MARKET_RANGE with `slippageInPoints` on Remote; on Local use MARKET directly per TIER 3).
   - If the user requested an immediate fill AND Q-R4-RANGE probe = FAIL or not-run → **TIER 3** (MARKET via [P-REMOTE-MARKET-2STEP](self-healing-playbook.md#p-remote-market-2step) on Remote; MARKET with pip-distance SL/TP at creation on Local).
   - Default (no explicit preference): start with TIER 1.

2. **TIER 1 — LIMIT / STOP / STOP_LIMIT (PREFERRED).**
   - **Remote:** `create_order(symbolId=<resolved>, orderType="LIMIT"|"STOP"|"STOP_LIMIT", tradeSide="BUY"|"SELL", volume=<cents>, limitPrice=<absolute>, stopPrice=<absolute if STOP_LIMIT or STOP>, stopLoss=<absolute>, takeProfit=<absolute>, label="<idempotency-prefix>-<...>", comment="<reason>")`. Absolute SL/TP IS accepted at creation on these order types (Q-R4 affects MARKET only).
   - **Local:** `place_limit_order(symbolName=<ticker>, side=<buy|sell>, volume=<units>, limitPrice=<display>, stopLossPips=<int>, takeProfitPips=<int>, label="<idempotency-prefix>-<...>", comment="<reason>", expiresAt=<ISO 8601 with mandatory Z>)` — or `place_stop_order` / `place_stop_limit_order` analogously. Pip-distance SL/TP IS accepted at creation per `references/local-http-server.md`.
   - **`expirationTimestamp` (Remote) / `expiresAt` (Local):** when the user wants auto-expiry, pass an explicit expiration. On Remote: integer epoch milliseconds ONLY per [Q-R2](known-quirks.md#q-r2). On Local: ISO 8601 with mandatory `Z` per [Q-L8](known-quirks.md#q-l8).

3. **TIER 2 — MARKET_RANGE + `slippageInPoints` (REMOTE ONLY; gated).**
   - Precondition: W0's Q-R4-RANGE probe PASSED.
   - Apply [P-REMOTE-MARKET-RANGE](self-healing-playbook.md#p-remote-market-range).
   - Call `create_order(symbolId=<resolved>, orderType="MARKET_RANGE", tradeSide="BUY"|"SELL", volume=<cents>, slippageInPoints=<int>, baseSlippagePrice=<absolute>, stopLoss=<absolute>, takeProfit=<absolute>, label="<idempotency-prefix>-<...>", comment="<reason>")`.
   - If the call fails with HTTP 400 `INVALID_REQUEST` (Q-R4-RANGE late failure that wasn't caught by W0's probe — e.g., build changed mid-session), DOWNGRADE to TIER 3 ([P-REMOTE-MARKET-2STEP](self-healing-playbook.md#p-remote-market-2step)).
   - **Local:** TIER 2 has no direct equivalent (Local does NOT have a `MARKET_RANGE` order type). Use TIER 1 with a near-market `limitPrice` + tight `expiresAt` for analogous semantics, or TIER 3 (MARKET).

4. **TIER 3 — MARKET (LAST RESORT).**
   - **Remote PREFERRED (single call) per [Q-R4](known-quirks.md#q-r4) and [P-REMOTE-MARKET-RELATIVE](self-healing-playbook.md#p-remote-market-relative):** convert the user's pip-distance SL/TP into positive integer POINTS and pass them as `relativeStopLoss` / `relativeTakeProfit` (direction implicit from `tradeSide`):
     - `create_order(symbolId=<resolved>, orderType="MARKET", tradeSide="BUY"|"SELL", volume=<cents>, relativeStopLoss=<points>, relativeTakeProfit=<points>, label="<idempotency-prefix>-<...>", comment="<reason>")`.
     - BUY → SL = fill − relativeStopLoss; TP = fill + relativeTakeProfit. SELL → mirrored.
     - 1 point = 1 / 10^pipDigits (e.g., 5-digit EURUSD: 30 pips = 300 points; 3-digit JPY pair: 30 pips = 300 points). Use `scripts/pip_math.py` to convert user pip distances to points when the values differ between pips and points.
     - SL/TP land atomically at fill time — no race window, no second call.
     - Mutually exclusive with absolute `stopLoss`/`takeProfit`; the absolute fields would be rejected on MARKET per Q-R4. Re-read via `get_positions(positionId)` to confirm both legs.
   - **Remote FALLBACK (two-step) per [P-REMOTE-MARKET-2STEP](self-healing-playbook.md#p-remote-market-2step):** USE ONLY when the user has stated absolute SL/TP prices that cannot be cleanly converted to point offsets at send time (e.g., "SL exactly at 1.16500 regardless of fill"):
     1. `create_order(symbolId=<resolved>, orderType="MARKET", tradeSide="BUY"|"SELL", volume=<cents>, label="<idempotency-prefix>-<...>-step1", comment="<reason>")` WITHOUT `stopLoss` / `takeProfit`.
     2. Await fill; capture the resulting `positionId` from the response or via short-poll on `get_positions`.
     3. `amend_position(positionId, stopLoss=<absolute>, takeProfit=<absolute>)` applying BOTH legs per [P-AMEND-SAFE](self-healing-playbook.md#p-amend-safe) (see W2 for the full safe-amend pattern).
     4. Re-read via `get_positions(positionId)` (or `get_position_details(positionId)`) to confirm both legs landed.
     - Accept the small window between fill and amend where the position has NO SL/TP. For high-volatility instruments, prefer the PREFERRED path above.
   - **Local:** Local's MARKET accepts pip-distance SL/TP at creation directly per `references/local-http-server.md` — no two-step pattern needed. Call `place_market_order(symbolName=<ticker>, side=<buy|sell>, volume=<units>, stopLossPips=<int>, takeProfitPips=<int>, label="<idempotency-prefix>-<...>", comment="<reason>")`.

5. **Pre-flight gates (all tiers).** Apply the gates in `references/self-healing-playbook.md` Section 1 before submitting:
   - 1.1 Quote sanity (±20% with `--allow-far-otm` override).
   - 1.2 Side-direction sanity.
   - 1.3 SL/TP sidedness.
   - 1.4 `volumeStep` compliance (Local; via cached `get_symbol_details.volumeStep`).
   - 1.5 Schema-fields-only enforcement (drop unknown keys; `trailingStopLoss` on `create_order` is dropped per [Q-R3](known-quirks.md#q-r3) — for trailing SL use W2's amend pattern).
   - 1.6 Pipettes-vs-display detection per [Q-K19](known-quirks.md#q-k19) (Remote).
   - 1.7 Required runtime fields present.

6. **Post-flight verification.**
   - Re-read via `get_positions` (filled) or `get_pending_orders` (pending). For TIER 3 on Remote, the re-read is AFTER the amend step.
   - Confirm volume, side, entry price (for fills), SL, TP, and status match user intent.
   - For Local order placement, [Q-L5](known-quirks.md#q-l5) means the placement response is only `{orderId, status}` — the re-read is the only way to verify content.
   - For Local pending-order reads via `get_pending_orders`, apply [Q-L2](known-quirks.md#q-l2) (SL absolute, TP raw pips asymmetric — normalize before comparing).
   - Apply [Q-L6](known-quirks.md#q-l6) field-name asymmetry on Local responses (`limitPrice` ↔ `targetPrice`, `orderId` ↔ `id`, `expiresAt` ↔ `expiration`, `side` ↔ `tradeSide`).

### Verifications

- Post-mutation re-read shows a new position (TIER 1/2 if filled immediately, or pending order for LIMIT/STOP/STOP_LIMIT) with the expected encoding.
- Idempotency: no other position/order carries the same `label` (workflow invariant — see below).
- Volume encoding sanity: Remote `volume` is 100× the Local equivalent for the same lot count (cents vs units).

### Invariants

- **Idempotency.** Every `label` MUST include the session's idempotency-key prefix from W0. A re-run with the same label MUST NOT place a duplicate — the agent first reads `get_pending_orders` and `get_positions` to check for the existing label.
- **Risk bound** — see W5; sizing math is upstream.
- **No silent SL/TP omission.** If the user did not provide a TP, the workflow places only an SL — NEVER a position with no SL.
- **No `trailingStopLoss` on `create_order`** per [Q-R3](known-quirks.md#q-r3). If the user wants trailing SL, place a normal order first, then apply trailing via `amend_position` in W2.

### Edge cases

- **SL distance smaller than the broker's minimum** (`get_symbol_details.minDistance` if Local exposes it; broker-defined on Remote). Surface the rejection cause and propose a wider SL.
- **Sized volume below `minVolume`.** Surface the floor and ask the user whether to round up (exceeds the risk budget per W5) or skip the trade.
- **`freeMargin` insufficient** (Remote: read `get_balance.freeMargin`; Local: same). Stop before placing; show the margin gap. Cross-reference W5's safety check.
- **Q-R4-RANGE late failure on TIER 2** (live build changed mid-session). Downgrade to TIER 3 and resubmit with the same idempotency label suffix `-step1` (the resubmit is allowed because the prior attempt did NOT result in a placed order; the agent confirms via `get_pending_orders` / `get_positions` that no half-state exists).
- **Pending order during a closed market session** (forex weekend, holiday). Local has `get_symbol_sessions(symbolName)` to detect — call before submitting. Remote has no `get_symbol_sessions` equivalent; use `get_spot_prices` quote-timestamp freshness (stale quote = market closed). On closed market, REFUSE the order and surface the next session open time.
- **`IMMEDIATE_OR_CANCEL` time-in-force on Remote.** Per [Q-R5](known-quirks.md#q-r5), IOC behaves like a working LIMIT (unfilled remainder persists). Do NOT rely on IOC for cancel-remainder semantics; use TIER 2 MARKET_RANGE for slippage-bounded immediate intent, or post-flight cancel any residual via `cancel_order`.

### Script references

- `scripts/pip_math.py pips-to-price --pip-size <float> --digits <int> --reference-price <float> --pips <int>` — convert user-stated pip distance into the absolute price the Remote tools expect. **Phase 4 forward-reference:** the current script also accepts a `--server` flag as an INERT parameter; Phase 4 REMOVES `--server` entirely. The form shown here is the post-Phase-4 invocation.
- `scripts/units_encoding.py lots-to-units --lots <float> --lot-size <int>` (Local) or `scripts/units_encoding.py lots-to-cents --lots <float> --lot-size <int>` (Remote) — convert user-stated lots into the server-specific volume integer. **Phase 4 forward-reference:** `--lot-size` becomes REQUIRED in Phase 4 (currently has a default of 100 000); the form shown here is the post-Phase-4 invocation with an explicit `--lot-size` parameter.

### Quirk and pattern references

Quirks: [Q-R4](known-quirks.md#q-r4) (MARKET rejects absolute SL/TP), [Q-R4-RANGE](known-quirks.md#q-r4-range) (MARKET_RANGE acceptance gated), [Q-R3](known-quirks.md#q-r3) (trailingStopLoss dropped), [Q-R2](known-quirks.md#q-r2) (`expirationTimestamp` integer-only), [Q-R5](known-quirks.md#q-r5) (IOC persists remainder), [Q-L5](known-quirks.md#q-l5) (`place_*_order` response is only `{orderId, status}`), [Q-L6](known-quirks.md#q-l6) (field-name asymmetry), [Q-L2](known-quirks.md#q-l2) (`get_pending_orders` SL/TP asymmetric), [Q-L8](known-quirks.md#q-l8) (`expiresAt` mandatory Z), [Q-K19](known-quirks.md#q-k19) (pipettes-vs-display).

Patterns: [P-REMOTE-MARKET-2STEP](self-healing-playbook.md#p-remote-market-2step), [P-REMOTE-MARKET-RANGE](self-healing-playbook.md#p-remote-market-range), [P-AMEND-SAFE](self-healing-playbook.md#p-amend-safe).

## W2 — Modify open position

### Goal

Change an open position's SL, TP, trailing-SL flag, or both legs simultaneously. ALWAYS applies [P-AMEND-SAFE](self-healing-playbook.md#p-amend-safe) on Remote (read-then-amend with BOTH SL and TP always present in the payload) to mitigate [Q-R10](known-quirks.md#q-r10) (omit-removes). On Local, `amend_position` uses absolute-price SL/TP on OPEN positions and accepts each leg independently — but the workflow still uses read-then-amend for verification symmetry.

### Trigger

"Move my SL to breakeven on EURUSD", "Set TP to 1.0900", "Enable trailing stop", "Tighten my SL to 1.0825", "Move both legs".

### Preconditions

- W0 has completed.
- The position is OPEN (not pending) — verify via `get_positions(positionId)`.

### Steps

1. **READ the current position state** ([P-AMEND-SAFE](self-healing-playbook.md#p-amend-safe) step 1):
   - Remote: `get_positions(positionId)` or `get_position_details(positionId)`. Capture current `stopLoss`, `takeProfit`, `trailingStopLoss` (boolean), `volume`, `entryPrice`, `tradeSide`.
   - Local: `get_positions()` and filter by `id` or `positionId` in the response — note [Q-L6](known-quirks.md#q-l6): the response uses `id` even though the input field is `positionId`. Capture current `stopLoss` (absolute price), `takeProfit` (absolute price), `volume`, `entryPrice`, `tradeSide`.

2. **COMPUTE the new amend payload, with BOTH legs always populated.**
   - For the leg the user wants to CHANGE: use the new value.
   - For the leg the user wants to PRESERVE: re-pass the CURRENT value read in step 1. NEVER omit a leg (Remote omit-removes per [Q-R10](known-quirks.md#q-r10); Local accepts the absent-leg-as-preserve convention but the workflow keeps the symmetry for clarity and safety).
   - For trailing SL (Remote only): set `trailingStopLoss: true` along with a `stopLoss` anchor. Trailing SL is ONLY honored on `amend_position` per [Q-R3](known-quirks.md#q-r3), never on `create_order` or `amend_order`.

3. **EXECUTE the amend, per [P-AMEND-SAFE](self-healing-playbook.md#p-amend-safe).**
   - Remote: `amend_position(positionId, stopLoss=<absolute>, takeProfit=<absolute>[, trailingStopLoss=<bool>])` — BOTH legs always populated.
   - Local: `amend_position(positionId, stopLoss=<absolute-price>, takeProfit=<absolute-price>)` — Local's `amend_position` uses absolute prices for OPEN positions (the pip-distance form is for `place_*_order` / `amend_order` on PENDING orders). Pass BOTH legs for symmetry with the Remote pattern.

4. **POST-FLIGHT VERIFICATION** ([P-AMEND-SAFE](self-healing-playbook.md#p-amend-safe) step 4):
   - Remote: re-read `get_positions(positionId)` or `get_position_details(positionId)`. Verify BOTH `stopLoss` AND `takeProfit` are present and match intent. If either leg is MISSING, this is a [P-AMEND-SAFE](self-healing-playbook.md#p-amend-safe) violation — reissue the amend with the correct values.
   - Local: re-read `get_positions()`; same verification.

5. **Trailing-SL post-flight check (Remote only).** After enabling `trailingStopLoss: true` via `amend_position`, the re-read confirms `trailingStopLoss: true` is present on the position response per [Q-R3](known-quirks.md#q-r3). If the flag is absent, the build may have a regression — surface to user and follow the unknown-quirk decision tree in `references/self-healing-playbook.md` Section 4.

### Verifications

- Post-amend re-read shows BOTH legs match user intent.
- Trailing-SL flag (if requested) is present in the post-amend re-read.

### Invariants

- **[P-AMEND-SAFE](self-healing-playbook.md#p-amend-safe) is MANDATORY on Remote** for every `amend_position` call.
- **Read before amend** — never amend from cached/inferred state; always read the live position immediately before the amend.
- **No leg removal.** Per [Q-R10](known-quirks.md#q-r10), explicit leg-removal via `amend_position` is NOT supported (omitting REMOVES on Remote; passing `null` is REJECTED). If the user explicitly wants to remove a leg, the workflow surfaces this and proposes (a) close the position, or (b) close partially and re-issue with the new leg shape via W1.
- SL only moves TOWARD the user — never widens automatically; widening must be an explicit user instruction.

### Edge cases

- **Breakeven SL move.** User says "move SL to breakeven on EURUSD". Compute `breakeven_absolute = entryPrice`. Apply [P-AMEND-SAFE](self-healing-playbook.md#p-amend-safe) with `stopLoss=breakeven_absolute, takeProfit=<current TP>`. Re-read confirms.
- **Position closed by SL hit mid-amend.** Detect via `get_positions(positionId)` returning empty / not-found; check `get_order_history.trades[]` (Local — see [Q-L7](known-quirks.md#q-l7)) or `get_order_history` (Remote) for the closing trade. Surface to user and abort the amend.
- **Trailing SL anchor missing on Remote.** Per [Q-R3](known-quirks.md#q-r3), `trailingStopLoss: true` requires a `stopLoss` value to anchor on. If the position has no SL, the amend payload MUST include both `trailingStopLoss: true` AND `stopLoss=<anchor>`.
- **Concurrent amends** (two workflows or two agents amending the same position). The read-then-amend window is a race. The post-flight re-read catches the inconsistency; if either leg is wrong, reissue the amend with the correct intended state.
- **Pending-order amend, not open-position amend.** If the target is a pending order (not yet filled), use `amend_order` (Local) or `amend_order` (Remote) instead of `amend_position`. The Q-R2 integer-only `expirationTimestamp` constraint and the Q-L6 field-name asymmetry both apply.

### Script references

- `scripts/pip_math.py pips-to-price --pip-size <float> --digits <int> --reference-price <float> --pips <int>` — when the user states "30 pips above entry", convert to absolute price for Remote `amend_position` or for Local `amend_position` on an OPEN position (where absolute price is required). **Phase 4 forward-reference:** the legacy `--server` flag is removed in Phase 4; the form shown here is post-Phase-4.

### Quirk and pattern references

Quirks: [Q-R10](known-quirks.md#q-r10) (omit-removes — MANDATORY [P-AMEND-SAFE](self-healing-playbook.md#p-amend-safe)), [Q-R3](known-quirks.md#q-r3) (trailing SL only via `amend_position`), [Q-R2](known-quirks.md#q-r2) (if the amend touches `expirationTimestamp` on a pending order, integer epoch ms only), [Q-L6](known-quirks.md#q-l6) (response field-name `id` not `orderId`), [Q-L7](known-quirks.md#q-l7) (Local history under `trades[]` for close-by-SL detection).

Pattern: [P-AMEND-SAFE](self-healing-playbook.md#p-amend-safe) (the workflow IS this pattern, expanded inline).

## W3 — Close position

### Goal

Close all or part of an open position. Remote uses `close_position(positionId, volume)` with explicit volume (in cents, since Remote has no "close all" without a volume argument). Local uses `close_position(positionId)` for full close (no volume parameter) and `close_position_partial(positionId, volume)` for partial close (in units). Volume must comply with `volumeStep` per `get_symbol_details`.

### Trigger

"Close my EURUSD position", "Take half off", "Close 0.1 of my 0.5 lot position", "Flatten the position".

### Preconditions

- W0 has completed.
- The position is OPEN — verify via `get_positions(positionId)`.
- The user's intended close volume is known (full or partial).

### Steps

1. **READ the current position state.**
   - Remote: `get_positions(positionId)`. Capture `volume` (current open volume in cents), `volumeStep` from cached `get_symbol_details` (Remote) or per-symbol metadata.
   - Local: `get_positions()`. Capture `volume` (in units), `volumeStep` from cached `get_symbol_details(symbolName)`.

2. **COMPUTE the close volume.**
   - Full close: pass the current open `volume` as-is.
   - Partial close: compute the partial value, then ROUND DOWN to the nearest multiple of `volumeStep` toward smaller risk. If the rounded volume is below `minVolume`, surface and ask the user to confirm (close the remainder fully instead).

3. **EXECUTE the close.**
   - Remote: `close_position(positionId, volume=<cents>)`. Per `references/remote-http-server.md`, the `volume` parameter is REQUIRED on Remote — there is no "close all without volume" form. To fully close, pass the current open `volume`.
   - Local: `close_position(positionId)` for FULL close (no volume parameter; closes the full remainder by default). `close_position_partial(positionId, volume=<units>)` for PARTIAL close.
   - **Asymmetry note:** Remote's `close_position` requires `volume`; Local's `close_position` takes none and closes everything. Local's `close_position_partial` is the only partial-close tool on Local. This asymmetry is a frequent integration pitfall — the workflow must use the right tool per server.

4. **POST-FLIGHT VERIFICATION.**
   - Re-read via `get_positions()`. Verify:
     - Full close: the position is no longer in the response (or shows `volume: 0` if the broker keeps it briefly in transition).
     - Partial close: the position's `volume_remaining == volume_before - volume_closed`, within `volumeStep` tolerance.
   - Read `get_deals()` (Remote: with timestamp window since the close; Local: `get_deals(count=200, symbolName=<ticker>)`) and verify the closing trade is recorded with the expected `dealId`, side opposite to `tradeSide`, and `volume == volume_closed`.

### Verifications

- Position state after close matches intent (gone, or partial remainder correct).
- Closing deal is recorded in `get_deals` history.

### Invariants

- **Volume compliance.** Closed volume MUST be a multiple of `volumeStep`. The workflow rounds the user's requested partial-close volume DOWN to the nearest valid step toward smaller risk (closes less than requested if it doesn't fit cleanly).
- **No double-close.** The workflow re-reads `get_positions` BEFORE submitting the close to confirm the position still exists; if the position has been closed by SL/TP hit or by another agent, the workflow surfaces and aborts.
- **Read-only on `get_deals` and `get_positions`** during verification — no mutations.

### Edge cases

- **Partial close volume violates `volumeStep`.** Round DOWN to the nearest valid step toward smaller risk; warn the user with the original and rounded values.
- **Full close on a hedging account with the same symbol but opposite-direction `positionId`.** The two positions are independent on hedging accounts — the close only affects the named `positionId`. Surface to the user that the opposite-direction position remains open.
- **Closed by SL/TP hit before the workflow's close call lands.** The post-flight re-read detects the close (the position is gone); cross-check `get_deals` for the actual closing reason (SL hit / TP hit / manual). Surface to user.
- **`close_position_partial` on Local for an FX pair with broker `lotSize: 1`** per [Q-L1](known-quirks.md#q-l1). The `volume` parameter is in BROKER UNITS — e.g., `volume: 0.05` (5 micro-lots when `lotSize=1`). The workflow uses the cached `lotSize` from W0's `get_symbol_details` lookup, not the legacy 100 000-units convention.
- **History dedupe when computing closed-volume cross-check.** Local `get_deals` caps at 200 per page per [Q-L4](known-quirks.md#q-l4)-adjacent pagination semantics; for high-frequency closes, loop with timestamp-advance and dedupe by `dealId`. Local `get_order_history` returns `trades[]` per [Q-L7](known-quirks.md#q-l7) (not `orders[]`).

### Script references

- `scripts/units_encoding.py units-to-cents --units <int>` — when reading a Local position volume and computing the equivalent Remote cents for cross-checks.
- `scripts/units_encoding.py lots-to-units --lots <float> --lot-size <int>` — when the user states a partial close in lots; `--lot-size` is the broker-defined value from `get_symbol_details`. **Phase 4 forward-reference:** `--lot-size` becomes REQUIRED in Phase 4; the form shown here is post-Phase-4.

### Quirk and pattern references

Quirks: [Q-L1](known-quirks.md#q-l1) (broker-defined volume), [Q-L4](known-quirks.md#q-l4) (truncated pagination on history if reading large windows), [Q-L7](known-quirks.md#q-l7) (history under `trades[]` not `orders[]`).

No named pattern; the close mechanic is direct.

## W4 — Read positions/orders

### Goal

Enumerate currently open positions and pending orders. Remote's `get_positions` returns BOTH `positions[]` AND `orders[]` in a single call. Local's `get_positions` returns ONLY `positions[]`; pending orders are read separately via `get_pending_orders`. Apply field-name normalization for Local responses per [Q-L6](known-quirks.md#q-l6) and SL/TP shape normalization per [Q-L2](known-quirks.md#q-l2).

### Trigger

"Show my open positions", "What orders do I have pending?", "Snapshot my book", "List my positions and orders".

### Preconditions

- W0 has completed.

### Steps

1. **READ positions and orders.**
   - **Remote:** `get_positions()` returns `{positions: [...], orders: [...]}` in ONE call. Each `positions[i]` has `positionId`, `symbolId`, `tradeSide`, `volume`, `entryPrice`, `stopLoss`, `takeProfit`, `trailingStopLoss`, `swap`, `commission`, `unrealizedPnl` (apply `moneyDigits` from `get_balance` for money fields). Each `orders[i]` has `orderType`, `tradeSide`, `volume`, `limitPrice`, `stopPrice`, etc.
   - **Local:** `get_positions()` returns ONLY `positions[]`. Pending orders are returned separately by `get_pending_orders()`.
   - Local responses use PascalCase enum values per [Q-L3](known-quirks.md#q-l3) (e.g., `tradeSide: "Buy"` / `"Sell"`, `orderType: "Limit"` / `"Stop"` / `"StopLimit"`).
   - Local response field-name asymmetry per [Q-L6](known-quirks.md#q-l6): `id` (response) ↔ `orderId` (input), `targetPrice` (response — overloads `limitPrice` for LIMIT and `stopPrice` for STOP_LIMIT) ↔ `limitPrice` / `stopPrice` (input), `expiration` (response) ↔ `expiresAt` (input), `tradeSide` (response) ↔ `side` (input).
   - Local `get_pending_orders` response SL/TP asymmetry per [Q-L2](known-quirks.md#q-l2): `stopLoss` is an ABSOLUTE PRICE; `takeProfit` is a RAW PIP DISTANCE. Normalize before comparing to user-stated values: `tp_price = entryPrice ± (takeProfit × pipSize)` (sign per `tradeSide`).

2. **READ deal/trade history (optional, for context).**
   - Remote: `get_order_history(fromTimestamp=<ms>, toTimestamp=<ms>)` and `get_deals(fromTimestamp=<ms>, toTimestamp=<ms>, maxRows=50)` — see W6 for the full pagination pattern.
   - Local: `get_order_history()` returns `trades[]` per [Q-L7](known-quirks.md#q-l7) (NOT `orders[]`); dedupe by `dealId` / `orderId`. For deals: `get_deals(count=200, symbolName=<ticker>)` — see W6.

3. **NORMALIZE for the user-facing output.**
   - Decode Remote pipettes → display prices using `scripts/units_encoding.py pipettes-to-price --pipettes <int> --pip-digits <int>` per [Q-K19](known-quirks.md#q-k19).
   - Apply `moneyDigits` (Remote): `display = raw / 10^moneyDigits`.
   - Normalize Local PascalCase enums to the agent's internal convention.
   - Normalize Local TP-raw-pips → absolute price for cross-server comparison (apply `tp_price = entryPrice ± takeProfit × pipSize`).
   - Map Local response enum value-names to inputs per [Q-L13](known-quirks.md#q-l13) (e.g., a `dealStatus: "Filled"` response does not necessarily match the input enum `"FILLED"`).

### Verifications

- Every position has `positionId`, `volume`, `tradeSide`, `entryPrice`.
- Every pending order has `orderId` (Remote) or `id` (Local), `orderType`, `volume`, and the conditional-required price field (`limitPrice` / `stopPrice` / both).
- Pipettes / `moneyDigits` decoding produces sane numerical ranges (e.g., balance is not a 10-digit integer).

### Invariants

- **Read-only workflow.** No mutations.
- **No silent data loss.** When pagination is involved (W6's deal history extension), every page is consumed and deduped by primary key.
- **Encoding consistency.** Remote price fields are pipettes → ALWAYS decode before showing to user; Local price fields are display floats → pass through.

### Edge cases

- **No positions, no orders.** Return an empty list to the user with the appropriate "No open positions / No pending orders" message.
- **`marginLevel: null` on Local `get_balance`** per [Q-L18](known-quirks.md#q-l18). When the read is part of a margin-safety check, treat `null` as "no positions" and short-circuit. W5 handles this case.
- **`get_account_statistics` unavailable on Local** per [Q-L12](known-quirks.md#q-l12). When the read includes lifetime statistics, check `response.available` first; on `false`, derive from in-session reads (see W5).
- **Stale Remote symbol cache.** If a position references a `symbolId` not in the cached `get_symbols` map, refresh `get_symbols` once per session.
- **PascalCase enum-value divergence on Local** per [Q-L13](known-quirks.md#q-l13). Normalize via an explicit input-enum ↔ response-enum map in the agent's normalization layer; never compare response enum values directly to user-supplied input strings.
- **Local error envelopes as plain-text strings** per [Q-L11](known-quirks.md#q-l11). On a read failure, regex-classify the message and apply the error-classification matrix in `references/self-healing-playbook.md` Section 3.

### Script references

- `scripts/units_encoding.py pipettes-to-price --pipettes <int> --pip-digits <int>` — Remote pipettes-to-display conversion.
- `scripts/units_encoding.py parse-money --raw <int> --money-digits <int>` — Remote `moneyDigits`-encoded money to display.

### Quirk and pattern references

Quirks: [Q-L2](known-quirks.md#q-l2) (`get_pending_orders` asymmetric SL/TP), [Q-L3](known-quirks.md#q-l3) (PascalCase responses), [Q-L6](known-quirks.md#q-l6) (field-name asymmetry), [Q-L7](known-quirks.md#q-l7) (`trades` key on history), [Q-L11](known-quirks.md#q-l11) (plain-text error strings), [Q-L12](known-quirks.md#q-l12) (`get_account_statistics` unavailable), [Q-L13](known-quirks.md#q-l13) (response enum value-name divergence), [Q-L18](known-quirks.md#q-l18) (`marginLevel: null` normal), [Q-K19](known-quirks.md#q-k19) (pipettes-vs-display decode on Remote).

No named pattern.

## W5 — Risk sizing

### Goal

Translate a user-stated risk percentage (or risk amount) plus a stop-loss distance into a server-native volume figure. Validate the candidate position against the account's margin level so the resulting open does not bring `(equity / (used_margin + forecast_margin)) × 100%` below 2× the broker's stop-out level. Output: a server-encoded `volume` (units for Local, cents for Remote) plus a forecast margin requirement. The output is consumed by W1.

> **Phase 4 forward-reference (transition note):** the script CLI invocations shown below reference the POST-PHASE-4 surface. Specifically: `pip_math.py` will no longer accept a `--server` flag; `units_encoding.py lots-to-units` will require an explicit `--lot-size` parameter; `tiered_margin.py compute` will wire `--account-currency-rate-vs-usd` into the math and emit both `margin_usd` AND `margin_account_ccy`; `conversion_rate.py compute-chain` will treat loose symbol matching as default with `--strict-symbols` as the opt-in. Until Phase 4 ships, the current scripts accept the legacy form; the workflow narrative below documents the end-state.

### Trigger

"Size for 30 pips SL on EURUSD at 1% risk, balance 10 000 USD", "Risk 2% on XAUUSD with SL at 1900", "How much can I open with 1% risk?".

### Preconditions

- W0 has completed (account state + symbol precision cached).

### Steps

1. **Compute pip value per lot in account currency.**
   - Invoke `scripts/conversion_rate.py compute-chain --from-asset <symbol-quote-ccy> --to-asset <account-ccy> --quotes '<JSON map of get_spot_prices results>'`. Output: `{"rate": <float>, "chain": [...], "warnings": [...]}`.
   - Pip value per lot = `lot_size_baseline × pip_size × conversion_rate` (in account currency).

2. **Compute risk amount in account currency.**
   - From risk-percent: `risk_amount = balance × (risk_pct / 100)`.
   - From risk-amount directly: `risk_amount = <user-supplied value>`.

3. **Compute volume via `scripts/position_sizing.py`.**
   - From risk-percent: `scripts/position_sizing.py from-risk-percent --balance <float> --risk-pct <float> --sl-pips <int> --pip-value-per-lot <float> --conversion-rate <float>`.
   - From risk-amount: `scripts/position_sizing.py from-risk-amount --risk-amount <float> --sl-pips <int> --pip-value-per-lot <float> --conversion-rate <float>`.
   - Output: `{"units": <int>, "cents": <int>, "risk_currency_amount": <float>, "warnings": [...]}`.

4. **Validate against margin tier curve.**
   - Invoke `scripts/tiered_margin.py compute --volume-base-units <int> --quote-rate-usd <float> --account-currency-rate-vs-usd <float> --tiers '<JSON tier curve>'`. Output: `{"margin_usd": <float>, "margin_account_ccy": <float>, "per_tier_breakdown": [...]}`. **Phase 4 forward-reference:** `--account-currency-rate-vs-usd` is currently INERT in the argparse; Phase 4 wires it into the math and the second output field. The invocation shown here is post-Phase-4.
   - Compute `post_trade_margin_level = (equity / (used_margin + margin_account_ccy)) × 100`.

5. **Decision: OK or REFUSE.**
   - If `post_trade_margin_level ≥ 2 × stop_out_level` AND `drawdown_pct ≤ user_max_drawdown_pct`, return OK with the computed `units` (Local) or `cents` (Remote).
   - Otherwise, return REFUSE with the failing condition surfaced to the user (e.g., "Would bring margin level to 35%, below the 2× stop-out floor of 100% — refusing").

6. **Account-statistics fallback (Q-L12).**
   - On Local, attempt `get_account_statistics()` for peak-equity tracking. If the response is `{"available": false}` per [Q-L12](known-quirks.md#q-l12), derive peak equity from in-session balance snapshots (W0 cached the initial balance; subsequent W5 invocations track the high-water mark).
   - On Remote, there is no `get_account_statistics`; ALWAYS derive peak equity from session reads.

7. **Hedging-mode handling.**
   - On hedging accounts (`accountType: "Hedged"` from `get_balance`), used margin can be LOWER than the sum of individual position margins (offsetting positions). Read `get_balance.margin` directly rather than computing from positions.

### Verifications

- Equity / used margin re-read within the last 5 seconds of the safety decision.
- Computed `volume` complies with the symbol's `volumeStep` and `minVolume`.

### Invariants

- The 2× stop-out buffer is the FLOOR — never allow opening that brings `post_trade_margin_level` below 2× the broker's stop-out level (from `SKILL.md` "Stop-out and margin level" section).
- Risk amount is the UPPER BOUND — the script rounds DOWN volumes to respect `volumeStep`.
- Read account state before EVERY safety check — never reuse cached `freeMargin` across multi-step decisions.

### Edge cases

- **`marginLevel: null` on Local** per [Q-L18](known-quirks.md#q-l18). Treat as "no positions / unconstrained"; short-circuit the stop-out check (the buffer condition is vacuously satisfied when `used_margin == 0`).
- **`get_account_statistics` unavailable on Local** per [Q-L12](known-quirks.md#q-l12). Fallback to in-session-derived peak equity (see step 6).
- **Conversion chain undefined** (e.g., exotic pair with no chain via USD / EUR / GBP). `scripts/conversion_rate.py compute-chain` returns `warnings: ["no chain"]`; surface to the user with a recommendation to bridge via a different reference currency.
- **Hedging-mode offsetting positions.** Used margin is lower than the sum of individual position margins; read `get_balance.margin` directly.
- **Stop-out level unknown** (broker has not exposed it). Default to 50% and warn the user.
- **Account in negative equity / margin call already.** Surface immediately; REFUSE any new position.
- **W5 REFUSE override.** A user may explicitly invoke a "force" mode to bypass REFUSE. The workflow LOGS the override and warns of the elevated risk; it does not silently auto-approve.

### Script references

- `scripts/conversion_rate.py compute-chain --from-asset <CCY> --to-asset <CCY> --quotes '<JSON>'` — symbol-quote → account-currency rate chain. **Phase 4 forward-reference:** Phase 4 ADDS a `--strict-symbols` flag (current behavior is strict; Phase 4 makes loose matching the default with `--strict-symbols` as opt-in). The form shown here is post-Phase-4 default (no flag = loose matching).
- `scripts/position_sizing.py from-risk-percent --balance <float> --risk-pct <float> --sl-pips <int> --pip-value-per-lot <float> --conversion-rate <float>` — risk-percent → volume.
- `scripts/position_sizing.py from-risk-amount --risk-amount <float> --sl-pips <int> --pip-value-per-lot <float> --conversion-rate <float>` — risk-amount → volume.
- `scripts/tiered_margin.py compute --volume-base-units <int> --quote-rate-usd <float> --account-currency-rate-vs-usd <float> --tiers '<JSON>'` — forecast margin in USD and account currency. **Phase 4 forward-reference:** `--account-currency-rate-vs-usd` exists in the current argparse but is INERT; Phase 4 wires it into the math.
- `scripts/units_encoding.py lots-to-units --lots <float> --lot-size <int>` (Local) — `--lot-size` REQUIRED post-Phase-4.
- `scripts/units_encoding.py lots-to-cents --lots <float> --lot-size <int>` (Remote) — `--lot-size` REQUIRED post-Phase-4 (forex: `--lot-size 100000`; Local ICMarkets: `--lot-size 1`).
- `scripts/pip_math.py pips-to-price --pip-size <float> --digits <int> --reference-price <float> --pips <int>` — convert user-stated pip distance to absolute price for Remote. **Phase 4 forward-reference:** the legacy `--server` flag is REMOVED in Phase 4; the form shown here is post-Phase-4.

### Quirk and pattern references

Quirks: [Q-L1](known-quirks.md#q-l1) (broker-defined volume), [Q-L12](known-quirks.md#q-l12) (`get_account_statistics` unavailable), [Q-L18](known-quirks.md#q-l18) (`marginLevel: null` normal).

No named pattern.

## W6 — History

### Goal

Reconstruct executed-trade and order history over a user-specified time window. Remote uses `get_order_history` + `get_deals` with the 720h window cap and `hasMore` pagination per [P-REMOTE-HISTORY-CHUNK](self-healing-playbook.md#p-remote-history-chunk). Local uses `get_order_history` (returns `trades[]` per [Q-L7](known-quirks.md#q-l7)) and `get_deals(count=200)` with the 200-deals-per-page cap. `getIndicatorValues` reads apply [P-LOCAL-OLDEST-FIRST](self-healing-playbook.md#p-local-oldest-first) per [Q-L9](known-quirks.md#q-l9).

### Trigger

"Show me every trade from last week", "Audit my account from 2026-04-01 to 2026-04-30", "Pull the last 1000 deals", "Backfill 5000 H1 candles".

### Preconditions

- W0 has completed.
- The user has specified a time window OR a deal-count target.

### Steps

1. **CHUNK the time window (Remote — 720h cap).**
   - Remote: if `(toTimestamp - fromTimestamp) > 720 hours` per [Q-R7](known-quirks.md#q-r7), apply [P-REMOTE-HISTORY-CHUNK](self-healing-playbook.md#p-remote-history-chunk):
     1. Compute window starts of size ≤ 720h covering the requested span.
     2. Loop through windows in chronological order.
     3. On each response, check `hasMore`. If `hasMore: true`, advance the window by the last record's timestamp and continue.
     4. Dedupe accumulated results by `dealId` / `orderId` / bar-open timestamp (depending on which endpoint).
   - **Propagation lag (Remote) per [Q-R11](known-quirks.md#q-r11):** `get_deals` / `get_order_history` lagged behind mutation responses by N seconds to minutes on rest-proxy ≤ 1.0.14; the 2026-05-14 audit on rest-proxy 1.0.18 PASSED the Verify-fixed probe (session 1 of 5 — quirk entry retained pending 4 more PASS sessions). Until the 5-session gate clears: for IMMEDIATE post-close verification, prefer the `deal` / `position` objects in the mutation response itself; for history audits, treat the trailing tail of the window as eventually-consistent (poll with backoff or re-query later). Once Q-R11 is removed from the ledger this caveat can be dropped.
   - Local: no 720h cap, but `get_deals` caps at 200/request. Apply windowed loop with timestamp-advance and dedupe by `dealId`.

2. **PULL orders in the window.**
   - Remote: `get_order_history(fromTimestamp=<ms>, toTimestamp=<ms>)` per chunk. Response has `hasMore` and `orders[]`.
   - Local: `get_order_history()` returns the CURRENTLY LOADED history under key `trades[]` per [Q-L7](known-quirks.md#q-l7) — NOT `orders[]`. The user may need to scroll the History tab in the cTrader UI to force-load older periods; surface this constraint. Adapt the consumer code to read `response.trades[]`.

3. **PULL deals in the window.**
   - Remote: `get_deals(fromTimestamp=<ms>, toTimestamp=<ms>, maxRows=50)` (default `maxRows`). Apply [P-REMOTE-HISTORY-CHUNK](self-healing-playbook.md#p-remote-history-chunk) if window > 720h. Pace successive calls to stay under the historical 5 r/s cap (see `references/remote-http-server.md` Rate limits section). Dedupe by `dealId`.
   - Local: `get_deals(count=200, symbolName=<ticker>)`. Per-symbol page cap. Loop with timestamp-advance for multi-window backfills; dedupe by `dealId`.

4. **PULL trendbars (historical price bars).**
   - Remote: `get_trendbars(symbolId=<id>, period=<one-of-9-values>, fromTimestamp=<ms>, toTimestamp=<ms>)`. Note [Q-R1](known-quirks.md#q-r1): the `period` enum is 9 values (`M_1, M_5, M_15, M_30, H_1, H_4, D_1, W_1, MN_1`), NOT 26. Apply [P-REMOTE-HISTORY-CHUNK](self-healing-playbook.md#p-remote-history-chunk) if window > 720h. Dedupe by bar-open timestamp.
   - Local: `get_trendbars(symbolName=<ticker>, period=<value>, from=<ISO-with-Z>, to=<ISO-with-Z>, count=<≤1000>)`. Per [Q-L4](known-quirks.md#q-l4), `count > 1000` is silently truncated with `truncated: true` on the response — loop with timestamp-advance and dedupe by bar-open timestamp. Per [Q-L8](known-quirks.md#q-l8), `from` / `to` MUST include the `Z` suffix.

5. **PULL indicator values (Local only).**
   - Local: `getIndicatorValues(<indicator-id>, <output-index>, ..., count=<≤1000>)`. Apply [P-LOCAL-OLDEST-FIRST](self-healing-playbook.md#p-local-oldest-first): the response's `values[]` is OLDEST-first per [Q-L9](known-quirks.md#q-l9); REVERSE the array before charting / signal generation / alerts.

6. **NORMALIZE for the user-facing output.**
   - Remote: decode pipettes → display via `scripts/units_encoding.py pipettes-to-price` per [Q-K19](known-quirks.md#q-k19); decode money via `scripts/units_encoding.py parse-money` (apply `moneyDigits`).
   - Local: pass through (display values already; `tradeSide` PascalCase per [Q-L3](known-quirks.md#q-l3)).

7. **GROUP and AGGREGATE.**
   - Group by `positionId` (Remote uses `positionId` on deals; Local uses `id` on trades — apply [Q-L6](known-quirks.md#q-l6) field-name normalization).
   - For each group: round-trip P&L = `sum(deal P&L) - commission - swap`. Apply `moneyDigits` on Remote money fields.
   - Aggregate by user's filter (label prefix, symbol, time bucket, etc.).

### Verifications

- Pagination completeness: for Remote, every response with `hasMore: true` was followed by a continuation call until `hasMore: false`.
- Volume sum integrity: `sum(deal volumes by positionId) == position.volume` per round trip.
- Dedupe integrity: no duplicate `dealId` / `orderId` across the accumulated pages.

### Invariants

- **Read-only.** No mutations.
- **Dedupe is mandatory.** Window-boundary deals appear in TWO consecutive windows; key by `dealId` to filter.
- **Encoding consistency.** Remote money fields are scaled by `moneyDigits`; ALWAYS decode before user display.

### Edge cases

- **Local history not fully loaded.** Surface the constraint and recommend the UI workaround (scroll the History tab in the cTrader UI). The Local server only returns what the cTrader UI client has currently loaded.
- **Remote window too wide to fit one `get_deals` page.** Use the timestamp-advancement pattern ([P-REMOTE-HISTORY-CHUNK](self-healing-playbook.md#p-remote-history-chunk)); see `references/remote-http-server.md` Pagination via `hasMore` section for the underlying mechanic.
- **Rate-limit pressure on Remote during a wide scan.** Pace successive `get_trendbars` calls to stay under the historical 5 r/s cap (see `references/remote-http-server.md` Rate limits section).
- **Labels reused across strategies** (collision). Surface the collision and ask the user to disambiguate (e.g., by additional filters like symbol or time bucket).
- **Open positions inside the window.** Include them with realized P&L = 0 and unrealized P&L from a fresh `get_positions()` read.
- **Symbol disabled on Remote** (`enabled: false` on `get_symbols`). The historical data may still exist; surface that the symbol is disabled and proceed with the read (it does not affect history reads).

### Script references

- `scripts/units_encoding.py parse-money --raw <int> --money-digits <int>` — Remote `moneyDigits` decoding on every money field returned by `get_deals` and `get_position_details`.
- `scripts/units_encoding.py pipettes-to-price --pipettes <int> --pip-digits <int>` — Remote pipettes-to-display on price fields.

### Quirk and pattern references

Quirks: [Q-R1](known-quirks.md#q-r1) (Remote `period` enum 9 values), [Q-R7](known-quirks.md#q-r7) (720h window cap), [Q-R11](known-quirks.md#q-r11) (history propagation lag), [Q-L3](known-quirks.md#q-l3) (PascalCase responses), [Q-L4](known-quirks.md#q-l4) (`get_trendbars` truncation), [Q-L6](known-quirks.md#q-l6) (field-name asymmetry on Local), [Q-L7](known-quirks.md#q-l7) (`trades` key on history), [Q-L8](known-quirks.md#q-l8) (timestamp `Z` suffix on Local), [Q-L9](known-quirks.md#q-l9) (indicator values OLDEST-first), [Q-K19](known-quirks.md#q-k19) (pipettes-vs-display decode on Remote).

Patterns: [P-REMOTE-HISTORY-CHUNK](self-healing-playbook.md#p-remote-history-chunk), [P-LOCAL-OLDEST-FIRST](self-healing-playbook.md#p-local-oldest-first).
