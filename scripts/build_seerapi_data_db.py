# SPDX-License-Identifier: MIT
"""Build the published SeerAPI runtime SQLite database.

IronsBot downloads this database as its main data source. The upstream SeerAPI
database is used as build input here; runtime extension fields are merged into
the final SQLite file before it is published.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from functools import partial
import json
import logging
import os
from pathlib import Path
import shutil
import sqlite3
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import urlopen

if __package__:
    from .autocard_sources import AutocardData, load_autocard_data
    from .build_http import BuildHttpClient, BuildHttpConfig, extract_text_assets
    from .config_package_sources import (
        AutocardSeasonEffect,
        SkinShopPrice,
        SkinStorePrice,
        SoulmarkIcon,
        parse_autocard_season_effects,
        parse_effect_icons,
        parse_items_tip,
        parse_mintmark_quality,
        parse_package_manifest,
        parse_skin_shop,
        parse_skin_store_pool,
    )
    from .effect_icon_build import (
        load_flash_effect_icon_png_assets,
        resolve_effect_icon_png_assets,
    )
    from .effect_icon_build_types import (
        EffectIconAssetCheck,
        EffectIconBuildConfig,
        EffectIconPngRender,
        SoulmarkIconRenderIssue,
    )
    from .effect_icon_png_renderer import (
        effect_icon_png_cache_metadata_path,
        effect_icon_png_cache_path,
        save_effect_icon_png_cache,
    )
    from .effect_icon_source_paths import (
        effect_icon_asset_url as _effect_icon_asset_url,
    )
    from .effect_icon_unity_sources import (
        unity_effect_icon_swf_fallback_icon_ids,
    )
    from .effect_metadata_sources import (
        EffectDescription,
        SpecialEffectStatus,
        parse_effect_descriptions,
        parse_special_effect_statuses,
    )
    from .item_exchange_sources import (
        ItemExchangePrice,
        parse_commodity_shop,
        parse_special_skill_shop,
    )
    from .json_value_helpers import item_int, item_text
    from .partner_contract_sources import (
        PetPartnerData,
        parse_pet_partner_data,
    )
    from .release_autocard_tables import (
        replace_autocard_season_effect_table,
        replace_autocard_tables,
    )
    from .release_config_tables import (
        SKIN_IMAGE_RESOLUTION_TABLE,
        replace_config_package_tables,
    )
    from .release_partner_tables import replace_pet_partner_tables
    from .release_reference_tables import (
        SPECIAL_EFFECT_STATUS_TABLE,
        replace_reference_tables,
    )
    from .release_render_manifest_tables import (
        replace_render_asset_manifest_table,
    )
    from .release_soulmark_icon_tables import (
        SOULMARK_ICON_TABLE,
        replace_soulmark_icon_tables,
    )
    from .render_asset_manifest_build import (
        RenderAssetManifestConfig,
        build_render_asset_manifest,
        collect_remote_asset_manifest,
    )
    from .render_asset_repository import (
        RenderAssetRepository,
        load_asset_repository_snapshot,
    )
    from .skin_image_asset_probe import (
        SkinImageAssetProbe,
        SkinImageAssetProbeConfig,
    )
    from .skin_image_resolution import (
        PET_IMAGE_ASSET_KINDS,
        ClassicSkinImageSource,
        PetImageSource,
        SkinImageResolution,
        content_hash_keys_for_classic_skin_fallbacks,
        resolve_classic_skin_image_resources,
        source_asset_keys_for_classic_skin_fallbacks,
    )
else:
    # GitHub Actions invokes this file directly as ``python scripts/...``.
    from autocard_sources import (  # type: ignore[import-not-found]
        AutocardData,
        load_autocard_data,
    )
    from build_http import (  # type: ignore[import-not-found]
        BuildHttpClient,
        BuildHttpConfig,
        extract_text_assets,
    )
    from config_package_sources import (  # type: ignore[import-not-found]
        AutocardSeasonEffect,
        SkinShopPrice,
        SkinStorePrice,
        SoulmarkIcon,
        parse_autocard_season_effects,
        parse_effect_icons,
        parse_items_tip,
        parse_mintmark_quality,
        parse_package_manifest,
        parse_skin_shop,
        parse_skin_store_pool,
    )
    from effect_icon_build import (  # type: ignore[import-not-found]
        load_flash_effect_icon_png_assets,
        resolve_effect_icon_png_assets,
    )
    from effect_icon_build_types import (  # type: ignore[import-not-found]
        EffectIconAssetCheck,
        EffectIconBuildConfig,
        EffectIconPngRender,
        SoulmarkIconRenderIssue,
    )
    from effect_icon_png_renderer import (  # type: ignore[import-not-found]
        effect_icon_png_cache_metadata_path,
        effect_icon_png_cache_path,
        save_effect_icon_png_cache,
    )
    from effect_icon_source_paths import (  # type: ignore[import-not-found]
        effect_icon_asset_url as _effect_icon_asset_url,
    )
    from effect_icon_unity_sources import (  # type: ignore[import-not-found]
        unity_effect_icon_swf_fallback_icon_ids,
    )
    from effect_metadata_sources import (  # type: ignore[import-not-found]
        EffectDescription,
        SpecialEffectStatus,
        parse_effect_descriptions,
        parse_special_effect_statuses,
    )
    from item_exchange_sources import (  # type: ignore[import-not-found]
        ItemExchangePrice,
        parse_commodity_shop,
        parse_special_skill_shop,
    )
    from json_value_helpers import item_int, item_text  # type: ignore[import-not-found]
    from partner_contract_sources import (  # type: ignore[import-not-found]
        PetPartnerData,
        parse_pet_partner_data,
    )
    from release_autocard_tables import (  # type: ignore[import-not-found]
        replace_autocard_season_effect_table,
        replace_autocard_tables,
    )
    from release_config_tables import (  # type: ignore[import-not-found]
        SKIN_IMAGE_RESOLUTION_TABLE,
        replace_config_package_tables,
    )
    from release_partner_tables import (  # type: ignore[import-not-found]
        replace_pet_partner_tables,
    )
    from release_reference_tables import (  # type: ignore[import-not-found]
        SPECIAL_EFFECT_STATUS_TABLE,
        replace_reference_tables,
    )
    from release_render_manifest_tables import (  # type: ignore[import-not-found]
        replace_render_asset_manifest_table,
    )
    from release_soulmark_icon_tables import (  # type: ignore[import-not-found]
        SOULMARK_ICON_TABLE,
        replace_soulmark_icon_tables,
    )
    from render_asset_manifest_build import (  # type: ignore[import-not-found]
        RenderAssetManifestConfig,
        build_render_asset_manifest,
        collect_remote_asset_manifest,
    )
    from render_asset_repository import (  # type: ignore[import-not-found]
        RenderAssetRepository,
        load_asset_repository_snapshot,
    )
    from skin_image_asset_probe import (  # type: ignore[import-not-found]
        SkinImageAssetProbe,
        SkinImageAssetProbeConfig,
    )
    from skin_image_resolution import (  # type: ignore[import-not-found]
        PET_IMAGE_ASSET_KINDS,
        ClassicSkinImageSource,
        PetImageSource,
        SkinImageResolution,
        content_hash_keys_for_classic_skin_fallbacks,
        resolve_classic_skin_image_resources,
        source_asset_keys_for_classic_skin_fallbacks,
    )

from solaris.analyze.output.pet_special_effect_facts import (
    replace_pet_special_effect_facts,
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
RENDER_ASSET_MANIFEST_CONTRACT_VERSION = "2"
RENDER_ASSET_MANIFEST_CONTRACT_VERSION_KEY = "render_asset_manifest_contract_version"
RENDER_ASSET_MANIFEST_REVISION_KEY = "render_asset_manifest_revision"
RENDER_ASSET_MANIFEST_SCOPES_KEY = "render_asset_manifest_complete_scopes"
RENDER_ASSET_MANIFEST_ASSET_REPOSITORY_KEY = (
    "render_asset_manifest_asset_repository"
)
RENDER_ASSET_MANIFEST_ASSET_REPOSITORY_REVISION_KEY = (
    "render_asset_manifest_asset_repository_revision"
)
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
    asset_repository_name=RENDER_ASSET_REPOSITORY,
    manifest_contract_version=RENDER_ASSET_MANIFEST_CONTRACT_VERSION,
    manifest_contract_version_key=RENDER_ASSET_MANIFEST_CONTRACT_VERSION_KEY,
    manifest_revision_key=RENDER_ASSET_MANIFEST_REVISION_KEY,
    manifest_scopes_key=RENDER_ASSET_MANIFEST_SCOPES_KEY,
    manifest_asset_repository_key=RENDER_ASSET_MANIFEST_ASSET_REPOSITORY_KEY,
    manifest_asset_repository_revision_key=(
        RENDER_ASSET_MANIFEST_ASSET_REPOSITORY_REVISION_KEY
    ),
    pet_info_scope=PET_INFO_RENDER_ASSET_SCOPE,
    type_matchup_scope=TYPE_MATCHUP_RENDER_ASSET_SCOPE,
    peak_pool_scope=PEAK_POOL_RENDER_ASSET_SCOPE,
    new_content_standard_scope=NEW_CONTENT_STANDARD_RENDER_ASSET_SCOPE,
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


@dataclass(frozen=True, slots=True)
class ConfigPackageData:
    version: str
    bundle_url: str
    mintmark_quality: dict[int, int]
    skin_store_prices: list["SkinStorePrice"]
    skin_shop_prices: list["SkinShopPrice"]
    skin_item_tips: dict[int, str]
    soulmark_icons: list["SoulmarkIcon"]
    autocard_season_effects: list["AutocardSeasonEffect"]


def _build_classic_skin_image_resolutions(
    db_path: Path,
) -> list[SkinImageResolution]:
    with sqlite3.connect(db_path) as conn:
        skin_rows = conn.execute(
            """
            SELECT id, name, resource_id
            FROM pet_skin
            WHERE category_id = ?
            ORDER BY id
            """,
            (CLASSIC_SKIN_CATEGORY_ID,),
        ).fetchall()
        skins = tuple(
            ClassicSkinImageSource(
                skin_id=int(skin_id),
                name=str(name).strip(),
                resource_id=int(resource_id),
            )
            for skin_id, name, resource_id in skin_rows
            if int(resource_id) > 0 and str(name).strip()
        )
        skin_names = {skin.name for skin in skins}
        pet_rows = conn.execute(
            """
            SELECT id, name, resource_id
            FROM pet
            WHERE resource_id > 0
            ORDER BY id
            """
        ).fetchall()
        pets = tuple(
            PetImageSource(
                pet_id=int(pet_id),
                name=str(name).strip(),
                resource_id=int(resource_id),
            )
            for pet_id, name, resource_id in pet_rows
            if str(name).strip() in skin_names
        )

    direct_keys = {
        (kind, skin.resource_id)
        for skin in skins
        for kind in PET_IMAGE_ASSET_KINDS
    }
    checks = SKIN_IMAGE_ASSET_PROBE.verify_assets(direct_keys)
    source_keys = source_asset_keys_for_classic_skin_fallbacks(
        skins,
        pets,
        checks,
    )
    checks.update(SKIN_IMAGE_ASSET_PROBE.verify_assets(source_keys - checks.keys()))

    hash_asset_keys = content_hash_keys_for_classic_skin_fallbacks(
        skins,
        pets,
        checks,
    )
    asset_hashes = {
        asset_key: asset_hash
        for asset_key in hash_asset_keys
        for check in (checks[asset_key],)
        if check.available
        and (asset_hash := SKIN_IMAGE_ASSET_PROBE.download_asset_hash(check))
        is not None
    }
    resolutions = resolve_classic_skin_image_resources(
        skins,
        pets,
        checks,
        asset_hashes,
    )
    fallback_count = sum(
        1
        for resolution in resolutions
        if resolution.head_resolution != "direct_skin"
        or resolution.body_resolution != "direct_skin"
    )
    unresolved_count = sum(
        1
        for resolution in resolutions
        if resolution.head_resolution in {"unresolved", "unverified"}
        or resolution.body_resolution in {"unresolved", "unverified"}
    )
    logger.info(
        "Resolved classic skin images: %s rows, %s with fallback, %s unresolved",
        len(resolutions),
        fallback_count,
        unresolved_count,
    )
    return resolutions


def _parse_content_length(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _short_error(error: Exception | str) -> str:
    return str(error).replace("\n", " ")[:200]


def _collect_soulmark_icon_render_issues(
    soulmark_icons: list[tuple[int, int, int, int]],
    asset_checks: dict[int, EffectIconAssetCheck],
    png_renders: dict[int, EffectIconPngRender],
    pet_names: dict[int, str],
) -> list[SoulmarkIconRenderIssue]:
    """Return every pet/soulmark whose verified icon did not yield a PNG."""
    issues: list[SoulmarkIconRenderIssue] = []
    for soulmark_id, pet_id, effect_id, icon_id in soulmark_icons:
        png_render = png_renders[icon_id]
        if png_render.available:
            continue
        asset_check = asset_checks[icon_id]
        issues.append(
            SoulmarkIconRenderIssue(
                icon_id=icon_id,
                soulmark_id=soulmark_id,
                pet_id=pet_id,
                pet_name=pet_names.get(pet_id, f"未知精灵#{pet_id}"),
                effect_id=effect_id,
                icon_asset_status=asset_check.status,
                icon_asset_error=asset_check.error,
                icon_png_error=png_render.error,
            )
        )
    return issues


def _effect_icon_ids(config_data: ConfigPackageData) -> list[int]:
    return sorted({item.icon_id for item in config_data.soulmark_icons})


def _seed_effect_icon_png_cache_from_database(db_path: Path) -> int:
    if not db_path.is_file():
        logger.info("No previous IronsBot database to seed effect icon PNG cache")
        return 0
    try:
        with sqlite3.connect(db_path) as conn:
            metadata_row = conn.execute(
                """
                SELECT value
                FROM ironsbot_metadata
                WHERE key = 'effect_icon_png_cache_version'
                """
            ).fetchone()
            if metadata_row is None or metadata_row[0] != EFFECT_ICON_PNG_CACHE_VERSION:
                logger.info(
                    "Previous effect icon PNG cache uses a different renderer version; "
                    "not seeding it"
                )
                return 0
            rows = conn.execute(
                f"""
                SELECT
                    icon_id,
                    icon_png,
                    icon_asset_content_length,
                    icon_asset_content_type
                FROM {SOULMARK_ICON_TABLE}
                WHERE icon_png_available = 1
                  AND icon_png IS NOT NULL
                  AND icon_asset_content_length IS NOT NULL
                GROUP BY icon_id
                """
            ).fetchall()
    except sqlite3.Error as error:
        logger.warning(
            "Unable to seed effect icon PNG cache from %s: %s",
            db_path,
            _short_error(error),
        )
        return 0

    seeded_count = 0
    for icon_id, png_data, content_length, content_type in rows:
        if not isinstance(png_data, bytes):
            continue
        check = EffectIconAssetCheck(
            icon_id=int(icon_id),
            url=_effect_icon_asset_url(int(icon_id), config=EFFECT_ICON_BUILD_CONFIG),
            available=True,
            status=200,
            content_type=str(content_type),
            content_length=int(content_length),
            error="",
        )
        if save_effect_icon_png_cache(
            int(icon_id),
            png_data,
            check,
            config=EFFECT_ICON_BUILD_CONFIG,
            logger=logger,
        ):
            seeded_count += 1
    logger.info(
        "Seeded %s effect icon PNGs from previous IronsBot database",
        seeded_count,
    )
    return seeded_count


def _export_effect_icon_png_cache_shard(
    icon_ids: list[int],
    output_dir: Path,
) -> int:
    exported_count = 0
    target_dir = output_dir / EFFECT_ICON_PNG_CACHE_VERSION
    target_dir.mkdir(parents=True, exist_ok=True)
    for icon_id in icon_ids:
        source_path = effect_icon_png_cache_path(
            icon_id,
            config=EFFECT_ICON_BUILD_CONFIG,
        )
        metadata_path = effect_icon_png_cache_metadata_path(
            icon_id,
            config=EFFECT_ICON_BUILD_CONFIG,
        )
        if not source_path.is_file() or not metadata_path.is_file():
            continue
        shutil.copy2(source_path, target_dir / source_path.name)
        shutil.copy2(metadata_path, target_dir / metadata_path.name)
        exported_count += 1
    logger.info(
        "Exported %s effect icon PNG cache entries to %s",
        exported_count,
        output_dir,
    )
    return exported_count


def _render_effect_icon_png_cache_shard(
    *,
    shard_index: int,
    shard_count: int,
    output_dir: Path,
) -> tuple[int, int]:
    if shard_count <= 0:
        raise ValueError("Effect icon shard count must be positive")
    if shard_index < 0 or shard_index >= shard_count:
        raise ValueError(
            f"Effect icon shard index must be in 0..{shard_count - 1}"
        )

    config_data = _fetch_config_package_data()
    icon_ids = set(_effect_icon_ids(config_data))
    fallback_icon_ids = unity_effect_icon_swf_fallback_icon_ids(
        icon_ids,
        config=_effect_icon_source_config(),
        fetch_package_manifest=lambda base_url, package_name: BUILD_HTTP.fetch_package_manifest(
            base_url,
            package_name,
            parse_manifest=parse_package_manifest,
        ),
        logger=logger,
    )
    shard_icon_ids = fallback_icon_ids[shard_index::shard_count]
    logger.info(
        "Rendering SWF fallback effect icon cache shard %s/%s: %s icons",
        shard_index + 1,
        shard_count,
        len(shard_icon_ids),
    )
    _checks, renders = load_flash_effect_icon_png_assets(
        set(shard_icon_ids),
        config=EFFECT_ICON_BUILD_CONFIG,
        request=BUILD_HTTP.request,
        open_url=urlopen,
        logger=logger,
        require_any=False,
    )
    _export_effect_icon_png_cache_shard(shard_icon_ids, output_dir)
    return len(shard_icon_ids), sum(
        1 for render in renders.values() if render.available
    )


def _fetch_config_package_data() -> ConfigPackageData:
    base_url = CONFIG_PACKAGE_BASE_URL.rstrip("/") + "/"
    version, manifest = BUILD_HTTP.fetch_package_manifest(
        base_url,
        PACKAGE_NAME,
        parse_manifest=parse_package_manifest,
    )
    for bundle in manifest.bundles:
        if bundle.name == CONFIG_BUNDLE_NAME:
            break
    else:
        if len(manifest.bundles) != 1:
            raise ValueError("ConfigPackage bundle not found")
        bundle = manifest.bundles[0]
    bundle_url = urljoin(base_url, bundle.file_hash)
    bundle_data = BUILD_HTTP.download_bytes(bundle_url)
    assets = extract_text_assets(bundle_data, CONFIG_TEXT_ASSETS)
    return ConfigPackageData(
        version=version,
        bundle_url=bundle_url,
        mintmark_quality=parse_mintmark_quality(assets[MINTMARK_BYTES_NAME]),
        skin_store_prices=parse_skin_store_pool(assets[SKIN_STORE_POOL_BYTES_NAME]),
        skin_shop_prices=parse_skin_shop(assets[SKIN_SHOP_BYTES_NAME]),
        skin_item_tips=parse_items_tip(assets[ITEMS_TIP_BYTES_NAME]),
        soulmark_icons=parse_effect_icons(assets[EFFECT_ICON_BYTES_NAME]),
        autocard_season_effects=parse_autocard_season_effects(
            assets[AUTOCARD_SEASON_EFFECT_BYTES_NAME]
        ),
    )


def _load_item_exchange_prices() -> list[ItemExchangePrice]:
    try:
        currency_names = _parse_unity_item_names(
            BUILD_HTTP.download_bytes(UNITY_ITEM_CATALOG_URL)
        )
    except (
        HTTPError,
        URLError,
        TimeoutError,
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as error:
        logger.warning("Official Unity item names skipped: %s", _short_error(error))
        currency_names = {}

    sources = (
        (
            BATTLEPASS_SHOP_SOURCE_NAME,
            BATTLEPASS_SHOP_URL,
            partial(
                parse_commodity_shop,
                source_key=BATTLEPASS_SHOP_SOURCE_KEY,
                source_name=BATTLEPASS_SHOP_SOURCE_NAME,
            ),
        ),
        (
            ACTIVITY_SHOP_SOURCE_NAME,
            ACTIVITY_SHOP_URL,
            partial(
                parse_commodity_shop,
                source_key=ACTIVITY_SHOP_SOURCE_KEY,
                source_name=ACTIVITY_SHOP_SOURCE_NAME,
            ),
        ),
        (
            SPECIAL_SKILL_SHOP_SOURCE_NAME,
            SPECIAL_SKILL_SHOP_URL,
            partial(
                parse_special_skill_shop,
                source_key=SPECIAL_SKILL_SHOP_SOURCE_KEY,
                source_name=SPECIAL_SKILL_SHOP_SOURCE_NAME,
            ),
        ),
    )
    prices: list[ItemExchangePrice] = []
    for source_name, source_url, parser in sources:
        try:
            prices.extend(
                replace(
                    price,
                    currency_name=currency_names.get(price.currency_item_id, ""),
                )
                for price in parser(BUILD_HTTP.download_bytes(source_url))
            )
        except (
            HTTPError,
            URLError,
            TimeoutError,
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as error:
            logger.warning(
                "Item exchange price source skipped (%s): %s",
                source_name,
                _short_error(error),
            )
    return prices


def _load_effect_descriptions() -> list[EffectDescription]:
    try:
        return parse_effect_descriptions(
            BUILD_HTTP.download_bytes(EFFECT_DESCRIPTION_URL)
        )
    except (
        HTTPError,
        URLError,
        TimeoutError,
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as error:
        logger.warning(
            "Effect description source skipped: %s",
            _short_error(error),
        )
        return []


def _load_special_effect_statuses() -> list[SpecialEffectStatus]:
    try:
        return parse_special_effect_statuses(
            BUILD_HTTP.download_bytes(SPECIAL_EFFECT_STATUS_URL)
        )
    except (
        HTTPError,
        URLError,
        TimeoutError,
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as error:
        logger.warning(
            "Special effect status source skipped: %s",
            _short_error(error),
        )
        return []


def _load_autocard_json(filename: str) -> tuple[dict[str, object], str]:
    if AUTOCARD_JSON_DIR:
        path = Path(AUTOCARD_JSON_DIR) / filename
        if path.exists():
            return (
                json.loads(path.read_text(encoding="utf-8")),
                str(path),
            )

    base_url = AUTOCARD_JSON_BASE_URL.rstrip("/") + "/"
    url = urljoin(base_url, filename)
    return (
        json.loads(BUILD_HTTP.download_bytes(url).decode("utf-8-sig")),
        url,
    )


def _parse_unity_item_names(data: bytes) -> dict[int, str]:
    """Read exchange-currency labels from the official Unity item catalog."""

    raw = json.loads(data.decode("utf-8-sig"))
    if not isinstance(raw, dict):
        raise ValueError("Unity item catalog root must be an object")
    items_root = raw.get("root")
    if not isinstance(items_root, dict):
        raise ValueError("Unity item catalog has no root object")
    rows = items_root.get("items")
    if not isinstance(rows, list):
        raise ValueError("Unity item catalog has no items list")

    item_names: dict[int, str] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        item_id = item_int(row, "id")
        item_name = item_text(row, "name").strip()
        if item_id <= 0 or not item_name:
            continue
        existing_name = item_names.setdefault(item_id, item_name)
        if existing_name != item_name:
            raise ValueError(
                f"Unity item catalog has conflicting name for item {item_id} "
                f"at index {index}"
            )
    return item_names


def _load_pet_partner_data() -> PetPartnerData:
    try:
        return parse_pet_partner_data(
            BUILD_HTTP.download_bytes(PARTNER_CONTRACTS_URL),
            schema_version=PARTNER_CONTRACTS_SCHEMA_VERSION,
            group_type=PARTNER_CONTRACT_GROUP_TYPE,
            cost_item_id=CONTRACT_BADGE_ITEM_ID,
            cost_item_name=CONTRACT_BADGE_ITEM_NAME,
            descriptions_reversed=PARTNER_CONTRACTS_V1_DESCRIPTIONS_REVERSED,
        )
    except (
        HTTPError,
        URLError,
        TimeoutError,
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
    ) as error:
        raise RuntimeError(
            "Unable to load official ConfigPackage partner contracts: "
            f"{_short_error(error)}"
        ) from error


def _quick_check(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        result = conn.execute("PRAGMA quick_check").fetchone()
    if not result or result[0] != "ok":
        raise sqlite3.DatabaseError(
            f"SQLite quick_check failed: {result}"
        )


def _merge_ironsbot_tables(
    db_path: Path,
    *,
    config_data: ConfigPackageData,
    autocard_data: AutocardData,
    item_exchange_prices: list[ItemExchangePrice],
    effect_descriptions: list[EffectDescription],
    special_effect_statuses: list[SpecialEffectStatus],
    pet_partner_data: PetPartnerData,
    weekly_preview_probe: dict[str, str],
    skin_image_resolutions: list[SkinImageResolution] | None = None,
) -> None:
    now = time.time()
    skin_image_resolutions = skin_image_resolutions or []
    asset_repository_snapshot = load_asset_repository_snapshot(
        RENDER_ASSET_REPOSITORY_CONFIG,
        BUILD_HTTP.download_bytes,
        logger=logger,
    )
    with sqlite3.connect(db_path) as conn:
        replace_config_package_tables(
            conn,
            config_data,
            skin_image_resolutions,
            now=now,
        )
        replace_reference_tables(
            conn,
            item_exchange_prices=item_exchange_prices,
            effect_descriptions=effect_descriptions,
            special_effect_statuses=special_effect_statuses,
            now=now,
        )
        remote_asset_manifest = collect_remote_asset_manifest(
            conn,
            asset_repository_snapshot,
            release_revision=config_data.version,
            config=RENDER_ASSET_MANIFEST_CONFIG,
        )
        deduplicated_soulmark_icons = sorted(
            {
                (
                    item.soulmark_id,
                    item.pet_id,
                    item.effect_id,
                    item.icon_id,
                )
                for item in config_data.soulmark_icons
            }
        )
        effect_icon_resolution = resolve_effect_icon_png_assets(
            {icon_id for _, _, _, icon_id in deduplicated_soulmark_icons},
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
        )
        effect_icon_asset_checks = effect_icon_resolution.asset_checks
        effect_icon_png_renders = effect_icon_resolution.png_renders
        render_asset_manifest_build = build_render_asset_manifest(
            remote_asset_manifest,
            {
                icon_id: (
                    render.data if render.available and render.data is not None else None
                )
                for icon_id, render in effect_icon_png_renders.items()
                if icon_id in effect_icon_asset_checks
            },
            asset_repository_snapshot,
            release_revision=config_data.version,
            effect_icon_source_version=EFFECT_ICON_PNG_CACHE_VERSION,
            config=RENDER_ASSET_MANIFEST_CONFIG,
        )
        render_asset_manifest = render_asset_manifest_build.entries
        issue_pet_ids = sorted(
            {
                pet_id
                for _, pet_id, _, icon_id in deduplicated_soulmark_icons
                if not effect_icon_png_renders[icon_id].available
            }
        )
        pet_names: dict[int, str] = {}
        if issue_pet_ids:
            placeholders = ", ".join("?" for _ in issue_pet_ids)
            pet_names = {
                int(pet_id): str(name)
                for pet_id, name in conn.execute(
                    f"SELECT id, name FROM pet WHERE id IN ({placeholders})",
                    issue_pet_ids,
                )
            }
        soulmark_icon_render_issues = _collect_soulmark_icon_render_issues(
            deduplicated_soulmark_icons,
            effect_icon_asset_checks,
            effect_icon_png_renders,
            pet_names,
        )
        replace_soulmark_icon_tables(
            conn,
            soulmark_icons=deduplicated_soulmark_icons,
            asset_checks=effect_icon_asset_checks,
            png_renders=effect_icon_png_renders,
            render_issues=soulmark_icon_render_issues,
            now=now,
        )
        replace_render_asset_manifest_table(
            conn,
            render_asset_manifest,
            updated_at=now,
        )
        replace_autocard_tables(conn, autocard_data, now)
        replace_autocard_season_effect_table(
            conn,
            config_data.autocard_season_effects,
            now,
        )
        replace_pet_partner_tables(conn, pet_partner_data, updated_at=now)
        special_effect_facts = replace_pet_special_effect_facts(conn, now=now)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ironsbot_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        metadata = {
            SEERAPI_SCHEMA_CONTRACT_VERSION_KEY: SEERAPI_SCHEMA_CONTRACT_VERSION,
            "built_at": str(int(now)),
            "upstream_seerapi_url": UPSTREAM_SEERAPI_URL,
            "config_package_base_url": CONFIG_PACKAGE_BASE_URL,
            "config_package_version": config_data.version,
            "config_bundle_url": config_data.bundle_url,
            "effect_icon_asset_base_url": EFFECT_ICON_ASSET_BASE_URL,
            "effect_icon_asset_suffix": EFFECT_ICON_ASSET_SUFFIX,
            "effect_icon_prefer_flash": str(int(EFFECT_ICON_PREFER_FLASH)),
            "effect_icon_primary_source": effect_icon_resolution.preferred_source,
            "effect_icon_unity_png_enabled": str(int(UNITY_EFFECT_ICON_PNG_ENABLED)),
            "effect_icon_unity_package_base_url": DEFAULT_PACKAGE_BASE_URL,
            "effect_icon_unity_package_version": (
                effect_icon_resolution.unity_package_version
            ),
            "effect_icon_unity_manifest_icon_count": str(
                effect_icon_resolution.unity_manifest_icon_count
            ),
            "effect_icon_unity_png_available_count": str(
                effect_icon_resolution.unity_png_available_count
            ),
            "effect_icon_unity_png_missing_count": str(
                len(effect_icon_resolution.unity_missing_icon_ids)
            ),
            "effect_icon_unity_png_missing_ids": ",".join(
                str(icon_id) for icon_id in effect_icon_resolution.unity_missing_icon_ids
            ),
            "effect_icon_flash_png_available_count": str(
                effect_icon_resolution.flash_png_available_count
            ),
            "effect_icon_flash_png_missing_count": str(
                len(effect_icon_resolution.flash_missing_icon_ids)
            ),
            "effect_icon_flash_png_missing_ids": ",".join(
                str(icon_id) for icon_id in effect_icon_resolution.flash_missing_icon_ids
            ),
            "effect_icon_unity_fallback_icon_count": str(
                effect_icon_resolution.unity_fallback_icon_count
            ),
            "effect_icon_swf_fallback_icon_count": str(
                effect_icon_resolution.swf_fallback_icon_count
            ),
            "effect_icon_swf_fallback_icon_ids": ",".join(
                str(icon_id) for icon_id in effect_icon_resolution.unity_missing_icon_ids
            ),
            "effect_icon_asset_checked_count": str(len(effect_icon_asset_checks)),
            "effect_icon_asset_available_count": str(
                sum(1 for check in effect_icon_asset_checks.values() if check.available)
            ),
            "effect_icon_asset_missing_count": str(
                sum(
                    1
                    for check in effect_icon_asset_checks.values()
                    if not check.available
                )
            ),
            "effect_icon_png_render_enabled": str(
                int(EFFECT_ICON_PNG_RENDER_ENABLED)
            ),
            "effect_icon_png_renderer": "ffdec-swf+unity-defaultpackage-png",
            "effect_icon_png_resolution_order": (
                "ffdec-swf,unity-defaultpackage-png"
                if EFFECT_ICON_PREFER_FLASH
                else "unity-defaultpackage-png,ffdec-swf"
            ),
            "effect_icon_png_render_java_command": (
                EFFECT_ICON_PNG_RENDER_JAVA_COMMAND
            ),
            "effect_icon_png_render_ffdec_jar": str(
                EFFECT_ICON_PNG_RENDER_FFDEC_JAR
            ),
            "effect_icon_png_cache_version": EFFECT_ICON_PNG_CACHE_VERSION,
            "effect_icon_png_render_zoom": str(EFFECT_ICON_PNG_RENDER_ZOOM),
            "effect_icon_png_render_checked_count": str(
                len(effect_icon_png_renders)
            ),
            "effect_icon_png_render_available_count": str(
                sum(
                    1
                    for render in effect_icon_png_renders.values()
                    if render.available
                )
            ),
            "effect_icon_png_render_missing_count": str(
                sum(
                    1
                    for render in effect_icon_png_renders.values()
                    if not render.available
                )
            ),
            "effect_icon_png_render_issue_row_count": str(
                len(soulmark_icon_render_issues)
            ),
            **render_asset_manifest_build.metadata,
            "mintmark_quality_count": str(len(config_data.mintmark_quality)),
            "skin_store_price_count": str(len(config_data.skin_store_prices)),
            "skin_shop_price_count": str(len(config_data.skin_shop_prices)),
            "skin_item_tip_count": str(len(config_data.skin_item_tips)),
            "skin_image_resolution_count": str(len(skin_image_resolutions)),
            "skin_image_resolution_fallback_count": str(
                sum(
                    1
                    for resolution in skin_image_resolutions
                    if resolution.head_resolution != "direct_skin"
                    or resolution.body_resolution != "direct_skin"
                )
            ),
            "skin_image_resolution_unresolved_count": str(
                sum(
                    1
                    for resolution in skin_image_resolutions
                    if resolution.head_resolution in {"unresolved", "unverified"}
                    or resolution.body_resolution in {"unresolved", "unverified"}
                )
            ),
            "item_exchange_price_count": str(len(item_exchange_prices)),
            "item_exchange_price_source_urls": "\n".join(
                (
                    BATTLEPASS_SHOP_URL,
                    ACTIVITY_SHOP_URL,
                    SPECIAL_SKILL_SHOP_URL,
                    UNITY_ITEM_CATALOG_URL,
                )
            ),
            "effect_description_count": str(len(effect_descriptions)),
            "effect_description_source_url": EFFECT_DESCRIPTION_URL,
            "special_effect_status_count": str(len(special_effect_statuses)),
            "special_effect_status_source_url": SPECIAL_EFFECT_STATUS_URL,
            "pet_special_effect_count": str(special_effect_facts.facts),
            "pet_special_effect_source_count": str(special_effect_facts.sources),
            "pet_special_effect_issue_count": str(special_effect_facts.issues),
            "pet_soulmark_display_count": str(
                special_effect_facts.soulmark_display_rows
            ),
            "pet_soulmark_display_addition_count": str(
                special_effect_facts.soulmark_display_addition_rows
            ),
            "pet_partner_group_count": str(len(pet_partner_data.groups)),
            "pet_partner_upgrade_count": str(len(pet_partner_data.upgrades)),
            "pet_partner_source_url": PARTNER_CONTRACTS_URL,
            "soulmark_icon_count": str(len(deduplicated_soulmark_icons)),
            "autocard_card_count": str(len(autocard_data.cards)),
            "autocard_role_count": str(len(autocard_data.roles)),
            "autocard_nature_count": str(len(autocard_data.natures)),
            "autocard_buff_count": str(len(autocard_data.buffs)),
            "autocard_season_effect_count": str(
                len(config_data.autocard_season_effects)
            ),
            "autocard_source": autocard_data.source,
            "weekly_preview_image_url": WEEKLY_PREVIEW_IMAGE_URL,
            "weekly_preview_source_url": WEEKLY_PREVIEW_SOURCE_URL,
            **weekly_preview_probe,
        }
        conn.executemany(
            """
            INSERT INTO ironsbot_metadata (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            sorted(metadata.items()),
        )
        conn.commit()


