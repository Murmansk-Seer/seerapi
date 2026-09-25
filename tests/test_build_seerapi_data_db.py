from collections.abc import Sequence
from dataclasses import replace
from email.message import Message
import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import struct
import sys
from threading import Event
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request

from PIL import Image
import pytest

SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / 'scripts' / 'build_seerapi_data_db.py'
)
SCRIPT_ROOT = SCRIPT_PATH.parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))
import autocard_sources
import config_package_sources
import effect_icon_build
import effect_icon_build_types
import effect_icon_cache_cli
import effect_icon_flash_sources
import effect_icon_png_renderer
import effect_icon_source_paths
import effect_icon_unity_sources
import effect_metadata_sources
import item_exchange_sources
import partner_contract_sources
import release_autocard_tables
import release_build_types
import release_config_tables
import release_publication
import release_reference_tables
import release_render_manifest_tables
import release_soulmark_icon_tables
import release_source_loaders
import render_asset_manifest_build
import render_asset_repository
import skin_image_asset_probe
import skin_image_resolution

SPEC = importlib.util.spec_from_file_location('build_seerapi_data_db', SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError
builder = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = builder
SPEC.loader.exec_module(builder)


def _fetch_package_manifest(base_url: str, package_name: str):
    return builder.BUILD_HTTP.fetch_package_manifest(
        base_url,
        package_name,
        parse_manifest=builder.parse_package_manifest,
    )


def _seed_effect_icon_cache(database_path: Path) -> int:
    return effect_icon_cache_cli.seed_effect_icon_png_cache_from_database(
        database_path,
        cache_version=builder.EFFECT_ICON_PNG_CACHE_VERSION,
        icon_table=builder.SOULMARK_ICON_TABLE,
        config=builder.EFFECT_ICON_BUILD_CONFIG,
        effect_icon_url=lambda icon_id: builder._effect_icon_asset_url(
            icon_id,
            config=builder.EFFECT_ICON_BUILD_CONFIG,
        ),
        logger=builder.logger,
    )


def _capture_exported_icon_ids(
    captured: dict[str, list[int]], icon_ids: Sequence[int]
) -> int:
    captured['icon_ids'] = list(icon_ids)
    return 2


def test_published_schema_contract_metadata_is_explicit() -> None:
    assert builder.SEERAPI_SCHEMA_CONTRACT_VERSION == '2'
    assert builder.SEERAPI_SCHEMA_CONTRACT_VERSION_KEY == (
        'seerapi_schema_contract_version'
    )


@pytest.fixture(autouse=True)
def _isolate_effect_icon_png_cache(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        builder,
        'EFFECT_ICON_BUILD_CONFIG',
        builder.replace(
            builder.EFFECT_ICON_BUILD_CONFIG,
            cache_dir=tmp_path / 'effect-icon-png',
        ),
    )


def test_release_config_table_writer_replaces_all_config_package_tables() -> None:
    config_data = release_build_types.ConfigPackageData(
        version='test',
        bundle_url='https://example.invalid/config',
        mintmark_quality={8: 6},
        skin_store_prices=[
            config_package_sources.SkinStorePrice(
                skin_id=538,
                pool_id=1,
                price=50,
                original_price=60,
                discount_rate=80,
                selected_price=45,
                ticket_id=1720001,
                ticket_num=2,
                start_time=1,
                end_time=2,
            )
        ],
        skin_shop_prices=[
            config_package_sources.SkinShopPrice(
                skin_id=539,
                resource_id=1400539,
                card_price=20,
                diamond_price=30,
                original_price=40,
            )
        ],
        skin_item_tips={1720001: '测试道具'},
        soulmark_icons=[],
        autocard_season_effects=[],
    )
    resolution = skin_image_resolution.SkinImageResolution(
        skin_id=538,
        head_resource_id=3382,
        body_resource_id=1400538,
        head_resolution='unique_name_source',
        body_resolution='direct_skin',
        source_pet_id=3382,
    )

    with sqlite3.connect(':memory:') as connection:
        release_config_tables.replace_config_package_tables(
            connection,
            config_data,
            [resolution],
            now=123.0,
        )
        assert connection.execute(
            'SELECT mintmark_id, quality, source, updated_at FROM mintmark_quality'
        ).fetchall() == [(8, 6, 'ConfigPackage/mintmark.bytes', 123.0)]
        assert connection.execute(
            'SELECT skin_id, pool_id, price, ticket_num FROM skin_store_price'
        ).fetchall() == [(538, 1, 50, 2)]
        assert connection.execute(
            'SELECT skin_id, resource_id, diamond_price FROM skin_shop_price'
        ).fetchall() == [(539, 1400539, 30)]
        assert connection.execute(
            'SELECT item_id, description FROM skin_item_tip'
        ).fetchall() == [(1720001, '测试道具')]
        assert connection.execute(
            'SELECT skin_id, head_resource_id, source_pet_id FROM skin_image_resolution'
        ).fetchall() == [(538, 3382, 3382)]


def test_release_reference_table_writer_replaces_official_reference_tables() -> None:
    price = item_exchange_sources.ItemExchangePrice(
        source_key='battlepass_shop',
        source_name='战令商店',
        source_entry_id=1,
        item_id=1728296,
        item_name='双源魂蒂',
        item_quantity=1,
        currency_item_id=1726710,
        currency_name='共鸣锚点',
        amount=2000,
        purchase_limit=6,
        start_time=0,
        end_time=0,
    )
    effect = effect_metadata_sources.EffectDescription(
        effect_id=544, name='冥妖之悼', description='效果说明'
    )
    status = effect_metadata_sources.SpecialEffectStatus(
        status_id=147,
        name='旧日之晷',
        description='状态说明',
        show_monster_id=4125,
    )

    with sqlite3.connect(':memory:') as connection:
        release_reference_tables.replace_reference_tables(
            connection,
            item_exchange_prices=[price],
            effect_descriptions=[effect],
            special_effect_statuses=[status],
            now=123.0,
        )
        assert connection.execute(
            'SELECT item_id, source_name, amount FROM item_exchange_price'
        ).fetchall() == [(1728296, '战令商店', 2000)]
        assert connection.execute(
            'SELECT effect_id, name, description FROM effect_description'
        ).fetchall() == [(544, '冥妖之悼', '效果说明')]
        assert connection.execute(
            'SELECT status_id, name, show_monster_id FROM special_effect_status'
        ).fetchall() == [(147, '旧日之晷', 4125)]


def test_release_soulmark_icon_writer_replaces_icons_and_issues() -> None:
    asset_check = effect_icon_build.EffectIconAssetCheck(
        icon_id=18,
        url='https://assets.example/18.swf',
        available=True,
        status=200,
        content_type='application/x-shockwave-flash',
        content_length=10,
        error='',
    )
    png_render = effect_icon_build.EffectIconPngRender(
        icon_id=18,
        available=True,
        content_type='image/png',
        content_length=3,
        data=b'png',
        error='',
    )
    issue = effect_icon_build_types.SoulmarkIconRenderIssue(
        icon_id=19,
        soulmark_id=2,
        pet_id=300,
        pet_name='测试精灵',
        effect_id=4,
        icon_asset_status=404,
        icon_asset_error='not found',
        icon_png_error='missing',
    )

    with sqlite3.connect(':memory:') as connection:
        release_soulmark_icon_tables.replace_soulmark_icon_tables(
            connection,
            soulmark_icons=[(1, 200, 3, 18)],
            asset_checks={18: asset_check},
            png_renders={18: png_render},
            render_issues=[issue],
            now=123.0,
        )
        assert connection.execute(
            'SELECT soulmark_id, icon_id, icon_asset_url, icon_png FROM soulmark_icon'
        ).fetchall() == [(1, 18, 'https://assets.example/18.swf', b'png')]
        assert connection.execute(
            'SELECT icon_id, pet_id, pet_name, icon_png_error '
            'FROM soulmark_icon_render_issue'
        ).fetchall() == [(19, 300, '测试精灵', 'missing')]


def test_effect_icon_source_paths_use_resolved_build_config() -> None:
    config = builder.replace(
        builder.EFFECT_ICON_BUILD_CONFIG,
        effect_icon_asset_base_url='https://assets.example/effect/',
        effect_icon_asset_suffix='.bin',
        default_package_base_url='https://assets.example/default/',
        unity_asset_prefix='Assets/effect/',
        unity_asset_suffix='.texture',
    )

    assert (
        effect_icon_source_paths.effect_icon_asset_url(42, config=config)
        == 'https://assets.example/effect/42.bin'
    )
    assert (
        effect_icon_source_paths.unity_effect_icon_asset_path(42, config=config)
        == 'Assets/effect/42.texture'
    )
    assert (
        effect_icon_source_paths.unity_effect_icon_expected_url(42, config=config)
        == 'https://assets.example/default/#Assets/effect/42.texture'
    )
    assert (
        effect_icon_source_paths.unity_effect_icon_id_from_asset_path(
            'Assets/effect/42.texture', config=config
        )
        == 42
    )
    assert (
        effect_icon_source_paths.unity_effect_icon_id_from_asset_path(
            'Assets/effect/not-an-id.texture', config=config
        )
        is None
    )
    assert (
        effect_icon_source_paths.unity_effect_icon_id_from_object_name('42.png') == 42
    )


def test_flash_effect_icon_adapter_accepts_ranged_swf_when_head_is_not_supported() -> (
    None
):
    class Response:
        status = 206
        headers = Message()
        headers['Content-Type'] = 'application/octet-stream'
        headers['Content-Length'] = '16'

        def __enter__(self) -> effect_icon_flash_sources.UrlResponse:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self, amount: int = -1) -> bytes:
            return b'FWS\x09' if amount >= 0 else b'FWS\x09payload'

    requests: list[tuple[str, str, dict[str, str] | None]] = []

    def fake_request(
        url: str,
        *,
        method: str,
        headers: dict[str, str] | None = None,
    ) -> Request:
        requests.append((url, method, headers))
        return Request(url, method=method, headers=headers or {})

    check = effect_icon_flash_sources.verify_effect_icon_asset(
        77,
        config=builder.EFFECT_ICON_BUILD_CONFIG,
        request=fake_request,
        open_url=lambda _request, **_kwargs: Response(),
    )

    assert check.available is True
    assert check.status == 206
    assert requests == [
        ('https://seer.61.com/resource/effectIcon/77.swf', 'HEAD', None),
        (
            'https://seer.61.com/resource/effectIcon/77.swf',
            'GET',
            {'Range': 'bytes=0-15'},
        ),
    ]


def _effect_icon_render_config(**changes):
    # Subprocess render tests stub execution, but still validate tool paths.
    values = {'java_command': sys.executable, 'ffdec_jar': Path(__file__), **changes}
    return builder.replace(builder.EFFECT_ICON_BUILD_CONFIG, **values)


