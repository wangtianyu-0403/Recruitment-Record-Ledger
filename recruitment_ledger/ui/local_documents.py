from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QInputDialog, QMenu, QMessageBox, QPushButton, QWidget

from ..validation import ValidationError, normalize_local_path


def open_local_path(value: str, parent: QWidget, *, file_only: bool = False) -> None:
    try:
        normalized = normalize_local_path(value)
        if not normalized:
            raise ValidationError("请先填写本地文件目录。")
        path = Path(normalized)
        if not path.exists():
            raise ValidationError("本地路径不存在，请检查文件是否已移动或删除。")
        if file_only and not path.is_file():
            raise ValidationError("本地简历链接必须指向一个文件。")
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
            raise ValidationError("无法使用系统默认程序打开该本地路径。")
    except (ValidationError, OSError) as exc:
        QMessageBox.warning(parent, "打开失败", str(exc))


class LocalDocumentButton(QPushButton):
    """可修改并持久保存的全局本地资料入口。"""

    def __init__(self, title: str, settings: QSettings, key: str, parent: QWidget) -> None:
        super().__init__(title, parent)
        self._settings = settings
        self._key = key
        menu = QMenu(self)
        self._open_action = menu.addAction("打开")
        self._open_action.triggered.connect(lambda: open_local_path(self._path(), self))
        menu.addAction("修改本地文件目录", self._edit_path)
        self.setMenu(menu)
        self._refresh()

    def _path(self) -> str:
        return str(self._settings.value(self._key, ""))

    def _refresh(self) -> None:
        path = self._path()
        self.setToolTip(path or "尚未设置本地文件目录")
        self._open_action.setEnabled(bool(path))

    def _edit_path(self) -> None:
        value, accepted = QInputDialog.getText(
            self, f"修改{self.text()}本地文件目录",
            "填写完整文件或文件夹路径（留空可清除）：", text=self._path(),
        )
        if not accepted:
            return
        try:
            path = normalize_local_path(value)
        except ValidationError as exc:
            QMessageBox.warning(self, "输入有误", str(exc))
            return
        self._settings.setValue(self._key, path)
        self._settings.sync()
        self._refresh()
