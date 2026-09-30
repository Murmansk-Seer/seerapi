"""Safely push an automated build-state commit when main moves during a build."""

from __future__ import annotations

import subprocess
import sys


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ['git', *args], check=False, capture_output=True, text=True
    )


def push_build_state() -> None:
    for attempt in range(1, 4):
        pushed = git('push', 'origin', 'HEAD:main')
        if pushed.returncode == 0:
            print(f'Build state pushed on attempt {attempt}.')
            return

        print(f'Build state push attempt {attempt}/3 failed: {pushed.stderr}', file=sys.stderr)
        fetched = git('fetch', 'origin', 'main:refs/remotes/origin/main')
        if fetched.returncode != 0:
            if attempt == 3:
                raise RuntimeError(f'Could not fetch main: {fetched.stderr}')
            continue

        # A push can succeed remotely even when the response is lost.
        if git('merge-base', '--is-ancestor', 'HEAD', 'origin/main').returncode == 0:
            print('Build state is already present on remote main.')
            return

        # Rebasing is safe only when the remote did not change build state.
        unchanged = git('diff', '--quiet', 'HEAD^', 'origin/main', '--', '.build-state')
        if unchanged.returncode != 0:
            raise RuntimeError(
                'Remote build state changed during this build; refusing to overwrite it.'
            )

        rebased = git('rebase', 'origin/main')
        if rebased.returncode != 0:
            raise RuntimeError(f'Could not rebase build state: {rebased.stderr}')

    raise RuntimeError('Could not push build state after 3 total attempts.')


if __name__ == '__main__':
    push_build_state()
