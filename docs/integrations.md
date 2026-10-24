# Package and feed integration

[K2 overview](../README.md) · [Development](development.md)

This reference is for package authors and feed maintainers. K2 uses opkg's
installed state and file ownership to discover launchers and device tools.
Descriptors are JSON data; they do not load arbitrary QML or shell commands.

## Application launch entries

Install `/usr/share/k2/applications/<package-name>.json` with the package:

```json
{
  "name": "Example Reader",
  "argv": ["/usr/bin/example-reader"],
  "instructions": "Open Example Reader to choose your books."
}
```

| Field | Meaning |
| --- | --- |
| `name` | Display name; defaults to the package name |
| `argv` | Executable and literal arguments; omit it for instructions without an Open action |
| `instructions` | Usage text shown in package details and installation results |

The descriptor and the absolute executable in `argv[0]` must belong to the
installed package's opkg file list. The package must have completed setup.
Arguments are passed directly without a shell. Use a launcher that sets up the
app's display and platform environment. The descriptor is limited to 32 KiB,
and `argv` to 64 entries including the executable.

K2 exits and releases its display and power session before running the entry.
Without an entry, it lists installed bin/sbin commands or explains that usage
instructions were not supplied. A launch entry does not declare compatibility
with a device or firmware version.

## Device and gear-menu shortcuts

To add an application to Device, supply a matching
`/usr/share/k2/features/<package-name>.json`:

```json
{
  "schema": 1,
  "id": "example-reader",
  "kind": "application",
  "title": "Example Reader",
  "description": "Read your books.",
  "executable": "/usr/bin/example-reader",
  "platforms": ["kindle", "kobo"],
  "popover": {"icon": "apps", "order": 40}
}
```

| Field | Requirement |
| --- | --- |
| `schema` | `1` |
| `id` | Must match the package name and descriptor filename |
| `kind` | `application`, `remote-access`, or `file-sharing` |
| `title`, `description` | Nonempty text, at most 512 characters each |
| `executable` | Absolute path owned by the package |
| `platforms` | Array containing the applicable families: `kindle` and/or `kobo` |
| `popover` | Optional gear-menu shortcut; omit it to show the feature only on Device |

For `application`, the executable must match the first argument in the launch
entry. Both descriptors and the executable must be owned by the same installed,
configured package. Features disappear after package removal.
Each feature descriptor is limited to 16 KiB.

`popover.icon` names a built-in icon, such as `apps`, `home`, `folder`, or
`terminal`; its default is `settings`. `popover.order` is an integer, default
100. Shortcuts sort by order, then title. The complete accepted icon list and
descriptor checks are in [`discovery.py`](../k2/features/packages/discovery.py).

### Apps that use K2's runtime

A Python/QML app can launch through `k2 --module package.module`. For example,
Home uses `k2 --module k2_home.app`. The selected module runs within K2's device
session and can use its shared UI runtime.

Reading apps can use `k2 --allow-sleep --module package.module` to allow the
original firmware to handle sleep. On Kobo, this requires matching `k2-nickel`
and `qt5-kobo-platform` packages: they coordinate input, display updates, sleep,
and resume with Nickel. Use the normal session for tools that must remain awake.

### Service controls

The `remote-access` kind selects K2's implemented service interface. Supernet's
descriptor uses `id: supernet`, `executable: /usr/bin/supernet`, and
`title: Developer tools`.

The provider supplies a read-only `status-json` command and explicit
`start-usb`, `start-wifi`, `start-both`, and `stop` actions. Additional controls
use `adb-start`, `adb-stop`, `awake-on`, and `awake-off`. Status and actions run
outside the UI thread. K2 coordinates them with package operations so conflicting
changes cannot run together.

`k2-vnc` uses the screen-sharing variant of `remote-access`, with
`/usr/bin/k2-vnc` and `platforms: ["kindle"]`. Its commands are `status-json`,
`start`, and `stop`. The `file-sharing` kind is reserved
for `k2-fileshare`, `/usr/bin/k2-fileshare`, and `platforms: ["kindle"]`.
These kinds require the corresponding service protocol; changing a descriptor
does not add a new type of interface. See the
[remote-access service](../k2/features/remote_access/service.py) and
[file-sharing service](../k2/features/file_sharing/service.py) for their contracts.

## Featured catalogue

App Store reads Featured content from the
[public K2 catalogue](https://raw.githubusercontent.com/katadelos/k2/main/feed/featured/index.json).
The catalogue and artwork live in [`feed/featured/`](../feed/featured/).

Editing the JSON changes the cards without rebuilding K2. The refresh button
reloads both Featured and the package lists; returning to Featured also reloads
its content.

```json
{
  "schema": 1,
  "items": [
    {
      "id": "koreader",
      "width": "full",
      "title": "KOReader",
      "description": "Read EPUBs, PDFs and comics. Adjust fonts, margins and page layout.",
      "image": "images/koreader.png",
      "action": {"label": "View KOReader", "route": "koreader"}
    }
  ]
}
```

### Fields and limits

The top-level object contains exactly `schema: 1` and `items`, with at most
20 items. The JSON download is limited to 128 KiB.

| Item field | Requirement |
| --- | --- |
| `id` | Unique, 1–64 characters; starts with a letter or digit, then letters, digits, `_`, or `-` |
| `width` | `full` or `half` |
| `title` | 1–80 characters |
| `description` | 1–500 characters |
| `headline` | Optional, 1–160 characters |
| `image` | Optional URL or relative path, up to 2048 characters |
| `action` | A `label` of 1–60 characters and exactly one of `route` or `package` |

Items appear in array order. Two consecutive half-width items share a row;
a single half-width item keeps half the row. Unknown fields are rejected.

The only supported route action is `koreader`. A package action such as
`{"label": "View app", "package": "supernet"}` opens package details. If the
package is absent from the catalogue, it opens a search in All instead. Neither
action installs software without confirmation.

Image paths resolve relative to the JSON URL. Artwork and redirects must keep
the same scheme, host, and port. Images may be PNG, JPEG, or WebP, no larger than
2 MiB or 2048 pixels per side. A failed image leaves the text readable. If the
catalogue cannot load, K2 offers **Try again** and **Browse all**.

### Preview locally

From the K2 checkout, serve the feed:

```sh
python3 -m http.server 8096 --bind 127.0.0.1 --directory feed
```

In another terminal, open the simulator with an explicit Featured URL:

```sh
K2_FEATURED_URL=http://127.0.0.1:8096/featured/index.json uv run k2-sim --page apps --watch
```

`K2_FEATURED_URL` accepts an HTTP or HTTPS JSON URL and overrides the
public K2 catalogue. URLs cannot contain credentials. Validation is implemented
in [`featured.py`](../k2/features/packages/featured.py).
