from PySide6.QtCore import QThread, Signal
from pathlib import Path
from typing import Dict, List, Tuple
from core.annotation import AnnotationFile
from core.checker import AnnotationChecker


class CheckWorker(QThread):
    """标注检查工作线程"""
    progress = Signal(int, str, str, str)  # row, status, details, color
    finished = Signal()

    def __init__(self, image_files: List[str], annotation_files: Dict[str, str],
                 checker: AnnotationChecker):
        super().__init__()
        self.image_files = image_files
        self.annotation_files = annotation_files
        self.checker = checker
        self._running = True

    def stop(self):
        """停止检查"""
        self._running = False

    def run(self):
        """执行检查任务"""
        for row, image_path in enumerate(sorted(self.image_files)):
            if not self._running:
                break

            image_name = Path(image_path).stem
            anno_path = self.annotation_files[image_name]

            # 加载标注文件
            annotation = AnnotationFile(anno_path)

            # 检查标注
            issues = self.checker.check_annotation(annotation)

            # 发送进度信号
            if not any(issues.values()):
                self.progress.emit(row, "正常", "", "#FFFFFF")
            else:
                details = []
                if issues['overlaps']:
                    details.append(f"发现 {len(issues['overlaps'])} 处重叠")
                    self.progress.emit(
                        row, "重叠问题",
                        "; ".join(details),
                        "#FFD0D0"
                    )
                if issues['invalid_labels']:
                    details.append(f"发现 {len(issues['invalid_labels'])} 个无效标签")
                    self.progress.emit(
                        row, "标签问题",
                        "; ".join(details),
                        "#FFFFD0"
                    )

        self.finished.emit()