def _create_special_effect_source_tables(database: Path) -> None:
    """Create the upstream tables required by the derived-fact builder."""
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE pet (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
            CREATE TABLE glossary_entry (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                desc TEXT NOT NULL
            );
            CREATE TABLE petglossaryentrylink (
                pet_id INTEGER NOT NULL,
                glossary_entry_id INTEGER NOT NULL
            );
            CREATE TABLE glossaryentrylink (
                source_id INTEGER NOT NULL,
                target_id INTEGER NOT NULL
            );
            CREATE TABLE skill (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                info TEXT,
                hide_effect_id INTEGER
            );
            CREATE TABLE skillinpetorm (
                pet_id INTEGER NOT NULL,
                skill_id INTEGER NOT NULL
            );
            CREATE TABLE skill_effect_in_use (
                id INTEGER PRIMARY KEY,
                info TEXT,
                analyze_info TEXT
            );
            CREATE TABLE skilleffectlink (
                skill_id INTEGER NOT NULL,
                effect_in_use_id INTEGER NOT NULL
            );
            CREATE TABLE skillfriendskilleffectlink (
                skill_id INTEGER NOT NULL,
                effect_in_use_id INTEGER NOT NULL
            );
            CREATE TABLE skill_hide_effect (
                id INTEGER PRIMARY KEY,
                description TEXT
            );
            CREATE TABLE soulmark (
                id INTEGER PRIMARY KEY,
                desc TEXT,
                analyze_desc TEXT,
                desc_formatting_adjustment TEXT,
                intensified INTEGER NOT NULL,
                is_adv INTEGER NOT NULL,
                intensified_to_id INTEGER
            );
            CREATE TABLE petsoulmarklink (
                pet_id INTEGER NOT NULL,
                soulmark_id INTEGER NOT NULL
            );
            """
        )


def _collect_remote_asset_manifest(
    connection: sqlite3.Connection,
    snapshot: render_asset_repository.AssetRepositorySnapshot | None,
    *,
    release_revision: str,
) -> render_asset_manifest_build.RemoteAssetManifestBuild:
    return render_asset_manifest_build.collect_remote_asset_manifest(
        connection,
        {'default': snapshot} if snapshot is not None else {},
        release_revision=release_revision,
        config=builder.RENDER_ASSET_MANIFEST_CONFIG,
    )


@pytest.mark.parametrize('standard_inventory', [False, True])
@pytest.mark.parametrize(
    ('missing', 'expected'),
    [
        (None, ('pet_info', 'type_matchup', 'peak_pool')),
        ('pet/body/100', ('type_matchup', 'peak_pool')),
        ('countermark/icon/8', ('type_matchup', 'peak_pool')),
        ('pet/head/100', ('type_matchup',)),
        ('pettype/1', ()),
        ('pettype/prop', ()),
        ('item/petitem/icon/9', ('pet_info', 'type_matchup', 'peak_pool')),
        ('battleeffect/signbuff/10', ('pet_info', 'type_matchup', 'peak_pool')),
        ('snapshot', ()),
        ('inventory', ()),
    ],
)
def test_renderer_scopes_follow_their_own_asset_families(
    missing, expected, standard_inventory
) -> None:
    with sqlite3.connect(':memory:') as connection:
        connection.executescript(
            """
            CREATE TABLE pet (resource_id INTEGER NOT NULL);
            CREATE TABLE element_type (id INTEGER NOT NULL);
            CREATE TABLE mintmark (id INTEGER NOT NULL);
            CREATE TABLE item (id INTEGER NOT NULL);
            CREATE TABLE special_effect_status (status_id INTEGER NOT NULL);
            INSERT INTO pet VALUES (100);
            INSERT INTO element_type VALUES (1);
            INSERT INTO mintmark VALUES (8);
            INSERT INTO item VALUES (9);
            INSERT INTO special_effect_status VALUES (10);
            """
        )
        if standard_inventory:
            connection.executescript(
                """
                CREATE TABLE suit (id INTEGER NOT NULL);
                CREATE TABLE equip (id INTEGER NOT NULL, part_type_id INTEGER NOT NULL);
                CREATE TABLE title_part (id INTEGER NOT NULL);
                CREATE TABLE skin_image_resolution (head_resource_id INTEGER NOT NULL);
                """
            )
            if 'pet_info' in expected:
                expected = (*expected, 'new_content_standard')
        if missing == 'inventory':
            connection.execute('DROP TABLE element_type')
        snapshot = (
            render_asset_repository.AssetRepositorySnapshot(
                revision='a' * 40,
                blobs_by_path={
                    f'newseer/assets/art/ui/assets/{path}.png': f'blob-{index}'
                    for index, path in enumerate(
                        (
                            'pet/head/100',
                            'pet/body/100',
                            'pettype/1',
                            'pettype/prop',
                            'countermark/icon/8',
                            'item/petitem/icon/9',
                            'battleeffect/signbuff/10',
                        )
                    )
                    if path != missing
                },
            )
            if missing != 'snapshot'
            else None
        )
        remote = _collect_remote_asset_manifest(
            connection,
            snapshot,
            release_revision='release-test',
        )
    result = render_asset_manifest_build.build_render_asset_manifest(
        remote,
        {},
        {'default': snapshot} if snapshot is not None else {},
        release_revision='release-test',
        effect_icon_source_version='test',
        config=builder.RENDER_ASSET_MANIFEST_CONFIG,
    )
    assert result.complete_scopes == expected
    assert json.loads(
        result.metadata[builder.RENDER_ASSET_MANIFEST_SCOPES_KEY]
    ) == list(expected)


def test_copy_or_download_upstream_database_uses_verified_local_input(
    monkeypatch, tmp_path: Path
) -> None:
    source = tmp_path / 'verified.sqlite'
    with sqlite3.connect(source) as conn:
        conn.execute('CREATE TABLE verified_source (value TEXT)')
        conn.execute("INSERT INTO verified_source VALUES ('api-data')")
    output = tmp_path / 'output.sqlite'
    monkeypatch.setattr(builder, 'UPSTREAM_SEERAPI_PATH', str(source))

    builder.BUILD_HTTP.copy_or_download_upstream_database(
        output,
        upstream_path=builder.UPSTREAM_SEERAPI_PATH,
        upstream_url=builder.UPSTREAM_SEERAPI_URL,
    )

    with sqlite3.connect(output) as conn:
        assert conn.execute('SELECT value FROM verified_source').fetchone() == (
            'api-data',
        )


def test_copy_or_download_upstream_database_rejects_missing_verified_input(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        builder,
        'UPSTREAM_SEERAPI_PATH',
        str(tmp_path / 'missing.sqlite'),
    )

    with pytest.raises(FileNotFoundError, match='Verified upstream'):
        builder.BUILD_HTTP.copy_or_download_upstream_database(
            tmp_path / 'output.sqlite',
            upstream_path=builder.UPSTREAM_SEERAPI_PATH,
            upstream_url=builder.UPSTREAM_SEERAPI_URL,
        )


def test_parse_battlepass_shop_keeps_exchange_price_details() -> None:
    payload = {
        'item': [
            {
                'commodity': '1_1728296_1',
                'consumeitemid': 1726710,
                'id': 1005,
                'limit': 6,
                'price': 2000,
                'quantity': 1,
                'timestart': 100,
                'timeend': 200,
            },
            {
                'commodity': '2_1728296_1',
                'consumeitemid': 1726710,
                'id': 1006,
                'limit': 6,
                'price': 2000,
                'quantity': 1,
            },
        ]
    }

    prices = item_exchange_sources.parse_commodity_shop(
        json.dumps(payload, ensure_ascii=False).encode('utf-8'),
        source_key=builder.BATTLEPASS_SHOP_SOURCE_KEY,
        source_name=builder.BATTLEPASS_SHOP_SOURCE_NAME,
    )

    assert prices == [
        item_exchange_sources.ItemExchangePrice(
            source_key='battlepass_shop',
            source_name='战令商店',
            source_entry_id=1005,
            item_id=1728296,
            item_name='',
            item_quantity=1,
            currency_item_id=1726710,
            amount=2000,
            purchase_limit=6,
            start_time=100,
            end_time=200,
        )
    ]


def _skin_asset_check(
    kind: str,
    resource_id: int,
    *,
    available: bool,
    status: int | None = None,
    error: str = '',
) -> Any:
    resolved_status = status if status is not None else (200 if available else 404)
    return skin_image_resolution.PetImageAssetCheck(
        kind=kind,
        resource_id=resource_id,
        url=f'https://example.invalid/{kind}/{resource_id}.png',
        available=available,
        status=resolved_status,
        content_type='image/png' if available else 'text/html',
        content_length=1 if available else None,
        error=error,
    )


def test_resolve_classic_skin_images_keeps_direct_assets_and_falls_back_per_kind() -> (
    None
):
    skins = (
        skin_image_resolution.ClassicSkinImageSource(250, '异次元·黄金天马', 1400250),
        skin_image_resolution.ClassicSkinImageSource(268, '波西亚', 1400268),
        skin_image_resolution.ClassicSkinImageSource(538, '天道魂帝', 1400538),
        skin_image_resolution.ClassicSkinImageSource(734, '记忆之核', 1400734),
        skin_image_resolution.ClassicSkinImageSource(761, '永恒圣拳', 1400761),
    )
    pets = (
        skin_image_resolution.PetImageSource(3382, '天道魂帝', 3382),
        skin_image_resolution.PetImageSource(3197, '永恒圣拳', 3197),
    )
    checks = {
        (kind, resource_id): _skin_asset_check(
            kind,
            resource_id,
            available=available,
        )
        for kind, resource_id, available in (
            ('head', 1400250, True),
            ('body', 1400250, True),
            ('head', 1400268, True),
            ('body', 1400268, True),
            ('head', 1400538, False),
            ('body', 1400538, True),
            ('head', 1400734, True),
            ('body', 1400734, True),
            ('head', 1400761, False),
            ('body', 1400761, False),
            ('head', 3382, True),
            ('body', 3382, True),
            ('head', 3197, True),
            ('body', 3197, True),
        )
    }

    rows = skin_image_resolution.resolve_classic_skin_image_resources(
        skins,
        pets,
        checks,
        {},
    )

    assert rows == [
        skin_image_resolution.SkinImageResolution(
            skin_id=250,
            head_resource_id=1400250,
            body_resource_id=1400250,
            head_resolution='direct_skin',
            body_resolution='direct_skin',
            source_pet_id=None,
        ),
        skin_image_resolution.SkinImageResolution(
            skin_id=268,
            head_resource_id=1400268,
            body_resource_id=1400268,
            head_resolution='direct_skin',
            body_resolution='direct_skin',
            source_pet_id=None,
        ),
        skin_image_resolution.SkinImageResolution(
            skin_id=538,
            head_resource_id=3382,
            body_resource_id=1400538,
            head_resolution='unique_name_source',
            body_resolution='direct_skin',
            source_pet_id=3382,
        ),
        skin_image_resolution.SkinImageResolution(
            skin_id=734,
            head_resource_id=1400734,
            body_resource_id=1400734,
            head_resolution='direct_skin',
            body_resolution='direct_skin',
            source_pet_id=None,
        ),
        skin_image_resolution.SkinImageResolution(
            skin_id=761,
            head_resource_id=3197,
            body_resource_id=3197,
            head_resolution='unique_name_source',
            body_resolution='unique_name_source',
            source_pet_id=3197,
        ),
    ]


def test_resolve_classic_skin_images_uses_content_hash_for_duplicate_names() -> None:
    skins = (
        skin_image_resolution.ClassicSkinImageSource(16, '皮皮', 1400016),
        skin_image_resolution.ClassicSkinImageSource(700, '皮皮', 1400700),
    )
    pets = (
        skin_image_resolution.PetImageSource(10, '皮皮', 10),
        skin_image_resolution.PetImageSource(3295, '皮皮', 3295),
    )
    checks = {
        (kind, resource_id): _skin_asset_check(
            kind,
            resource_id,
            available=available,
        )
        for kind, resource_id, available in (
            ('head', 1400016, False),
            ('body', 1400016, True),
            ('head', 1400700, False),
            ('body', 1400700, True),
            ('head', 10, True),
            ('body', 10, True),
            ('head', 3295, True),
            ('body', 3295, True),
        )
    }
    hashes = {
        ('body', 1400016): 'same-as-10',
        ('body', 1400700): 'same-as-10',
        ('body', 10): 'same-as-10',
        ('body', 3295): 'different',
    }

    rows = skin_image_resolution.resolve_classic_skin_image_resources(
        skins,
        pets,
        checks,
        hashes,
    )

    assert [(row.skin_id, row.head_resource_id, row.source_pet_id) for row in rows] == [
        (16, 10, 10),
        (700, 10, 10),
    ]
    assert all(row.head_resolution == 'content_verified_source' for row in rows)
    assert all(row.body_resolution == 'direct_skin' for row in rows)


def test_resolve_classic_skin_images_keeps_unresolved_assets_explicit() -> None:
    skin = skin_image_resolution.ClassicSkinImageSource(
        999, '不存在的经典皮肤', 1400999
    )
    checks = {
        (kind, skin.resource_id): _skin_asset_check(
            kind,
            skin.resource_id,
            available=False,
        )
        for kind in skin_image_resolution.PET_IMAGE_ASSET_KINDS
    }

    rows = skin_image_resolution.resolve_classic_skin_image_resources(
        (skin,),
        (),
        checks,
        {},
    )

    assert rows == [
        skin_image_resolution.SkinImageResolution(
            skin_id=999,
            head_resource_id=0,
            body_resource_id=0,
            head_resolution='unresolved',
            body_resolution='unresolved',
            source_pet_id=None,
        )
    ]


def test_resolve_classic_skin_images_keeps_transient_failures_unverified() -> None:
    skin = skin_image_resolution.ClassicSkinImageSource(538, '天道魂帝', 1400538)
    source = skin_image_resolution.PetImageSource(3382, '天道魂帝', 3382)
    checks = {
        ('head', 1400538): _skin_asset_check(
            'head',
            1400538,
            available=False,
            status=0,
            error='timed out',
        ),
        ('body', 1400538): _skin_asset_check('body', 1400538, available=True),
        ('head', 3382): _skin_asset_check('head', 3382, available=True),
        ('body', 3382): _skin_asset_check('body', 3382, available=True),
    }

    rows = skin_image_resolution.resolve_classic_skin_image_resources(
        (skin,),
        (source,),
        checks,
        {},
    )

    assert rows == [
        skin_image_resolution.SkinImageResolution(
            skin_id=538,
            head_resource_id=0,
            body_resource_id=1400538,
            head_resolution='unverified',
            body_resolution='direct_skin',
            source_pet_id=None,
        )
    ]


def test_verify_pet_image_asset_retries_transient_failures(monkeypatch) -> None:
    attempts = iter(
        [
            _skin_asset_check(
                'body',
                1400538,
                available=False,
                status=0,
                error='timed out',
            ),
            _skin_asset_check('body', 1400538, available=True),
        ]
    )
    probe = skin_image_asset_probe.SkinImageAssetProbe(
        skin_image_asset_probe.SkinImageAssetProbeConfig(
            base_url='https://example.invalid/',
            timeout_seconds=1,
            retry_attempts=2,
            retry_backoff_seconds=0,
            workers=1,
        ),
        request=builder.BUILD_HTTP.request,
        logger=builder.logger,
    )
    monkeypatch.setattr(probe, '_probe_range', lambda *args, **kwargs: next(attempts))

    check = probe.verify_asset('body', 1400538)

    assert check.available
    assert check.status == 200


def test_parse_special_skill_shop_reads_current_skill_scroll_prices() -> None:
    payload = {
        'item': [
            {
                'coin_id': 1726992,
                'id': 3,
                'item_id': 1727009,
                'item_name': '魔灵密卷',
                'limit': 1,
                'price': 400,
            },
            {
                'coin_id': 1726992,
                'id': 44,
                'item_id': 1728277,
                'item_name': '咎者焚卷',
                'limit': 1,
                'price': 400,
            },
        ]
    }

    prices = item_exchange_sources.parse_special_skill_shop(
        json.dumps(payload, ensure_ascii=False).encode('utf-8'),
        source_key=builder.SPECIAL_SKILL_SHOP_SOURCE_KEY,
        source_name=builder.SPECIAL_SKILL_SHOP_SOURCE_NAME,
    )

    assert prices == [
        item_exchange_sources.ItemExchangePrice(
            source_key='special_skill_shop',
            source_name='微光秘境',
            source_entry_id=3,
            item_id=1727009,
            item_name='魔灵密卷',
            item_quantity=1,
            currency_item_id=1726992,
            amount=400,
            purchase_limit=1,
            start_time=0,
            end_time=0,
        ),
        item_exchange_sources.ItemExchangePrice(
            source_key='special_skill_shop',
            source_name='微光秘境',
            source_entry_id=44,
            item_id=1728277,
            item_name='咎者焚卷',
            item_quantity=1,
            currency_item_id=1726992,
            amount=400,
            purchase_limit=1,
            start_time=0,
            end_time=0,
        ),
    ]


def test_parse_effect_descriptions_keeps_named_entries() -> None:
    payload = {
        'root': {
            'item': [
                {
                    'id': 544,
                    'kind': 1,
                    'kinddes': '冥妖之悼',
                    'desc': '效果说明',
                },
                {'id': 545, 'kind': 1, 'kinddes': '', 'desc': '忽略'},
                {'id': 546, 'kind': 1, 'kinddes': '无说明', 'desc': ''},
                {
                    'id': 547,
                    'kind': 4,
                    'kinddes': '己方',
                    'desc': '不是专属效果',
                },
            ]
        }
    }

    rows = effect_metadata_sources.parse_effect_descriptions(
        json.dumps(payload, ensure_ascii=False).encode('utf-8')
    )

    assert rows == [
        effect_metadata_sources.EffectDescription(
            effect_id=544,
            name='冥妖之悼',
            description='效果说明',
        )
    ]


def test_parse_special_effect_statuses_keeps_display_name_aliases() -> None:
    payload = {
        'config': {
            'item': [
                {
                    'id': 147,
                    'dec': '旧日之晷',
                    'des': '状态说明',
                    'tips': '旧日之晷',
                    'show_monster': 4125,
                },
                {
                    'id': 148,
                    'dec': '宙变之殢',
                    'des': '另一条说明',
                    'tips': '时晷',
                    'show_monster': 0,
                },
                {'id': 0, 'dec': '忽略'},
            ]
        }
    }

    rows = effect_metadata_sources.parse_special_effect_statuses(
        json.dumps(payload, ensure_ascii=False).encode('utf-8')
    )

    assert rows == [
        effect_metadata_sources.SpecialEffectStatus(
            status_id=147,
            name='旧日之晷',
            description='状态说明',
            show_monster_id=4125,
        ),
        effect_metadata_sources.SpecialEffectStatus(
            status_id=148,
            name='宙变之殢',
            description='另一条说明',
            show_monster_id=0,
        ),
        effect_metadata_sources.SpecialEffectStatus(
            status_id=148,
            name='时晷',
            description='另一条说明',
            show_monster_id=0,
        ),
    ]


def test_parse_autocard_season_effects() -> None:
    def text(value: str) -> bytes:
        encoded = value.encode()
        return struct.pack('<H', len(encoded)) + encoded

    payload = b''.join(
        (
            b'\x01',
            struct.pack('<i', 1),
            text('50044'),
            text('50044'),
            text('3_1'),
            struct.pack('<iii', 1, 3, 2),
            text('霁天'),
            text('每个商店阶段前3次购买价格减少1枚金币'),
            struct.pack('<iiiii', 10, 5, 0, 1, 1),
        )
    )

    assert config_package_sources.parse_autocard_season_effects(payload) == [
        config_package_sources.AutocardSeasonEffect(
            effect_id=10,
            sanctuary_id=2,
            name='霁天',
            description='每个商店阶段前3次购买价格减少1枚金币',
            buff_id='50044',
            buff_param='3_1',
            count_buff_id='50044',
            count_type=1,
            count_num=3,
            unlock_round=5,
            pic_id=0,
            season_id=1,
            stage=1,
        )
    ]


def _test_png(
    *,
    alpha: int = 255,
    size: tuple[int, int] = (2, 2),
) -> bytes:
    output = io.BytesIO()
    Image.new('RGBA', size, (10, 20, 30, alpha)).save(output, format='PNG')
    return output.getvalue()


def _manifest_text(value: str) -> bytes:
    encoded = value.encode('utf-8')
    return struct.pack('<H', len(encoded)) + encoded


def _package_manifest_bytes(
    *,
    assets: list[tuple[str, int]],
    bundles: list[tuple[str, str, int]],
) -> bytes:
    parts = [
        struct.pack('<I', 1),
        _manifest_text('test-package'),
        b'\x00\x00\x00',
        struct.pack('<i', 0),
        _manifest_text(''),
        _manifest_text(''),
        struct.pack('<i', len(assets)),
    ]
    for asset_path, bundle_index in assets:
        parts.extend(
            [
                _manifest_text(asset_path),
                struct.pack('<i', bundle_index),
                struct.pack('<H', 0),
            ]
        )
    parts.append(struct.pack('<i', len(bundles)))
    for name, file_hash, file_size in bundles:
        parts.extend(
            [
                _manifest_text(name),
                struct.pack('<I', 0),
                _manifest_text(file_hash),
                _manifest_text(''),
                struct.pack('<q', file_size),
                b'\x00',
                struct.pack('<b', 0),
                struct.pack('<H', 0),
            ]
        )
    return b''.join(parts)


def test_parse_package_manifest_maps_assets_to_bundles() -> None:
    manifest = config_package_sources.parse_package_manifest(
        _package_manifest_bytes(
            assets=[
                ('Assets/Art/Ui/assets/effectIcon/307.png', 1),
                ('Assets/Other/example.txt', 0),
            ],
            bundles=[
                ('misc', 'misc-hash', 12),
                ('art_ui_effecticon', 'effect-hash', 34),
            ],
        )
    )

    assert manifest.assets['Assets/Art/Ui/assets/effectIcon/307.png'] == (
        config_package_sources.BundleInfo('art_ui_effecticon', 'effect-hash', 34)
    )


def test_load_unity_effect_icon_png_assets_uses_default_package_manifest(
    monkeypatch,
) -> None:
    png_data = _test_png()
    manifest_data = _package_manifest_bytes(
        assets=[('Assets/Art/Ui/assets/effectIcon/307.png', 0)],
        bundles=[('art_ui_effecticon', 'effect-hash', 456)],
    )
    downloaded_urls: list[str] = []

    def fake_download(url: str) -> bytes:
        downloaded_urls.append(url)
        if 'PackageManifest_DefaultPackage.version' in url:
            return b'20260807162107'
        if 'PackageManifest_DefaultPackage_20260807162107.bytes' in url:
            return manifest_data
        if url == 'https://game.test/DefaultPackage/effect-hash':
            return b'bundle-data'
        raise AssertionError(url)

    monkeypatch.setattr(
        builder,
        'DEFAULT_PACKAGE_BASE_URL',
        'https://game.test/DefaultPackage/',
    )
    monkeypatch.setattr(builder.BUILD_HTTP, 'download_bytes', fake_download)
    monkeypatch.setattr(
        effect_icon_unity_sources,
        'extract_unity_effect_icon_pngs',
        lambda data, icon_ids, **_kwargs: ({307: png_data}, {}),
    )

    load = effect_icon_unity_sources.load_unity_effect_icon_png_assets(
        {206, 307},
        config=builder._effect_icon_source_config(),
        fetch_package_manifest=_fetch_package_manifest,
        download_bytes=builder.BUILD_HTTP.download_bytes,
    )

    assert load.package_version == '20260807162107'
    assert load.total_manifest_icon_count == 1
    assert load.png_renders[307].data == png_data
    assert load.asset_checks[307].url == (
        'https://game.test/DefaultPackage/effect-hash'
        '#Assets/Art/Ui/assets/effectIcon/307.png'
    )
    assert load.png_renders[206].available is False
    assert load.asset_checks[206].status == 404
    assert downloaded_urls[-1] == 'https://game.test/DefaultPackage/effect-hash'


def test_resolve_effect_icon_png_assets_prefers_unity_and_falls_back_to_swf(
    monkeypatch,
) -> None:
    assert builder.EFFECT_ICON_PREFER_FLASH is False
    unity_png = _test_png()
    fallback_png = _test_png(size=(3, 3))
    unity_check = effect_icon_build_types.EffectIconAssetCheck(
        icon_id=307,
        url='https://game.test/effect-hash#Assets/Art/Ui/assets/effectIcon/307.png',
        available=True,
        status=200,
        content_type='image/png',
        content_length=len(unity_png),
        error='',
    )
    missing_check = effect_icon_build_types.EffectIconAssetCheck(
        icon_id=206,
        url='https://game.test/DefaultPackage/#Assets/Art/Ui/assets/effectIcon/206.png',
        available=False,
        status=404,
        content_type='',
        content_length=None,
        error='Unity DefaultPackage effectIcon PNG missing',
    )
    fallback_check = effect_icon_build_types.EffectIconAssetCheck(
        icon_id=206,
        url='https://seer.61.com/resource/effectIcon/206.swf',
        available=True,
        status=200,
        content_type='application/x-shockwave-flash',
        content_length=123,
        error='',
    )
    fallback_inputs: list[set[int]] = []

    monkeypatch.setattr(
        effect_icon_build,
        'load_unity_effect_icon_png_assets',
        lambda icon_ids, **_kwargs: effect_icon_unity_sources.UnityEffectIconPngLoad(
            package_version='20260807162107',
            total_manifest_icon_count=2109,
            sources={},
            asset_checks={206: missing_check, 307: unity_check},
            png_renders={
                206: effect_icon_build_types.EffectIconPngRender(
                    206,
                    False,
                    '',
                    None,
                    None,
                    'Unity DefaultPackage effectIcon PNG missing',
                ),
                307: effect_icon_build_types.EffectIconPngRender(
                    307,
                    True,
                    'image/png',
                    len(unity_png),
                    unity_png,
                    '',
                ),
            },
        ),
    )
    monkeypatch.setattr(
        effect_icon_build,
        'verify_effect_icon_assets',
        lambda icon_ids, **_kwargs: (
            fallback_inputs.append(set(icon_ids)) or {206: fallback_check}
        ),
    )
    monkeypatch.setattr(
        effect_icon_build,
        'render_effect_icon_png_assets',
        lambda checks, **_kwargs: {
            206: effect_icon_build_types.EffectIconPngRender(
                206,
                True,
                'image/png',
                len(fallback_png),
                fallback_png,
                '',
            )
        },
    )

    resolution = effect_icon_build.resolve_effect_icon_png_assets(
        {206, 307},
        config=builder._effect_icon_source_config(),
        fetch_package_manifest=_fetch_package_manifest,
        download_bytes=builder.BUILD_HTTP.download_bytes,
        request=builder.BUILD_HTTP.request,
        open_url=builder.urlopen,
        logger=builder.logger,
    )

    assert fallback_inputs == [{206}]
    assert resolution.png_renders[307].data == unity_png
    assert resolution.png_renders[206].data == fallback_png
    assert resolution.asset_checks[307] == unity_check
    assert resolution.asset_checks[206] == fallback_check
    assert resolution.unity_missing_icon_ids == (206,)
    assert resolution.preferred_source == 'unity'


def test_resolve_effect_icon_png_assets_prefers_flash_and_falls_back_to_unity(
    monkeypatch,
) -> None:
    monkeypatch.setattr(builder, 'EFFECT_ICON_PREFER_FLASH', True)
    flash_png = _test_png(size=(3, 3))
    unity_png = _test_png()
    flash_check = effect_icon_build_types.EffectIconAssetCheck(
        icon_id=307,
        url='https://seer.61.com/resource/effectIcon/307.swf',
        available=True,
        status=200,
        content_type='application/x-shockwave-flash',
        content_length=123,
        error='',
    )
    missing_flash_check = effect_icon_build_types.EffectIconAssetCheck(
        icon_id=206,
        url='https://seer.61.com/resource/effectIcon/206.swf',
        available=False,
        status=404,
        content_type='text/html',
        content_length=None,
        error='',
    )
    unity_check = effect_icon_build_types.EffectIconAssetCheck(
        icon_id=206,
        url='https://game.test/effect-hash#Assets/Art/Ui/assets/effectIcon/206.png',
        available=True,
        status=200,
        content_type='image/png',
        content_length=len(unity_png),
        error='',
    )
    swf_inputs: list[set[int]] = []
    unity_inputs: list[set[int]] = []

    monkeypatch.setattr(
        effect_icon_build,
        'load_unity_effect_icon_png_assets',
        lambda icon_ids, **_kwargs: (
            unity_inputs.append(set(icon_ids))
            or effect_icon_unity_sources.UnityEffectIconPngLoad(
                package_version='20260807162107',
                total_manifest_icon_count=2109,
                sources={},
                asset_checks={206: unity_check},
                png_renders={
                    206: effect_icon_build_types.EffectIconPngRender(
                        206,
                        True,
                        'image/png',
                        len(unity_png),
                        unity_png,
                        '',
                    ),
                },
            )
        ),
    )
    monkeypatch.setattr(
        effect_icon_build,
        'verify_effect_icon_assets',
        lambda icon_ids, **_kwargs: (
            swf_inputs.append(set(icon_ids))
            or {206: missing_flash_check, 307: flash_check}
        ),
    )
    monkeypatch.setattr(
        effect_icon_build,
        'render_effect_icon_png_assets',
        lambda checks, **_kwargs: {
            206: effect_icon_build_types.EffectIconPngRender(
                206,
                False,
                '',
                None,
                None,
                'SWF asset unavailable',
            ),
            307: effect_icon_build_types.EffectIconPngRender(
                307,
                True,
                'image/png',
                len(flash_png),
                flash_png,
                '',
            ),
        },
    )

    resolution = effect_icon_build.resolve_effect_icon_png_assets(
        {206, 307},
        config=builder._effect_icon_source_config(),
        fetch_package_manifest=_fetch_package_manifest,
        download_bytes=builder.BUILD_HTTP.download_bytes,
        request=builder.BUILD_HTTP.request,
        open_url=builder.urlopen,
        logger=builder.logger,
    )

    assert swf_inputs == [{206, 307}]
    assert unity_inputs == [{206}]
    assert resolution.png_renders[307].data == flash_png
    assert resolution.png_renders[206].data == unity_png
    assert resolution.asset_checks[307] == flash_check
    assert resolution.asset_checks[206] == unity_check
    assert resolution.preferred_source == 'flash'
    assert resolution.flash_missing_icon_ids == (206,)
    assert resolution.unity_fallback_icon_count == 1


def test_render_effect_icon_png_uses_cached_png(monkeypatch, tmp_path) -> None:
    png_data = _test_png()
    check = effect_icon_build_types.EffectIconAssetCheck(
        icon_id=1644,
        url='https://example.test/1644.swf',
        available=True,
        status=200,
        content_type='application/x-shockwave-flash',
        content_length=123,
        error='',
    )
    config = _effect_icon_render_config(cache_dir=tmp_path)
    effect_icon_png_renderer.save_effect_icon_png_cache(
        1644,
        png_data,
        check,
        config=config,
        logger=builder.logger,
    )

    render = effect_icon_png_renderer._render_effect_icon_png(
        1644,
        check,
        config=config,
        download_effect_icon=lambda _check: (_ for _ in ()).throw(AssertionError),
        logger=builder.logger,
    )

    assert render.available is True
    assert render.data == png_data


def test_render_effect_icon_assets_uses_complete_cache_without_ffdec(
    tmp_path, caplog
) -> None:
    caplog.set_level('INFO')
    check = effect_icon_build_types.EffectIconAssetCheck(
        icon_id=1644,
        url='https://example.test/1644.swf',
        available=True,
        status=200,
        content_type='application/x-shockwave-flash',
        content_length=123,
        error='',
    )
    config = _effect_icon_render_config(
        cache_dir=tmp_path,
        java_command='missing-java',
        ffdec_jar=tmp_path / 'missing-ffdec.jar',
    )
    effect_icon_png_renderer.save_effect_icon_png_cache(
        1644,
        _test_png(),
        check,
        config=config,
        logger=builder.logger,
    )

    renders = effect_icon_png_renderer.render_effect_icon_png_assets(
        {1644: check},
        config=config,
        download_effect_icon=lambda _check: (_ for _ in ()).throw(AssertionError),
        logger=builder.logger,
    )

    assert renders[1644].available is True
    assert renders[1644].data == _test_png()
    assert 'Resolving official effect icon PNGs: 1 unique icons' in caplog.text
    assert 'Resolved official effect icon PNGs: 1/1 available' in caplog.text
    assert 'Rendering official effect icon PNGs' not in caplog.text


def test_parallel_effect_icon_renders_return_in_icon_id_order(
    monkeypatch,
    tmp_path,
) -> None:
    first_started = Event()
    release_first = Event()
    calls: list[int] = []

    def render(icon_id, _check, **_kwargs):
        calls.append(icon_id)
        if icon_id == 1:
            first_started.set()
            assert release_first.wait(1)
        else:
            assert first_started.wait(1)
            release_first.set()
        return effect_icon_build_types.EffectIconPngRender(
            icon_id=icon_id,
            available=True,
            content_type='image/png',
            content_length=3,
            data=b'png',
            error='',
        )

    monkeypatch.setattr(effect_icon_png_renderer, '_render_effect_icon_png', render)
    checks = {
        icon_id: effect_icon_build_types.EffectIconAssetCheck(
            icon_id=icon_id,
            url=f'https://example.test/{icon_id}.swf',
            available=True,
            status=200,
            content_type='application/x-shockwave-flash',
            content_length=123,
            error='',
        )
        for icon_id in (2, 1)
    }

    renders = effect_icon_png_renderer.render_effect_icon_png_assets(
        checks,
        config=_effect_icon_render_config(cache_dir=tmp_path, render_workers=2),
        download_effect_icon=lambda _check: b'unused',
        logger=builder.logger,
    )

    assert sorted(calls) == [1, 2]
    assert tuple(renders) == (1, 2)


@pytest.mark.parametrize('missing_tool', ['java', 'jar'])
@pytest.mark.parametrize('unity_available', [False, True])
def test_missing_renderer_keeps_cached_flash_and_falls_back_per_icon(
    monkeypatch, tmp_path, missing_tool, unity_available
) -> None:
    cached_id, missing_id = 1644, 1645
    png = _test_png()
    check = effect_icon_build_types.EffectIconAssetCheck(
        cached_id,
        'https://example.test/cached.swf',
        True,
        200,
        'application/x-shockwave-flash',
        123,
        '',
    )
    missing_check = replace(
        check, icon_id=missing_id, url='https://example.test/missing.swf'
    )
    config = _effect_icon_render_config(
        cache_dir=tmp_path,
        prefer_flash=True,
        png_require_cached=True,
        ffdec_jar=tmp_path / 'missing.jar',
    )
    monkeypatch.setattr(
        effect_icon_png_renderer.shutil,
        'which',
        lambda _command: None if missing_tool == 'java' else 'java',
    )
    effect_icon_png_renderer.save_effect_icon_png_cache(
        cached_id,
        png,
        check,
        config=config,
        logger=builder.logger,
    )
    monkeypatch.setattr(
        effect_icon_build,
        'verify_effect_icon_assets',
        lambda *_args, **_kwargs: {cached_id: check, missing_id: missing_check},
    )
    unity_requests = []

    def unity_load(ids, **kwargs):
        unity_requests.append(ids)
        assert ids == {missing_id}
        return effect_icon_build_types.UnityEffectIconPngLoad(
            package_version='test',
            total_manifest_icon_count=1,
            sources={},
            asset_checks={missing_id: replace(missing_check, content_type='image/png')},
            png_renders={
                missing_id: effect_icon_build_types.EffectIconPngRender(
                    missing_id,
                    unity_available,
                    'image/png',
                    len(png) if unity_available else None,
                    png if unity_available else None,
                    '' if unity_available else 'missing',
                )
            },
        )

    monkeypatch.setattr(
        effect_icon_build, 'load_unity_effect_icon_png_assets', unity_load
    )

    def resolve():
        return effect_icon_build.resolve_effect_icon_png_assets(
            {cached_id, missing_id},
            config=config,
            fetch_package_manifest=lambda *_: (_ for _ in ()).throw(AssertionError),
            download_bytes=lambda *_: (_ for _ in ()).throw(AssertionError),
            request=builder.BUILD_HTTP.request,
            open_url=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError),
            logger=builder.logger,
        )

    if unity_available:
        result = resolve()
        assert result.png_renders[cached_id].data == png
        assert result.asset_checks[cached_id] == check
        assert result.flash_png_available_count == 1
        assert result.unity_fallback_icon_count == 1
    else:
        with pytest.raises(ValueError, match='Missing resolved effect icon PNGs: 1645'):
            resolve()
    assert unity_requests == [{missing_id}]


def test_effect_icon_cache_is_invalidated_when_source_size_changes(
    monkeypatch,
    tmp_path,
) -> None:
    icon_id = 1644
    check = effect_icon_build_types.EffectIconAssetCheck(
        icon_id=icon_id,
        url='https://example.test/1644.swf',
        available=True,
        status=200,
        content_type='application/x-shockwave-flash',
        content_length=123,
        error='',
    )
    changed_check = builder.replace(check, content_length=124)
    config = _effect_icon_render_config(cache_dir=tmp_path)
    effect_icon_png_renderer.save_effect_icon_png_cache(
        icon_id,
        _test_png(),
        check,
        config=config,
        logger=builder.logger,
    )

    assert (
        effect_icon_png_renderer.load_effect_icon_png_cache(
            icon_id, check, config=config, logger=builder.logger
        )
        is not None
    )
    assert (
        effect_icon_png_renderer.load_effect_icon_png_cache(
            icon_id, changed_check, config=config, logger=builder.logger
        )
        is None
    )


def test_effect_icon_cache_rejects_oversized_png() -> None:
    oversized_png = _test_png(
        size=(builder.EFFECT_ICON_PNG_MAX_DIMENSION + 1, 1),
    )

    with pytest.raises(ValueError, match='dimensions exceed'):
        effect_icon_png_renderer.visible_png_pixel_count(
            oversized_png,
            config=builder.EFFECT_ICON_BUILD_CONFIG,
        )


def test_seed_effect_icon_cache_uses_matching_renderer_version(
    monkeypatch,
    tmp_path,
) -> None:
    icon_id = 1644
    database_path = tmp_path / 'previous.sqlite'
    with sqlite3.connect(database_path) as connection:
        connection.execute('CREATE TABLE seerapi_metadata (key TEXT, value TEXT)')
        connection.execute(
            'INSERT INTO seerapi_metadata VALUES (?, ?)',
            ('effect_icon_png_cache_version', builder.EFFECT_ICON_PNG_CACHE_VERSION),
        )
        connection.execute(
            """
            CREATE TABLE soulmark_icon (
                icon_id INTEGER,
                icon_png BLOB,
                icon_png_available INTEGER,
                icon_asset_content_length INTEGER,
                icon_asset_content_type TEXT
            )
            """
        )
        connection.execute(
            'INSERT INTO soulmark_icon VALUES (?, ?, 1, 123, ?)',
            (icon_id, _test_png(), 'application/x-shockwave-flash'),
        )
    monkeypatch.setattr(
        builder,
        'EFFECT_ICON_BUILD_CONFIG',
        _effect_icon_render_config(cache_dir=tmp_path / 'cache'),
    )
    check = effect_icon_build_types.EffectIconAssetCheck(
        icon_id=icon_id,
        url='https://example.test/1644.swf',
        available=True,
        status=200,
        content_type='application/x-shockwave-flash',
        content_length=123,
        error='',
    )

    assert _seed_effect_icon_cache(database_path) == 1
    assert (
        effect_icon_png_renderer.load_effect_icon_png_cache(
            icon_id,
            check,
            config=builder.EFFECT_ICON_BUILD_CONFIG,
            logger=builder.logger,
        )
        == _test_png()
    )


def test_seed_effect_icon_cache_rejects_previous_renderer_version(
    monkeypatch,
    tmp_path,
) -> None:
    database_path = tmp_path / 'previous.sqlite'
    with sqlite3.connect(database_path) as connection:
        connection.execute('CREATE TABLE seerapi_metadata (key TEXT, value TEXT)')
        connection.execute(
            'INSERT INTO seerapi_metadata VALUES (?, ?)',
            ('effect_icon_png_cache_version', 'effect-icon-png-legacy'),
        )
        connection.execute(
            """
            CREATE TABLE soulmark_icon (
                icon_id INTEGER,
                icon_png BLOB,
                icon_png_available INTEGER,
                icon_asset_content_length INTEGER,
                icon_asset_content_type TEXT
            )
            """
        )
        connection.execute(
            'INSERT INTO soulmark_icon VALUES (1644, ?, 1, 123, ?)',
            (_test_png(), 'application/x-shockwave-flash'),
        )
    monkeypatch.setattr(
        builder,
        'EFFECT_ICON_BUILD_CONFIG',
        _effect_icon_render_config(cache_dir=tmp_path / 'cache'),
    )

    assert _seed_effect_icon_cache(database_path) == 0
    assert not effect_icon_png_renderer.effect_icon_png_cache_path(
        1644,
        config=builder.EFFECT_ICON_BUILD_CONFIG,
    ).exists()


def test_render_effect_icon_cache_shard_consumes_planned_id_snapshot(
    monkeypatch,
    tmp_path,
) -> None:
    captured: dict[str, list[int]] = {}
    monkeypatch.setattr(
        builder,
        'load_flash_effect_icon_png_assets',
        lambda icon_ids, **_kwargs: (
            captured.setdefault('render_ids', sorted(icon_ids))
            and (
                {icon_id: object() for icon_id in icon_ids},
                {
                    icon_id: effect_icon_build_types.EffectIconPngRender(
                        icon_id,
                        True,
                        'image/png',
                        1,
                        b'x',
                        '',
                    )
                    for icon_id in icon_ids
                },
            )
        ),
    )
    icon_count, available_count = (
        effect_icon_cache_cli.render_effect_icon_png_cache_shard(
            shard_index=0,
            shard_count=2,
            output_dir=tmp_path,
            shard_icon_ids=[100, 102],
            repair_icon_ids=[102],
            render_icons=lambda icon_ids: builder.load_flash_effect_icon_png_assets(
                icon_ids,
                config=builder.EFFECT_ICON_BUILD_CONFIG,
                request=builder.BUILD_HTTP.request,
                open_url=builder.urlopen,
                logger=builder.logger,
                require_any=False,
            )[1],
            export_cache=lambda icon_ids, _output_dir: _capture_exported_icon_ids(
                captured, icon_ids
            ),
            logger=builder.logger,
        )
    )

    assert captured['icon_ids'] == [100, 102]
    assert captured['render_ids'] == [102]
    assert (icon_count, available_count) == (1, 1)


def test_plan_effect_icon_cache_shard_only_repairs_retryable_missing_pngs(
    tmp_path,
) -> None:
    available_check = effect_icon_build_types.EffectIconAssetCheck(
        100,
        'https://example/100.swf',
        True,
        200,
        'application/x-shockwave-flash',
        10,
        '',
    )
    missing_check = effect_icon_build_types.EffectIconAssetCheck(
        101, 'https://example/101.swf', False, 404, 'text/html', None, ''
    )
    transient_check = effect_icon_build_types.EffectIconAssetCheck(
        102, 'https://example/102.swf', False, 0, '', None, 'timed out'
    )
    uncached_check = effect_icon_build_types.EffectIconAssetCheck(
        103,
        'https://example/103.swf',
        True,
        200,
        'application/x-shockwave-flash',
        10,
        '',
    )
    cached_render = effect_icon_build_types.EffectIconPngRender(
        100, True, 'image/png', 1, b'x', ''
    )

    def unavailable_render(icon_id: int) -> effect_icon_build_types.EffectIconPngRender:
        return effect_icon_build_types.EffectIconPngRender(
            icon_id, False, '', None, None, 'not cached'
        )

    exported: list[int] = []

    plan = effect_icon_cache_cli.plan_effect_icon_png_cache_shard(
        shard_index=0,
        shard_count=1,
        output_dir=tmp_path,
        fetch_icon_ids=lambda: {100, 101, 102, 103},
        find_fallback_icon_ids=lambda icon_ids: sorted(icon_ids),
        inspect_icons=lambda _icon_ids: (
            {
                100: available_check,
                101: missing_check,
                102: transient_check,
                103: uncached_check,
            },
            {
                100: cached_render,
                101: unavailable_render(101),
                102: unavailable_render(102),
                103: unavailable_render(103),
            },
        ),
        export_cache=lambda icon_ids, _output_dir: exported.extend(icon_ids) or 1,
        logger=builder.logger,
    )

    assert plan.icon_ids == (100, 101, 102, 103)
    assert plan.cached_count == 1
    assert plan.repair_icon_ids == (102, 103)
    assert plan.needs_render is True
    assert exported == [100, 101, 102, 103]
    plan_output = tmp_path / 'github-output'
    effect_icon_cache_cli.write_effect_icon_cache_shard_plan(plan, plan_output)
    assert plan_output.read_text(encoding='utf-8').splitlines() == [
        'needs_render=true',
        'icon_count=4',
        'cached_count=1',
        'repair_count=2',
        'shard_icon_ids=100,101,102,103',
        'repair_icon_ids=102,103',
    ]


def test_flash_preferred_cache_partition_renders_all_icons(monkeypatch) -> None:
    monkeypatch.setattr(builder, 'EFFECT_ICON_PREFER_FLASH', True)

    assert effect_icon_unity_sources.unity_effect_icon_swf_fallback_icon_ids(
        {100, 101},
        config=builder._effect_icon_source_config(),
        fetch_package_manifest=lambda *_args: (_ for _ in ()).throw(AssertionError),
        logger=builder.logger,
    ) == [100, 101]


def test_unity_preferred_cache_partition_only_renders_missing_unity_icons(
    monkeypatch,
) -> None:
    monkeypatch.setattr(builder, 'EFFECT_ICON_PREFER_FLASH', False)
    manifest = config_package_sources.parse_package_manifest(
        _package_manifest_bytes(
            assets=[('Assets/Art/Ui/assets/effectIcon/100.png', 0)],
            bundles=[('art_ui_effecticon', 'effect-hash', 34)],
        )
    )

    assert effect_icon_unity_sources.unity_effect_icon_swf_fallback_icon_ids(
        {100, 101},
        config=builder._effect_icon_source_config(),
        fetch_package_manifest=lambda *_args: ('20260925120000', manifest),
        logger=builder.logger,
    ) == [101]


def test_render_effect_icon_png_assets_skips_ffdec_for_confirmed_missing(
    monkeypatch,
) -> None:
    check = effect_icon_build_types.EffectIconAssetCheck(
        icon_id=206,
        url='https://seer.61.com/resource/effectIcon/206.swf',
        available=False,
        status=404,
        content_type='text/html',
        content_length=None,
        error='',
    )
    monkeypatch.setattr(
        effect_icon_png_renderer.shutil,
        'which',
        lambda _command: (_ for _ in ()).throw(AssertionError),
    )

    renders = effect_icon_png_renderer.render_effect_icon_png_assets(
        {206: check},
        config=builder.EFFECT_ICON_BUILD_CONFIG,
        download_effect_icon=lambda _check: (_ for _ in ()).throw(AssertionError),
        logger=builder.logger,
        require_any=False,
    )

    assert renders[206] == effect_icon_build_types.EffectIconPngRender(
        icon_id=206,
        available=False,
        content_type='',
        content_length=None,
        data=None,
        error='SWF asset unavailable',
    )


def test_require_cached_effect_icons_rejects_missing_pngs(monkeypatch) -> None:
    check = effect_icon_build_types.EffectIconAssetCheck(
        icon_id=1644,
        url='https://example.test/1644.swf',
        available=True,
        status=200,
        content_type='application/x-shockwave-flash',
        content_length=123,
        error='',
    )
    config = _effect_icon_render_config(
        png_render_enabled=False,
        png_require_cached=True,
    )

    with pytest.raises(ValueError, match='Missing pre-rendered effect icon PNGs: 1644'):
        effect_icon_png_renderer.render_effect_icon_png_assets(
            {1644: check},
            config=config,
            download_effect_icon=lambda _check: (_ for _ in ()).throw(AssertionError),
            logger=builder.logger,
        )


def test_effect_icon_render_defaults_allow_complex_swf_exports() -> None:
    assert builder.EFFECT_ICON_PNG_RENDER_WORKERS == 2
    assert builder.EFFECT_ICON_PNG_COMPOSITE_RENDER_TIMEOUT_SECONDS >= 45
    assert builder.EFFECT_ICON_PNG_SHAPE_RENDER_TIMEOUT_SECONDS >= 30


def test_collect_soulmark_icon_render_issues_keeps_pet_level_context() -> None:
    unavailable_asset = effect_icon_build_types.EffectIconAssetCheck(
        icon_id=206,
        url='https://example.test/206.swf',
        available=False,
        status=404,
        content_type='text/html',
        content_length=123,
        error='HTTP Error 404: Not Found',
    )
    render_failure_asset = effect_icon_build_types.EffectIconAssetCheck(
        icon_id=509,
        url='https://example.test/509.swf',
        available=True,
        status=200,
        content_type='application/x-shockwave-flash',
        content_length=456,
        error='',
    )
    successful_asset = effect_icon_build_types.EffectIconAssetCheck(
        icon_id=1644,
        url='https://example.test/1644.swf',
        available=True,
        status=200,
        content_type='application/x-shockwave-flash',
        content_length=789,
        error='',
    )
    issues = release_publication._collect_soulmark_icon_render_issues(
        [(220, 461, 0, 206), (527, 3142, 791, 509), (1, 2, 3, 1644)],
        {206: unavailable_asset, 509: render_failure_asset, 1644: successful_asset},
        {
            206: effect_icon_build_types.EffectIconPngRender(
                206, False, '', None, None, 'asset unavailable'
            ),
            509: effect_icon_build_types.EffectIconPngRender(
                509, False, '', None, None, 'FFDec timed out'
            ),
            1644: effect_icon_build_types.EffectIconPngRender(
                1644, True, 'image/png', 10, _test_png(), ''
            ),
        },
        {461: '阿尔克', 3142: '王·雷伊'},
    )

    assert issues == [
        effect_icon_build_types.SoulmarkIconRenderIssue(
            icon_id=206,
            soulmark_id=220,
            pet_id=461,
            pet_name='阿尔克',
            effect_id=0,
            icon_asset_status=404,
            icon_asset_error='HTTP Error 404: Not Found',
            icon_png_error='asset unavailable',
        ),
        effect_icon_build_types.SoulmarkIconRenderIssue(
            icon_id=509,
            soulmark_id=527,
            pet_id=3142,
            pet_name='王·雷伊',
            effect_id=791,
            icon_asset_status=200,
            icon_asset_error='',
            icon_png_error='FFDec timed out',
        ),
    ]


def test_effect_icon_render_asset_manifest_is_hashed_and_release_versioned(
    tmp_path: Path,
) -> None:
    result = render_asset_manifest_build.build_render_asset_manifest(
        render_asset_manifest_build.RemoteAssetManifestBuild(
            pet_info_entries=(),
            new_content_standard_entries=(),
            pet_info_scope_complete=False,
            new_content_standard_scope_complete=False,
            skin_body_entries=(),
            skin_body_scope_complete=False,
        ),
        {18: b'png', 19: None},
        {},
        release_revision='config-20260806',
        effect_icon_source_version=builder.EFFECT_ICON_PNG_CACHE_VERSION,
        config=builder.RENDER_ASSET_MANIFEST_CONFIG,
    )
    entries = result.entries

    assert [(entry.asset_kind, entry.asset_key) for entry in entries] == [
        ('soulmark_icon_png', '18'),
        ('soulmark_icon_png', '19'),
    ]
    assert (
        entries[0].sha256
        == '8f8cbb7dcf46e0bc7d53265749a6c17d116093a6ba95e442764060c76fd4a86c'
    )
    assert entries[0].release_revision == 'config-20260806'
    assert entries[0].available is True
    assert entries[1].sha256 == ''
    assert entries[1].available is False
    assert render_asset_manifest_build.render_asset_manifest_revision(entries) == (
        render_asset_manifest_build.render_asset_manifest_revision(
            tuple(reversed(entries))
        )
    )
    changed_source = (
        render_asset_manifest_build.RenderAssetManifestEntry(
            asset_kind=entries[0].asset_kind,
            asset_key=entries[0].asset_key,
            sha256=entries[0].sha256,
            release_revision=entries[0].release_revision,
            available=entries[0].available,
            source='different-build-source',
        ),
        entries[1],
    )
    assert render_asset_manifest_build.render_asset_manifest_revision(entries) != (
        render_asset_manifest_build.render_asset_manifest_revision(changed_source)
    )

    database = tmp_path / 'manifest.sqlite'
    with sqlite3.connect(database) as connection:
        release_render_manifest_tables.replace_render_asset_manifest_table(
            connection,
            entries,
            updated_at=123.0,
        )
        rows = connection.execute(
            """
            SELECT asset_kind, asset_key, sha256, release_revision, available
            FROM render_asset_manifest
            ORDER BY asset_key
            """
        ).fetchall()

    assert rows == [
        (
            'soulmark_icon_png',
            '18',
            '8f8cbb7dcf46e0bc7d53265749a6c17d116093a6ba95e442764060c76fd4a86c',
            'config-20260806',
            1,
        ),
        ('soulmark_icon_png', '19', '', 'config-20260806', 0),
    ]


def test_render_asset_manifest_metadata_publishes_immutable_asset_snapshot() -> None:
    entries = (
        render_asset_manifest_build.RenderAssetManifestEntry(
            asset_kind='pet_head',
            asset_key='1',
            sha256='',
            release_revision='config-20260815',
            available=True,
            source='example',
        ),
    )
    snapshot = render_asset_repository.AssetRepositorySnapshot(
        revision='a' * 40,
        blobs_by_path={},
    )

    scopes = (
        builder.PET_INFO_RENDER_ASSET_SCOPE,
        builder.TYPE_MATCHUP_RENDER_ASSET_SCOPE,
        builder.PEAK_POOL_RENDER_ASSET_SCOPE,
    )
    metadata = render_asset_manifest_build.render_asset_manifest_metadata(
        entries,
        {'default': snapshot},
        complete_scopes=scopes,
        config=builder.RENDER_ASSET_MANIFEST_CONFIG,
    )

    assert metadata == {
        builder.RENDER_ASSET_MANIFEST_REVISION_KEY: (
            render_asset_manifest_build.render_asset_manifest_revision(entries)
        ),
        builder.RENDER_ASSET_MANIFEST_CONTRACT_VERSION_KEY: '3',
        builder.RENDER_ASSET_MANIFEST_SCOPES_KEY: (
            '["pet_info","type_matchup","peak_pool"]'
        ),
        builder.RENDER_ASSET_MANIFEST_REPOSITORIES_KEY: (
            json.dumps(
                {
                    'default': {
                        'repository': 'Murmansk-Seer/seer-unity-assets',
                        'revision': 'a' * 40,
                    }
                },
                separators=(',', ':'),
            )
        ),
        'render_asset_manifest_count': '1',
        'render_asset_manifest_available_count': '1',
    }

    unavailable = render_asset_manifest_build.render_asset_manifest_metadata(
        entries,
        {},
        complete_scopes=(),
        config=builder.RENDER_ASSET_MANIFEST_CONFIG,
    )

    assert unavailable[builder.RENDER_ASSET_MANIFEST_REPOSITORIES_KEY] == '{}'


def test_pet_info_remote_asset_manifest_requires_all_mandatory_assets(
    tmp_path: Path,
) -> None:
    database = tmp_path / 'pet-info-assets.sqlite'
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE pet (resource_id INTEGER NOT NULL);
            CREATE TABLE element_type (id INTEGER NOT NULL);
            CREATE TABLE mintmark (id INTEGER NOT NULL);
            CREATE TABLE item (id INTEGER NOT NULL);
            CREATE TABLE special_effect_status (status_id INTEGER NOT NULL);
            INSERT INTO pet VALUES (100), (101);
            INSERT INTO element_type VALUES (1);
            INSERT INTO mintmark VALUES (8);
            INSERT INTO item VALUES (9);
            INSERT INTO special_effect_status VALUES (10);
            """
        )
        snapshot = render_asset_repository.AssetRepositorySnapshot(
            revision='a' * 40,
            blobs_by_path={
                'newseer/assets/art/ui/assets/pet/head/100.png': 'head-100',
                'newseer/assets/art/ui/assets/pet/body/100.png': 'body-100',
                'newseer/assets/art/ui/assets/pet/head/101.png': 'head-101',
                'newseer/assets/art/ui/assets/pet/body/101.png': 'body-101',
                'newseer/assets/art/ui/assets/pettype/1.png': 'type-1',
                'newseer/assets/art/ui/assets/pettype/prop.png': 'prop',
                'newseer/assets/art/ui/assets/countermark/icon/8.png': 'mintmark',
                'newseer/assets/art/ui/assets/item/petitem/icon/9.png': 'item',
            },
        )
        remote = _collect_remote_asset_manifest(
            connection,
            snapshot,
            release_revision='release-1',
        )
        entries = remote.pet_info_entries
        complete = remote.pet_info_scope_complete

    assert complete is True
    by_identity = {(entry.asset_kind, entry.asset_key): entry for entry in entries}
    assert by_identity[('pet_head', '100')].available is True
    assert by_identity[('item', '9')].available is True
    assert by_identity[('sign_buff', '10')].available is False
    assert '#blob:item' in by_identity[('item', '9')].source


