# SPDX-License-Identifier: MIT
"""Network adapter for verifying classic skin image assets."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import hashlib
import logging
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

if __package__:
    from .skin_image_resolution import (
        PET_IMAGE_ASSET_KINDS,
        PetImageAssetCheck,
        is_transient_asset_failure,
    )
else:
    from skin_image_resolution import (  # type: ignore[import-not-found]
        PET_IMAGE_ASSET_KINDS,
        PetImageAssetCheck,
        is_transient_asset_failure,
    )


@dataclass(frozen=True, slots=True)
class SkinImageAssetProbeConfig:
    base_url: str
    timeout_seconds: float
    retry_attempts: int
    retry_backoff_seconds: float
    workers: int


class SkinImageAssetProbe:
    """Validate asset headers and hashes without knowing about release tables."""

    def __init__(
        self,
        config: SkinImageAssetProbeConfig,
        *,
        request: Callable[..., Request],
        logger: logging.Logger,
        open_url: Callable[..., object] = urlopen,
    ) -> None:
        self._config = config
        self._request = request
        self._logger = logger
        self._open_url = open_url

    def asset_url(self, kind: str, resource_id: int) -> str:
        if kind not in PET_IMAGE_ASSET_KINDS:
            raise ValueError(f"unsupported pet image asset kind: {kind}")
        return urljoin(
            self._config.base_url.rstrip("/") + "/",
            f"{kind}/{resource_id}.png",
        )

    def verify_asset(self, kind: str, resource_id: int) -> PetImageAssetCheck:
        url = self.asset_url(kind, resource_id)
        prior_error = ""
        for attempt in range(1, max(1, self._config.retry_attempts) + 1):
            check = self._probe_range(kind, resource_id, url, prior_error=prior_error)
            if not is_transient_asset_failure(check) or attempt >= max(
                1, self._config.retry_attempts
            ):
                return check
            prior_error = check.error
            delay = self._config.retry_backoff_seconds * attempt
            self._logger.warning(
                "Classic skin image probe failed (%s/%s): %s/%s (%s); retrying in %.1fs",
                attempt,
                self._config.retry_attempts,
                kind,
                resource_id,
                check.error or f"HTTP {check.status}",
                delay,
            )
            time.sleep(delay)
        raise AssertionError("unreachable")

    def verify_assets(
        self, asset_keys: set[tuple[str, int]]
    ) -> dict[tuple[str, int], PetImageAssetCheck]:
        if not asset_keys:
            return {}
        self._logger.info(
            "Validating classic skin image assets: %s image resources",
            len(asset_keys),
        )
        checks: dict[tuple[str, int], PetImageAssetCheck] = {}
        with ThreadPoolExecutor(
            max_workers=min(self._config.workers, len(asset_keys))
        ) as executor:
            futures = {
                executor.submit(self.verify_asset, kind, resource_id): (kind, resource_id)
                for kind, resource_id in sorted(asset_keys)
            }
            for future in as_completed(futures):
                kind, resource_id = futures[future]
                try:
                    checks[(kind, resource_id)] = future.result()
                except Exception as error:
                    checks[(kind, resource_id)] = PetImageAssetCheck(
                        kind=kind,
                        resource_id=resource_id,
                        url=self.asset_url(kind, resource_id),
                        available=False,
                        status=0,
                        content_type="",
                        content_length=None,
                        error=_short_error(error),
                    )
        transient_failures = [
            check for check in checks.values() if check.status == 0 or check.status >= 500
        ]
        if transient_failures:
            sample = ", ".join(
                f"{check.kind}/{check.resource_id} ({check.status}: {check.error})"
                for check in transient_failures[:5]
            )
            self._logger.warning(
                "Classic skin image asset verification still has transient failures; "
                "affected image kinds will remain unverified: %s",
                sample,
            )
        return checks

    def download_asset_hash(self, check: PetImageAssetCheck) -> str | None:
        if not check.available:
            return None
        try:
            with self._open_url(
                self._request(check.url, method="GET"),
                timeout=self._config.timeout_seconds,
            ) as response:
                data = response.read()
                if response.status != 200 or not _is_png_asset(
                    response.headers.get_content_type(), data[:16]
                ):
                    return None
        except (HTTPError, URLError, TimeoutError, OSError):
            return None
        return hashlib.sha256(data).hexdigest()

    def _probe_range(
        self,
        kind: str,
        resource_id: int,
        url: str,
        *,
        prior_error: str,
    ) -> PetImageAssetCheck:
        try:
            with self._open_url(
                self._request(url, method="GET", headers={"Range": "bytes=0-15"}),
                timeout=self._config.timeout_seconds,
            ) as response:
                content_type = response.headers.get_content_type()
                content_length = _parse_content_length(response.headers.get("Content-Length"))
                header = response.read(16)
                available = response.status in (200, 206) and _is_png_asset(
                    content_type, header
                )
                return PetImageAssetCheck(
                    kind, resource_id, url, available, response.status, content_type,
                    content_length,
                    "" if available else prior_error or f"unexpected ranged response: {response.status} {content_type}",
                )
        except HTTPError as error:
            return PetImageAssetCheck(
                kind, resource_id, url, False, error.code,
                error.headers.get_content_type(),
                _parse_content_length(error.headers.get("Content-Length")),
                "" if error.code == 404 else _short_error(error),
            )
        except (URLError, TimeoutError, OSError) as error:
            return PetImageAssetCheck(
                kind, resource_id, url, False, 0, "", None,
                prior_error or _short_error(error),
            )


def _is_png_asset(content_type: str, header: bytes = b"") -> bool:
    return content_type.lower().split(";", maxsplit=1)[0] == "image/png" or header.startswith(
        b"\x89PNG\r\n\x1a\n"
    )


def _parse_content_length(value: str | None) -> int | None:
    try:
        return int(value) if value else None
    except ValueError:
        return None


def _short_error(error: Exception | str) -> str:
    return str(error).replace("\n", " ")[:200]
