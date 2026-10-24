# Development

[K2 overview](../README.md) · [Simulator reference](simulator.md) · [Integrations](integrations.md)

K2 uses Python 3.14 or later, PyQt5, and Qt Quick. Most interface and application
work can be done in the desktop simulator. Native integration and hardware
behaviour need a matching device build and device checks.

## Run on a computer

Install [uv](https://docs.astral.sh/uv/getting-started/installation/).
The dependency sources and versions are recorded in `pyproject.toml` and
`uv.lock`. The simulator needs the Python bindings but does not load the native
HAL library.

From the K2 checkout:

```sh
uv sync
uv run pre-commit install
uv run k2-sim --device pw5 --watch
```

Use `--device elipsa` for the Kobo Elipsa 2E layout. The simulator uses sample
package data and temporary files. It does not invoke opkg or change files on a
reader. Featured content and some previews can still make network requests.

With `--watch`, QML edits reload while retaining application state. If a QML
file has a syntax error, the last working view remains visible and the error
is written to stderr. Restart the process after changing Python code.

The [simulator reference](simulator.md) covers scenarios, direct page selection,
headless operation, and commands for scripts.

## Check a change

Run the same checks used by GitHub Actions:

```sh
uv run pre-commit run --all-files
```

The hooks fail on lint, formatting, complexity, type, security, and import
boundary violations. Python checks cover the whole package when Python or their
configuration changes. Other hooks check file syntax, merge markers, accidental
private keys, whitespace, and script metadata.

To format Python or apply safe lint fixes, run:

```sh
uv run ruff format k2
uv run ruff check --fix k2
```

Review the changes before committing. Ruff limits function complexity to 15.
Mypy checks function bodies throughout the package and requires annotations at
the core, composition, device, and worker boundaries. Import Linter checks the
dependency rules below. Automated checks support code review; they do not
establish that hardware behaviour is correct.

For a UI change, exercise the affected flow in the simulator. Check device
behaviour on hardware when the change involves display updates, input, sleep,
USB, or the original firmware. Keep checks proportional to the change.

## Code structure

| Directory | Responsibility |
| --- | --- |
| `k2/app/` | Compose the production backends and features; expose the application shell |
| `k2/core/` | Shared data types and backend protocols without Qt or device dependencies |
| `k2/features/` | Packages, KOReader, files, file sharing, remote access, and device controls; each feature owns its services, view model, routes, and QML |
| `k2/ui/` | Navigation, confirmations, shared operations, worker lifetimes, runtime, and reusable QML components |
| `k2/adapters/` | Device hardware, opkg, launching, and display/power sessions |
| `k2/simulator/` | Simulator composition, sample backends, scenarios, and headless commands |
| `bin/`, `integration/` | Device launchers and firmware integration assets |
| `feed/featured/` | Featured catalogue content and artwork |

Start at [`app/bootstrap.py`](../k2/app/bootstrap.py) to see how features are
connected. The simulator has its own
[`bootstrap.py`](../k2/simulator/bootstrap.py), which supplies simulated backends
to the same feature models and QML.

Keep dependencies directed toward shared contracts. Core code cannot import
Qt, features, adapters, or the app. Adapters cannot import UI or feature
implementations. Shared UI infrastructure cannot import features or device
adapters. Features cannot depend on application composition or the simulator.
The enforced rules are in [`pyproject.toml`](../pyproject.toml).

A feature route declares its title, QML file, persistent view model, and optional
enter/leave callbacks. View models submit confirmation callbacks and request
shared operation resources; QML binds to capabilities such as `canChange` and
`canLaunch`. View models survive navigation and QML reloads.

### Device sessions and shared apps

[`bin/k2`](../bin/k2) sets the device environment.
[`adapters/session.py`](../k2/adapters/session.py) supervises the interface and
releases display, input, and power resources before handing control to another
app. Kindle uses X11; Kobo uses the Nickel bridge. Both retain the original
firmware services.

Shared QML components are available as `import k2.ui.components 1.0`.
See [application integration](integrations.md#application-launch-entries)
for launch descriptors and the `--module` entry point.

## Credits

K2 uses Python, PyQt, Qt, [eboard](https://github.com/katadelos/eboard),
and [ereader-hal](https://github.com/katadelos/ereader-hal). Each retains its own
license.

The Nickel bridge uses the
[MainNavButton ABI](https://github.com/pgaskin/NickelMenu/blob/master/src/nickelmenu.cc)
and [NickelTC](https://github.com/pgaskin/NickelTC). The Kindle shortcut follows
the [Scriptlet specification](https://kindlemodding.org/kindle-dev/scriptlets.html).

The interface uses ktrmnl2's KTRMNL DIN Mittelschrift for headings and controls,
and Neue Haas Display Roman for body text. Bundled fonts retain their respective
licenses. The Featured KOReader icon is unmodified; its
[attribution and license](../feed/featured/images/koreader.LICENSE.txt) accompany
the image.
