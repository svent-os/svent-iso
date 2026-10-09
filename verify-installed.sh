#!/bin/bash
set -euo pipefail
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH:-}"
if [ -d /run/live/medium ]; then
    printf '%s\n' 'Run this check after installing and booting from the target disk.' >&2
    exit 1
fi
for package in svent-xfce svent-core svent-artwork svent-boot lxdm locales-all firefox-esr libreoffice-writer libreoffice-calc libreoffice-impress vlc gimp torbrowser-launcher; do
    status=$(dpkg-query -W -f='${Status}' "$package")
    test "$status" = 'install ok installed'
done
if getent passwd svent-live >/dev/null; then
    printf '%s\n' 'The live account was not removed.' >&2
    exit 1
fi
test ! -e /usr/share/applications/svent-install.desktop
test ! -e /etc/sudoers.d/svent-live-installer
test -s /usr/share/keyrings/svent-archive-keyring.gpg
test -f /etc/apt/sources.list.d/svent.sources
test -s /boot/grub/grub.cfg
test "$(systemctl get-default)" = graphical.target
systemctl is-enabled lxdm.service NetworkManager.service >/dev/null
if grep -q '^autologin=svent-live$' /etc/lxdm/lxdm.conf; then
    printf '%s\n' 'The installed display manager still uses the live account.' >&2
    exit 1
fi
locale -a | grep -i '^es_ES\.utf8$' >/dev/null
locale -a | grep -i '^ja_JP\.utf8$' >/dev/null
printf '%s\n' 'Installed-system checks passed.'