def test_optional_battle_effect_assets_use_the_release_snapshot() -> None:
    with sqlite3.connect(':memory:') as connection:
        connection.execute('CREATE TABLE battle_effect (id INTEGER NOT NULL)')
        connection.executemany(
            'INSERT INTO battle_effect VALUES (?)',
            [(1,), (2,)],
        )
        snapshot = render_asset_repository.AssetRepositorySnapshot(
            revision='a' * 40,
            blobs_by_path={
                'newseer/assets/art/ui/assets/battleeffect/abnormal/1.png': (
                    'effect-1'
                ),
            },
        )

        remote = _collect_remote_asset_manifest(
            connection,
            snapshot,
            release_revision='release-1',
        )

    by_key = {entry.asset_key: entry for entry in remote.supplemental_entries}
    assert set(by_key) == {'1', '2'}
    assert by_key['1'].available is True
    assert '#blob:effect-1' in by_key['1'].source
    assert by_key['2'].available is False

    published = render_asset_manifest_build.build_render_asset_manifest(
        remote,
        {},
        {'default': snapshot},
        release_revision='release-1',
        effect_icon_source_version='test',
        config=builder.RENDER_ASSET_MANIFEST_CONFIG,
    )
    assert published.complete_scopes == ()
    assert {
        (entry.asset_kind, entry.asset_key, entry.available)
        for entry in published.entries
    } == {
        ('battle_effect', '1', True),
        ('battle_effect', '2', False),
    }


