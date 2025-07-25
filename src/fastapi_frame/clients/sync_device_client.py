#!/usr/bin/env python
"""
汎用Syncクライアント（API_SPEC駆動・完全sync版）
Kengo NAKADA: https://github.com/shimane-dev, kengo.nakada@gmail.com
"""

import httpx
from typing import Any, Callable, Optional
from x_logger.x_logger import XLogger

import asyncio
from fastapi_frame.clients.async_device_client import AsyncDeviceClient


class SyncDeviceClient(AsyncDeviceClient):
    def __init__(
        self,
        server_ip: str,
        server_port: int,
        base_url: Optional[str] = None,
        api_spec: Optional[list] = None,
        logger: Optional[Any] = None,
    ):
        super().__init__(server_ip, server_port, base_url, api_spec, logger)

        # 各APIメソッドを同期ラップで再定義
        self._register_sync_api_spec_methods(api_spec)

    def _sync_wrap(self, coro):
        try:
            # 既存ループ外なら新規作成
            return asyncio.run(coro)
        except RuntimeError:
            # 既存ループ内ならnest_asyncioで流用
            import nest_asyncio

            nest_asyncio.apply()
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(coro)

    def _register_sync_api_spec_methods(self, api_spec):
        for api in api_spec:
            async_method = getattr(self, api.name)

            def make_sync_method(async_method):
                def sync_method(*args, **kwargs):
                    return self._sync_wrap(async_method(*args, **kwargs))

                return sync_method

            setattr(self, api.name, make_sync_method(async_method))
