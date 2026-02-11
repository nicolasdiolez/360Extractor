import cv2
import numpy as np
import torch
from ultralytics import YOLO
from utils.logger import logger

class AIService:
    """
    Wrapper for YOLO 26 to handle person detection and segmentation.
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
            
        # detailed logging
        logger.info(f"PyTorch Version: {torch.__version__}")
        if torch.cuda.is_available():
             logger.info(f"CUDA Available: True (Version: {torch.version.cuda})")
             logger.info(f"CUDA Device Count: {torch.cuda.device_count()}")
             logger.info(f"Current CUDA Device: {torch.cuda.current_device()}")
             logger.info(f"Device Name: {torch.cuda.get_device_name(0)}")
        else:
             logger.info("CUDA Available: False")
             
        return info
    
    def __init__(self, model_name='yolo26n-seg.pt'):
        """
        Initialize the AI model.
        """
        # 1. Setup Device
        device_info = self.get_device_info()
        self.device = device_info['device']
        
        if not device_info['is_accelerated']:
            logger.warning("⚠️ No GPU detected! AI processing will be slow (running on CPU).")
            logger.info("For better performance, use a Mac with Apple Silicon or a CUDA-compatible GPU.")
        else:
            logger.info(f"✓ GPU detected: {device_info['device_name']}")

        # 2. Load Model
        logger.info(f"Loading AI Model: {model_name} on {self.device}...")
        try:
            self.model = YOLO(model_name)
            logger.info(f"Successfully loaded {model_name}")
            logger.info(f"✅ ACTIVE AI MODEL: {model_name}")
        except Exception as e:
            logger.error(f"Failed to load model {model_name}: {e}")
            self.model = None

        # Class 0 is 'person' in COCO dataset
        # Future: Make this configurable in settings
        self.target_classes = [0] 

    def process_image(self, image, mode='none', conf=0.25):
        """
        Process an image to detect/remove operators.
        
        Args:
            image (np.ndarray): The input image (BGR).
            mode (str): Processing mode - 'none', 'skip_frame', 'generate_mask'.
            conf (float): Confidence threshold.
            
        Returns:
            tuple: (processed_image, mask_or_status)
                - If mode='skip_frame': returns (None, True) if person found, (image, False) otherwise.
                - If mode='generate_mask': returns (image, mask) where mask is binary (0=person, 255=bg).
                - If mode='none': returns (image, None).
        """
        if mode == 'none' or self.model is None:
            return image, None
            
        # Run inference
        # stream=False ensures we get all results
        results = self.model(image, classes=self.target_classes, device=self.device, verbose=False, conf=conf)
        
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
                # Get binary mask from results
                full_mask = np.zeros(image.shape[:2], dtype=np.uint8)
                
                for m in results[0].masks.xy:
                    # m is polygon coordinates
                    pts = np.array(m, np.int32)
                    pts = pts.reshape((-1, 1, 2))
                    # Fill the polygon on the mask
                    cv2.fillPoly(full_mask, [pts], 255)
                
                # Refinement: Dilation to cover edges/halos
                # Kernel size depends on resolution, but 5x5 is a safe start for 2k-4k
                kernel = np.ones((15, 15), np.uint8) 
                full_mask = cv2.dilate(full_mask, kernel, iterations=1)

                # Invert mask for photogrammetry convention:
                # Black (0) = Ignore/Masked (The Person), White (255) = Keep (Background).
                final_mask = cv2.bitwise_not(full_mask)
                
                return image, final_mask
            else:
                # No person, return full white mask (keep everything)
                h, w = image.shape[:2]
                return image, 255 * np.ones((h, w), dtype=np.uint8)

        return image, None