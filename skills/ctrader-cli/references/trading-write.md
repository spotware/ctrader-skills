# Trading write reference

This reference covers every state-changing verb: `order place-market`, `order place-limit`, `order place-stop`, `order place-stop-limit`, `order modify`, `order cancel`, `position close`, `position close-partial`, `position modify`, `alert create`, and `alert delete`.
The confirmation mechanism, the volume semantics, and the three-state protection rule apply across this whole set, and each works differently from what habit built on the read-only verbs would predict.

## The authorization gate

On every command in the mutating set, `-q` is not a routine menu-skip convenience the way it is for a read. It **is** the confirmation. Passing it answers the confirmation prompt automatically and the mutation executes immediately, with no further chance to abort.

Because `-q` is also the flag you reach for reflexively on shell-routed reads to keep stdout minimal, the single most important discipline in this reference is: never let it travel from a read command to a write command out of habit. Add `-q` to a mutating command only when both of the following are true:

- The user has explicitly authorized this specific action. Not authorization to trade in general, and not authorization given earlier in the conversation for a different order or a different symbol; the specific action you are about to submit.
- You have confirmed the target account is a demo account by reading the account's own record from `accounts` and checking that it reports `"Live": false`. Do this check freshly before the mutation, not from memory of an earlier read in the same session.

Never run a mutating command to discover how it behaves. If you need to understand a flag's shape or a response's fields, read `--commands`, this reference, or a neighboring read-only command instead of a live trial mutation.

## The confirmation mechanism

Only `-q` reliably confirms a mutating command at a direct, flag-style launch invocation (the shape you use: explicit flags, `--account=`, stdin redirected from `/dev/null`). The other forms that the CLI's own refusal message names do not work the way that message implies, in this invocation shape:

- `--yes` and `-y` both produce the identical refusal text, followed by `Cancelled.`, at exit 1, exactly as if no confirmation flag had been passed at all — the same refusal on `order place-limit`, `order modify`, and `order cancel` alike. The refusal reads:

```text
Refused: confirmation required. Append `yes` as a trailing positional inside the shell, or pass --yes/-q at launch time.
Cancelled.
```

- A bare trailing `yes` positional, mixed into an otherwise flag-style command line, does not confirm and does not cleanly refuse either. It ends the process with an unhandled `ConsoleInvalidUsageException` stack trace on stderr (empty stdout, exit 1). The trailing-`yes`-positional convention belongs to typing at the interactive shell's own `>` prompt; it is not something you can append to a launch line built of `--flag=value` arguments.
- The `all` keyword (for bulk operations such as `alert delete --alert=all` or a bare `all` positional) is shell-prompt syntax in the same sense. At a direct launch invocation, `--alert=all` is rejected with `Error: Alert id must be a number, got 'all'.`, and a bare `all` positional is rejected with `Error: 'alert' is required. Provide it as a positional argument inside the shell, or pass --alert=<value> when launching the command.` Note that `--help` also documents a dedicated `--all` launch flag (`target every applicable entity`, covering `stop`, `order cancel`, `position close`, and `alert delete`); prefer explicit-ID deletion or cancellation until you have verified `--all` yourself.

So: `-q` at launch is the confirmation form that applies to the invocations you compose. Of the other forms, only the bare trailing `yes` positional ends the process with the usage-trace exception; `--yes` and `-y` fail gracefully with the refusal text plus `Cancelled.`, and the `all` spellings (`--alert=all` and a bare `all` positional) fail gracefully with a one-line `Error:`. The trailing `yes` and bare `all` keywords are the interactive shell's own `>`-prompt syntax; `--yes`/`-y` are launch options per the CLI's own `--help` (`--yes, -y  skip confirmations`) that do not confirm in this invocation shape — never rely on them.

Expect the same `-q`-confirms / `--yes`-and-`-y`-refuse pattern on every verb in the mutating set: `--commands` shows each one exposing the identical confirmation convention, listing trailing-`yes` positional forms alongside its argument shapes. Re-confirm on first use of a verb where precision matters.

## The four-stage guarded sequence

Drive every mutation through this four-stage sequence, in order, every time:

1. **Pre-flight read.** Before submitting anything, read the instrument's own tradeable limits with `symbol --symbol=<name>` (returns `lotSize`, `minVolume`, `maxVolume`, `volumeStep`, `digits`, `pipSize`, current `bid`/`ask`), and read the current state of the entity you are about to mutate (`orders`, `positions`, or `alerts`) so you know its prior values.
2. **Act.** Submit the mutating command with `-q`, after the authorization gate above has been satisfied.
3. **Read back.** Immediately re-read the affected entity with `orders`, `positions`, `orders-history`, or `alerts` as appropriate.
4. **Verify.** Compare the read-back against what you expected the mutation to have produced (the new price, the new stop, the removed order, the deleted alert) before you report success to the user. A command's own confirmation JSON is not a substitute for this independent read-back.

## Volume is expressed in units by default

`--volume` is interpreted in units unless you say otherwise. On EURUSD (`lotSize=100000`, `minVolume=1000`, `volumeStep=1000`), these three invocations of `order place-limit` resolve to the identical stored order:

