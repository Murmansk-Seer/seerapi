# SPDX-License-Identifier: MIT
"""Immutable render-asset repository snapshot loading for SeerAPI builds."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import json
import logging
from pathlib import Path
import shutil
import subprocess
import tempfile
from urllib.error import HTTPError, URLError


@dataclass(frozen=True, slots=True)
class AssetRepositorySnapshot:
    """One immutable Git tree used to publish remote render material facts."""

    revision: str
    blobs_by_path: dict[str, str]
    repository: str = "Murmansk-Seer/seer-unity-assets"


@dataclass(frozen=True, slots=True)
class RenderAssetRepository:
    """Repository endpoints needed to load one immutable render asset tree."""

    name: str
    git_url: str
    ref: str
    commit_url: str
    tree_url_template: str


def load_asset_repository_snapshot(
    repository: RenderAssetRepository,
    download_bytes: Callable[[str], bytes],
    *,
    logger: logging.Logger,
) -> AssetRepositorySnapshot | None:
    """Load a complete immutable asset tree, falling back from REST to Git."""

    try:
        commit_payload = json.loads(download_bytes(repository.commit_url).decode("utf-8"))
        revision = str(commit_payload.get("sha", "")).strip()
        if not revision:
            raise ValueError("repository commit response has no sha")
        tree_url = repository.tree_url_template.format(revision=revision)
        tree_payload = json.loads(download_bytes(tree_url).decode("utf-8"))
        if tree_payload.get("truncated") is True:
            raise ValueError("repository tree response is truncated")
        raw_tree = tree_payload.get("tree")
        if not isinstance(raw_tree, list):
            raise ValueError("repository tree response has no tree list")
        blobs_by_path = {
            str(entry["path"]): str(entry["sha"])
            for entry in raw_tree
            if isinstance(entry, dict)
            and entry.get("type") == "blob"
            and isinstance(entry.get("path"), str)
            and isinstance(entry.get("sha"), str)
        }
        if not blobs_by_path:
            raise ValueError("repository tree has no blob entries")
    except (
        HTTPError,
        URLError,
        TimeoutError,
        OSError,
        UnicodeDecodeError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        logger.warning(
            "Render asset REST snapshot is unavailable; trying Git tree fallback: %s",
            error,
        )
        return _load_asset_repository_snapshot_from_git(repository, logger=logger)
    return AssetRepositorySnapshot(
        repository=repository.name,
        revision=revision,
        blobs_by_path=blobs_by_path,
    )


def _load_asset_repository_snapshot_from_git(
    repository: RenderAssetRepository,
    *,
    logger: logging.Logger,
) -> AssetRepositorySnapshot | None:
    """Read commit/tree objects through Git without downloading the PNG corpus."""

    if shutil.which("git") is None:
        logger.warning("Git is unavailable; render asset scopes stay incomplete")
        return None
    try:
        with tempfile.TemporaryDirectory(prefix="seer-render-assets-") as temp_dir:
            checkout = Path(temp_dir) / "repository"
            subprocess.run(
                (
                    "git",
                    "clone",
                    "--quiet",
                    "--filter=blob:none",
                    "--no-checkout",
                    "--depth=1",
                    "--branch",
                    repository.ref,
                    repository.git_url,
                    str(checkout),
                ),
                check=True,
                capture_output=True,
                text=True,
                timeout=90,
            )
            revision = subprocess.run(
                ("git", "-C", str(checkout), "rev-parse", "HEAD"),
                check=True,
                capture_output=True,
                text=True,
                timeout=15,
            ).stdout.strip()
            tree = subprocess.run(
                ("git", "-C", str(checkout), "ls-tree", "-r", revision),
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            ).stdout
    except (OSError, subprocess.SubprocessError, TimeoutError) as error:
        logger.warning("Git render asset snapshot is unavailable: %s", error)
        return None
    try:
        blobs_by_path = parse_git_tree_blobs(tree)
    except ValueError as error:
        logger.warning("Git render asset tree is malformed: %s", error)
        return None
    return AssetRepositorySnapshot(
        repository=repository.name,
        revision=revision,
        blobs_by_path=blobs_by_path,
    )


def parse_git_tree_blobs(tree: str) -> dict[str, str]:
    """Parse stable ``git ls-tree -r`` blob records without reading blobs."""

    blobs_by_path: dict[str, str] = {}
    for line in tree.splitlines():
        metadata, separator, path = line.partition("\t")
        parts = metadata.split()
        if separator != "\t" or len(parts) != 3:
            raise ValueError("invalid ls-tree entry")
        _mode, kind, blob_id = parts
        if kind != "blob" or not path or not blob_id:
            continue
        blobs_by_path[path] = blob_id
    if not blobs_by_path:
        raise ValueError("tree has no blob entries")
    return blobs_by_path
