from typing import List, Dict, Tuple
from .annotation import AnnotationFile, BBox

class AnnotationChecker:
    def __init__(self, overlap_threshold: float = 0.6):
        self.overlap_threshold = overlap_threshold
        self.max_class_id = -1  # Will be set when loading labels file
        
    def set_labels(self, labels_file: str):
        """Load and set labels from file"""
        try:
            with open(labels_file, 'r') as f:
                labels = f.readlines()
                self.max_class_id = len(labels) - 1
        except Exception:
            pass  # 静默处理错误
            
    def check_annotation(self, anno: AnnotationFile) -> Dict[str, List[Tuple]]:
        """Check annotation file for issues"""
        issues = {
            'overlaps': [],
            'invalid_labels': []
        }
        
        # Check for invalid class IDs
        if self.max_class_id >= 0:
            for i, box in enumerate(anno.boxes):
                if box.class_id > self.max_class_id:
                    issues['invalid_labels'].append(
                        (i, box.class_id, self.max_class_id))
        
        # Check for overlapping boxes
        for i, box1 in enumerate(anno.boxes):
            for j, box2 in enumerate(anno.boxes[i+1:], i+1):
                iou = BBox.calculate_iou(box1, box2)
                if iou > self.overlap_threshold:
                    issues['overlaps'].append((i, j, iou))
        
        return issues 