"""
SZTU 校园网登录助手 - 现代化极简图形界面版
基于 Srun 深澜认证协议
"""

import sys
import os
import json
import time
import platform
import subprocess
import winreg

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QCheckBox, QComboBox,
    QSpinBox, QGroupBox, QFormLayout, QFrame, QMessageBox,
    QSystemTrayIcon, QMenu, QAction, QToolButton, QSizePolicy,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize
from PyQt5.QtGui import QFont, QTextCursor, QIcon, QClipboard, QPainter, QPixmap

# Determine base paths for PyInstaller compatibility
if getattr(sys, 'frozen', False):
    BUNDLE_DIR = sys._MEIPASS          # bundled resources (icon, modules)
    SCRIPT_DIR = os.path.dirname(sys.executable)  # where the .exe lives
else:
    BUNDLE_DIR = os.path.dirname(os.path.abspath(__file__))
    SCRIPT_DIR = BUNDLE_DIR

if BUNDLE_DIR not in sys.path:
    sys.path.insert(0, BUNDLE_DIR)

from SztuSrunLogin.LoginManager import LoginManager

CONFIG_DIR = os.path.join(os.environ.get("APPDATA", SCRIPT_DIR), "SZTUCampusLogin")
os.makedirs(CONFIG_DIR, exist_ok=True)
CONFIG_FILE = os.path.join(CONFIG_DIR, ".login_config.json")
ICON_PATH = os.path.join(BUNDLE_DIR, "icon.png")
ARROW_PATH = os.path.join(BUNDLE_DIR, "down_arrow.png").replace("\\", "/")

ISP_OPTIONS = [
    ("中国联通 (cucc)", "@cucc"),
    ("中国移动 (cmcc)", "@cmcc"),
    ("中国电信 (ctcc)", "@ctcc"),
    ("校园网 (无后缀)", ""),
]

AUTOSTART_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
AUTOSTART_REG_NAME = "SZTUCampusLogin"


def _get_autostart_command():
    """Build the command string that Windows will run on startup."""
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if not os.path.isfile(pythonw):
        pythonw = sys.executable
    script = os.path.join(SCRIPT_DIR, "gui_app.py")
    return f'"{pythonw}" "{script}"'


def is_autostart_enabled():
    """Check if the autostart registry entry exists."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, AUTOSTART_REG_KEY, 0, winreg.KEY_READ
        )
        winreg.QueryValueEx(key, AUTOSTART_REG_NAME)
        winreg.CloseKey(key)
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return False


def set_autostart(enable):
    """Add or remove the autostart registry entry."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, AUTOSTART_REG_KEY, 0, winreg.KEY_SET_VALUE
        )
        if enable:
            winreg.SetValueEx(
                key, AUTOSTART_REG_NAME, 0, winreg.REG_SZ, _get_autostart_command()
            )
        else:
            try:
                winreg.DeleteValue(key, AUTOSTART_REG_NAME)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        return True
    except OSError:
        return False


class LogStream:
    """Redirects print() output to a Qt signal callback."""

    def __init__(self, callback):
        self.callback = callback

    def write(self, text):
        if text and text.strip():
            self.callback(text.rstrip())

    def flush(self):
        pass


class LoginWorker(QThread):
    """Runs the login process in a background thread to keep the GUI responsive."""

    log_signal = pyqtSignal(str)
    result_signal = pyqtSignal(bool, str)

    def __init__(self, username, password, suffix, server_ip):
        super().__init__()
        self.username = username
        self.password = password
        self.suffix = suffix
        self.server_ip = server_ip

    def run(self):
        lm = LoginManager(
            url_login_page=f"http://{self.server_ip}/srun_portal_pc?ac_id=1&theme=cucc",
            url_get_challenge_api=f"http://{self.server_ip}/cgi-bin/get_challenge",
            url_login_api=f"http://{self.server_ip}/cgi-bin/srun_portal",
        )

        old_stdout = sys.stdout
        sys.stdout = LogStream(lambda msg: self.log_signal.emit(msg))
        try:
            lm.login(self.username, self.password, suffix=self.suffix)
            self.result_signal.emit(True, "登录成功")
        except Exception as e:
            self.log_signal.emit(f"错误: {e}")
            self.result_signal.emit(False, f"登录失败: {e}")
        finally:
            sys.stdout = old_stdout


