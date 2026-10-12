#!/bin/bash
set -euo pipefail
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH:-}"
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
test "$(id -u)" -eq 0 || { printf '%s\n' 'Run this script as root.' >&2; exit 1; }
for command in lb debootstrap xorriso mksquashfs unsquashfs python3 sha256sum flock; do
    command -v "$command" >/dev/null
done
exec 9>.build.lock
flock -n 9 || { printf '%s\n' 'Another build is running.' >&2; exit 1; }
bash -n build.sh
sh -n auto/config config/hooks/normal/0200-live.hook.chroot
python3 -c 'import ast; from pathlib import Path; ast.parse(Path("config/includes.chroot/usr/libexec/svent/prepare-live-shutdown").read_text())'
free=$(df -Pk . | awk 'NR == 2 {print $4}')
test "$free" -ge 8388608 || { printf '%s\n' 'At least 8 GiB of free disk space is required.' >&2; exit 1; }
chmod +x auto/config config/hooks/normal/0200-live.hook.chroot
if [ -d .build ]; then
    lb clean
fi
lb config
lb build 2>&1 | tee build.log
iso=sventos-live-amd64.hybrid.iso
test -s "$iso"
test -s binary/live/filesystem.squashfs
unsquashfs -cat binary/live/filesystem.squashfs etc/passwd | grep -q '^svent-live:'
unsquashfs -cat binary/live/filesystem.squashfs etc/lxdm/lxdm.conf | grep -Eq '^autologin[[:space:]]*=[[:space:]]*svent-live$'
unsquashfs -cat binary/live/filesystem.squashfs home/svent-live/.config/xfce4/xfconf/xfce-perchannel-xml/xfwm4.xml | grep -q 'name="use_compositing" type="bool" value="false"'
sha256sum "$iso" > "$iso.sha256"
sha256sum -c "$iso.sha256"
ls -lh "$iso"
