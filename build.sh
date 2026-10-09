#!/bin/bash
set -euo pipefail
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH:-}"
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if [ "$(id -u)" -ne 0 ]; then
    printf '%s\n' 'Run this script as root.' >&2
    exit 1
fi
for tool in lb debootstrap tee sha256sum stat xorriso unsquashfs mktemp; do
    command -v "$tool" >/dev/null || exit 1
done
bash -n build.sh verify-installed.sh
chmod +x auto/config auto/build auto/clean config/hooks/normal/*.hook.chroot
sh -n config/includes.chroot/etc/grub.d/06_svent_colors
sh -n auto/config auto/build auto/clean config/hooks/normal/*.hook.chroot config/includes.chroot/usr/local/bin/* config/includes.chroot/usr/local/sbin/*
lb clean --purge
rm -f config/bootstrap config/chroot config/binary config/common config/source
lb config
grep -q '^LB_DISTRIBUTION="trixie"$' config/bootstrap
grep -q '^LB_DISTRIBUTION_CHROOT="trixie"$' config/bootstrap
grep -q '^LB_DISTRIBUTION_BINARY="trixie"$' config/bootstrap
lb build 2>&1 | tee build.log
iso=sventos-live-r3-amd64.hybrid.iso
test -s "$iso"
test -s binary/boot/grub/grub.cfg
grep -q 'Start SventOS' binary/boot/grub/grub.cfg
grep -q 'set menu_color_normal=light-red/black' binary/boot/grub/grub.cfg
if grep -q '@KERNEL_LIVE@\|@INITRD_LIVE@\|@APPEND_LIVE@' binary/boot/grub/grub.cfg; then
    printf '%s\n' 'Unresolved GRUB template variables.' >&2
    exit 1
fi
checkdir=$(mktemp -d)
trap 'rm -rf -- "$checkdir"' EXIT
xorriso -osirrox on -indev "$iso" -extract /boot/grub/grub.cfg "$checkdir/grub.cfg"
grep -Fq 'Start SventOS [Live R3]' "$checkdir/grub.cfg"
grep -Fq 'set menu_color_highlight=white/red' "$checkdir/grub.cfg"
xorriso -osirrox on -indev "$iso" -extract /live/filesystem.squashfs "$checkdir/filesystem.squashfs"
unsquashfs -cat "$checkdir/filesystem.squashfs" etc/svent-build | grep -qx sventos-live-r3
unsquashfs -cat "$checkdir/filesystem.squashfs" etc/passwd | grep -Eq '^svent-live:[^:]*:[0-9]+:[0-9]+:.*:/home/svent-live:/bin/bash$'
unsquashfs -cat "$checkdir/filesystem.squashfs" etc/shadow | grep -q '^svent-live:\$6\$'
unsquashfs -cat "$checkdir/filesystem.squashfs" etc/lxdm/lxdm.conf | grep -qx 'autologin=svent-live'
unsquashfs -cat "$checkdir/filesystem.squashfs" etc/X11/default-display-manager | grep -qx /usr/sbin/lxdm
size=$(stat -c %s "$iso")
if [ "$size" -gt 4000000000 ]; then
    printf 'ISO exceeds the 4 GB limit: %s bytes\n' "$size" >&2
    exit 1
fi
sha256sum "$iso" > "$iso.sha256"
printf 'ISO ready: %s (%s bytes)\n' "$iso" "$size"
