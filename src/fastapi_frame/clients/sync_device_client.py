#!/usr/bin/env python
"""
汎用Syncクライアント（API_SPEC駆動・完全sync版）
Kengo NAKADA: https://github.com/shimane-dev, kengo.nakada@gmail.com
"""

import httpx
from typing import Any, Callable, Optional
from x_logger.x_logger import XLogger


class SyncDeviceClient:
    def __init__(
        self,
        server_ip: str = "127.0.0.1",
        server_port: int = 8000,
        base_url: Optional[str] = None,
        api_spec: Optional[list] = None,
        logger: Optional[Any] = None,
    ):
        self._logger = logger or XLogger()
        self._base_url = base_url or f"http://{server_ip}:{server_port}"
        self._client = httpx.Client()

        self._api_spec = api_spec
        if api_spec:
            self._register_api_spec_methods()

    def _post(self, url: str, **kwargs) -> Any:
        try:
            res = self._client.post(url, **kwargs)
            res.raise_for_status()
            return res
        except Exception as e:
            self._logger.error(f"[POST ERROR] {e}")
            return None

    @staticmethod
    def _response(res) -> Any:
        # APIレスポンス(dict) or None
        return res.json() if res is not None else None

    def print_response(self, res: Any) -> None:
        # レスポンス内容をデバッグログに出力
        self._logger.debug(res)

    def _register_api_spec_methods(self) -> None:
        for api in self._api_spec:
            if not hasattr(self, api.name):
                method = self._make_api_method(api)
                setattr(self, api.name, method)

    def _make_api_method(self, api):
        """
        API_SPECエントリからメソッドを生成（引数解釈と戻り値自動化も維持）
        """

        def method(*args, **kwargs):
            self._logger.debug(f"[CLIENT CALL] {api.name} args={args} kwargs={kwargs}")
            # req_data判定（現行設計踏襲）
            if (
                api.request_model
                and len(args) == 1
                and isinstance(args[0], api.request_model)
            ):
                req_data = args[0].dict()
            elif len(args) == 1 and isinstance(args[0], dict):
                req_data = args[0]
            elif api.arg_names and len(args) == len(api.arg_names):
                req_data = {name: arg for name, arg in zip(api.arg_names, args)}
            elif kwargs:
                req_data = kwargs
            else:
                req_data = None

            self._logger.debug(f"[CLIENT REQUEST] {api.name} req_data={req_data}")

            try:
                url = f"{self._base_url}/instance/{api.object_name}/{api.name}"
                resp = self._post(url, json=req_data)
                self._logger.debug(f"[CLIENT RESPONSE] {api.name} resp={resp}")

                if api.response_model and hasattr(api.response_model, "parse_obj"):
                    result = api.response_model.parse_obj(resp.json())
                    self._logger.debug(f"[CLIENT PARSED] {api.name} result={result}")
                    return result
                return resp.json()
            except Exception as e:
                self._logger.error(f"[CLIENT ERROR] {api.name} error: {e}")
                raise

        return method


