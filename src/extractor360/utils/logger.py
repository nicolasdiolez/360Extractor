import logging
import sys

def setup_logger(name="Application360", level=logging.INFO):
    """
    Sets up a logger with a consistent format.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Check if handler already exists to avoid duplicates
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            '[%(levelname)s] %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
    return logger

# Create a default logger instance
logger = setup_logger()