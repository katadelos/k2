# Device tools

[K2 overview](../README.md) · [Using K2](user-guide.md)

These tools are optional packages. Install them from App Store if your device's
feed supplies them. Their controls appear on the Device page after package
setup succeeds. Open that page through **gear → Device details**.

| Feature | Package | Platforms |
| --- | --- | --- |
| SSH, USB debugging, and wake controls | `supernet` | Kindle and Kobo; available controls depend on installed providers |
| Wireless file transfers | `k2-fileshare` | Kindle with the `kindlehf` profile |
| View and control the screen from a computer | `k2-vnc` | Kindle with the `kindlehf` profile |

## Connect over SSH

1. Install `supernet` and open **Developer tools**.
2. Add your SSH public key to the file shown on the page, then refresh the
   status. Authentication uses public keys only.
3. Choose **USB**, **Wi-Fi**, or **Both**. For Wi-Fi, join a network through the
   reader's original settings first.
4. Choose **Start SSH**. Use the displayed address, port, and connection
   instructions from your computer.

Installing Supernet or opening the page does not start SSH. Connection types
are chosen for each session; stop SSH before changing them. **Stop SSH** closes
Supernet's sessions after confirmation. Stop it before updating or removing
the package. Its configuration and authorised keys are preserved on upgrade.

On Kindle, stopping a session that used USB leaves USB networking enabled
while apps are using storage. Reboot the reader to restore USB file-transfer
mode. On Kobo, Supernet releases the USB network connection that it created.
If setup fails or SSH stops unexpectedly, use **Clean up connection**.

An active SSH connection keeps the reader awake where the firmware supports
Supernet's wake controls. An idle listener does not. On Kobo, Nickel may turn
Wi-Fi off after K2 exits, which can interrupt a Wi-Fi SSH connection. SSH does
not start automatically at boot.

### USB debugging and wake controls

ADB controls appear when a provider is installed. USB SSH and ADB cannot use
the USB connection at the same time; Wi-Fi SSH can run alongside ADB.
**Keep awake** prevents sleep during debugging and resets after reboot.

### KPP Mods maintenance

On Kindle with KPP Mods installed, Developer tools also offers:

- **Restart interface** to restart the KPP interface.
- **Disable optional extensions** to retain the core interface while turning
  off optional extensions. Their settings are kept.
- **Export diagnostics** to save runtime status, the extension list, and recent
  system logs under `/mnt/us/kppmods-diagnostics/`. Review these files before
  sharing them.

The page also displays recent extension errors.

## Transfer files over Wi-Fi

Install `k2-fileshare`, join Wi-Fi, and open **File Sharing** from Device or its
gear-menu shortcut. Start sharing, then choose either connection method:

- **Computer:** find `Kindle <serial suffix>` in Finder or Windows Network.
  Open the **Reader** share with username `reader` and the displayed password.
  Use the direct SMB address from K2 if discovery does not work.
- **Phone or browser:** scan the QR code to browse folders, download files,
  and upload files through the web page.

The share contains the reader's user files. Package runtime and system directories are
excluded, and links are not followed. Changes are visible in K2's file manager;
the original firmware handles indexing for its library. Browser uploads do not
replace existing files, and incomplete uploads are removed.

Use a trusted network. The browser page uses unencrypted HTTP, and anyone with
its QR link can access the shared files. The link expires when sharing stops.
The SMB service requires SMB2 or SMB3 with signing; guest access is disabled.

### End a sharing session

Sharing continues after K2 closes and keeps the reader awake. Return to
**File Sharing** and stop the session when finished, and before updating or
removing the package.

USB file export and wireless sharing cannot run together. Starting sharing
switches USB to network mode. After stopping, reboot the Kindle to restore
USB file-transfer mode. Sharing stops if the required storage, USB mode, or
Wi-Fi address changes. It does not start automatically at boot.

If K2 cannot determine whether sharing stopped, it reports an unknown state
and keeps **Stop** available. Check the status again rather than assuming
that transfers have ended.

## Share the screen

Install `k2-vnc` and open **Screen sharing** on Device. When Supernet is also
installed, use the **Screen** tab beside **Developer tools**.

1. Connect the Kindle to Wi-Fi or set up USB networking. Screen sharing uses
   an existing connection; it does not configure one.
2. Choose **Start screen sharing**.
3. Open a VNC client on your computer, such as Screen Sharing on macOS. Enter
   the address, port, and password displayed by K2.
4. Use the client to view the screen, tap, and type. Sharing continues after K2
   closes. Return to **Screen sharing → Stop sharing** when finished.

A new password is generated for each session. The reader stays awake until
sharing stops. Use a trusted network: VNC screen and input traffic are
unencrypted.
