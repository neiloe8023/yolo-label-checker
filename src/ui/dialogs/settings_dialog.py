from PySide6.QtWidgets import (QDialog, QVBoxLayout, QCheckBox,
                               QPushButton, QGroupBox)


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # 自动保存设置
        save_group = QGroupBox("保存设置")
        save_layout = QVBoxLayout()
        self.auto_save = QCheckBox("自动保存修改")
        save_layout.addWidget(self.auto_save)
        save_group.setLayout(save_layout)

        # 确定按钮
        btn_ok = QPushButton("确定")
        btn_ok.clicked.connect(self.accept)

        layout.addWidget(save_group)
        layout.addWidget(btn_ok)
