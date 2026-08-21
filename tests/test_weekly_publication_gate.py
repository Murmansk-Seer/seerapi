import importlib.util
from pathlib import Path
import sys

SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "weekly_publication_gate.py"
)
SPEC = importlib.util.spec_from_file_location("weekly_publication_gate", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError
gate = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = gate
SPEC.loader.exec_module(gate)


SHA_A = "a" * 64
SHA_B = "b" * 64


def test_weekly_cycle_starts_on_friday() -> None:
    assert gate.weekly_cycle("20260806222000") == "2026-08-07"
    assert gate.weekly_cycle("20260807090000") == "2026-08-07"


def test_same_week_never_defers_unchanged_api_data() -> None:
    assert not gate.should_defer(
        current_config_version="20260807090000",
        previous_config_version="20260806222000",
        current_api_data_sha256=SHA_A,
        previous_api_data_sha256=SHA_A,
    )


def test_new_week_with_unchanged_api_data_defers() -> None:
    assert gate.should_defer(
        current_config_version="20260814222000",
        previous_config_version="20260807090000",
        current_api_data_sha256=SHA_A,
        previous_api_data_sha256=SHA_A,
    )


def test_new_week_with_changed_api_data_does_not_defer() -> None:
    assert not gate.should_defer(
        current_config_version="20260814222000",
        previous_config_version="20260807090000",
        current_api_data_sha256=SHA_B,
        previous_api_data_sha256=SHA_A,
    )


def test_missing_or_invalid_state_does_not_defer() -> None:
    assert not gate.should_defer(
        current_config_version="20260814222000",
        previous_config_version="",
        current_api_data_sha256=SHA_A,
        previous_api_data_sha256=SHA_A,
    )
    assert not gate.should_defer(
        current_config_version="20260814222000",
        previous_config_version="20260807090000",
        current_api_data_sha256="not-a-sha",
        previous_api_data_sha256="not-a-sha",
    )
