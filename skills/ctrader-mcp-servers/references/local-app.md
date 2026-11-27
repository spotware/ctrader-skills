# Charts and app tools on the Local server

## Charts and the active chart

Chart tools act on the active chart.

- `open_chart` takes `symbolName` and an optional `timeframe`, answers the new chart's `chartId` and symbol with the `timeframe` the call sent, `null` when it sent none, and makes the new chart the active chart. Read the chart's timeframe from `list_charts` or `get_active_chart` after the call.
- `list_charts` lists every open chart with its id, symbol and timeframe and shows which one is active. `focus_chart` and `close_chart` take a `chartId` from that list. Closing the active chart makes another one active.
- `change_chart_symbol` and `change_chart_timeframe` change the active chart and answer without a `chartId`.
- `get_chart_viewport` reads the active chart's scroll position and zoom; `scroll_chart` and `zoom_chart` change them, with the inputs their schemas give.

Before a sequence of chart changes, confirm the active chart with `get_active_chart`. After `load_workspace`, call `list_charts` and take the chart ids from that answer.

## Indicators

The indicator tools act on the active chart. To work on another chart, make it active with `focus_chart` first.

- `listAvailableIndicators` lists the indicators that can be added; its items carry `title` and `isOverlay`.
- `addChartIndicator` takes as `typeName` a `title` from `listAvailableIndicators`, exactly as listed (for example "Simple Moving Average"). If the add is refused, read the list and use the matching title. The add answers the new indicator's `id` and `title`.
- `listChartIndicators` answers the active chart's symbol and timeframe and, under `indicators`, each attached indicator with `id`, `title`, `typeName`, `isRunning`, `lineOutputCount` and `barOutputCount`. Right after `addChartIndicator`, the new indicator can list `isRunning` `false` while `getIndicatorValues` answers an empty `values` list with `totalBarCount` 0. Before reading the values of an indicator just added, read `listChartIndicators`: when its item lists `isRunning` `false`, read `listChartIndicators` once more a second later, and when the item still lists `false`, tell the user that the indicator has not started yet, report no values, and read again when the user asks. When the item lists `isRunning` `true` and `getIndicatorValues` answers an empty `values` list, read the values once more a second later; when that answer is empty too, report that the tool returned no values.
- `getIndicatorValues` takes the `id` as `indicatorId`, an `outputIndex` below the output count and a `count` (default and cap in its description); without `outputIndex` the first output is read. It answers under `values` the last `count` values of that output, oldest first, so the last one is that of the bar still forming, with `totalBarCount` and no times. No Local tool names the line behind an `outputIndex`: when the user asks for one line of an indicator with several outputs, such as a band of Bollinger Bands or the signal line of a MACD, tell the user that the tools do not identify that line, and do not present an index as a named line.
- `update_indicator_parameters` takes the `indicatorId` and `parameters`, an object whose keys are the indicator's parameter names. No Local tool lists the parameter names or the current values of an indicator: ask the user for each name as the indicator's settings in cTrader show it, and send it exactly as shown, letter case included. Send one parameter per call: a name the indicator does not have is refused with `<name>: unknown parameter` only when it is the only key, and a call with a known and an unknown key answers `updated`. On that refusal, show the user the text and ask for the name again. A value of the wrong form is refused with `The input string '<value>' was not in a correct format.`, and a setting chosen from a list can refuse the name of a choice this way and take a number in its place; no Local tool lists which number stands for which choice, so when the user cannot give the number, tell the user that this setting is changed in the indicator's settings in cTrader. No tool reads the parameters back, so report the answer of the call and tell the user that the tools cannot read the change back.
- `removeChartIndicator` takes the `indicatorId`.

## Drawings

`add_chart_object` draws on the active chart. Take the drawing type and the anchors it needs from the `add_chart_object` description, which lists every type. Give every anchor of a two- or three-point type both a price and a time, each time in ISO 8601 UTC with `Z`.

