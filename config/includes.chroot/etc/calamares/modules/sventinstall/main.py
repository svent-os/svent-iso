import configparser
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import urllib.request
import xml.etree.ElementTree as ET

import libcalamares


XFCE = ['svent-xfce', 'xfce4', 'xfce4-session', 'xfce4-panel', 'xfdesktop4', 'xfwm4', 'xfce4-settings', 'xfce4-terminal', 'xfce4-appfinder', 'xfce4-power-manager', 'xfce4-power-manager-plugins', 'xfce4-notifyd', 'xfce4-screenshooter']
LIVE_PACKAGES = ['calamares', 'live-boot', 'live-boot-initramfs-tools', 'live-config', 'live-config-systemd', 'live-tools']
LIVE_FILES = [
    'etc/sudoers.d/svent-live',
    'etc/systemd/system/lxdm.service.d/10-live.conf',
    'etc/systemd/logind.conf.d/10-live.conf',
    'etc/systemd/system/run-live-medium.mount.d/10-live-shutdown.conf',
    'etc/systemd/system/svent-live-shutdown.service',
    'etc/systemd/system/multi-user.target.wants/svent-live-shutdown.service',
    'usr/libexec/svent/prepare-live-shutdown',
    'usr/libexec/svent/prepare-install-launcher',
    'usr/local/bin/svent-install',
    'usr/share/applications/svent-install.desktop',
    'usr/share/svent/installer']


def target(*args):
    return libcalamares.utils.check_target_env_call(['env', 'DEBIAN_FRONTEND=noninteractive', 'NEEDRESTART_MODE=a', *args])


def target_root():
    root = Path(libcalamares.globalstorage.value('rootMountPoint')).resolve()
    if not root.is_absolute() or root == Path('/') or not (root / 'etc/passwd').is_file():
        raise RuntimeError('The installation target is invalid.')
    return root


def path_in(root, name):
    path = root / name
    if not path.parent.resolve().is_relative_to(root.resolve()):
        raise RuntimeError('A target path points outside the installation: ' + name)
    return path


def remove(root, name):
    path = path_in(root, name)
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def prepare(root, resolver=Path('/etc/resolv.conf')):
    path = path_in(root, 'etc/resolv.conf')
    if path.exists() or path.is_symlink():
        path.unlink()
    path.write_bytes(resolver.read_bytes())
    passwd = (root / 'etc/passwd').read_text()
    if any(line.startswith('svent-live:') for line in passwd.splitlines()):
        target('userdel', '--force', 'svent-live')
        remove(root, 'home/svent-live')
        group = (root / 'etc/group').read_text()
        if any(line.startswith('svent-live:') for line in group.splitlines()):
            target('groupdel', 'svent-live')
    policy = path_in(root, 'usr/sbin/policy-rc.d')
    policy.write_text('#!/bin/sh\nexit 101\n')
    policy.chmod(0o755)


def selection(operations, metadata, desktop, boot, firmware):
    if desktop not in ('xfce', 'bspwm', 'both', 'none') or boot not in ('grub', 'none'):
        raise RuntimeError('Desktop or bootloader selection is invalid.')
    requested = set(metadata['mandatory'])
    allowed = set(metadata['mandatory']) | set(metadata['base'])
    for members in metadata['categories'].values():
        allowed.update(members)
    for operation in operations:
        for item in operation.get('install', []):
            name = item if isinstance(item, str) else item['package']
            if name not in allowed:
                raise RuntimeError('Unexpected package selection: ' + name)
            requested.add(name)
    extras = []
    if desktop in ('xfce', 'both'):
        extras.append('svent-xfce')
    if desktop in ('bspwm', 'both'):
        extras.extend(['svent-bspwm', 'flameshot', 'pavucontrol', 'playerctl', 'brightnessctl', 'i3lock'])
    if desktop != 'none':
        extras.extend(['svent-login', 'lxdm', 'mousepad', 'thunar', 'gvfs', 'network-manager-gnome', 'libpam-gnome-keyring', 'gnome-keyring'])
    if boot == 'grub':
        extras.extend(['svent-boot', 'grub2-common', 'efibootmgr'])
        extras.extend(['grub-efi-amd64', 'grub-efi-amd64-signed', 'shim-signed'] if firmware == 'efi' else ['grub-pc'])
    vm = metadata['virtualization']
    extras.extend(vm['packages'])
    if desktop != 'none':
        extras.extend(vm['desktop_packages'])
    selected_metas = []
    for meta, members in metadata['categories'].items():
        if members and set(members) <= requested:
            extras.append(meta)
            selected_metas.append(meta)
    return sorted(requested | set(extras)), selected_metas


