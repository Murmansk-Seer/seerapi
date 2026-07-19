from pathlib import Path
import shutil

import seerapi

SKILL_NAME = 'seerapi-cli'


def get_skill_source_dir() -> Path:
    return Path(seerapi.__file__).resolve().parent / 'skills' / SKILL_NAME


def install_skill(*, target_dir: Path) -> Path:
    source_dir = get_skill_source_dir()
    if not source_dir.is_dir():
        raise FileNotFoundError(f'Skill source directory not found: {source_dir}')

    destination = target_dir
    if destination.name != SKILL_NAME:
        destination = destination / SKILL_NAME

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_dir, destination, dirs_exist_ok=True)
    return destination
