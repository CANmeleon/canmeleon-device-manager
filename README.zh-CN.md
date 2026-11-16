# CANmeleon 设备管理器 — USB-CAN/CAN FD 固件管理

[English](README.md) · [简体中文](README.zh-CN.md)

CANmeleon 设备管理器用于在 Windows 上连接支持的 USB-CAN/CAN FD 设备，读取设备信息，安装、更新和切换 CANmeleon 固件，并对进入 KH-Updater 模式的支持设备执行恢复。

**[下载 Windows x64 版本](https://canmeleon.com/zh/device-manager/#downloads)** · [支持设备](https://canmeleon.com/zh/firmware/devices/) · [固件总览](https://github.com/CANmeleon/canmeleon-usb-can-firmware) · [使用指南](https://canmeleon.com/zh/device-manager/)

## 下载与安装

| 安装包 | 使用方式 |
| --- | --- |
| [Windows x64 安装程序](https://gitee.com/ChengDu-KunHong/canmeleon-device-manager/releases/download/latest/CANmeleon-device-manager-setup-x64.exe) | 运行程序并按安装向导完成安装。 |
| [Windows x64 便携 ZIP](https://gitee.com/ChengDu-KunHong/canmeleon-device-manager/releases/download/latest/CANmeleon-device-manager-win64.zip) | 完整解压，运行 `CANmeleon-device-manager.exe`。 |

[软件版本说明](https://gitee.com/ChengDu-KunHong/canmeleon-device-manager/releases)。以上下载托管于 Gitee。图文指南对应 **0.8.5**；管理器版本与设备固件包版本分别管理。

## 主要功能

| 操作 | 能力 |
| --- | --- |
| 识别设备 | 查看 USB 节点、驱动、设备信息及已安装固件。 |
| 选择固件 | 浏览固件目录，连接支持设备后核对适用性。 |
| 管理存储 | 写入前查看已装固件、可用空间和待执行变更。 |
| 安装与更新 | 下载固件包或导入完整离线 ZIP，再安装适用固件。 |
| 切换固件 | 选择已安装固件运行，设备以相应 USB 身份和驱动重新连接。 |
| 恢复设备 | 为处于 KH-Updater 恢复模式的支持设备写入适用固件。 |

硬件、存储和授权允许时可以保存多种固件，每次运行一种。可用通道、运行模式及软件终端电阻控制取决于设备和固件。

## 首次连接与安装固件

1. 在[支持设备列表](https://canmeleon.com/zh/firmware/devices/)核对完整型号，安装当前运行固件所需的驱动。
2. 关闭占用设备的 CAN 软件，通过 USB 连接设备，在管理器中刷新列表。
3. 选择设备并连接，查看设备信息和已安装固件。
4. 在固件目录中选择版本及适用固件，检查空间和待执行变更。
5. 确认安装或更新，等待写入完成。写入期间保持供电，不拔出设备或关闭管理器。
6. 重新连接并核对版本，切换到目标固件运行；等待 USB 重新识别后打开对应 CAN 软件。

完整步骤见[固件管理指南](https://canmeleon.com/zh/device-manager/firmware-management/)。

## 离线更新与恢复

通过[固件下载指南](https://github.com/CANmeleon/canmeleon-usb-can-firmware/blob/main/README.zh-CN.md)取得完整固件 ZIP，使用管理器的导入功能准备本地缓存，再执行安装。

设备显示恢复模式时，按[设备恢复指南](https://canmeleon.com/zh/device-manager/updates-and-recovery/)操作。恢复可能覆盖已安装固件，写入前核对目标设备和固件包，并保持供电至完成。

## 常见问题

**任何 USB-CAN 设备都能安装吗？**

使用支持 CANmeleon 管理的硬件。扫描到 USB 名称或目录显示某固件，不代表支持安装；应核对连接后给出的适用性结果。

**切换固件会同时打开 CANoe、PCAN-View 等软件吗？**

切换只改变设备运行的固件。电脑端软件需单独打开，并使用目标固件要求的驱动。

**为什么下载完成后设备版本没变化？**

下载或导入只更新电脑缓存，还需准备并执行安装计划，再连接设备读取版本。

**源码在哪里？**

本仓库提供使用文档和软件发布包入口，许可信息以对应发布包为准。

## 帮助与反馈

- [故障排查](https://canmeleon.com/zh/device-manager/faq/)：设备识别、驱动、空间和更新错误。
- [管理器问题反馈](https://github.com/CANmeleon/canmeleon-device-manager/issues)：附设备型号、管理器及固件版本、错误信息和复现步骤；现有技术支持：[support@kunhong-elec.com](mailto:support@kunhong-elec.com)。
- [固件问题反馈](https://github.com/CANmeleon/canmeleon-usb-can-firmware/issues) · [VN16xx 固件](https://github.com/CANmeleon/canmeleon-VN16xx-firmware)。
