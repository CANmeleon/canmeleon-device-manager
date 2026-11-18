from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt, QSize, QThread, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (QApplication, QComboBox, QFileDialog, QCheckBox, QGroupBox, QTabWidget, QListWidgetItem, QHBoxLayout,
    QLabel, QListWidget, QMainWindow, QMessageBox, QProgressBar, QPushButton, QStackedWidget,
    QTableWidget, QTableWidgetItem, QDialog, QInputDialog, QVBoxLayout, QWidget, QHeaderView)

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
        self.visible_catalog = []
        self.empty_slots = []
        self.max_slots = None
        self.release_channel = "stable"
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
        outer.setContentsMargins(12, 10, 12, 8)
        header = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(QPixmap(str(root / "oem" / brand["logo"])).scaled(24, 24))
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
        self.page_keys = brand["pages"]
        self.device_rows = []
        self.term_states = {}
        self.checks = {}
        self.flow = QStackedWidget()
        outer.addWidget(self.flow, 1)
        pick = QWidget()
        self.pick_layout = QVBoxLayout(pick)
        self.pick_layout.addWidget(self.label("选择设备", "Select device"))
        controls = QHBoxLayout()
        controls.addWidget(self.button("刷新", "Refresh", self.refresh_devices))
        controls.addWidget(self.button("连接", "Connect", self.read_device, "selected"))
        controls.addStretch()
        self.pick_layout.addLayout(controls)
        self.device_table = self.make_table(4)
        self.device_table.itemSelectionChanged.connect(self.update_actions)
        self.device_table.cellDoubleClicked.connect(lambda *_: self.read_device())
        self.pick_layout.addWidget(self.device_table, 1)
        self.flow.addWidget(pick)
        manager = QWidget()
        layout = QVBoxLayout(manager)
        bar = QHBoxLayout()
        self.identity = QLabel()
        bar.addWidget(self.identity, 1)
        bar.addWidget(self.button("刷新设备信息", "Refresh device info", self.read_device, "selected"))
        bar.addWidget(self.button("断开连接", "Disconnect", self.refresh_devices))
        layout.addLayout(bar)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        self.tab_names = []
        for key, zh, en in [("firmware", "固件管理", "Firmware"), ("devices", "设备信息", "Device information")]:
            if key in self.page_keys:
                self.tabs.addTab(getattr(self, "page_" + key)(), zh)
                self.tab_names.append((zh, en))
        self.flow.addWidget(manager)
        if "firmware" in self.page_keys:
            self.market = self.create_market()
            self.pick_layout.addWidget(self.market, 2)
        if "help" in self.page_keys:
            self.help_dialog = QDialog(self)
            self.help_dialog.setMinimumWidth(440)
            help_layout = QVBoxLayout(self.help_dialog)
            self.help_text = QLabel()
            self.help_text.setWordWrap(True)
            help_layout.addWidget(self.help_text)
            help_actions = QHBoxLayout()
            help_actions.addWidget(self.button("查询操作结果", "Look up operation", self.lookup_operation))
            help_actions.addWidget(self.button("复制诊断信息", "Copy diagnostics", self.copy_diagnostics, "always"))
            if brand.get("help_url"):
                help_actions.addWidget(self.button("帮助网页", "Help website",
                    lambda: QDesktopServices.openUrl(QUrl(brand["help_url"])), "always"))
            help_actions.addWidget(self.button("关闭", "Close", self.help_dialog.accept, "always"))
            help_layout.addLayout(help_actions)
            header.insertWidget(2, self.button("帮助", "Help", self.show_help, "always"))
        if not self.tab_names:
            help_page = QWidget()
            help_layout = QVBoxLayout(help_page)
            help_layout.addWidget(self.label("关于与帮助", "About & help"))
            help_layout.addWidget(QLabel(f"{brand['name']} {VERSION} · CDM {client.version}"))
            help_layout.addStretch()
            self.flow.addWidget(help_page)
            self.flow.setCurrentWidget(help_page)
        self.status = QLabel()
        self.status.setWordWrap(True)
        outer.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setFixedHeight(4)
        self.progress.hide()
        outer.addWidget(self.progress)
        self.setCentralWidget(central)
        self.language.currentIndexChanged.connect(self.retranslate)
        self.setStyleSheet("QLabel#title {font-weight:bold;font-size:16px} "
                           "QGroupBox {font-weight:bold} QListWidget::item:selected, "
                           "QTableWidget::item:selected {background:" + brand["theme_color"] + ";color:white}")
        self.retranslate()
        self.scan_timer = QTimer(self)
        self.scan_timer.timeout.connect(self.poll_devices)
        self.scan_timer.start(5000)
        QTimer.singleShot(0, self.initialize)

    @staticmethod
    def make_table(columns):
        table = QTableWidget(0, columns)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().hide()
        return table

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
        self.info_text = QLabel()
        self.info_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.info_text)
        self.term_group = QGroupBox()
        term = QVBoxLayout(self.term_group)
        self.channel_layout = QHBoxLayout()
        term.addLayout(self.channel_layout)
        controls = QHBoxLayout()
        controls.addWidget(self.button("刷新状态", "Refresh states", self.get_termination, "identified"))
        controls.addWidget(self.button("应用设置", "Apply changes", self.set_termination, "write_channel"))
        controls.addStretch()
        term.addLayout(controls)
        self.term_status = QLabel()
        term.addWidget(self.term_status)
        layout.addWidget(self.term_group)
        mode_bar = QHBoxLayout()
        self.mode_choice = QComboBox()
        mode_bar.addWidget(self.mode_choice)
        self.mode_button = self.button("切换 USB 模式…", "Change USB mode…", self.change_mode, "mode")
        mode_bar.addWidget(self.mode_button)
        mode_bar.addStretch()
        layout.addLayout(mode_bar)
        layout.addStretch()
        return page

    def page_firmware(self):
        page = QWidget()
        self.firmware_layout = QVBoxLayout(page)
        self.installed_group = QGroupBox()
        layout = QVBoxLayout(self.installed_group)
        self.table = self.make_table(4)
        self.table.itemSelectionChanged.connect(self.update_actions)
        self.table.cellDoubleClicked.connect(lambda *_: self.choose_for_slot())
        layout.addWidget(self.table)
        row = QHBoxLayout()
        row.addWidget(self.button("为选中槽位选择固件…", "Choose firmware for slot…", self.choose_for_slot, "slot"))
        row.addWidget(self.button("切换到选中固件", "Switch to selected firmware", self.switch_firmware, "firmware"))
        row.addWidget(self.button("卸载选中固件…", "Uninstall selected firmware…", self.uninstall_selected, "firmware"))
        row.addStretch()
        layout.addLayout(row)
        self.firmware_layout.addWidget(self.installed_group, 1)
        return page

    def create_market(self):
        box = QGroupBox()
        layout = QVBoxLayout(box)
        row = QHBoxLayout()
        row.addWidget(self.button("导入离线固件包", "Import offline firmware", self.import_firmware))
        row.addWidget(self.button("刷新固件市场", "Refresh catalog", self.refresh_catalog))
        if self.brand.get("online_firmware"):
            self.channel_choice = QComboBox()
            self.channel_choice.addItems(["stable", "beta"])
            row.addWidget(self.channel_choice)
            self.channel_choice.currentTextChanged.connect(self.select_channel)
            row.addWidget(self.button("检查在线固件…", "Check online firmware…", self.check_online))
        row.addStretch()
        layout.addLayout(row)
        filters = QHBoxLayout()
        self.versions = QComboBox()
        filters.addWidget(self.versions)
        self.compatible = QCheckBox()
        self.texts.append((self.compatible, "只看可安装", "Compatible only"))
        filters.addWidget(self.compatible)
        filters.addStretch()
        layout.addLayout(filters)
        self.catalog = QListWidget()
        self.catalog.setViewMode(QListWidget.ViewMode.IconMode)
        self.catalog.setMovement(QListWidget.Movement.Static)
        self.catalog.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.catalog.setGridSize(QSize(178, 60))
        self.catalog.setWordWrap(True)
        self.catalog.setUniformItemSizes(True)
        self.catalog.setStyleSheet("QListWidget::item {border:1px solid #ccd1d4; border-radius:4px; margin:2px;}")
        self.catalog.currentRowChanged.connect(self.catalog_changed)
        self.versions.currentIndexChanged.connect(self.render_catalog)
        self.compatible.toggled.connect(self.render_catalog)
        layout.addWidget(self.catalog, 1)
        self.reason = QLabel()
        self.reason.setWordWrap(True)
        layout.addWidget(self.reason)
        self.install_button = self.button("安装选中固件…", "Install selected firmware…", self.preview_install, "catalog")
        layout.addWidget(self.install_button, 0, Qt.AlignmentFlag.AlignLeft)
        return box

    def show_help(self):
        self.help_dialog.setWindowTitle(self.tr2("帮助", "Help"))
        self.help_text.setText(f"{self.brand['name']} {VERSION}  ·  CDM {self.client.version}\n\n" + self.tr2(
            "选择设备后点击连接。在固件市场选择固件可查看安装预览。写入时请保持供电，结果未知时请重新查询设备。",
            "Select a device and connect. Choose firmware in the catalog to preview installation. Keep power connected during writes. Query the device again if the result is unknown."))
        self.help_dialog.exec()

    def retranslate(self):
        for obj, zh, en in self.texts:
            obj.setText(self.tr2(zh, en))
        for index, names in enumerate(self.tab_names):
            self.tabs.setTabText(index, self.tr2(*names))
        self.device_table.setHorizontalHeaderLabels([self.tr2(*names) for names in
            [("设备", "Device"), ("USB 节点", "USB node"), ("状态", "State"), ("驱动", "Driver")]])
        self.render_devices()
        if hasattr(self, "term_group"):
            self.term_group.setTitle(self.tr2("终端电阻", "Termination"))
        if hasattr(self, "market"):
            self.market.setTitle(self.tr2("固件市场", "Firmware catalog"))
            self.installed_group.setTitle(self.tr2("已安装固件", "Installed firmware"))
            self.table.setHorizontalHeaderLabels([self.tr2("固件", "Firmware"), self.tr2("版本", "Version"), self.tr2("状态", "State"), self.tr2("大小 / 容量", "Size / capacity")])
            self.update_versions()
            self.render_firmware()
            self.render_catalog()
        self.settings.parent.mkdir(parents=True, exist_ok=True)
        self.settings.write_text(json.dumps({"language": self.language.currentIndex()}), encoding="utf-8")
        self.update_actions()

    def selected_device(self):
        index = self.device_table.currentRow()
        if 0 <= index < len(self.device_rows):
            return self.device_rows[index]

    def update_actions(self):
        selected = self.selected_device()
        identified = bool(self.device and self.uid)
        can_write = identified and not self.uncertain
        index = self.table.currentRow() if hasattr(self, "table") else -1
        row = self.selected_firmware()
        for button, needs in self.actions:
            allowed = {"always": True, "ready": self.ready,
                "selected": self.ready and selected and selected.get("connectable", True),
                "identified": identified, "write_channel": can_write and bool(self.changed_channels()),
                "mode": can_write and hasattr(self, "mode_choice") and self.mode_choice.count() > 0,
                "slot": can_write and index >= 0,
                "firmware": can_write and 0 <= index < len(self.firmware_rows) and not self.firmware_rows[index]["running"],
                "catalog": can_write and row and row.get("availability") == "Available"}.get(needs)
            button.setEnabled(bool(allowed) and self.job is None)
        self.device_table.setEnabled(self.ready and self.job is None)
        self.language.setEnabled(self.job is None)
        for channel, box in self.checks.items():
            box.setEnabled(can_write and channel in self.term_states and self.job is None)
        if hasattr(self, "market"):
            self.install_button.setVisible(identified)
            self.compatible.setEnabled(identified and self.job is None)
            self.versions.setEnabled(self.job is None)
            self.table.setEnabled(self.job is None)
            if hasattr(self, "channel_choice"):
                self.channel_choice.setEnabled(self.job is None)
            self.catalog.setEnabled(self.job is None)
            if 0 <= index < len(self.firmware_rows):
                self.install_button.setText(self.tr2("替换选中槽位的固件…", "Replace firmware in selected slot…"))
            elif index >= len(self.firmware_rows) and index >= 0:
                self.install_button.setText(self.tr2("安装到选中空槽…", "Install into selected empty slot…"))
            else:
                self.install_button.setText(self.tr2("安装选中固件…", "Install selected firmware…"))

    def start(self, action, success, writing=False, quiet=False):
        if self.job is not None:
            return
        if not quiet:
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
                if not quiet:
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
        if hasattr(self, "term_status"):
            self.term_status.clear()
        self.diagnostic = {"ui_version": VERSION, "cdm_version": self.client.version, "code": code,
                           "message": str(error), "device": self.device, "uid": self.uid,
                           "operation_id": getattr(error, "operation_id", None)}
        guidance = ERROR_HELP.get(code, ("操作失败。请刷新设备，检查驱动或连接，并复制诊断信息供排查。", "Operation failed. Refresh the device, check drivers/connections and copy diagnostics."))
        self.status.setText(f"{code} · {self.tr2(*guidance)}")

    def initialize(self):
        def ready(_):
            self.ready = True
            if self.tab_names:
                self.refresh_devices()
        self.start(self.client.handshake, ready)

    def clear_session(self):
        self.device = self.uid = self.plan = None
        self.firmware_rows = []
        self.empty_slots = []
        self.max_slots = None
        if hasattr(self, "mode_choice"):
            self.mode_choice.clear()
        self.catalog_rows = []
        self.channels = 0
        self.term_states.clear()
        self.identity.clear()
        for box in self.checks.values():
            self.channel_layout.removeWidget(box)
            box.deleteLater()
        self.checks.clear()
        if hasattr(self, "market"):
            self.catalog.clear()
            self.render_firmware()
            self.pick_layout.addWidget(self.market, 2)
        self.flow.setCurrentIndex(0)
        self.update_actions()

    def render_devices(self):
        self.device_table.setRowCount(len(self.device_rows))
        for index, row in enumerate(self.device_rows):
            name = row.get("product_name") or row.get("name") or row["id"]
            state = self.tr2("可连接", "Ready") if row.get("connectable", True) else self.tr2("不可连接", "Unavailable")
            for column, value in enumerate((name, row.get("usb_node_label") or row.get("location"), state,
                                            row.get("driver_version") or row.get("driver_status"))):
                self.device_table.setItem(index, column, QTableWidgetItem(str(value or "—")))

    def refresh_devices(self):
        self.clear_session()
        self.device_rows = []
        self.render_devices()
        def done(rows):
            self.device_rows = rows
            self.render_devices()
            if len(rows) == 1:
                self.device_table.selectRow(0)
            self.status.setText(self.tr2(f"发现 {len(rows)} 台设备", f"Found {len(rows)} device(s)"))
            if hasattr(self, "market"):
                self.refresh_catalog()
        self.start(self.client.devices, done)

    def poll_devices(self):
        if (not self.ready or self.job or self.flow.currentIndex() != 0 or
                not self.isVisible() or QApplication.activeModalWidget()):
            return
        def done(rows):
            if rows == self.device_rows:
                return
            previous = (self.selected_device() or {}).get("id")
            self.device_rows = rows
            self.device_table.clearSelection()
            self.device_table.setCurrentCell(-1, -1)
            self.render_devices()
            for i, row in enumerate(rows):
                if row["id"] == previous or len(rows) == 1:
                    self.device_table.selectRow(i)
                    break
            self.status.setText(self.tr2(f"发现 {len(rows)} 台设备", f"Found {len(rows)} device(s)"))
        self.start(self.client.devices, done, quiet=True)

    def read_device(self):
        row = self.selected_device()
        if not row or not row.get("connectable", True) or self.job:
            return
        device = row["id"]
        tab = self.tabs.currentIndex() if self.uid else 0
        expected_uid = self.uid
        self.clear_session()
        def done(data):
            view = device_view(data)
            if not view["uid"] or (expected_uid and expected_uid != view["uid"]):
                raise CliError("TARGET_MISMATCH", "Device identity changed")
            self.device, self.uid, self.channels = device, view["uid"], view["channels"]
            self.uncertain = False
            self.firmware_rows = view["firmware"]
            self.empty_slots = data.get("empty_slots", [])
            self.max_slots = data.get("max_slots")
            self.identity.setText(f"{row.get('name') or device}    UID: {self.uid}")
            self.flow.setCurrentIndex(1)
            self.tabs.setCurrentIndex(tab)
            if hasattr(self, "term_group"):
                for mode in data.get("modes", []):
                    self.mode_choice.addItem(mode.get("label") or mode["mode"], mode["mode"])
                self.mode_choice.setVisible(bool(self.mode_choice.count()))
                self.mode_button.setVisible(bool(self.mode_choice.count()))
                running = next((f for f in self.firmware_rows if f["running"]), {})
                self.info_text.setText(f"UID: {self.uid}    ·    {self.channels} CH    ·    {running.get('name', '—')} {running.get('version', '')}")
                for ch in range(1, self.channels + 1):
                    box = QCheckBox(f"CH{ch}")
                    self.checks[ch] = box
                    self.channel_layout.addWidget(box)
                    box.stateChanged.connect(self.update_actions)
                self.term_status.clear()
            if hasattr(self, "market"):
                self.firmware_layout.addWidget(self.market, 2)
                self.render_firmware()
                self.refresh_catalog(after=self.get_termination)
            else:
                self.get_termination()
        self.start(lambda: self.client.info(device), done)

    def render_firmware(self):
        count = len(self.firmware_rows)
        title = self.tr2("固件槽位", "Firmware slots")
        self.installed_group.setTitle(f"{title} · {count}/{self.max_slots}" if self.max_slots else title)
        self.table.setRowCount(count + len(self.empty_slots))
        for i, row in enumerate(self.firmware_rows):
            for j, text in enumerate([row["name"], row["version"], self.tr2("运行中", "Running") if row["running"] else self.tr2("已安装", "Installed"), f"{row['size_kib']} KiB" if row.get("size_kib") else "—"]):
                self.table.setItem(i, j, QTableWidgetItem(str(text)))
        for i, slot in enumerate(self.empty_slots):
            for j, value in enumerate([self.tr2(f"空槽 {i+1}", f"Empty slot {i+1}"), "—", self.tr2("可安装", "Available"), f"{slot['capacity_kib']} KiB"]):
                self.table.setItem(count+i, j, QTableWidgetItem(value))

    def selected_firmware(self):
        index = self.catalog.currentRow() if hasattr(self, "catalog") else -1
        return self.visible_catalog[index] if 0 <= index < len(self.visible_catalog) else None

    def refresh_catalog(self, checked=False, *, after=None):
        device = self.device
        def done(rows):
            seen = set()
            self.catalog_rows = []
            for row in rows:
                key = (row["id"], row["version"], row.get("sha256"), row["availability"])
                if key not in seen:
                    seen.add(key)
                    self.catalog_rows.append(row)
            self.update_versions()
            self.render_catalog()
            if after:
                after()
        channel = self.release_channel
        self.start(lambda: self.client.catalog(device) if channel == "stable" else self.client.catalog(device, channel), done)

    def update_versions(self):
        previous = self.versions.currentData()
        self.versions.blockSignals(True)
        self.versions.clear()
        self.versions.addItem(self.tr2("全部版本", "All versions"), None)
        for version in dict.fromkeys(row["version"] for row in self.catalog_rows):
            self.versions.addItem(version, version)
        self.versions.setCurrentIndex(max(0, self.versions.findData(previous)))
        self.versions.blockSignals(False)

    def render_catalog(self, *_):
        previous = self.selected_firmware()
        self.catalog.clear()
        self.visible_catalog = [row for row in self.catalog_rows
                                if (not self.versions.currentData() or row["version"] == self.versions.currentData())
                                and (not self.uid or not self.compatible.isChecked() or row["availability"] == "Available")]
        for row in self.visible_catalog:
            item = QListWidgetItem(f"{row['name']}\n{row['version']}")
            item.setSizeHint(QSize(174, 54))
            item.setToolTip(f"{row['name']} · {row['version']}")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.catalog.addItem(item)
        if self.visible_catalog:
            self.catalog.setCurrentRow(self.visible_catalog.index(previous) if previous in self.visible_catalog else 0)
        self.catalog_changed()

    def catalog_changed(self):
        self.plan = None
        row = self.selected_firmware() or {}
        key = self.tr2("summary_zh", "summary_en")
        summary = (row.get("presentation") or {}).get(key, "")
        if not self.uid:
            state = self.tr2("连接设备后确认兼容性", "Connect a device to check compatibility")
        elif row.get("availability") == "Available":
            state = self.tr2("可安装", "Available")
        else:
            state = row.get("reason") or self.tr2("不可安装", "Unavailable")
        self.reason.setText(f"{state}  ·  {summary}" if summary else state)
        self.update_actions()

    def import_firmware(self):
        path, _ = QFileDialog.getOpenFileName(self, self.tr2("选择完整固件发布包", "Select complete firmware release"), "", "ZIP (*.zip)")
        if path:
            channel = self.release_channel
            self.start(lambda: self.client.import_zip(path, channel), lambda _: self.refresh_catalog())

    def select_channel(self, channel):
        self.release_channel = channel
        self.catalog_rows.clear()
        self.render_catalog()
        self.refresh_catalog()

    def check_online(self):
        channel = self.release_channel
        def checked(info):
            version = info.get("latest_online")
            if not info.get("online_checked") or not version:
                raise CliError("INVALID_RESPONSE", "Missing online firmware version")
            if info.get("cached"):
                self.status.setText(self.tr2(f"{version} 已在本机", f"{version} is already available locally"))
                return
            if self.confirm(self.tr2(f"下载 {channel} 固件包 {version}？", f"Download {channel} firmware package {version}?")):
                self.start(lambda: self.client.download(channel, version), lambda _: self.refresh_catalog())
        self.start(lambda: self.client.check_online(channel), checked)

    def lookup_operation(self):
        default = self.diagnostic.get("operation_id") or getattr(self.client, "last_operation_id", None) or ""
        identifier, ok = QInputDialog.getText(self.help_dialog, self.tr2("查询操作结果", "Look up operation"),
                                              self.tr2("操作编号", "Operation ID"), text=default)
        if ok and identifier.strip():
            self.start(lambda: self.client.operation(identifier.strip()), lambda state:
                       QMessageBox.information(self.help_dialog, self.tr2("操作记录", "Operation record"),
                       f"{identifier.strip()}\n{state}\n" + self.tr2("请刷新设备核对当前状态。", "Refresh the device to verify its current state.")))

    def change_mode(self):
        device, uid, mode = self.device, self.uid, self.mode_choice.currentData()
        if self.job or self.uncertain or not uid or not mode:
            return
        if self.confirm(f"UID: {uid}\nUSB · {self.mode_choice.currentText()}\n" + self.tr2(
                "模式切换后请重新连接并核对设备。", "Reconnect and check the device after changing mode.")):
            def acknowledged(_):
                self.refresh_devices()
                QMessageBox.information(self, self.tr2("USB 模式", "USB mode"), self.tr2(
                    "设备已应答。重新枚举后，请连接设备核对实际模式。",
                    "Device acknowledged the request. Reconnect after enumeration to check the actual mode."))
            self.start(lambda: self.client.set_mode(device, uid, mode), acknowledged, writing=True)

    def uninstall_selected(self):
        index = self.table.currentRow()
        if self.job or self.uncertain or not self.uid or not 0 <= index < len(self.firmware_rows):
            return
        target = self.firmware_rows[index]
        if target["running"]:
            return
        device, uid, firmware = self.device, self.uid, target["id"]
        def previewed(_):
            if self.confirm(f"UID: {uid}\n" + self.tr2("卸载设备上的固件？", "Uninstall firmware from this device?") +
                            f"\n{target['name']} · {target['version']}\n{firmware}"):
                self.start(lambda: self.client.uninstall(device, uid, firmware, preview=False),
                           lambda _: self.read_device(), writing=True)
        self.start(lambda: self.client.uninstall(device, uid, firmware, preview=True), previewed)

    def confirm(self, text):
        return QMessageBox.question(self, self.tr2("确认设备操作", "Confirm device operation"), text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes

    def choose_for_slot(self):
        if not self.uid or self.job or self.uncertain or self.table.currentRow() < 0:
            return
        candidates = [i for i, row in enumerate(self.visible_catalog) if row["availability"] == "Available"]
        if not candidates:
            self.status.setText(self.tr2("当前筛选没有兼容固件，请更改筛选或导入固件包。",
                                         "No compatible firmware in this filter. Change the filter or import a package."))
            return
        labels = [f"{n+1}. {self.visible_catalog[i]['name']} · {self.visible_catalog[i]['version']}"
                  for n, i in enumerate(candidates)]
        choice, ok = QInputDialog.getItem(self, self.tr2("选择固件", "Choose firmware"),
                                         self.tr2("兼容固件", "Compatible firmware"), labels, 0, False)
        if ok:
            self.catalog.setCurrentRow(candidates[labels.index(choice)])
            self.preview_install()

    def preview_install(self):
        row = self.selected_firmware()
        if not row or not self.uid or self.job or self.uncertain or row["availability"] != "Available":
            return
        device, uid = self.device, self.uid
        index = self.table.currentRow()
        count = len(self.firmware_rows)
        if index < 0 and self.max_slots and count >= self.max_slots:
            choices = [f"{i+1} · {item['name']} {item['version']}" for i, item in enumerate(self.firmware_rows)]
            choice, ok = QInputDialog.getItem(self, self.tr2("槽位已满", "All slots occupied"),
                self.tr2("选择要替换的固件", "Choose firmware to replace"), choices, 0, False)
            if not ok:
                return
            index = choices.index(choice)
            self.table.selectRow(index)
        options = {}
        destination = self.tr2("自动选择空闲位置", "Automatically selected free space")
        if index >= count and index-count < len(self.empty_slots):
            options["target_slot"] = self.empty_slots[index-count]["id"]
            destination = self.tr2(f"空槽 {index-count+1}", f"Empty slot {index-count+1}")
        elif 0 <= index < count:
            old = self.firmware_rows[index]
            options["replace"] = old["id"]
            destination = self.tr2("将替换", "Will replace") + f" {old['name']} · {old['version']} · {old['id']}"
        if self.release_channel != "stable":
            options["channel"] = self.release_channel
        def done(data):
            self.plan = plan_view(data["plan"])
            plan = self.plan
            text = self.tr2("即将安装固件。保持 USB 连接和供电。\n", "Install firmware. Keep USB and power connected.\n")
            text += f"UID: {uid}\n{destination}\n{plan['name']} · {plan['firmware_version']}\n{plan['size_bytes']} bytes\n"
            text += self.tr2("保留其他固件；安装后不会自动切换。继续？", "Other firmware is preserved. Installation does not switch the running firmware. Continue?")
            if self.confirm(text):
                self.start(lambda: self.client.install(device, uid, row["id"], row["version"], plan["plan_id"], **options),
                           lambda _: self.read_device(), writing=True)
            self.plan = None
        self.start(lambda: self.client.install(device, uid, row["id"], row["version"], **options), done)

    def switch_firmware(self):
        index = self.table.currentRow()
        if index < 0:
            return
        row = self.firmware_rows[index]
        device, uid = self.device, self.uid
        if self.confirm(self.tr2("切换后设备会重新枚举。\n", "The device will reconnect after switching.\n") + f"UID: {uid}\n{row['name']} {row['version']}"):
            self.start(lambda: self.client.switch(device, uid, row["id"]), lambda _: self.read_device(), writing=True)

    def get_termination(self):
        if not self.checks or not self.device:
            return
        device = self.device
        channels = tuple(self.checks)
        self.term_states.clear()
        self.term_status.setText(self.tr2("读取中…", "Reading…"))
        def read():
            states = {}
            for ch in channels:
                value = self.client.termination(device, ch)
                if value.get("channel") != ch or type(value.get("enabled")) is not bool:
                    raise CliError("INVALID_RESPONSE", "Unexpected termination response")
                states[ch] = value["enabled"]
            return states
        def done(states):
            self.term_states = states
            for ch, enabled in states.items():
                self.checks[ch].setChecked(enabled)
            self.term_status.setText(self.tr2("已读取设备状态", "Device states read"))
        self.start(read, done)

    def changed_channels(self):
        return {ch: box.isChecked() for ch, box in self.checks.items()
                if ch in self.term_states and self.term_states[ch] != box.isChecked()}

    def set_termination(self):
        changes = self.changed_channels()
        device, uid = self.device, self.uid
        if not changes or not uid or self.uncertain:
            return
        lines = [f"CH{ch} · " + (self.tr2("开启", "Enabled") if enabled else self.tr2("关闭", "Disabled"))
                 for ch, enabled in changes.items()]
        if not self.confirm("\n".join([f"UID: {uid}", *lines])):
            return
        def apply():
            for ch, enabled in changes.items():
                self.client.termination(device, ch, uid, enabled)
                actual = self.client.termination(device, ch)
                if actual.get("channel") != ch or actual.get("enabled") is not enabled:
                    raise CliError("OUTCOME_UNKNOWN", f"CH{ch}: readback mismatch")
        self.start(apply, lambda _: self.get_termination(), writing=True)

    def copy_diagnostics(self):
        QApplication.clipboard().setText(json.dumps(self.diagnostic or {"ui_version": VERSION, "cdm_version": self.client.version}, ensure_ascii=False, indent=2))

    def closeEvent(self, event):
        if self.job is not None:
            self.status.setText(self.tr2("操作进行中，请等待结果。关闭界面不会取消设备操作。", "An operation is running. Wait for its result; closing the UI does not cancel device work."))
            event.ignore()
        else:
            event.accept()
