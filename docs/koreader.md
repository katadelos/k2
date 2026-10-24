# KOReader

[K2 overview](../README.md) · [Using K2](user-guide.md)

K2 can install and update [KOReader](https://koreader.rocks/), open an existing
copy, and manage added plugins. KOReader is a separate reading app with its own
settings and updater. K2 downloads its official releases directly; it does not
install KOReader through opkg.

## Install or choose a copy

1. Open **KOReader** on the home screen.
2. If KOReader is already installed, select the copy that you want to manage.
   K2 checks standard locations and custom paths used by existing launchers.
3. If it is not installed, use the update button to check for a release, then
   choose **Install KOReader**. Review the proposed installation and confirm.
   K2 selects the stable release for the device's original firmware and installs
   it in user storage.
4. Choose **Open KOReader** to start reading. K2 closes and releases the screen
   before launching it.

On Kindle, **Add to Kindle library** creates a `documents/KOReader.sh` shortcut
and icon for the selected copy. The shortcut also appears in KPP Mods.

On Kobo, installation excludes KOReader's program folder from the stock library
scan. Restart the reader before the next USB file transfer if prompted.

## Update KOReader

Close KOReader before changing its installation or plugins. Open its page in K2
and use the update control to check the official stable release. If an update
is available, choose **Update**, review it, and confirm.

K2 preserves settings, reading progress, and custom plugins when updating the
selected installation. It avoids downgrading newer builds, but may offer a
newer stable release for an older nightly. Use KOReader's own updater to stay
on the nightly channel.

If the selected copy is incomplete or uses the wrong build, the page reports
that setup needs attention and offers **Reinstall** when a suitable release is
available. Review the proposed change before confirming it.

## Choose a customisation

Open **Customise KOReader** to browse SimpleUI, ZenOS, Bookshelf, Bookends,
Reading Insights, LocalSend, and Customisable Sleep Screen. The **All**,
**Installed**, and **Updates** tabs help you find and manage them.

Select an entry to read its purpose, setup instructions, and compatibility
requirements. **View preview** opens an upstream screenshot when one is
available. K2 caches previews for later viewing.

Choose **Install** or **Update** and confirm the change. Some entries also offer
**Enable** and **Disable**. Restart KOReader after changes and complete any
setup described in the entry.

K2 checks known interface conflicts, required KOReader versions, and native
requirements such as those for LocalSend. When it blocks a change, read the
reason on the page. It does not disable a competing plugin for you.

The catalogue installs reviewed releases. A refresh may find a newer upstream
release that is not yet offered for installation. Existing Zen UI installations
and plugins installed or updated outside K2 may need their own updater.

For plugins managed by K2, updates preserve files that you added or modified.
K2 removes obsolete upstream files only when they are unchanged. It does not
downgrade a newer installed version. You can browse installed plugins offline.

## Add another plugin

From the KOReader page, open **Customise KOReader → Manage other plugins →
Add plugin**. Supply an HTTPS archive URL or the path to a local ZIP or tar
archive. The archive must contain a
`.koplugin` folder with `main.lua`; GitHub source archives for repositories named
`*.koplugin` are also accepted.

Review and confirm the installation. Installing an archive with the same plugin
name updates that added plugin and preserves extra files in its folder. Open
KOReader to enable or configure it.

Use this page to remove an added plugin. Removal deletes its folder while
keeping KOReader's shared settings and reading progress. Plugins bundled with
KOReader are managed inside KOReader.

## Resolve a plugin error

Read the error before retrying. Some settings or plugin locations can only be
managed inside KOReader, including linked plugin folders and settings that
contain Lua expressions.

If K2 cannot recover from a failed plugin change, it keeps the previous files
in `.k2-plugin-transaction` and reports their location. Further changes are
blocked until recovery can finish. Keep those files. If the error identifies a
conflicting plugin folder, resolve the conflict before retrying; recovery will
not overwrite an existing folder.

## Uninstall KOReader

Choose **Uninstall KOReader** and read the confirmation. It deletes the selected
installation, including its plugins, customisations, settings, and reading
history, and removes the shortcut created by K2. Books outside that installation
folder are kept.
