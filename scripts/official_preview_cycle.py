"""Resolve the weekly preview window from official DefaultPackage assets."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import logging
import os
from pathlib import Path
from urllib.parse import urljoin

from build_http import BuildHttpClient, BuildHttpConfig
from config_package_sources import parse_package_manifest
from preview_window_dll import PreviewWindow, parse_preview_window

BASE_URL = 'https://newseer.61.com/Assets/StandaloneWindows64/DefaultPackage/'
DLL_ASSET = 'game_dll_gamelogic_dll_bytes'
UI_ASSET = 'game_ui_activitylistpreview'


@dataclass(frozen=True)
class OfficialPreviewCycle:
    window: PreviewWindow
    manifest_version: str
    dll_hash: str
    ui_hash: str

    def outputs(self) -> dict[str, str]:
        return {
            'preview_cycle_start': self.window.cycle_id,
            'preview_cycle_end': self.window.end.isoformat(timespec='seconds'),
            'preview_manifest_version': self.manifest_version,
            'preview_dll_hash': self.dll_hash,
            'preview_ui_hash': self.ui_hash,
        }


def fetch_official_preview_cycle(
    client: BuildHttpClient,
    *,
    expected_version: str = '',
) -> OfficialPreviewCycle:
    version, manifest = client.fetch_package_manifest(
        BASE_URL, 'DefaultPackage', parse_manifest=parse_package_manifest
    )
    if expected_version and version != expected_version:
        raise ValueError('DefaultPackage version changed during the build')
    bundles = {bundle.name: bundle for bundle in manifest.bundles}
    dll_bundle = bundles.get(DLL_ASSET)
    ui_bundle = bundles.get(UI_ASSET)
    if dll_bundle is None or ui_bundle is None:
        raise ValueError('DefaultPackage is missing preview DLL or UI assets')
    dll = client.download_bytes(urljoin(BASE_URL, dll_bundle.file_hash))
    if hashlib.md5(dll).hexdigest() != dll_bundle.file_hash.lower():
        raise ValueError('Official game DLL does not match its manifest hash')
    return OfficialPreviewCycle(
        window=parse_preview_window(dll),
        manifest_version=version,
        dll_hash=dll_bundle.file_hash,
        ui_hash=ui_bundle.file_hash,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--github-output', type=Path)
    parser.add_argument('--json-output', type=Path)
    parser.add_argument('--expected-version', default='')
    args = parser.parse_args()
    client = BuildHttpClient(
        BuildHttpConfig(
            timeout_seconds=45,
            retry_attempts=3,
            retry_backoff_seconds=2,
            official_package_cache_dir=(
                Path(cache_dir)
                if (cache_dir := os.environ.get('SEERAPI_DATA_OFFICIAL_PACKAGE_CACHE_DIR'))
                else None
            ),
        ),
        logger=logging.getLogger(__name__),
    )
    cycle = fetch_official_preview_cycle(client, expected_version=args.expected_version)
    values = cycle.outputs()
    if args.github_output:
        with args.github_output.open('a', encoding='utf-8') as output:
            for name, value in values.items():
                output.write(f'{name}={value}\n')
    if args.json_output:
        args.json_output.write_text(json.dumps(values, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(values, ensure_ascii=False))  # noqa: T201 - build status


if __name__ == '__main__':
    main()
