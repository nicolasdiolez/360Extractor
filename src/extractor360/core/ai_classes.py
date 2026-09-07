"""
AI configuration that does NOT require torch/ultralytics.

Holds the COCO class mapping (readable names to COCO IDs 0-79) and the
segmentation-model naming/resolution helpers, so the processing core can be
imported — and the CLI can run without AI — on machines where the heavy AI
stack is not installed.
"""
import os

# Segmentation model variants shipped by Ultralytics, smallest/fastest first.
# Standard weights are provisioned in the model cache; missing weights may be
# downloaded by Ultralytics on first use.
AI_MODEL_VARIANTS = {
    'n': 'yolo26n-seg.pt',
    's': 'yolo26s-seg.pt',
    'm': 'yolo26m-seg.pt',
    'l': 'yolo26l-seg.pt',
    'x': 'yolo26x-seg.pt',
}
DEFAULT_AI_MODEL = AI_MODEL_VARIANTS['n']


def resolve_ai_model_name(value) -> str:
    """Resolve an ``ai_model`` setting into a concrete model name or path.

    Accepts a size letter (``n``/``s``/``m``/``l``/``x``), a full model name
    (``yolo26l-seg.pt``) or a custom path to a ``.pt`` file. Empty/unknown
    values fall back to the bundled nano model, so a bad setting can never
    crash the pipeline before inference even starts.
    """
    if not value:
        return DEFAULT_AI_MODEL
    value = str(value).strip()
    key = value.lower()
    if key in AI_MODEL_VARIANTS:
        return AI_MODEL_VARIANTS[key]
    # A path or an explicit .pt filename is passed through untouched.
    if value.endswith('.pt') or os.sep in value or (os.altsep and os.altsep in value):
        return value
    return DEFAULT_AI_MODEL


COCO_CLASSES = {
    0: 'person', 1: 'bicycle', 2: 'car', 3: 'motorcycle', 4: 'airplane', 
    5: 'bus', 6: 'train', 7: 'truck', 8: 'boat', 9: 'traffic light', 
    10: 'fire hydrant', 11: 'stop sign', 12: 'parking meter', 13: 'bench', 14: 'bird', 
    15: 'cat', 16: 'dog', 17: 'horse', 18: 'sheep', 19: 'cow', 
    20: 'elephant', 21: 'bear', 22: 'zebra', 23: 'giraffe', 24: 'backpack', 
    25: 'umbrella', 26: 'handbag', 27: 'tie', 28: 'suitcase', 29: 'frisbee', 
    30: 'skis', 31: 'snowboard', 32: 'sports ball', 33: 'kite', 34: 'baseball bat', 
    35: 'baseball glove', 36: 'skateboard', 37: 'surfboard', 38: 'tennis racket', 39: 'bottle', 
    40: 'wine glass', 41: 'cup', 42: 'fork', 43: 'knife', 44: 'spoon', 
    45: 'bowl', 46: 'banana', 47: 'apple', 48: 'sandwich', 49: 'orange', 
    50: 'broccoli', 51: 'carrot', 52: 'hot dog', 53: 'pizza', 54: 'donut', 
    55: 'cake', 56: 'chair', 57: 'couch', 58: 'potted plant', 59: 'bed', 
    60: 'dining table', 61: 'toilet', 62: 'tv', 63: 'laptop', 64: 'mouse', 
    65: 'remote', 66: 'keyboard', 67: 'cell phone', 68: 'microwave', 69: 'oven', 
    70: 'toaster', 71: 'sink', 72: 'refrigerator', 73: 'book', 74: 'clock', 
    75: 'vase', 76: 'scissors', 77: 'teddy bear', 78: 'hair drier', 79: 'toothbrush'
}

# Reverse mapping for string to ID
COCO_STR_TO_ID = {v.lower(): k for k, v in COCO_CLASSES.items()}

PRESETS = {
    "Humans": [0],
    "Vehicles": [2, 3, 4, 5, 6, 7, 8],
    "Plants": [58],
}

def parse_custom_classes(custom_str: str) -> list[int]:
    """Parse a comma-separated string of class names into COCO IDs."""
    if not custom_str.strip():
        return []
        
    ids = []
    # Split by comma and clean up whitespace
    items = [x.strip().lower() for x in custom_str.split(',')]
    for item in items:
        if item in COCO_STR_TO_ID:
            ids.append(COCO_STR_TO_ID[item])
    return ids
