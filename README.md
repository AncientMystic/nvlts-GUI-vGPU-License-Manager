# ◈ vGPU License Manager — Glass GUI for NVIDIA Local Trusted Store (`nvlts`)

A polished, cross-platform **Python + tkinter** desktop app that wraps the
[`nvlts` — NVIDIA Local Trusted Store](https://git.collinwebdesigns.de/vgpu/nvlts)
utility and turns its command-line workflow into a friendly point-and-click experience.

![platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-blue)
![python](https://img.shields.io/badge/python-3.8%2B-green)
![deps](https://img.shields.io/badge/dependencies-stdlib%20only%20(tkinter)-brightgreen)
![license-type](https://img.shields.io/badge/license-Permanent%20(3000--12--31)-76B900)

> **Scope note:** this project covers only the **“(You are here)”** path from the
> upstream guide — local trusted-store credentials via `nvlts`. The
> FastAPI-DLS / `gridd-unlock-patcher` / patched-driver route is intentionally
> out of scope and not implemented here.

---

## Table of contents

- [What this is](#what-this-is)
- [What it does (features)](#what-it-does-features)
- [Quick start](#quick-start)
- [License editions](#license-editions)
- [How permanent licensing works](#how-permanent-licensing-works)
- [How status checking works](#how-status-checking-works)
- [Project layout](#project-layout)
- [README vs code — findings baked into this tool](#readme-vs-code--findings-baked-into-this-tool)
- [Troubleshooting](#troubleshooting)
- [Thank you](#thank-you)
- [Extended thanks](#extended-thanks)
- [Further reading](#further-reading)
- [Disclaimer](#disclaimer)

---

## What this is

`nvlts` generates a **local** trusted credential with a valid vGPU license —
no internet connection, no DLS server, no patched DLLs, WHQL signatures intact.
The trade-off is **environmental fingerprinting**: the credential is bound to the
guest's NIC MAC addresses and machine ID, so NIC changes invalidate it.

This GUI (`vgpu_license_manager.py`) sits on top of the `nvlts` binary and:

1. Showcases every license edition with its `ProductName` / `FeatureName` /
   `FeatureVersion` so you pick the right one instead of guessing JSON files.
2. Checks the **current** vGPU license state via `nvidia-smi -q`, using the
   correct OS-specific invocation automatically.
3. Issues a **permanent** license with one click (`nvlts -g -c … [-r]`).
4. Adds safety rails the raw CLI lacks: admin checks, trusted-store directory
   pre-creation, config validation, backups, decrypt preview, and a live log of
   every exact command it runs.

---

## What it does (features)

| # | Feature | Details |
|---|---------|---------|
| 1 | 🎴 License showcase | All 10 editions (5 current + 5 legacy) with product, feature, version, description, and a ★ Recommended badge on vWS. Values load from your on-disk `configs/*.json` when present, otherwise from the embedded catalog. |
| 2 | 🔍 License status check | Runs `nvidia-smi -q`, filters lines containing `License` (same as `grep` / `Select-String`), and interprets Licensed vs Unlicensed with an expiry hint. |
| 3 | ★ Permanent license | Builds a config from the GUI fields, pre-creates store directories, then runs `nvlts -g -c <temp-config> [-r] [-debug]`. Expiry is always `3000-12-31` (hard-coded in `nvlts`). |
| 4 | 🖥️ OS-aware | Auto-detects Windows vs Linux for `nvidia-smi` paths, trusted-store paths (`TrustedStorage` / `/var/lib/nvidia/vGPULicensing`), sidecar files (`nvlts.lic`, `ClientConfigToken`), and restart method (`NVDisplay.ContainerLocalSystem` vs `nvidia-gridd`). |
| 5 | 🔧 Driver helpers | `Auto-detect guest` fills `GuestDriverVersion` from `nvidia-smi --query-gpu`. Host version stays editable. |
| 6 | 🔓 Decrypt preview | `nvlts -d -f <temp>` with a 3000-char preview of the (not-strictly-JSON) store content. |
| 7 | 💾 Backup | Timestamped `trustedstore_backup_*` folder with the encrypted store, tag, `nvlts.lic`, and client token. |
| 8 | 🫆 Fingerprint | Hostname, primary MAC, machine ID (registry `MachineGuid` / `product_uuid`+`machine-id`), IPs — plus the NIC-change warning. |
| 9 | 📜 Operation log | Every exact shell command plus stdout/stderr, timestamped. Nothing hidden. |
| 10 | 🪟 Glassmorphism UI | Frosted-glass cards on a deep gradient with ambient glow blobs, pill badges, and a neon-green accent. Still 100% stdlib `tkinter`. |

---

## Quick start

**Prerequisites**

- Python 3.8+ with `tkinter`
  (`sudo apt install python3-tk` on Debian/Ubuntu if missing; bundled on Windows).
- NVIDIA vGPU **guest driver** installed (`nvidia-smi` must exist).
- The `nvlts` binary — already bundled under `source/` in this repo
  (`source/nvlts_1.0.3_windows_amd64/nvlts.exe`, Linux tarball alongside).
  The app auto-detects it; you can also `Browse…` to any copy or put one on `PATH`
  (`/opt/nvlts/nvlts` is also checked).
- **Run elevated**: *Run as Administrator* (Windows) or `sudo` (Linux) —
  writing the trusted store and restarting the display service require it.

**Launch**

```powershell
# Windows (elevated PowerShell)
python .\vgpu_license_manager.py
```

```bash
# Linux (root for real licensing work)
sudo python3 vgpu_license_manager.py
```

**Typical flow**

1. Launch elevated → tool auto-finds `nvlts`, `configs/`, and `nvidia-smi`.
2. `✔ Check license status` — confirm `Unlicensed` (or check expiry).
3. Pick an edition (most users want **vWS**), verify driver versions.
4. `★ Apply PERMANENT license` (keep `Auto-restart service (-r)` on).
5. `✔ Check license status` again — expect `Licensed (Expiry: Permanent)`.
6. Leave your NICs alone afterwards (see warning below).

> ⚠️ **Do NOT change, add, or remove NICs afterwards** — not even a VPN TAP
> adapter. It invalidates the credential and you must re-apply. (Whether
> WireGuard's WinTUN L3 device affects this is still unknown upstream.)

---

## License editions

| Edition (GUI label) | `ProductName` | `FeatureName` | Ver | File | For |
|---|---|---|---|---|---|
| **vWS (Recommended)** ★ | NVIDIA RTX Virtual Workstation | Quadro-Virtual-DWS | 5.0 | `vWS.json` | Full workstation: CUDA, OpenGL, ISV apps. What most homelab/vGPU users want. |
| vPC | NVIDIA Virtual PC | GRID-Virtual-PC | 2.0 | `vPC.json` | Standard virtual desktops. |
| vApps | NVIDIA Virtual Applications | GRID-Virtual-Apps | 3.0 | `vApps.json` | App remoting / RDSH session hosts. |
| vCS | NVIDIA Virtual Compute Server | NVIDIA-vComputeServer | 9.0 | `vCS.json` | Headless compute (AI/ML, HPC). No graphics. |
| vGaming | NVIDIA vGaming | GRID-vGaming | 8.0 | `vGaming.json` | Cloud-gaming profiles. |
| Legacy Quadro vDWS | Quadro Virtual Data Center Workstation | Quadro-Virtual-DWS | 5.0 | `Legacy_Quadro_vDWS.json` | Older guest drivers (pre-Ampere era naming). |
| Legacy GRID vWS | GRID Virtual Workstation | GRID-Virtual-WS | 2.0 | `Legacy_GRID_vWS.json` | Old GRID drivers. |
| Legacy GRID vPC | GRID Virtual PC | GRID-Virtual-PC | 2.0 | `Legacy_GRID_vPC.json` | Old GRID drivers. |
| Legacy GRID vApps | GRID Virtual Applications | GRID-Virtual-Apps | 3.0 | `Legacy_GRID_vApps.json` | Old GRID drivers. |
| Legacy GRID vGaming | GRID vGaming | GRID-vGaming | 8.0 | `Legacy_GRID_vGaming.json` | Old GRID drivers. |

Only **`ProductName` + `FeatureName` must match** the driver; other fields should
still be filled sensibly (upstream advises against leaving them empty).

---

## How permanent licensing works

The app reproduces the documented manual flow:

```shell
nvlts -g -r -c configs/vWS.json   # "NVIDIA RTX Virtual Workstation"
```

except it **generates the config from the GUI** (so driver versions are always
fresh) and runs it as:

```shell
nvlts -g -c <temp-config.json> [-r] [-debug]
```

What `nvlts -g` does under the hood (release build, `schema_node_locked.go`):

1. Writes an **empty** node-locked file —
   `…/vGPU Licensing/License/nvlts.lic` (Win) /
   `/etc/nvidia/vGPULicense/nvlts.lic` (Linux).
2. Snapshots the environment (MACs, IPs, hostname, guest/host driver, OS,
   GPU list, machine ID, hypervisor, CPU sockets/cores).
3. Builds the trusted-store lease with **`expires = 3000-12-31T23:59:59`** —
   hence *permanent*; there is no expiry option to set.
4. AES-GCM-encrypts it into the trusted store
   (`TrustedStorage/NGUgNGMgNTMgMzEgMmUgMzA` + `DataStore.bin`).
5. With `-r`, restarts `NVDisplay.ContainerLocalSystem` (Win) /
   `nvidia-gridd` (Linux) so the driver picks it up.

---

## How status checking works

The app detects the OS once (`platform.system()`) and then runs the same
logical pipeline on both:

- Linux: `nvidia-smi -q | grep "License"`
- Windows: `& 'nvidia-smi' -q | Select-String "License"`

Filtering is done in Python (line contains `License`), so output is identical
in shape on both OSes, with `nvidia-smi` resolved from `PATH` plus well-known
locations (`C:\Windows\System32\nvidia-smi.exe`, `/usr/bin/nvidia-smi`, …).

---

## Project layout

```text
vGPU-manager/
├── vgpu_license_manager.py   # ← the app (this README's subject)
├── README.md                 # ← you are here
└── source/
    ├── nvlts-v1.0.3/                     # upstream Go source (reference)
    │   ├── configs/                      # the 10 edition JSONs
    │   ├── main.go / schema*.go / utils_*.go / …
    │   └── scripts/install.sh            # upstream Linux installer
    ├── nvlts-v1.0.3.zip                  # source archive
    ├── nvlts_1.0.3_windows_amd64/        # Windows release (nvlts.exe)
    ├── nvlts_1.0.3_windows_amd64.zip
    └── nvlts_1.0.3_linux_amd64.tar.gz    # Linux release
```

---

## README vs code — findings baked into this tool

Audited against `nvlts` v1.0.3 source; the GUI compensates for each item:

1. **Release builds are the permanent/node-locked variant.** `.goreleaser.yml`
   builds with plain `go build` (no `-tags net`), activating
   `schema_node_locked.go` (`//go:build !net`). The JWT/`2099` variant in
   `schema_net.go` is not in the releases and the README never mentions tags.
2. **`generate()` forgets `MkdirAll`.** `encrypt()` creates the store dir,
   `generate()` doesn't — fresh machines fail. The GUI pre-creates it.
3. **Default `-c config.json` ships nowhere.** Only `configs/*.json` exist;
   an explicit `-c` is mandatory. The GUI always passes one.
4. **`-r` is OS-specific** though documented Windows-only: `systemctl restart
   nvidia-gridd` on Linux. Handled per-OS.
5. **Expiry is unconditional.** `Config` JSON has no expiry field, so the
   `3000-12-31` permanent date always wins. Shown as a badge, not an option.
6. **Fingerprint fragility.** MAC list + machine ID (+ IPs/hostname/GPU/CPU).
   The GUI surfaces the fingerprint and warns before you touch NICs.

---

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `nvlts: NOT FOUND` | Unzip a release under `source/` or `Browse…` to `nvlts(.exe)`; or install to `/opt/nvlts/nvlts` / `PATH`. |
| `nvidia-smi: NOT FOUND` | Guest driver not installed (or not on `PATH`). Install the vGPU guest driver first. |
| Write/restart failures | Not elevated — relaunch as Administrator / root. |
| `Licensed` but apps still limited | Wrong edition picked (`ProductName`/`FeatureName` mismatch) — try the Legacy variant matching your driver era, or vWS. |
| License dies after network change | Expected: new/removed NIC (incl. VPN TAP) changes the fingerprint → re-apply. |
| `No lines containing 'License'` | Driver too old or `nvidia-smi -q` output differs — check full `nvidia-smi -q` manually. |

---

## Thank you

Huge thank you to the developer of the upstream project that makes all of this
possible:

> **CoiaPrant ([@rbqvq](https://t.me/rbqvq))** — author of
> **[NVIDIA Local Trusted Store (`nvlts`)](https://git.collinwebdesigns.de/vgpu/nvlts)**:
> a local, offline, WHQL-signature-preserving way to license vGPU guests that
> “just works” where DLS patching used to be mandatory. If this GUI helped you,
> the credit belongs upstream — consider reporting bugs with your OS version,
> MAC, driver versions, and GPU model so the tool keeps improving.
>
> - Project: <https://git.collinwebdesigns.de/vgpu/nvlts>
> - Telegram (recommended, EN/简中): [@rbqvq](https://t.me/rbqvq)
> - Email (EN/简中): [`coiaprant@gmail.com`](mailto:coiaprant@gmail.com)
>   (if no reply, your mail may have hit Gmail spam — retry from another address)
> - Discord: vGPU channel `@CoiaPrant` ([#thDa7CSY](https://discord.gg/thDa7CSY))
>   — checked infrequently; prefer Telegram/email.

---

## Extended thanks

The upstream README credits the wider vGPU community — those thanks are
repeated here because this GUI stands on the same shoulders:

- [vgpu-unlock-rs](https://github.com/mbilker/vgpu_unlock-rs) — unlock groundwork the community builds on.
- [FastAPI-DLS](https://git.collinwebdesigns.de/oscar.krause/fastapi-dls) — the DLS-compatible path this tool deliberately avoids needing.
- [gridd-unlock-patcher](https://git.collinwebdesigns.de/vgpu/gridd-unlock-patcher) — NLS root-CA replacement approach.
- [patched-nvidia-grid-drivers](https://github.com/acgdaily/patched-nvidia-grid-drivers) — certificate-check-skipped drivers.
- [Foxi Net Disk](https://alist.homelabproject.cc/foxipan) — driver mirror referenced upstream.
- The vGPU community testers and bug reporters — fingerprint quirks (NIC/MAC/machine-id behavior) were characterized by real users.

---

## Further reading

Guides and unlock projects linked from the upstream README, worth knowing even
though this tool doesn't use them:

- [NVIDIA vGPU Guide (Proxmox)](https://gitlab.com/polloloco/vgpu-proxmox) — host-driver install walkthrough.
- [vgpu_unlock](https://github.com/DualCoder/vgpu_unlock) — consumer-GPU vGPU unlock.
- [vGPU_Unlock Wiki](https://docs.google.com/document/d/1pzrWJ9h-zANCtyqRgS7Vzla0Y8Ea2-5z2HEi4X75d2Q) — community guide for `vgpu_unlock`.
- [Proxmox 8 vGPU in VMs and LXC](https://medium.com/@dionisievldulrincz/proxmox-8-vgpu-in-vms-and-lxc-containers-4146400207a3) — merged-driver setup.
- [Proxmox All-In-One Installer](https://wvthoog.nl/proxmox-vgpu-v3/) (`proxmox-installer.sh`).

---

## Disclaimer

- For **lab / educational use**; respect NVIDIA's licensing terms for your
  deployment. This GUI only drives the upstream `nvlts` binary — it performs
  no cracking, patching, or signature modification itself.
- Not affiliated with NVIDIA Corporation, CoiaPrant, or any linked project.
- The `nvlts` binary/source under `source/` remain under their **upstream
  LICENSE**; this wrapper script is provided as-is, without warranty.
