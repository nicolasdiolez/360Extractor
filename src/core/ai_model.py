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

    def process_image(self, image, mode='none', conf=0.25, classes=None, invert_mask=True, feather_mask=False):
        """
        Process an image to detect/remove target objects.
        
        Args:
            image (np.ndarray): The input image (BGR).
            mode (str): Processing mode - 'none', 'skip_frame', 'generate_mask'.
            conf (float): Confidence threshold.
            classes (list): List of COCO class IDs to target.
            invert_mask (bool): If True, invert masks (black targets, white bg).
            
        Returns:
            tuple: (processed_image, mask_or_status)
                - If mode='skip_frame': returns (None, True) if targets found, (image, False) otherwise.
                - If mode='generate_mask': returns (image, mask) where mask is binary.
                - If mode='none': returns (image, None).
        """
        if mode == 'none' or self.model is None:
            return image, None
            
        # Run inference
        # stream=False ensures we get all results
        target_classes = classes if classes is not None else self.target_classes
        results = self.model(image, classes=target_classes, device=self.device, verbose=False, conf=conf)
        
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
                # Kernel size depends dynamically on image resolution
                k_size = max(3, int(image.shape[1] * 0.005))
                kernel = np.ones((k_size, k_size), np.uint8) 
                full_mask = cv2.dilate(full_mask, kernel, iterations=1)

                if feather_mask:
                    blur_k = k_size * 2 + 1
                    full_mask = cv2.GaussianBlur(full_mask, (blur_k, blur_k), 0)

                # Invert mask for photogrammetry convention:
                # Black (0) = Ignore/Masked (The Person), White (255) = Keep (Background).
                if invert_mask:
                    final_mask = cv2.bitwise_not(full_mask)
                else:
                    final_mask = full_mask
                
                return image, final_mask
            else:
                # No person, return full white mask (keep everything)
                h, w = image.shape[:2]
                bg_val = 255 if invert_mask else 0
                return image, bg_val * np.ones((h, w), dtype=np.uint8)

        return image, None

    def process_batch(self, images, mode='none', conf=0.25, classes=None, invert_mask=True, feather_mask=False):
        """
        Process a batch of images to detect/remove target objects.
        
        Args:
            images (list of np.ndarray): The input images (BGR).
            mode (str): Processing mode - 'none', 'skip_frame', 'generate_mask'.
            conf (float): Confidence threshold.
            classes (list): List of COCO class IDs to target.
            invert_mask (bool): If True, invert masks (black targets, white bg).
            
        Returns:
            list of tuples: [(processed_image, mask_or_status), ...]
        """
        if mode == 'none' or self.model is None or not images:
            return [(img, None) for img in images]
            
        # Run inference on the whole batch
        target_classes = classes if classes is not None else self.target_classes
        results = self.model(images, classes=target_classes, device=self.device, verbose=False, conf=conf)
        
        batch_results = []
        for i, res in enumerate(results):
            img = images[i]
            has_detection = False
            if res and res.boxes:
                has_detection = True

            if mode == 'skip_frame':
                if has_detection:
                    batch_results.append((None, True))
                else:
                    batch_results.append((img, False))
            elif mode == 'generate_mask':
                if has_detection and res.masks:
                    full_mask = np.zeros(img.shape[:2], dtype=np.uint8)
                    for m in res.masks.xy:
                        pts = np.array(m, np.int32).reshape((-1, 1, 2))
                        cv2.fillPoly(full_mask, [pts], 255)
                    k_size = max(3, int(img.shape[1] * 0.005))
                    kernel = np.ones((k_size, k_size), np.uint8)
                    full_mask = cv2.dilate(full_mask, kernel, iterations=1)
                    if feather_mask:
                        blur_k = k_size * 2 + 1
                        full_mask = cv2.GaussianBlur(full_mask, (blur_k, blur_k), 0)

                    if invert_mask:
                        final_mask = cv2.bitwise_not(full_mask)
                    else:
                        final_mask = full_mask
                    batch_results.append((img, final_mask))
                else:
                    h, w = img.shape[:2]
                    bg_val = 255 if invert_mask else 0
                    batch_results.append((img, bg_val * np.ones((h, w), dtype=np.uint8)))
            else:
                batch_results.append((img, None))
                
        return batch_results