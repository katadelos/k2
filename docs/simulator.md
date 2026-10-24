# Simulator reference

[Development setup](development.md#run-on-a-computer) · [K2 overview](../README.md)

Run commands from the K2 checkout after `uv sync`. The simulator uses the same
feature models and QML as the device app, with simulated backends.

## Launch options

```sh
uv run k2-sim --device pw5 --page apps --watch
uv run k2-sim --device elipsa --page koreader --scenario koreader-installed
```

| Option | Values and behaviour |
| --- | --- |
| `--device` | `pw5` (default, 1236 × 1648) or `elipsa` (1404 × 1872) |
| `--page` | `home` (default), `apps`, `device`, `storage`, `files`, `about`, `activity`, `koreader`, `koreader-customise` |
| `--scenario` | A scenario from the table below; default `normal` |
| `--scale` | Window scale from 0.1 to 2; desktop mode fits the screen, headless mode defaults to 1 |
| `--watch` | Reload QML changes while keeping application state; Python edits require a restart |
| `--headless` | Use an offscreen window with software rendering |
| `--screenshot PATH` | Save a frame; with `--watch`, update it after edits and state changes |

The `storage` page is available for direct preview but has no link in the
current device interface. A simulator profile represents a screen layout and
sample device data; it does not validate firmware compatibility.

## Scenarios

| Scenario | Use it to explore |
| --- | --- |
| `normal` | A sample catalogue with installed packages and updates |
| `empty` | An empty package catalogue |
| `offline` | Startup without a feed refresh and failures on manual package operations |
| `loading` | The splash screen, held open for layout work |
| `supernet` | Developer tools with a simulated SSH key |
| `supernet-setup` | Developer tools before a public key is added |
| `koreader-installed` | An existing KOReader installation and customisations |
| `koreader-conflict` | Two KOReader installations to choose between |
| `koreader-offline` | An existing KOReader installation with failed release checks |

## Headless use

Save a frame and exit:

```sh
uv run k2-sim --headless --device pw5 --page apps --screenshot /tmp/k2.png
```

For an interactive process that accepts commands:

```sh
uv run k2-sim --headless --watch
```

Send one JSON object per line on stdin. Replies use stdout; Qt diagnostics use
stderr. An optional `id` is echoed in the reply, whose other field is `result`
or `error`.

For example, send these commands to inspect a package and capture its page:

```json
{"id":1,"command":"navigate","page":"apps"}
{"id":2,"command":"search","text":"dropbear"}
{"id":3,"command":"select","name":"dropbear"}
{"id":4,"command":"state"}
{"id":5,"command":"screenshot","path":"/tmp/k2.png"}
```

### Interface and package commands

| Command | Fields |
| --- | --- |
| `state`, `back`, `reload`, `controls`, `quit` | None |
| `navigate` | `page`: route name |
| `tap` | `x`, `y`: window pixel coordinates |
| `screenshot` | `path`: output filename |
| `tab` | `value`: `Featured`, `All`, `Installed`, or `Updates` |
| `search` | `text`: search string |
| `select` | `name`: package name |
| `request` | `action`: `install`, `upgrade`, `remove`, or `update`; `name`: package name, omitted for a feed refresh or Update all |
| `confirm`, `cancel`, `retry` | None |
| `featured-refresh` | None |
| `featured-open` | `name`: card ID |
| `brightness` | `value`: integer from 0 to the maximum in `state.brightness` |
| `wifi` | `enabled`: boolean |
| `feature` | `name`: installed feature ID, such as `supernet` |
| `feature-transport` | `value`: `usb`, `wifi`, or `both` |
| `feature-action` | `action`: service action, such as `start` or `stop` |
| `feature-refresh` | None |

Wait until startup has finished (`loading` and `busy` are false), then select
the package before requesting a change. Requests made while package work is
busy are ignored. `request` prepares a plan
asynchronously: query `state` until `pending.ready` is true before sending
`confirm`. If the plan has an error or no changes, it cannot be confirmed.
After confirmation, wait until `busy` is false and inspect the result.
For `update`, the feed refresh starts directly without confirmation.

### KOReader commands

| Command | Fields |
| --- | --- |
| `reader-refresh`, `reader-release`, `reader-plugins` | None |
| `reader-select` | `path`: installation path |
| `reader-request` | `action`: `install`, `uninstall`, `plugin-install`, or `plugin-remove`; `value`: archive source or plugin ID for plugin actions |
| `reader-customise` | `online`: boolean, true to check upstream releases |
| `reader-customisation` | `name`: catalogue ID |
| `reader-customise-tab` | `value`: `All`, `Installed`, or `Updates` |
| `reader-customise-action` | `action`: `install`, `remove`, `enable`, or `disable` |
| `reader-preview` | None |

KOReader changes use the same `pending.ready`, `confirm`, and `cancel` flow.
Wait for `readerBusy` to become false before reading their outcome.

The command definitions are in [`console.py`](../k2/simulator/console.py);
[`state.py`](../k2/simulator/state.py) defines the returned state. The shared
transport and preview commands are in [`ui/console.py`](../k2/ui/console.py).
