# SventOS local builds and Armory downloads

Build on Debian 13 (trixie), amd64. `auto/config` configures live-build.
`build.sh` runs syntax checks, installer tests, `lb build`, and image checks.
The live system uses Debian repositories and the signed Svent APT repository
at `https://apt.zirov.net`, suite `rolling`, component `main`.

Calamares copies the live system and installs selected packages through APT.
Source checkouts are not packages: changing a recipe requires rebuilding its
`.deb`. Rebuilding the ISO alone does not update the public APT repository.

## Armory changes

`sv-armory-ad` 1.4.1 and `sv-armory-network` 1.2.2 accept complete HTTPS
downloads without comparing them against pinned sizes or hashes. ZIP members
are extracted by their configured paths. Network ZIP destination names,
including Wintun's DLL and license, are preserved. The AD SpoolSample source
archive is also downloaded without a pinned checksum comparison.

HTTPS certificate checks, secure paths, rejection of empty files, basic MZ
format checks for Windows binaries, retries, staging and upstream licenses
remain in place. Download failures include the underlying error.

`--check` checks presence and basic format, not authenticity or cryptographic
integrity. Valid existing files are reused; these changes do not automatically
update the collection to the latest upstream release. Versioned URLs remain
versioned URLs.

Each manager records the hash of the file actually installed solely for safe
removal. The existing removal script preserves files modified by the user.
These local hashes do not validate or block downloads. APT signatures,
repository recovery checks and image checksums are separate and unchanged.

## Build both packages without publishing

From the directory containing the source repositories:

```bash
sudo apt-get update
sudo apt-get install -y build-essential dpkg-dev debhelper python3 mono-mcs \
  libmono-system-data4.0-cil libmono-system-xml-linq4.0-cil \
  libmono-microsoft-csharp4.0-cil ca-certificates
(
set -eu
cd svent-active-directory/tools/sv-armory-ad
chmod +x debian/rules debian/postinst debian/postrm
dpkg-checkbuilddeps
python3 -m unittest discover -s tests -v
dpkg-buildpackage -b -us -uc
)
(
set -eu
cd svent-network/tools/sv-armory-network
chmod +x debian/rules debian/postinst debian/postrm
dpkg-checkbuilddeps
python3 -m unittest discover -s tests -v
dpkg-buildpackage -b -us -uc
)
```

The expected artifacts are:

- `svent-active-directory/tools/sv-armory-ad_1.4.1_all.deb`
- `svent-network/tools/sv-armory-network_1.2.2_all.deb`

The build downloads and compiles SpoolSample. It does not execute the Windows
tools. Package configuration downloads the actual collections.

## Test before publishing

Use a disposable Debian 13 test VM with the trusted Svent APT source enabled.
Transfer both `.deb` files and install them from their directory:

```bash
sudo apt-get update
sudo apt-get install ./sv-armory-ad_1.4.1_all.deb ./sv-armory-network_1.2.2_all.deb
armory-ad --check
armory-network --check
```

A successful mock test suite is not a substitute for this network and package
configuration test. A broken URL or failed connection can still abort package
configuration. Completing APT manually does not finish Calamares' later jobs.

## Build an ISO with local packages

This allows an ISO test before publishing anything. From the directory
containing all source repositories:

```bash
mkdir -p svent-iso/config/packages.chroot
cp svent-active-directory/tools/sv-armory-ad_1.4.1_all.deb \
  svent-network/tools/sv-armory-network_1.2.2_all.deb \
  svent-iso/config/packages.chroot/
sudo apt-get install -y live-build debootstrap xorriso squashfs-tools \
  python3 python3-yaml grub-common grub-pc-bin grub-efi-amd64-bin mtools dosfstools
cd svent-iso
sudo bash build.sh
```

live-build configures these packages in the live system, downloading the
collections during the image build. This adds time, network use and disk use.
Calamares inherits the newer packages when copying the live filesystem. A
normal APT install does not downgrade them to older repository versions.
Do not place multiple versions of the same package in `config/packages.chroot`.
APT may prefer a future higher version, whose behavior needs review.

If both corrected packages have already been published, the regular online
installer can obtain them from APT without local `.deb` files in the image.

`build.sh` requires at least 8 GiB free; the collections and installer package
selections can need substantially more. Outputs are
`sventos-live-amd64.hybrid.iso` and its `.sha256`. Test boot and a complete
installation in a fresh VM before distributing the image.

## Publishing from a replacement build VM

Follow `svent-bin/SVENT-MAINTENANCE.md` for the repository recovery workflow.
Use Debian 13, amd64, and keep the original signing identity. A new public
key cannot replace the existing secret signing key without a key migration.
Keep signing keys and R2 credentials outside source repositories.

Configure rclone's `r2` S3 remote for the existing bucket `svent-apt`, with
Cloudflare as provider, region `auto`, the account's R2 S3 endpoint and
bucket-scoped Object Read & Write credentials. Use interactive prompts for
secrets. Do not store credential values in shell history or source files.

Clone the trusted `pkgs` configuration and public keyring. Configure
`SVENT_PKGS`, `SVENT_R2`, `SVENT_REPOS`, and `SVENT_BACKUPS`; the backup directory
must be separate from the package repository. Import the original secret key
and verify its fingerprint against a trusted record and `conf/distributions`.

Run `python3 svent-bin/svent-pkg.py prepare` before importing any changed
packages. It copies the full remote repository into a retained local snapshot,
checks the signed indices and active packages, reconstructs a local database
and makes a complete backup. It does not publish. It requires enough space
for recovery and backups. Preserve its printed snapshot path.

After package and ISO tests succeed, import only the two changed `.deb` files
with `reprepro includedeb rolling`, export and check the repository. Do not
rebuild unchanged metapackages. Do not overwrite an already published version.
Retain the tested artifacts rather than rebuilding the same version.

Before publication, compare the remote `InRelease` with the retained recovery
snapshot. If it changed, stop and reconcile the repository before publishing.
Do not let another publisher run concurrently.

Run `python3 svent-bin/svent-pkg.py publish` only as the final explicit step.
The inspected publisher checks remote package coverage, verifies local package
hashes, makes a full backup and copies the pool before the indices. It uses
`rclone copy`, not deletion or synchronization. These checks reduce risk but
do not make publication atomic or protect against every concurrent change.

Do not delete the remote bucket, remove the existing repository, use
`rclone sync`, or bypass missing-package safeguards. Retain the recovery
snapshot, backups and the original signing key outside disposable storage.

## Validation status

The Windows checks cover mocked downloads, changed upstream payloads, ZIP
members, executable format rejection, safe paths and staged failure behavior.
The real Debian package builds, upstream downloads, live-build image and full
Calamares installation still require validation on Linux.
