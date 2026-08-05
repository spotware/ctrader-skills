# Command reference: the read-only surface

Per-verb detail for every command that only reads data. Each entry gives the pipeline it uses, the flags that make it work, the exact field names and casing of the payload, and the shape you get back when there is nothing to return. Field names are quoted verbatim from live payloads.

## accounts

Batch verb. Call it as `accounts -e` (no `--account`; the batch form rejects that flag with `Error: Parameter account is not allowed`). Payload is a flat PascalCase array with no banner and no header, stdout starting at byte zero: `[{"Id":47246474,"Number":5816091,"Broker":"Spotware","Live":false,"DepositCurrency":"EUR","Leverage":100,"Balance":1000.0}]`. `Live: false` is the field to check before authorizing any mutation on the account. Adding `-q` reroutes the same verb into the shell pipeline: the payload becomes `{"accounts":[{"traderLogin":...,"brokerName":...,"depositCurrency":...,"environment":"demo","isCurrent":true,"balance":...,"accountName":null,"leverage":...,"accountType":"Hedged","accessRights":"FullAccess","accountStatus":"Active","isSwapFree":false,"isLimitedRisk":false,"traderId":...}]}` after a banner and header, with several fields (`environment`, `accountType`, `accessRights`, `accountStatus`, `isSwapFree`, `isLimitedRisk`, `traderId`) that the batch shape does not carry at all. An unrecognized `--broker=` value returns exit 0 with an empty array `[]`, not an error; treat the empty array as "no accounts match that filter."

## symbols

Batch verb. As with `accounts`, the batch and shell-routed forms genuinely differ in schema, not just casing. Call it `symbols --account=<n> -e`: this batch form requires `--account` (the inverse of `accounts`, which forbids it). The batch payload is PascalCase with only `Id`, `Name`, `Description` per entry, no banner: `[{"Id":1,"Name":"EURUSD","Description":"Euro vs US Dollar"}, ...]`. Expect hundreds of entries from a typical broker. Add `-q` and the same verb becomes shell-routed: the payload wraps as `{"symbols":[{"name":...,"description":...,"category":"Default Category","assetClass":"Forex"}, ...]}` — the entries gain `category` and `assetClass` but carry no id field in any casing, so the numeric `Id` exists only in the batch shape. Omitting `--account` on the batch form returns exit 1 with `Error: Option account does not exist` followed by the full usage block on stdout. Because this payload is large, filter by name client-side or use `symbol --symbol=<name>` for one instrument's detail rather than loading the full array into context.

## periods

Bare invocation only, no flags whatsoever, no credentials: `ctrader-cli.exe periods`. Passing `-e` to it returns exit 1 with `Error: Parameter e is not allowed`. The payload is plain text, not JSON: a space-separated token list such as `t1 t2 t3 ... HMonth1`, mixing lowercase (`m1`, `h1`, `t1`) and capitalized (`D1`, `W1`, `Month1`) family names. Parse it as whitespace-separated tokens. Period tokens accepted by other commands (`candles`) are case-insensitive even though this canonical list shows one casing per family; a call with `--period=d1` succeeds and echoes back `"timeframe": "d1"` verbatim rather than normalizing to the list's casing.

## account

Always shell-routed; there is no batch code path for this verb regardless of flags. Call it `account --account=<n> -e`. A bare positional number at launch (`account 5816091 -e`) exits 0 but is silently discarded — the payload is the default account's regardless of the number passed — so always use the `--account` flag, which is applied and validated. Payload after the banner and `[timestamp] account <n>` header is a camelCase object: `isCurrent`, `balance`, `equity`, `margin`, `freeMargin`, `marginLevel`, `netProfit`, `grossProfit`, `leverage`, `depositAsset`, `accountName`, `accountType`, `traderId`, `brokerName`, `connectionState`, `isSwapFree`.

## account-stats

Always shell-routed, same wrapper as `account`. Call it `account-stats --account=<n> -e`. On an account with no trading history, the payload collapses to a single boolean: `{"available": false}`. No public source documents the populated payload, so discover its shape from a live call against an account with history rather than assuming fields.

## symbol

