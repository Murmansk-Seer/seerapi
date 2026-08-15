# SPDX-License-Identifier: MIT
"""Flash HTTP adapter for build-time effect icon source verification."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
from urllib.error import HTTPError, URLError
from urllib.request import Request

if __package__:
    from .effect_icon_build_types import EffectIconAssetCheck, EffectIconBuildConfig
    from .effect_icon_source_paths import effect_icon_asset_url
else:
    from effect_icon_build_types import (  # type: ignore[import-not-found]
        EffectIconAssetCheck,
        EffectIconBuildConfig,
    )
    from effect_icon_source_paths import (  # type: ignore[import-not-found]
        effect_icon_asset_url,
    )


BuildRequest = Callable[..., Request]
OpenUrl = Callable[..., object]


def _parse_content_length(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _short_error(error: Exception | str) -> str:
    return str(error).replace("\n", " ")[:200]


def is_effect_icon_asset_content(content_type: str, header: bytes = b"") -> bool:
    normalized = content_type.lower().split(";", maxsplit=1)[0]
    return normalized in {
        "application/x-shockwave-flash",
        "application/vnd.adobe.flash.movie",
    } or header.startswith((b"CWS", b"FWS", b"ZWS"))


def _probe_effect_icon_asset_range(
    icon_id: int,
    url: str,
    *,
    config: EffectIconBuildConfig,
    request: BuildRequest,
    open_url: OpenUrl,
    prior_error: str = "",
) -> EffectIconAssetCheck:
    try:
        range_request = request(url, method="GET", headers={"Range": "bytes=0-15"})
        with open_url(
            range_request, timeout=config.asset_verify_timeout_seconds
        ) as response:
            content_type = response.headers.get_content_type()
            content_length = _parse_content_length(response.headers.get("Content-Length"))
            header = response.read(16)
            available = response.status in (200, 206) and is_effect_icon_asset_content(
                content_type, header
            )
            error = "" if available else prior_error or (
                f"unexpected ranged response: {response.status} {content_type}"
            )
            return EffectIconAssetCheck(
                icon_id=icon_id,
                url=url,
                available=available,
                status=response.status,
                content_type=content_type,
                content_length=content_length,
                error=error,
            )
    except HTTPError as error:
        return EffectIconAssetCheck(
            icon_id=icon_id,
            url=url,
            available=False,
            status=error.code,
            content_type=error.headers.get_content_type(),
            content_length=_parse_content_length(error.headers.get("Content-Length")),
            error="" if error.code == 404 else _short_error(error),
        )
    except (URLError, TimeoutError, OSError) as error:
        return EffectIconAssetCheck(
            icon_id=icon_id,
            url=url,
            available=False,
            status=0,
            content_type="",
            content_length=None,
            error=prior_error or _short_error(error),
        )


def verify_effect_icon_asset(
    icon_id: int,
    *,
    config: EffectIconBuildConfig,
    request: BuildRequest,
    open_url: OpenUrl,
) -> EffectIconAssetCheck:
    url = effect_icon_asset_url(icon_id, config=config)
    try:
        with open_url(
            request(url, method="HEAD"), timeout=config.asset_verify_timeout_seconds
        ) as response:
            content_type = response.headers.get_content_type()
            content_length = _parse_content_length(response.headers.get("Content-Length"))
            available = (
                response.status == 200
                and (content_length is None or content_length > 0)
                and is_effect_icon_asset_content(content_type)
            )
            if available:
                return EffectIconAssetCheck(
                    icon_id=icon_id,
                    url=url,
                    available=True,
                    status=response.status,
                    content_type=content_type,
                    content_length=content_length,
                    error="",
                )
            return _probe_effect_icon_asset_range(
                icon_id,
                url,
                config=config,
                request=request,
                open_url=open_url,
                prior_error=f"unexpected HEAD response: {response.status} {content_type}",
            )
    except HTTPError as error:
        if error.code in {403, 405, 501}:
            return _probe_effect_icon_asset_range(
                icon_id,
                url,
                config=config,
                request=request,
                open_url=open_url,
                prior_error=_short_error(error),
            )
        return EffectIconAssetCheck(
            icon_id=icon_id,
            url=url,
            available=False,
            status=error.code,
            content_type=error.headers.get_content_type(),
            content_length=_parse_content_length(error.headers.get("Content-Length")),
            error="" if error.code == 404 else _short_error(error),
        )
    except (URLError, TimeoutError, OSError) as error:
        return _probe_effect_icon_asset_range(
            icon_id,
            url,
            config=config,
            request=request,
            open_url=open_url,
            prior_error=_short_error(error),
        )


def verify_effect_icon_assets(
    icon_ids: set[int],
    *,
    config: EffectIconBuildConfig,
    request: BuildRequest,
    open_url: OpenUrl,
    logger: logging.Logger,
    require_any: bool = True,
) -> dict[int, EffectIconAssetCheck]:
    if not icon_ids:
        return {}
    logger.info("Validating official effect icon assets: %s unique icons", len(icon_ids))
    checks: dict[int, EffectIconAssetCheck] = {}
    worker_count = min(config.asset_verify_workers, len(icon_ids))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {
            executor.submit(
                verify_effect_icon_asset,
                icon_id,
                config=config,
                request=request,
                open_url=open_url,
            ): icon_id
            for icon_id in sorted(icon_ids)
        }
        for future in as_completed(futures):
            icon_id = futures[future]
            try:
                checks[icon_id] = future.result()
            except Exception as error:
                checks[icon_id] = EffectIconAssetCheck(
                    icon_id=icon_id,
                    url=effect_icon_asset_url(icon_id, config=config),
                    available=False,
                    status=0,
                    content_type="",
                    content_length=None,
                    error=_short_error(error),
                )
    available_count = sum(check.available for check in checks.values())
    missing_checks = [check for check in checks.values() if not check.available]
    if available_count == 0 and require_any:
        raise ValueError("No official effect icon assets could be verified")
    if missing_checks:
        logger.warning(
            "Effect icon asset validation missing %s/%s icons; first missing: %s",
            len(missing_checks),
            len(checks),
            ", ".join(str(check.icon_id) for check in missing_checks[:10]),
        )
    return checks


def download_effect_icon_asset(
    check: EffectIconAssetCheck,
    *,
    config: EffectIconBuildConfig,
    request: BuildRequest,
    open_url: OpenUrl,
) -> bytes:
    with open_url(
        request(check.url, method="GET"), timeout=config.asset_verify_timeout_seconds
    ) as response:
        content_type = response.headers.get_content_type()
        data = response.read()
        if response.status != 200 or not is_effect_icon_asset_content(
            content_type, data[:16]
        ):
            raise ValueError(f"unexpected SWF response: {response.status} {content_type}")
        return data
