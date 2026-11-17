from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QThread, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (QApplication, QComboBox, QFileDialog, QFormLayout, QHBoxLayout,
    QLabel, QListWidget, QMainWindow, QMessageBox, QProgressBar, QPushButton, QStackedWidget,
    QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget, QHeaderView)

from . import VERSION
from .client import CliError, device_view, plan_view


ERROR_HELP = {
    "RUNTIME_MISSING": ("请运行 setup.ps1 或重新安装软件。", "Run setup.ps1 or reinstall this product."),
    "VERSION_MISMATCH": ("后端版本不匹配，请重新初始化或安装完整软件包。", "Runtime version mismatch. Run setup or reinstall the complete package."),
    "TARGET_NOT_FOUND": ("设备已断开，请刷新并重新选择。", "Device disconnected. Refresh and select it again."),
    "TARGET_AMBIGUOUS": ("无法唯一定位设备，请仅连接目标设备后刷新。", "Cannot identify one device. Connect only the target and refresh."),
    "TARGET_MISMATCH": ("设备身份变化，已拒绝操作。请重新读取设备。", "Device identity changed. Operation refused. Read the device again."),
    "STALE_PLAN": ("设备或固件发生变化，请重新预览安装。", "Device or firmware changed. Preview the installation again."),
    "BUSY": ("设备正在使用，请断开原版 CDM 的连接或关闭占用软件后重试。", "Device is busy. Disconnect the original CDM or close the application using it."),
    "DEVICE_BUSY": ("设备正在使用，请释放设备后重试。", "Device is busy. Release it before retrying."),
    "OUTCOME_UNKNOWN": ("结果尚不能确认。设备可能仍在写入，请保持供电，稍后刷新并读取状态，勿重复安装。", "Outcome unknown. The device may still be writing. Keep power connected, then refresh and read its state. Do not repeat installation."),
    "TIMEOUT": ("操作超时，请重新查询设备状态后再决定下一步。", "Operation timed out. Read the device state before deciding what to do next."),
    "INSUFFICIENT_SPACE": ("没有足够的连续空间。请使用原版 CDM 整理固件后重试。", "Insufficient contiguous space. Use the original CDM to manage firmware first."),
    "UNSUPPORTED": ("当前设备或固件不支持此操作，可使用原版 CDM 查看详细信息。", "This device or firmware does not support this operation. Check the original CDM for details."),
    "INVALID_PACKAGE": ("固件包无效，请选择官方完整发布 ZIP。", "Invalid firmware package. Select the complete official release ZIP."),
    "INVALID_RESPONSE": ("后端响应无法解析。请检查版本并复制诊断信息。", "Cannot parse backend response. Check versions and copy diagnostics."),
}


class Job(QThread):
    def __init__(self, action, parent=None):
        super().__init__(parent)
        self.action, self.value, self.error = action, None, None

    def run(self):
        try:
            self.value = self.action()
        except Exception as exc:
            self.error = exc


