#!/usr/bin/env python
# from typing import TYPE_CHECKING
#
# if TYPE_CHECKING:
#     from cobotta_server2.cobotta_ctrl import CobottaCtrl
import re
import inspect

# from starlette.responses import JSONResponse, Response

from fastapi import HTTPException
from fastapi import APIRouter
from fastapi.responses import JSONResponse

# from cobotta_server2.cobotta_ctrl import CobottaCtrl
# from cobotta_server2.server.fastapi.models.api_spec import API_SPECS

from x_logger.x_logger import XLogger
from x_logger.util import *


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
        request_modelから (args, kwargs) を抽出
        - *以降（キーワード専用）は kwargs 側に渡す
        - arg_namesには依存しない（request_model準拠で自動抽出）
        """
        args = []
        kwargs = {}

        # 旧：if api.arg_names and request is not None:
        # 新：request_modelで自動判別
        model_fields = []
        if getattr(api, "request_model", None):
            # pydanticフィールド名（宣言順）
            model_fields = list(api.request_model.__fields__.keys())

        if model_fields and request is not None:
            # request: Pydanticモデルまたはdict
            if hasattr(request, "dict") and callable(request.dict):
                request_dict = request.dict()
            elif isinstance(request, dict):
                request_dict = request
            else:
                request_dict = {}

            # 引数の分離処理
            kwonly = set()
            if target_func:
                sig = inspect.signature(target_func)
                # *以降の引数を取得
                for name, param in sig.parameters.items():
                    if param.kind == inspect.Parameter.KEYWORD_ONLY:
                        kwonly.add(name)

            for i, name in enumerate(model_fields):
                if name in request_dict:
                    if name in kwonly:
                        kwargs[name] = request_dict[name]
                    else:
                        args.append(request_dict[name])

            # kwargsでまだ入れていないものを追加
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

    @staticmethod
    def _wrap_response(result, api):
        """
        戻り値を response_model のフィールド名に合うようラップして返す
        """
        if api.response_model and hasattr(api.response_model, "__fields__"):
            if isinstance(result, dict):
                return api.response_model(**result)
            else:
                field = next(iter(api.response_model.__fields__))
                return api.response_model(**{field: result})
        return result

    def _make_handler(self, api):
        async def handler(request: api.request_model = None):
            try:
                self._logger.info(
                    f"[API CALL] name={api.name} path={api.path} method={api.method} call_type={api.call_type} request={request}"
                )

                target = getattr(self._device, api.name, None)
                if target is None:
                    raise HTTPException(
                        status_code=404, detail=f"Unknown API member: {api.name}"
                    )

                args, kwargs = self._extract_args_kwargs(api, request, target)

                if api.call_type == "method":
                    if inspect.iscoroutinefunction(target):
                        result = await target(*args, **kwargs)
                    else:
                        result = target(*args, **kwargs)
                    self._logger.info(f"[RETURN method] {api.name} result={result}")

                elif api.call_type == "property":
                    result = target
                    self._logger.info(f"[RETURN property] {api.name} result={result}")

                else:
                    raise HTTPException(
                        status_code=500, detail=f"Unknown call_type: {api.call_type}"
                    )

                return self._wrap_response(result, api)

            except Exception as e:
                self._logger.error(f"API {api.name} error: {e}")
                return JSONResponse(status_code=400, content={"error": str(e)})

        return handler

    def __getattr__(self, name) -> dict:
        """instance.P1, instance.P2, ..., F1, F2... の形式にマッチ"""
        m = re.match(r"([PIF])(\d+)$", name)
        if m:
            kind, id_num = m.group(1), int(m.group(2))
            var = getattr(self, f"_var_{kind}")
            var.ID = id_num
            return {"result": var.Value}

        raise AttributeError(
            f"'{type(self).__name__}' object has no attribute '{name}'"
        )

    def __setattr__(self, name, value):
        """instance.P1, instance.P2, ..., F1, F2... の形式にマッチ"""
        if isinstance(name, str):
            m = re.match(r"([PIF])(\d+)$", name)
            if m:
                kind, id_num = m.group(1), int(m.group(2))
                var = object.__getattribute__(self, f"_var_{kind}")
                var.ID = id_num
                var.Value = value
                return
        # それ以外は通常通り
        super().__setattr__(name, value)

    #
    # @var
    #

    # async def P1(self):
    #     ret = self._cobotta.P1
    #     self._logger.info(f"busy_status = {ret}")
    #     return {"result": str(ret)}

    # async def P2(self):
    #     ret = self._cobotta.P2
    #     self._logger.info(f"busy_status = {ret}")
    #     return {"result": str(ret)}

    #
    # command
    #
