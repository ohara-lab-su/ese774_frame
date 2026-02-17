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

from fastapi import HTTPException, APIRouter, Request
from fastapi.responses import JSONResponse

from fastapi_frame import adapter

import logging

# from x_logger.x_logger import XLogger
# from x_logger.util import *

logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


class DeviceRouter:
    """
    device_instance + api_spec から FastAPI ルートを生成する。

    責務:
    - request_model に基づく入力受理
    - API名から device/router メンバ解決
    - 実呼び出し時の args/kwargs 展開
    - response_model 契約に沿った返却形への整形
    - __dispatch__ 汎用エンドポイント提供
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
    def _model_field_names(model_cls) -> list[str]:
        v2_fields = getattr(model_cls, "model_fields", None)
        if isinstance(v2_fields, dict):
            return list(v2_fields.keys())
        return list(getattr(model_cls, "__fields__", {}).keys())

    @staticmethod
    def _extract_args_kwargs(
        api,
        request,
        target_func=None,
    ):
        """
        request を target_func 呼び出し用の (args, kwargs) に展開する。

        ルール:
        - request_model フィールド順で positional 値を構成
        - target_func の keyword-only 引数は kwargs 側へ強制
        - request_model が無い場合は dict を kwargs、非dict を単一 args 扱い
        """
        args = []
        kwargs = {}

        model_fields = []
        req_model = getattr(api, "request_model", None)
        if req_model is not None:
            v2_fields = getattr(req_model, "model_fields", None)
            if isinstance(v2_fields, dict):
                model_fields = list(v2_fields.keys())
            else:
                model_fields = list(getattr(req_model, "__fields__", {}).keys())

        if model_fields and request is not None:
            # pydantic / dict / その他を dict に正規化
            if hasattr(request, "model_dump") and callable(request.model_dump):
                request_dict = request.model_dump()
            elif hasattr(request, "dict") and callable(request.dict):
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
            if hasattr(request, "model_dump") and callable(request.model_dump):
                kwargs = request.model_dump()
            elif hasattr(request, "dict") and callable(request.dict):
                kwargs = request.dict()
            elif isinstance(request, dict):
                kwargs = request
            else:
                args = [request]

        return args, kwargs

    @staticmethod
    def _wrap_response(result, api):
        """
        ctrl の戻り値を response_model 契約に合わせる。

        - response_model が無ければそのまま返す
        - modelインスタンスは dict 化
        - 単一フィールド model は暗黙ラップを許可
        - 多フィールド model へスカラー返却は契約違反として TypeError
        """
        model_cls = getattr(api, "response_model", None)
        if model_cls is None:
            return result

        field_names = DeviceRouter._model_field_names(model_cls)
        if not field_names:
            return result

        try:
            if isinstance(result, model_cls):
                if hasattr(result, "model_dump"):
                    return result.model_dump()
                if hasattr(result, "dict"):
                    return result.dict()
                return result
        except TypeError:
            return result

        if isinstance(result, dict):
            return result

        # 単一フィールドのみ自動ラップ
        if len(field_names) == 1:
            return {field_names[0]: result}

        # 多フィールドは暗黙ラップしない（契約違反を明示）
        raise TypeError(
            f"response_model={model_cls.__name__} requires dict/model, got {type(result).__name__}"
        )

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
        async def handler(
            request: api.request_model = None, raw_request: Request = None
        ):
            try:
                self._logger.info(f"[API CALL] {api.name}")

                # I/F未定義キーを明示的に422にする
                req_model = getattr(api, "request_model", None)
                if req_model is not None and raw_request is not None:
                    try:
                        raw_payload = await raw_request.json()
                    except Exception:
                        raw_payload = None

                    if isinstance(raw_payload, dict):
                        allowed = set(self._model_field_names(req_model))
                        unknown = sorted(set(raw_payload.keys()) - allowed)
                        if unknown:
                            detail = [
                                {
                                    "loc": ["body", key],
                                    "msg": "extra field not permitted",
                                    "type": "value_error.extra",
                                }
                                for key in unknown
                            ]
                            raise HTTPException(status_code=422, detail=detail)

                target = self._dispatch_api(api, request)
                args, kwargs = self._extract_args_kwargs(api, request, target)

                if target is None:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Unknown API member: {api.name}",
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

                return self._wrap_response(result, api)

            except HTTPException:
                raise
            except Exception as e:
                self._logger.exception(f"API {api.name} unexpected error")
                raise HTTPException(status_code=500, detail=str(e))

        return handler

    async def _dispatch_handler(self, request: dict):
        try:
            if not isinstance(request, dict):
                raise HTTPException(
                    status_code=422, detail="request body must be object"
                )

            unknown = sorted(set(request.keys()) - {"method", "args", "kwargs"})
            if unknown:
                raise HTTPException(
                    status_code=422,
                    detail=f"unknown keys in dispatch payload: {unknown}",
                )

            method = request.get("method")
            if not method:
                raise HTTPException(
                    status_code=400,
                    detail="method is required",
                )

            target = getattr(self._device, method, None)
            if target is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"No such method: {method}",
                )

            args = adapter.unpack_args(request.get("args"))
            kwargs = adapter.unpack_kwargs(request.get("kwargs"))

            if callable(target):
                if inspect.iscoroutinefunction(target):
                    result = await target(*args, **kwargs)
                else:
                    result = target(*args, **kwargs)
            else:
                result = target

            return JSONResponse(content=adapter.pack_result(result))

        except HTTPException:
            raise
        except Exception as e:
            self._logger.exception("dispatch unexpected error")
            raise HTTPException(status_code=500, detail=str(e))