class Window(QMainWindow):
    def __init__(self, client, brand: dict, root: Path, settings: Path):
        super().__init__()
        self.client, self.brand, self.root, self.settings = client, brand, root, settings
        self.job = None
        self.ready = False
        self.device = None
        self.uid = None
        self.uncertain = False
        self.plan = None
        self.channels = 0
        self.catalog_rows = []
        self.firmware_rows = []
        self.diagnostic = {}
        self.texts = []
        self.actions = []
        self.setWindowTitle(f"{brand['name']} · {VERSION}")
        self.resize(1040, 740)
        self.setMinimumSize(850, 620)
        self.setWindowIcon(QIcon(str(root / "oem" / brand["icon"])))
        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(26, 20, 26, 20)
        header = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(QPixmap(str(root / "oem" / brand["logo"])).scaled(42, 42))
        header.addWidget(logo)
        title = QLabel(brand["name"])
        title.setObjectName("title")
        header.addWidget(title)
        header.addStretch()
        self.language = QComboBox()
        self.language.addItems(["简体中文", "English"])
        if settings.exists():
            try:
                self.language.setCurrentIndex(int(json.loads(settings.read_text(encoding="utf-8")).get("language", 0)))
            except (ValueError, OSError):
                pass
        header.addWidget(self.language)
        outer.addLayout(header)
        selector = QHBoxLayout()
        self.devices_combo = QComboBox()
        self.devices_combo.setMinimumWidth(420)
        selector.addWidget(self.devices_combo, 1)
        selector.addWidget(self.button("刷新设备", "Refresh devices", self.refresh_devices))
        selector.addWidget(self.button("读取设备", "Read device", self.read_device, "selected"))
        outer.addLayout(selector)
        body = QHBoxLayout()
        self.nav = QListWidget()
        self.nav.setFixedWidth(150)
        self.pages = QStackedWidget()
        self.page_keys = brand["pages"]
        for key in self.page_keys:
            self.pages.addWidget(getattr(self, f"page_{key}")())
        body.addWidget(self.nav)
        body.addWidget(self.pages, 1)
        outer.addLayout(body, 1)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(self.status.textInteractionFlags())
        outer.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setFixedHeight(5)
        self.progress.hide()
        outer.addWidget(self.progress)
        self.setCentralWidget(central)
        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.devices_combo.currentIndexChanged.connect(self.selection_changed)
        self.language.currentIndexChanged.connect(self.retranslate)
        color = brand["theme_color"]
        self.setStyleSheet(f"""
            QMainWindow {{background:#F3F7F8;}} QWidget {{font-family:'Segoe UI','Microsoft YaHei';font-size:13px;color:#19363B;}}
            QLabel#title {{font-size:24px;font-weight:600;}} QPushButton {{background:{color};color:white;border:0;border-radius:6px;padding:9px 13px;}}
            QPushButton:disabled {{background:#DCE5E6;color:#87999D;}} QComboBox {{background:white;padding:8px;border:1px solid #CCDCDE;border-radius:6px;}}
            QListWidget,QTextEdit,QTableWidget {{background:white;border:1px solid #DCE5E6;border-radius:7px;}}
            QListWidget::item {{padding:15px;}} QListWidget::item:selected {{background:{color};color:white;}}
            QHeaderView::section {{background:#EAF1F2;padding:8px;border:0;}} QProgressBar::chunk {{background:{color};}}
        """)
        self.retranslate()
        self.nav.setCurrentRow(0)
        QTimer.singleShot(0, self.initialize)

    def tr2(self, zh, en):
        return en if self.language.currentIndex() == 1 else zh

    def label(self, zh, en):
        obj = QLabel()
        obj.setWordWrap(True)
        self.texts.append((obj, zh, en))
        return obj

    def button(self, zh, en, action, needs="ready"):
        obj = QPushButton()
        self.texts.append((obj, zh, en))
        obj.clicked.connect(action)
        self.actions.append((obj, needs))
        return obj

    def page_devices(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self.label("设备信息与通道配置", "Device information and channels"))
        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setMaximumHeight(260)
        layout.addWidget(self.info_text)
        form = QHBoxLayout()
        self.channel = QComboBox()
        form.addWidget(self.channel)
        form.addWidget(self.button("读取电阻", "Read termination", self.get_termination, "channel"))
        form.addWidget(self.button("开启电阻", "Enable termination", lambda: self.set_termination(True), "write_channel"))
        form.addWidget(self.button("关闭电阻", "Disable termination", lambda: self.set_termination(False), "write_channel"))
        layout.addLayout(form)
        self.term_status = QLabel()
        layout.addWidget(self.term_status)
        layout.addWidget(self.label("通道号对应设备物理 CH1、CH2 等。设置后会回读确认；不支持的通道不会强行设置。",
                                   "Channel numbers refer to physical CH1, CH2, etc. Settings are read back; unsupported operations are refused."))
        layout.addStretch()
        return page

    def page_firmware(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self.label("已安装固件", "Installed firmware"))
        self.table = QTableWidget(0, 3)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self.update_actions)
        layout.addWidget(self.table)
        layout.addWidget(self.button("切换到选中固件", "Switch to selected firmware", self.switch_firmware, "firmware"))
        row = QHBoxLayout()
        row.addWidget(self.button("导入完整固件 ZIP", "Import firmware ZIP", self.import_firmware))
        row.addWidget(self.button("刷新可用固件", "Refresh catalog", self.refresh_catalog, "identified"))
        layout.addLayout(row)
        self.catalog = QComboBox()
        self.catalog.currentIndexChanged.connect(self.catalog_changed)
        layout.addWidget(self.catalog)
        self.reason = QLabel()
        self.reason.setWordWrap(True)
        layout.addWidget(self.reason)
        layout.addWidget(self.button("预览安装…", "Preview installation…", self.preview_install, "catalog"))
        layout.addWidget(self.label("安装前检查设备 UID 和固件版本。安装不会自动切换运行；空间不足时请使用原版 CDM 管理固件。",
                                   "Verify UID and firmware version before installing. Installation does not switch the running firmware. Use the original CDM if space is insufficient."))
        return page

    def page_help(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        self.help_text = QTextEdit()
        self.help_text.setReadOnly(True)
        layout.addWidget(self.help_text)
        layout.addWidget(self.button("复制诊断信息", "Copy diagnostics", self.copy_diagnostics, "always"))
        if self.brand.get("help_url"):
            layout.addWidget(self.button("打开帮助网页", "Open help website",
                lambda: QDesktopServices.openUrl(QUrl(self.brand["help_url"])), "always"))
        return page

    def retranslate(self):
        for obj, zh, en in self.texts:
            obj.setText(self.tr2(zh, en))
        current = self.nav.currentRow()
        self.nav.clear()
        names = {"devices": ("设备", "Devices"), "firmware": ("固件", "Firmware"), "help": ("关于与帮助", "About & help")}
        self.nav.addItems([self.tr2(*names[key]) for key in self.page_keys])
        self.nav.setCurrentRow(max(0, current))
        if hasattr(self, "table"):
            self.table.setHorizontalHeaderLabels([self.tr2("固件", "Firmware"), self.tr2("版本", "Version"), self.tr2("状态", "State")])
            self.render_firmware()
        if hasattr(self, "help_text"):
            self.help_text.setPlainText(self.tr2(
                f"{self.brand['name']} {VERSION}\nCDM {self.client.version} · CLI schema 1\n\n先刷新并选择设备，再读取设备信息。固件使用官方完整 ZIP 离线导入。\n\n写入期间保持供电、不要拔线或关闭程序。结果未知时先重新查询设备，切勿直接重试安装。\n\n本版不提供自检、恢复、V2、量产或软件自动更新。请使用完整新版安装包升级。\n\n修改 oem/branding.json 可定制品牌；页面位于 oem/ui.py，设备执行通过公开 CLI。源码 MIT 许可不覆盖后端及第三方组件。",
                f"{self.brand['name']} {VERSION}\nCDM {self.client.version} · CLI schema 1\n\nRefresh, select a device, then read its information. Import a complete official firmware ZIP for offline installation.\n\nKeep power connected during writes. Do not unplug or close the program. If the outcome is unknown, query the device before considering another installation.\n\nSelf-test, recovery, V2, production and automatic software updates are not included. Upgrade using the complete installer.\n\nCustomize oem/branding.json and oem/ui.py. Device operations use the public CLI. The source MIT license excludes the runtime and third-party components."))
        self.settings.parent.mkdir(parents=True, exist_ok=True)
        self.settings.write_text(json.dumps({"language": self.language.currentIndex()}), encoding="utf-8")
        self.update_actions()

    def update_actions(self):
        selected = self.devices_combo.currentData() is not None
        identified = bool(self.device and self.uid)
        can_write = identified and not self.uncertain
        for button, needs in self.actions:
            allowed = {"always": True, "ready": self.ready, "selected": self.ready and selected,
                "identified": self.ready and identified, "channel": identified and self.channels > 0,
                "write_channel": can_write and self.channels > 0,
                "firmware": can_write and hasattr(self, "table") and self.table.currentRow() >= 0,
                "catalog": can_write and hasattr(self, "catalog") and self.catalog.currentData() is not None
                    and self.catalog.currentData().get("availability") == "Available"}.get(needs, False)
            button.setEnabled(bool(allowed) and self.job is None)
        self.devices_combo.setEnabled(self.ready and self.job is None)
        if hasattr(self, "catalog"):
            self.catalog.setEnabled(self.job is None)

    def start(self, action, success, writing=False):
        if self.job is not None:
            return
        self.status.setText(self.tr2("正在处理，请保持设备连接…", "Working. Keep the device connected…"))
        self.progress.show()
        job = Job(action, self)
        self.job = job
        self.update_actions()
        def finished():
            self.job = None
            self.progress.hide()
            if job.error:
                self.failed(job.error, writing)
            else:
                self.status.setText(self.tr2("操作完成", "Operation completed"))
                try:
                    success(job.value)
                except Exception as exc:
                    self.failed(exc, writing)
            self.update_actions()
            job.deleteLater()
        job.finished.connect(finished)
        job.start()

    def failed(self, error, writing=False):
        code = getattr(error, "code", "OUTCOME_UNKNOWN" if writing else "CLIENT_ERROR")
        if writing or code in ("OUTCOME_UNKNOWN", "TIMEOUT"):
            self.uncertain = True
        self.plan = None
        self.diagnostic = {"ui_version": VERSION, "cdm_version": self.client.version, "code": code,
                           "message": str(error), "device": self.device, "uid": self.uid,
                           "operation_id": getattr(error, "operation_id", None)}
        guidance = ERROR_HELP.get(code, ("操作失败。请刷新设备，检查驱动或连接，并复制诊断信息供排查。", "Operation failed. Refresh the device, check drivers/connections and copy diagnostics."))
        self.status.setText(f"{code} · {self.tr2(*guidance)}")

    def initialize(self):
        def ready(_):
            self.ready = True
            self.refresh_devices()
        self.start(self.client.handshake, ready)

    def selection_changed(self):
        self.device = self.uid = self.plan = None
        self.channels = 0
        self.firmware_rows = []
        if hasattr(self, "info_text"):
            self.info_text.clear()
            self.channel.clear()
            self.term_status.clear()
        if hasattr(self, "catalog"):
            self.catalog.clear()
            self.render_firmware()
        self.update_actions()

    def refresh_devices(self):
        previous = self.devices_combo.currentData()
        self.selection_changed()
        def done(rows):
            self.devices_combo.clear()
            for row in rows:
                name = row.get("product_name") or row.get("name") or row.get("device_type") or row["id"]
                self.devices_combo.addItem(f"{name} · {row.get('usb_node_label') or row.get('location') or row['id']}", row["id"])
            self.devices_combo.setCurrentIndex(self.devices_combo.findData(previous) if previous else -1)
            self.status.setText(self.tr2(f"找到 {len(rows)} 台设备，请选择后读取。", f"Found {len(rows)} device(s). Select one and read it."))
        self.start(self.client.devices, done)

    def read_device(self):
        device = self.devices_combo.currentData()
        if not device:
            return
        self.selection_changed()
        def done(data):
            view = device_view(data)
            self.device, self.uid, self.channels = device, view["uid"], view["channels"]
            self.uncertain = False
            self.firmware_rows = view["firmware"]
            if hasattr(self, "info_text"):
                current = next((row for row in self.firmware_rows if row["running"]), {})
                self.info_text.setPlainText(f"UID: {self.uid or '—'}\n{self.tr2('通道', 'Channels')}: {self.channels or '—'}\n{self.tr2('当前固件', 'Running firmware')}: {current.get('name', '—')} {current.get('version', '')}")
                self.channel.clear()
                self.channel.addItems([f"CH{i}" for i in range(1, self.channels + 1)])
            if hasattr(self, "table"):
                self.render_firmware()
                self.refresh_catalog()
        self.start(lambda: self.client.info(device), done)

    def render_firmware(self):
        self.table.setRowCount(len(self.firmware_rows))
        for i, row in enumerate(self.firmware_rows):
            for j, text in enumerate([row["name"], row["version"], self.tr2("运行中", "Running") if row["running"] else self.tr2("已安装", "Installed")]):
                self.table.setItem(i, j, QTableWidgetItem(str(text)))

    def refresh_catalog(self):
        device = self.device
        if not device:
            return
        def done(rows):
            self.catalog_rows = rows
            self.catalog.clear()
            for row in rows:
                self.catalog.addItem(f"{row['name']} · {row['version']} · {row['availability']}", row)
            self.catalog_changed()
        self.start(lambda: self.client.catalog(device), done)

    def catalog_changed(self):
        self.plan = None
        row = self.catalog.currentData()
        self.reason.setText(str(row.get("reason") or "") if row else self.tr2("请导入固件包或读取设备。", "Import a firmware ZIP or read the device."))
        self.update_actions()

    def import_firmware(self):
        path, _ = QFileDialog.getOpenFileName(self, self.tr2("选择完整固件发布包", "Select complete firmware release"), "", "ZIP (*.zip)")
        if path:
            self.start(lambda: self.client.import_zip(path), lambda _: self.refresh_catalog() if self.device else None)

    def confirm(self, text):
        return QMessageBox.question(self, self.tr2("确认设备操作", "Confirm device operation"), text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes

    def preview_install(self):
        row = self.catalog.currentData()
        if not row or not self.uid:
            return
        device, uid = self.device, self.uid
        def done(data):
            self.plan = plan_view(data["plan"])
            plan = self.plan
            text = self.tr2("即将安装固件。保持 USB 连接和供电。\n", "Install firmware. Keep USB and power connected.\n")
            text += f"UID: {uid}\n{plan['name']} · {plan['firmware_version']}\n{plan['size_bytes']} bytes\n"
            text += self.tr2("保留其他固件；安装后不会自动切换。继续？", "Other firmware is preserved. Installation does not switch the running firmware. Continue?")
            if self.confirm(text):
                self.start(lambda: self.client.install(device, uid, row["id"], row["version"], plan["plan_id"]),
                           lambda _: self.read_device(), writing=True)
            self.plan = None
        self.start(lambda: self.client.install(device, uid, row["id"], row["version"]), done)

    def switch_firmware(self):
        index = self.table.currentRow()
        if index < 0:
            return
        row = self.firmware_rows[index]
        device, uid = self.device, self.uid
        if self.confirm(self.tr2("切换后设备会重新枚举。\n", "The device will reconnect after switching.\n") + f"UID: {uid}\n{row['name']} {row['version']}"):
            self.start(lambda: self.client.switch(device, uid, row["id"]), lambda _: self.read_device(), writing=True)

    def get_termination(self):
        device, channel = self.device, self.channel.currentIndex() + 1
        self.start(lambda: self.client.termination(device, channel), self.show_termination)

    def show_termination(self, data):
        state = self.tr2("开启", "Enabled") if data["enabled"] else self.tr2("关闭", "Disabled")
        self.term_status.setText(f"CH{data['channel']} · {state}")

    def set_termination(self, enabled):
        device, uid, channel = self.device, self.uid, self.channel.currentIndex() + 1
        state = self.tr2("开启", "Enable") if enabled else self.tr2("关闭", "Disable")
        if self.confirm(f"UID: {uid}\nCH{channel} · {state}"):
            self.start(lambda: self.client.termination(device, channel, uid, enabled), self.show_termination, writing=True)

    def copy_diagnostics(self):
        QApplication.clipboard().setText(json.dumps(self.diagnostic or {"ui_version": VERSION, "cdm_version": self.client.version}, ensure_ascii=False, indent=2))

    def closeEvent(self, event):
        if self.job is not None:
            self.status.setText(self.tr2("操作进行中，请等待结果。关闭界面不会取消设备操作。", "An operation is running. Wait for its result; closing the UI does not cancel device work."))
            event.ignore()
        else:
            event.accept()
