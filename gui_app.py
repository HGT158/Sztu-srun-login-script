"""
SZTU 校园网登录助手 - 图形界面版
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
    QSystemTrayIcon, QMenu, QAction,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QTextCursor, QIcon

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
                cmd = ["ping", "-n", "4", "-w", "2000", self.testip]
            else:
                cmd = ["ping", "-c", "4", "-W", "2", self.testip]
            result = subprocess.run(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15
            )
            self.result_signal.emit(result.returncode == 0)
        except Exception:
            self.result_signal.emit(False)


STYLESHEET = """
QMainWindow {
    background-color: #f5f5f5;
}
QGroupBox {
    font-weight: bold;
    border: 1px solid #ddd;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 14px;
    background-color: white;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}
QLineEdit, QComboBox, QSpinBox {
    border: 1px solid #ccc;
    border-radius: 4px;
    padding: 4px 8px;
    background: white;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    border-color: #1a73e8;
}
QPushButton#login_btn {
    background-color: #1a73e8;
    color: white;
    border: none;
    border-radius: 6px;
    font-weight: bold;
}
QPushButton#login_btn:hover {
    background-color: #1557b0;
}
QPushButton#login_btn:disabled {
    background-color: #94c2f7;
}
QPushButton#stop_btn {
    background-color: #e8e8e8;
    color: #333;
    border: 1px solid #ccc;
    border-radius: 6px;
}
QPushButton#stop_btn:hover {
    background-color: #d0d0d0;
}
QPushButton#stop_btn:disabled {
    color: #aaa;
}
QPushButton#clear_btn {
    background-color: transparent;
    color: #666;
    border: 1px solid #ccc;
    border-radius: 4px;
    font-size: 11px;
}
QPushButton#clear_btn:hover {
    background-color: #eee;
}
QTextEdit {
    border: 1px solid #ddd;
    border-radius: 4px;
    background-color: #1e1e1e;
    color: #d4d4d4;
}
QCheckBox {
    spacing: 5px;
}
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.auto_reconnect_timer = None
        self.is_connected = False
        self.login_worker = None
        self.ping_worker = None
        self._login_in_progress = False

        self._init_ui()
        self._load_config()

    # ------------------------------------------------------------------ #
    #  UI Construction
    # ------------------------------------------------------------------ #

    def _init_ui(self):
        self.setWindowTitle("SZTU 校园网登录助手")
        self.setFixedSize(500, 660)
        self.setStyleSheet(STYLESHEET)
        self.setWindowIcon(QIcon(ICON_PATH))

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(10)

        # ---------- Title ----------
        title = QLabel("SZTU 校园网登录助手—桂辰改进版")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Microsoft YaHei", 16, QFont.Bold))
        title.setStyleSheet("color: #1a73e8; margin-bottom: 2px;")
        root.addWidget(title)

        subtitle = QLabel("深圳技术大学 · Srun 认证客户端")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #666; font-size: 12px; margin-bottom: 6px;")
        root.addWidget(subtitle)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #e0e0e0;")
        root.addWidget(line)

        # ---------- Login form ----------
        form_group = QGroupBox("登录信息")
        form = QFormLayout()
        form.setSpacing(10)
        form.setContentsMargins(12, 18, 12, 12)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("请输入学号 / 工号")
        self.username_input.setMinimumHeight(32)
        form.addRow("账　号:", self.username_input)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("请输入密码")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setMinimumHeight(32)
        form.addRow("密　码:", self.password_input)

        self.isp_combo = QComboBox()
        for label, _ in ISP_OPTIONS:
            self.isp_combo.addItem(label)
        self.isp_combo.setMinimumHeight(32)
        form.addRow("运营商:", self.isp_combo)

        self.server_input = QLineEdit("172.19.0.5")
        self.server_input.setMinimumHeight(32)
        form.addRow("服务器:", self.server_input)

        form_group.setLayout(form)
        root.addWidget(form_group)

        # ---------- Options ----------
        opt_layout = QHBoxLayout()
        opt_layout.setSpacing(10)

        self.remember_cb = QCheckBox("记住密码")
        self.remember_cb.setChecked(True)
        opt_layout.addWidget(self.remember_cb)

        self.autostart_cb = QCheckBox("开机自启")
        self.autostart_cb.setChecked(is_autostart_enabled())
        self.autostart_cb.stateChanged.connect(self._on_autostart_changed)
        opt_layout.addWidget(self.autostart_cb)

        self.auto_reconnect_cb = QCheckBox("自动重连")
        opt_layout.addWidget(self.auto_reconnect_cb)

        opt_layout.addWidget(QLabel("间隔:"))
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(30, 3600)
        self.interval_spin.setValue(300)
        self.interval_spin.setSuffix(" 秒")
        self.interval_spin.setMinimumWidth(100)
        opt_layout.addWidget(self.interval_spin)

        opt_layout.addStretch()
        root.addLayout(opt_layout)

        # ---------- Buttons ----------
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.login_btn = QPushButton("登 录")
        self.login_btn.setObjectName("login_btn")
        self.login_btn.setMinimumHeight(40)
        self.login_btn.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        self.login_btn.setCursor(Qt.PointingHandCursor)
        self.login_btn.clicked.connect(self._on_login)
        btn_layout.addWidget(self.login_btn)

        self.stop_btn = QPushButton("停 止")
        self.stop_btn.setObjectName("stop_btn")
        self.stop_btn.setMinimumHeight(40)
        self.stop_btn.setFont(QFont("Microsoft YaHei", 11))
        self.stop_btn.setCursor(Qt.PointingHandCursor)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._on_stop)
        btn_layout.addWidget(self.stop_btn)

        root.addLayout(btn_layout)

        # ---------- Log area ----------
        log_header = QHBoxLayout()
        log_label = QLabel("运行日志")
        log_label.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        log_header.addWidget(log_label)
        log_header.addStretch()
        clear_btn = QPushButton("清空")
        clear_btn.setObjectName("clear_btn")
        clear_btn.setFixedSize(50, 24)
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.clicked.connect(lambda: self.log_text.clear())
        log_header.addWidget(clear_btn)
        root.addLayout(log_header)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setMinimumHeight(150)
        root.addWidget(self.log_text)

        # ---------- Status bar ----------
        self.status_label = QLabel("状态: 未连接")
        self.status_label.setStyleSheet(
            "color: #666; font-size: 12px; padding: 4px 0;"
        )
        root.addWidget(self.status_label)

        # Allow pressing Enter in password field to trigger login
        self.password_input.returnPressed.connect(self._on_login)

    # ------------------------------------------------------------------ #
    #  Logging & Status
    # ------------------------------------------------------------------ #

    def _log(self, message):
        self.log_text.append(message)
        self.log_text.moveCursor(QTextCursor.End)

    def _set_status(self, text, color="#666"):
        self.status_label.setText(f"状态: {text}")
        self.status_label.setStyleSheet(
            f"color: {color}; font-size: 12px; padding: 4px 0;"
        )

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

        if self.remember_cb.isChecked():
            self._save_config()

        self._login_in_progress = True
        self.login_btn.setEnabled(False)
        self._set_status("正在登录...", "#e67e00")

        ts = time.strftime("%H:%M:%S")
        self._log(f"{'=' * 44}")
        self._log(f"[{ts}] 开始登录 {username}{suffix}")

        self.login_worker = LoginWorker(username, password, suffix, server_ip)
        self.login_worker.log_signal.connect(self._log)
        self.login_worker.result_signal.connect(self._on_login_result)
        self.login_worker.start()

    def _on_login_result(self, success, message):
        self._login_in_progress = False
        self.login_btn.setEnabled(True)

        ts = time.strftime("%H:%M:%S")
        if success:
            self.is_connected = True
            self._set_status("已连接", "green")
            self._log(f"[{ts}] [OK] {message}")
            if self.auto_reconnect_cb.isChecked():
                self._start_auto_reconnect()
        else:
            self.is_connected = False
            self._set_status("连接失败", "red")
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
            self._log(f"[{ts}] 检测到网络断开，正在重连...")
            self._set_status("正在重连...", "#e67e00")
            self._on_login()
        else:
            self._log(f"[{ts}] 网络正常")

    def _on_stop(self):
        self._stop_auto_reconnect()
        self.is_connected = False
        self.login_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self._set_status("已停止", "#666")
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
            self.auto_reconnect_cb.setChecked(cfg.get("auto_reconnect", False))
            self.interval_spin.setValue(cfg.get("interval", 300))
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    #  Window events
    # ------------------------------------------------------------------ #

    def closeEvent(self, event):
        self._stop_auto_reconnect()
        if self.remember_cb.isChecked():
            self._save_config()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei", 10))
    app.setWindowIcon(QIcon(ICON_PATH))
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
