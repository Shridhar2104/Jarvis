"""
orchestrator/agents/file_ops.py — Bulk file operations agent

Handles mass rename, directory reorganisation, and content
search-and-replace across repos. Reports a diff-style summary on completion.

Params (from job.context_json):
    operation:    "rename" | "move" | "search_replace" | "delete"
    source_dir:   str   — directory to operate on
    pattern:      str   — glob pattern or search string
    replacement:  str   — replacement string (for search_replace / rename)
    dry_run:      bool  — if True, report what would change without doing it
"""

import asyncio
import fnmatch
import logging
import re
from pathlib import Path

from orchestrator.agents.base import BaseAgent, AgentFailedError
from db.models import Job

logger = logging.getLogger(__name__)


class FileOpsAgent(BaseAgent):

    async def run(self) -> str:
        ctx = self.job.context_json
        operation: str = ctx.get("operation", "")
        source_dir = Path(ctx.get("source_dir", ".")).expanduser()
        pattern: str = ctx.get("pattern", "*")
        replacement: str = ctx.get("replacement", "")
        dry_run: bool = ctx.get("dry_run", False)

        if not source_dir.exists():
            raise AgentFailedError(f"Source directory not found: {source_dir}")

        self._log(f"FileOps: {operation} in {source_dir} | pattern={pattern}")

        if operation == "rename":
            return await self._rename(source_dir, pattern, replacement, dry_run)
        elif operation == "search_replace":
            return await self._search_replace(source_dir, pattern, replacement, dry_run)
        elif operation == "move":
            dest = Path(ctx.get("destination", "")).expanduser()
            return await self._move(source_dir, pattern, dest, dry_run)
        elif operation == "delete":
            return await self._delete(source_dir, pattern, dry_run)
        else:
            raise AgentFailedError(f"Unknown file operation: {operation}")

    # ── Operations ────────────────────────────────────────────────────────────

    async def _rename(self, directory: Path, pattern: str, replacement: str, dry_run: bool) -> str:
        matches = list(directory.rglob(pattern))
        if not matches:
            return f"No files matching '{pattern}' found in {directory}."

        renamed = 0
        for path in matches:
            new_name = re.sub(pattern, replacement, path.name)
            new_path = path.parent / new_name
            self._log(f"{'[dry-run] ' if dry_run else ''}rename: {path.name} → {new_name}")
            if not dry_run:
                path.rename(new_path)
                renamed += 1

        label = "Would rename" if dry_run else "Renamed"
        return f"{label} {len(matches)} files in {directory.name}."

    async def _search_replace(self, directory: Path, pattern: str, replacement: str, dry_run: bool) -> str:
        files = [f for f in directory.rglob("*") if f.is_file()]
        changed = 0
        for f in files:
            try:
                content = f.read_text(errors="ignore")
                if pattern in content:
                    new_content = content.replace(pattern, replacement)
                    self._log(f"{'[dry-run] ' if dry_run else ''}replace in: {f.relative_to(directory)}")
                    if not dry_run:
                        f.write_text(new_content)
                        changed += 1
            except Exception as e:
                self._log(f"Skipped {f.name}: {e}")

        label = "Would update" if dry_run else "Updated"
        return f"{label} {changed} files with replacement."

    async def _move(self, source: Path, pattern: str, dest: Path, dry_run: bool) -> str:
        dest.mkdir(parents=True, exist_ok=True)
        matches = list(source.glob(pattern))
        for path in matches:
            self._log(f"{'[dry-run] ' if dry_run else ''}move: {path.name} → {dest}")
            if not dry_run:
                path.rename(dest / path.name)
        label = "Would move" if dry_run else "Moved"
        return f"{label} {len(matches)} files to {dest.name}."

    async def _delete(self, directory: Path, pattern: str, dry_run: bool) -> str:
        matches = list(directory.rglob(pattern))
        for path in matches:
            self._log(f"{'[dry-run] ' if dry_run else ''}delete: {path}")
            if not dry_run:
                path.unlink(missing_ok=True)
        label = "Would delete" if dry_run else "Deleted"
        return f"{label} {len(matches)} files."