Always shell-routed. A bare positional symbol name does not work at launch (`symbol EURUSD -e` returns exit 1: `Error: 'symbol' is required. Provide it as a positional argument inside the shell, or pass --symbol=<value> when launching the command.`). The working form is `symbol --symbol=<name> --account=<n> -e`. Success payload: `{"name","description","category","assetClass","digits","pipSize","lotSize","minVolume","maxVolume","volumeStep","bid","ask"}` — the complete field set needed for order sizing (for EURUSD: `digits=5`, `pipSize=0.0001`, `lotSize=100000`, `minVolume=1000`, `maxVolume=10000000`, `volumeStep=1000`). There is no commission field and no swap field in this output. Commission is a `backtest` input (`--commission`, alongside `--spread`); no swap flag exists on any command, and the only swap-related field anywhere in the CLI surface is the `isSwapFree` boolean in the `account`/`accounts` payloads. A resolvable-format but nonexistent name returns a distinct exit 1: `Error: Symbol not found: NOTAREALSYMBOL` — different from the missing-flag error above, so branch on message text, not just exit code.

## sessions

Always shell-routed. Call it `sessions --symbol=<name> --account=<n> -e`. Payload: `{"symbolName","timeZone","marketIsAlwaysOpen","sessions":[{"start","end","startSecond","endSecond"}, ...]}`. For EURUSD, five session windows are returned (Sunday through Thursday), each with human-readable `start`/`end` day-and-time strings plus integer `startSecond`/`endSecond` giving seconds-of-week offsets for machine parsing.

## price

Always shell-routed. A bare positional symbol does not work outside the shell; use `price --symbol=<name> --account=<n> -e -q`. Success payload: `{"symbolName","bid","ask","spread","high","low","open"}`. An unknown symbol returns exit 1 with `Error: Symbol not found: NOTASYMBOL. Use 'symbols' to list available symbols.` — note this wording differs from the `candles` unknown-symbol message below; do not assume one canonical unknown-symbol string across market-data commands.

## prices

Always shell-routed. Call it `prices --symbols=<name1>,<name2>,... --account=<n> -e -q`. Unlike `price` and `candles`, this plural form degrades per symbol inside a still-exit-0 response rather than hard-failing the whole call: `{"results":[{"symbolName":"EURUSD","ok":true,"quote":{...}},{"symbolName":"NOTASYMBOL","ok":false,"error":"Symbol not found: NOTASYMBOL. Use 'symbols' to list available symbols."}]}`. When processing a multi-symbol batch, check the per-item `ok` field rather than relying on the overall exit code.

## candles

Always shell-routed. Use `candles --symbol=<name> --period=<token> --account=<n> -e -q` plus either `--count=<n>` or a `--from=`/`--to=` range.

Count form payload: `{"symbolName","timeframe","requested","returned","available","bars":[...]}`. `available` reports the total cached bars for that symbol-and-period pair and varies by timeframe (for example 13999 for EURUSD m1 versus 1296 for D1). **The count form returns at most 1000 bars per call**: requesting `--count=10000` or `--count=1001` both yield `"requested":1000` with no warning. To retrieve more history, page backward or forward through repeated `--from`/`--to` windows; there is no cursor or offset parameter.

Range form payload has a different shape, without `requested`/`available`: `{"symbolName","timeframe","from","to","returned","bars":[...]}`. Accepted date formats for `--from`/`--to`: `yyyy-MM-dd`, `dd/MM/yyyy` (day-first), and a bare ISO datetime without offset — all three are interpreted as UTC. Omitting `--to` defaults it to the exact invocation instant; the still-open current bar is excluded, so only fully closed bars come back. The `to` bound is inclusive (a 10:00-14:00 window returns exactly 5 hourly bars). A reversed range (`from` after `to`) is rejected at exit 1 with `Error: Invalid parameters: 'from' must be before 'to'.` A closed-market window (a weekend date range) returns exit 0 with `{"returned":0,"bars":[]}` — this, not an error, is how you distinguish "no data in this window" from a malformed request.

**Result ordering is always oldest-first ascending**, in both the count and range forms; never assume newest-first. Daily (`D1`) bar timestamps are not midnight UTC — they carry the broker's daily session boundary (`21:00Z` during summer time, `22:00Z` during winter time), so deriving "which calendar day" a bar belongs to from the UTC date component alone will be off by the session-boundary offset.

