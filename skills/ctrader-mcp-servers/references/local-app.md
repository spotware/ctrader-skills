# Charts and app tools on the Local server

## Charts and the active chart

Chart tools act on the active chart.

- `open_chart` takes `symbolName` and an optional `timeframe`, answers the new chart's `chartId`, symbol and timeframe, and makes it the active chart.
- `list_charts` lists every open chart with its id, symbol and timeframe and shows which one is active. `focus_chart` and `close_chart` take a `chartId` from that list. Closing the active chart makes another one active.
- `change_chart_symbol` and `change_chart_timeframe` change the active chart and answer without a `chartId`.
- `get_chart_viewport` reads the active chart's scroll position and zoom; `scroll_chart` and `zoom_chart` change them, with the inputs their schemas give.

Before a sequence of chart changes, confirm the active chart with `get_active_chart`. After `load_workspace`, call `list_charts` and take the chart ids from that answer.

## Indicators

The indicator tools act on the active chart. To work on another chart, make it active with `focus_chart` first.

- `listAvailableIndicators` lists the indicators that can be added; its items carry `title` and `isOverlay`.
- `addChartIndicator` takes as `typeName` a `title` from `listAvailableIndicators`, exactly as listed (for example "Simple Moving Average"). If the add is refused, read the list and use the matching title. The add answers the new indicator's `id` and `title`.
- `listChartIndicators` answers the active chart's symbol and timeframe and, under `indicators`, each attached indicator with `id`, `title`, `typeName`, `isRunning`, `lineOutputCount` and `barOutputCount`.
- `getIndicatorValues` takes the `id` as `indicatorId` and an `outputIndex` below the output count; without `outputIndex` the first output is read. It answers the most recent values under `values`, with `totalBarCount`.
- `update_indicator_parameters` takes the `indicatorId` and `parameters`, an object whose keys are the indicator's parameter names; `removeChartIndicator` takes the `indicatorId`.

## Drawings

`add_chart_object` draws on the active chart. Take the drawing type and the anchors it needs from the `add_chart_object` description, which lists every type. Give every anchor of a two- or three-point type both a price and a time, each time in ISO 8601 UTC with `Z`.

`add_chart_object` also takes `color` (hex), `text`, `fill` and `extend` where the description allows them, and `side` for `risk_reward`. It answers the new object's `objectId`.

`get_chart_objects` lists `objectId`, type and name only, so it confirms that an object exists, not where it sits: keep the anchors that were sent, and match objects by `objectId`, since the listed type can differ from the `object_type` sent.

`update_chart_object` names the object by `objectName`, `delete_chart_object` by `objectId`; for an object added through `add_chart_object`, both take the `objectId` of the add answer.

`update_chart_object` changes only the fields it receives: the first two anchors, `color`, `fill`, `text`, `lineThickness` and `lineStyle` (values in the schema). It has no third anchor; to move a third anchor, delete the object and add it again with the user's agreement. `get_chart_objects` returns no color or text, so confirm such an update by the answer's `status`.

`clear_chart_objects` deletes every drawing on the active chart.

## Chart templates

`save_chart_template` saves the active chart's settings as a template under `name`. `list_chart_templates` lists the custom templates; `apply_chart_template` applies one to the active chart and `delete_chart_template` deletes one, both by the `templateId` that list gives.

## Workspaces

The description of `save_workspace` says it creates a new workspace or overwrites an existing one: before saving under a name `list_workspaces` already lists, confirm with the user.

The description of `load_workspace` says it restores the saved layout and charts: before a load, offer to save the current layout under a new name.

After `delete_workspace`, read `list_workspaces`; if the name is still listed, tell the user.

## Watchlists

Watchlists are named; several can share a name, and `create_watchlist` accepts a name already in use. Read `get_watchlists` first; when a name occurs twice, tell the user before changing either.

`add_symbol_to_watchlist` and `remove_symbol_from_watchlist` take `watchlistName` and `symbolName`; `rename_watchlist` takes `name` and `newName`; `delete_watchlist` takes `name`. Check a symbol with `get_symbols` before adding it, and read the list again after adding or removing.

## Price alerts

`create_price_alert` takes `symbolName`, `price`, `condition` (`above` or `below`), `quoteType` (`bid` by default, or `ask`) and an optional `message`, and answers the alert's `id`. Check the current quote first; when the condition is already met, tell the user instead of creating the alert.

`get_price_alerts` items carry `id`, `symbolName`, `price`, `conditionType`, `quoteType` and `message`; an `above` alert on the default quote reads back `GreaterOrEqual` and `Bid`.

`delete_price_alert` takes the integer `alertId`.

## cBots

`listPlugins` answers a list whose items carry `id`, `name`, `typeTitle`, `isEnabled`, `isRunning` and `isCrashed`; pass the `id` (a GUID) as `pluginId` to `startPlugin` and `stopPlugin`.

A running cBot acts on the account the app is logged in to until it stops, so start one only when the user asks for that start. Before `startPlugin`, read whether the account is demo or live as step 1 of the rules for order-changing calls in `SKILL.md` describes, and read `listPlugins` for the cBot's item. Show the user the cBot by `name` and `typeTitle`, say whether the account is demo or live, and get a yes. After the call, read `listPlugins` again and report `isRunning` and `isCrashed` as it shows them.

## App sections, layout and panels

The layout and panel tools name their parameter differently: `set_layout_mode` takes `mode`, `set_asp_tab` takes `tab`, `set_trade_watch_tab` takes `tabName`, `set_market_watch_panel` takes `panel`, and `switch_app` takes `app`; the values are in each schema. `get_layout_mode`, `get_asp_tab`, `get_trade_watch_tab`, `get_market_watch_panel` and `get_current_app` read the current setting.

When `get_trade_watch_tab` answers an empty value, read `get_layout_mode` before setting a tab.

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
| `delete_chart_template`, and `save_chart_template` under a name in use | `list_chart_templates` |
| `save_workspace` under a name in use, `load_workspace`, `delete_workspace` | `list_workspaces` |
| `delete_watchlist` | `get_watchlists` |
| `delete_price_alert` | `get_price_alerts` |
| `stopPlugin` | `listPlugins` |

## Recipe: draw a trade's risk and reward

1. Read the levels of the trade. For an open position, take `entryPrice`, `stopLossPrice` and `takeProfitPrice` from its item in `get_positions`; for a pending order, take `targetPrice` and the same two protection keys from its item in `get_pending_orders`. Take the side from `tradeSide`.
2. Read `get_active_chart`. When the active chart shows another symbol, open a chart of the trade's symbol with `open_chart`.
3. Draw the trade with `add_chart_object` of type `risk_reward`: `side` (`buy` or `sell`), `price1` the entry, `price2` the stop loss, `price3` the take profit, `time1` where the block starts and, optionally, `time2` where it ends, with times in ISO 8601 UTC with `Z`.
4. Keep the `objectId` of the answer: `get_chart_objects` confirms that the object exists, not where it sits.
5. Remove the drawing only with the user's agreement, with `delete_chart_object` and that `objectId`.
