#!/usr/bin/env python
"""

Kengo NAKADA:
https://github.com/shimane-dev, https://github.com/kengo-nakada
kengo.nakada@mat.shimane-u.ac.jp, kengo.nakada@gmail.com
"""
import httpx
import asyncio
from typing import Any


# for state

from x_logger.x_logger import XLogger
from x_logger.util import *


class AsyncDeviceClient:

    def __init__(
        self,
        server_ip,
        server_port,
        api_spec,
        base_url=None,
        logger=None,
    ):
        self._api_spec = api_spec
        if base_url is None:
            base_url = f"http://{server_ip}:{server_port}"
        self._base_url = base_url
        self._client = httpx.AsyncClient()
        self._logger = logger or get_silent_logger()

        # API 登録(ctrl)
        self._register_api_spec_methods()

    async def _post(self, url: str, **kwargs) -> Any:
        # POST送信（例外時はログ出力）
        try:
            res = await self._client.post(url, **kwargs)
            res.raise_for_status()
            return res
        except Exception as e:
            self._logger.error(str(e))
            return None

    def _register_api_spec_methods(self) -> None:
        for api in self._api_spec:
            if not hasattr(self, api.name):
                method = self._make_api_method(api)
                setattr(self, api.name, method)

    # def _register_api_spec_methods(self, base_url: str) -> None:
    #     # API_SPECから動的にAPIメソッドを生やす
    #     for api in self._api_spec:
    #         if not hasattr(self, api.name):
    #             method = self._make_api_method(api, base_url)
    #             setattr(self, api.name, method)

    @staticmethod
    def auto_extract_result(obj):
        if hasattr(obj, "dict") and callable(getattr(obj, "dict")):
            d = obj.dict()
            if len(d) == 1:
                return next(iter(d.values()))
            else:
                return d
        else:
            return obj

        # def _make_api_method(self, api: Any, base_url: str) -> Any:

    def _make_api_method(self, api: Any) -> Any:
        """
        各 API_SPEC から動的に API メソッドを生成

        Args:
            api (API_SPEC): API_SPEC
            base_url (str):

        Returns:

        """

        async def method(*args, **kwargs):
            self._logger.debug(f"[CLIENT CALL] {api.name} args={args} kwargs={kwargs}")

            # 位置＋キーワード引数を dict 化
            if api.arg_names:
                req_data = {name: arg for name, arg in zip(api.arg_names, args)}
                req_data.update(kwargs)

            elif kwargs:
                req_data = kwargs

            elif len(args) == 1 and isinstance(args[0], dict):
                req_data = args[0]

            elif len(args) == 1 and hasattr(api.request_model, "parse_obj"):
                req_data = args[0].dict()

            else:
                req_data = None

            self._logger.debug(f"[CLIENT REQUEST] {api.name} req_data={req_data}")

            try:
                # url = f"{base_url}/{api.name}"
                # url = f"{self._base_url}/instance/cobotta/{api.name}"
                url = f"{self._base_url}/instance/{api.object_name}/{api.name}"
                resp = await self._post(url, json=req_data)
                self._logger.debug(f"[CLIENT RESPONSE] {api.name} resp={resp}")

                if (
                    api.response_model
                    and hasattr(api.response_model, "parse_obj")
                    and resp is not None
                ):
                    result = api.response_model.parse_obj(resp.json())
                    self._logger.debug(f"[CLIENT PARSED] {api.name} result={result}")
                    return self.auto_extract_result(result)
                    # return result

                return resp.json() if resp is not None else None

            except Exception as e:
                self._logger.error(f"[CLIENT ERROR] {api.name} error: {e}")
                raise

        method.__name__ = api.name
        return method