class PingWorker(QThread):
    """Checks internet connectivity via ping in a background thread."""

    result_signal = pyqtSignal(bool)

    def __init__(self, testip="114.114.114.114"):
        super().__init__()
        self.testip = testip

    def run(self):
        try:
            if platform.system().lower() == "windows":
                cmd = ["ping", "-n", "3", "-w", "1500", self.testip]
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0  # SW_HIDE
                result = subprocess.run(
                    cmd,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=10,
                    startupinfo=startupinfo,
                    creationflags=0x08000000,  # CREATE_NO_WINDOW
                )
            else:
                cmd = ["ping", "-c", "3", "-W", "2", self.testip]
                result = subprocess.run(
                    cmd,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=10,
                )
            self.result_signal.emit(result.returncode == 0)
        except Exception:
            self.result_signal.emit(False)


STYLESHEET = """
/* 全局主窗口背景与基础字体 */
QMainWindow {
    background-color: #f8fafc;
}
QWidget {
    font-family: "Segoe UI", "Microsoft YaHei UI", "PingFang SC", sans-serif;
    color: #1e293b;
}

/* 卡片容器样式 */
QFrame.CardFrame {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
}

/* 卡片标题 */
QLabel.CardTitle {
    font-size: 13px;
    font-weight: 700;
    color: #334155;
    padding-bottom: 2px;
}

/* 标签通用样式 */
QLabel.FormLabel {
    font-size: 13px;
    font-weight: 600;
    color: #475569;
}

/* 输入框与选择器 */
QLineEdit, QComboBox, QSpinBox {
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 5px 8px;
    background-color: #ffffff;
    font-size: 13px;
    color: #0f172a;
    selection-background-color: #1a73e8;
}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover {
    border-color: #94a3b8;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    border: 1.5px solid #1a73e8;
    background-color: #ffffff;
}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {
    background-color: #f1f5f9;
    color: #94a3b8;
    border-color: #e2e8f0;
}

/* 下拉菜单样式与倒三角图标 */
QComboBox {
    padding-right: 22px;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 22px;
    border-left-width: 0px;
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
}
QComboBox::down-arrow {
    image: url({ARROW_PATH});
    width: 10px;
    height: 10px;
    margin-right: 6px;
}
QComboBox QAbstractItemView {
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    background-color: #ffffff;
    selection-background-color: #eff6ff;
    selection-color: #1a73e8;
    padding: 4px;
    outline: none;
}

/* 微调框样式 */
QSpinBox::up-button, QSpinBox::down-button {
    width: 16px;
    background: transparent;
    border: none;
}

/* 复选框样式 */
QCheckBox {
    font-size: 13px;
    color: #334155;
    spacing: 6px;
}
QCheckBox::indicator {
    width: 15px;
    height: 15px;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    background-color: #ffffff;
}
QCheckBox::indicator:hover {
    border-color: #1a73e8;
}
QCheckBox::indicator:checked {
    background-color: #1a73e8;
    border-color: #1a73e8;
    image: none;
}

/* 主操作按钮：登录 */
QPushButton#login_btn {
    background-color: #1a73e8;
    color: #ffffff;
    border: none;
    border-radius: 8px;
    font-size: 14px;
    font-weight: bold;
    padding: 8px 16px;
}
QPushButton#login_btn:hover {
    background-color: #1557b0;
}
QPushButton#login_btn:pressed {
    background-color: #0d47a1;
}
QPushButton#login_btn:disabled {
    background-color: #bfdbfe;
    color: #ffffff;
}

/* 次要操作按钮：停止 */
QPushButton#stop_btn {
    background-color: #ffffff;
    color: #475569;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 600;
    padding: 8px 16px;
}
QPushButton#stop_btn:hover {
    background-color: #f1f5f9;
    color: #1e293b;
    border-color: #94a3b8;
}
QPushButton#stop_btn:pressed {
    background-color: #e2e8f0;
}
QPushButton#stop_btn:disabled {
    background-color: #f8fafc;
    color: #cbd5e1;
    border-color: #f1f5f9;
}

/* 辅助小按钮（清空、复制） */
QPushButton.SmallToolBtn {
    background-color: #f1f5f9;
    color: #475569;
    border: 1px solid #e2e8f0;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 500;
    padding: 2px 7px;
}
QPushButton.SmallToolBtn:hover {
    background-color: #e2e8f0;
    color: #0f172a;
}
QPushButton.SmallToolBtn:pressed {
    background-color: #cbd5e1;
}

/* 控制台日志文本框 */
QTextEdit#log_text {
    border: 1px solid #1e293b;
    border-radius: 8px;
    background-color: #0f172a;
    color: #e2e8f0;
    padding: 6px;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 12px;
    line-height: 1.35;
}

/* 状态胶囊徽标基础 */
QLabel.StatusBadge {
    border-radius: 11px;
    padding: 2px 9px;
    font-size: 12px;
    font-weight: 600;
}
""".replace("{ARROW_PATH}", ARROW_PATH)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.auto_reconnect_timer = None
        self.is_connected = False
        self.login_worker = None
        self.ping_worker = None
        self._login_in_progress = False

        self._init_ui()
        self._init_tray_icon()
        self._load_config()

    # ------------------------------------------------------------------ #
    #  UI Construction
    # ------------------------------------------------------------------ #

    def _init_ui(self):
        self.setWindowTitle("SZTU 校园网登录助手")
        # 固定舒适的默认窗口尺寸
        self.setFixedSize(480, 640)
        self.setStyleSheet(STYLESHEET)
        if os.path.isfile(ICON_PATH):
            self.setWindowIcon(QIcon(ICON_PATH))

        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        # ============================================================== #
        #  Top Header Bar (Logo + Title + Status Badge)
        # ============================================================== #
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(2, 0, 2, 0)
        header_layout.setSpacing(10)

        # Left: App Title & Subtitle
        title_box = QVBoxLayout()
        title_box.setSpacing(1)

        title_lbl = QLabel("SZTU 校园网登录助手—桂辰改进版")
        title_lbl.setFont(QFont("Segoe UI", 13, QFont.Bold))
        title_lbl.setStyleSheet("color: #1a73e8; margin: 0px; padding: 0px;")
        title_box.addWidget(title_lbl)

        subtitle_lbl = QLabel("深圳技术大学 · Srun 认证客户端")
        subtitle_lbl.setStyleSheet("color: #64748b; font-size: 11px;")
        title_box.addWidget(subtitle_lbl)

        header_layout.addLayout(title_box)
        header_layout.addStretch()

        # Right: Connection Status Badge (Pill)
        self.status_badge = QLabel("● 未连接")
        self.status_badge.setProperty("class", "StatusBadge")
        self._set_status_badge("disconnected", "● 未连接")
        header_layout.addWidget(self.status_badge, alignment=Qt.AlignVCenter)

        root.addWidget(header_widget)

        # ============================================================== #
        #  Card 1: 登录凭据 (Authentication Card)
        # ============================================================== #
        auth_card = QFrame()
        auth_card.setProperty("class", "CardFrame")
        auth_layout = QVBoxLayout(auth_card)
        auth_layout.setContentsMargins(14, 10, 14, 10)
        auth_layout.setSpacing(8)

        card1_title = QLabel("账号认证")
        card1_title.setProperty("class", "CardTitle")
        auth_layout.addWidget(card1_title)

        form_layout = QFormLayout()
        form_layout.setSpacing(8)
        form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form_layout.setContentsMargins(0, 2, 0, 0)

        # Username
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("请输入学号 / 工号")
        self.username_input.setMinimumHeight(32)
        form_layout.addRow(self._create_form_label("账号:"), self.username_input)

        # Password + Toggle Visibility Button
        pwd_container = QWidget()
        pwd_layout = QHBoxLayout(pwd_container)
        pwd_layout.setContentsMargins(0, 0, 0, 0)
        pwd_layout.setSpacing(4)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("请输入密码")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setMinimumHeight(32)
        pwd_layout.addWidget(self.password_input)

        self.pwd_toggle_btn = QToolButton()
        self.pwd_toggle_btn.setText("显示")
        self.pwd_toggle_btn.setCheckable(True)
        self.pwd_toggle_btn.setCursor(Qt.PointingHandCursor)
        self.pwd_toggle_btn.setStyleSheet("""
            QToolButton {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                background-color: #ffffff;
                color: #64748b;
                font-size: 11px;
                padding: 6px 8px;
            }
            QToolButton:hover {
                background-color: #f1f5f9;
                color: #1e293b;
            }
            QToolButton:checked {
                background-color: #eff6ff;
                color: #1a73e8;
                border-color: #93c5fd;
            }
        """)
        self.pwd_toggle_btn.toggled.connect(self._toggle_password_visibility)
        pwd_layout.addWidget(self.pwd_toggle_btn)

        form_layout.addRow(self._create_form_label("密码:"), pwd_container)

        # ISP Selector
        self.isp_combo = QComboBox()
        for label, _ in ISP_OPTIONS:
            self.isp_combo.addItem(label)
        self.isp_combo.setMinimumHeight(32)
        form_layout.addRow(self._create_form_label("运营商:"), self.isp_combo)

        auth_layout.addLayout(form_layout)
        root.addWidget(auth_card)

        # ============================================================== #
        #  Card 2: 自动化与高级选项 (Options Card)
        # ============================================================== #
        opt_card = QFrame()
        opt_card.setProperty("class", "CardFrame")
        opt_layout = QVBoxLayout(opt_card)
        opt_layout.setContentsMargins(14, 10, 14, 10)
        opt_layout.setSpacing(8)

        card2_title = QLabel("运行设置")
        card2_title.setProperty("class", "CardTitle")
        opt_layout.addWidget(card2_title)

        # Row 1: Checkboxes
        row1 = QHBoxLayout()
        row1.setSpacing(16)

        self.remember_cb = QCheckBox("记住密码")
        self.remember_cb.setChecked(True)
        self.remember_cb.setCursor(Qt.PointingHandCursor)
        row1.addWidget(self.remember_cb)

        self.autostart_cb = QCheckBox("开机自启")
        self.autostart_cb.setChecked(is_autostart_enabled())
        self.autostart_cb.setCursor(Qt.PointingHandCursor)
        self.autostart_cb.stateChanged.connect(self._on_autostart_changed)
        row1.addWidget(self.autostart_cb)

        row1.addStretch()
        opt_layout.addLayout(row1)

        # Row 2: Auto-reconnect & interval
        row2 = QHBoxLayout()
        row2.setSpacing(8)

        self.auto_reconnect_cb = QCheckBox("断线自动重连")
        self.auto_reconnect_cb.setCursor(Qt.PointingHandCursor)
        self.auto_reconnect_cb.toggled.connect(self._on_auto_reconnect_toggled)
        row2.addWidget(self.auto_reconnect_cb)

        row2.addSpacing(6)
        interval_lbl = QLabel("间隔:")
        interval_lbl.setStyleSheet("color: #64748b; font-size: 12px;")
        row2.addWidget(interval_lbl)

        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(10, 3600)
        self.interval_spin.setValue(300)
        self.interval_spin.setMinimumHeight(28)
        self.interval_spin.setFixedWidth(68)
        self.interval_spin.setAlignment(Qt.AlignCenter)
        self.interval_spin.setEnabled(False)  # default disabled until auto_reconnect checked
        row2.addWidget(self.interval_spin)

        self.sec_lbl = QLabel("秒")
        self.sec_lbl.setStyleSheet("color: #64748b; font-size: 12px;")
        self.sec_lbl.setEnabled(False)
        row2.addWidget(self.sec_lbl)

        row2.addStretch()
        opt_layout.addLayout(row2)

        # Row 3: Server IP
        row3 = QHBoxLayout()
        row3.setSpacing(8)

        server_lbl = QLabel("服务器:")
        server_lbl.setStyleSheet("color: #64748b; font-size: 12px;")
        row3.addWidget(server_lbl)

        self.server_input = QLineEdit("172.19.0.5")
        self.server_input.setPlaceholderText("默认: 172.19.0.5")
        self.server_input.setMinimumHeight(28)
        row3.addWidget(self.server_input)

        opt_layout.addLayout(row3)
        root.addWidget(opt_card)

        # ============================================================== #
        #  Action Buttons (Login & Stop)
        # ============================================================== #
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.login_btn = QPushButton("一 键 登 录")
        self.login_btn.setObjectName("login_btn")
        self.login_btn.setMinimumHeight(38)
        self.login_btn.setCursor(Qt.PointingHandCursor)
        self.login_btn.clicked.connect(self._on_login)
        btn_layout.addWidget(self.login_btn, 3)

        self.stop_btn = QPushButton("停止重连")
        self.stop_btn.setObjectName("stop_btn")
        self.stop_btn.setMinimumHeight(38)
        self.stop_btn.setCursor(Qt.PointingHandCursor)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._on_stop)
        btn_layout.addWidget(self.stop_btn, 1)

        root.addLayout(btn_layout)

        # ============================================================== #
        #  Card 3: 运行日志 (Logs Card - 弹性伸缩)
        # ============================================================== #
        log_card = QFrame()
        log_card.setProperty("class", "CardFrame")
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(12, 10, 12, 10)
        log_layout.setSpacing(6)

        # Log Header
        log_header = QHBoxLayout()
        log_header.setSpacing(6)

        log_title = QLabel("运行控制台")
        log_title.setProperty("class", "CardTitle")
        log_header.addWidget(log_title)

        log_header.addStretch()

        copy_btn = QPushButton("复制")
        copy_btn.setProperty("class", "SmallToolBtn")
        copy_btn.setCursor(Qt.PointingHandCursor)
        copy_btn.clicked.connect(self._copy_log)
        log_header.addWidget(copy_btn)

        clear_btn = QPushButton("清空")
        clear_btn.setProperty("class", "SmallToolBtn")
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.clicked.connect(lambda: self.log_text.clear())
        log_header.addWidget(clear_btn)

        log_layout.addLayout(log_header)

        # Text Console
        self.log_text = QTextEdit()
        self.log_text.setObjectName("log_text")
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(110)
        self.log_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        log_layout.addWidget(self.log_text)

        # Add log card to root layout with stretch factor 1 so it expands with window resize
        root.addWidget(log_card, 1)

        # Enter in password triggers login
        self.password_input.returnPressed.connect(self._on_login)
        self.username_input.returnPressed.connect(lambda: self.password_input.setFocus())

    def _create_form_label(self, text):
        lbl = QLabel(text)
        lbl.setProperty("class", "FormLabel")
        lbl.setMinimumWidth(50)
        return lbl

    def _toggle_password_visibility(self, checked):
        if checked:
            self.password_input.setEchoMode(QLineEdit.Normal)
            self.pwd_toggle_btn.setText("隐藏")
        else:
            self.password_input.setEchoMode(QLineEdit.Password)
            self.pwd_toggle_btn.setText("显示")

    def _on_auto_reconnect_toggled(self, checked):
        self.interval_spin.setEnabled(checked)
        self.sec_lbl.setEnabled(checked)

    def _copy_log(self):
        text = self.log_text.toPlainText()
        if text:
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
            self._log("已复制日志到剪贴板")

    # ------------------------------------------------------------------ #
    #  System Tray
    # ------------------------------------------------------------------ #

    def _init_tray_icon(self):
        if os.path.isfile(ICON_PATH):
            self.tray_icon = QSystemTrayIcon(QIcon(ICON_PATH), self)
        else:
            self.tray_icon = QSystemTrayIcon(self.windowIcon(), self)
        self.tray_icon.setToolTip("SZTU 校园网登录助手")

        tray_menu = QMenu()
        show_action = QAction("显示主窗口", self)
        show_action.triggered.connect(self._show_window)
        tray_menu.addAction(show_action)

        quit_action = QAction("退出程序", self)
        quit_action.triggered.connect(self._quit_app)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _show_window(self):
        self.showNormal()
        self.activateWindow()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self._show_window()

    def _quit_app(self):
        self._stop_auto_reconnect()
        if self.remember_cb.isChecked():
            self._save_config()
        self.tray_icon.hide()
        QApplication.instance().quit()

    # ------------------------------------------------------------------ #
    #  Logging & Status
    # ------------------------------------------------------------------ #

    def _log(self, message):
        self.log_text.append(message)
        self.log_text.moveCursor(QTextCursor.End)

    def _set_status_badge(self, state, text):
        """
        Update the visual status badge in the top right header.
        state: 'connected' | 'connecting' | 'failed' | 'disconnected'
        """
        self.status_badge.setText(text)
        if state == "connected":
            self.status_badge.setStyleSheet("""
                background-color: #ecfdf5;
                color: #059669;
                border: 1px solid #a7f3d0;
            """)
        elif state == "connecting":
            self.status_badge.setStyleSheet("""
                background-color: #fffbeb;
                color: #d97706;
                border: 1px solid #fde68a;
            """)
        elif state == "failed":
            self.status_badge.setStyleSheet("""
                background-color: #fef2f2;
                color: #dc2626;
                border: 1px solid #fecaca;
            """)
        else:  # disconnected
            self.status_badge.setStyleSheet("""
                background-color: #f1f5f9;
                color: #64748b;
                border: 1px solid #cbd5e1;
            """)

    # ------------------------------------------------------------------ #
    #  Login
    # ------------------------------------------------------------------ #

    def _on_login(self):
        if self._login_in_progress:
            return

        username = self.username_input.text().strip()
        password = self.password_input.text().strip()

        if not username or not password:
            QMessageBox.warning(self, "提示", "请输入账号和密码")
            return

        suffix = ISP_OPTIONS[self.isp_combo.currentIndex()][1]
        server_ip = self.server_input.text().strip()
        if not server_ip:
            server_ip = "172.19.0.5"

        if self.remember_cb.isChecked():
            self._save_config()

        self._login_in_progress = True
        self.login_btn.setEnabled(False)
        self.login_btn.setText("正在登录...")
        self._set_status_badge("connecting", "◐ 正在登录...")

        ts = time.strftime("%H:%M:%S")
        self._log(f"\n{'=' * 36}")
        self._log(f"[{ts}] 开始登录: {username}{suffix}")

        self.login_worker = LoginWorker(username, password, suffix, server_ip)
        self.login_worker.log_signal.connect(self._log)
        self.login_worker.result_signal.connect(self._on_login_result)
        self.login_worker.start()

    def _on_login_result(self, success, message):
        self._login_in_progress = False
        self.login_btn.setEnabled(True)
        self.login_btn.setText("一 键 登 录")

        ts = time.strftime("%H:%M:%S")
        if success:
            self.is_connected = True
            self._set_status_badge("connected", "● 已连接")
            self._log(f"[{ts}] [OK] {message}")
            if self.auto_reconnect_cb.isChecked():
                self._start_auto_reconnect()
        else:
            self.is_connected = False
            self._set_status_badge("failed", "● 连接失败")
            self._log(f"[{ts}] [FAIL] {message}")

    # ------------------------------------------------------------------ #
    #  Auto-reconnect
    # ------------------------------------------------------------------ #

    def _start_auto_reconnect(self):
        self._stop_auto_reconnect()
        interval_ms = self.interval_spin.value() * 1000
        self.auto_reconnect_timer = QTimer()
        self.auto_reconnect_timer.timeout.connect(self._check_connection)
        self.auto_reconnect_timer.start(interval_ms)
        self.stop_btn.setEnabled(True)
        self._log(
            f"[{time.strftime('%H:%M:%S')}] "
            f"自动重连已启动，检测间隔 {self.interval_spin.value()} 秒"
        )

    def _stop_auto_reconnect(self):
        if self.auto_reconnect_timer:
            self.auto_reconnect_timer.stop()
            self.auto_reconnect_timer = None

    def _check_connection(self):
        """Start a background ping to detect disconnection."""
        if self._login_in_progress:
            return
        self.ping_worker = PingWorker()
        self.ping_worker.result_signal.connect(self._on_ping_result)
        self.ping_worker.start()

    def _on_ping_result(self, connected):
        ts = time.strftime("%H:%M:%S")
        if not connected:
            self._log(f"[{ts}] 检测到网络断开，正在自动重连...")
            self._set_status_badge("connecting", "◐ 正在重连...")
            self._on_login()
        else:
            self._log(f"[{ts}] 网络检测正常")

    def _on_stop(self):
        self._stop_auto_reconnect()
        self.is_connected = False
        self.login_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self._set_status_badge("disconnected", "● 已停止重连")
        self._log(f"[{time.strftime('%H:%M:%S')}] 已停止自动重连")

    # ------------------------------------------------------------------ #
    #  Autostart
    # ------------------------------------------------------------------ #

    def _on_autostart_changed(self, state):
        enable = state == Qt.Checked
        if set_autostart(enable):
            action = "已开启" if enable else "已关闭"
            self._log(f"[{time.strftime('%H:%M:%S')}] 开机自启动{action}")
        else:
            QMessageBox.warning(self, "提示", "设置开机自启动失败，请尝试以管理员身份运行")
            self.autostart_cb.blockSignals(True)
            self.autostart_cb.setChecked(not enable)
            self.autostart_cb.blockSignals(False)

    # ------------------------------------------------------------------ #
    #  Config persistence
    # ------------------------------------------------------------------ #

    def _save_config(self):
        config = {
            "username": self.username_input.text().strip(),
            "password": self.password_input.text().strip(),
            "isp_index": self.isp_combo.currentIndex(),
            "server_ip": self.server_input.text().strip(),
            "auto_reconnect": self.auto_reconnect_cb.isChecked(),
            "interval": self.interval_spin.value(),
        }
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False)
        except Exception:
            pass

    def _load_config(self):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            self.username_input.setText(cfg.get("username", ""))
            self.password_input.setText(cfg.get("password", ""))
            self.isp_combo.setCurrentIndex(cfg.get("isp_index", 0))
            self.server_input.setText(cfg.get("server_ip", "172.19.0.5"))
            auto_rec = cfg.get("auto_reconnect", False)
            self.auto_reconnect_cb.setChecked(auto_rec)
            self.interval_spin.setEnabled(auto_rec)
            self.sec_lbl.setEnabled(auto_rec)
            self.interval_spin.setValue(cfg.get("interval", 300))
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    #  Window events
    # ------------------------------------------------------------------ #

    def closeEvent(self, event):
        if self.remember_cb.isChecked():
            self._save_config()
        self.hide()
        self.tray_icon.showMessage(
            "SZTU 校园网登录助手",
            "程序已最小化到系统托盘，双击图标可恢复窗口",
            QSystemTrayIcon.Information,
            2000,
        )
        event.ignore()


def main():
    # 2. 启用 High-DPI 缩放属性
    if hasattr(Qt, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei UI", 10))
    if os.path.isfile(ICON_PATH):
        app.setWindowIcon(QIcon(ICON_PATH))
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
