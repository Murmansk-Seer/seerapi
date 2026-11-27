"""Inventory of ID-bound state and glossary icons for the client contract."""

from __future__ import annotations

import sqlite3

if __package__:
    from .render_asset_manifest_types import (
        RemoteRenderAssetCandidate,
        RemoteRenderAssetRequest,
    )
else:
    from render_asset_manifest_types import (
        RemoteRenderAssetCandidate,
        RemoteRenderAssetRequest,
    )


def effect_icon_requests(
    connection: sqlite3.Connection, status_ids: tuple[int, ...]
) -> tuple[RemoteRenderAssetRequest, ...]:
    keys = {('sign_buff', str(status_id)) for status_id in status_ids}
    for table, column, kind in (
        ('special_effect_status_variant', 'icon_key', 'sign_buff'),
        ('special_effect_glossary_icon', 'icon_id', 'abnormal'),
    ):
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        if exists:
            keys.update(
                (kind, str(row[0]))
                for row in connection.execute(f'SELECT DISTINCT {column} FROM {table}')
                if row[0] is not None and str(row[0]) != '0'
            )
    requests = []
    for kind, key in sorted(keys):
        folder = 'signbuff' if kind == 'sign_buff' else 'abnormal'
        path = f'newseer/assets/art/ui/assets/battleeffect/{folder}/{key}.png'
        requests.append(
            RemoteRenderAssetRequest(
                kind, key, (RemoteRenderAssetCandidate(kind, path),), False
            )
        )
    return tuple(requests)
