import logging
from typing import Optional


def setup_logging(
    log_level: str = "INFO", log_file: Optional[str] = None
) -> logging.Logger:
    """
    设置日志配置

    Args:
        log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: 日志文件路径，如果为None则不保存到文件

    Returns:
        Logger对象
    """
    # 创建logger
    logger = logging.getLogger("atlas_generator")

    # 清除已有的处理器，避免重复
    if logger.handlers:
        logger.handlers.clear()

    # 设置日志级别
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    logger.setLevel(level_map.get(log_level.upper(), logging.INFO))

    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level_map.get(log_level.upper(), logging.INFO))

    # 创建文件处理器（如果需要）
    handlers = [console_handler]
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)  # 文件记录更详细的日志
        handlers.append(file_handler)

    # 设置日志格式
    formatter = logging.Formatter(
        "[%(asctime)s]%(name)s.%(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    for handler in handlers:
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
