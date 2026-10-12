import configparser
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch
import uuid
import shutil
import xml.etree.ElementTree as ET

import yaml


ROOT = Path(__file__).resolve().parents[1]
INCLUDE = ROOT / 'config/includes.chroot'


def load(path, name):
    from importlib.machinery import SourceFileLoader
    loader = SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.values = {}
        self.library = types.SimpleNamespace(
            globalstorage=types.SimpleNamespace(value=lambda key: self.values.get(key)),
            utils=types.SimpleNamespace(check_target_env_call=lambda args: self.calls.append(args)),
            job=types.SimpleNamespace(configuration={'phase': 'configure'}))
        self.patch = patch.dict(sys.modules, {'libcalamares': self.library})
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.module = load(INCLUDE / 'etc/calamares/modules/sventinstall/main.py', 'installer_test')
        self.launcher = load(INCLUDE / 'usr/local/bin/svent-install', 'catalog_test')
        self.metadata = {
            'mandatory': ['firefox-esr', 'sv-firefox-config', 'svent-core'],
            'base': ['tree', 'openvpn', 'obsidian'],
            'categories': {'sv-tools-web': ['sv-alpha', 'sv-beta']},
            'virtualization': {'kind': 'none', 'packages': [], 'desktop_packages': [], 'services': []}}

    def directory(self):
        path = ROOT / ('.installer-test-' + uuid.uuid4().hex)
        path.mkdir()
        for name in ['etc', 'etc/skel', 'home', 'root', 'usr/sbin', 'var/lib/dpkg']:
            (path / name).mkdir(parents=True, exist_ok=True)
        self.addCleanup(shutil.rmtree, path)
        return path

    def test_all_desktops_and_bootloader_choices(self):
        for desktop in ['xfce', 'bspwm', 'both', 'none']:
            for boot in ['grub', 'none']:
                with self.subTest(desktop=desktop, boot=boot):
                    packages, metas = self.module.selection([{'install': ['tree', 'sv-alpha']}], self.metadata, desktop, boot, 'bios')
                    self.assertIn('sv-firefox-config', packages)
                    self.assertEqual('svent-xfce' in packages, desktop in ('xfce', 'both'))
                    self.assertEqual('svent-bspwm' in packages, desktop in ('bspwm', 'both'))
                    self.assertEqual('grub-pc' in packages, boot == 'grub')
                    self.assertEqual(metas, [])

    def test_complete_category_preserves_metapackage(self):
        packages, metas = self.module.selection([{'install': ['sv-alpha', 'sv-beta']}], self.metadata, 'xfce', 'grub', 'efi')
        self.assertIn('sv-tools-web', packages)
        self.assertIn('grub-efi-amd64-signed', packages)
        self.assertEqual(metas, ['sv-tools-web'])
        with self.assertRaises(RuntimeError):
            self.module.selection([{'install': ['unexpected']}], self.metadata, 'xfce', 'grub', 'bios')

    def test_virtual_machine_packages_are_conditional(self):
        vm = self.launcher.virtualization('vmware', lambda name: True)
        self.metadata['virtualization'] = vm
        packages, _ = self.module.selection([], self.metadata, 'bspwm', 'grub', 'bios')
        self.assertIn('open-vm-tools-desktop', packages)
        packages, _ = self.module.selection([], self.metadata, 'none', 'none', 'bios')
        self.assertIn('open-vm-tools', packages)
        self.assertNotIn('open-vm-tools-desktop', packages)
        self.assertEqual(self.launcher.virtualization('none', lambda name: True)['packages'], [])
        self.assertEqual(self.launcher.virtualization('oracle', lambda name: False)['packages'], [])

    def test_virtual_machine_graphics_fallback_in_both_desktops(self):
        root = self.directory()
        home = root / 'home/test-user'
        (home / '.config/picom').mkdir(parents=True)
        (home / '.config/picom/picom.conf').write_text('backend = "glx";\n')
        vm = self.launcher.virtualization('vmware', lambda name: True)
        with patch.object(self.module.os, 'chown', create=True):
            self.module.guest_integration(root, vm, 'both')
        xml = ET.parse(home / '.config/xfce4/xfconf/xfce-perchannel-xml/xfwm4.xml')
        self.assertEqual(xml.find(".//property[@name='use_compositing']").get('value'), 'false')
        self.assertIn('backend = "xrender";', (home / '.config/picom/picom.conf').read_text())
        self.assertIn('vmware-user-suid-wrapper', (root / 'etc/X11/Xsession.d/95svent-guest').read_text())

    def test_target_dns_and_live_user_removal_before_new_user(self):
        root = self.directory()
        (root / 'etc/passwd').write_text('root:x:0:0::/root:/bin/bash\nsvent-live:x:1000:1000::/home/svent-live:/bin/zsh\n')
        (root / 'etc/group').write_text('svent-live:x:1000:\n')
        (root / 'home/svent-live').mkdir()
        resolver = root / 'resolver'
        resolver.write_text('nameserver 192.0.2.1\n')
        self.module.prepare(root, resolver)
        self.assertEqual((root / 'etc/resolv.conf').read_text(), resolver.read_text())
        self.assertFalse((root / 'home/svent-live').exists())
        self.assertIn(['env', 'DEBIAN_FRONTEND=noninteractive', 'NEEDRESTART_MODE=a', 'userdel', '--force', 'svent-live'], self.calls)
        self.assertTrue((root / 'usr/sbin/policy-rc.d').is_file())

    def test_cleanup_keeps_unrelated_files_and_removes_live_launcher(self):
        root = self.directory()
        home = root / 'home/new-user'
        (home / 'Desktop').mkdir(parents=True)
        (home / 'Desktop/svent-install.desktop').write_text('live')
        (home / 'Desktop/personal.txt').write_text('keep')
        (root / 'etc/sudoers.d').mkdir()
        (root / 'etc/sudoers.d/svent-live').write_text('live')
        self.module.clean_live(root, 'xfce')
        self.assertTrue((home / 'Desktop/personal.txt').exists())
        self.assertFalse((home / 'Desktop/svent-install.desktop').exists())
        self.assertFalse((root / 'etc/sudoers.d/svent-live').exists())
        with self.assertRaises(RuntimeError):
            self.module.remove(root, '../outside/file')

    def test_native_configuration_and_images(self):
        config = INCLUDE / 'etc/calamares'
        settings = yaml.safe_load((config / 'settings.conf').read_text())
        boot = yaml.safe_load((config / 'modules/bootloader.conf').read_text())
        users = yaml.safe_load((config / 'modules/users.conf').read_text())
        branding = yaml.safe_load((config / 'branding/svent/branding.desc').read_text())
        self.assertIn('sventinstall@prepare', settings['sequence'][1]['exec'])
        self.assertLess(settings['sequence'][1]['exec'].index('sventinstall@validate'), settings['sequence'][1]['exec'].index('partition'))
        self.assertLess(settings['sequence'][1]['exec'].index('sventinstall@prepare'), settings['sequence'][1]['exec'].index('users'))
        self.assertEqual(boot['efiBootLoaderVar'], 'packagechooser_boot')
        self.assertIn('svent-live', users['user']['forbidden_names'])
        self.assertEqual(branding['windowSize'], '960px,600px')
        self.assertTrue(branding['welcomeExpandingLogo'])
        self.assertIn('packagechooserq@boot', settings['sequence'][0]['show'])
        choice = yaml.safe_load((config / 'modules/boot.conf').read_text())
        self.assertEqual(choice['packageChoice'], 'grub')
        self.assertTrue((config / 'branding/svent' / choice['qmlFilename']).is_file())
        for name in ['welcome-image.png', 'installation-image.png', 'xfce-desktop.png', 'bspwm-desktop.png', 'check.png', 'partial.png', 'radio.png']:
            self.assertTrue((config / 'branding/svent' / name).read_bytes().startswith(b'\x89PNG\r\n\x1a\n'))

    def test_tool_rows_have_no_visible_package_child(self):
        for selected in (True, False):
            item = self.launcher.tool_item('sv-example', 'Example', 'Example description', selected)
            self.assertEqual(item['selected'], selected)
            self.assertNotIn('packages', item)
            self.assertEqual([child for child in item['subgroups'] if not child.get('hidden')], [])
            payload = item['subgroups'][0]
            self.assertTrue(payload['selected'])
            self.assertEqual(payload['packages'], ['sv-example'])
            self.assertEqual(payload['hidden'] and payload['selected'] and item['selected'], selected)

    def test_dependency_failure_stops_before_partitioning(self):
        root = self.directory()
        metadata_file = root / 'metadata.json'
        import json
        metadata_file.write_text(json.dumps(self.metadata))
        self.values.update({'packagechooser_desktop': 'xfce', 'packagechooser_boot': 'grub', 'firmwareType': 'bios', 'packageOperations': []})
        self.library.job.configuration['phase'] = 'validate'
        real_path = Path
        def mapped(name):
            return metadata_file if name == '/run/svent-installer/metadata.json' else real_path(name)
        with patch.object(self.module, 'Path', side_effect=mapped), patch.object(self.module.subprocess, 'run', return_value=types.SimpleNamespace(returncode=1, stderr='Dependency conflict')):
            error = self.module.run()
        self.assertIn('Dependency conflict', error[1])
        self.assertEqual(self.calls, [])

    def test_cleanup_cannot_remove_a_selected_tool(self):
        with patch.object(self.module.subprocess, 'run', return_value=types.SimpleNamespace(returncode=0, stdout='Remv sv-alpha [1.0]\n', stderr='')):
            with self.assertRaises(RuntimeError):
                self.module.remove_packages(Path('/target'), ['calamares'], ['sv-alpha'])
        self.assertEqual(self.calls, [])

    def test_dynamic_catalog_and_hidden_firefox(self):
        class Version:
            summary = 'Useful tool'
            dependencies = []
        class Package:
            candidate = Version()
        cache = {name: Package() for name in self.launcher.MANDATORY + ['svent-xfce', 'svent-bspwm', 'svent-login', 'svent-boot', 'grub-pc', 'grub-efi-amd64', 'efibootmgr'] + [p for p, _, _ in self.launcher.BASE if p != 'obsidian']}
        for category, _, _ in self.launcher.CATEGORIES:
            member = 'sv-' + category + '-future-tool'
            cache[member] = Package()
            dependency = types.SimpleNamespace(rawtype='Depends', or_dependencies=[types.SimpleNamespace(name=member)])
            cache['sv-tools-' + category] = types.SimpleNamespace(candidate=types.SimpleNamespace(dependencies=[dependency]))
        groups, metadata = self.launcher.generate(cache, {}, self.metadata['virtualization'])
        self.assertTrue(groups[0]['hidden'])
        self.assertNotIn('firefox-esr', str(groups[1:]))
        self.assertIn('sv-web-future-tool', metadata['categories']['sv-tools-web'])
        cache['sv-wireless-future-tool'] = Package()
        dependency = types.SimpleNamespace(rawtype='Depends', or_dependencies=[types.SimpleNamespace(name='sv-wireless-future-tool')])
        cache['sv-tools-wireless'] = types.SimpleNamespace(candidate=types.SimpleNamespace(dependencies=[dependency], summary='Wireless assessment tools.'))
        groups, metadata = self.launcher.generate(cache, {}, self.metadata['virtualization'])
        self.assertIn('sv-wireless-future-tool', metadata['categories']['sv-tools-wireless'])
        del cache['sv-web-future-tool']
        with self.assertRaises(RuntimeError):
            self.launcher.generate(cache, {}, self.metadata['virtualization'])


if __name__ == '__main__':
    unittest.main()
