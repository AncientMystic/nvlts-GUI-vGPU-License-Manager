[English](README.md) | 简体中文

# NVIDIA Local Trusted Store / 本地可信存储 (nvlts)

一个用于 NVIDIA 本地可信存储的工具

> [!note]
> 仅在 18.x 和 19.x 版本上测试过, 其他版本未测试, 但应该可用

**延伸阅读**

- [NVIDIA vGPU 指南](https://gitlab.com/polloloco/vgpu-proxmox) - 本文档是关于在最新 Proxmox VE 版本上安装 NVIDIA vGPU 主机驱动程序的指南
- [vgpu_unlock](https://github.com/DualCoder/vgpu_unlock) - 为消费级 Nvidia GPU 解锁 vGPU 功能
- [vGPU_Unlock Wiki](https://docs.google.com/document/d/1pzrWJ9h-zANCtyqRgS7Vzla0Y8Ea2-5z2HEi4X75d2Q) - `vgpu_unlock` 指南
- [Proxmox 8 vGPU 在 VM 和 LXC 容器中](https://medium.com/@dionisievldulrincz/proxmox-8-vgpu-in-vms-and-lxc-containers-4146400207a3) - 安装 _合并驱动程序_ 以在 Proxmox VM 和 LXC 中使用
- [Proxmox 一体化安装脚本](https://wvthoog.nl/proxmox-vgpu-v3/) - 也称为 `proxmox-installer.sh`

**官方链接**

- https://git.collinwebdesigns.de/vgpu/nvlts (私有 Git)

## 前情提要

NVIDIA vGPU 软件需要授权许可证才能解锁所有功能

在 vGPU 18.x 版本后, 它会验证 NLS (NVIDIA 许可系统, 包括云许可服务 "CLS" 和委托许可服务 "DLS") 服务实例证书是否由 NVIDIA (NLS ROOT CA) 签发

这使我们必须修改驱动程序

> 如果觉得麻烦, 可以在主机上使用 18.x, 在虚拟机上使用 17.x \
> 经过我的测试, 它工作

这里有三种解决方法:

- [FastAPI-DLS](https://git.collinwebdesigns.de/oscar.krause/fastapi-dls) 搭配 [gridd-unlock-patcher](https://git.collinwebdesigns.de/vgpu/gridd-unlock-patcher) (替换 NLS ROOT CA)

  它适用于所有虚拟机, 但在虚拟机中的驱动程序更新后需要手动破解

  您需要使用 [gridd-unlock-patcher](https://git.collinwebdesigns.de/vgpu/gridd-unlock-patcher) 来替换 NLS ROOT CA

- [FastAPI-DLS](https://git.collinwebdesigns.de/oscar.krause/fastapi-dls) 搭配 [patched-nvidia-grid-driver](https://github.com/acgdaily/patched-nvidia-grid-drivers) (跳过证书检查)

  它适用于所有虚拟机, 但在虚拟机中的驱动程序更新后需要手动破解

  当然, 您只需要下载驱动程序并替换文件

  请参阅 我的 Blog 了解更多信息, [链接](https://blog.gov.cooking/archives/vgpu-remove-nvidia-vgpu-18-certificate-check.html)

- **(您在这里)** [NVIDIA 本地可信存储 (nvlts)](https://git.collinwebdesigns.de/vgpu/nvlts) (生成带有有效授权许可证的本地可信凭证)

  它适用于所有虚拟机, 并且这个工具是本地的, 不需要互联网连接, 但最少有一个网卡 (也许必须有一个 IP 地址?)

  您无需修改 DLL 和设置 DLS 实例, 同时保持 WHQL 签名完整

  但此方法强烈依赖于环境指纹, 目前似乎只检查网卡 MAC 地址和设备 ID

  > 无论您修改 VM 网卡, 插入或移除网卡, 甚至安装 OpenVPN TAP 网卡. 它都会使凭证失效

  > 我不确定这是否会影响 WireGuard 使用的 WinTun L3 设备

## 安装

- Linux 一键脚本

```shell
bash <(curl -sSL "https://git.collinwebdesigns.de/vgpu/nvlts/-/raw/master/scripts/install.sh") # 安装
bash <(curl -sSL "https://git.collinwebdesigns.de/vgpu/nvlts/-/raw/master/scripts/update.sh") # 升级
bash <(curl -sSL "https://git.collinwebdesigns.de/vgpu/nvlts/-/raw/master/scripts/uninstall.sh") # 卸载
```

- 预构建二进制文件

  从 [Releases](https://git.collinwebdesigns.de/vgpu/nvlts/-/releases) 下载

- 使用 `go install` 安装 (适用于 Golang 开发者)

```shell
go install git.collinwebdesigns.de/vgpu/nvlts@latest
```

- 自己编译

  查看 `构建` 章节

### 用法

```shell
  -c string
        生成所用的配置文件 (默认 "config.json")
  -d    将 NVIDIA Local Trusted Store 解密到文件
  -debug
        显示调试日志
  -e    将文件加密到 NVIDIA Local Trusted Store
  -f string
        要加密 / 保存解密的文件 (默认 "trusted_store.json")
  -g    生成许可证到 NVIDIA Local Trusted Store
  -h    显示帮助
  -r    自动重启 NVDisplay.ContainerLocalSystem 服务
```

- 从 NVIDIA Local Trusted Store 解密到文件 (默认: `trusted_store.json`)

```shell
nvlts -d
```

> 解密后的内容并非严格意义上的 JSON, NVIDIA 并未使用 json 库处理它, 它使用了 `snprintf` 来拼接字符串

- 将文件 (默认: `trusted_store.json`) 加密到 NVIDIA Local Trusted Store 并重启服务

```shell
nvlts -e -r
```

- 使用配置文件 (默认: `config.json`) 生成 (空的 NodeLockedLicense 和 NVIDIA Local Trusted Store) 并重启服务

```shell
nvlts -g -r
```

您可以在 `configs` 目录中找到示例配置文件

> 只有 `ProductName` 和 `FeatureName` 必须匹配, 其他项可以随意填写, 但最好不要留空 (可能会停止工作)

## Bug 反馈

提供您的系统信息 (操作系统版本, MAC 地址, Host/Guest 驱动版本和 GPU 型号) 以及 NVIDIA Local Trusted Store 文件

- (推荐) Telegram [@rbqvq](https://t.me/rbqvq) (英语 / 简体中文)

- 发送电子邮件至 [`coiaprant@gmail.com`](mailto:coiaprant@gmail.com) (英语 / 简体中文)

  > 如果长时间没有回复, 则表示您的电子邮件已被 Gmail 拒绝或归类为垃圾邮件, 您可以考虑更换电子邮件地址并重新发送

- 在 [Discord vGPU 频道 `@CoiaPrant`](https://discord.gg/thDa7CSY) (在频道/群组请使用英语, 私信可使用英语/简体中文)

  > 我不经常查看 Discord, 这取决于 Google 的消息推送 (FCM), 如果长时间没有回复, 请改用电子邮件方式

## 构建

所需最低 Go 版本: `go 1.23.0`

> 当然, 您可以自己做向前兼容, 这并不复杂

- 生产构建

```shell
go build -ldflags="-s -w" -trimpath .
```

- 调试构建

```shell
go build .
```

## 致谢

感谢 vGPU 社区以及所有使用本项目并报告 bug 的人
特别感谢:

- [vgpu-unlock-rs](https://github.com/mbilker/vgpu_unlock-rs)
- [FastAPI-DLS](https://git.collinwebdesigns.de/oscar.krause/fastapi-dls)
- [gridd-unlock-patcher](https://git.collinwebdesigns.de/vgpu/gridd-unlock-patcher)
- [patched-nvidia-grid-driver](https://github.com/acgdaily/patched-nvidia-grid-drivers)
- [佛西云盘 - 您可以在此处找到驱动程序](https://alist.homelabproject.cc/foxipan)