`add_chart_object` also takes `color` (hex), `text`, `fill` and `extend` where the description allows them, and `side` for `risk_reward`; a `risk_reward` call without `side` draws a buy. It answers the new object's `objectId`. A call that lacks an anchor its type requires is refused with `Missing required parameters for` the type and the missing name, for example `Missing required parameters for risk_reward: price3`, and draws nothing.

`get_chart_objects` lists `objectId`, type and name only, so it confirms that an object exists, not where it sits: keep the anchors that were sent, and match objects by `objectId`, since the listed type can differ from the `object_type` sent.

`update_chart_object` names the object by `objectName`, `delete_chart_object` by `objectId`; for an object added through `add_chart_object`, both take the `objectId` of the add answer.

`update_chart_object` changes only the fields it receives: the first two anchors, `color`, `fill`, `text`, `lineThickness` and `lineStyle` (values in the schema). It has no third anchor; to move a third anchor, delete the object and add it again with the user's agreement. `get_chart_objects` returns no color or text, so confirm such an update by the answer's `status`.

`clear_chart_objects` deletes every drawing on the active chart.

## Chart templates

`save_chart_template` saves the active chart's settings as a template under `name`. `list_chart_templates` lists the custom templates; `apply_chart_template` applies one to the active chart and `delete_chart_template` deletes one, both by the `templateId` that list gives, the name the template was saved under.

`apply_chart_template` replaces the indicators attached to the active chart with those saved in the template: a template saved without indicators removes every indicator of the chart, and one saved with an indicator leaves that indicator only. Before applying a template, read `get_active_chart` and `listChartIndicators`, and confirm with the user, naming the chart and the indicators it loses.

## Workspaces

The description of `save_workspace` says it creates a new workspace or overwrites an existing one: before saving under a name `list_workspaces` already lists, confirm with the user.

The description of `load_workspace` says it restores the saved layout and charts: before a load, offer to save the current layout under a new name.

After `delete_workspace`, read `list_workspaces`; if the name is still listed, tell the user.

## Watchlists

Watchlists are named, and several can share a name: `create_watchlist` and `rename_watchlist` each accept a name already in use. A `get_watchlists` item carries `name`, `key`, `isEditable` and `symbols`.

`add_symbol_to_watchlist` and `remove_symbol_from_watchlist` take `watchlistName` and `symbolName`; `rename_watchlist` takes `name` and `newName`; `delete_watchlist` takes `name`. A call by a name that occurs more than once acts on the first list of that name in the `get_watchlists` answer. Read `get_watchlists` first; before a call by a name that occurs more than once, tell the user which list that is, by its place in the answer, its `isEditable` and its symbols. Before a `create_watchlist` or a `rename_watchlist` that would give a list a name the `get_watchlists` answer already shows, tell the user that the list will then share that name with each list that already has it. Check a symbol with `get_symbols` before adding it.

Watchlist changes sent at the same moment, or one right after another, do not all take effect, although each answers its status. Send one watchlist change at a time and read `get_watchlists` after it; send the next change when the read shows this one. When the read does not show the change, read again a second later, and send the change again only when that read does not show it either.

## Price alerts

`create_price_alert` takes `symbolName`, `price`, `condition` (`above` or `below`), `quoteType` (`bid` by default, or `ask`) and an optional `message`, and answers the alert's `id`. Check the current quote first; when the condition is already met, tell the user instead of creating the alert.

`get_price_alerts` items carry `id`, `symbolName`, `price`, `conditionType`, `quoteType` and `message`; an `above` alert on the default quote reads back `GreaterOrEqual` and `Bid`.

`delete_price_alert` takes the integer `alertId`.

## cBots

`listPlugins` answers a list whose items carry `id`, `name`, `typeTitle`, `isEnabled`, `isRunning` and `isCrashed`; pass the `id` (a GUID) as `pluginId` to `startPlugin` and `stopPlugin`.

