# Getting started

[K2 overview](../README.md) · [Using K2](user-guide.md)

## Before you install

On touch Kindles, you need a jailbreak with Scriptlet support to run the installer
from the library. Kindle 4 uses an existing SDK setup and KUAL or a root shell.
On Kobo, you need a configured package manager and a root
shell that can run `opkg`.

The Kindle installer needs an internet connection. An existing package setup
must supply K2 and its dependencies, including opkg **0.7.0-r14 or later**.

### Device profiles

Use the profile selected by the bootstrap. It depends on the firmware as well
as the hardware; packages from different profiles are not interchangeable.

| Device profile | Target |
| --- | --- |
| `kindle5` | Kindle 4 and other ARM soft-float Kindle firmware with a 2.6 kernel |
| `kindlepw2` | Kindle firmware with the ARM soft-float ABI and a kernel newer than 2.6 |
| `kindlehf` | Kindle firmware with the ARM hard-float ABI |
| `kobo` | Older Kobo firmware and kernel, including Kobo Touch |
| `kobov4` | Newer Kobo firmware and kernel, including Forma and Elipsa 2E |

These are build targets, not a guarantee for every firmware release on each
model. Kobo's launch integration targets firmware 4.x. Optional tools can have
narrower requirements, listed in the [device tools guide](device-tools.md).

## Install on Kindle

1. Download [install-kindle.sh](../integration/install-kindle.sh) using
   **Download raw file** and copy it into the Kindle's `documents` folder.
   Keep the filename `install-kindle.sh`.
2. Eject and disconnect the Kindle from your computer. Connect to Wi-Fi in
   the Kindle's settings.
3. Open **Install k2** in the library. Keep Wi-Fi connected while it runs;
   installation can take a few minutes.
4. When installation finishes, open **k2** in the library. The installer
   removes itself after checking that K2 and its library shortcut are installed.

The installer reuses an existing package setup or prepares one automatically.
If installation stops, follow the message on screen and open **Install k2**
again. It stays in the library until installation succeeds. Further details
are saved in `k2-install.log` on USB storage.

### Kindle 4

Use the `kindle5` build with `qt5-ereader-platform`, the shared Qt framebuffer
plugin. The configured feed must contain both packages. The framebuffer plugin
is available in local feeds and build artifacts; it is not in the public feed.
Open **k2 → Open k2** in KUAL, or run this command in a root shell:

```sh
sh /mnt/us/.eink-sdk/control/run k2
```

The D-pad moves the focus outline; Centre selects. Back closes a menu or returns
to the previous page, Home opens k2's home screen, and Menu opens device controls.
The page buttons turn package-list pages or scroll other pages. Select a text
field or press Keyboard to open the on-screen keyboard; use the D-pad and Centre
to enter text. Back closes it. KPP Mods is unavailable on Kindle 4.

k2 takes over the framebuffer while open and restores the original Kindle
interface when it exits.

## Install on Kobo

Run these commands in the reader's **root shell**, not on your computer.
They keep the configured feeds and upgrade opkg before installing K2.

```sh
opkg update
opkg upgrade opkg
opkg install k2
```

Restart the reader after the first installation so Nickel, Kobo's original
interface, loads the `k2-nickel` integration. Open **k2** from the button in
Nickel's bottom bar. Restart again after an update to `k2-nickel`.

## First use

1. Join a network in the reader's original settings if you want to download
   software. K2 can turn Wi-Fi on and off, but network setup stays there.
2. Open **App Store**. **Featured** shows selected apps; **All** lists the
   packages available from your feeds. Use the refresh button to check again.
3. Select a package to read its description. Choose **Install**, review the
   proposed changes, and confirm. Dependencies are included in the review.
4. Read the result. If the package supplies a launcher, use **Open**; otherwise,
   follow its usage instructions.

To install a reading app, open **KOReader** on K2's home screen and follow the
[KOReader guide](koreader.md). To return to the reader's original interface,
open the gear menu and choose **Exit k2**.

## Update or remove K2

Use **App Store → Updates** to update K2. Follow any request to restart K2 or
the reader. [Using K2](user-guide.md#update-packages) explains update results.

K2 cannot remove itself from its interface. Close K2 and run one of these
commands in the reader's root shell:

```sh
# Kindle
opkg remove k2

# Kobo
opkg remove k2
```

The separate `k2-nickel` package supplies the Kobo button. If you also remove
that package, restart the reader to unload it.
