#!/bin/bash
set -euo pipefail
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH:-}"
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if [ "$(id -u)" -ne 0 ]; then
    printf '%s\n' 'Run this script as root.' >&2
    exit 1
fi
for tool in lb debootstrap tee sha256sum stat; do
    command -v "$tool" >/dev/null || exit 1
done
bash -n build.sh verify-installed.sh
chmod +x auto/config auto/build auto/clean config/hooks/normal/*.hook.chroot
sh -n auto/config auto/build auto/clean config/hooks/normal/*.hook.chroot config/includes.chroot/usr/local/bin/* config/includes.chroot/usr/local/sbin/*
lb clean --purge
rm -f config/bootstrap config/chroot config/binary config/common config/source
lb config
grep -q '^LB_DISTRIBUTION="trixie"$' config/bootstrap
grep -q '^LB_DISTRIBUTION_CHROOT="trixie"$' config/bootstrap
grep -q '^LB_DISTRIBUTION_BINARY="trixie"$' config/bootstrap
lb build 2>&1 | tee build.log
iso=live-image-amd64.hybrid.iso
test -s "$iso"
size=$(stat -c %s "$iso")
if [ "$size" -gt 4000000000 ]; then
    printf 'ISO exceeds the 4 GB limit: %s bytes\n' "$size" >&2
    exit 1
fi
sha256sum "$iso" > "$iso.sha256"
printf 'ISO ready: %s (%s bytes)\n' "$iso" "$size"
