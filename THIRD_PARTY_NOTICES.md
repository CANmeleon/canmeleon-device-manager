# License boundaries / 许可边界

The MIT license covers original OEM code, documentation, scripts and the example logo. It does not grant rights to CANmeleon trademarks or relicense downloaded software.

MIT 许可仅覆盖本仓库原创 OEM 代码、文档、脚本和示例图标，不改变商标、原版 CDM 或第三方组件的许可。

- **CDM runtime:** separately distributed binary, retained without modification. Keep its notices and complete dependency directory. The source license in this repository does not cover its implementation or bundled firmware.
- **PySide6 / Shiboken6 / Qt:** separately licensed by their respective owners (including LGPL/GPL/commercial options). The OEM package uses dynamically loaded libraries. Preserve their distribution licenses; the MIT license does not replace them. Build inputs are pinned in `requirements.lock`.
- **Python:** Python Software Foundation license; downloaded from the official Python NuGet package.
- **Nuitka, ordered-set, zstandard, pytest and development dependencies:** retain the license metadata shipped with each locked distribution; these are build/test dependencies, not OEM-owned code.
- **Inno Setup:** its own license and commercial-use terms apply. No claim of an acquired commercial license is made by this repository.

Drivers and device firmware retain their own terms. Review the relevant packages before redistributing a customized product. Do not copy proprietary logos into the OEM template without permission.

The packaged Qt/PySide libraries are dynamically loaded, unmodified library distributions. LGPL/GPL texts are in `licenses/`; original wheel metadata/notices are preserved in the installed package. Corresponding upstream sources: [PySide 6.11.1](https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.11.1-src/) and [Qt 6.11.1](https://download.qt.io/official_releases/qt/6.11/6.11.1/submodules/). The OEM build instructions allow rebuilding the application and using compatible replacement libraries. Restrictions on reverse engineering for debugging modifications to LGPL libraries are not imposed by the OEM MIT license.
