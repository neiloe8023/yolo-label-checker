from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QPushButton, QTableWidget, QGraphicsView,
                               QStatusBar, QSlider, QFileDialog, QTableWidgetItem,
                               QHeaderView, QGraphicsScene, QGraphicsRectItem,
                               QGraphicsTextItem, QMessageBox, QMenuBar, QMenu,
                               QListWidget, QLabel, QListWidgetItem)
from PySide6.QtCore import Qt, QDir, QRectF, QTimer, QSettings
from PySide6.QtGui import QColor, QImage, QPixmap, QPen, QPainter
import os
from pathlib import Path
from typing import List, Dict, Optional
import cv2
from core.annotation import AnnotationFile, BBox
from core.checker import AnnotationChecker
from .workers import CheckWorker
import csv
from datetime import datetime
import random
import colorsys
from .widgets.editable_box import EditableBox
from .dialogs.label_editor import LabelEditorDialog


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YOLO 标注检查工具")
        self.resize(1200, 800)

        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 创建主布局
        main_layout = QHBoxLayout(central_widget)

        # 创建左侧布局
        left_layout = QVBoxLayout()

        # 工具栏按钮
        toolbar_layout = QHBoxLayout()
        self.btn_select_dir = QPushButton("选择目录")
        self.btn_select_labels = QPushButton("选择标签文件")
        self.btn_export = QPushButton("导出结果")

        toolbar_layout.addWidget(self.btn_select_dir)
        toolbar_layout.addWidget(self.btn_select_labels)
        toolbar_layout.addWidget(self.btn_export)

        # 创建文件列表
        self.file_table = QTableWidget()
        self.setup_file_table()

        # 创建一个水平布局来放置滑块和刷新按钮
        threshold_layout = QHBoxLayout()
        self.threshold_slider = QSlider(Qt.Horizontal)
        self.threshold_slider.setRange(0, 100)
        self.threshold_slider.setValue(60)
        self.btn_refresh = QPushButton("刷新")

        threshold_layout.addWidget(self.threshold_slider)
        threshold_layout.addWidget(self.btn_refresh)

        # 添加到左侧布局
        left_layout.addLayout(toolbar_layout)
        left_layout.addWidget(self.file_table)
        left_layout.addLayout(threshold_layout)

        # 创建中间布局（预览区域）
        middle_layout = QVBoxLayout()
        self.preview_view = QGraphicsView()
        self.preview_scene = QGraphicsScene()
        self.preview_view.setScene(self.preview_scene)
        self.preview_view.setRenderHint(QPainter.Antialiasing)
        middle_layout.addWidget(self.preview_view)

        # 创建右侧布局（类别列表）
        right_layout = QVBoxLayout()
        category_label = QLabel("图片中的类别:")
        self.category_list = QListWidget()
        right_layout.addWidget(category_label)
        right_layout.addWidget(self.category_list)

        # 设置右侧布局的最大宽度
        right_widget = QWidget()
        right_widget.setLayout(right_layout)
        right_widget.setMaximumWidth(200)  # 设置最大宽度

        # 添加到主布局
        main_layout.addLayout(left_layout, stretch=1)
        main_layout.addLayout(middle_layout, stretch=2)
        main_layout.addWidget(right_widget)

        # 状态栏
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)

        # 添加永久状态栏项目
        self.total_files_label = QLabel("文件总数: 0")
        self.total_overlaps_label = QLabel("重叠总数: 0")
        self.total_invalid_labels_label = QLabel("无标签总数: 0")

        self.statusBar.addPermanentWidget(self.total_files_label)
        self.statusBar.addPermanentWidget(self.total_overlaps_label)
        self.statusBar.addPermanentWidget(self.total_invalid_labels_label)

        # 连接信号
        self.setup_connections()

        # 添加成员变量
        self.current_dir: str = ""
        self.labels_file: str = ""
        self.image_files: List[str] = []
        self.annotation_files: Dict[str, str] = {}  # image_name -> anno_path
        self.current_image: Optional[str] = None
        self.current_annotation: Optional[AnnotationFile] = None
        self.label_names: List[str] = []
        self.checker = AnnotationChecker()
        self.check_worker: Optional[CheckWorker] = None
        self.auto_save = False
        self.has_changes = False
        self.current_box = None

        # 添加绘制相关的成员变量
        self.is_drawing = False
        self.draw_start_pos = None

        # 添加菜单栏
        self.setup_menu()

        # 添加设置对象
        self.settings = QSettings("YOLOChecker", "LabelChecker")

        # 从设置中加载自动保存选项
        self.auto_save = self.settings.value("auto_save", False, type=bool)

        # 添加标签颜色字典
        self.label_colors = {}

        # 保存原始的事件处理器
        self.original_mouse_press = self.preview_scene.mousePressEvent
        self.original_mouse_move = self.preview_scene.mouseMoveEvent
        self.original_mouse_release = self.preview_scene.mouseReleaseEvent

    def setup_file_table(self):
        """设置文件列表表格"""
        headers = ["文件名", "状态", "问题详情"]
        self.file_table.setColumnCount(len(headers))
        self.file_table.setHorizontalHeaderLabels(headers)

        # 设置列宽
        header = self.file_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setDefaultSectionSize(100)

        # 设置选择模式
        self.file_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.file_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)

        # 禁止编辑
        self.file_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        # 重写文件列表的键盘事件处理
        self.file_table.keyPressEvent = self.table_key_press_event

    def setup_connections(self):
        self.btn_select_dir.clicked.connect(self.select_directory)
        self.btn_select_labels.clicked.connect(self.select_labels_file)
        self.btn_export.clicked.connect(self.export_results)
        self.btn_refresh.clicked.connect(self.refresh_check)
        self.threshold_slider.valueChanged.connect(self.threshold_changed)
        self.file_table.itemSelectionChanged.connect(self.on_selection_changed)
        self.category_list.itemClicked.connect(self.on_category_selected)

    def select_directory(self):
        """选择数据目录"""
        # 获取上次的目录
        last_dir = self.settings.value("last_directory", "")

        # 从上次的目录开始选择
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "选择数据目录",
            last_dir
        )

        if dir_path:
            # 保存选择的目录
            self.settings.setValue("last_directory", dir_path)
            self.load_directory(dir_path)

    def select_labels_file(self):
        """选择标签文件"""
        # 获取上次的目录
        last_dir = self.settings.value("last_labels_directory", "")

        # 从上次的目录开始选择
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择标签文件",
            last_dir,
            "Text Files (*.txt)"
        )

        if file_path:
            # 保存选择的目录
            self.settings.setValue("last_labels_directory", str(Path(file_path).parent))
            self.load_labels_file(file_path)

    def load_directory(self, path: str):
        """加载目录中的图片和标注文件"""
        self.current_dir = path
        self.image_files.clear()
        self.annotation_files.clear()

        # 清除当前预览
        self.preview_scene.clear()
        self.current_image = None
        self.current_annotation = None

        # 检查并加载 classes.txt
        classes_file = Path(path) / "classes.txt"
        if classes_file.exists():
            self.load_labels_file(str(classes_file))

        # 获取所有文件
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp'}
        for file in Path(path).iterdir():
            if file.suffix.lower() in image_extensions:
                # 查找对应的标注文件
                anno_path = file.with_suffix('.txt')
                if anno_path.exists():
                    self.image_files.append(str(file))
                    self.annotation_files[file.stem] = str(anno_path)

        self.update_file_table()
        self.statusBar.showMessage(f"已加载 {len(self.image_files)} 个文件")

    def update_file_table(self):
        """更新文件列表显示"""
        self.file_table.setRowCount(len(self.image_files))

        for row, image_path in enumerate(sorted(self.image_files)):
            # 文件名
            file_name = os.path.basename(image_path)
            name_item = QTableWidgetItem(file_name)
            self.file_table.setItem(row, 0, name_item)

            # 状态（默认"未检查"）
            status_item = QTableWidgetItem("未检查")
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.file_table.setItem(row, 1, status_item)

            # 问题详情（默认为空）
            detail_item = QTableWidgetItem("")
            self.file_table.setItem(row, 2, detail_item)

    def set_row_status(self, row: int, status: str, details: str = "", color: QColor = None):
        """设置指定行的状态和颜色"""
        if 0 <= row < self.file_table.rowCount():
            # 更新状态
            status_item = self.file_table.item(row, 1)
            status_item.setText(status)

            # 更详情
            detail_item = self.file_table.item(row, 2)
            detail_item.setText(details)

            # 设置颜色
            if color:
                for col in range(self.file_table.columnCount()):
                    self.file_table.item(row, col).setBackground(color)

    def load_labels_file(self, path: str):
        """加载标签文件"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                self.label_names = [line.strip() for line in f if line.strip()]
            self.labels_file = path
            self.checker.set_labels(path)

            # 为每个标签生成随机颜色
            for label in self.label_names:
                if label not in self.label_colors:
                    # 生成明亮的随机颜色
                    hue = random.random()
                    saturation = 0.6 + random.random() * 0.4
                    value = 0.8 + random.random() * 0.2

                    # 转换HSV到RGB
                    import colorsys
                    rgb = colorsys.hsv_to_rgb(hue, saturation, value)
                    self.label_colors[label] = QColor(
                        int(rgb[0] * 255),
                        int(rgb[1] * 255),
                        int(rgb[2] * 255)
                    )

            self.statusBar.showMessage(f"已加载 {len(self.label_names)} 个标签")
        except Exception as e:
            self.statusBar.showMessage(f"加载标签文件失败: {str(e)}")

    def export_results(self):
        """导出检查结果"""
        if not self.image_files:
            self.statusBar.showMessage("没有可导出的结果")
            return

        # 获取保存路径
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"check_results_{timestamp}.csv"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出结果",
            default_name,
            "CSV Files (*.csv)"
        )

        if not file_path:
            return

        try:
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                # 写入表头
                writer.writerow(["文件名", "状态", "问题详情"])

                # 写入所有行的数据
                for row in range(self.file_table.rowCount()):
                    file_name = self.file_table.item(row, 0).text()
                    status = self.file_table.item(row, 1).text()
                    details = self.file_table.item(row, 2).text()
                    writer.writerow([file_name, status, details])

            self.statusBar.showMessage(f"结果已导出到: {file_path}")

        except Exception as e:
            self.statusBar.showMessage(f"导出失败: {str(e)}")

    def refresh_check(self):
        """检查所有文件的标注"""
        if not self.image_files:
            self.statusBar.showMessage("没有加载任何文件")
            return

        # 如果已有正在运行的检查任务，先停止它
        if self.check_worker and self.check_worker.isRunning():
            self.check_worker.stop()
            self.check_worker.wait()

        # 更新检查器的阈值
        self.checker.overlap_threshold = self.threshold_slider.value() / 100.0

        # 创建并启动工作线程
        self.check_worker = CheckWorker(
            self.image_files,
            self.annotation_files,
            self.checker
        )
        self.check_worker.progress.connect(self.update_check_progress)
        self.check_worker.finished.connect(self.on_check_finished)

        # 用相关控件
        self.btn_refresh.setEnabled(False)
        self.threshold_slider.setEnabled(False)
        self.statusBar.showMessage("正在检查...")

        self.check_worker.start()

    def update_check_progress(self, row: int, status: str, details: str, color: str):
        """更新检查进度"""
        self.set_row_status(row, status, details, QColor(color))

    def on_check_finished(self):
        """检查完成时的处理"""
        # 新启用控件
        self.btn_refresh.setEnabled(True)
        self.threshold_slider.setEnabled(True)
        self.statusBar.showMessage("检查完成")

        # 更新状态栏统计信息
        self.update_status_counts()

        # 如果当前有选中的文件，重新加载预览以更新显示
        if self.current_image:
            self.load_preview(self.current_image)

    def threshold_changed(self, value):
        """当重叠阈值改变时更"""
        self.statusBar.showMessage(f"重叠阈值: {value}%")
        # 使用计时器延迟执行检查，避免滑动时频繁更新
        if hasattr(self, '_threshold_timer'):
            self._threshold_timer.stop()
        else:
            self._threshold_timer = QTimer()
            self._threshold_timer.setSingleShot(True)
            self._threshold_timer.timeout.connect(self.refresh_check)
        self._threshold_timer.start(500)  # 500ms 后执行检查

    def on_selection_changed(self):
        """当选择的文件改变时更新预览"""
        selected_items = self.file_table.selectedItems()
        if not selected_items:
            return

        row = selected_items[0].row()
        image_path = self.image_files[row]

        # 如果是同一张图片，不需要处理
        if image_path == self.current_image:
            return

        # 如果当前图片已修改，提示保存
        if self.has_changes and self.current_image:
            if not self.maybe_save():
                # 如果用户取消，复之前的选择
                current_index = self.image_files.index(self.current_image)
                self.file_table.selectRow(current_index)
                return

        self.load_preview(image_path)

    def load_preview(self, image_path: str):
        """加载并显示图片及其标注框"""
        # 清除现有场景重置修改状态
        self.has_changes = False
        self.current_image = image_path
        self.preview_scene.clear()

        # 加载图片
        image = cv2.imread(image_path)
        if image is None:
            self.statusBar.showMessage(f"无法加载图片: {image_path}")
            return

        # BGR to RGB
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        height, width, channel = image.shape

        # 创建QImage
        bytes_per_line = channel * width
        q_image = QImage(image.data, width, height, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(q_image)

        # 添加图片到场景
        self.preview_scene.addPixmap(pixmap)
        self.preview_scene.setSceneRect(QRectF(pixmap.rect()))

        # 自适应视图大小
        self.preview_view.fitInView(self.preview_scene.sceneRect(),
                                    Qt.AspectRatioMode.KeepAspectRatio)

        # 加载并显示标注框
        self.load_and_show_annotations(width, height)

        # 更新类别列表
        self.update_category_list()

        # 更新窗口标题
        self.setWindowTitle(f"YOLO 标注检查工具 - {image_path}")

    def load_and_show_annotations(self, image_width: int, image_height: int):
        """加载并显示标注框"""
        if not self.current_image:
            return

        # 获取对应的标注文件
        image_name = Path(self.current_image).stem
        if image_name not in self.annotation_files:
            return

        # 加载标注文件
        anno_path = self.annotation_files[image_name]
        self.current_annotation = AnnotationFile(anno_path)

        # 检查标注问题
        issues = self.checker.check_annotation(self.current_annotation)

        # 绘制所有标注框
        for i, box in enumerate(self.current_annotation.boxes):
            # 转换YOLO格式到像素坐标
            x = (box.x - box.w / 2) * image_width
            y = (box.y - box.h / 2) * image_height
            w = box.w * image_width
            h = box.h * image_height

            # 确定注框类型
            box_type = 'normal'
            if any(i in (a, b) for a, b, _ in issues['overlaps']):
                box_type = 'overlap'
            elif any(i == idx for idx, _, _ in issues['invalid_labels']):
                box_type = 'invalid_label'

            # 创建可编辑的标注框
            editable_box = EditableBox(x, y, w, h,
                                       self.on_box_changed,  # 直接传递方法引用
                                       class_id=box.class_id,
                                       editable=False,
                                       box_type=box_type,
                                       main_window=self)
            self.preview_scene.addItem(editable_box)

            # 如果有标签名称，显示标签（作为独立的景项）
            if 0 <= box.class_id < len(self.label_names):
                label_name = self.label_names[box.class_id]
                label_text = QGraphicsTextItem()
                label_text.setPlainText(label_name)
                # 使用标签对应的颜色
                label_text.setDefaultTextColor(self.label_colors.get(label_name, Qt.white))
                # 置标签位置（在标注框上方）
                label_text.setPos(x, y - 20)
                self.preview_scene.addItem(label_text)
                # 将标签与注关联（后续新）
                editable_box.label_item = label_text

    def resizeEvent(self, event):
        """口大小改变时重新适应视图"""
        super().resizeEvent(event)
        if self.preview_scene.items():
            self.preview_view.fitInView(
                self.preview_scene.sceneRect(),
                Qt.AspectRatioMode.KeepAspectRatio
            )

    def setup_menu(self):
        """设置菜单栏"""
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu("文件")
        
        # 自动保存选项
        self.auto_save_action = file_menu.addAction("自动保存修改")
        self.auto_save_action.setCheckable(True)  # 设置为可勾选
        self.auto_save_action.setChecked(self.auto_save)  # 设置初始状态
        self.auto_save_action.triggered.connect(self.toggle_auto_save)

    def toggle_auto_save(self, checked: bool):
        """切换自动保存选项"""
        self.auto_save = checked
        self.settings.setValue("auto_save", checked)  # 保存设置

    def keyPressEvent(self, event):
        """键盘事件处理"""
        # 如果正在绘制，不处理键盘事件
        if self.is_drawing:
            super().keyPressEvent(event)
            return

        # 优先处理 A、D 键切换图片，不考虑焦点位置
        if event.key() == Qt.Key_A:
            self.prev_image()
            return
        elif event.key() == Qt.Key_D:
            self.next_image()
            return

        # 其他键盘事件处理
        if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_E:
            self.edit_selected_label()
        elif event.key() == Qt.Key_Delete:
            self.delete_selected_box()
        elif event.key() == Qt.Key_W:
            self.add_new_box()
        else:
            super().keyPressEvent(event)

    def edit_selected_label(self):
        """编辑选中标注框的标签"""
        items = self.preview_scene.selectedItems()
        if not items or not isinstance(items[0], EditableBox):
            return

        box = items[0]
        current_label = self.label_names[box.class_id] if box.class_id < len(self.label_names) else ""

        dialog = LabelEditorDialog(self, current_label, self.label_names)
        if dialog.exec():
            new_label = dialog.get_selected_label()
            if new_label in self.label_names:
                # 更新注框的类别ID
                box.class_id = self.label_names.index(new_label)
                # 更新标签文本
                if box.label_item:
                    box.label_item.setPlainText(new_label)
                    box.label_item.setDefaultTextColor(
                        self.label_colors.get(new_label, Qt.white))
                # 标记已修改
                self.has_changes = True
                # 如果开启自动保存，立即保存
                if self.auto_save:
                    self.save_current_annotation()

    def delete_selected_box(self):
        """删除选中的标注框"""
        items = self.preview_scene.selectedItems()
        if items:
            for item in items:
                if isinstance(item, EditableBox):
                    # 删除标签
                    if item.label_item:
                        self.preview_scene.removeItem(item.label_item)
                    # 删除标注框
                    self.preview_scene.removeItem(item)
            # 标记为已修改，但不立即保存
            self.has_changes = True
            # 更新类别列表
            self.update_category_list()

    def add_new_box(self):
        """添加新标注框"""
        if not self.current_image:
            return

        # 启用场景的鼠标追踪
        self.preview_view.setMouseTracking(True)
        self.preview_scene.mousePressEvent = self.scene_mouse_press
        self.preview_scene.mouseMoveEvent = self.scene_mouse_move
        self.preview_scene.mouseReleaseEvent = self.scene_mouse_release

        # 设置状态
        self.is_drawing = True
        self.draw_start_pos = None
        self.current_box = None

        # 设置鼠标指针为十字形
        self.preview_view.setCursor(Qt.CrossCursor)

    def scene_mouse_press(self, event):
        """场景鼠标按下事件"""
        if self.is_drawing:
            # 右键取消绘制
            if event.button() == Qt.RightButton:
                self.cancel_drawing()
            # 左键绘制
            elif event.button() == Qt.LeftButton:
                self.draw_start_pos = event.scenePos()

    def scene_mouse_move(self, event):
        """场景鼠标移动事件"""
        if self.is_drawing and self.draw_start_pos:
            if self.current_box:
                if self.current_box.label_item:
                    self.preview_scene.removeItem(self.current_box.label_item)
                self.preview_scene.removeItem(self.current_box)

            pos = event.scenePos()
            x = min(self.draw_start_pos.x(), pos.x())
            y = min(self.draw_start_pos.y(), pos.y())
            w = abs(pos.x() - self.draw_start_pos.x())
            h = abs(pos.y() - self.draw_start_pos.y())

            self.current_box = EditableBox(
                x, y, w, h,
                on_change=self.on_box_changed,
                class_id=0,
                editable=True,  # 确保新绘制的标注框是可编辑的
                box_type='normal',
                main_window=self
            )
            self.current_box.setSelected(True)  # 立即选中
            self.current_box.set_editable(True)  # 立即设置为可编辑
            self.current_box.setFocus()  # 立即获得焦点
            self.preview_scene.addItem(self.current_box)

    def scene_mouse_release(self, event):
        """场景鼠标释放事件"""
        if self.is_drawing and event.button() == Qt.LeftButton:
            self.finish_drawing()

    def cancel_drawing(self):
        """取消绘制"""
        if self.current_box:
            if self.current_box.label_item:
                self.preview_scene.removeItem(self.current_box.label_item)
            self.preview_scene.removeItem(self.current_box)
            self.current_box = None

        # 重置所有状态
        self.is_drawing = False
        self.preview_view.setMouseTracking(False)

        # 恢复原始的事件处理器
        self.preview_scene.mousePressEvent = self.original_mouse_press
        self.preview_scene.mouseMoveEvent = self.original_mouse_move
        self.preview_scene.mouseReleaseEvent = self.original_mouse_release

        self.preview_view.unsetCursor()  # 恢复默认鼠标指针

    def finish_drawing(self):
        """完成绘制"""
        self.is_drawing = False
        self.preview_view.setMouseTracking(False)

        # 恢复原始的事件处理器
        self.preview_scene.mousePressEvent = self.original_mouse_press
        self.preview_scene.mouseMoveEvent = self.original_mouse_move
        self.preview_scene.mouseReleaseEvent = self.original_mouse_release

        self.preview_view.unsetCursor()

        if self.current_box:
            self.has_changes = True
            self.update_category_list()

    def on_box_changed(self):
        """标注框改变时的处理"""
        self.has_changes = True

    def maybe_save(self) -> bool:
        """根据设置决定是否保存
        返回值：
            bool: True 表示可以继续（已保存或选择保存），False 表示取消操作
        """
        if self.has_changes:
            if self.auto_save:
                self.save_current_annotation()
                return True
            else:
                # 创建自定义按钮
                save_button = QPushButton("保存")
                discard_button = QPushButton("不保存")
                cancel_button = QPushButton("取消")

                # 创建消息框
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("保存修改")
                msg_box.setText("标注已修改，是否保存？")
                msg_box.addButton(save_button, QMessageBox.AcceptRole)
                msg_box.addButton(discard_button, QMessageBox.DestructiveRole)
                msg_box.addButton(cancel_button, QMessageBox.RejectRole)

                # 显示消息框并获取结果
                ret = msg_box.exec()

                # 根据用户选择执行相应操作
                if msg_box.clickedButton() == save_button:
                    self.save_current_annotation()
                    return True
                elif msg_box.clickedButton() == discard_button:
                    return True
                else:  # cancel_button
                    return False
        return True

    def save_current_annotation(self):
        """保存当前注"""
        if not self.current_image or not self.has_changes:
            return

        # 获所有标注框
        boxes = []
        for item in self.preview_scene.items():
            if isinstance(item, EditableBox):
                rect = item.rect()
                pos = item.pos()
                # 转换为YOLO格式
                x = (pos.x() + rect.center().x()) / self.preview_scene.width()
                y = (pos.y() + rect.center().y()) / self.preview_scene.height()
                w = rect.width() / self.preview_scene.width()
                h = rect.height() / self.preview_scene.height()
                # 添加别ID
                boxes.append(f"{item.class_id} {x:.6f} {y:.6f} {w:.6f} {h:.6f}")

        # 保存到文件
        image_name = Path(self.current_image).stem
        anno_path = self.annotation_files[image_name]
        try:
            with open(anno_path, 'w') as f:
                f.write('\n'.join(boxes))
            self.has_changes = False
            self.statusBar.showMessage("保存成功")
        except Exception as e:
            self.statusBar.showMessage(f"保存失败: {str(e)}")

    def refresh_single_file(self, image_path: str):
        """刷单个文件检查状态"""
        if not image_path or image_path not in self.image_files:
            return

        row = self.image_files.index(image_path)
        image_name = Path(image_path).stem
        if image_name not in self.annotation_files:
            return

        # 加载并检查标注
        annotation = AnnotationFile(self.annotation_files[image_name])
        issues = self.checker.check_annotation(annotation)

        # 更新状态
        if not any(issues.values()):
            self.set_row_status(row, "正常", "", QColor("#FFFFFF"))
        else:
            details = []
            if issues['overlaps']:
                details.append(f"发现 {len(issues['overlaps'])} 处重叠")
                self.set_row_status(
                    row, "重叠问题",
                    "; ".join(details),
                    QColor("#FFD0D0")  # 浅红色
                )
            if issues['invalid_labels']:
                details.append(f"发现 {len(issues['invalid_labels'])} 个无标签")
                self.set_row_status(
                    row, "标签问题",
                    "; ".join(details),
                    QColor("#FFFFD0")  # 浅黄色
                )

    def prev_image(self):
        """显示上一张图片"""
        if not self.image_files or not self.current_image:
            return

        current_index = self.image_files.index(self.current_image)
        if current_index > 0:
            # 如果有未保存的修改
            if self.has_changes:
                # 不管状态如何，都使用 maybe_save 来处理保存
                if not self.maybe_save():
                    return  # 如果用户取消，则不切换图片
                # 如果状态异常，刷新状态
                current_status = self.file_table.item(current_index, 1).text()
                if current_status != "正常":
                    self.refresh_single_file(self.current_image)

            # 加载上一张图片
            self.load_preview(self.image_files[current_index - 1])
            # 更新列表选中项
            self.file_table.selectRow(current_index - 1)

    def next_image(self):
        """显示下一张图片"""
        if not self.image_files or not self.current_image:
            return

        current_index = self.image_files.index(self.current_image)
        if current_index < len(self.image_files) - 1:
            # 如果有未保存的修改
            if self.has_changes:
                # 不管状态如何，都使用 maybe_save 来处理保存
                if not self.maybe_save():
                    return  # 如果用户取消，则不切换图片
                # 如果状态异常，刷新状态
                current_status = self.file_table.item(current_index, 1).text()
                if current_status != "正常":
                    self.refresh_single_file(self.current_image)

            # 加载下一张图片
            self.load_preview(self.image_files[current_index + 1])
            # 更新列表选中项
            self.file_table.selectRow(current_index + 1)

    def update_category_list(self):
        """更新类别列表"""
        self.category_list.clear()
        if not self.current_image:
            return

        # 收集所有标注框，按类别分组但保持独立项目
        box_items = []  # [(label_name, box, scene_box), ...]

        # 收集标注框
        for item in self.preview_scene.items():
            if isinstance(item, EditableBox):
                if item.class_id < len(self.label_names):
                    label = self.label_names[item.class_id]
                    # 计算标注框在YOLO格式下的坐标
                    rect = item.rect()
                    pos = item.pos()
                    x = (pos.x() + rect.center().x()) / self.preview_scene.width()
                    y = (pos.y() + rect.center().y()) / self.preview_scene.height()
                    w = rect.width() / self.preview_scene.width()
                    h = rect.height() / self.preview_scene.height()
                    # 建对应的BBox对象用于比较
                    yolo_box = BBox(item.class_id, x, y, w, h)
                    box_items.append((label, item, yolo_box))

        # 获取当前标注文件的问题
        image_name = Path(self.current_image).stem
        anno_path = self.annotation_files[image_name]
        annotation = AnnotationFile(anno_path)
        issues = self.checker.check_annotation(annotation)

        # 加到列表
        for label, scene_box, yolo_box in box_items:
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, [scene_box])  # 存储关联的标注框

            # 查找对应的标注框索引
            box_index = -1
            for i, box in enumerate(annotation.boxes):
                if (abs(box.x - yolo_box.x) < 0.001 and
                        abs(box.y - yolo_box.y) < 0.001 and
                        abs(box.w - yolo_box.w) < 0.001 and
                        abs(box.h - yolo_box.h) < 0.001):
                    box_index = i
                    break

            # 根据问题类型设置颜色
            if box_index >= 0:
                if any(box_index in (a, b) for a, b, _ in issues['overlaps']):
                    # 重叠问题 - 红色
                    item.setForeground(Qt.red)
                elif any(box_index == idx for idx, _, _ in issues['invalid_labels']):
                    # 标签问题 - 黄色
                    item.setForeground(Qt.yellow)

            self.category_list.addItem(item)

    def on_category_selected(self, item):
        """当选择类别时"""
        # 取消所有标注框选中状态
        for box_item in self.preview_scene.items():
            if isinstance(box_item, EditableBox):
                box_item.setSelected(False)
                box_item.set_editable(False)

        # 选中该类别的所有标注框
        boxes = item.data(Qt.UserRole)
        for box in boxes:
            self.select_box(box)

    def select_box(self, box: EditableBox, select: bool = True):
        """选中或取消选中标注框，并同步类别列表"""
        box.setSelected(select)
        box.set_editable(select)

        # 同步类别列表选择
        if select:
            # 查找对应的类别列表项（通过关联的标注框来确定）
            for i in range(self.category_list.count()):
                item = self.category_list.item(i)
                item_boxes = item.data(Qt.UserRole)
                if item_boxes and item_boxes[0] == box:  # 比较标注框对象
                    self.category_list.setCurrentItem(item)
                    break

    def table_key_press_event(self, event):
        """件列表的键盘事件处理"""
        if event.key() == Qt.Key_A:
            self.prev_image()
        elif event.key() == Qt.Key_D:
            self.next_image()
        else:
            # 调用原始的键盘事件处理
            QTableWidget.keyPressEvent(self.file_table, event)

    def update_status_counts(self):
        """更新状态栏的统计信息"""
        total_files = len(self.image_files)
        total_overlaps = 0
        total_invalid_labels = 0

        # 统计所有文件的问题
        for image_path in self.image_files:
            image_name = Path(image_path).stem
            if image_name in self.annotation_files:
                annotation = AnnotationFile(self.annotation_files[image_name])
                issues = self.checker.check_annotation(annotation)
                total_overlaps += len(issues['overlaps'])
                total_invalid_labels += len(issues['invalid_labels'])

        # 更新状态栏显示
        self.total_files_label.setText(f"文件总数: {total_files}")
        self.total_overlaps_label.setText(f"重叠总数: {total_overlaps}")
        self.total_invalid_labels_label.setText(f"无标签总数: {total_invalid_labels}")
