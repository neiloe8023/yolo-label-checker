from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsItem
from PySide6.QtCore import Qt, QRectF, QPointF, QTimer
from PySide6.QtGui import QPen, QColor
from typing import Optional, Callable
import math


class EditableBox(QGraphicsRectItem):
    HANDLE_SIZE = 8
    HANDLE_SPACE = 4
    HANDLE_CURSORS = {
        0: Qt.SizeFDiagCursor,  # 左上
        1: Qt.SizeVerCursor,  # 上中
        2: Qt.SizeBDiagCursor,  # 右上
        3: Qt.SizeHorCursor,  # 右中
        4: Qt.SizeFDiagCursor,  # 右下
        5: Qt.SizeVerCursor,  # 下中
        6: Qt.SizeBDiagCursor,  # 左下
        7: Qt.SizeHorCursor,  # 左中
        8: Qt.CrossCursor  # 旋转手柄 (改用十字光标)
    }

    def __init__(self, x: float, y: float, w: float, h: float,
                 on_change: Optional[Callable] = None,
                 class_id: int = 0,
                 editable: bool = False,
                 box_type: str = 'normal',
                 main_window=None):
        # 先调用父类初始化
        super().__init__(0, 0, w, h)

        if on_change is None:
            raise ValueError("回调函数 on_change 不能为 None")
        self._on_change = on_change

        # 先设置基本属性
        self.class_id = class_id
        self.editable = editable
        self.box_type = box_type
        self.main_window = main_window
        self.handles = []
        self.handle_selected = None
        self.mouse_press_pos = None
        self.mouse_press_rect = None
        self.rotation_angle = 0
        self.label_item = None
        self.selected_handle = None  # 添加选中的锚点标记
        self.hovered_handle = None  # 添加悬浮的锚点标记

        # 设置缓存模式
        self.setCacheMode(QGraphicsItem.DeviceCoordinateCache)

        # 初始化手柄
        self.setup_handles()

        # 设置位置
        self.setPos(x, y)

        # 最后设置标志位，因为这会触发 itemChange
        self.setFlags(QGraphicsItem.ItemIsSelectable)

        # 添加键盘移动相关的变量
        self.move_speed = 1.0
        self.move_timer = QTimer()
        self.move_timer.timeout.connect(self.continue_move)
        self.current_move = QPointF(0, 0)

        # 启用鼠标追踪，以便接收 hoverMoveEvent
        self.setAcceptHoverEvents(True)

    def __del__(self):
        """析构函数"""
        pass

    def setup_handles(self):
        """初始化调整手柄"""
        self.handles = []
        for i in range(9):  # 8个调整手柄 + 1个旋转手柄
            self.handles.append(QRectF())
        self.update_handles()

    def update_handles(self):
        """更新手柄位置"""
        rect = self.rect()
        s = self.HANDLE_SIZE
        b = self.HANDLE_SPACE

        # 角落和边缘手柄
        self.handles[0] = QRectF(rect.left() - s / 2, rect.top() - s / 2, s, s)
        self.handles[1] = QRectF(rect.center().x() - s / 2, rect.top() - s / 2, s, s)
        self.handles[2] = QRectF(rect.right() - s / 2, rect.top() - s / 2, s, s)
        self.handles[3] = QRectF(rect.right() - s / 2, rect.center().y() - s / 2, s, s)
        self.handles[4] = QRectF(rect.right() - s / 2, rect.bottom() - s / 2, s, s)
        self.handles[5] = QRectF(rect.center().x() - s / 2, rect.bottom() - s / 2, s, s)
        self.handles[6] = QRectF(rect.left() - s / 2, rect.bottom() - s / 2, s, s)
        self.handles[7] = QRectF(rect.left() - s / 2, rect.center().y() - s / 2, s, s)

        # 旋转手柄
        self.handles[8] = QRectF(rect.center().x() - s / 2, rect.top() - b - s, s, s)

    def handle_at(self, point: QPointF) -> int:
        """返回当前的手柄索引"""
        for i, handle in enumerate(self.handles):
            if handle.contains(point):
                return i
        return None

    def set_editable(self, editable: bool):
        self.editable = editable
        if editable:
            self.setFlags(QGraphicsItem.ItemIsSelectable |
                          QGraphicsItem.ItemIsMovable |
                          QGraphicsItem.ItemIsFocusable)
            self.setFocus()
        else:
            self.setFlags(QGraphicsItem.ItemIsSelectable)
            self.clearFocus()
            self.move_timer.stop()
            self.current_move = QPointF(0, 0)
        self.update()

    def mousePressEvent(self, event):
        if not self.editable:
            self.set_editable(True)
            self.highlight_label(True)
            if self.main_window:
                self.main_window.select_box(self)
            super().mousePressEvent(event)
            return

        self.handle_selected = self.handle_at(event.pos())
        if self.handle_selected is not None:
            self.mouse_press_pos = event.pos()
            self.mouse_press_rect = self.rect()
        super().mousePressEvent(event)
        self.update()  # 重绘以显示高亮的锚点

    def mouseMoveEvent(self, event):
        if self.handle_selected is not None:
            if self.handle_selected == 8:  # 旋转手柄
                center = self.rect().center()
                angle = math.degrees(math.atan2(event.pos().y() - center.y(),
                                                event.pos().x() - center.x()))
                self.setRotation(angle)
                self.rotation_angle = angle
            else:
                rect = QRectF(self.mouse_press_rect)
                delta = event.pos() - self.mouse_press_pos

                if self.handle_selected in [0, 1, 2]:  # 上边
                    rect.setTop(rect.top() + delta.y())
                if self.handle_selected in [4, 5, 6]:  # 下边
                    rect.setBottom(rect.bottom() + delta.y())
                if self.handle_selected in [0, 7, 6]:  # 左边
                    rect.setLeft(rect.left() + delta.x())
                if self.handle_selected in [2, 3, 4]:  # 右边
                    rect.setRight(rect.right() + delta.x())

                self.setRect(rect.normalized())
                self.update_handles()

            self.notify_change()
        else:
            old_pos = self.pos()
            super().mouseMoveEvent(event)
            if old_pos != self.pos():
                if self.label_item:
                    self.label_item.setPos(self.pos().x(), self.pos().y() - 20)
                self.notify_change()

    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        super().mouseReleaseEvent(event)
        self.handle_selected = None  # 清除选中的锚点
        self.mouse_press_pos = None
        self.mouse_press_rect = None
        self.update_handles()
        self.update()  # 重绘以清除高亮

    def paint(self, painter, option, widget=None):
        """绘制标注框和手柄"""
        # 根据类型设置颜色
        if self.box_type == 'overlap':
            pen = QPen(Qt.red, 2)
        elif self.box_type == 'invalid_label':
            pen = QPen(Qt.yellow, 2)
        else:
            pen = QPen(Qt.green, 2)
        self.setPen(pen)

        super().paint(painter, option, widget)

        # 只在编辑模式且有焦点时显示手柄
        if self.editable and self.hasFocus():
            for i, handle in enumerate(self.handles):
                # 设置手柄颜色
                if i == self.handle_selected:  # 当前选中的锚点
                    painter.setBrush(QColor(255, 0, 0))  # 红色
                    painter.setPen(QPen(QColor(255, 0, 0), 1))
                elif i == self.hovered_handle:  # 鼠标悬浮的锚点
                    painter.setBrush(QColor(255, 165, 0))  # 橙色
                    painter.setPen(QPen(QColor(255, 165, 0), 1))
                else:
                    if i == 8:  # 旋转手柄使用绿色
                        painter.setBrush(QColor(0, 255, 0))
                    else:  # 其他手柄使用白色
                        painter.setBrush(QColor(255, 255, 255))
                    painter.setPen(QPen(QColor(0, 0, 0), 1))

                painter.drawRect(handle)

    def cursor_for_handle(self, handle: int):
        """返回手柄对应的光标"""
        if handle is None:
            return Qt.ArrowCursor
        return self.HANDLE_CURSORS.get(handle, Qt.ArrowCursor)

    def highlight_label(self, highlight: bool):
        """高亮或取消高亮标签"""
        if self.label_item and self.main_window:
            self.label_item.setDefaultTextColor(Qt.white if highlight else
                                                self.main_window.label_colors.get(
                                                    self.main_window.label_names[self.class_id], Qt.white))

    def itemChange(self, change, value):
        """项变化事件"""
        try:
            if change == QGraphicsItem.ItemSelectedChange:
                self.highlight_label(bool(value))

            if change == QGraphicsItem.ItemVisibleChange:
                return super().itemChange(change, value)

            return super().itemChange(change, value)
        except Exception:
            return super().itemChange(change, value)

    def focusOutEvent(self, event):
        """失去焦点时的处理"""
        super().focusOutEvent(event)
        self.set_editable(False)
        self.setSelected(False)
        self.highlight_label(False)

    def keyPressEvent(self, event):
        """键盘按下事件"""
        if not self.editable:
            return

        # 设置移动方向
        if event.key() == Qt.Key_Left:
            self.current_move = QPointF(-self.move_speed, 0)
        elif event.key() == Qt.Key_Right:
            self.current_move = QPointF(self.move_speed, 0)
        elif event.key() == Qt.Key_Up:
            self.current_move = QPointF(0, -self.move_speed)
        elif event.key() == Qt.Key_Down:
            self.current_move = QPointF(0, self.move_speed)
        else:
            super().keyPressEvent(event)
            return

        # 开始移动
        self.move_box()
        # 启动定时器，实现持续移动
        if not self.move_timer.isActive():
            self.move_timer.start(20)  # 50fps

    def keyReleaseEvent(self, event):
        """键盘释放事件"""
        if event.key() in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
            self.move_timer.stop()
            self.current_move = QPointF(0, 0)
        super().keyReleaseEvent(event)

    def continue_move(self):
        """持续移动"""
        if self.current_move != QPointF(0, 0):
            self.move_box()

    def move_box(self):
        """移动标注框"""
        new_pos = self.pos() + self.current_move
        self.setPos(new_pos)

        # 更新标签位置
        if self.label_item:
            self.label_item.setPos(new_pos.x(), new_pos.y() - 20)

        # 通知变更
        self.notify_change()

    def notify_change(self):
        """Notify change event."""
        if self._on_change is not None:
            try:
                self._on_change()
            except Exception as e:
                print(f"在调用回调函数时发生错误: {e}")
        else:
            print("错误：_on_change 回调函数为 None")

    def hoverMoveEvent(self, event):
        """鼠标悬浮移动事件"""
        if self.editable and self.hasFocus():
            # 检查是否悬浮在某个锚点上
            handle = self.handle_at(event.pos())
            if handle != self.hovered_handle:
                self.hovered_handle = handle
                self.update()  # 重绘以更新高亮显示
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):
        """鼠标离开事件"""
        if self.hovered_handle is not None:
            self.hovered_handle = None
            self.update()  # 重绘以清除高亮
        super().hoverLeaveEvent(event)
