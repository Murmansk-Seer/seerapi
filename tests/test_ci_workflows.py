from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_BUILD_WORKFLOW = ROOT / ".github/workflows/build-seerapi-data-db.yml"
FFDEC_ACTION = ROOT / ".github/actions/setup-ffdec/action.yml"


def test_data_build_reuses_the_pinned_ffdec_setup_action() -> None:
    workflow = DATA_BUILD_WORKFLOW.read_text(encoding="utf-8")
    action = FFDEC_ACTION.read_text(encoding="utf-8")

    assert workflow.count("uses: ./.github/actions/setup-ffdec") == 2
    assert "actions/setup-java" not in workflow
    assert "jpexs-decompiler/releases/download" not in workflow
    assert 'default: "26.2.1"' in action
    assert (
        'default: "0333b56998a55bd83f4e0deb678a811fcdc45607582b4f5dd438309c8c3ad5ce"'
        in action
    )
    assert "uses: actions/cache@v4" in action
    assert "sha256sum --check" in action
