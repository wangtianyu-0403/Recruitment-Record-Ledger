from __future__ import annotations

import csv
import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QDialogButtonBox, QInputDialog, QMessageBox, QPushButton, QToolBar

from recruitment_ledger.backup import BackupManager
from recruitment_ledger.database import Database
from recruitment_ledger.export import export_applications_to_csv
from recruitment_ledger.models import ApplicationRecord
from recruitment_ledger.repository import ApplicationRepository, SortMode
from recruitment_ledger.ui.application_dialog import ApplicationDialog
from recruitment_ledger.ui.main_window import MainWindow
from recruitment_ledger.ui.local_documents import LocalDocumentButton
from recruitment_ledger.ui import main_window
from recruitment_ledger.validation import ValidationError


def test_application_resume_survives_create_edit_and_export(service, tmp_path):
    resume = tmp_path / "中文 简历.pdf"
    resume.write_bytes(b"resume")
    application_id = service.create(ApplicationRecord(
        company_name="测试公司", position_name="工程师",
        application_date="2026-10-05", status="已投递",
        local_resume_path=f'  "{resume}"  ',
    ))
    record = service.get(application_id)
    assert record.local_resume_path == str(resume)
    service.update(replace(record, position_name="软件工程师"))
    record = service.get(application_id)
    assert record.local_resume_path == str(resume)
    target = export_applications_to_csv([record], tmp_path / "export.csv")
    with target.open(encoding="utf-8-sig", newline="") as stream:
        assert next(csv.DictReader(stream))["本地简历"] == str(resume)


def test_dialog_saves_and_reopens_resume(qtbot, service, tmp_path):
    resume = tmp_path / "resume.pdf"
    resume.write_bytes(b"resume")
    saved = []
    dialog = ApplicationDialog(save_callback=lambda record: saved.append(service.create(record)))
    qtbot.addWidget(dialog)
    dialog.company_edit.setText("测试公司")
    dialog.position_edit.setText("工程师")
    dialog.local_resume_edit.setText(str(resume))
    buttons = dialog.findChild(QDialogButtonBox)
    qtbot.mouseClick(buttons.button(QDialogButtonBox.StandardButton.Save), Qt.MouseButton.LeftButton)
    reopened = ApplicationDialog(service.get(saved[0]))
    qtbot.addWidget(reopened)
    assert reopened.local_resume_edit.text() == str(resume)


def test_resume_button_and_shortcut_menus_open_and_remember_paths(
    qtbot, monkeypatch, service, database, app_paths, tmp_path,
):
    settings_file = str(tmp_path / "settings.ini")
    monkeypatch.setattr(main_window, "QSettings", lambda: QSettings(settings_file, QSettings.Format.IniFormat))
    resume = tmp_path / "中文 简历.pdf"
    resume.write_bytes(b"resume")
    service.create(ApplicationRecord(
        company_name="测试公司", position_name="工程师",
        application_date="2026-10-05", status="已投递", local_resume_path=str(resume),
    ))
    opened = []
    from PySide6.QtGui import QDesktopServices
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url) or True)
    window = MainWindow(service, BackupManager(database, app_paths), app_paths)
    qtbot.addWidget(window)
    assert window.TABLE_HEADERS[6:8] == ("公司官网", "本地简历")
    qtbot.mouseClick(window.table.cellWidget(0, 7), Qt.MouseButton.LeftButton)
    assert opened[-1].toLocalFile() == str(resume).replace("\\", "/")
    toolbar = next(bar for bar in window.findChildren(QToolBar) if bar.windowTitle() == "操作工具栏")
    labels = [toolbar.widgetForAction(action).text() for action in toolbar.actions()
              if isinstance(toolbar.widgetForAction(action), QPushButton)]
    assert labels[-2:] == ["备份数据库", "恢复数据库"]
    for label, path in (("个人页", tmp_path), ("简历页", resume)):
        button = next(button for button in window.findChildren(QPushButton) if button.text() == label)
        actions = button.menu().actions()
        assert [action.text() for action in actions] == ["打开", "修改本地文件目录"]
        assert not actions[0].isEnabled()
        monkeypatch.setattr(QInputDialog, "getText", lambda *args, p=path, **kwargs: (str(p), True))
        actions[1].trigger()
        actions[0].trigger()
        assert opened[-1].toLocalFile() == str(path).replace("\\", "/")
    window.close()
    reopened = MainWindow(service, BackupManager(database, app_paths), app_paths)
    qtbot.addWidget(reopened)
    for label, path in (("个人页", tmp_path), ("简历页", resume)):
        button = next(button for button in reopened.findChildren(QPushButton) if button.text() == label)
        button.menu().actions()[0].trigger()
        assert opened[-1].toLocalFile() == str(path).replace("\\", "/")