def _parse_cli_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--seed-effect-icon-cache",
        type=Path,
        metavar="DATABASE",
        help="restore matching effect icon PNGs from a previous IronsBot SQLite database",
    )
    parser.add_argument(
        "--render-effect-icon-shard",
        type=int,
        metavar="INDEX",
        help="render one zero-based effect icon cache shard instead of building SQLite",
    )
    parser.add_argument(
        "--effect-icon-shard-count",
        type=int,
        default=1,
        metavar="COUNT",
        help="total shard count used with --render-effect-icon-shard",
    )
    parser.add_argument(
        "--export-effect-icon-cache-shard",
        type=Path,
        metavar="DIRECTORY",
        help="output directory for the rendered shard cache",
    )
    arguments = parser.parse_args()
    if arguments.render_effect_icon_shard is None:
        if (
            arguments.effect_icon_shard_count != 1
            or arguments.export_effect_icon_cache_shard is not None
        ):
            parser.error(
                "--effect-icon-shard-count and --export-effect-icon-cache-shard "
                "require --render-effect-icon-shard"
            )
    elif arguments.export_effect_icon_cache_shard is None:
        parser.error(
            "--render-effect-icon-shard requires --export-effect-icon-cache-shard"
        )
    return arguments


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    arguments = _parse_cli_args()
    if arguments.seed_effect_icon_cache is not None:
        _seed_effect_icon_png_cache_from_database(arguments.seed_effect_icon_cache)
        return
    if arguments.render_effect_icon_shard is not None:
        icon_count, available_count = _render_effect_icon_png_cache_shard(
            shard_index=arguments.render_effect_icon_shard,
            shard_count=arguments.effect_icon_shard_count,
            output_dir=arguments.export_effect_icon_cache_shard,
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

    logger.info("Loading official ConfigPackage: %s", CONFIG_PACKAGE_BASE_URL)
    config_data = _fetch_config_package_data()
    if not config_data.mintmark_quality:
        raise ValueError("mintmark Quality map is empty")
    logger.info(
        "Loading autocard JSON data: %s",
        AUTOCARD_JSON_DIR or AUTOCARD_JSON_BASE_URL,
    )
    autocard_data = load_autocard_data(
        _load_autocard_json,
        content_file=AUTOCARD_CONTENT_FILE,
        nature_file=AUTOCARD_NATURE_FILE,
        role_file=AUTOCARD_ROLE_FILE,
        buff_file=AUTOCARD_BUFF_FILE,
    )
    logger.info("Loading official item exchange prices")
    item_exchange_prices = _load_item_exchange_prices()
    logger.info("Loading official named effect descriptions")
    effect_descriptions = _load_effect_descriptions()
    logger.info("Loading official special effect statuses")
    special_effect_statuses = _load_special_effect_statuses()
    logger.info("Loading official contract-partner data")
    pet_partner_data = _load_pet_partner_data()
    logger.info("Resolving classic skin image resources")
    skin_image_resolutions = _build_classic_skin_image_resolutions(OUTPUT_DB)
    logger.info("Probing weekly preview image: %s", WEEKLY_PREVIEW_IMAGE_URL)
    weekly_preview_probe = BUILD_HTTP.probe_image(WEEKLY_PREVIEW_IMAGE_URL)

    _merge_ironsbot_tables(
        OUTPUT_DB,
        config_data=config_data,
        autocard_data=autocard_data,
        item_exchange_prices=item_exchange_prices,
        effect_descriptions=effect_descriptions,
        special_effect_statuses=special_effect_statuses,
        pet_partner_data=pet_partner_data,
        weekly_preview_probe=weekly_preview_probe,
        skin_image_resolutions=skin_image_resolutions,
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
