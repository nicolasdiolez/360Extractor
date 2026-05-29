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
        Process a single image. Thin wrapper around process_batch for callers
        that only have one image.

        Returns:
            tuple: (processed_image, mask_or_status). See process_batch.
        """
        if mode == 'none' or self.model is None:
            return image, None
        return self.process_batch(
            [image], mode=mode, conf=conf, classes=classes,
            invert_mask=invert_mask, feather_mask=feather_mask
        )[0]

    @staticmethod
    def _build_mask(mask_tensors, image, invert_mask, feather_mask):
        """
        Build a binary/soft mask from YOLO segmentation tensors and resize it to
        the image size. Shared by single and batch processing.
        """
        # Combined hard mask (any detection above 0.5), used for the non-feather path.
        combined_mask = torch.any(mask_tensors > 0.5, dim=0).byte() * 255

        if feather_mask:
            # Soft edges: use probability values instead of hard thresholding.
            soft_mask_t = torch.max(mask_tensors, dim=0)[0]
            full_mask = soft_mask_t.cpu().numpy()
            full_mask = cv2.resize(full_mask, (image.shape[1], image.shape[0]), interpolation=cv2.INTER_LINEAR)
            full_mask = (full_mask * 255).astype(np.uint8)
        else:
            full_mask = combined_mask.cpu().numpy()
            full_mask = cv2.resize(full_mask, (image.shape[1], image.shape[0]), interpolation=cv2.INTER_NEAREST)

        # Refinement: dilation to cover edges/halos.
        k_size = max(3, int(image.shape[1] * 0.005))
        kernel = np.ones((k_size, k_size), np.uint8)
        full_mask = cv2.dilate(full_mask, kernel, iterations=1)

        # Photogrammetry convention: black (0) = ignore (the person),
        # white (255) = keep (background).
        return cv2.bitwise_not(full_mask) if invert_mask else full_mask

    @staticmethod
    def _empty_mask(image, invert_mask):
        """Full 'keep everything' mask when there is no detection."""
        h, w = image.shape[:2]
        bg_val = 255 if invert_mask else 0
        return bg_val * np.ones((h, w), dtype=np.uint8)

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
                    # res.masks.data is shape (N, H, W)
                    final_mask = self._build_mask(res.masks.data, img, invert_mask, feather_mask)
                    batch_results.append((img, final_mask))
                else:
                    batch_results.append((img, self._empty_mask(img, invert_mask)))
            else:
                batch_results.append((img, None))
                
        return batch_results