- `--volume=1000` with no `--volume-type` flag at all
- `--volume=1000 --volume-type=units`
- `--volume=0.01 --volume-type=lots`

Each reads back as `volume: 1000, volumeLots: 0.01`. The confirmation text printed at submission time for the untyped case reads `BUY 1000 units (= 0.01 lots)`, spelling out the resolution in the same call.

Always read the instrument's limits first with `symbol --symbol=<name>` before choosing a volume, since `minVolume`, `maxVolume`, and `volumeStep` are per-instrument and a value outside them is what you are validating against, not a fixed constant.

## Stop loss and take profit: the three-state rule

`order modify` treats `--sl` and `--tp` as three-state flags; expect the same from `position modify` and confirm on first use:

- Passing a value replaces the field with that value.
- Passing `0` removes the field (read back as `null`).
- Omitting the flag entirely preserves whatever value is already set; it does not clear it.

Modifying with `--sl=0` prints confirmation text `SL=remove` and reads back as `stopLoss: null`, while a `takeProfit` omitted from the same call comes back unchanged. A call with `--sl=1.0250` (a plain value) replaces the field. Supply prices as absolute values, not as pip offsets.

## Wrong-side rejection

A stop loss or take profit on the wrong side of the reference price is rejected client-side, before the request ever reaches the server, so no state changes. The exact shape, for a buy limit order at 1.0378 modified with `--sl=1.0500`:

```text
Warning: SL=1.0500 is on the profit side of reference price 1.0378 for buy (server may reject).
Error: SL/TP is on the wrong side of the reference price. The server would silently drop the protection. Modification rejected.
```

Exit code 1, two lines of plain text: a `Warning:` line naming the specific side violation, then an `Error:` line stating the rejection. The order's protection is left exactly as it was; treat this rejection as a safe no-op, and still confirm with a read-back rather than an assumption.

## Flag names that matter

Use the exact flag names below. An unrecognized near-miss is treated as if the value were never supplied, so the result is a missing-value message naming the option the command still needs rather than a message about the name you typed:

- `--order=<id>` identifies the target for `order modify` and `order cancel`. `--order-id=<id>` is not recognized: it produces `Error: 'order' is required. Provide it as a positional argument inside the shell, or pass --order=<value> when launching the command.`, which reads like a missing value rather than a wrong flag name.
- `--position=<id>` identifies the target for `position close`, `position close-partial`, and `position modify`, following the same naming convention as `--order`.
- `--alert=<id>` identifies the target for `alert delete`.
- `--symbol=<name>` must be passed as an explicit named flag everywhere a symbol is required, including `order place-*` and `alert create`. A bare positional symbol is not consumed at a direct launch invocation; it reroutes into the interactive shell instead.

## Response keys per command

Each mutating command returns its own identifier key and its own `status` string; read the key that matches the command you actually called rather than assuming a single conceptual identifier name across the set:

| Command | Identifier key | `status` value |
| --- | --- | --- |
| `order place-limit` | `orderId` | `"placed"` |
| `order modify` | `orderId` | `"modified"` |
| `alert create` | `id` | `"created"` |
| `alert delete` | `alertId` | `"deleted"` |

The `id` versus `alertId` naming difference between the two alert commands is the CLI's convention to read from, not an inconsistency to work around. For the placement verbs beyond the table, expect `{"orderId": <int>, "status": "placed"}` when the submission rests as a pending order and `{"positionId": <int>, "status": "opened"}` when it fills into a position immediately — the normal outcome for `place-market` — and read whichever of the two keys is present rather than assuming `orderId`. For `order cancel`, `position close`, `position close-partial`, and `position modify`, expect `orderId` (cancel) or `positionId` (the position commands, with `close-partial` also carrying `volume` and `volumeLots` for the partial amount); confirm the exact key on first use before relying on it in a script.

## Alerts: create and delete

`alert create` requires the flag form at launch: `--symbol=`, `--price=`, and `--condition=` (accepted values `above` and `below`); bare positionals are not consumed at a direct launch invocation. The confirmation text echoes the alert in plain language, for example `Create alert: EURUSD below 0.5.`, before the JSON payload.

A populated `alerts` read returns an object keyed `alerts`, each entry carrying `id`, `symbolName`, `price`, `condition` (the human-facing string, `above`/`below`), `conditionType` (the internal enum name, `GreaterOrEqual`/`LessOrEqual`), `quoteType`, and `message` (an empty string when none was supplied at creation). An account with no alerts returns `{"alerts": []}`.

`alert delete` takes `--alert=<id>` and returns the `alertId`/`"deleted"` pair described above. Delete by explicit numeric ID; `--alert=all` and a bare `all` positional are both rejected at launch (see the confirmation section above); `--help` documents a separate `--all` launch flag for bulk deletion — verify it before relying on it.

Follow the four-stage sequence for alerts exactly as for orders: read `alerts` before creating (to know the starting state), create with `-q` after authorization, read `alerts` back to confirm the new entry's fields match what you intended, and after a delete, read `alerts` again to confirm the entry is gone rather than trusting the delete command's own JSON alone.
