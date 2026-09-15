# SPDX-License-Identifier: MIT
"""HTTP and bundle I/O adapters for the SeerAPI release build."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import io
import logging
from pathlib import Path
import shutil
import time
from typing import TypeVar
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class BuildHttpConfig:
    timeout_seconds: float
    retry_attempts: int
    retry_backoff_seconds: float
    user_agent: str = "SeerAPI data builder"


class BuildHttpClient:
    """Own retrying release-build HTTP access and atomic local downloads."""

    def __init__(self, config: BuildHttpConfig, *, logger: logging.Logger) -> None:
        self._config = config
        self._logger = logger

    def request(
        self,
        url: str,
        *,
        method: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> Request:
        request_headers = {"User-Agent": self._config.user_agent}
        if headers:
            request_headers.update(headers)
        return Request(url, headers=request_headers, method=method)

    def open_with_retries(self, request: Request):
        attempts = max(1, self._config.retry_attempts)
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
                return urlopen(request, timeout=self._config.timeout_seconds)
            except HTTPError as error:
                last_error = error
                if error.code < 500 and error.code != 429:
                    raise
            except (URLError, TimeoutError, OSError) as error:
                last_error = error

            if attempt >= attempts:
                break

            delay = self._config.retry_backoff_seconds * attempt
            self._logger.warning(
                "HTTP request failed (%s/%s): %s; retrying in %.1fs",
                attempt,
                attempts,
                last_error,
                delay,
            )
            time.sleep(delay)

        if last_error is not None:
            raise last_error
        raise RuntimeError("HTTP request failed without an exception")

    def download_bytes(self, url: str) -> bytes:
        with self.open_with_retries(self.request(url)) as response:
            return response.read()

    def download_file(self, url: str, path: Path) -> None:
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.unlink(missing_ok=True)
        with (
            self.open_with_retries(self.request(url)) as response,
            tmp_path.open("wb") as output,
        ):
            shutil.copyfileobj(response, output)
        tmp_path.replace(path)

    def copy_or_download_upstream_database(
        self,
        path: Path,
        *,
        upstream_path: str,
        upstream_url: str,
    ) -> None:
        """Use a verified local database when configured, otherwise download it."""
        if upstream_path:
            source = Path(upstream_path).expanduser()
            if not source.is_file():
                raise FileNotFoundError(
                    "Verified upstream SeerAPI database does not exist: " f"{source}"
                )
            if source.resolve() != path.resolve():
                shutil.copy2(source, path)
            return
        self.download_file(upstream_url, path)

    def probe_image(self, url: str, *, max_error_chars: int = 200) -> dict[str, str]:
        try:
            with self.open_with_retries(self.request(url, method="HEAD")) as response:
                headers = response.headers
                return {
                    "weekly_preview_status": str(response.status),
                    "weekly_preview_content_type": headers.get_content_type()
                    or "image/png",
                    "weekly_preview_content_length": headers.get(
                        "Content-Length", ""
                    ),
                    "weekly_preview_probe_error": "",
                }
        except (HTTPError, URLError, TimeoutError, OSError) as error:
            self._logger.warning("Weekly preview image probe skipped: %s", error)
            return {
                "weekly_preview_status": "",
                "weekly_preview_content_type": "",
                "weekly_preview_content_length": "",
                "weekly_preview_probe_error": str(error)[:max_error_chars],
            }

    def fetch_package_manifest(
        self,
        base_url: str,
        package_name: str,
        *,
        parse_manifest: Callable[[bytes], T],
    ) -> tuple[str, T]:
        normalized_base_url = base_url.rstrip("/") + "/"
        version_url = urljoin(
            normalized_base_url,
            f"PackageManifest_{package_name}.version",
        )
        version = self.download_bytes(
            f"{version_url}?t={int(time.time())}"
        ).decode().strip()
        manifest_url = urljoin(
            normalized_base_url,
            f"PackageManifest_{package_name}_{version}.bytes",
        )
        return version, parse_manifest(self.download_bytes(manifest_url))


def extract_text_assets(bundle_data: bytes, wanted: set[str]) -> dict[str, bytes]:
    """Read selected Unity TextAsset payloads from a ConfigPackage bundle."""
    import UnityPy

    result: dict[str, bytes] = {}
    env = UnityPy.load(io.BytesIO(bundle_data))
    for obj in env.objects:
        if obj.type.name != "TextAsset":
            continue
        data = obj.read()
        name = str(data.m_Name)
        normalized_name = name if name.endswith(".bytes") else f"{name}.bytes"
        if normalized_name not in wanted:
            continue
        script = data.m_Script
        result[normalized_name] = (
            script
            if isinstance(script, bytes)
            else script.encode("utf-8", "surrogateescape")
        )
        if len(result) == len(wanted):
            break

    missing = wanted.difference(result)
    if missing:
        raise ValueError(f"ConfigPackage text assets missing: {sorted(missing)}")
    return result
