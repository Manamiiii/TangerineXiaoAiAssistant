from __future__ import annotations

from contextlib import contextmanager
import logging
from logging.handlers import RotatingFileHandler
import os
import sys
from pathlib import Path


def configure_logging(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("xiaoai_pc")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    for handler in logger.handlers:
        handler.close()
    logger.handlers.clear()
    handlers = [RotatingFileHandler(
        directory / "assistant.log", maxBytes=512_000, backupCount=2, encoding="utf-8"
    )]
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler())
    for handler in handlers:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)


@contextmanager
def single_instance(directory: Path):
    if os.name != "nt":
        raise RuntimeError("此版本仅支持 Windows。")
    import msvcrt

    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "assistant.lock"
    handle = path.open("a+b")
    try:
        handle.seek(0, 2)
        if not handle.tell():
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            raise RuntimeError("助手已有实例运行，请从托盘退出原实例，或在命令行窗口按 Ctrl+C 停止。") from None
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    finally:
        handle.close()