def installed(root, packages):
    available = set()
    for stanza in (root / 'var/lib/dpkg/status').read_text().split('\n\n'):
        if '\nStatus: install ok installed' not in '\n' + stanza:
            continue
        match = re.search(r'^Package: (.+)$', stanza, re.MULTILINE)
        if match:
            available.add(match.group(1))
    return sorted(set(packages) & available)


def validate_selection():
    metadata = json.loads(Path('/run/svent-installer/metadata.json').read_text())
    packages, _ = selection(
        libcalamares.globalstorage.value('packageOperations') or [], metadata,
        libcalamares.globalstorage.value('packagechooser_desktop'),
        libcalamares.globalstorage.value('packagechooser_boot'),
        libcalamares.globalstorage.value('firmwareType'))
    packages = [p for p in packages if p != 'obsidian']
    result = subprocess.run(['apt-get', '--simulate', '-o', 'Debug::NoLocking=1', 'install', '--no-install-recommends', *packages], capture_output=True, text=True, timeout=120)
    if result.returncode:
        raise RuntimeError('The selected packages cannot be installed.\n' + result.stderr[-3000:])
    removed = set(re.findall(r'^Remv ([^\s:]+)', result.stdout, re.MULTILINE))
    if removed & set(packages):
        raise RuntimeError('Selected packages conflict: ' + ', '.join(sorted(removed & set(packages))))


def remove_packages(root, removals, protected):
    result = subprocess.run(['chroot', str(root), 'apt-get', '--simulate', 'remove', *removals], capture_output=True, text=True, timeout=120)
    if result.returncode:
        raise RuntimeError('Live package cleanup could not be planned.\n' + result.stderr[-3000:])
    removed = set(re.findall(r'^Remv ([^\s:]+)', result.stdout, re.MULTILINE))
    conflicts = removed & set(protected)
    if conflicts:
        raise RuntimeError('Cleanup would remove selected packages: ' + ', '.join(sorted(conflicts)))
    target('apt-get', 'remove', '-y', *removals)


def obsidian(root):
    request = urllib.request.Request('https://api.github.com/repos/obsidianmd/obsidian-releases/releases/latest', headers={'User-Agent': 'SventOS-Installer'})
    with urllib.request.urlopen(request, timeout=30) as response:
        release = json.load(response)
    asset = next(item for item in release['assets'] if item['name'].endswith('_amd64.deb'))
    url = asset['browser_download_url']
    if not url.startswith('https://github.com/obsidianmd/obsidian-releases/releases/download/'):
        raise RuntimeError('The Obsidian download URL is invalid.')
    path = path_in(root, 'var/cache/svent-installer/obsidian.deb')
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'SventOS-Installer'}), timeout=120) as source, path.open('wb') as output:
        while block := source.read(1024 * 1024):
            output.write(block)
            digest.update(block)
    if path.stat().st_size != asset['size']:
        raise RuntimeError('The Obsidian download is incomplete.')
    if asset.get('digest') and asset['digest'] != 'sha256:' + digest.hexdigest():
        raise RuntimeError('The Obsidian download checksum does not match.')
    package = subprocess.check_output(['dpkg-deb', '--field', str(path), 'Package'], text=True).strip()
    architecture = subprocess.check_output(['dpkg-deb', '--field', str(path), 'Architecture'], text=True).strip()
    if package != 'obsidian' or architecture != 'amd64':
        raise RuntimeError('The Obsidian package metadata is invalid.')
    target('apt-get', 'install', '-y', '--no-install-recommends', '/var/cache/svent-installer/obsidian.deb')
    path.unlink()


