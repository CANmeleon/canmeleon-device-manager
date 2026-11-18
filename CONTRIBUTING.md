# Development and release

Use Windows x64. Run `scripts/setup.ps1`, `scripts/run.ps1`, then `scripts/package.ps1`. See [the development guide](docs/oem-development.md). The runtime and its dependencies must remain complete.

This repository is the source of truth for the OEM layer. Backend changes belong in the private CDM repository. Never add private source, internal Git history, firmware algorithms, downloaded runtimes, credentials or test artifacts here.

Before a change, inspect Git status. Run `.venv/Scripts/python.exe -m pytest -q` and parse modified PowerShell scripts. Keep the UI, error guidance and documentation bilingual. Tests must cover identity binding, stale plans and uncertain outcomes when those behaviors change.

For a release, freeze and validate the original CDM ZIP first, update `cdm-runtime.lock.json`, then build the OEM installer from that exact runtime. Verify the final installed program on hardware. Publish original assets, the OEM installer and this source under one new `CDM-x.y.z` tag on Gitee and GitHub. Preserve each public repository's history; do not overwrite existing tags or assets. Internal backend and public OEM source commits are distinct and must be recorded separately.

From 0.9.0 publish to the canmeleon organization on Gitee and CANmeleon on GitHub. Verify both organizations before promoting the legacy Gitee bridge. Preserve the frozen 0.6.0 ZIP feed and tagged ZIP. Source archives are OEM development inputs, not application installers. Test an exported source tree without `.git` before release, and the real public Source ZIP after release. Download and verify all published assets. Do not claim full publication if a platform or required validation is missing.

开发维护：仅维护 OEM 层，所有设备操作通过公开 CLI。修改前检查 Git 状态；相关测试、双语提示和文档同步更新。正式发布必须先验证最终安装包，再将同一份制品分发到双平台，并从公开 Source ZIP 验证二次开发流程。不覆盖历史版本，保留旧仓桥接入口与冻结清单，不公开内部源码或日志。
