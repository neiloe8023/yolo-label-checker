import numpy as np
from dataclasses import dataclass
from typing import List, Tuple

@dataclass
class BBox:
    class_id: int
    x: float  # center x
    y: float  # center y
    w: float  # width
    h: float  # height
    
    def to_xyxy(self) -> Tuple[float, float, float, float]:
        """Convert from center format to corner format"""
        x1 = self.x - self.w/2
        y1 = self.y - self.h/2
        x2 = self.x + self.w/2
        y2 = self.y + self.h/2
        return (x1, y1, x2, y2)
    
    @staticmethod
    def calculate_iou(box1: 'BBox', box2: 'BBox') -> float:
        """Calculate IoU between two boxes"""
        x1_1, y1_1, x2_1, y2_1 = box1.to_xyxy()
        x1_2, y1_2, x2_2, y2_2 = box2.to_xyxy()
        
        # Calculate intersection area
        x1_i = max(x1_1, x1_2)
        y1_i = max(y1_1, y1_2)
        x2_i = min(x2_1, x2_2)
        y2_i = min(y2_1, y2_2)
        
        if x2_i < x1_i or y2_i < y1_i:
            return 0.0
            
        intersection = (x2_i - x1_i) * (y2_i - y1_i)
        
        # Calculate union area
        area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
        area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
        union = area1 + area2 - intersection
        
        return intersection / union if union > 0 else 0.0

class AnnotationFile:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.boxes: List[BBox] = []
        self.load_file()
    
    def load_file(self):
        """Load YOLO format annotation file"""
        try:
            with open(self.file_path, 'r') as f:
                for line in f:
                    values = list(map(float, line.strip().split()))
                    if len(values) == 5:
                        self.boxes.append(BBox(
                            class_id=int(values[0]),
                            x=values[1],
                            y=values[2],
                            w=values[3],
                            h=values[4]
                        ))
        except Exception as e:
            pass  # 静默处理错误