An unknown symbol returns exit 1 with `Error: Symbol not available: NOTASYMBOL` — worded differently from `price`'s `Symbol not found` message. An invalid period value returns exit 1 with `Error: Invalid timeframe: 'BADPERIOD'.`, a distinct message you can match separately from the symbol-not-found family.

## orders

Shell-routed only (no batch code path): the CLI's own `--help` lists `orders` only under interactive commands, never under BATCH MODE. Call it `orders --account=<n> -e -q`. Omitting `-q` still exits 0 eventually under redirected stdin, but the JSON is followed by the full interactive command menu and a `Bye.` line — noise to skip past, not a failure signal. `--account` can be omitted for a cTID with exactly one linked account (the banner then reads `Using your only account: ...` instead of `Using account: ...`), but pass it explicitly for determinism.

Populated payload: `{"orders": [{"id","symbolName","tradeSide","orderType","volume","volumeLots","targetPrice","limitPrice","slippagePips","currentPrice","stopLoss","stopLossPips","takeProfit","takeProfitPips","expiration","label","comment"}, ...]}`. Optional fields are `null` when not set (`limitPrice`, `slippagePips`, `currentPrice`, `stopLoss`, `stopLossPips`, `takeProfit`, `takeProfitPips`, `expiration`).

**Empty-result shape:** `{"orders": []}`, exit 0.

## positions

Same routing and call shape as `orders`: `positions --account=<n> -e -q`.

**Empty-result shape:** `{"positions": []}`, exit 0 — the normal case on an account with no open trades. For a populated entry, expect naming by analogy with `orders`/`orders-history` and confirm the exact field set on first use.

## order

Shell-routed only. `order <id>` as a bare trailing positional does **not** work at launch time — that syntax is documented shell-prompt-only in `--commands`' own entry for this verb — and returns exit 1: `Error: 'order' is required. Provide it as a positional argument inside the shell, or pass --order=<value> when launching the command.` The working non-interactive form is `order --order=<id> --account=<n> -e -q`.

A known id returns the order object directly, unwrapped (the same field set as one `orders[]` array element, not wrapped under an `order` key and not array-wrapped): `{"id":312753167,"symbolName":"EURUSD", ...}`.

**Unknown-id shape:** exit 1 with a plain-text, non-JSON line: `Order #999999999 not found.` Do not attempt to JSON-parse stdout unconditionally; check the exit code first, or treat a JSON-parse failure itself as the not-found signal. This lookup is scoped to currently active orders — `order`/`orders` do not search closed or historical orders; use `orders-history` for that.

## position

Shell-routed only, symmetric with `order`. Bare positional fails identically at launch; use `position --position=<id> --account=<n> -e -q`.

**Unknown-id shape:** exit 1, plain text: `Position #999999999 not found.` Like `order`, this lookup is scoped to currently open positions, not closed history.

## exposure

Shell-routed only. Call it `exposure --account=<n> -e -q`. The JSON root key is the plural `exposures`, even though the command itself is singular — do not assume the payload key mirrors the command name.

**Empty-result shape:** `{"exposures": []}`, exit 0. For a populated entry, confirm the exact field set on first use.

## orders-history

Shell-routed only; no `<symbol>` positional form exists for this verb (per `--commands`, only bare, `<count>`, and `<from> <to>` forms are defined) — `deals` supports the symbol form but `orders-history` does not. **History subcommands apply only the flags that fit their positional template.** A bare trailing CLI positional (e.g. `orders-history 50` typed at launch) is not applied at all; use the named launch flags `--count=`, `--from=`, `--to=` instead, which the CLI translates internally into the positional template. An unsupported flag for this subcommand, such as `--symbol=`, is silently not applied rather than rejected: `orders-history --symbol=EURUSD --count=5` still runs, and its header line reads plain `orders-history 5` with no trace of the symbol filter. **The echoed header line is exactly how you confirm which filters actually took effect** — read it before trusting the query you think you sent, since `--commands` output alone defines which flags a given history subcommand's template accepts.

Count-based call (`orders-history --count=<n> --account=<n> -e -q`) returns `{"requested","returned","lookbackDays","orders":[...]}` when the count covers every order in the lookback window, and adds an `available` key — `{"requested","returned","available","lookbackDays","orders":[...]}` — when more orders exist in the lookback window than were returned (for example `--count=3` against 4 matching orders returns `"available": 4`, while a call whose count covers every matching order, or an empty history, omits the key). Default `requested` is 100 when `--count` is omitted; `lookbackDays` reports the lookback window (30) and appears only in this count-based envelope.

