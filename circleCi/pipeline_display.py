"""
CircleCI Pipeline 显示工具

提供时间格式化、UI 展示等辅助函数。
"""
from typing import Optional


def format_duration(started_at, stopped_at=None) -> str:
    """格式化持续时间

    Args:
        started_at: 开始时间（ISO 格式字符串或 datetime）
        stopped_at: 结束时间（可选，ISO 格式字符串或 datetime）

    Returns:
        str: 格式化后的持续时间字符串，如 "1h 30m 45s"
    """
    if not started_at:
        return 'N/A'

    try:
        from datetime import datetime, timezone

        # 解析 started_at
        if isinstance(started_at, str):
            start = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
        else:
            start = started_at

        # 确定结束时间
        if stopped_at:
            if isinstance(stopped_at, str):
                end = datetime.fromisoformat(stopped_at.replace('Z', '+00:00'))
            else:
                end = stopped_at
        else:
            # 如果没有 stopped_at，使用当前时间
            end = datetime.now(timezone.utc)

        # 计算时间差
        duration = end - start
        total_seconds = int(duration.total_seconds())

        if total_seconds < 0:
            return 'N/A'

        # 格式化显示
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    except Exception as e:
        return 'N/A'


def convert_utc_to_beijing(utc_time_str) -> Optional[str]:
    """将 UTC 时间转换为北京时间（UTC+8）

    Args:
        utc_time_str: UTC 时间字符串（ISO 格式）

    Returns:
        格式化后的北京时间字符串，如 "2024-01-15 14:30:00"，或 None
    """
    if not utc_time_str:
        return None

    try:
        from datetime import datetime, timedelta

        # 解析 UTC 时间
        if isinstance(utc_time_str, str):
            dt = datetime.fromisoformat(utc_time_str.replace('Z', '+00:00'))
        else:
            dt = utc_time_str

        # 转换为北京时间 (UTC+8)
        beijing_time = dt + timedelta(hours=8)

        # 格式化返回
        return beijing_time.strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        return utc_time_str


def format_time_ago(utc_time_str: str) -> str:
    """计算相对时间（多久之前）

    Args:
        utc_time_str: UTC 时间字符串

    Returns:
        相对时间描述，如 "3天前", "5小时前", "刚刚"
    """
    if not utc_time_str:
        return ""
    try:
        from datetime import datetime, timezone
        utc_time = datetime.fromisoformat(utc_time_str.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        delta = now - utc_time

        if delta.days > 0:
            return f"{delta.days}天前"
        elif delta.seconds >= 3600:
            hours = delta.seconds // 3600
            return f"{hours}小时前"
        elif delta.seconds >= 60:
            minutes = delta.seconds // 60
            return f"{minutes}分钟前"
        else:
            return "刚刚"
    except Exception as e:
        return ""


def small_metric(label: str, value: str):
    """小字体的 metric 展示（替代 st.metric 的 36px 大字）

    Args:
        label: 标签文字
        value: 值文字
    """
    import streamlit as st
    st.markdown(f"""
    <div style="font-size:13px; line-height:1.4; margin-bottom:4px;">
        <div style="color:#888; font-size:11px;">{label}</div>
        <div style="font-size:15px; font-weight:600; color:#333;">{value}</div>
    </div>
    """, unsafe_allow_html=True)