def test_optional_autocard_assets_use_the_release_snapshot() -> None:
    with sqlite3.connect(':memory:') as connection:
        connection.execute(
            'CREATE TABLE autocard_card (id INTEGER, raw_json TEXT NOT NULL)'
        )
        connection.executemany(
            'INSERT INTO autocard_card VALUES (?, ?)',
            [
                (101, '{"picID": 7}'),
                (20001, '{"picID": 8}'),
                (10101, '{"picID": 7}'),
            ],
        )
        connection.execute('CREATE TABLE autocard_role (id INTEGER, pic_id INTEGER)')
        connection.execute('INSERT INTO autocard_role VALUES (3, 9)')
        snapshot = render_asset_repository.AssetRepositorySnapshot(
            revision='a' * 40,
            blobs_by_path={
                'newseer/assets/art/autocard/texture/cards/card_7.png': 'card-7',
                'newseer/assets/art/autocard/texture/roles/card/role_9.png': 'role-9',
            },
        )

        remote = _collect_remote_asset_manifest(
            connection,
            snapshot,
            release_revision='release-1',
        )

    by_identity = {
        (entry.asset_kind, entry.asset_key): entry
        for entry in remote.supplemental_entries
    }
    assert set(by_identity) == {
        ('autocard_card', 'card_7'),
        ('autocard_card', 'card_20001'),
        ('autocard_role', 'role_9'),
    }
    assert by_identity[('autocard_card', 'card_7')].available is True
    assert by_identity[('autocard_card', 'card_20001')].available is False
    assert by_identity[('autocard_role', 'role_9')].available is True


