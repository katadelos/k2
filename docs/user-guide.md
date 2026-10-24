# Using K2

[K2 overview](../README.md) · [Installation](getting-started.md)

## Find your way around

The home screen opens **App Store**, **KOReader**, **File manager**, and
**About k2**. The back button returns to the previous page.

Open the gear menu for brightness, Wi-Fi, dark mode, **Device details**,
and **Exit k2**. Installed tools can add shortcuts here and on the Device page.
Brightness appears when the device supports it.

## Install an app or package

1. Open **App Store**. Choose **Featured** for selected apps or **All** for the
   full catalogue. The catalogue includes command-line tools and libraries as
   well as apps.
2. Search for a package or select it from the list. Searching from Featured
   switches to All; in Installed or Updates, it filters that tab. Tap outside
   the keyboard to dismiss it.
3. Read the description and choose **Install**. K2 shows the packages that
   opkg proposes to install or change, their versions, and available download
   sizes.
4. Review the list and confirm. Wait for the operation to finish, then read
   its result. **Show details** displays the command output.

The download size is the total size of the archives. Files already in the
download cache may reduce the amount transferred.

Installed apps with a launch entry have an **Open** action. K2 closes before
starting the app so it can use the screen. Packages without a launcher display
their usage instructions or command names. Optional tools can instead link to
their controls inside K2.

### Refresh the catalogue

Use the refresh button in App Store to reload the package lists and Featured
content. K2 also checks once after startup if a network connection is available.
It keeps your current tab, search, and page when the lists refresh.

You can browse the saved package catalogue offline. A failed refresh does not
mean that installed packages have been removed. Check the refresh status in
App Store before relying on the list of available versions. K2 does not enable
Wi-Fi or install updates automatically.

## Update packages

Open **App Store → Updates**. Select a package to update it, or choose
**Update all** to review updates for all installed packages. Update all includes
packages hidden by the current search. Confirm the proposed changes to proceed.

An update can require a restart:

- After a successful K2 update, K2 can close and reopen itself once its runtime
  packages are ready and background work has finished.
- Some runtime updates require you to exit and reopen K2.
- An update to the Kobo integration requires a reader restart.

Follow the message in the result. If an operation fails partway through, some
packages may already have changed; check Activity before trying again.

## Read operation results

K2 opens the operation page when you confirm a package change. Its title is
**Activity**, or **Update** during an update. Use **Show details** for the command
output. If you browse away while work is in progress, tap the progress button
above the page to return. After a failure, the status row on the home screen
also opens the details.

Activity retains the last result after K2 closes and flags interrupted
operations for review.

## Remove a package

Open **App Store → Installed**, select the package, and choose **Remove**.
Review the proposed removals before confirming. Stop any file-sharing or SSH
session provided by that package first.

K2 protects itself and the core packages that it needs to run. To remove K2,
use the [shell instructions](getting-started.md#update-or-remove-k2).

## Manage books and folders

Open **File manager** from the home screen, or **Files** from Device. It shows
the reader's user storage: `/mnt/us` on Kindle and `/mnt/onboard` on Kobo.

| Task | Action |
| --- | --- |
| Open a folder | Tap it; use the breadcrumbs to return to a parent folder |
| Change the view | Use the grid/list control above the files |
| Create a folder | Tap the folder-plus icon |
| Rename, move, copy, or delete | Long-press an item or open its three-dot menu |
| Choose a destination | After Move or Copy, browse to a folder and select **Move here** or **Copy here** |
| Filter the list | Open the folder menu and select **Show books only** |
| Show hidden files or reload the folder | Use the folder menu |

The file manager organises files; open your reading app to read books.
K2 does not replace an existing file during a move or copy. Deletion requires
confirmation and is permanent; there is no trash. The file manager does not
follow links and protects package storage from changes.

Some kernels or filesystems cannot perform the exclusive rename operation
required by **Rename** and **Move**. If K2 reports this limitation, copy the item
to another folder, check the copy, and then delete the original to complete a
move. Copy keeps the filename; renaming on these devices requires another tool.

## Adjust settings

Use the gear menu to change brightness where supported, toggle Wi-Fi, or select
dark mode. On Kindles that expose a system dark-mode setting, K2 uses that
setting. Elsewhere, K2 remembers its own choice for the interface and keyboard.

Connect to new Wi-Fi networks and manage saved passwords in the reader's
original settings. K2's Wi-Fi control reconnects through the firmware.

**Device details** shows the model, firmware, architecture, and kernel. It also
opens installed [device tools](device-tools.md).

K2 keeps the reader awake while you use it or change packages. On Kobo this
also prevents cover and power-button sleep while K2 is open; choose **Exit k2**
when finished to return to normal sleep behaviour. Kindle's original software
still controls its screen state.

## Common problems

### App Store is empty or out of date

Check the network connection in the original interface, then refresh App Store.
If Featured is unavailable, use **Browse all** to open the package catalogue.
If the package itself is missing, the configured feed may not supply it for your
device. K2 uses the feeds selected by package setup.

### An installation or update failed

Open the [operation result](#read-operation-results), select **Show details**,
and read the output. A package error
and an error while reloading the catalogue are separate results: a failed list
refresh does not necessarily mean that installation failed.

For an insufficient-space error, free space in user storage and retry. For a
package marked **Setup needed**, review its setup error, resolve the cause,
then use **Finish setup** in package details. Do not remove package runtime files through
another file manager to make room.

### An installed tool has no shortcut

The package must supply a K2 integration and complete its setup before its
controls appear. Check its package details and Activity. A command-line package
may have usage instructions without a graphical launcher.

### K2 is missing from the reader's interface

On Kindle, check that the Scriptlet shortcut was installed and that the
jailbreak's Scriptlet integration is available. On Kobo, restart the reader
after installing or updating `k2-nickel`. See [installation](getting-started.md).

For plugin problems, see [KOReader](koreader.md). For USB access and services
that continue after K2 closes, see [device tools](device-tools.md).