def guest_integration(root, vm, desktop):
    folder = path_in(root, 'etc/svent')
    folder.mkdir(exist_ok=True)
    (folder / 'virtualization').write_text(vm['kind'] + '\n')
    if vm['kind'] != 'none' and desktop != 'none':
        homes = [root / 'etc/skel', root / 'root'] + [p for p in (root / 'home').iterdir() if p.is_dir() and not p.is_symlink()]
        for home in homes:
            if desktop in ('xfce', 'both'):
                path = path_in(root, str((home / '.config/xfce4/xfconf/xfce-perchannel-xml/xfwm4.xml').relative_to(root)))
                if path.is_symlink():
                    continue
                tree = ET.parse(path) if path.exists() else ET.ElementTree(ET.Element('channel', name='xfwm4', version='1.0'))
                parent = tree.getroot().find("property[@name='general']")
                if parent is None:
                    parent = ET.SubElement(tree.getroot(), 'property', name='general', type='empty')
                node = parent.find("property[@name='use_compositing']")
                if node is None:
                    node = ET.SubElement(parent, 'property', name='use_compositing')
                node.set('type', 'bool')
                node.set('value', 'false')
                path.parent.mkdir(parents=True, exist_ok=True)
                tree.write(path, encoding='utf-8', xml_declaration=True)
                owner = home.stat()
                os.chown(path, owner.st_uid, owner.st_gid)
                os.chown(path.parent, owner.st_uid, owner.st_gid)
            if desktop in ('bspwm', 'both'):
                path = path_in(root, str((home / '.config/picom/picom.conf').relative_to(root)))
                if path.is_symlink():
                    continue
                if path.is_file():
                    text = path.read_text()
                    if re.search(r'^\s*backend\s*=', text, re.MULTILINE):
                        text = re.sub(r'^\s*backend\s*=.*?;', 'backend = "xrender";', text, count=1, flags=re.MULTILINE)
                    else:
                        text = 'backend = "xrender";\n' + text
                    path.write_text(text)
    for unit in vm['services']:
        if any((root / base / unit).is_file() for base in ['usr/lib/systemd/system', 'lib/systemd/system']):
            target('systemctl', 'enable', unit)
    if desktop in ('bspwm', 'both'):
        script = path_in(root, 'etc/X11/Xsession.d/95svent-guest')
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text('''case "${DESKTOP_SESSION:-} ${XDG_CURRENT_DESKTOP:-}" in
    *bspwm*)
        case "$(cat /etc/svent/virtualization 2>/dev/null)" in
            vmware)
                if [ -x /usr/bin/vmware-user-suid-wrapper ]; then
                    /usr/bin/vmware-user-suid-wrapper >/dev/null 2>&1 &
                fi
                ;;
            kvm|qemu)
                if [ -x /usr/bin/spice-vdagent ]; then
                    /usr/bin/spice-vdagent >/dev/null 2>&1 &
                fi
                ;;
            oracle)
                if [ -x /usr/bin/VBoxClient ]; then
                    /usr/bin/VBoxClient --clipboard >/dev/null 2>&1 &
                    /usr/bin/VBoxClient --vmsvga >/dev/null 2>&1 &
                fi
                ;;
        esac
        ;;
esac
''')
        script.chmod(0o755)


def clean_live(root, desktop):
    for name in LIVE_FILES:
        remove(root, name)
    for target_name in ['sleep.target', 'suspend.target', 'hibernate.target', 'hybrid-sleep.target', 'suspend-then-hibernate.target']:
        path = path_in(root, 'etc/systemd/system/' + target_name)
        if path.is_symlink() and os.readlink(path) == '/dev/null':
            path.unlink()
    for name in ['etc/live', 'etc/calamares']:
        remove(root, name)
    homes = [root / 'etc/skel', root / 'root'] + [p for p in (root / 'home').iterdir() if p.is_dir() and not p.is_symlink()]
    for home in homes:
        for suffix in ['Desktop/svent-install.desktop', '.config/autostart/svent-install-launcher.desktop', '.config/autostart/live-display.desktop', '.config/autostart/xfce4-screensaver.desktop', '.config/autostart/light-locker.desktop']:
            remove(root, str((home / suffix).relative_to(root)))
        if desktop in ('bspwm', 'none') and home == root / 'etc/skel':
            remove(root, str((home / '.config/xfce4').relative_to(root)))
    for name in ['root/.bash_profile', 'root/.xinitrc']:
        path = path_in(root, name)
        if path.is_file() and any(word in path.read_text() for word in ['exec startx', 'exec openbox-session']):
            path.unlink()
    remove(root, 'usr/sbin/policy-rc.d')
    remove(root, 'var/lib/svent-login/state.json')