@pytest.mark.parametrize(
    'case', ['complete', 'missing', 'unresolved', 'empty', 'absent', 'head_missing']
)
def test_skin_body_manifest_is_independent_and_deduplicated(case: str) -> None:
    with sqlite3.connect(':memory:') as connection:
        connection.executescript("""
            CREATE TABLE pet (resource_id INTEGER);
            CREATE TABLE element_type (id INTEGER);
            CREATE TABLE mintmark (id INTEGER);
            CREATE TABLE item (id INTEGER);
            CREATE TABLE special_effect_status (status_id INTEGER);
            CREATE TABLE pet_skin (id INTEGER, resource_id INTEGER);
            INSERT INTO pet VALUES (100);
            INSERT INTO element_type VALUES (1);
            INSERT INTO mintmark VALUES (8);
        """)
        if case != 'absent':
            connection.execute(
                'CREATE TABLE skin_image_resolution (skin_id INTEGER, body_resource_id INTEGER)'
            )
            if case != 'empty':
                connection.executemany(
                    'INSERT INTO skin_image_resolution VALUES (?, ?)',
                    [(1, 100), (2, 101), (3, 101)]
                    + ([(4, 0)] if case == 'unresolved' else []),
                )
        paths = {
            'pet/head/100': 'head',
            'pet/body/100': 'base',
            'pet/body/101': 'skin',
            'pettype/1': 'type',
            'pettype/prop': 'prop',
            'countermark/icon/8': 'mark',
        }
        if case == 'missing':
            del paths['pet/body/101']
        if case == 'head_missing':
            del paths['pet/head/100']
        snapshot = render_asset_repository.AssetRepositorySnapshot(
            revision='a' * 40,
            blobs_by_path={
                f'newseer/assets/art/ui/assets/{path}.png': blob
                for path, blob in paths.items()
            },
        )
        remote = _collect_remote_asset_manifest(
            connection, snapshot, release_revision='release'
        )
    config = builder.RENDER_ASSET_MANIFEST_CONFIG
    scopes = render_asset_manifest_build.complete_render_asset_scopes(
        remote, config=config
    )
    assert ('skin_body' in scopes) == (case in {'complete', 'head_missing'})
    assert 'type_matchup' in scopes
    assert ('peak_pool' in scopes) == (case != 'head_missing')
    result = render_asset_manifest_build.build_render_asset_manifest(
        remote,
        {},
        {'default': snapshot} if snapshot is not None else {},
        release_revision='release',
        effect_icon_source_version='test',
        config=config,
    )
    identities = [(entry.asset_kind, entry.asset_key) for entry in result.entries]
    assert len(identities) == len(set(identities))
    assert identities.count(('pet_body', '100')) == 1
    if case not in {'absent', 'empty'}:
        body = next(
            entry
            for entry in result.entries
            if (entry.asset_kind, entry.asset_key) == ('pet_body', '101')
        )
        assert body.available == (case != 'missing')
        if body.available:
            assert '#blob:skin' in body.source
            changed = replace(
                body, source=body.source.replace('#blob:skin', '#blob:new')
            )
            assert render_asset_manifest_build.render_asset_manifest_revision(
                (body,)
            ) != render_asset_manifest_build.render_asset_manifest_revision((changed,))


