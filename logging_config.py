import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
import os

# Define constants for logging
LOG_DIR = Path.home() / ".roo" / "logs"
LOG_FILE = LOG_DIR / "roo.log"
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10 MB
BACKUP_COUNT = 5  # Keep 5 backup files

def configure_logging(debug: bool = False):
    """
    Sets up logging configuration with rotation and formatting.
    Creates log directory if it doesn't exist.
    
    Args:
        debug (bool): If True, sets logging level to DEBUG and enables console output
    """
    try:
        # Create log directory if it doesn't exist
        os.makedirs(LOG_DIR, exist_ok=True)
        
        # Set up rotating file handler
        file_handler = RotatingFileHandler(
            filename=str(LOG_FILE),
            maxBytes=MAX_LOG_SIZE,
            backupCount=BACKUP_COUNT,
            encoding='utf-8'
        )
        
        # Define formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        
        # Configure console handler for debug output
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)

        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG if debug else logging.INFO)
        
        # Set handlers based on debug mode
        file_handler.setLevel(logging.DEBUG if debug else logging.INFO)
        console_handler.setLevel(logging.DEBUG if debug else logging.INFO)
        
        root_logger.addHandler(file_handler)
        # Do not add console handler by default to suppress initial messages
        # root_logger.addHandler(console_handler)
        
        logging.info("Logging system initialized") # This will now only go to the file
    except Exception as e:
        print(f"Failed to configure logging: {e}", file=sys.stderr)
        # Set up basic logging as fallback
        logging.basicConfig(
            level=logging.DEBUG if debug else logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )

def log_event(message: str, level: str = 'info', print_to_console: bool = False) -> None:
    """Logs a message with a specified log level."""
    try:
        # Log the message with the appropriate level
        if level == 'debug':
            logging.debug(message)
        elif level == 'info':
            logging.info(message)
        elif level == 'warning':
            logging.warning(message)
        elif level == 'error':
            logging.error(message)
        elif level == 'critical':
            logging.critical(message)
        
        # Optionally print to console
        if print_to_console:
            print(f"[{level.upper()}] {message}", file=sys.stderr)
    except Exception as e:
        # Handle logging failures
        print(f"CRITICAL LOGGING ERROR: {e} | Original message: {message}", file=sys.stderr)