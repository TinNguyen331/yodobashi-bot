"""
Utility functions for Yodobashi Bot (HTTP version)
"""
import yaml
from datetime import datetime
from pathlib import Path
from loguru import logger


def load_config(config_path: str = "config.yaml") -> dict:
    """Load configuration from YAML file"""
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(
            f"Config file not found: {config_path}\n"
            "Please copy config.example.yaml to config.yaml and fill in your details."
        )
    with open(config_file, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def setup_logging(log_dir: str = "logs"):
    """Setup logging with loguru"""
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)
    log_file = log_path / f"bot_{datetime.now().strftime('%Y%m%d')}.log"

    import sys
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>",
        level="INFO",
        colorize=True
    )
    logger.add(
        str(log_file),
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
        level="DEBUG",
        rotation="1 day",
        retention="7 days"
    )
    return logger


def get_project_root() -> Path:
    """Get project root directory"""
    return Path(__file__).parent.parent


def wait_until_time(target_time_str: str, check_interval: int = 1):
    """Wait until target time is reached"""
    import time
    target_hour, target_minute = map(int, target_time_str.split(':'))

    while True:
        now = datetime.now()
        target = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
        if now >= target:
            logger.info(f"Target time {target_time_str} reached!")
            break
        remaining = (target - now).total_seconds()
        logger.debug(f"Waiting... {remaining:.0f}s remaining until {target_time_str}")
        time.sleep(min(check_interval, remaining))
