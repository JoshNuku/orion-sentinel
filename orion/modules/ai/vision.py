"""Vision AI: YOLOv3-Tiny wrapper for ORION."""
import cv2
import numpy as np
import logging
import os
from .. import config

logger = logging.getLogger(__name__)


class IntelligenceUnit:
    def __init__(self):
        self.net = None
        self.classes = []
        self.output_layers = []
        self.loaded = False
        self.frame_count = 0
        self.model_loaded = False

    def load_model(self):
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            weights_path = os.path.join(base_dir, config.YOLO_WEIGHTS)
            config_path = os.path.join(base_dir, config.YOLO_CONFIG)
            classes_path = os.path.join(base_dir, config.YOLO_CLASSES)
            with open(classes_path, 'r') as f:
                self.classes = [line.strip() for line in f.readlines()]
            logger.info(f"📋 Loaded {len(self.classes)} classes from COCO dataset")
            self.net = cv2.dnn.readNet(weights_path, config_path)
            self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
            self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
            layer_names = self.net.getLayerNames()
            self.output_layers = [layer_names[i - 1] for i in self.net.getUnconnectedOutLayers()]
            self.model_loaded = True
            logger.info("🧠 YOLOv3-Tiny model loaded successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Model load failed: {e}")
            return False

    def unload_model(self):
        self.net = None
        self.classes = []
        self.output_layers = []
        self.model_loaded = False
        logger.info("💤 AI model unloaded")

    def analyze_frame(self, frame):
        if not self.model_loaded:
            return None, 0.0
        try:
            height, width = frame.shape[:2]
            blob = cv2.dnn.blobFromImage(frame, 1/255.0, (config.INPUT_SIZE, config.INPUT_SIZE), swapRB=True, crop=False)
            self.net.setInput(blob)
            outputs = self.net.forward(self.output_layers)
            detections = self._parse_detections(outputs, width, height)
            self.frame_count += 1
            if config.DEBUG_SAVE_FRAMES and self.frame_count % 30 == 0:
                cv2.imwrite(f"debug_frame_{self.frame_count}.jpg", frame)
                logger.info(f"💾 Saved debug_frame_{self.frame_count}.jpg")
            if detections:
                if config.DEBUG_SHOW_ALL_DETECTIONS:
                    logger.info(f"🔍 Detected {len(detections)} object(s):")
                    for class_name, confidence, bbox in detections:
                        logger.info(f"   • {class_name}: {confidence:.2%} at {bbox}")
            else:
                if config.DEBUG_SHOW_ALL_DETECTIONS:
                    logger.info(f"🔍 No objects detected in frame {self.frame_count} (size: {width}x{height})")

            def map_threat_type(class_name):
                if class_name in ["car"]:
                    return "car"
                if class_name in ["truck"]:
                    return "truck"
                if class_name in ["bus"]:
                    return "bus"
                if class_name in ["motorcycle"]:
                    return "motorcycle"
                if class_name == "person":
                    return "person"
                if class_name in ["dog", "cat", "bird", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe"]:
                    return "animal"
                return "unknown"

            threats = [d for d in detections if map_threat_type(d[0]) != "unknown"]
            if threats:
                best_threat = max(threats, key=lambda x: x[1])
                mapped_type = map_threat_type(best_threat[0])
                logger.warning(f"⚠️  THREAT: {mapped_type} ({best_threat[1]:.2%})")
                return mapped_type, best_threat[1]
            return "unknown", 0.0
        except Exception as e:
            logger.error(f"❌ Inference error: {e}")
            return None, 0.0

    def _parse_detections(self, outputs, width, height):
        boxes = []
        confidences = []
        class_ids = []
        for output in outputs:
            for detection in output:
                scores = detection[5:]
                class_id = np.argmax(scores)
                confidence = scores[class_id]
                if confidence > config.CONFIDENCE_THRESHOLD:
                    center_x = int(detection[0] * width)
                    center_y = int(detection[1] * height)
                    w = int(detection[2] * width)
                    h = int(detection[3] * height)
                    x = int(center_x - w / 2)
                    y = int(center_y - h / 2)
                    boxes.append([x, y, w, h])
                    confidences.append(float(confidence))
                    class_ids.append(class_id)

        indices = cv2.dnn.NMSBoxes(boxes, confidences, config.CONFIDENCE_THRESHOLD, config.NMS_THRESHOLD)
        detections = []
        if len(indices) > 0:
            for i in indices.flatten():
                class_name = self.classes[class_ids[i]]
                confidence = confidences[i]
                bbox = boxes[i]
                detections.append((class_name, confidence, bbox))
        return detections

    def is_loaded(self):
        return self.model_loaded