@pytest.mark.parametrize('missing', [False, True])
def test_skin_body_manifest_covers_catalogue_fallbacks(missing: bool) -> None:
    with sqlite3.connect(':memory:') as connection:
        connection.executescript("""
            CREATE TABLE pet_skin (id INTEGER PRIMARY KEY, resource_id INTEGER);
            CREATE TABLE skin_image_resolution (skin_id INTEGER, body_resource_id INTEGER);
            INSERT INTO pet_skin VALUES (1, 100), (2, 200), (3, 300), (4, 300);
            INSERT INTO skin_image_resolution VALUES (1, 101), (3, 0), (5, 400);
        """)
        bodies = (101, 300, 400) if missing else (101, 200, 300, 400)
        snapshot = render_asset_repository.AssetRepositorySnapshot(
            revision='b' * 40,
            blobs_by_path={
                f'newseer/assets/art/ui/assets/pet/body/{body}.png': str(body)
                for body in bodies
            },
        )
        entries, complete = render_asset_manifest_build._build_skin_body_manifest(
            connection,
            {'default': snapshot},
            release_revision='release',
            config=builder.RENDER_ASSET_MANIFEST_CONFIG,
        )
    assert [entry.asset_key for entry in entries] == ['101', '200', '300', '400']
    assert complete is not missing
    assert [entry.asset_key for entry in entries if not entry.available] == (
        ['200'] if missing else []
    )


def test_skin_body_manifest_requires_catalogue_schema() -> None:
    with sqlite3.connect(':memory:') as connection:
        connection.executescript("""
            CREATE TABLE skin_image_resolution (skin_id INTEGER, body_resource_id INTEGER);
            INSERT INTO skin_image_resolution VALUES (1, 100);
        """)
        snapshot = render_asset_repository.AssetRepositorySnapshot(
            revision='b' * 40,
            blobs_by_path={'newseer/assets/art/ui/assets/pet/body/100.png': 'body'},
        )
        assert render_asset_manifest_build._build_skin_body_manifest(
            connection,
            {'default': snapshot},
            release_revision='release',
            config=builder.RENDER_ASSET_MANIFEST_CONFIG,
        ) == ((), False)


def test_equipment_manifest_routes_mounts_to_generated_repository() -> None:
    with sqlite3.connect(':memory:') as connection:
        connection.executescript(
            """
            CREATE TABLE equip (id INTEGER NOT NULL, part_type_id INTEGER NOT NULL);
            INSERT INTO equip VALUES (12, 0), (1301170, 6);
            """
        )

        assert render_asset_manifest_build._select_equipment_asset_ids(connection) == (
            (12,),
            (1301170,),
        )


def test_mount_manifest_uses_typed_repository_override() -> None:
    default = render_asset_repository.AssetRepositorySnapshot(
        repository='example/default-assets',
        revision='a' * 40,
        blobs_by_path={},
    )
    mounts = render_asset_repository.AssetRepositorySnapshot(
        repository='example/generated-assets',
        revision='b' * 40,
        blobs_by_path={'mount/1301170.png': 'blob'},
        sha256_by_path={'mount/1301170.png': 'content-sha'},
    )

    entries, complete = render_asset_manifest_build._resolve_requests(
        (
            render_asset_manifest_build.RemoteRenderAssetRequest(
                asset_kind='mount',
                asset_key='1301170',
                candidates=(
                    render_asset_manifest_build.RemoteRenderAssetCandidate(
                        'default',
                        'newseer/assets/art/ui/assets/item/cloth/prev/1301170.png',
                    ),
                    render_asset_manifest_build.RemoteRenderAssetCandidate(
                        'default',
                        'newseer/assets/art/ui/assets/item/cloth/icon/1301170.png',
                    ),
                    render_asset_manifest_build.RemoteRenderAssetCandidate(
                        'mount', 'mount/1301170.png'
                    ),
                ),
                required=True,
            ),
        ),
        {'default': default, 'mount': mounts},
        release_revision='release',
        config=builder.RENDER_ASSET_MANIFEST_CONFIG,
    )

    assert complete is True
    assert entries[0].source.startswith(
        f'example/generated-assets@{"b" * 40}:mount/1301170.png'
    )
    assert entries[0].sha256 == 'content-sha'


def test_mount_manifest_prefers_existing_unity_asset() -> None:
    unity_path = 'newseer/assets/art/ui/assets/item/cloth/prev/1301170.png'
    default = render_asset_repository.AssetRepositorySnapshot(
        repository='example/default-assets',
        revision='a' * 40,
        blobs_by_path={unity_path: 'unity-blob'},
    )
    mounts = render_asset_repository.AssetRepositorySnapshot(
        repository='example/generated-assets',
        revision='b' * 40,
        blobs_by_path={'mount/1301170.png': 'generated-blob'},
    )

    entries, complete = render_asset_manifest_build._resolve_requests(
        (
            render_asset_manifest_build.RemoteRenderAssetRequest(
                asset_kind='mount',
                asset_key='1301170',
                candidates=(
                    render_asset_manifest_build.RemoteRenderAssetCandidate(
                        'default', unity_path
                    ),
                    render_asset_manifest_build.RemoteRenderAssetCandidate(
                        'default',
                        'newseer/assets/art/ui/assets/item/cloth/icon/1301170.png',
                    ),
                    render_asset_manifest_build.RemoteRenderAssetCandidate(
                        'mount', 'mount/1301170.png'
                    ),
                ),
                required=True,
            ),
        ),
        {'default': default, 'mount': mounts},
        release_revision='release',
        config=builder.RENDER_ASSET_MANIFEST_CONFIG,
    )

    assert complete is True
    mount = next(entry for entry in entries if entry.asset_kind == 'mount')
    assert mount.source.startswith(
        f'example/default-assets@{"a" * 40}:{unity_path}#blob:unity-blob'
    )


def test_mount_manifest_uses_unity_icon_before_generated_asset() -> None:
    icon_path = 'newseer/assets/art/ui/assets/item/cloth/icon/1300081.png'
    default = render_asset_repository.AssetRepositorySnapshot(
        repository='example/default-assets',
        revision='a' * 40,
        blobs_by_path={icon_path: 'icon-blob'},
    )
    mounts = render_asset_repository.AssetRepositorySnapshot(
        repository='example/generated-assets',
        revision='b' * 40,
        blobs_by_path={'mount/1300081.png': 'generated-blob'},
    )

    requests = render_asset_manifest_build._new_content_standard_requests
    with sqlite3.connect(':memory:') as connection:
        connection.executescript(
            """
            CREATE TABLE suit (id INTEGER);
            CREATE TABLE equip (id INTEGER, part_type_id INTEGER);
            CREATE TABLE title_part (id INTEGER);
            CREATE TABLE pet (resource_id INTEGER);
            CREATE TABLE skin_image_resolution (head_resource_id INTEGER);
            INSERT INTO equip VALUES (1300081, 6);
            """
        )
        resolved_requests = requests(
            connection,
            config=builder.RENDER_ASSET_MANIFEST_CONFIG,
        )
        assert resolved_requests is not None
        mount_request = next(
            request for request in resolved_requests if request.asset_kind == 'mount'
        )

    entries, complete = render_asset_manifest_build._resolve_requests(
        (mount_request,),
        {'default': default, 'mount': mounts},
        release_revision='release',
        config=builder.RENDER_ASSET_MANIFEST_CONFIG,
    )

    assert complete is True
    assert entries[0].source.startswith(
        f'example/default-assets@{"a" * 40}:{icon_path}#blob:icon-blob'
    )


def test_parse_git_tree_blobs_reads_only_blob_entries() -> None:
    tree = '\n'.join(
        (
            '100644 blob abc123\tassets/pet.png',
            '040000 tree def456\tassets',
            '100644 blob fedcba\tassets/type.png',
        )
    )

    assert render_asset_repository.parse_git_tree_blobs(tree) == {
        'assets/pet.png': 'abc123',
        'assets/type.png': 'fedcba',
    }


