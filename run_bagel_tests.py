"""从主仓根目录运行贝果日常、完整或全仓离线检查。"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path


def main() -> int:
    """统一范围、导入模式、离屏GUI与墙钟计时。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        'suite', choices=('fast', 'full', 'all'), nargs='?', default='fast'
    )
    args, extra = parser.parse_known_args()
    root = Path(__file__).resolve().parent.parent
    tests = 'zzz-od-test/test'
    paths = [
        f'{tests}/zzz_od/application/bagel',
        f'{tests}/zzz_od/gui/view/bagel',
        f'{tests}/zzz_od/operation/back_to_normal_world/test_check_screen_and_run.py',
    ]
    selection = ['-m', 'bagel_fast'] if args.suite == 'fast' else []
    if args.suite == 'all':
        paths = ['zzz-od-test/']
        selection = [
            '-m',
            'not requires_secrets',
            '--continue-on-collection-errors',
            '-o',
            'pythonpath=src zzz-od-test/test/one_dragon/base/push/channel',
        ]
    environment = dict(
        os.environ,
        PYTHONDONTWRITEBYTECODE='1',
        PYTHONIOENCODING='utf-8',
        QT_QPA_PLATFORM='offscreen',
    )
    started = time.perf_counter()
    result = subprocess.run(
        [
            sys.executable,
            '-m',
            'pytest',
            *paths,
            '--import-mode=importlib',
            '-p',
            'no:cacheprovider',
            '-q',
            '--tb=short',
            *selection,
            *extra,
        ],
        cwd=root,
        env=environment,
    )
    print(
        f'{args.suite}: wall={time.perf_counter() - started:.2f}s, exit={result.returncode}',
        flush=True,
    )
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
