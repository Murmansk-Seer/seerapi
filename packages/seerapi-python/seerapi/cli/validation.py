from difflib import get_close_matches
from typing import get_args

from seerapi._model_map import MODEL_MAP
from seerapi._typing import NamedModelName

NAMED_MODEL_NAMES: frozenset[str] = frozenset(get_args(NamedModelName))


def is_valid_resource(name: str) -> bool:
    return name in MODEL_MAP


def is_named_resource(name: str) -> bool:
    return name in NAMED_MODEL_NAMES


def get_suggestions(name: str, *, n: int = 3) -> list[str]:
    return get_close_matches(name, MODEL_MAP.keys(), n=n, cutoff=0.6)


def unknown_resource_error(name: str) -> dict[str, object]:
    error: dict[str, object] = {
        'error': 'unknown resource',
        'resource': name,
        'hint': 'run seerapi resources',
    }
    suggestions = get_suggestions(name)
    if suggestions:
        error['did_you_mean'] = suggestions
    return error