Start a cBot only when the user asks for that start. The Local tools do not show which account a started cBot trades on. The cTrader Help Centre says that a cBot instance runs until it is stopped, a local instance only while the cTrader Windows or Mac app stays open, and that stopping an instance does not close the positions it opened. Before `startPlugin`, read whether the account is demo or live as step 1 of the rules for order-changing calls in `SKILL.md` describes, and read `listPlugins` for the cBot's item. Show the user the cBot by `name` and `typeTitle`, say whether the account the app is logged in to is demo or live, that the Local tools do not show which account the cBot trades on, and that the cBot runs until it is stopped or, as a local instance, until the app closes, and get a yes. Before `stopPlugin`, tell the user that stopping the cBot does not close the positions it opened. After either call, read `listPlugins` again and report `isRunning` and `isCrashed` as it shows them. After `stopPlugin`, also read `get_positions` and report the positions still open.

## App sections, layout and panels

The layout and panel tools name their parameter differently: `set_layout_mode` takes `mode`, `set_asp_tab` takes `tab`, `set_trade_watch_tab` takes `tabName`, `set_market_watch_panel` takes `panel`, and `switch_app` takes `app`; the values are in each schema. `get_layout_mode`, `get_asp_tab`, `get_trade_watch_tab`, `get_market_watch_panel` and `get_current_app` read the current setting.

When `get_trade_watch_tab` answers an empty value, the read names no tab. Read `get_layout_mode`: under `asp` or `chart_only` the layout shows no TradeWatch panel, so tell the user and offer `set_layout_mode` with `all` or `trade_watch`, sent only with the user's agreement, before a tab is set; under `all` or `trade_watch`, set the tab the user asked for with `set_trade_watch_tab` and read `get_trade_watch_tab` again.

## Notifications

`show_notification` takes `caption`, `description` and `type` (values in the schema).

## News

`get_news` takes `feed` (`general` or `crypto`) and `limit`; items carry `id`, `title`, `summary` and `publishedAt`. Sort by `publishedAt` before presenting.

## Operations that delete or overwrite

Read the state before each call below. The calls of the first two rows change orders and positions: show and confirm them as the rules for order-changing calls in `SKILL.md` describe. Before every other call of the table, confirm with the user, naming the items it acts on.

| Call | Read first |
| --- | --- |
| `close_position`, `close_position_partial`, `close_all_positions` | `get_positions` |
| `cancel_order`, `cancel_all_pending_orders` | `get_pending_orders` |
| `close_chart` | `list_charts` |
| `delete_chart_object`, `clear_chart_objects` | `get_chart_objects` |
| `removeChartIndicator` | `listChartIndicators` |
| `apply_chart_template` | `get_active_chart`, `listChartIndicators` |
| `delete_chart_template`, and `save_chart_template` under a name in use | `list_chart_templates` |
| `save_workspace` under a name in use, `load_workspace`, `delete_workspace` | `list_workspaces` |
| `delete_watchlist`, which acts on the first list of its name | `get_watchlists` |
| `delete_price_alert` | `get_price_alerts` |
| `stopPlugin` | `listPlugins` |

## Recipe: draw a trade's risk and reward

1. Read the levels of the trade. For an open position, take `entryPrice`, `stopLossPrice` and `takeProfitPrice` from its item in `get_positions`; for a pending order, take `targetPrice` and the same two protection keys from its item in `get_pending_orders`. Take the side from `tradeSide`. The drawing needs both levels: when `stopLossPrice` or `takeProfitPrice` reads `null`, ask the user for the level to draw for that leg, and say that it is a level of the drawing and sets nothing on the trade; without it, make no drawing.
2. Read `get_active_chart`. When the active chart shows another symbol, open a chart of the trade's symbol with `open_chart`.
3. Draw the trade with `add_chart_object` of type `risk_reward`: `side` from `tradeSide` (`buy` or `sell`) on every call, since a call without it draws a buy; `price1` the entry, `price2` the stop loss, `price3` the take profit; `time1` where the block starts, the position's `openTime` for an open position, and for a pending order the current time, `utcTime` of `get_server_time`, unless the user names another start; and, optionally, `time2` where it ends. `openTime` and `utcTime` read in ISO 8601 UTC with `Z`; send every time in that form, converting a start the user names in another zone first.
4. Keep the `objectId` of the answer: `get_chart_objects` confirms that the object exists, not where it sits.
5. Remove the drawing only with the user's agreement, with `delete_chart_object` and that `objectId`.
