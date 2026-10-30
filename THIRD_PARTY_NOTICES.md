# Third-party notices

## Vendored VoxNode code

The files `src/xiaoai_pc/vendor/voxnode/account.py`, `qrlogin.py`, and `mina.py`
are adapted from [Almmor/VoxNode](https://github.com/Almmor/VoxNode), commit
`19ec9a0172e90eda1aee09cd338a4a3c2c4d5750`.

Copyright (c) 2026 VoxNode contributors. Licensed under MIT.
The full original license is retained in [licenses/VoxNode-MIT.txt](licenses/VoxNode-MIT.txt).

VoxNode credits the MIT-licensed projects MiService (Copyright (c) 2021-2026 Yonsm)
and xiaomusic (Copyright (c) 2023 涵曦) for these protocol implementations.
Their full copyright and MIT permission notices are retained verbatim in
[licenses/VoxNode-UPSTREAM-NOTICES.md](licenses/VoxNode-UPSTREAM-NOTICES.md).
They are provenance references, not installed runtime dependencies.

Local modifications: disable plaintext token persistence; redact response data from
errors; preserve passToken during a bounded service-token refresh; check HTTP status;
validate JSON shapes; propagate conversation/network errors; validate inner TTS status;
handle malformed conversation items. See docs/RESEARCH.md and the repository diff.

The archived upstream notices also discuss software we do **not** ship (including
PyQt6, Android components and mss). Their presence in the archival file does
not mean they are dependencies of this project. In particular, the upstream PyQt
dynamic-linking statement is not relied on here; consult the vendor's GPL/commercial
licensing terms if adding PyQt in the future.

## Installed and bundled components

| Component | License | Role |
|---|---|---|
| requests | Apache-2.0 | HTTPS client |
| urllib3 | MIT | HTTP transport |
| charset-normalizer | MIT | Encoding detection |
| idna | BSD-3-Clause | Domain encoding |
| certifi | MPL-2.0 | CA certificate bundle |
| pycaw | MIT | Windows Core Audio interfaces and device access |
| comtypes | MIT | COM interop used by pycaw |
| psutil | BSD-3-Clause | Required by pycaw; no system-monitoring feature is exposed |
| pystray | LGPL-3.0-or-later | Windows system tray; Copyright 2016–2022 Moses Palmér |
| Pillow | MIT-CMU and included third-party notices | Icon and QR image display |
| six | MIT | pystray compatibility dependency |
| Tcl/Tk | BSD-style terms in the Python license and Tk license.terms | Settings window |
| Python | PSF License and included third-party notices | Embedded runtime in exe |
| PyInstaller | GPL-2.0-or-later with distribution exception | Build tool and bootloader |

The build script copies actual installed license texts, the Python license, and
PyInstaller copyright/exception notices into the portable distribution under
`licenses/runtime/`; these are also included as exe resources. No certificate
verification is disabled or CA bundle modified.

The dependency versions tested are recorded in requirements-runtime.lock and
requirements-build.lock. Public binary release should retain this notice and the
complete bundled license directory. This package is an unsigned portable
test build, not an installer or a device-validated production release.

## pystray source and relinking

This application uses pystray 0.19.5, covered by LGPL-3.0-or-later. Both the full
GNU GPL and GNU LGPL texts are included under `licenses/runtime/pystray/`.
The portable package includes the unmodified, complete upstream source archive
and corresponding application source/build scripts under `source/`. The build
checks that installed pystray Python sources match the accompanying archive.

Modification of the library portions and reverse engineering for debugging such
modifications are permitted. The accompanying application code may be used,
modified, rebuilt, recombined and redistributed for this purpose; third-party
licenses remain applicable. No signing key, activation or installation secret is
required to run a rebuilt executable. See [rebuild instructions](docs/DESKTOP.md#依赖源码和重建),
including `scripts/build.py --pystray-source` for a modified corresponding archive.
Upstream terms: [pystray LGPL](https://github.com/moses-palmer/pystray/blob/v0.19.5/COPYING.LGPL).
