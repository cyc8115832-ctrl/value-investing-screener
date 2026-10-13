"""SQLite保留既有naive UTC格式；排程一律使用台灣時區。"""
from datetime import datetime, timezone, timedelta

TAIWAN_TIMEZONE = timezone(timedelta(hours=8))


def utc_now_naive():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def taiwan_now():
    return datetime.now(TAIWAN_TIMEZONE)
