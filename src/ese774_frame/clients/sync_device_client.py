#!/usr/bin/env python
"""
汎用Syncクライアント（API_SPEC駆動・完全sync版）
Kengo NAKADA: https://github.com/shimane-dev, kengo.nakada@gmail.com
"""

import asyncio
from typing import Any, Optional
from ese774_frame.clients.async_device_client import AsyncDeviceClient


class SyncDeviceClient(AsyncDeviceClient):
    """
    AsyncDeviceClient を同期インターフェースで提供するラッパ。

    各 API メソッドを同期ラップし、
    dispatch も同期呼び出しで利用できるようにする。
    """

    def __init__(
        self,
        server_ip: str,
        server_port: int,
        base_url: Optional[str] = None,
        api_spec: Optional[list] = None,
        logger: Optional[Any] = None,
        log_level: str = "INFO",
        object_name: str = "device",
    ):
        self._loop = asyncio.new_event_loop()

        super().__init__(
            server_ip=server_ip,
            server_port=server_port,
            base_url=base_url,
            api_spec=api_spec,
            logger=logger,
            log_level=log_level,
            object_name=object_name,
        )
        self._register_sync_api_spec_methods(api_spec)

    # @staticmethod
    # def _sync_wrap(coro):
    #     """
    #     coroutine を同期実行する。

    #     通常は asyncio.run() を使い、
    #     既存イベントループ環境では nest_asyncio + run_until_complete で実行する。
    #     """
    #     try:
    #         return asyncio.run(coro)
    #     except RuntimeError:
    #         import nest_asyncio

    #         nest_asyncio.apply()
    #         loop = asyncio.get_event_loop()
    #         return loop.run_until_complete(coro)
    def _sync_wrap(self, coro):
        """
        coroutine を同期実行する。

        AsyncDeviceClient が保持する httpx.AsyncClient を同じ event loop 上で使い続ける。
        """
        if self._loop.is_closed():
            self._loop = asyncio.new_event_loop()

        return self._loop.run_until_complete(coro)

    def _register_sync_api_spec_methods(self, api_spec):
        for api in api_spec or []:
            async_method = getattr(self, api.name)

            def make_sync_method(async_method):
                def sync_method(*args, **kwargs):
                    return self._sync_wrap(async_method(*args, **kwargs))

                return sync_method

            setattr(self, api.name, make_sync_method(async_method))

    def dispatch(self, method: str, *args, **kwargs) -> Any:
        return self._sync_wrap(super().dispatch(method, *args, **kwargs))
