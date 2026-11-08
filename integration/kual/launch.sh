#!/bin/sh
set -eu
# Detach before the framebuffer session stops the Java framework running KUAL.
exec /bin/sh /mnt/us/.eink-sdk/control/run python3 -c '
import subprocess
with open("/var/run/k2.log", "a") as log:
    subprocess.Popen(
        ["/bin/sh", "/var/run/eink-sdk/usr/bin/k2"],
        stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
        start_new_session=True,
    )
'