@pytest.mark.parametrize("path", ["resume.pdf", "https://example.com/resume.pdf", "C:\\bad\x00.pdf"])
def test_application_rejects_nonlocal_or_incomplete_resume_paths(service, path):
    with pytest.raises(ValidationError):
        service.create(ApplicationRecord(
            company_name="公司", position_name="岗位", application_date="2026-10-05",
            status="已投递", local_resume_path=path,
        ))


def test_upgrade_old_database_preserves_manual_order_pins_and_history(tmp_path):
    path = tmp_path / "legacy.db"
    legacy = sqlite3.connect(path)
    legacy.executescript((Path(__file__).parent / "fixtures/schema_v2.sql").read_text(encoding="utf-8"))
    for company, order, pinned in (("甲", 8, 0), ("乙", -4, 0), ("丙", 2, 1)):
        legacy.execute(
            "INSERT INTO applications (company_name, position_name, application_date, status, "
            "created_at, updated_at, manual_order, is_pinned) VALUES (?, '岗位', '2026-10-05', "
            "'已投递', '2026-10-05', '2026-10-05', ?, ?)", (company, order, pinned),
        )
    legacy.execute(
        "INSERT INTO status_history (application_id, new_status, changed_at) VALUES (1, '已投递', '2026-10-05')"
    )
    legacy.commit()
    legacy.close()
    with Database(path) as upgraded:
        repository = ApplicationRepository(upgraded)
        upgraded.initialize()
        records = repository.list_applications(sort_mode=SortMode.MANUAL)
        assert [(record.company_name, record.manual_order, record.is_pinned, record.local_resume_path)
                for record in records] == [("丙", 2, True, ""), ("乙", -4, False, ""), ("甲", 8, False, "")]
        assert repository.list_status_history(1)[0].new_status == "已投递"


@pytest.mark.parametrize("target_kind", ["missing", "directory", "system_failure"])
def test_resume_open_reports_failure_without_launching_invalid_paths(
    qtbot, monkeypatch, service, database, app_paths, tmp_path, target_kind,
):
    from PySide6.QtGui import QDesktopServices

    path = tmp_path / "resume.pdf"
    if target_kind == "directory":
        path.mkdir()
    elif target_kind == "system_failure":
        path.write_bytes(b"resume")
    opened = []
    warnings = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url) or False)
    monkeypatch.setattr(QMessageBox, "warning", lambda parent, title, text: warnings.append(text))
    service.create(ApplicationRecord(
        company_name="公司", position_name="岗位", application_date="2026-10-05",
        status="已投递", local_resume_path=str(path),
    ))
    window = MainWindow(service, BackupManager(database, app_paths), app_paths)
    qtbot.addWidget(window)
    qtbot.mouseClick(window.table.cellWidget(0, 7), Qt.MouseButton.LeftButton)
    assert len(warnings) == 1
    assert len(opened) == (1 if target_kind == "system_failure" else 0)


def test_shortcut_cancel_invalid_and_clear_preserve_expected_path(qtbot, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QWidget

    parent = QWidget()
    qtbot.addWidget(parent)
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("resume", str(tmp_path))
    button = LocalDocumentButton("简历页", settings, "resume", parent)
    edit = button.menu().actions()[1]
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda parent, title, text: warnings.append(text))
    for value, accepted in (("changed", False), ("https://example.com", True)):
        monkeypatch.setattr(QInputDialog, "getText", lambda *args, **kwargs: (value, accepted))
        edit.trigger()
        assert settings.value("resume") == str(tmp_path)
    assert len(warnings) == 1
    monkeypatch.setattr(QInputDialog, "getText", lambda *args, **kwargs: ("", True))
    edit.trigger()
    assert settings.value("resume") == ""
    assert not button.menu().actions()[0].isEnabled()


def test_new_column_preserves_old_saved_column_widths(
    qtbot, monkeypatch, service, database, app_paths, tmp_path,
):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("table/column_widths", [170, 200, 110, 140, 120, 130, 90, 180, 260])
    monkeypatch.setattr(main_window, "QSettings", lambda: settings)
    window = MainWindow(service, BackupManager(database, app_paths), app_paths)
    qtbot.addWidget(window)
    assert window.table.columnWidth(0) == 170
    assert window.table.columnWidth(7) == 100
    assert window.table.columnWidth(8) == 180
    assert window.table.columnWidth(9) == 260
