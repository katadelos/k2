#!/bin/sh
# Name: Install k2
# Author: k2
# Install k2 from the Kindle library.
set -eu
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
store=/mnt/us/.eink-sdk
runner=$store/control/run
launcher=/mnt/us/documents/k2.sh
log=/mnt/us/k2-install.log
lock=/tmp/k2-install.lock

message() {
    printf '%s\n' "$@"
    eips -c 2>/dev/null || true
    eips 1 2 'Install k2' 2>/dev/null || true
    row=4
    for line do
        eips 1 "$row" "$line" 2>/dev/null || true
        row=$((row + 2))
    done
}

mkdir "$lock" 2>/dev/null || { message 'k2 installation is already running.'; exit 1; }
work=
awake=
failure='Installation did not finish.'
hint='See k2-install.log over USB, then retry.'
cleanup() {
    result=$?
    trap - 0
    if [ -n "$awake" ]; then
        kill "$awake" 2>/dev/null || true
        wait "$awake" 2>/dev/null || true
    fi
    [ -z "$work" ] || rm -rf "$work"
    rmdir "$lock"
    if [ "$result" -ne 0 ]; then
        message "$failure" "$hint"
    fi
    sleep 5
    exit "$result"
}
trap cleanup 0
trap 'exit 1' 1 2 15

fail() {
    failure=$1
    hint=$2
    exit 1
}

[ "$(id -u)" = 0 ] || fail 'Root access is required.' 'Open Install k2 from your library.'
installer=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)/$(basename -- "$0")
[ "$installer" != "$launcher" ] || fail 'Rename this file to install-kindle.sh.' 'Then open Install k2 again.'

profiles=$(lipc-get-prop com.lab126.wifid profileCount 2>/dev/null) ||
    fail 'Cannot check Wi-Fi settings.' 'Restart the Kindle, then try again.'
case "$profiles" in
    ''|*[!0-9]*) fail 'Cannot check saved Wi-Fi networks.' 'Restart the Kindle, then try again.' ;;
esac
[ "$profiles" -gt 0 ] || fail 'No Wi-Fi network is saved.' 'Connect in Settings, then try again.'
state=$(lipc-get-prop com.lab126.wifid cmState 2>/dev/null) ||
    fail 'Cannot check the Wi-Fi connection.' 'Connect in Settings, then try again.'
[ "$state" = CONNECTED ] || fail 'Wi-Fi is not connected.' 'Connect in Settings, then try again.'

work=$(mktemp -d /tmp/k2-install.XXXXXX)
(
    while :; do
        lipc-set-prop com.lab126.powerd touchScreenSaverTimeout 1 2>/dev/null || true
        sleep 15
    done
) &
awake=$!

install_k2() {
    date
    if [ ! -f "$runner" ] || [ ! -s "$store/opkg/opkg.conf" ] || [ ! -x "$store/usr/bin/opkg" ]; then
        message 'Preparing installation...' 'Keep Wi-Fi connected.'
        # Download completely before running; a failed curl must stop installation.
        curl -fL --connect-timeout 15 --max-time 60 \
            https://katadelos.github.io/eink-opkg-beta/install.sh -o "$work/bootstrap.sh"
        /bin/sh "$work/bootstrap.sh"
    fi
    [ -f "$runner" ] && [ -s "$store/opkg/opkg.conf" ] && [ -x "$store/usr/bin/opkg" ] ||
        fail 'Package setup is incomplete.' 'See k2-install.log over USB, then retry.'
    message 'Checking available packages...' 'Keep Wi-Fi connected.'
    /bin/sh "$runner" opkg update
    /bin/sh "$runner" opkg upgrade opkg
    message 'Installing k2...' 'This can take a few minutes.'
    /bin/sh "$runner" opkg install k2
    /bin/sh "$runner" opkg status k2 > "$work/k2-status"
    grep -q '^Status: [^ ]* ok installed$' "$work/k2-status" ||
        fail 'k2 installation is incomplete.' 'See k2-install.log over USB, then retry.'
    [ -s "$launcher" ] && cmp -s "$launcher" "$store/usr/share/k2/integration/k2.sh" ||
        fail 'The k2 library shortcut is missing.' 'See k2-install.log over USB, then retry.'
    rm -- "$installer" || fail 'k2 is installed.' 'Remove Install k2 from your library.'
}

message 'Starting installation...' 'Keep Wi-Fi connected.'
install_k2 > "$log" 2>&1
message 'k2 is installed.' 'Open k2 from your library.'
