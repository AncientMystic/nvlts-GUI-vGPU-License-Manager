English | [简体中文](README_zh-CN.md)

# NVIDIA Local Trusted Store (nvlts)

A utility for the NVIDIA Local Trusted Store

> [!note]
> It has only been tested on 18.x and 19.x, other versions have not been tested, but should work

**Further Reading**

- [NVIDIA vGPU Guide](https://gitlab.com/polloloco/vgpu-proxmox) - This document serves as a guide to install NVIDIA vGPU host drivers on the latest Proxmox VE version
- [vgpu_unlock](https://github.com/DualCoder/vgpu_unlock) - Unlock vGPU functionality for consumer-grade Nvidia GPUs.
- [vGPU_Unlock Wiki](https://docs.google.com/document/d/1pzrWJ9h-zANCtyqRgS7Vzla0Y8Ea2-5z2HEi4X75d2Q) - Guide for `vgpu_unlock`
- [Proxmox 8 vGPU in VMs and LXC Containers](https://medium.com/@dionisievldulrincz/proxmox-8-vgpu-in-vms-and-lxc-containers-4146400207a3) - Install _Merged Drivers_ for using in Proxmox VMs and LXCs
- [Proxmox All-In-One Installer Script](https://wvthoog.nl/proxmox-vgpu-v3/) - Also known as `proxmox-installer.sh`

**Official Links**

- https://git.collinwebdesigns.de/vgpu/nvlts (Private Git)

## Background

NVIDIA vGPU Software required a License for unlock all functions.

After vGPU 18.x release, it verifies that NLS (NVIDIA License System, include Cloud License Service "CLS" and Delegated License Service "DLS") service instance certificate is issued by NVIDIA (NLS ROOT CA)

This makes it necessary to patch the driver.

> If you find it troublesome, you can use 18.x on Host and 17.x on Guest. \
> After my test, it works.

Here are three ways to solve:

- [FastAPI-DLS](https://git.collinwebdesigns.de/oscar.krause/fastapi-dls) with [gridd-unlock-patcher](https://git.collinwebdesigns.de/vgpu/gridd-unlock-patcher) (Replace NLS ROOT CA)

  It works for all guests, but requires manual driver patching after guest driver update

  You need use [gridd-unlock-patcher](https://git.collinwebdesigns.de/vgpu/gridd-unlock-patcher) to replace NLS ROOT CA

- [FastAPI-DLS](https://git.collinwebdesigns.de/oscar.krause/fastapi-dls) with [patched-nvidia-grid-driver](https://github.com/acgdaily/patched-nvidia-grid-drivers) (Skip certificate check)

  It works for all guests, but requires manual driver patching after guest driver update

  Of course, you only need to download the driver to replace

  See my blog (zh_CN) to learn more, [Link](https://blog.gov.cooking/archives/vgpu-remove-nvidia-vgpu-18-certificate-check.html)

- **(You at here)** [NVIDIA Local Trusted Store (nvlts)](https://git.collinwebdesigns.de/vgpu/nvlts) (Generate a local trusted credential with a valid license)

  It works for all guests, and this tool is local and does not require an Internet connection, but a network card (with an IP address?) is required.

  You don't need to patch DLL and setup DLS instance and keep WHQL signatures intact

  But method strongly relies on environmental fingerprinting, and currently seems to only check NIC MAC addresses and machine id

  > Whether you modify the VM NIC, insert or remove a NIC or even install an OpenVPN TAP NIC. It will invalidate the credentials.

  > I'm not sure if this affects the WinTun L3 device used by WireGuard

## Install

- Linux Scripts

```shell
bash <(curl -sSL "https://git.collinwebdesigns.de/vgpu/nvlts/-/raw/master/scripts/install.sh") # Install
bash <(curl -sSL "https://git.collinwebdesigns.de/vgpu/nvlts/-/raw/master/scripts/update.sh") # Upgrade
bash <(curl -sSL "https://git.collinwebdesigns.de/vgpu/nvlts/-/raw/master/scripts/uninstall.sh") # Uninstall
```

- Pre-Built binary

  Download it from [Releases](https://git.collinwebdesigns.de/vgpu/nvlts/-/releases)

- Install with `go install` (For Golang developers)

```shell
go install git.collinwebdesigns.de/vgpu/nvlts@latest
```

- Build by yourself

  See `Build` section

## Usage

```shell
  -c string
        Generate config (default "config.json")
  -d    Decrypt NVIDIA Local Trusted Store to file
  -debug
        Show debug logs
  -e    Encrypt file to NVIDIA Local Trusted Store
  -f string
        File to encrypt / save decrypted (default "trusted_store.json")
  -g    Generate license to NVIDIA Local Trusted Store
  -h    Show help
  -r    Auto restart NVDisplay.ContainerLocalSystem service
```

- Decrypt from NVIDIA Local Trusted Store to file (Default: `trusted_store.json`)

```shell
nvlts -d
```

> The decrypted content is not strictly JSON. NVIDIA does not use the json library to process it. It uses `snprintf` to concatenate strings.

- Encrypt file (Default: `trusted_store.json`) to NVIDIA Local Trusted Store and Restart Service

```shell
nvlts -e -r
```

- Generate (both empty NodeLockedLicense and NVIDIA Local Trusted Store) with config (Default: `config.json`) and Restart Service

```shell
nvlts -g -r
```

You can find example config in `configs` directory

> Only `ProductName` and `FeatureName` must match, other items can be filled in freely, but it is best not to leave them empty (it may stop working)

## Bug Report

Provide your system infomation (OS version, MAC address, Host/Guest driver version and GPU model) and NVIDIA Local Trusted Store file

- (Recommend) Telegram [@rbqvq](https://t.me/rbqvq) (English / Simplified Chinese)

- Send email to [`coiaprant@gmail.com`](mailto:coiaprant@gmail.com) (English / Simplified Chinese)

> If there is no response for a long time, it means that your email has been rejected by Gmail or classified as spam. You can consider changing your email address and resend it.

- On [Discord vGPU Channel `@CoiaPrant`](https://discord.gg/thDa7CSY) (English for Channel/Group, English / Simplified Chinese for DM/PM)

> I don't check Discord often, it depends on Google's message push (FCM), if there is no response for a long time, please use the Email method instead

## Build

Required minimal Go version: `go 1.23.0`

> Of course you can do foward compatibility yourself, nothing complicated

- Release

```shell
go build -ldflags="-s -w" -trimpath .
```

- Debug

```shell
go build .
```

## Credits

Thanks to vGPU community and all who uses this project and report bugs.
Special thanks to:

- [vgpu-unlock-rs](https://github.com/mbilker/vgpu_unlock-rs)
- [FastAPI-DLS](https://git.collinwebdesigns.de/oscar.krause/fastapi-dls)
- [gridd-unlock-patcher](https://git.collinwebdesigns.de/vgpu/gridd-unlock-patcher)
- [patched-nvidia-grid-driver](https://github.com/acgdaily/patched-nvidia-grid-drivers)
- [Foxi Net Disk - You can find driver here](https://alist.homelabproject.cc/foxipan)
