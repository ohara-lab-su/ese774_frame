#!/usr/bin/env python
"""
K.NAKADA, kengo.nakada@gmail.com, kengo.nakada@mat.shimane-u.ac.jp
"""

import os
from contextlib import contextmanager

from fastapi_frame.clients.make_pyi_async_device_client import (
    make_pyi_async_device_client,
)
from fastapi_frame.clients.make_pyi_sync_device_client import (
    make_pyi_sync_device_client,
)

from server.spec import simple_api_spec


@contextmanager
def chdir(path: str):
    prev_cwd = os.getcwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(prev_cwd)


def main():
    # この make.py と同じディレクトリに .pyi を出力
    out_dir = os.path.dirname(os.path.abspath(__file__))
    with chdir(out_dir):
        make_pyi_async_device_client(
            filename="async_simple_client.pyi",
            api_spec=simple_api_spec,
            class_name="AsyncSimpleClient",
        )
        make_pyi_sync_device_client(
            filename="sync_simple_client.pyi",
            api_spec=simple_api_spec,
            class_name="SyncSimpleClient",
        )


if __name__ == "__main__":
    main()
