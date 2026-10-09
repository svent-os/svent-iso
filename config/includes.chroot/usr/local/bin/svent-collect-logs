#!/bin/bash
set -uo pipefail
output="${1:-/tmp/svent-boot-diagnostics.txt}"
{
    printf '%s\n' 'SventOS boot diagnostics' 'Kernel command line'
    cat /etc/svent-build
    cat /proc/cmdline
    printf '%s\n' 'Live account'
    getent passwd svent-live
    printf '%s\n' 'System state'
    systemctl get-default
    systemctl --failed --no-pager
    systemctl status live-config.service display-manager.service lxdm.service --no-pager -l
    printf '%s\n' 'Display manager selection'
    cat /etc/X11/default-display-manager
    ls -l /etc/systemd/system/display-manager.service
    printf '%s\n' 'Boot service journal'
    journalctl -b -u live-config.service -u lxdm.service --no-pager -n 250
    printf '%s\n' 'LXDM configuration'
    cat /etc/lxdm/lxdm.conf
    printf '%s\n' 'Graphics devices'
    lspci -nnk | sed -n '/VGA\|Display\|3D/,+4p'
    printf '%s\n' 'Graphics errors'
    journalctl -b --no-pager | grep -Ei 'vmwgfx|drm|xorg|lxdm|xfce|user-setup|failed|error' | tail -n 160
    for log in /var/log/lxdm.log /var/log/Xorg.0.log /home/svent-live/.local/share/xorg/Xorg.0.log /home/svent-live/.xsession-errors; do
        if [ -f "$log" ]; then
            printf '\n%s\n' "$log"
            tail -n 120 "$log"
        fi
    done
} > "$output" 2>&1
printf 'Diagnostics saved to %s\n' "$output"
