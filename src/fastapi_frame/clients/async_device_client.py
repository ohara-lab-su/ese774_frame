#!/usr/bin/env python
"""
FastAPI 用の汎用 async クライアント。

- api_spec からメソッドを動的生成
- HTTP で device API を呼び出し
- adapter で args/kwargs/result を pack/unpack

Kengo NAKADA:
https://github.com/shimane-dev, https://github.com/kengo-nakada
kengo.nakada@mat.shimane-u.ac.jp, kengo.nakada@gmail.com
"""

import httpx
import asyncio
from typing import Any, Callable, Optional

from fastapi_frame import adapter


class AsyncDeviceClient:
    """
    FastAPI サーバーに対する async クライアント。
    """

    def __init__(
        self,
        server_ip: str = "127.0.0.1",
        server_port: int = 8000,
        base_url: Optional[str] = None,
        api_spec: Optional[list] = None,
        logger: Optional[Any] = None,
        log_level: Optional[str] = None,
        object_name: str = "device",
    ):
        if logger is None:
            import logging

            log_level = log_level or "INFO"
            logging.basicConfig(level=log_level.upper())
            logger = logging.getLogger(__name__)

        self._logger = logger
        self._base_url = base_url or f"http://{server_ip}:{server_port}"
        self._client = httpx.AsyncClient()
        self._object_name = object_name

        if api_spec:
            self._object_name = api_spec[0].object_name

        self._logger.info(f"[SERVER IP] {server_ip}")
        self._logger.info(f"[SERVER PORT] {server_port}")
        self._logger.info(f"[BASE URL] {base_url}")

        self._api_spec = api_spec
        if api_spec:
            self._register_api_spec_methods()

    def _register_api_spec_methods(self) -> None:
        """api_spec に基づいてメソッドを動的に追加する。"""

        self._logger.debug("[CLIENT REGISTER] API_SPEC")

        for api in self._api_spec:
            self._logger.debug(f"[CREATE METHOD FROM API_SPEC] {api.name}")
            method = self._make_api_method(api)
            if not hasattr(self, api.name):
                self._logger.debug(f"[CLIENT REGISTER] {api.name}")
                setattr(self, api.name, method)

            # raw 名で必ず退避
            # 継承先でオーバーライトしたときの呼び出し退避用
            raw_name = f"_{api.name}_raw"
            self._logger.debug(f"[CLIENT REGISTER(row)] {raw_name}")
            setattr(self, raw_name, method)

    def _make_api_method(
        self,
        api: Any,
    ) -> Any:
        """api_spec 1件分の呼び出し関数を生成する。"""

        async def method(*args, **kwargs):
            self._logger.debug(f"[CLIENT CALL] {api.name} args={args} kwargs={kwargs}")

            # request_model のフィールド順を使って args を kwargs 化
            model_fields = []
            if getattr(api, "request_model", None):
                model_fields = list(api.request_model.__fields__.keys())

            if model_fields and args:
                req_data = {name: arg for name, arg in zip(model_fields, args)}
                req_data.update(kwargs)
            elif kwargs:
                req_data = kwargs
            elif len(args) == 1 and isinstance(args[0], dict):
                req_data = args[0]
            elif len(args) == 1 and hasattr(api.request_model, "parse_obj"):
                req_data = args[0].dict()
            else:
                req_data = None

            # request_model のデフォルト値を補完
            if getattr(api, "request_model", None) and isinstance(req_data, dict):
                fields = api.request_model.__fields__
                for key, f in fields.items():
                    if key not in req_data and f.default is not None:
                        req_data[key] = f.default

            self._logger.info(f"[CLIENT REQUEST] {api.name} req_data={req_data}")

            try:
                # API 呼び出し
                url = f"{self._base_url}/instance/{api.object_name}/{api.name}"
                resp = await self._post(url, json=req_data)
                self._logger.debug(f"[CLIENT RESPONSE] {api.name} resp={resp}")

                if resp is None:
                    return None

                # adapter で復元して返す
                payload = resp.json()
                return adapter.unpack_result(payload)

            except Exception as e:
                self._logger.error(f"[CLIENT ERROR] {api.name} error: {e}")
                raise

        method.__name__ = api.name
        return method

    async def dispatch(
        self,
        method: str,
        *args,
        **kwargs,
    ) -> Any:
        """
        一般形ディスパッチ (*args, **kwargs)

        payload = {"method": str, "args": <packed>, "kwargs": <packed>}
        """
        payload = {
            "method": method,
            "args": adapter.pack_args(args),
            "kwargs": adapter.pack_kwargs(kwargs),
        }
        url = f"{self._base_url}/instance/{self._object_name}/__dispatch__"
        resp = await self._post(url, json=payload)
        if resp is None:
            return None
        return adapter.unpack_result(resp.json())

    async def _post(
        self,
        url: str,
        **kwargs,
    ) -> Any:
        """httpx.AsyncClient の薄いラッパー。"""

        try:
            res = await self._client.post(url, **kwargs)
            res.raise_for_status()
            return res
        except Exception as e:
            self._logger.error(str(e))
            return None
