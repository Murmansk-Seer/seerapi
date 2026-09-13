# SPDX-License-Identifier: MIT
"""Build the published SeerAPI runtime SQLite database.

IronsBot downloads this database as its main data source. The upstream SeerAPI
database is used as build input here; runtime extension fields are merged into
the final SQLite file before it is published.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
import logging
import os
from pathlib import Path
import sqlite3
from urllib.request import urlopen

if __package__:
    from .autocard_sources import load_autocard_data
    from .build_http import BuildHttpClient, BuildHttpConfig
    from .config_package_sources import (
        parse_package_manifest,
    )
    from .effect_icon_build import (
        load_flash_effect_icon_png_assets,
        resolve_effect_icon_png_assets,
    )
    from .effect_icon_build_types import (
        EffectIconBuildConfig,
    )
    from .effect_icon_cache_cli import (
        add_effect_icon_cache_cli_arguments,
        export_effect_icon_png_cache_shard,
        plan_effect_icon_png_cache_shard,
        render_effect_icon_png_cache_shard,
        seed_effect_icon_png_cache_from_database,
        validate_effect_icon_cache_cli_arguments,
        write_effect_icon_cache_shard_plan,
    )
    from .effect_icon_source_paths import (
        effect_icon_asset_url as _effect_icon_asset_url,
    )
    from .effect_icon_unity_sources import (
        unity_effect_icon_swf_fallback_icon_ids,
    )
    from .release_config_tables import (
        SKIN_IMAGE_RESOLUTION_TABLE,
    )
    from .release_metadata import (
        ReleaseMetadataContext,
    )
    from .release_publication import (
        ReleasePublicationContext,
        ReleasePublicationInput,
        publish_release_tables,
    )
    from .release_reference_tables import (
        SPECIAL_EFFECT_STATUS_TABLE,
    )
    from .release_skin_image_loader import build_classic_skin_image_resolutions
    from .release_soulmark_icon_tables import (
        SOULMARK_ICON_TABLE,
    )
    from .release_source_loaders import ReleaseSourceConfig, ReleaseSourceLoader
    from .render_asset_manifest_build import (
        RenderAssetManifestConfig,
    )
    from .render_asset_repository import (
        RenderAssetRepository,
        load_asset_repository_snapshot,
    )
    from .skin_image_asset_probe import (
        SkinImageAssetProbe,
        SkinImageAssetProbeConfig,
    )
else:
    # GitHub Actions invokes this file directly as ``python scripts/...``.
    from autocard_sources import (  # type: ignore[import-not-found]
        load_autocard_data,
    )
    from build_http import (  # type: ignore[import-not-found]
        BuildHttpClient,
        BuildHttpConfig,
    )
    from config_package_sources import (  # type: ignore[import-not-found]
        parse_package_manifest,
    )
    from effect_icon_build import (  # type: ignore[import-not-found]
        load_flash_effect_icon_png_assets,
        resolve_effect_icon_png_assets,
    )
    from effect_icon_build_types import (  # type: ignore[import-not-found]
        EffectIconBuildConfig,
    )
    from effect_icon_cache_cli import (  # type: ignore[import-not-found]
        add_effect_icon_cache_cli_arguments,
        export_effect_icon_png_cache_shard,
        plan_effect_icon_png_cache_shard,
        render_effect_icon_png_cache_shard,
        seed_effect_icon_png_cache_from_database,
        validate_effect_icon_cache_cli_arguments,
        write_effect_icon_cache_shard_plan,
    )
    from effect_icon_source_paths import (  # type: ignore[import-not-found]
        effect_icon_asset_url as _effect_icon_asset_url,
    )
    from effect_icon_unity_sources import (  # type: ignore[import-not-found]
        unity_effect_icon_swf_fallback_icon_ids,
    )
    from release_config_tables import (  # type: ignore[import-not-found]
        SKIN_IMAGE_RESOLUTION_TABLE,
    )
    from release_metadata import (  # type: ignore[import-not-found]
        ReleaseMetadataContext,
    )
    from release_publication import (  # type: ignore[import-not-found]
        ReleasePublicationContext,
        ReleasePublicationInput,
        publish_release_tables,
    )
    from release_reference_tables import (  # type: ignore[import-not-found]
        SPECIAL_EFFECT_STATUS_TABLE,
    )
    from release_skin_image_loader import (  # type: ignore[import-not-found]
        build_classic_skin_image_resolutions,
    )
    from release_soulmark_icon_tables import (  # type: ignore[import-not-found]
        SOULMARK_ICON_TABLE,
    )
    from release_source_loaders import (  # type: ignore[import-not-found]
        ReleaseSourceConfig,
        ReleaseSourceLoader,
    )
    from render_asset_manifest_build import (  # type: ignore[import-not-found]
        RenderAssetManifestConfig,
    )
    from render_asset_repository import (  # type: ignore[import-not-found]
        RenderAssetRepository,
        load_asset_repository_snapshot,
    )
    from skin_image_asset_probe import (  # type: ignore[import-not-found]
        SkinImageAssetProbe,
        SkinImageAssetProbeConfig,
    )


ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DB = ROOT / os.environ.get("SEERAPI_DATA_OUTPUT", "seerapi-data.sqlite")
UPSTREAM_SEERAPI_URL = os.environ.get(
    "IRONSBOT_DATA_UPSTREAM_SEERAPI_URL",
    "https://github.com/Murmansk-Seer/api-data/releases/download/latest/seerapi-data.sqlite",
)
UPSTREAM_SEERAPI_PATH = os.environ.get("IRONSBOT_DATA_UPSTREAM_SEERAPI_PATH", "")
CONFIG_PACKAGE_BASE_URL = os.environ.get(
    "IRONSBOT_DATA_CONFIG_PACKAGE_BASE_URL",
    "https://newseer.61.com/Assets/StandaloneWindows64/ConfigPackage/",
)
PACKAGE_NAME = "ConfigPackage"
CONFIG_BUNDLE_NAME = "pgame_configs_bytes"
DEFAULT_PACKAGE_BASE_URL = os.environ.get(
    "IRONSBOT_DATA_DEFAULT_PACKAGE_BASE_URL",
    "https://newseer.61.com/Assets/StandaloneWindows64/DefaultPackage/",
)
DEFAULT_PACKAGE_NAME = "DefaultPackage"
UNITY_EFFECT_ICON_ASSET_PREFIX = "Assets/Art/Ui/assets/effectIcon/"
UNITY_EFFECT_ICON_ASSET_SUFFIX = ".png"
UNITY_EFFECT_ICON_PNG_ENABLED = os.environ.get(
    "IRONSBOT_DATA_EFFECT_ICON_UNITY_PNG_ENABLED",
    "1",
).lower() not in {"0", "false", "no", "off"}
EFFECT_ICON_PREFER_FLASH = os.environ.get(
    "IRONSBOT_DATA_EFFECT_ICON_PREFER_FLASH",
    "1",
).lower() in {"1", "true", "yes", "on"}
MINTMARK_BYTES_NAME = "mintmark.bytes"
SKIN_STORE_POOL_BYTES_NAME = "skinStorePool.bytes"
SKIN_SHOP_BYTES_NAME = "skin_shop.bytes"
ITEMS_TIP_BYTES_NAME = "itemsTip.bytes"
EFFECT_ICON_BYTES_NAME = "effectIcon.bytes"
AUTOCARD_SEASON_EFFECT_BYTES_NAME = "autocardSeasonEffect.bytes"
EFFECT_ICON_ASSET_BASE_URL = os.environ.get(
    "IRONSBOT_DATA_EFFECT_ICON_ASSET_BASE_URL",
    "https://seer.61.com/resource/effectIcon/",
)
EFFECT_ICON_ASSET_SUFFIX = os.environ.get(
    "IRONSBOT_DATA_EFFECT_ICON_ASSET_SUFFIX",
    ".swf",
)
EFFECT_ICON_ASSET_VERIFY_TIMEOUT_SECONDS = float(
    os.environ.get("IRONSBOT_DATA_EFFECT_ICON_ASSET_VERIFY_TIMEOUT_SECONDS", "15")
)
EFFECT_ICON_ASSET_VERIFY_WORKERS = max(
    1,
    int(os.environ.get("IRONSBOT_DATA_EFFECT_ICON_ASSET_VERIFY_WORKERS", "16")),
)
EFFECT_ICON_PNG_RENDER_ENABLED = os.environ.get(
    "IRONSBOT_DATA_EFFECT_ICON_PNG_RENDER_ENABLED",
    "1",
).lower() not in {"0", "false", "no", "off"}
EFFECT_ICON_PNG_REQUIRE_CACHED = os.environ.get(
    "IRONSBOT_DATA_EFFECT_ICON_PNG_REQUIRE_CACHED",
    "0",
).lower() in {"1", "true", "yes", "on"}
EFFECT_ICON_PNG_RENDER_JAVA_COMMAND = os.environ.get(
    "IRONSBOT_DATA_EFFECT_ICON_PNG_RENDER_JAVA_COMMAND",
    "java",
)
EFFECT_ICON_PNG_RENDER_FFDEC_JAR = Path(
    os.environ.get(
        "IRONSBOT_DATA_EFFECT_ICON_PNG_RENDER_FFDEC_JAR",
        "ffdec.jar",
    )
)
EFFECT_ICON_PNG_RENDER_ZOOM = max(
    1,
    int(os.environ.get("IRONSBOT_DATA_EFFECT_ICON_PNG_RENDER_ZOOM", "6")),
)
EFFECT_ICON_PNG_RENDER_TIMEOUT_SECONDS = float(
    os.environ.get("IRONSBOT_DATA_EFFECT_ICON_PNG_RENDER_TIMEOUT_SECONDS", "60")
)
EFFECT_ICON_PNG_COMPOSITE_RENDER_TIMEOUT_SECONDS = float(
    os.environ.get(
        "IRONSBOT_DATA_EFFECT_ICON_PNG_COMPOSITE_RENDER_TIMEOUT_SECONDS",
        "45",
    )
)
EFFECT_ICON_PNG_SHAPE_RENDER_TIMEOUT_SECONDS = float(
    os.environ.get(
        "IRONSBOT_DATA_EFFECT_ICON_PNG_SHAPE_RENDER_TIMEOUT_SECONDS",
        "30",
    )
)
EFFECT_ICON_PNG_RENDER_WORKERS = max(
    1,
    int(os.environ.get("IRONSBOT_DATA_EFFECT_ICON_PNG_RENDER_WORKERS", "2")),
)
EFFECT_ICON_PNG_CACHE_VERSION = os.environ.get(
    "IRONSBOT_DATA_EFFECT_ICON_PNG_CACHE_VERSION",
    "ffdec-original-timeline-sprite-v1",
)
EFFECT_ICON_PNG_CACHE_DIR = Path(
    os.environ.get(
        "IRONSBOT_DATA_EFFECT_ICON_PNG_CACHE_DIR",
        str(ROOT / ".cache" / "effect-icon-png"),
    )
)
EFFECT_ICON_PNG_MAX_DIMENSION = 1024
EFFECT_ICON_BUILD_CONFIG = EffectIconBuildConfig(
    unity_asset_prefix=UNITY_EFFECT_ICON_ASSET_PREFIX,
    unity_asset_suffix=UNITY_EFFECT_ICON_ASSET_SUFFIX,
    unity_png_enabled=UNITY_EFFECT_ICON_PNG_ENABLED,
    default_package_base_url=DEFAULT_PACKAGE_BASE_URL,
    default_package_name=DEFAULT_PACKAGE_NAME,
    effect_icon_asset_base_url=EFFECT_ICON_ASSET_BASE_URL,
    effect_icon_asset_suffix=EFFECT_ICON_ASSET_SUFFIX,
    asset_verify_timeout_seconds=EFFECT_ICON_ASSET_VERIFY_TIMEOUT_SECONDS,
    asset_verify_workers=EFFECT_ICON_ASSET_VERIFY_WORKERS,
    prefer_flash=EFFECT_ICON_PREFER_FLASH,
    png_render_enabled=EFFECT_ICON_PNG_RENDER_ENABLED,
    png_require_cached=EFFECT_ICON_PNG_REQUIRE_CACHED,
    java_command=EFFECT_ICON_PNG_RENDER_JAVA_COMMAND,
    ffdec_jar=EFFECT_ICON_PNG_RENDER_FFDEC_JAR,
    render_zoom=EFFECT_ICON_PNG_RENDER_ZOOM,
    render_timeout_seconds=EFFECT_ICON_PNG_RENDER_TIMEOUT_SECONDS,
    composite_render_timeout_seconds=(
        EFFECT_ICON_PNG_COMPOSITE_RENDER_TIMEOUT_SECONDS
    ),
    shape_render_timeout_seconds=EFFECT_ICON_PNG_SHAPE_RENDER_TIMEOUT_SECONDS,
    render_workers=EFFECT_ICON_PNG_RENDER_WORKERS,
    cache_version=EFFECT_ICON_PNG_CACHE_VERSION,
    cache_dir=EFFECT_ICON_PNG_CACHE_DIR,
    max_png_dimension=EFFECT_ICON_PNG_MAX_DIMENSION,
)


def _effect_icon_source_config() -> EffectIconBuildConfig:
    """Resolve source flags at call time for CLI and isolated build tests."""

    return replace(
        EFFECT_ICON_BUILD_CONFIG,
        unity_png_enabled=UNITY_EFFECT_ICON_PNG_ENABLED,
        default_package_base_url=DEFAULT_PACKAGE_BASE_URL,
        default_package_name=DEFAULT_PACKAGE_NAME,
        prefer_flash=EFFECT_ICON_PREFER_FLASH,
    )


CONFIG_TEXT_ASSETS = {
    MINTMARK_BYTES_NAME,
    SKIN_STORE_POOL_BYTES_NAME,
    SKIN_SHOP_BYTES_NAME,
    ITEMS_TIP_BYTES_NAME,
    EFFECT_ICON_BYTES_NAME,
    AUTOCARD_SEASON_EFFECT_BYTES_NAME,
}
SEERAPI_SCHEMA_CONTRACT_VERSION = "1"
SEERAPI_SCHEMA_CONTRACT_VERSION_KEY = "ironsbot_schema_contract_version"
RENDER_ASSET_MANIFEST_CONTRACT_VERSION = "3"
RENDER_ASSET_MANIFEST_CONTRACT_VERSION_KEY = "render_asset_manifest_contract_version"
RENDER_ASSET_MANIFEST_REVISION_KEY = "render_asset_manifest_revision"
RENDER_ASSET_MANIFEST_SCOPES_KEY = "render_asset_manifest_complete_scopes"
RENDER_ASSET_MANIFEST_REPOSITORIES_KEY = "render_asset_manifest_repositories"
PET_INFO_RENDER_ASSET_SCOPE = "pet_info"
TYPE_MATCHUP_RENDER_ASSET_SCOPE = "type_matchup"
PEAK_POOL_RENDER_ASSET_SCOPE = "peak_pool"
NEW_CONTENT_STANDARD_RENDER_ASSET_SCOPE = "new_content_standard"
RENDER_ASSET_REPOSITORY = "Murmansk-Seer/seer-unity-assets"
RENDER_ASSET_REPOSITORY_GIT_URL = os.environ.get(
    "IRONSBOT_DATA_RENDER_ASSET_REPOSITORY_GIT_URL",
    f"https://github.com/{RENDER_ASSET_REPOSITORY}.git",
)
RENDER_ASSET_REPOSITORY_REF = os.environ.get(
    "IRONSBOT_DATA_RENDER_ASSET_REPOSITORY_REF",
    "main",
)
RENDER_ASSET_REPOSITORY_COMMIT_URL = os.environ.get(
    "IRONSBOT_DATA_RENDER_ASSET_REPOSITORY_COMMIT_URL",
    "https://api.github.com/repos/"
    f"{RENDER_ASSET_REPOSITORY}/commits/{RENDER_ASSET_REPOSITORY_REF}",
)
RENDER_ASSET_REPOSITORY_TREE_URL_TEMPLATE = os.environ.get(
    "IRONSBOT_DATA_RENDER_ASSET_REPOSITORY_TREE_URL_TEMPLATE",
    "https://api.github.com/repos/"
    f"{RENDER_ASSET_REPOSITORY}/git/trees/{{revision}}?recursive=1",
)
RENDER_ASSET_REPOSITORY_CONFIG = RenderAssetRepository(
    name=RENDER_ASSET_REPOSITORY,
    git_url=RENDER_ASSET_REPOSITORY_GIT_URL,
    ref=RENDER_ASSET_REPOSITORY_REF,
    commit_url=RENDER_ASSET_REPOSITORY_COMMIT_URL,
    tree_url_template=RENDER_ASSET_REPOSITORY_TREE_URL_TEMPLATE,
)
RENDER_ASSET_MANIFEST_CONFIG = RenderAssetManifestConfig(
    manifest_contract_version=RENDER_ASSET_MANIFEST_CONTRACT_VERSION,
    manifest_contract_version_key=RENDER_ASSET_MANIFEST_CONTRACT_VERSION_KEY,
    manifest_revision_key=RENDER_ASSET_MANIFEST_REVISION_KEY,
    manifest_scopes_key=RENDER_ASSET_MANIFEST_SCOPES_KEY,
    manifest_repositories_key=RENDER_ASSET_MANIFEST_REPOSITORIES_KEY,
    pet_info_scope=PET_INFO_RENDER_ASSET_SCOPE,
    type_matchup_scope=TYPE_MATCHUP_RENDER_ASSET_SCOPE,
    peak_pool_scope=PEAK_POOL_RENDER_ASSET_SCOPE,
    new_content_standard_scope=NEW_CONTENT_STANDARD_RENDER_ASSET_SCOPE,
    skin_body_scope="skin_body",
    special_effect_status_table=SPECIAL_EFFECT_STATUS_TABLE,
    skin_image_resolution_table=SKIN_IMAGE_RESOLUTION_TABLE,
)
AUTOCARD_JSON_DIR = os.environ.get("IRONSBOT_DATA_AUTOCARD_JSON_DIR", "")
AUTOCARD_JSON_BASE_URL = os.environ.get(
    "IRONSBOT_DATA_AUTOCARD_JSON_BASE_URL",
    "https://raw.githubusercontent.com/Murmansk-Seer/seer-unity-config-parser/main/json/",
)
AUTOCARD_CONTENT_FILE = "autocardContent.json"
AUTOCARD_NATURE_FILE = "autocardNature.json"
AUTOCARD_ROLE_FILE = "autocardRole.json"
AUTOCARD_BUFF_FILE = "autocardBuff.json"
WEEKLY_PREVIEW_IMAGE_URL = (
    "https://raw.githubusercontent.com/Murmansk-Seer/"
    "seer-unity-preview-img-dumper/main/img/preview.png"
)
WEEKLY_PREVIEW_SOURCE_URL = (
    "https://github.com/Murmansk-Seer/seer-unity-preview-img-dumper"
)
BATTLEPASS_SHOP_URL = os.environ.get(
    "IRONSBOT_DATA_BATTLEPASS_SHOP_URL",
    "https://raw.githubusercontent.com/Murmansk-Seer/"
    "config-sources/main/unity/battlepassShop.json",
)
ACTIVITY_SHOP_URL = os.environ.get(
    "IRONSBOT_DATA_ACTIVITY_SHOP_URL",
    "https://raw.githubusercontent.com/Murmansk-Seer/"
    "config-sources/main/unity/Activity_ShopConfig.json",
)
SPECIAL_SKILL_SHOP_URL = os.environ.get(
    "IRONSBOT_DATA_SPECIAL_SKILL_SHOP_URL",
    "https://raw.githubusercontent.com/Murmansk-Seer/"
    "config-sources/main/unity/spHideMovesShop.json",
)
UNITY_ITEM_CATALOG_URL = os.environ.get(
    "IRONSBOT_DATA_UNITY_ITEM_CATALOG_URL",
    "https://raw.githubusercontent.com/Murmansk-Seer/"
    "config-sources/main/unity/itemsOptimizeCatItems17.json",
)
EFFECT_DESCRIPTION_URL = os.environ.get(
    "IRONSBOT_DATA_EFFECT_DESCRIPTION_URL",
    "https://raw.githubusercontent.com/Murmansk-Seer/"
    "config-sources/main/unity/effectDes.json",
)
SPECIAL_EFFECT_STATUS_URL = os.environ.get(
    "IRONSBOT_DATA_SPECIAL_EFFECT_STATUS_URL",
    "https://raw.githubusercontent.com/Murmansk-Seer/"
    "config-sources/main/unity/signIconFight.json",
)
PARTNER_CONTRACTS_URL = os.environ.get(
    "IRONSBOT_DATA_PARTNER_CONTRACTS_URL",
    "https://raw.githubusercontent.com/Murmansk-Seer/"
    "config-sources/main/unity/partner_contracts.json",
)
PARTNER_CONTRACTS_SCHEMA_VERSION = 1
# ``partner_contracts.json`` v1 was generated with its two upgrade description
# keys reversed: ``before_description`` contains the strengthened text and
# ``after_description`` contains the original text. Normalize the source at the
# publishing boundary so every consumer of ``seerapi-data.sqlite`` sees the
# documented before/after meaning.
PARTNER_CONTRACTS_V1_DESCRIPTIONS_REVERSED = True
# ``partner.bytes`` uses two unrelated group types. Only type 2 is the
# contract/bond system paid with Contract Badges; type 1 is the elemental king
# inheritance system and has a different, currently unmodelled, currency.
PARTNER_CONTRACT_GROUP_TYPE = "2"
CONTRACT_BADGE_ITEM_ID = 1722827
CONTRACT_BADGE_ITEM_NAME = "契约徽章"
BATTLEPASS_SHOP_SOURCE_KEY = "battlepass_shop"
BATTLEPASS_SHOP_SOURCE_NAME = "战令商店"
ACTIVITY_SHOP_SOURCE_KEY = "activity_shop"
ACTIVITY_SHOP_SOURCE_NAME = "活动商店"
SPECIAL_SKILL_SHOP_SOURCE_KEY = "special_skill_shop"
SPECIAL_SKILL_SHOP_SOURCE_NAME = "微光秘境"
HTTP_TIMEOUT_SECONDS = 180
HTTP_RETRY_ATTEMPTS = int(os.environ.get("IRONSBOT_DATA_HTTP_RETRY_ATTEMPTS", "3"))
HTTP_RETRY_BACKOFF_SECONDS = float(
    os.environ.get("IRONSBOT_DATA_HTTP_RETRY_BACKOFF_SECONDS", "2")
)
PET_IMAGE_ASSET_BASE_URL = os.environ.get(
    "IRONSBOT_DATA_PET_IMAGE_ASSET_BASE_URL",
    "https://newseer.61.com/web/monster/",
)
PET_IMAGE_ASSET_VERIFY_TIMEOUT_SECONDS = float(
    os.environ.get("IRONSBOT_DATA_PET_IMAGE_ASSET_VERIFY_TIMEOUT_SECONDS", "15")
)
PET_IMAGE_ASSET_VERIFY_WORKERS = max(
    1,
    int(os.environ.get("IRONSBOT_DATA_PET_IMAGE_ASSET_VERIFY_WORKERS", "8")),
)
CLASSIC_SKIN_CATEGORY_ID = 0
logger = logging.getLogger(__name__)
BUILD_HTTP = BuildHttpClient(
    BuildHttpConfig(
        timeout_seconds=HTTP_TIMEOUT_SECONDS,
        retry_attempts=HTTP_RETRY_ATTEMPTS,
        retry_backoff_seconds=HTTP_RETRY_BACKOFF_SECONDS,
    ),
    logger=logger,
)
SKIN_IMAGE_ASSET_PROBE = SkinImageAssetProbe(
    SkinImageAssetProbeConfig(
        base_url=PET_IMAGE_ASSET_BASE_URL,
        timeout_seconds=PET_IMAGE_ASSET_VERIFY_TIMEOUT_SECONDS,
        retry_attempts=HTTP_RETRY_ATTEMPTS,
        retry_backoff_seconds=HTTP_RETRY_BACKOFF_SECONDS,
        workers=PET_IMAGE_ASSET_VERIFY_WORKERS,
    ),
    request=BUILD_HTTP.request,
    logger=logger,
)


def _release_source_loader() -> ReleaseSourceLoader:
    return ReleaseSourceLoader(
        BUILD_HTTP,
        ReleaseSourceConfig(
            config_package_base_url=CONFIG_PACKAGE_BASE_URL,
            config_package_name=PACKAGE_NAME,
            config_bundle_name=CONFIG_BUNDLE_NAME,
            config_text_assets=CONFIG_TEXT_ASSETS,
            mintmark_bytes_name=MINTMARK_BYTES_NAME,
            skin_store_pool_bytes_name=SKIN_STORE_POOL_BYTES_NAME,
            skin_shop_bytes_name=SKIN_SHOP_BYTES_NAME,
            items_tip_bytes_name=ITEMS_TIP_BYTES_NAME,
            effect_icon_bytes_name=EFFECT_ICON_BYTES_NAME,
            autocard_season_effect_bytes_name=AUTOCARD_SEASON_EFFECT_BYTES_NAME,
            autocard_json_dir=AUTOCARD_JSON_DIR,
            autocard_json_base_url=AUTOCARD_JSON_BASE_URL,
            unity_item_catalog_url=UNITY_ITEM_CATALOG_URL,
            battlepass_shop_url=BATTLEPASS_SHOP_URL,
            battlepass_shop_source_key=BATTLEPASS_SHOP_SOURCE_KEY,
            battlepass_shop_source_name=BATTLEPASS_SHOP_SOURCE_NAME,
            activity_shop_url=ACTIVITY_SHOP_URL,
            activity_shop_source_key=ACTIVITY_SHOP_SOURCE_KEY,
            activity_shop_source_name=ACTIVITY_SHOP_SOURCE_NAME,
            special_skill_shop_url=SPECIAL_SKILL_SHOP_URL,
            special_skill_shop_source_key=SPECIAL_SKILL_SHOP_SOURCE_KEY,
            special_skill_shop_source_name=SPECIAL_SKILL_SHOP_SOURCE_NAME,
            effect_description_url=EFFECT_DESCRIPTION_URL,
            special_effect_status_url=SPECIAL_EFFECT_STATUS_URL,
            partner_contracts_url=PARTNER_CONTRACTS_URL,
            partner_contracts_schema_version=PARTNER_CONTRACTS_SCHEMA_VERSION,
            partner_contract_group_type=PARTNER_CONTRACT_GROUP_TYPE,
            contract_badge_item_id=CONTRACT_BADGE_ITEM_ID,
            contract_badge_item_name=CONTRACT_BADGE_ITEM_NAME,
            partner_contracts_descriptions_reversed=(
                PARTNER_CONTRACTS_V1_DESCRIPTIONS_REVERSED
            ),
        ),
        logger=logger,
    )


def _quick_check(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        result = conn.execute("PRAGMA quick_check").fetchone()
    if not result or result[0] != "ok":
        raise sqlite3.DatabaseError(
            f"SQLite quick_check failed: {result}"
        )


def _release_publication_context() -> ReleasePublicationContext:
    return ReleasePublicationContext(
        load_asset_repository_snapshots=lambda: {
            "default": snapshot
            for snapshot in (
                load_asset_repository_snapshot(
                    RENDER_ASSET_REPOSITORY_CONFIG,
                    BUILD_HTTP.download_bytes,
                    logger=logger,
                ),
            )
            if snapshot is not None
        },
        resolve_effect_icons=lambda icon_ids: resolve_effect_icon_png_assets(
            icon_ids,
            config=_effect_icon_source_config(),
            fetch_package_manifest=lambda base_url, package_name: BUILD_HTTP.fetch_package_manifest(
                base_url,
                package_name,
                parse_manifest=parse_package_manifest,
            ),
            download_bytes=BUILD_HTTP.download_bytes,
            request=BUILD_HTTP.request,
            open_url=urlopen,
            logger=logger,
        ),
        render_asset_manifest_config=RENDER_ASSET_MANIFEST_CONFIG,
        effect_icon_cache_version=EFFECT_ICON_PNG_CACHE_VERSION,
        metadata_context=ReleaseMetadataContext(
            schema_contract_version_key=SEERAPI_SCHEMA_CONTRACT_VERSION_KEY,
            schema_contract_version=SEERAPI_SCHEMA_CONTRACT_VERSION,
            upstream_seerapi_url=UPSTREAM_SEERAPI_URL,
            config_package_base_url=CONFIG_PACKAGE_BASE_URL,
            effect_icon_asset_base_url=EFFECT_ICON_ASSET_BASE_URL,
            effect_icon_asset_suffix=EFFECT_ICON_ASSET_SUFFIX,
            effect_icon_prefer_flash=EFFECT_ICON_PREFER_FLASH,
            effect_icon_unity_png_enabled=UNITY_EFFECT_ICON_PNG_ENABLED,
            default_package_base_url=DEFAULT_PACKAGE_BASE_URL,
            effect_icon_png_render_enabled=EFFECT_ICON_PNG_RENDER_ENABLED,
            effect_icon_png_java_command=EFFECT_ICON_PNG_RENDER_JAVA_COMMAND,
            effect_icon_png_ffdec_jar=str(EFFECT_ICON_PNG_RENDER_FFDEC_JAR),
            effect_icon_png_cache_version=EFFECT_ICON_PNG_CACHE_VERSION,
            effect_icon_png_render_zoom=EFFECT_ICON_PNG_RENDER_ZOOM,
            item_exchange_source_urls=(
                BATTLEPASS_SHOP_URL,
                ACTIVITY_SHOP_URL,
                SPECIAL_SKILL_SHOP_URL,
                UNITY_ITEM_CATALOG_URL,
            ),
            effect_description_url=EFFECT_DESCRIPTION_URL,
            special_effect_status_url=SPECIAL_EFFECT_STATUS_URL,
            partner_contracts_url=PARTNER_CONTRACTS_URL,
            weekly_preview_image_url=WEEKLY_PREVIEW_IMAGE_URL,
            weekly_preview_source_url=WEEKLY_PREVIEW_SOURCE_URL,
        ),
        logger=logger,
    )


def _parse_cli_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    add_effect_icon_cache_cli_arguments(parser)
    arguments = parser.parse_args()
    validate_effect_icon_cache_cli_arguments(parser, arguments)
    return arguments


def _release_effect_icon_ids() -> set[int]:
    return {
        item.icon_id
        for item in _release_source_loader().fetch_config_package_data().soulmark_icons
    }


def _swf_fallback_effect_icon_ids(icon_ids: set[int]) -> tuple[int, ...]:
    return unity_effect_icon_swf_fallback_icon_ids(
        icon_ids,
        config=_effect_icon_source_config(),
        fetch_package_manifest=lambda base_url, package_name: BUILD_HTTP.fetch_package_manifest(
            base_url,
            package_name,
            parse_manifest=parse_package_manifest,
        ),
        logger=logger,
    )


def _export_effect_icon_cache(icon_ids: list[int] | tuple[int, ...], output_dir: Path) -> int:
    return export_effect_icon_png_cache_shard(
        icon_ids,
        output_dir,
        cache_version=EFFECT_ICON_PNG_CACHE_VERSION,
        config=EFFECT_ICON_BUILD_CONFIG,
        logger=logger,
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    arguments = _parse_cli_args()
    if arguments.seed_effect_icon_cache is not None:
        seed_effect_icon_png_cache_from_database(
            arguments.seed_effect_icon_cache,
            cache_version=EFFECT_ICON_PNG_CACHE_VERSION,
            icon_table=SOULMARK_ICON_TABLE,
            config=EFFECT_ICON_BUILD_CONFIG,
            effect_icon_url=lambda icon_id: _effect_icon_asset_url(
                icon_id,
                config=EFFECT_ICON_BUILD_CONFIG,
            ),
            logger=logger,
        )
        return
    if arguments.plan_effect_icon_shard is not None:
        inspect_config = replace(
            EFFECT_ICON_BUILD_CONFIG,
            png_render_enabled=False,
            png_require_cached=False,
        )
        plan = plan_effect_icon_png_cache_shard(
            shard_index=arguments.plan_effect_icon_shard,
            shard_count=arguments.effect_icon_shard_count,
            output_dir=arguments.export_effect_icon_cache_shard,
            fetch_icon_ids=_release_effect_icon_ids,
            find_fallback_icon_ids=_swf_fallback_effect_icon_ids,
            inspect_icons=lambda icon_ids: load_flash_effect_icon_png_assets(
                icon_ids,
                config=inspect_config,
                request=BUILD_HTTP.request,
                open_url=urlopen,
                logger=logger,
                require_any=False,
            ),
            export_cache=_export_effect_icon_cache,
            logger=logger,
        )
        write_effect_icon_cache_shard_plan(
            plan,
            arguments.effect_icon_shard_plan_output,
        )
        return
    if arguments.render_effect_icon_shard is not None:
        icon_count, available_count = render_effect_icon_png_cache_shard(
            shard_index=arguments.render_effect_icon_shard,
            shard_count=arguments.effect_icon_shard_count,
            output_dir=arguments.export_effect_icon_cache_shard,
            repair_icon_ids=arguments.effect_icon_repair_ids,
            fetch_icon_ids=_release_effect_icon_ids,
            find_fallback_icon_ids=_swf_fallback_effect_icon_ids,
            render_icons=lambda icon_ids: load_flash_effect_icon_png_assets(
                icon_ids,
                config=EFFECT_ICON_BUILD_CONFIG,
                request=BUILD_HTTP.request,
                open_url=urlopen,
                logger=logger,
                require_any=False,
            )[1],
            export_cache=_export_effect_icon_cache,
            logger=logger,
        )
        logger.info(
            "Rendered effect icon cache shard: %s icons, %s available",
            icon_count,
            available_count,
        )
        return
    OUTPUT_DB.parent.mkdir(parents=True, exist_ok=True)
    if UPSTREAM_SEERAPI_PATH:
        logger.info(
            "Using verified upstream SeerAPI database: %s",
            UPSTREAM_SEERAPI_PATH,
        )
    else:
        logger.info("Downloading upstream SeerAPI database: %s", UPSTREAM_SEERAPI_URL)
    BUILD_HTTP.copy_or_download_upstream_database(
        OUTPUT_DB,
        upstream_path=UPSTREAM_SEERAPI_PATH,
        upstream_url=UPSTREAM_SEERAPI_URL,
    )
    _quick_check(OUTPUT_DB)

    sources = _release_source_loader()
    logger.info("Loading official ConfigPackage: %s", CONFIG_PACKAGE_BASE_URL)
    config_data = sources.fetch_config_package_data()
    if not config_data.mintmark_quality:
        raise ValueError("mintmark Quality map is empty")
    logger.info(
        "Loading autocard JSON data: %s",
        AUTOCARD_JSON_DIR or AUTOCARD_JSON_BASE_URL,
    )
    autocard_data = load_autocard_data(
        sources.load_autocard_json,
        content_file=AUTOCARD_CONTENT_FILE,
        nature_file=AUTOCARD_NATURE_FILE,
        role_file=AUTOCARD_ROLE_FILE,
        buff_file=AUTOCARD_BUFF_FILE,
    )
    logger.info("Loading official item exchange prices")
    item_exchange_prices = sources.load_item_exchange_prices()
    logger.info("Loading official named effect descriptions")
    effect_descriptions = sources.load_effect_descriptions()
    logger.info("Loading official special effect statuses")
    special_effect_statuses = sources.load_special_effect_statuses()
    logger.info("Loading official contract-partner data")
    pet_partner_data = sources.load_pet_partner_data()
    logger.info("Resolving classic skin image resources")
    skin_image_resolutions = build_classic_skin_image_resolutions(
        OUTPUT_DB,
        classic_skin_category_id=CLASSIC_SKIN_CATEGORY_ID,
        asset_probe=SKIN_IMAGE_ASSET_PROBE,
        logger=logger,
    )
    logger.info("Probing weekly preview image: %s", WEEKLY_PREVIEW_IMAGE_URL)
    weekly_preview_probe = BUILD_HTTP.probe_image(WEEKLY_PREVIEW_IMAGE_URL)

    publish_release_tables(
        OUTPUT_DB,
        release=ReleasePublicationInput(
            config_data=config_data,
            autocard_data=autocard_data,
            item_exchange_prices=item_exchange_prices,
            effect_descriptions=effect_descriptions,
            special_effect_statuses=special_effect_statuses,
            pet_partner_data=pet_partner_data,
            weekly_preview_probe=weekly_preview_probe,
            skin_image_resolutions=skin_image_resolutions,
        ),
        context=_release_publication_context(),
    )
    _quick_check(OUTPUT_DB)
    size_mb = OUTPUT_DB.stat().st_size / 1024 / 1024
    logger.info(
        (
            "Built %s (%.2f MB), mintmark_quality rows: %s, "
            "skin shop rows: %s, exchange price rows: %s, effect descriptions: %s, "
            "special effect statuses: %s, "
            "soulmark icons: %s, classic skin image rows: %s, "
            "contract partners: %s, autocard cards: %s"
        ),
        OUTPUT_DB,
        size_mb,
        len(config_data.mintmark_quality),
        len(config_data.skin_shop_prices),
        len(item_exchange_prices),
        len(effect_descriptions),
        len(special_effect_statuses),
        len(config_data.soulmark_icons),
        len(skin_image_resolutions),
        len(pet_partner_data.groups),
        len(autocard_data.cards),
    )


if __name__ == "__main__":
    main()
