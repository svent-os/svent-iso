#!/bin/bash
set -euo pipefail
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH:-}"
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
test "$(id -u)" -eq 0 || { printf '%s\n' 'Run this script as root.' >&2; exit 1; }
for command in lb debootstrap xorriso mksquashfs unsquashfs python3 sha256sum flock grub-script-check; do
    command -v "$command" >/dev/null
done
exec 9>.build.lock
flock -n 9 || { printf '%s\n' 'Another build is running.' >&2; exit 1; }
bash -n build.sh
grub-script-check config/bootloaders/grub-pc/grub.cfg
sh -n auto/config config/hooks/normal/0200-live.hook.chroot
python3 -c 'import ast; from pathlib import Path; ast.parse(Path("config/includes.chroot/usr/libexec/svent/prepare-live-shutdown").read_text())'
python3 -c 'import ast; from pathlib import Path; ast.parse(Path("config/includes.chroot/usr/libexec/svent/prepare-install-launcher").read_text())'
python3 -c 'import yaml; from pathlib import Path; root=Path("config/includes.chroot/etc/calamares"); [yaml.safe_load(p.read_text()) for p in root.rglob("*") if p.suffix in (".conf", ".desc")]; settings=yaml.safe_load((root/"settings.conf").read_text()); assert settings["sequence"] == [{"show": ["welcome"]}]'
python3 -c 'import yaml; from pathlib import Path; b=yaml.safe_load(Path("config/includes.chroot/etc/calamares/branding/svent/branding.desc").read_text()); assert {"componentName", "slideshow", "strings", "images", "style"} <= b.keys(); assert isinstance(b["slideshow"], list)'
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
grub-script-check binary/boot/grub/grub.cfg
test "$(grep -c '^menuentry ' binary/boot/grub/grub.cfg)" -eq 2
grep -q '^set menu_color_normal=light-red/black$' binary/boot/grub/grub.cfg
grep -q '^set menu_color_highlight=white/red$' binary/boot/grub/grub.cfg
if grep -Eq '@(KERNEL_LIVE|INITRD_LIVE|APPEND_LIVE)@' binary/boot/grub/grub.cfg; then
    printf '%s\n' 'Unresolved GRUB boot parameters.' >&2
    exit 1
fi
test -s binary/live/filesystem.squashfs
unsquashfs -cat binary/live/filesystem.squashfs etc/passwd | grep -q '^svent-live:'
unsquashfs -cat binary/live/filesystem.squashfs etc/lxdm/lxdm.conf | grep -Eq '^autologin[[:space:]]*=[[:space:]]*svent-live$'
unsquashfs -cat binary/live/filesystem.squashfs home/svent-live/.config/xfce4/xfconf/xfce-perchannel-xml/xfwm4.xml | grep -q 'name="use_compositing" type="bool" value="false"'
sha256sum "$iso" > "$iso.sha256"
sha256sum -c "$iso.sha256"
ls -lh "$iso"
