#!/usr/bin/env python
"""
Kengo NAKADA:
https://github.com/shimane-dev, https://github.com/kengo-nakada
kengo.nakada@mat.shimane-u.ac.jp, kengo.nakada@gmail.com
"""
import re
import inspect
from pprint import pformat

import logging

logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

from fastapi import HTTPException
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from x_logger.x_logger import XLogger
from x_logger.util import *

from fastapi_frame import adapter


class DeviceRouter:

    def __init__(self, device_instance, api_spec=None, logger: XLogger = None):
        """
        app = FastAPI()
        app に食わせる CobottaCtrl 用の I/F Class
        エンドポイントの定義用

        Args:
            device_instance:
            api_spec:
            logger:
        """
        self._logger: XLogger = logger or get_silent_logger()

        # DeviceCtrl
        self._device = device_instance

        # ApiSpec
        self._api_spec = api_spec

        # FastAPI 依存している唯一のクラス
        self.router: APIRouter = APIRouter()

        if not api_spec:
            self._logger.warning("No API Spec")
            return  # コンストラクタが途中中断するだけ(インスタンスはそのまま生成)

        # API の登録
        for api in api_spec:
            handler = self._make_handler(api)

            if api.method == "post":
                self.router.post(
                    api.path,
                    response_model=api.response_model,
                    description=api.description,
                    summary=api.summary,
                )(handler)

            elif api.method == "get":
                self.router.get(
                    api.path,
                    response_model=api.response_model,
                    description=api.description,
                    summary=api.summary,
                )(handler)

    @staticmethod
    def _extract_args_kwargs(api, request, target_func=None):
        """
        APIリクエスト用のPydanticモデルやdictから、Python関数呼び出し用の
        (args, kwargs)タプルを抽出する。

        Args:
            api : object
                api_specで定義されているAPI情報オブジェクト。
            request : Any
                リクエストボディ。pydanticモデルまたはdictまたは任意。
            target_func : Optional[Callable]
                ディスパッチ対象のPython関数本体（キーワード専用引数判定用）。

        Returns:
            args : list
            kwargs : dict
        """
        args = []
        kwargs = {}

        model_fields = []
        if getattr(api, "request_model", None):
            model_fields = list(api.request_model.__fields__.keys())

        if model_fields and request is not None:
            if hasattr(request, "dict") and callable(request.dict):
                request_dict = request.dict()
            elif isinstance(request, dict):
                request_dict = request
            else:
                request_dict = {}

            kwonly = set()
            if target_func:
                sig = inspect.signature(target_func)
                for name, param in sig.parameters.items():
                    if param.kind == inspect.Parameter.KEYWORD_ONLY:
                        kwonly.add(name)

            for i, name in enumerate(model_fields):
                if name in request_dict:
                    if name in kwonly:
                        kwargs[name] = request_dict[name]
                    else:
                        args.append(request_dict[name])

            for k, v in request_dict.items():
                if k not in model_fields or k in kwonly:
                    kwargs[k] = v

        elif request is not None:
            if hasattr(request, "dict") and callable(request.dict):
                kwargs = request.dict()
            elif isinstance(request, dict):
                kwargs = request
            else:
                args = [request]

        return args, kwargs

    def _get_api_spec(self, method_name: str):
        for api in self._api_spec:
            if api.name == method_name:
                return api
        raise ValueError(f"[device_router] No such api_spec for: {method_name}")

    def _dispatch_api(self, api, request):
        if hasattr(self, api.name):
            self._logger.info(f"[Router CALL] {api.name}, path={api.path}")
            return getattr(self, api.name)

        if hasattr(self._device, api.name):
            self._logger.info(f"[DeviceCtrl CALL] {api.name}, path={api.path}")
            return getattr(self._device, api.name)

        raise AttributeError(f"No such method/property: {api.name}")

    def _make_handler(self, api):
        async def handler(request: api.request_model = None):
            try:
                self._logger.info(f"[API CALL] {api.name}")

                target = self._dispatch_api(api, request)

                args, kwargs = self._extract_args_kwargs(api, request, target)

                if target is None:
                    raise HTTPException(
                        status_code=404, detail=f"Unknown API member: {api.name}"
                    )

                if callable(target):
                    if inspect.iscoroutinefunction(target):
                        result = await target(*args, **kwargs)
                    else:
                        result = target(*args, **kwargs)
                    self._logger.info(f"[RETURN method] {api.name} result={result}")
                else:
                    result = target
                    self._logger.info(f"[RETURN property] {api.name} result={result}")

                # 返り値は常に adapter でパック（pydantic には渡さない）
                return JSONResponse(content=adapter.pack_result(result))

            except Exception as e:
                self._logger.error(f"API {api.name} error: {e}")
                return JSONResponse(status_code=400, content={"error": str(e)})

        return handler
