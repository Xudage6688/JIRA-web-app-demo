"""
日志配置模块
提供统一的日志配置，替代 print() 调用
"""
import logging
import sys


def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    创建配置好的 logger

    Args:
        name: logger 名称
        level: 日志级别

    Returns:
        配置好的 Logger 实例
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s - %(name)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(level)

    return logger


# 模块级 logger 实例
circleci_logger = setup_logger('circleci')
jira_logger = setup_logger('jira')
config_logger = setup_logger('config')