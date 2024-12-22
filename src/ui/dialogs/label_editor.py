from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLineEdit,
                               QPushButton, QListWidget, QLabel)
from PySide6.QtCore import Qt


class LabelEditorDialog(QDialog):
    def __init__(self, parent=None, current_label="", labels=None):
        super().__init__(parent)
        self.setWindowTitle("编辑标签")
        self.selected_label = current_label
        self.labels = labels or []
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # 输入区域
        input_layout = QHBoxLayout()
        self.label_input = QLineEdit()
        self.label_input.setText(self.selected_label)
        self.btn_ok = QPushButton("确定")
        self.btn_ok.clicked.connect(self.accept)
        input_layout.addWidget(self.label_input)
        input_layout.addWidget(self.btn_ok)

        # 标签列表
        self.label_list = QListWidget()
        self.label_list.addItems(self.labels)
        self.label_list.itemClicked.connect(self.on_item_clicked)
        self.label_list.itemDoubleClicked.connect(self.on_item_double_clicked)

        layout.addLayout(input_layout)
        layout.addWidget(QLabel("可用标签:"))
        layout.addWidget(self.label_list)

    def on_item_clicked(self, item):
        """单击标签项时，将标签填入输入框"""
        self.label_input.setText(item.text())

    def on_item_double_clicked(self, item):
        """双击标签项时，直接选定并关闭"""
        self.selected_label = item.text()
        self.accept()

    def get_selected_label(self):
        """获取选定的标签"""
        return self.label_input.text()
