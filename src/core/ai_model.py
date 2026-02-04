import cv2
import numpy as np
import torch
from ultralytics import YOLO
from utils.logger import logger

class AIService:
    """
    Wrapper for YOLOv8 to handle person detection and segmentation.
    """
    
    @classmethod
    def is_gpu_available(cls) -> bool:
        """Check if GPU acceleration is available (MPS or CUDA)."""
        return torch.backends.mps.is_available() or torch.cuda.is_available()
    
    @classmethod
    def get_device_info(cls) -> dict:
        """Get detailed device information."""
        info = {
            'device': 'cpu',
            'device_name': 'CPU',
            'is_accelerated': False
        }
        
        if torch.backends.mps.is_available():
            info['device'] = 'mps'
            info['device_name'] = 'Apple Silicon GPU (MPS)'
            info['is_accelerated'] = True
        elif torch.cuda.is_available():
            info['device'] = 'cuda'
            info['device_name'] = torch.cuda.get_device_name(0)
            info['is_accelerated'] = True
            
        return info
    
    def __init__(self, model_name='yolo26n-seg.pt'):
        """
        Initialize the AI model.
        
        Args:
            model_name (str): Path or name of the YOLO model.
                              Defaults to 'yolov8n-seg.pt' (Nano Segmentation).
        """
        device_info = self.get_device_info()
        self.device = device_info['device']
        
        if not device_info['is_accelerated']:
            logger.warning("⚠️ No GPU detected! AI processing will be slow (running on CPU).")
            logger.info("For better performance, use a Mac with Apple Silicon or a CUDA-compatible GPU.")
        else:
            logger.info(f"✓ GPU detected: {device_info['device_name']}")
            
        logger.info(f"Loading AI Model: {model_name} on {self.device}...")
        self.model = YOLO(model_name)
        # Class 0 is 'person' in COCO dataset
        self.target_class = 0

    def process_image(self, image, mode='none'):
        """
        Process an image to detect/remove operators.
        
        Args:
            image (np.ndarray): The input image (BGR).
            mode (str): Processing mode - 'none', 'skip_frame', 'generate_mask'.
            
        Returns:
            tuple: (processed_image, mask_or_status)
                - If mode='skip_frame': returns (None, True) if person found, (image, False) otherwise.
                - If mode='generate_mask': returns (image, mask) where mask is binary (0=person, 255=bg).
                - If mode='none': returns (image, None).
        """
        if mode == 'none':
            return image, None
            
        # Run inference
        # stream=False ensures we get all results
        # Use the detected device
        results = self.model(image, classes=[self.target_class], device=self.device, verbose=False)
        
        has_detection = False
        if results and results[0].boxes:
            has_detection = True

        if mode == 'skip_frame':
            if has_detection:
                return None, True # Signal to skip
            else:
                return image, False

        if mode == 'generate_mask':
            mask = None
            if has_detection and results[0].masks:
                # Combine all masks for 'person' class
                # masks.data contains tensor masks
                masks_tensor = results[0].masks.data
                
                # Resize masks to original image size if needed (YOLO might resize)
                # Ultralytics results[0].masks.data is usually lower res. 
                # We can use results[0].plot() or handle masks manually.
                
                # Better approach: Get binary mask from results
                full_mask = np.zeros(image.shape[:2], dtype=np.uint8)
                
                for m in results[0].masks.xy:
                    # m is polygon coordinates
                    pts = np.array(m, np.int32)
                    pts = pts.reshape((-1, 1, 2))
                    # Fill the polygon on the mask
                    cv2.fillPoly(full_mask, [pts], 255)
                
                # Invert mask? 
                # Usually for photogrammetry: 
                # Black (0) = Ignore/Masked, White (255) = Keep.
                # So if we detected a person (drawn 255 above), we want that to be 0.
                
                # Current full_mask has 255 where person is.
                # We want 0 where person is, 255 elsewhere.
                final_mask = cv2.bitwise_not(full_mask)
                
                return image, final_mask
            else:
                # No person, return full white mask (keep everything)
                h, w = image.shape[:2]
                return image, 255 * np.ones((h, w), dtype=np.uint8)

        return image, None