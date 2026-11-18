# CDM_OEM 二次开发 / OEM development

## 快速开始 / Quick start

Windows x64，PowerShell 5.1 或更新版本。克隆本仓库或下载对应 Release 的 Source ZIP，解压到可写目录。首次准备需要网络；脚本不要求 Git，也不修改全局 Python。

Use Windows x64 and PowerShell 5.1 or later. Clone this repository or extract the matching Source ZIP into a writable directory. Initial setup requires network access; Git and a global Python installation are not required.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run.ps1
```

`setup.ps1` 准备项目内 Python 3.12.10、虚拟环境和锁定依赖，再按锁定文件下载完整 CDM。大小、SHA-256 或 CLI 版本不匹配会停止。Gitee 不可达时回退 GitHub，不使用 latest。

Setup prepares project-local Python 3.12.10, a virtual environment and locked dependencies, then downloads the complete pinned CDM. Size, SHA-256 and CLI version must match. GitHub is the fallback for Gitee; setup never downloads a floating latest runtime.

使用本地软件 ZIP / Use a local software ZIP:

```powershell
.\scripts\setup.ps1 -RuntimeZip 'D:\downloads\CANmeleon-device-manager-win64.zip'
```

本地 ZIP 必须与 `cdm-runtime.lock.json` 一致。这只替代 CDM 下载，Python 与开发依赖仍可能需要联网。初始化可重复执行。`-EnvironmentOnly` 仅准备开发环境，用于尚未生成后端正式候选的维护者。

The local ZIP must match the runtime lock. This replaces only the CDM download; Python/development dependencies may still need network access. Setup is repeatable. `-EnvironmentOnly` prepares development tools without the runtime, for maintainers before the formal backend candidate exists.

## 定制 / Customization

- `oem/branding.json`：名称、主题色、Logo、图标、帮助网址、页面列表。帮助网址设为空可隐藏链接。`pages` 支持 `devices`、`firmware`、`help`。
- `oem/ui.py`：页面布局和双语文案；`oem/client.py`：公开 CLI 调用封装。不要导入内部 CDM 模块或解析内部状态文件。
- 客户品牌需修改 `product_id` 和 `app_id`，避免覆盖示例或其他产品；本品牌后续升级保持这两个标识不变。
- 将 Logo 和 ICO 放在 `oem/` 内。修改 ICO 后重新构建，安装器与任务栏使用同一产品身份。

Edit branding.json for the name, accent color, logo, icon, help URL and visible pages. An empty help URL hides the link. Edit ui.py for layout and bilingual wording. Keep device operations in the public CLI adapter. Assign distinct product_id and app_id values for a new product and keep them stable across its upgrades. Brand assets must remain inside oem/.

## 打包 / Packaging

安装 Inno Setup 6.7.3，然后运行：

Install Inno Setup 6.7.3, then run:

```powershell
winget install --id JRSoftware.InnoSetup --version 6.7.3 --exact
.\scripts\package.ps1
# 本地后端候选 / Local backend candidate:
.\scripts\package.ps1 -RuntimeZip 'D:\downloads\CANmeleon-device-manager-win64.zip'
```

Nuitka 首次构建可能下载 C 编译工具。生成目录位于 `build/`，安装包位于 `dist/`。可用 `-Iscc` 指定编译器路径；已有构建可用 `-PackageDir` 指定，但仍执行包校验。安装器包含 OEM EXE 和完整原版后端，最终用户不需要 Python 或另装 CDM。

Nuitka may download C build tools on the first build. Package directories are under build/ and installers under dist/. Pass -Iscc for a custom compiler path or -PackageDir for an existing package; verification still runs. The installer includes the OEM EXE and complete backend. End users need neither Python nor a separate CDM installation.

中文源码路径会自动使用临时 ASCII 编译目录，生成结果仍返回项目 `build/`。如果 Windows 临时目录本身含中文，可设置 `CDM_OEM_BUILD_ROOT` 为可写的英文路径。此目录仅用于编译副本，不修改全局 Python。

Non-ASCII source paths use an isolated ASCII compiler scratch directory; outputs return to the project build/ directory. If the Windows temporary path also contains non-ASCII characters, set CDM_OEM_BUILD_ROOT to a writable ASCII path. This does not modify global Python.

首版安装器为英文安装向导，软件界面可切换中英文。采用 SHA-256 完整性记录，未签名时不声称有 Authenticode 签名。UI/后端通过完整安装包一起更新，不调用原版更新器。安装或卸载前等待设备操作完成并退出 OEM。

The first installer wizard is English; the application supports Chinese and English. Build records report SHA-256 integrity and unsigned status honestly. Upgrade UI/runtime together with the complete installer. Wait for device operations to finish and close OEM before installation or removal.

## 使用与故障处理 / Use and troubleshooting

设备选择页每五秒刷新。连接后可按版本和兼容性筛选市场；双击已装固件或空槽，选择目标固件并核对预览。满槽时选择替换目标。卸载仅对未运行固件开放。在设备信息中可切换后端列出的 USB 模式，应答后重新连接核对。帮助中的操作编号查询可用于售后核查。

The picker refreshes every five seconds while idle. Filter by version and compatibility. Double-click an occupied or empty slot to choose firmware and review the target. When full, select which firmware to replace. Switch away from a running image before uninstalling it. USB modes come from the connected device. Reconnect after a mode acknowledgement. Look up a recorded operation ID in Help.

将 `branding.json` 的 `online_firmware` 设为 `false` 可隐藏在线入口。启用时仅在点击检查或确认下载后联网，支持 stable/beta。TLS 校验失败时可改用官方完整 ZIP。 / Set `online_firmware` to false to hide online firmware controls. Checking and downloading are explicit actions. If certificate verification fails, import the official ZIP.

1. 在设备表中选择目标，点击“连接”（或双击行）。单台设备预选，多台设备须手动选择。连接前可浏览固件市场，连接后默认进入固件管理并自动查询兼容性。在“设备信息”中勾选通道后点击“应用设置”。/ Select a device and click Connect or double-click its row. A single device is highlighted. With multiple devices, select one explicitly. Browse the catalog before connecting. Connect to open firmware management and check compatibility. Under Device information, select channel termination states and apply changes.
2. 导入官方完整固件 ZIP，选择兼容固件，检查预览和 UID 后确认安装。软件 ZIP 与固件 ZIP 不可混用。/ Import the complete official firmware ZIP, review compatibility and UID, then confirm the preview. Software and firmware ZIPs are different.
3. 安装后检查已安装列表；需要时手动切换，安装不会自动切换。/ Verify the installed list; switching is a separate operation.
4. 写入时保持供电与 USB 连接。超时或未知结果先刷新读取，不自动重试。/ Keep USB and power connected. Query state after timeout/unknown outcome; never retry automatically.
5. 占用时先断开原版 CDM 的设备连接或释放其他软件。空间不足、恢复模式、V2 和复杂布局请使用原版支持流程。/ Release other applications when busy. Use supported original-CDM workflows for insufficient space, recovery and complex layouts; this demo does not claim V2 support.

核心提示可离线查看。网络失败不影响已准备好的本地操作。设置终端电阻后后端会回读；不支持不等于关闭。诊断复制包括版本、错误码和设备 UID，请在对外发送前检查隐私信息。

Core guidance works offline. Network failures do not disable prepared local workflows. Termination is read back after writes; unsupported does not mean disabled. Diagnostics include versions, error codes and device UID; review them before sharing.

## 验证范围 / Validation scope

查看对应 Release 的验收记录。模拟测试、构建检查、设备实测与源代码重建分别记录；本示例不提供 CAN 吞吐性能认证。固件版本与 CDM 软件版本独立。

See the release validation record. Mock tests, build checks, hardware tests and source rebuilds are recorded separately. The demo is not a CAN performance certification tool. Firmware and CDM software versions are independent.