def test_render_asset_repository_snapshot_reads_complete_rest_tree() -> None:
    repository = render_asset_repository.RenderAssetRepository(
        name='example/assets',
        git_url='https://example.invalid/assets.git',
        ref='main',
        commit_url='https://example.invalid/commit',
        tree_url_template='https://example.invalid/tree/{revision}',
    )
    payloads = {
        repository.commit_url: b'{"sha":"a"}',
        'https://example.invalid/tree/a': (
            b'{"truncated":false,"tree":['
            b'{"type":"blob","path":"assets/pet.png","sha":"pet"},'
            b'{"type":"tree","path":"assets","sha":"ignored"}]}'
        ),
    }

    snapshot = render_asset_repository.load_asset_repository_snapshot(
        repository,
        payloads.__getitem__,
        logger=builder.logger,
    )

    assert snapshot == render_asset_repository.AssetRepositorySnapshot(
        revision='a',
        blobs_by_path={'assets/pet.png': 'pet'},
        repository='example/assets',
    )


def test_render_asset_repository_snapshot_uses_git_when_rest_fails(
    monkeypatch,
) -> None:
    repository = render_asset_repository.RenderAssetRepository(
        name='example/assets',
        git_url='https://example.invalid/assets.git',
        ref='main',
        commit_url='https://example.invalid/commit',
        tree_url_template='https://example.invalid/tree/{revision}',
    )
    expected = render_asset_repository.AssetRepositorySnapshot(
        revision='b',
        blobs_by_path={'assets/pet.png': 'pet'},
    )
    calls: list[render_asset_repository.RenderAssetRepository] = []

    def git_fallback(
        value: render_asset_repository.RenderAssetRepository,
        *,
        logger,
    ) -> render_asset_repository.AssetRepositorySnapshot:
        del logger
        calls.append(value)
        return expected

    monkeypatch.setattr(
        render_asset_repository,
        '_load_asset_repository_snapshot_from_git',
        git_fallback,
    )

    snapshot = render_asset_repository.load_asset_repository_snapshot(
        repository,
        lambda _url: (_ for _ in ()).throw(
            HTTPError('url', 403, 'rate', Message(), None)
        ),
        logger=builder.logger,
    )

    assert snapshot is expected
    assert calls == [repository]


def test_pet_info_remote_asset_manifest_disables_scope_for_missing_mandatory_asset(
    tmp_path: Path,
) -> None:
    database = tmp_path / 'missing-pet-info-assets.sqlite'
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE pet (resource_id INTEGER NOT NULL);
            CREATE TABLE element_type (id INTEGER NOT NULL);
            CREATE TABLE mintmark (id INTEGER NOT NULL);
            CREATE TABLE item (id INTEGER NOT NULL);
            CREATE TABLE special_effect_status (status_id INTEGER NOT NULL);
            INSERT INTO pet VALUES (100);
            INSERT INTO element_type VALUES (1);
            INSERT INTO mintmark VALUES (8);
            """
        )
        snapshot = render_asset_repository.AssetRepositorySnapshot(
            revision='b' * 40,
            blobs_by_path={
                'newseer/assets/art/ui/assets/pet/head/100.png': 'head-100',
                'newseer/assets/art/ui/assets/pet/body/100.png': 'body-100',
                'newseer/assets/art/ui/assets/pettype/1.png': 'type-1',
                'newseer/assets/art/ui/assets/pettype/prop.png': 'prop',
            },
        )
        remote = _collect_remote_asset_manifest(
            connection,
            snapshot,
            release_revision='release-1',
        )
        entries = remote.pet_info_entries
        complete = remote.pet_info_scope_complete

    assert complete is False
    missing = next(
        entry
        for entry in entries
        if (entry.asset_kind, entry.asset_key) == ('mintmark', '8')
    )
    assert missing.available is False
    assert 'missing:' in missing.source


def test_new_content_standard_remote_asset_manifest_requires_all_assets(
    tmp_path: Path,
) -> None:
    database = tmp_path / 'new-content-standard-assets.sqlite'
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE suit (id INTEGER NOT NULL);
            CREATE TABLE equip (id INTEGER NOT NULL, part_type_id INTEGER NOT NULL);
            CREATE TABLE title_part (id INTEGER NOT NULL);
            CREATE TABLE pet (resource_id INTEGER NOT NULL);
            CREATE TABLE skin_image_resolution (head_resource_id INTEGER NOT NULL);
            INSERT INTO suit VALUES (11);
            INSERT INTO equip VALUES (12, 0);
            INSERT INTO title_part VALUES (13);
            INSERT INTO pet VALUES (100);
            INSERT INTO skin_image_resolution VALUES (100), (101);
            """
        )
        snapshot = render_asset_repository.AssetRepositorySnapshot(
            revision='c' * 40,
            blobs_by_path={
                'newseer/assets/art/ui/assets/item/cloth/suiticon/11.png': 'suit',
                'newseer/assets/art/ui/assets/item/cloth/prev/12.png': 'equip',
                'newseer/assets/art/ui/assets/achieve/title/13.png': 'title',
                'newseer/assets/art/ui/assets/pet/head/101.png': 'skin-head',
            },
        )
        remote = _collect_remote_asset_manifest(
            connection,
            snapshot,
            release_revision='release-1',
        )
        entries = remote.new_content_standard_entries
        complete = remote.new_content_standard_scope_complete

    assert complete is True
    assert [(entry.asset_kind, entry.asset_key) for entry in entries] == [
        ('equip', '12'),
        ('pet_head', '101'),
        ('suit', '11'),
        ('title', '13'),
    ]


