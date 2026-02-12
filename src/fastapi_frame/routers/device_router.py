#!/usr/bin/env python
"""
FastAPI 用 DeviceRouter

- api_spec に従ってルートを動的生成
- device のメソッド/プロパティを透過的に公開
- args/kwargs の抽出と adapter の pack/unpack を一括処理

Kengo NAKADA:
https://github.com/shimane-dev, https://github.com/kengo-nakada
kengo.nakada@mat.shimane-u.ac.jp, kengo.nakada@gmail.com
"""

import inspect
from typing import Any, Callable, Optional

from fastapi import HTTPException, APIRouter
from fastapi.responses import JSONResponse

from fastapi_frame import adapter

import logging

# from x_logger.x_logger import XLogger
# from x_logger.util import *

logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


class DeviceRouter:
    """
    device_instance と api_spec から FastAPI のルートを生成する。
    """

    def __init__(
        self,
        device_instance,
        api_spec=None,
        logger: Optional[Any] = None,
        log_level: Optional[str] = None,
    ):
        # XLogger が存在しない時に仕方がないのでデフォルトの logging を使う
        if logger is None:

            log_level = log_level or "INFO"
            logging.basicConfig(level=log_level.upper())
            logger = logging.getLogger(__name__)

        # self._logger: XLogger = logger or get_silent_logger()
        self._logger = logger

        self._device = device_instance
        self._api_spec = api_spec
        self.router: APIRouter = APIRouter()

        if not api_spec:
            self._logger.warning("No API Spec")
            return

        # object_name は spec から取得
        self._object_name = api_spec[0].object_name

        # 通常 API を登録（post/get）
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

        # 一般形ディスパッチ API（*args, **kwargs）
        self.router.post(f"/instance/{self._object_name}/__dispatch__")(
            self._dispatch_handler
        )

    @staticmethod
    def _extract_args_kwargs(
        api,
        request,
        target_func=None,
    ):
        """
        request_model の定義と target_func のシグネチャから
        args/kwargs を組み立てる。
        """
        args = []
        kwargs = {}

        model_fields = []
        if getattr(api, "request_model", None):
            model_fields = list(api.request_model.__fields__.keys())

        if model_fields and request is not None:
            # pydantic / dict / その他を dict に正規化
            if hasattr(request, "dict") and callable(request.dict):
                request_dict = request.dict()
            elif isinstance(request, dict):
                request_dict = request
            else:
                request_dict = {}

            # target_func の kw-only 引数を検出
            kwonly = set()
            if target_func:
                sig = inspect.signature(target_func)
                for name, param in sig.parameters.items():
                    if param.kind == inspect.Parameter.KEYWORD_ONLY:
                        kwonly.add(name)

            # モデル定義の順番に args を積み、kw-only は kwargs へ
            for name in model_fields:
                if name in request_dict:
                    if name in kwonly:
                        kwargs[name] = request_dict[name]
                    else:
                        args.append(request_dict[name])

            # 余剰項目や kw-only は kwargs に回す
            for k, v in request_dict.items():
                if k not in model_fields or k in kwonly:
                    kwargs[k] = v

        elif request is not None:
            # request_model が無い場合は dict か単一引数として扱う
            if hasattr(request, "dict") and callable(request.dict):
                kwargs = request.dict()
            elif isinstance(request, dict):
                kwargs = request
            else:
                args = [request]

        return args, kwargs

    def _dispatch_api(
        self,
        api,
        request,
    ):
        """
        Router 側 or Device 側のメソッド/プロパティを解決する。
        """
        if hasattr(self, api.name):
            self._logger.info(f"[Router CALL] {api.name}, path={api.path}")
            return getattr(self, api.name)

        if hasattr(self._device, api.name):
            self._logger.info(f"[DeviceCtrl CALL] {api.name}, path={api.path}")
            return getattr(self._device, api.name)

        raise AttributeError(f"No such method/property: {api.name}")

    def _make_handler(
        self,
        api,
    ):
        """
        api_spec 1件分の FastAPI handler を生成する。
        """

        async def handler(request: api.request_model = None):
            try:
                self._logger.info(f"[API CALL] {api.name}")

                target = self._dispatch_api(api, request)
                args, kwargs = self._extract_args_kwargs(api, request, target)

                if target is None:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Unknown API member: {api.name}",
                    )

                # method 呼び出し or property 参照を分岐
                if callable(target):
                    if inspect.iscoroutinefunction(target):
                        result = await target(*args, **kwargs)
                    else:
                        result = target(*args, **kwargs)
                    self._logger.info(f"[RETURN method] {api.name} result={result}")
                else:
                    result = target
                    self._logger.info(f"[RETURN property] {api.name} result={result}")

                # adapter で pack して返す
                return JSONResponse(
                    content=adapter.pack_result(result),
                )

            except Exception as e:
                self._logger.error(f"API {api.name} error: {e}")
                return JSONResponse(
                    status_code=400,
                    content={"error": str(e)},
                )

        return handler

    async def _dispatch_handler(self, request: dict):
        """
        一般形ディスパッチ:
        request = {"method": str, "args": <packed>, "kwargs": <packed>}
        """
        try:
            method = request.get("method")
            if not method:
                raise HTTPException(
                    status_code=400,
                    detail="method is required",
                )

            # device のメソッドを動的に解決
            target = getattr(self._device, method, None)
            if target is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"No such method: {method}",
                )

            # adapter で args/kwargs を復元
            args = adapter.unpack_args(request.get("args"))
            kwargs = adapter.unpack_kwargs(request.get("kwargs"))

            # method 呼び出し or property 参照を分岐
            if callable(target):
                if inspect.iscoroutinefunction(target):
                    result = await target(*args, **kwargs)
                else:
                    result = target(*args, **kwargs)
            else:
                result = target

            return JSONResponse(
                content=adapter.pack_result(result),
            )

        except Exception as e:
            self._logger.error(f"dispatch error: {e}")
            return JSONResponse(
                status_code=400,
                content={"error": str(e)},
            )
