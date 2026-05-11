"""
skills/files.py — File management

List, create, delete, move, and open files and folders.
"""

import asyncio
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class FilesSkill:
    async def list(self, path: str = "~/Desktop", **_) -> str:
        p = Path(path).expanduser()
        if not p.exists():
            return f"Path not found: {path}"
        items = sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name))
        names = [f"{'📁 ' if i.is_dir() else ''}{i.name}" for i in items[:20]]
        return f"{p}: " + ", ".join(names) + ("…" if len(items) > 20 else "")

    async def create(self, path: str, is_dir: bool = False, **_) -> str:
        p = Path(path).expanduser()
        if is_dir:
            p.mkdir(parents=True, exist_ok=True)
            return f"Folder created: {p.name}"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.touch()
        return f"File created: {p.name}"

    async def delete(self, path: str, **_) -> str:
        p = Path(path).expanduser()
        if not p.exists():
            return f"Not found: {path}"
        if p.is_dir():
            import shutil
            shutil.rmtree(p)
        else:
            p.unlink()
        return f"Deleted: {p.name}"

    async def move(self, source: str, destination: str, **_) -> str:
        src = Path(source).expanduser()
        dst = Path(destination).expanduser()
        if not src.exists():
            return f"Source not found: {source}"
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dst)
        return f"Moved {src.name} to {dst.parent.name}."

    async def open(self, path: str, **_) -> str:
        p = Path(path).expanduser()
        proc = await asyncio.create_subprocess_exec("open", str(p))
        await proc.communicate()
        return f"Opened {p.name}."