Range-based call (`orders-history --from=<date> --to=<date> --account=<n> -e -q`) returns a different envelope: `{"from","to","returned","available","orders":[...]}` — no `requested`/`lookbackDays` here, and `available` is present unconditionally rather than only on truncation. Dates without an explicit offset are interpreted as UTC (`2026-08-01` becomes `"2026-08-01T00:00:00.000Z"`).

Each order object in either envelope carries: `id`, `symbolName`, `tradeSide`, `orderType`, `status`, `volume`, `volumeLots`, `executedVolume`, `executedVolumeLots`, `targetPrice`, `executionPrice` (null when never filled), `stopLoss`, `takeProfit`, `positionId` (null when never filled, the cross-reference to a resulting position once filled), `openTime` (ISO-8601 UTC with a trailing `Z`), `closeTime` (null while still open), `expiration`, `label`, `comment`. A `--to` bound resolving to midnight of the current day can fail to exclude still-open orders opened later that same day; a range entirely outside the data window returns an empty result. If you need a strict upper bound on `openTime`, filter client-side rather than relying solely on `--to`.

**Empty-result shape:** an empty `orders` array with the surrounding envelope keys still present (for example `returned: 0`), exit 0 — never an error.

## deals

Shell-routed only. Unlike `orders-history`, `deals` supports every positional combination per `--commands`: bare, `<count>`, `<symbol>`, `<symbol> <count>`, `<from> <to>`, `<symbol> <from> <to>`. As with `orders-history`, bare trailing positionals typed at launch (`deals 50`) are not applied — use `--count=`, `--symbol=`, `--from=`, `--to=` instead, and check the echoed header line (e.g. `deals EURUSD 2026-08-01 2026-08-05`) to confirm which filters took effect.

**Empty-result shape:** count-only or bare calls return `{"deals": [], "count": 0}`; a range call adds echo keys, `{"from":"...","to":"...","deals":[],"count":0}` — the `from`/`to` keys appear only when a range was supplied. For a populated entry, confirm the exact field set against a real deal before scripting against it.

## alerts

Shell-routed only. Call it `alerts --account=<n> -e -q`.

**Empty-result shape:** `{"alerts": []}`, exit 0.

Populated payload: `{"alerts": [{"id","symbolName","price","condition","conditionType","quoteType","message"}, ...]}`. `condition` is the human-facing string (`above`/`below`); `conditionType` is the internal enum name (`GreaterOrEqual`/`LessOrEqual`); `quoteType` reports the quote side (`Bid`); `message` is always present, an empty string when none was supplied at creation.

## indicators

Batch-style discovery call, shell-routed: `indicators -e -q`. This is the sole discovery mechanism for valid indicator names. Payload: `{"indicators":[{"title","kind"}, ...],"count":88}`. Of the 88 entries, 87 carry `"kind":"BuiltInIndicators"` and one (`"Bar Sample"`) carries `"kind":"Indicator"`. The `title` string is the exact token to pass as `--indicator=` to other indicator subcommands.

## indicator parameters

Call it `indicator parameters --indicator="<title>" -e -q`, using the exact `title` string from `indicators`. A bare positional indicator name (even quoted) does not work: `indicator parameters "Simple Moving Average" -e` returns exit 1, `Error: 'indicator' is required. Provide it as a positional argument inside the shell, or pass --indicator=<value> when launching the command.`

Success payload: `{"indicator":"<title>","parameters":[{"name","friendlyName","type","groupName","description","defaultValue"}, ...]}`. For Simple Moving Average, the three parameters are `Source` (type `DataSeries`, default `Close`), `Periods` (type `Integer`, default `14`), and `Shift` (type `Integer`, default `0`).

The `name` field is the token to use in a `--ind-params=<name>=<value>,...` override on other indicator commands; resolve it here rather than trusting the CLI's own generic `--help` text, which illustrates the override syntax with a singular `Period=20` example — the real name for Simple Moving Average is plural `Periods`. Always call `indicator parameters --indicator=<title>` first to get the exact name for the indicator you are working with, since names vary per indicator.
