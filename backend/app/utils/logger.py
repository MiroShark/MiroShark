"""
Logging configuration module
Provides unified log management with output to both console and file
"""

import os
import sys
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Any


def _ensure_utf8_stdout() -> None:
    """
    Ensure stdout/stderr uses UTF-8 encoding
    Fixes character encoding issues on Windows console
    """
    if sys.platform == 'win32':
        # Reconfigure standard output to UTF-8 on Windows
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')


# Log directory
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs')


def setup_logger(name: str = 'miroshark', level: int = logging.DEBUG) -> logging.Logger:
    """
    Set up a logger

    Args:
        name: Logger name
        level: Log level

    Returns:
        Configured logger
    """
    # Ensure log directory exists
    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Prevent log propagation to root logger to avoid duplicate output
    logger.propagate = False
    
    # If handlers already exist, don't add duplicates
    if logger.handlers:
        return logger
    
    # Log format
    detailed_formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s: %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # 1. File handler - detailed logs (named by date, with rotation)
    log_filename = datetime.now().strftime('%Y-%m-%d') + '.log'
    file_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, log_filename),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    
    # 2. Console handler - concise logs (INFO and above)
    # Ensure UTF-8 encoding on Windows to avoid character encoding issues
    _ensure_utf8_stdout()
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


def get_logger(name: str = 'miroshark') -> logging.Logger:
    """
    Get a logger (create one if it doesn't exist)

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        return setup_logger(name)
    return logger


logger = setup_logger()


# Convenience methods
def debug(msg: object, *args: object, **kwargs: Any) -> None:
    logger.debug(msg, *args, **kwargs)

def info(msg: object, *args: object, **kwargs: Any) -> None:
    logger.info(msg, *args, **kwargs)

def warning(msg: object, *args: object, **kwargs: Any) -> None:
    logger.warning(msg, *args, **kwargs)

def error(msg: object, *args: object, **kwargs: Any) -> None:
    logger.error(msg, *args, **kwargs)

def critical(msg: object, *args: object, **kwargs: Any) -> None:
    logger.critical(msg, *args, **kwargs)