def test_new_content_standard_remote_asset_manifest_stays_incomplete_when_missing(
    tmp_path: Path,
) -> None:
    database = tmp_path / 'missing-new-content-standard-assets.sqlite'
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE suit (id INTEGER NOT NULL);
            CREATE TABLE equip (id INTEGER NOT NULL, part_type_id INTEGER NOT NULL);
            CREATE TABLE title_part (id INTEGER NOT NULL);
            CREATE TABLE pet (resource_id INTEGER NOT NULL);
            CREATE TABLE skin_image_resolution (head_resource_id INTEGER NOT NULL);
            INSERT INTO suit VALUES (11);
            INSERT INTO equip VALUES (12, 0);
            INSERT INTO title_part VALUES (13);
            INSERT INTO pet VALUES (100);
            INSERT INTO skin_image_resolution VALUES (100);
            """
        )
        snapshot = render_asset_repository.AssetRepositorySnapshot(
            revision='d' * 40,
            blobs_by_path={
                'newseer/assets/art/ui/assets/item/cloth/suiticon/11.png': 'suit',
                'newseer/assets/art/ui/assets/item/cloth/prev/12.png': 'equip',
            },
        )
        remote = _collect_remote_asset_manifest(
            connection,
            snapshot,
            release_revision='release-1',
        )
        entries = remote.new_content_standard_entries
        complete = remote.new_content_standard_scope_complete

    assert complete is False
    missing = next(entry for entry in entries if entry.asset_kind == 'title')
    assert missing.available is False


def test_render_effect_icon_png_uses_original_swf_sprite_export(monkeypatch) -> None:
    png_data = _test_png(size=(7, 5))
    check = effect_icon_build_types.EffectIconAssetCheck(
        icon_id=1644,
        url='https://example.test/1644.swf',
        available=True,
        status=200,
        content_type='application/x-shockwave-flash',
        content_length=123,
        error='',
    )

    calls: list[list[str]] = []

    def fake_run(args, **_kwargs):
        calls.append(args)
        assert '-swf2xml' not in args
        assert '-xml2swf' not in args
        assert args[-1].endswith('1644.swf')
        output_dir = Path(args[-2])
        item_dir = output_dir / 'DefineSprite_6_item'
        item_dir.mkdir()
        (item_dir / '1.png').write_bytes(png_data)
        return effect_icon_png_renderer.subprocess.CompletedProcess(
            args=args,
            returncode=0,
        )

    monkeypatch.setattr(effect_icon_png_renderer.subprocess, 'run', fake_run)
    config = _effect_icon_render_config(
        java_command=sys.executable,
        ffdec_jar=Path(__file__),
        render_zoom=6,
    )

    render = effect_icon_png_renderer._render_effect_icon_png(
        1644,
        check,
        config=config,
        download_effect_icon=lambda _check: b'FWS',
        logger=builder.logger,
    )

    assert render == effect_icon_build_types.EffectIconPngRender(
        icon_id=1644,
        available=True,
        content_type='image/png',
        content_length=len(png_data),
        data=png_data,
        error='',
    )
    assert len(calls) == 1
    assert 'sprite' in calls[0]


def test_render_effect_icon_png_falls_back_to_shape_export(monkeypatch) -> None:
    png_data = _test_png()
    check = effect_icon_build_types.EffectIconAssetCheck(
        icon_id=1644,
        url='https://example.test/1644.swf',
        available=True,
        status=200,
        content_type='application/x-shockwave-flash',
        content_length=123,
        error='',
    )

    calls: list[list[str]] = []

    def fake_run(args, **_kwargs):
        calls.append(args)
        if 'sprite' in args:
            raise RuntimeError('sprite export unavailable')
        output_dir = Path(args[-2])
        output_dir.mkdir(exist_ok=True)
        (output_dir / '1.png').write_bytes(png_data)
        return effect_icon_png_renderer.subprocess.CompletedProcess(
            args=args,
            returncode=0,
        )

    monkeypatch.setattr(effect_icon_png_renderer.subprocess, 'run', fake_run)

    render = effect_icon_png_renderer._render_effect_icon_png(
        1644,
        check,
        config=_effect_icon_render_config(),
        download_effect_icon=lambda _check: b'FWS',
        logger=builder.logger,
    )

    assert render.available is True
    assert render.data == png_data
    assert len(calls) == 2
    assert 'sprite' in calls[0]
    assert 'shape' in calls[1]


def test_render_effect_icon_png_retries_transient_verification_failure(
    monkeypatch,
) -> None:
    png_data = _test_png()
    check = effect_icon_build_types.EffectIconAssetCheck(
        icon_id=806,
        url='https://seer.61.com/resource/effectIcon/806.swf',
        available=False,
        status=0,
        content_type='',
        content_length=None,
        error='TLS handshake timed out',
    )
    download_calls: list[object] = []

    def fake_download(asset_check):
        download_calls.append(asset_check)
        return b'FWS'

    def fake_run(args, **_kwargs):
        (Path(args[-2]) / '1.png').write_bytes(png_data)
        return effect_icon_png_renderer.subprocess.CompletedProcess(
            args=args,
            returncode=0,
        )

    monkeypatch.setattr(effect_icon_png_renderer.subprocess, 'run', fake_run)

    render = effect_icon_png_renderer._render_effect_icon_png(
        806,
        check,
        config=_effect_icon_render_config(),
        download_effect_icon=fake_download,
        logger=builder.logger,
    )

    assert download_calls == [check]
    assert render.available is True
    assert render.data == png_data
    assert (
        release_soulmark_icon_tables.effect_icon_runtime_asset_url(check) == check.url
    )


def test_effect_icon_runtime_asset_url_omits_confirmed_missing_asset() -> None:
    check = effect_icon_build_types.EffectIconAssetCheck(
        icon_id=999999,
        url='https://seer.61.com/resource/effectIcon/999999.swf',
        available=False,
        status=404,
        content_type='text/html',
        content_length=None,
        error='',
    )

    assert release_soulmark_icon_tables.effect_icon_runtime_asset_url(check) is None


def test_render_effect_icon_png_rejects_transparent_ffdec_output(monkeypatch) -> None:
    check = effect_icon_build_types.EffectIconAssetCheck(
        icon_id=1644,
        url='https://example.test/1644.swf',
        available=True,
        status=200,
        content_type='application/x-shockwave-flash',
        content_length=123,
        error='',
    )

    def fake_run(args, **_kwargs):
        (Path(args[-2]) / '1.png').write_bytes(_test_png(alpha=0))
        return effect_icon_png_renderer.subprocess.CompletedProcess(
            args=args,
            returncode=0,
        )

    monkeypatch.setattr(effect_icon_png_renderer.subprocess, 'run', fake_run)

    render = effect_icon_png_renderer._render_effect_icon_png(
        1644,
        check,
        config=_effect_icon_render_config(),
        download_effect_icon=lambda _check: b'FWS',
        logger=builder.logger,
    )

    assert render.available is False
    assert render.data is None
    assert 'fully transparent' in render.error


def test_render_effect_icon_png_preserves_exported_canvas_and_alpha(
    monkeypatch,
) -> None:
    check = effect_icon_build_types.EffectIconAssetCheck(
        icon_id=1644,
        url='https://example.test/1644.swf',
        available=True,
        status=200,
        content_type='application/x-shockwave-flash',
        content_length=123,
        error='',
    )
    exported = io.BytesIO()
    Image.new('RGBA', (9, 7), (0, 0, 0, 0)).save(exported, format='PNG')
    with Image.open(io.BytesIO(exported.getvalue())) as image:
        image.putpixel((8, 6), (255, 100, 0, 80))
        preserved = io.BytesIO()
        image.save(preserved, format='PNG')
    png_data = preserved.getvalue()

    def fake_run(args, **_kwargs):
        assert '-swf2xml' not in args
        assert '-xml2swf' not in args
        output_dir = Path(args[-2])
        item_dir = output_dir / 'DefineSprite_6_item'
        item_dir.mkdir()
        (item_dir / '1.png').write_bytes(png_data)
        return effect_icon_png_renderer.subprocess.CompletedProcess(
            args=args,
            returncode=0,
        )

    monkeypatch.setattr(effect_icon_png_renderer.subprocess, 'run', fake_run)

    render = effect_icon_png_renderer._render_effect_icon_png(
        613,
        check,
        config=_effect_icon_render_config(),
        download_effect_icon=lambda _check: b'FWS',
        logger=builder.logger,
    )

    assert render.available is True
    render_data = render.data
    assert isinstance(render_data, bytes)
    assert render_data == png_data
    with Image.open(io.BytesIO(render_data)) as image:
        assert image.size == (9, 7)
        assert image.convert('RGBA').getpixel((8, 6)) == (255, 100, 0, 80)


def test_parse_unity_item_names_reads_exchange_currency_names() -> None:
    payload = {
        'root': {
            'items': [
                {'id': 1726992, 'name': '共振晶体'},
                {'id': 1726710, 'name': '共鸣锚点'},
            ]
        }
    }

    names = release_source_loaders._parse_unity_item_names(
        json.dumps(payload, ensure_ascii=False).encode('utf-8')
    )

    assert names == {1726992: '共振晶体', 1726710: '共鸣锚点'}


def test_parse_pet_partner_data_keeps_badge_cost_and_skill_upgrade() -> None:
    partners = {
        'data': [
            {
                'id': 15,
                'partnerName': '源初之夜',
                'partnerMonsterId': '4329|3491',
                'cost': 8,
            }
        ]
    }
    upgrades = {
        'data': [
            {
                'monID': 4329,
                'descBefore': '强化前魂印',
                'descAfter': '强化后魂印',
                'skill': '36696',
            },
            {
                'monID': 9999,
                'descBefore': '未加入羁绊组',
                'descAfter': '未加入羁绊组',
                'skill': '1',
            },
        ]
    }

    data = partner_contract_sources.parse_pet_partner_data(
        json.dumps(
            {
                'schema_version': 1,
                'source': {
                    'package': 'ConfigPackage',
                    'config_package_version': 'test-version',
                },
                'groups': [
                    {
                        'key': partners['data'][0]['id'],
                        'type': '2',
                        'name': partners['data'][0]['partnerName'],
                        'member_pet_ids': [4329, 3491],
                        'cost': partners['data'][0]['cost'],
                    },
                    {
                        'key': 1,
                        'type': '1',
                        'name': '雷电传承',
                        'member_pet_ids': [3142, 3150],
                        'cost': 3,
                    },
                ],
                'upgrades': [
                    {
                        'pet_id': upgrade['monID'],
                        # partner_contracts.json v1 has these source keys
                        # reversed; the builder normalizes them on ingest.
                        'before_description': upgrade['descAfter'],
                        'after_description': upgrade['descBefore'],
                        'skill_ids': [upgrade['skill']],
                    }
                    for upgrade in upgrades['data']
                ]
                + [
                    {
                        'pet_id': 3142,
                        'before_description': '强化后魂印',
                        'after_description': '强化前魂印',
                        'skill_ids': ['123'],
                    }
                ],
            },
            ensure_ascii=False,
        ).encode('utf-8'),
        schema_version=builder.PARTNER_CONTRACTS_SCHEMA_VERSION,
        group_type=builder.PARTNER_CONTRACT_GROUP_TYPE,
        cost_item_id=builder.CONTRACT_BADGE_ITEM_ID,
        cost_item_name=builder.CONTRACT_BADGE_ITEM_NAME,
        descriptions_reversed=builder.PARTNER_CONTRACTS_V1_DESCRIPTIONS_REVERSED,
    )

    assert data.groups == [
        partner_contract_sources.PetPartnerGroup(
            group_id=15,
            name='源初之夜',
            member_pet_ids=(4329, 3491),
            cost_item_id=1722827,
            cost_item_name='契约徽章',
            cost_item_quantity=8,
        )
    ]
    assert data.upgrades == [
        partner_contract_sources.PetPartnerUpgrade(
            pet_id=4329,
            before_description='强化前魂印',
            after_description='强化后魂印',
            skill_id=36696,
        )
    ]
    assert all(3142 not in group.member_pet_ids for group in data.groups)
    assert all(upgrade.pet_id != 3142 for upgrade in data.upgrades)


def test_replace_autocard_roles_populates_official_schema_and_skips_npcs() -> None:
    data = autocard_sources.AutocardData(
        cards=[],
        roles=[
            {
                'id': 1,
                'name': 'Raw role name',
                'nature': 7,
                'health': 99,
                'picID': 17,
                'skillID': 42,
                'skillName': 'Raw skill name',
                'skillTxt': 'Raw skill text',
                'skillUpgrade': 'Raw upgrade',
                'desc': 'Raw description',
            },
            {
                'id': 10001,
                'name': 'NPC role excluded by the official analyzer',
                'nature': 8,
                'health': 88,
            },
        ],
        natures=[
            {'id': 7, 'name': 'Ground'},
            {'id': 999, 'name': 'None'},
        ],
        buffs=[],
        source='test-source',
    )

    with sqlite3.connect(':memory:') as connection:
        connection.execute(
            """
            CREATE TABLE autocard_element_type (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE autocard_role (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                health INTEGER NOT NULL,
                skill_desc TEXT NOT NULL,
                is_passive_skill BOOLEAN NOT NULL,
                skill_cost INTEGER,
                skill_game_limit INTEGER,
                skill_round_limit INTEGER,
                element_type_id INTEGER NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO autocard_role (
                id,
                name,
                description,
                health,
                skill_desc,
                is_passive_skill,
                skill_cost,
                skill_game_limit,
                skill_round_limit,
                element_type_id
            )
            VALUES (1, 'Official role', 'Official description', 42,
                    'Official skill description', 0, 3, 4, 5, 6)
            """
        )

        release_autocard_tables.replace_autocard_role_table(connection, data, 123.0)
        release_autocard_tables.replace_autocard_role_table(connection, data, 456.0)

        role_columns = {
            row[1] for row in connection.execute('PRAGMA table_info(autocard_role)')
        }
        rows = connection.execute(
            """
            SELECT
                id,
                name,
                description,
                health,
                skill_desc,
                is_passive_skill,
                skill_cost,
                skill_game_limit,
                skill_round_limit,
                element_type_id
            FROM autocard_role
            ORDER BY id
            """
        ).fetchall()
        raw_rows = connection.execute(
            """
            SELECT
                role_id,
                pic_id,
                skill_id,
                skill_name,
                skill_upgrade,
                raw_json,
                source,
                updated_at
            FROM autocard_role_raw
            ORDER BY role_id
            """
        ).fetchall()
        element_types = connection.execute(
            'SELECT id, name FROM autocard_element_type ORDER BY id'
        ).fetchall()

    assert role_columns == {
        'id',
        'name',
        'description',
        'health',
        'skill_desc',
        'is_passive_skill',
        'skill_cost',
        'skill_game_limit',
        'skill_round_limit',
        'element_type_id',
    }
    assert rows == [
        (
            1,
            'Raw role name',
            'Raw description',
            99,
            'Raw skill text',
            1,
            None,
            None,
            None,
            7,
        )
    ]
    assert raw_rows[0][:5] == (
        1,
        17,
        42,
        'Raw skill name',
        'Raw upgrade',
    )
    assert json.loads(raw_rows[0][5]) == data.roles[0]
    assert raw_rows[0][6:] == ('test-source', 456.0)
    assert element_types == [(7, 'Ground'), (999, 'None')]


def test_replace_autocard_roles_rejects_legacy_schema() -> None:
    data = autocard_sources.AutocardData(
        cards=[],
        roles=[],
        natures=[],
        buffs=[],
        source='test-source',
    )
    with sqlite3.connect(':memory:') as connection:
        connection.execute(
            """
            CREATE TABLE autocard_role (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                raw_json TEXT NOT NULL
            )
            """
        )

        with pytest.raises(RuntimeError, match='expected official columns'):
            release_autocard_tables.replace_autocard_role_table(
                connection,
                data,
                123.0,
            )


def test_merge_writes_item_exchange_prices(tmp_path) -> None:
    database = tmp_path / 'seerapi-data.sqlite'
    _create_special_effect_source_tables(database)
    price = item_exchange_sources.ItemExchangePrice(
        source_key='battlepass_shop',
        source_name='战令商店',
        source_entry_id=1005,
        item_id=1728296,
        item_name='双源魂蒂',
        item_quantity=1,
        currency_item_id=1726710,
        currency_name='共鸣锚点',
        amount=2000,
        purchase_limit=6,
        start_time=0,
        end_time=0,
    )
    effect_description = effect_metadata_sources.EffectDescription(
        effect_id=544,
        name='冥妖之悼',
        description='效果说明',
    )
    special_effect_status = effect_metadata_sources.SpecialEffectStatus(
        status_id=147,
        name='旧日之晷',
        description='状态说明',
        show_monster_id=4125,
    )
    config_data = release_build_types.ConfigPackageData(
        version='test',
        bundle_url='https://example.invalid/config.bytes',
        mintmark_quality={},
        skin_store_prices=[],
        skin_shop_prices=[],
        skin_item_tips={},
        soulmark_icons=[],
        autocard_season_effects=[
            config_package_sources.AutocardSeasonEffect(
                effect_id=10,
                sanctuary_id=2,
                name='霁天',
                description='每个商店阶段前3次购买价格减少1枚金币',
                buff_id='50044',
                buff_param='3_1',
                count_buff_id='50044',
                count_type=1,
                count_num=3,
                unlock_round=5,
                pic_id=0,
                season_id=1,
                stage=1,
            )
        ],
    )
    autocard_data = autocard_sources.AutocardData(
        cards=[],
        roles=[],
        natures=[],
        buffs=[
            {
                'id': 50073,
                'object': '赛季效果',
                'param': 'a',
                'paramDes': (
                    '游戏开始时，前排最左侧和最右侧位置变为【沃土】，初始养分计数为1'
                ),
                'IsDeathEffect': 0,
                'IsPlaceEffect': 0,
                'effectIcon': '',
            }
        ],
        source='test',
    )
    pet_partner_data = partner_contract_sources.PetPartnerData(
        groups=[
            partner_contract_sources.PetPartnerGroup(
                group_id=15,
                name='源初之夜',
                member_pet_ids=(4329, 3491),
                cost_item_id=1722827,
                cost_item_name='契约徽章',
                cost_item_quantity=8,
            )
        ],
        upgrades=[
            partner_contract_sources.PetPartnerUpgrade(
                pet_id=4329,
                before_description='强化前魂印',
                after_description='强化后魂印',
                skill_id=36696,
            )
        ],
    )

    release_publication.publish_release_tables(
        database,
        release=release_publication.ReleasePublicationInput(
            config_data=config_data,
            autocard_data=autocard_data,
            item_exchange_prices=[price],
            effect_descriptions=[effect_description],
            special_effect_statuses=[special_effect_status],
            pet_partner_data=pet_partner_data,
            weekly_preview_probe={},
            skin_image_resolutions=[
                skin_image_resolution.SkinImageResolution(
                    skin_id=538,
                    head_resource_id=3382,
                    body_resource_id=1400538,
                    head_resolution='unique_name_source',
                    body_resolution='direct_skin',
                    source_pet_id=3382,
                )
            ],
        ),
        context=builder._release_publication_context(),
    )

    with sqlite3.connect(database) as connection:
        row = connection.execute(
            """
            SELECT
                item_id,
                item_name,
                currency_item_id,
                currency_name,
                amount,
                purchase_limit,
                source_name
            FROM item_exchange_price
            """
        ).fetchone()
        effect_row = connection.execute(
            """
            SELECT effect_id, name, description
            FROM effect_description
            """
        ).fetchone()
        special_effect_status_row = connection.execute(
            """
            SELECT status_id, name, description, show_monster_id
            FROM special_effect_status
            """
        ).fetchone()
        partner_row = connection.execute(
            """
            SELECT group_id, name, cost_item_id, cost_item_quantity
            FROM pet_partner_group
            """
        ).fetchone()
        partner_upgrade_row = connection.execute(
            """
            SELECT pet_id, group_id, skill_id
            FROM pet_partner_upgrade
            """
        ).fetchone()
        skin_image_row = connection.execute(
            """
            SELECT
                skin_id,
                head_resource_id,
                body_resource_id,
                head_resolution,
                body_resolution,
                source_pet_id
            FROM skin_image_resolution
            """
        ).fetchone()
        autocard_buff_row = connection.execute(
            """
            SELECT
                id,
                object,
                param,
                param_description,
                is_death_effect,
                is_place_effect,
                effect_icon
            FROM autocard_buff
            """
        ).fetchone()
        autocard_season_effect_row = connection.execute(
            """
            SELECT
                id,
                sanctuary_id,
                name,
                description,
                buff_id,
                buff_param,
                unlock_round,
                stage
            FROM autocard_season_effect
            """
        ).fetchone()
        icon_issue_count = connection.execute(
            'SELECT COUNT(*) FROM soulmark_icon_render_issue'
        ).fetchone()
    assert row == (
        1728296,
        '双源魂蒂',
        1726710,
        '共鸣锚点',
        2000,
        6,
        '战令商店',
    )
    assert effect_row == (544, '冥妖之悼', '效果说明')
    assert special_effect_status_row == (147, '旧日之晷', '状态说明', 4125)
    assert partner_row == (15, '源初之夜', 1722827, 8)
    assert partner_upgrade_row == (4329, 15, 36696)
    assert skin_image_row == (
        538,
        3382,
        1400538,
        'unique_name_source',
        'direct_skin',
        3382,
    )
    assert autocard_buff_row == (
        50073,
        '赛季效果',
        'a',
        '游戏开始时，前排最左侧和最右侧位置变为【沃土】，初始养分计数为1',
        0,
        0,
        '',
    )
    assert autocard_season_effect_row == (
        10,
        2,
        '霁天',
        '每个商店阶段前3次购买价格减少1枚金币',
        '50044',
        '3_1',
        5,
        1,
    )
    assert icon_issue_count == (0,)
