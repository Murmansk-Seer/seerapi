"""Complete Unity snapshots, shared by every production configuration entrypoint.

Parsing and JSON validation finish before any live output is touched. Historical
fork-only files are retained, but never substituted for a failed required parser.
"""

from collections.abc import Mapping
import json
from pathlib import Path
import re
import shutil
from tempfile import TemporaryDirectory
from typing import Any

from seerapi_models.somua import SOMUA_RESOURCES
from solaris.parse import import_parser_classes

# Registered historical parsers whose assets are absent from the verified official
# ConfigPackage 20261113190033 / 08dfdb04c492b4a26d0547bae5b585d0. This explicit
# inventory is not inferred from missing downloads. Preserve historical JSON, but
# do not require a stale resource mirror to manufacture a current official input.
RETIRED_UNITY_SOURCES = frozenset(
    {
        'ActivityCenter_test.bytes',
        'AdAstraGalaxy_guoqing.bytes',
        'AdAstraGalaxy_temp.bytes',
        'AdAstraShop.bytes',
        'BackFlowTask.bytes',
        'Bravechalltask.bytes',
        'Bravecommtask.bytes',
        'FrameInfo.bytes',
        'PreferentialBest.bytes',
        'Startrekbossconfig.bytes',
        'TitleBg.bytes',
        'announcement.bytes',
        'bottlebonus.bytes',
        'brave_tower.bytes',
        'diamon_box.bytes',
        'diamon_task.bytes',
        'elGacha.bytes',
        'error_code_analysis.bytes',
        'exchangeRestrict.bytes',
        'exp_tower.bytes',
        'fightLabBossConfig.bytes',
        'fightTestLevelConfig.bytes',
        'gainWay.bytes',
        'h5_12th_box.bytes',
        'h5_12th_task.bytes',
        'itemsOptimizeCatItems16.bytes',
        'itemsOptimizeCatItems19.bytes',
        'itemsOptimizeCatItems20.bytes',
        'itemsOptimizeCatItems21.bytes',
        'itemsOptimizeCatItems22.bytes',
        'itemsOptimizeCatItems8.bytes',
        'itemsOptimizeCatItems9.bytes',
        'journey_content.bytes',
        'journey_level.bytes',
        'latestActivity_temp.bytes',
        'learningpower_tower.bytes',
        'ninjaroom.bytes',
        'package_update.bytes',
        'pass_task.bytes',
        'peakCrusade_levelRules.bytes',
        'product_coins.bytes',
        'profilephotoAutoGive.bytes',
        'pveEnter.bytes',
        'redbutton.bytes',
        'shopbanner.bytes',
        'side_effect.bytes',
        'sixteenyearsactpanel.bytes',
        'toolbar.bytes',
        'twelveYearsPromise.bytes',
    }
)


def _current_parsers():
    return [
        parser
        for parser in import_parser_classes()
        if parser.source_config_filename() not in RETIRED_UNITY_SOURCES
    ]


def required_unity_sources() -> set[str]:
    return {parser.source_config_filename() for parser in _current_parsers()}


def parse_unity_snapshot(assets: Mapping[str, bytes]) -> dict[str, Any]:
    """Export every registered official table; fail closed on any missing input."""
    parsers = _current_parsers()
    outputs = [parser.parsed_config_filename() for parser in parsers]
    if len(outputs) != len(set(outputs)):
        raise ValueError('Duplicate Unity parser output filenames')
    missing = {parser.source_config_filename() for parser in parsers} - assets.keys()
    if missing:
        raise ValueError(f'Unity snapshot missing required files: {sorted(missing)}')
    snapshot = {}
    for parser in parsers:
        source = parser.source_config_filename()
        try:
            parsed = parser().parse(assets[source])
            # Reject unserializable data and non-finite numbers before promotion.
            encoded = json.dumps(parsed, ensure_ascii=False, allow_nan=False)
            parsed = json.loads(encoded)
            if parser.parsed_config_filename() in SOMUA_RESOURCES:
                model = SOMUA_RESOURCES[parser.parsed_config_filename()]
                for row in parsed['data']:
                    model.model_validate(row, strict=True)
        except Exception as error:
            # Context only: the original exception remains chained and fatal.
            raise ValueError(
                f'Unity snapshot parse/validate failed: {source}: {error}'
            ) from error
        snapshot[parser.parsed_config_filename()] = parsed
    return snapshot


def publish_unity_snapshot(
    snapshot: Mapping[str, Any],
    output_dir: Path,
    *,
    version: str,
    parser_revision: str,
    extra_files: Mapping[str, bytes] | None = None,
) -> None:
    """Promote a complete staged directory and all version markers together."""
    if not re.fullmatch(r'\d{14}', version):
        raise ValueError(f'Invalid Unity snapshot version: {version!r}')
    if not re.fullmatch(r'[0-9a-f]{40}', parser_revision):
        raise ValueError('Unity snapshot requires an immutable parser commit SHA')
    expected = {parser.parsed_config_filename() for parser in _current_parsers()}
    if set(snapshot) != expected:
        raise ValueError(
            f'Incomplete Unity snapshot: missing={sorted(expected - snapshot.keys())}, '
            f'unexpected={sorted(snapshot.keys() - expected)}'
        )
    files = dict(extra_files or {})
    if set(files) & (expected | {'.version', '.somua-version', '.parser-revision'}):
        raise ValueError('Extra snapshot files cannot replace parsed tables or markers')
    for filename, parsed in snapshot.items():
        files[filename] = (
            json.dumps(parsed, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
        ).encode('utf-8')
    files.update(
        {
            '.version': (version + '\n').encode(),
            '.somua-version': (version + '\n').encode(),
            '.parser-revision': (parser_revision + '\n').encode(),
        }
    )
    if any(Path(name).name != name or name in {'.', '..'} for name in files):
        raise ValueError('Snapshot filenames must be plain basenames')
    output_dir = output_dir.resolve()
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(
        prefix='.unity-snapshot-', dir=output_dir.parent
    ) as temporary:
        staging = Path(temporary) / 'candidate'
        backup = Path(temporary) / 'previous'
        if output_dir.exists():
            shutil.copytree(output_dir, staging)
        else:
            staging.mkdir()
        for filename, data in files.items():
            (staging / filename).write_bytes(data)
        (staging / '.parse-status.json').unlink(missing_ok=True)
        had_previous = output_dir.exists()
        if had_previous:
            output_dir.rename(backup)
        try:
            staging.rename(output_dir)
        except BaseException:
            if had_previous:
                backup.rename(output_dir)
            raise