def configure(root):
    metadata = json.loads(Path('/run/svent-installer/metadata.json').read_text())
    desktop = libcalamares.globalstorage.value('packagechooser_desktop')
    boot = libcalamares.globalstorage.value('packagechooser_boot')
    firmware = libcalamares.globalstorage.value('firmwareType')
    operations = libcalamares.globalstorage.value('packageOperations') or []
    packages, metas = selection(operations, metadata, desktop, boot, firmware)
    requested = list(packages)
    libcalamares.job.setprogress(0.05)
    target('apt-get', 'update', '--error-on=any')
    libcalamares.job.setprogress(0.15)
    if 'obsidian' in packages:
        packages.remove('obsidian')
        obsidian(root)
    target('apt-get', 'install', '-y', '--no-install-recommends', *packages)
    target('apt-mark', 'manual', *packages)
    libcalamares.job.setprogress(0.65)
    removals = list(LIVE_PACKAGES)
    if desktop in ('bspwm', 'none'):
        removals.extend(XFCE)
    if desktop == 'none':
        removals.extend(['lxdm', 'svent-login', 'xfce4-screensaver'])
    vm = metadata['virtualization']
    wanted_guest = set(vm['packages']) | (set(vm['desktop_packages']) if desktop != 'none' else set())
    removals.extend(p for p in ['open-vm-tools', 'open-vm-tools-desktop', 'qemu-guest-agent', 'spice-vdagent', 'virtualbox-guest-utils', 'virtualbox-guest-x11'] if p not in wanted_guest and p not in packages)
    removals = installed(root, removals)
    if removals:
        remove_packages(root, removals, requested)
    clean_live(root, desktop)
    if desktop == 'none':
        path = path_in(root, 'etc/lxdm/lxdm.conf')
        if path.is_file():
            settings = configparser.ConfigParser(interpolation=None, strict=False)
            settings.read(path)
            settings.remove_option('base', 'autologin')
            with path.open('w') as output:
                settings.write(output)
        remove(root, 'etc/systemd/system/display-manager.service')
        remove(root, 'etc/X11/default-display-manager')
        autologin = libcalamares.globalstorage.value('autologinUser')
        if autologin:
            if not re.fullmatch(r'[a-z_][a-z0-9_-]*', autologin):
                raise RuntimeError('The automatic login user is invalid.')
            path = path_in(root, 'etc/systemd/system/getty@tty1.service.d/20-svent-autologin.conf')
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('[Service]\nExecStart=\nExecStart=-/sbin/agetty --autologin ' + autologin + ' --noclear %I $TERM\n')
        target('systemctl', 'set-default', 'multi-user.target')
    else:
        path = path_in(root, 'etc/lxdm/lxdm.conf')
        settings = configparser.ConfigParser(interpolation=None, strict=False)
        settings.read(path)
        if not settings.has_section('base'):
            settings.add_section('base')
        settings.remove_option('base', 'autologin')
        autologin = libcalamares.globalstorage.value('autologinUser')
        if autologin:
            settings.set('base', 'autologin', autologin)
        settings.set('base', 'session', '/usr/bin/startxfce4' if desktop in ('xfce', 'both') else '/usr/bin/bspwm')
        with path.open('w') as output:
            settings.write(output)
        target('systemctl', 'enable', 'lxdm.service')
        target('systemctl', 'set-default', 'graphical.target')
    target('systemctl', 'enable', 'NetworkManager.service')
    guest_integration(root, vm, desktop)
    libcalamares.job.setprogress(0.8)
    for item in Path('/etc/NetworkManager/system-connections').glob('*'):
        if item.is_file() and not item.is_symlink():
            destination = path_in(root, 'etc/NetworkManager/system-connections/' + item.name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(item, destination)
            settings = configparser.ConfigParser(interpolation=None, strict=False)
            settings.read(destination)
            if settings.has_section('connection'):
                settings.set('connection', 'permissions', '')
                with destination.open('w') as output:
                    settings.write(output)
            destination.chmod(0o600)
    remove(root, 'etc/resolv.conf')
    (root / 'etc/resolv.conf').symlink_to('/run/NetworkManager/resolv.conf')
    target('update-initramfs', '-u', '-k', 'all')
    target('apt-get', 'check')
    target('apt-get', 'clean')
    libcalamares.job.setprogress(0.95)
    record = path_in(root, 'var/lib/svent/installation.json')
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(json.dumps({'desktop': desktop, 'bootloader': boot, 'packages': requested, 'complete_categories': metas, 'virtualization': vm}, indent=2) + '\n')
    log = Path('/var/log/svent-calamares.log')
    if log.is_file():
        saved_log = path_in(root, 'var/log/svent-installation.log')
        shutil.copyfile(log, saved_log)
        saved_log.chmod(0o600)
    libcalamares.job.setprogress(1.0)


def pretty_name():
    return {'validate': 'Check selected package dependencies', 'prepare': 'Prepare the installation target', 'configure': 'Install applications and configure SventOS'}[libcalamares.job.configuration['phase']]


def run():
    try:
        phase = libcalamares.job.configuration['phase']
        if phase == 'validate':
            validate_selection()
            return None
        root = target_root()
        if phase == 'prepare':
            prepare(root)
        else:
            configure(root)
    except Exception as error:
        return ('SventOS installation failed', str(error))
    return None
