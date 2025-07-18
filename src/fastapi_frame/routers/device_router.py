#!/usr/bin/env python
# from typing import TYPE_CHECKING
#
# if TYPE_CHECKING:
#     from cobotta_server2.cobotta_ctrl import CobottaCtrl
import re
import inspect
from pprint import pformat

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
            APIリクエスト用のPydanticモデルやdictから、Python関数呼び出し用の
            (args, kwargs)タプルを抽出する。

            - pydanticモデルなら、フィールド順（宣言順）でargs/kwargsに詰める。
            - 関数側に*以降（キーワード専用）引数があれば、kwargsへ。
            - requestがdictでなければargs[0]に詰める。
            - target_funcのsignatureからkwonly（キーワード専用引数）も抽出。
            - FastAPIのrouter動的ディスパッチ機構で利用。

            Parameters
            ----------
            api : object
                api_specで定義されているAPI情報オブジェクト。
                通常は request_model 属性を持つ（pydanticモデル型）。
            request : Any
                リクエストボディ。pydanticモデルまたはdictまたは任意。
            target_func : Optional[Callable]
                ディスパッチ対象のPython関数本体（キーワード専用引数判定用）。
                Noneの場合は全てargs/kwargsはmodel順に割当。

            Returns
            -------
            args : list
                Python関数の位置引数に詰める値リスト。
            kwargs : dict
                Python関数のキーワード引数に詰める値dict。
        """
        args = []
        kwargs = {}

        # モデル（Pydantic等）のフィールド名リストを取得
        model_fields = []
        if getattr(api, "request_model", None):
            # pydanticフィールド名（宣言順）
            model_fields = list(api.request_model.__fields__.keys())

        # Pydanticモデル or dictからの抽出（通常はこちらがメイン分岐）
        if model_fields and request is not None:
            # request: Pydanticモデルまたはdict
            if hasattr(request, "dict") and callable(request.dict):
                request_dict = request.dict()
            elif isinstance(request, dict):
                request_dict = request
            else:
                request_dict = {}

            # 引数の分離処理
            # 対象関数（実装メソッド）のシグネチャからキーワード専用引数名を抽出
            kwonly = set()
            if target_func:
                sig = inspect.signature(target_func)
                # *以降の引数を取得
                for name, param in sig.parameters.items():
                    if param.kind == inspect.Parameter.KEYWORD_ONLY:
                        kwonly.add(name)

            # モデル宣言順にargs/kwargsへ値を分配
            for i, name in enumerate(model_fields):
                if name in request_dict:
                    # キーワード専用引数ならkwargsへ、それ以外はargsへ
                    if name in kwonly:
                        kwargs[name] = request_dict[name]
                    else:
                        args.append(request_dict[name])

            # モデルに無いがリクエストに含まれる余剰フィールドやkwonly引数はkwargsへ
            # kwargsでまだ入れていないものを追加
            for k, v in request_dict.items():
                if k not in model_fields or k in kwonly:
                    kwargs[k] = v

        # モデルが無い場合は、単純にrequestをargs/kwargsへ振り分け
        elif request is not None:
            # pydanticモデルならdict化、dictならそのまま、どちらでもなければargsへ
            if hasattr(request, "dict") and callable(request.dict):
                kwargs = request.dict()
            elif isinstance(request, dict):
                kwargs = request
            else:
                args = [request]

        # 最終的に (args, kwargs) で返す
        return args, kwargs

    def _get_api_spec(self, method_name: str):
        """
        method_name で api_spec リストから ApiSpec オブジェクトを返す
        """
        for api in self._api_spec:
            if api.name == method_name:
                return api
        raise ValueError(f"[device_router] No such api_spec for: {method_name}")

    def wrap_with_response_model(self, method_name: str, result):
        """
        api_spec から response_model を取得し、型にラップして返す
        変換失敗時はエラー内容・データ内容を詳細にロギングして例外送出
        """
        api = self._get_api_spec(method_name)
        return self._wrap_response(result, api)

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

    def _dispatch_api(self, api, request):
        """
        Routerサブクラス、もしくはデバイス本体（_device）の順で
        property/method/attribute を探索し、返す。
        """
        # まず Router側を優先して探索
        if hasattr(self, api.name):
            return getattr(self, api.name)
        # 次に DeviceCtrl 側を探索
        if hasattr(self._device, api.name):
            return getattr(self._device, api.name)
        # どちらにもなければエラー
        raise AttributeError(f"No such method/property: {api.name}")

    def _make_handler(self, api):
        async def handler(request: api.request_model = None):
            try:
                self._logger.info(
                    f"[API CALL] name={api.name} path={api.path} method={api.method} request={request}"
                )

                # targetは「callable/propertyどちらもあり得る」
                target = self._dispatch_api(api, request)
                # target = getattr(self._device, api.name, None)

                # 引数抽出
                args, kwargs = self._extract_args_kwargs(api, request, target)

                if target is None:
                    raise HTTPException(
                        status_code=404, detail=f"Unknown API member: {api.name}"
                    )

                # ターゲットがcallableなら関数/コルーチン実行。そうでなければプロパティとして返す。
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

            except Exception as e:
                self._logger.error(f"API {api.name} error: {e}")
                return JSONResponse(status_code=400, content={"error": str(e)})

        return handler

