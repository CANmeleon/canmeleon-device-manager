# OEM CLI integration / CLI 接入

The executable is the complete pinned CDM runtime's `CANmeleon-device-manager.exe`. No arguments opens the original GUI; OEM always passes a public command. There is no Python import dependency on CDM.

可执行入口来自锁定的完整 CDM 运行目录。无参数打开原版 GUI，OEM 始终携带公开命令。不得只复制主 EXE 或依赖内部 Python 包。

| OEM operation / 操作 | Public command / 命令 |
| --- | --- |
| Version / 版本 | `version --json` |
| Discovery / 枚举 | `devices list --json` |
| Identity / 信息 | `device info --device ID --json` |
| Local catalog / 本地目录 | `firmware catalog --device ID --offline --json` |
| Import / 导入 | `releases import --file ZIP --json` |
| Preview / 预览 | `firmware install --device ID --expect-uid UID --firmware FIRMWARE --version VERSION --dry-run --json` |
| Install / 安装 | Same arguments, replace `--dry-run` with `--plan-id PLAN --yes` |
| Switch / 切换 | `firmware switch --device ID --expect-uid UID --firmware INSTALLED_ID --yes --json` |
| Termination / 电阻 | `termination get/set --device ID --channel N`; set also requires `--expect-uid UID --state on/off --yes` |

All calls use explicit argument arrays, hidden child windows, stdin=DEVNULL and captured UTF-8 output. The adapter adds `--json --offline --cache-dir ... --timeout 300 --wait 90`. The UI waits for CDM's own bounded task result rather than killing writes with an outer timeout.

返回 envelope 包含 `schema_version=1`、`tool_version`、`operation_id`、`ok`、`data` 和 `error`。失败按 `error.code` 判断，不能匹配错误文本。写操作仅在 `completion=verified` 时显示已验证；无效响应、超时或无法确认结果不得显示成功。额外字段可忽略，必要字段缺失应报错。

The envelope contains schema_version=1, tool_version, operation_id, ok, data and error. Use error.code, not message text. A write is verified only when completion=verified. Invalid responses/timeouts/uncertain outcomes are not success. Ignore extra fields, but reject missing required fields.

UID comes from a successful device read. Device IDs may change when moved to another USB port. Installed firmware IDs and plan IDs must be refreshed after changes. Catalog availability comes from the backend, never brand/PID guesses. The adapter maps only display fields; raw protocol diagnostics and storage layouts are not a supported OEM UI contract.

UID 来自设备读取；换 USB 口后重新枚举。固件标识和计划会过期，变更后重新读取。兼容性以实际后端判断为准。原始协议诊断和存储布局不是 OEM UI 的公开模型。

错误处理：设备丢失重新枚举，身份不符拒绝写入，计划过期重新预览，占用则释放设备，不支持/空间不足引导原版处理，未知结果保持供电并查询。CLI 不提供通用取消或断点续作；本示例不构造这些承诺。

Handle disappearance by rediscovery, identity mismatch by refusing writes, stale plans by re-previewing, busy devices by releasing access, unsupported/space errors through original-CDM guidance, and unknown outcomes by keeping power and querying. Generic cancellation and resume are not provided.
