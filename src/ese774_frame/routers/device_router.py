#!/usr/bin/env python
"""
FastAPI 用 DeviceRouter

実際にハンドラーメソッドが動くところ

- api_spec に従ってルートを動的生成
- device のメソッド/プロパティを透過的に公開
- args/kwargs の抽出と adapter の pack/unpack を一括処理

設計思想:
    - Router は「透過プロキシ」である
    - FastAPI/Pydantic は入出力契約の検証のみを担当
    - 実処理ロジックは device_instance 側に存在
    - API名とメンバ名は 1:1 対応させる

Kengo NAKADA:
https://github.com/shimane-dev, https://github.com/kengo-nakada
kengo.nakada@mat.shimane-u.ac.jp, kengo.nakada@gmail.com
"""

import inspect
from typing import Any, Callable, Optional, List, Dict, Union, Tuple, TypeVar

from fastapi import HTTPException, APIRouter, Request
from fastapi.responses import JSONResponse

from ese774_frame import adapter

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

    本クラスは「透過型プロキシ」として振る舞い、
    device_instance の API を HTTP レイヤーに公開する。
    """

    def __init__(
        self,
        device_instance: Any,
        api_spec=None,
        logger: Optional[Any] = None,
        log_level: Optional[str] = None,
        object_name: Optional[str] = None,
        dispatch_exclude: Optional[List[str]] = None,
    ):
        """
        Args:
            device_instance: 実デバイスオブジェクト。
            api_spec: ApiSpec のリスト。ルート生成の契約情報。
                      None の場合は完全自動 dispatch モード。
            logger: ロガー。未指定時は logging を使用。
            log_level: logger 未指定時のログレベル。
            object_name: 自動 dispatch モードで使う公開オブジェクト名。
            dispatch_exclude: 自動 dispatch モードで追加非公開にする API 名。
        """
        # XLogger が存在しない時に仕方がないのでデフォルトの logging を使う
        if logger is None:

            log_level = log_level or "INFO"
            logging.basicConfig(level=log_level.upper())
            logger = logging.getLogger(__name__)

        # self._logger: XLogger = logger or get_silent_logger()
        self._logger = logger

        self._device = device_instance
        self._api_spec = api_spec
        self._auto_dispatch = api_spec is None
        self._dispatch_exclude = set(dispatch_exclude or [])
        self.router: APIRouter = APIRouter()

        if api_spec is not None:
            # 既存モードでは object_name を従来どおり spec から取得する。
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
        else:
            # 拡張モード:
            # ApiSpec/Pydantic を要求せず、device の public API を原則公開する。
            # '_' で始まる API と dispatch_exclude 指定 API は非公開。
            self._object_name = object_name or self._infer_object_name(device_instance)
            self._logger.info(
                f"[AUTO DISPATCH] object={self._object_name} "
                f"exclude={sorted(self._dispatch_exclude)}"
            )

        # 一般形ディスパッチ API（*args, **kwargs）
        # ApiSpec の有無に関係なく transport core として提供する。
        self.router.post(f"/instance/{self._object_name}/__dispatch__")(
            self._dispatch_handler
        )

        if self._auto_dispatch:
            # 既存の ApiSpec クライアントも変更せず利用できるよう、
            # /instance/<object>/<api_name> を汎用的に受ける。
            # server 側には ApiSpec/Pydantic model を要求しない。
            self.router.api_route(
                f"/instance/{self._object_name}/{{method_name}}",
                methods=["POST", "GET"],
            )(self._dynamic_api_handler)

    @staticmethod
    def _infer_object_name(device_instance: Any) -> str:
        """
        device class から完全動的モードの object_name を推定する。

        明示 object_name が無い場合だけ使用する。機器固有名は持たず、
        class 名末尾の一般的な制御クラス接尾辞を除去して小文字化する。
        例: FooCtrl -> foo, BarController -> bar。
        """
        cls = type(device_instance)

        for attr_name in ("object_name", "OBJECT_NAME"):
            value = inspect.getattr_static(cls, attr_name, None)
            if isinstance(value, str) and value:
                return value

        name = cls.__name__
        for suffix in ("Controller", "Ctrl", "Device"):
            if name.endswith(suffix) and len(name) > len(suffix):
                name = name[: -len(suffix)]
                break

        return name.lower() or "device"

    def _get_dynamic_target(self, method: str) -> Any:
        """完全動的モードで公開可能な device member を1回だけ取得する。"""
        if not isinstance(method, str) or not method:
            raise HTTPException(status_code=400, detail="method is required")

        if method.startswith("_") or method in self._dispatch_exclude:
            raise HTTPException(
                status_code=404,
                detail=f"No such method: {method}",
            )

        # hasattr() は property getter を実行するため使用しない。
        # getattr_static() で存在だけを確認し、実値の取得は getattr() 1回に限定する。
        try:
            inspect.getattr_static(self._device, method)
        except AttributeError:
            raise HTTPException(
                status_code=404,
                detail=f"No such method: {method}",
            )

        try:
            return getattr(self._device, method)
        except AttributeError:
            raise HTTPException(
                status_code=404,
                detail=f"No such method: {method}",
            )

    @staticmethod
    def _dynamic_payload_to_args_kwargs(
        target: Any,
        payload: Any,
    ) -> Tuple[List[Any], Dict[str, Any]]:
        """
        既存 ApiSpec client が送る通常 JSON body を device 呼び出しへ変換する。

        dict は通常 kwargs として扱う。parameter 名と一致しない場合は、
        従来 ApiSpec handler と同様に body の定義順を positional args として扱う。
        dict 以外は単一 positional argument とする。
        """
        if payload is None:
            return [], {}

        if not isinstance(payload, dict):
            return [adapter.unpack_result(payload)], {}

        payload = adapter.unpack_result(payload)
        if not isinstance(payload, dict):
            return [payload], {}

        if not callable(target):
            if payload:
                raise TypeError("property does not accept request arguments")
            return [], {}

        try:
            signature = inspect.signature(target)
        except (TypeError, ValueError):
            return [], dict(payload)

        params = signature.parameters
        accepts_var_keyword = any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()
        )

        positional_only = [
            name
            for name, p in params.items()
            if p.kind == inspect.Parameter.POSITIONAL_ONLY
        ]

        named_allowed = {
            name
            for name, p in params.items()
            if p.kind
            in (
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            )
        }

        keys = set(payload.keys())
        if accepts_var_keyword or keys.issubset(named_allowed | set(positional_only)):
            args = []
            kwargs = dict(payload)
            for name in positional_only:
                if name in kwargs:
                    args.append(kwargs.pop(name))
            return args, kwargs

        # request_model の field 名と device 引数名が異なる旧 I/F 用。
        # JSON object の挿入順は client 側 model field 順を維持する。
        return list(payload.values()), {}

    async def _call_dynamic_target(
        self,
        target: Any,
        args: List[Any],
        kwargs: Dict[str, Any],
    ) -> Any:
        if callable(target):
            if inspect.iscoroutinefunction(target):
                return await target(*args, **kwargs)
            return target(*args, **kwargs)

        if args or kwargs:
            raise TypeError("property does not accept arguments")
        return target

    async def _dynamic_api_handler(
        self,
        method_name: str,
        request: Request,
    ):
        """
        ApiSpec を持たない server で従来の named API URL を受ける。

        これにより、機器別 client が従来どおり ApiSpec を持っていても、
        server 側を api_spec=None に切り替えるだけで同じ client を利用できる。
        """
        try:
            target = self._get_dynamic_target(method_name)

            if request.method == "GET":
                payload = dict(request.query_params)
            else:
                try:
                    payload = await request.json()
                except Exception:
                    payload = None

            args, kwargs = self._dynamic_payload_to_args_kwargs(target, payload)
            result = await self._call_dynamic_target(target, args, kwargs)
            return JSONResponse(content=adapter.pack_result(result))

        except HTTPException:
            raise
        except TypeError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except Exception as e:
            self._logger.exception(
                f"dynamic API {method_name} unexpected error"
            )
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    def _model_field_names(
        model_cls,
    ) -> List[str]:
        """
        Pydantic モデルからフィールド名一覧を取得する。

        Pydantic v2 では model_fields、
        v1 では __fields__ が使われるため両対応する。

        Args:
            model_cls: Pydantic モデルクラス。

        Returns:
            フィールド名のリスト。
        """
        v2_fields = getattr(model_cls, "model_fields", None)
        if isinstance(v2_fields, dict):
            return list(v2_fields.keys())
        return list(getattr(model_cls, "__fields__", {}).keys())

    @staticmethod
    def _extract_args_kwargs(
        api: "ApiSpec",
        request,
        target_func=None,
    ) -> Tuple[List[Any], Dict[str, Any]]:
        """
        request を target_func 呼び出し用の (args, kwargs) に展開する。

        処理モードは 2 系統ある:

        1) request_model が存在する場合
            - モデルフィールド順に positional 引数を構築
            - target_func の keyword-only 引数は kwargs 側へ回す

        2) request_model が存在しない場合
            - request をそのまま kwargs または単一 args として扱う

        Args:
            api: ApiSpec オブジェクト。
            request: FastAPI が生成した request_model インスタンス
                     または dict / スカラー。
            target_func: 実際に呼び出す対象関数。

        Returns:
            tuple[list[Any], dict[str, Any]]:
                呼び出し用 args, kwargs。
        """
        args = []
        kwargs = {}

        model_fields = []
        req_model = getattr(api, "request_model", None)

        #
        # Pydantic モデルが定義されている場合のみフィールド順を取得
        # Pydantic のクラスがもているメンバ一覧
        #
        if req_model is not None:
            # fields があると V2、filed 情報とはメンバ一覧
            v2_fields = getattr(req_model, "model_fields", None)
            if isinstance(v2_fields, dict):
                model_fields = list(v2_fields.keys())
            else:
                # V1 の時の field 情報
                model_fields = list(getattr(req_model, "__fields__", {}).keys())

        #
        # === Pydantic 契約ベース解釈ルート ===
        # メンバ一覧がある時
        # pydantic 情報と request に基づいて送られてきた引数の実態を dict として取得する
        #
        if model_fields and request is not None:
            # Pydantic v2 / v1 / dict に正規化
            if hasattr(request, "model_dump") and callable(request.model_dump):
                request_dict = request.model_dump()  # V2

            elif hasattr(request, "dict") and callable(request.dict):
                request_dict = request.dict()  # V1

            elif isinstance(request, dict):
                request_dict = request
            else:
                request_dict = {}

            #
            # target_func の kw-only 引数を検出
            # Pydaitc 定義のオブジェクトから引数情報引き出すのではなくて
            # 直接function情報から引数情報を引き出す場合
            #
            kwonly = set()
            if target_func:
                sig = inspect.signature(target_func)
                for name, param in sig.parameters.items():
                    if param.kind == inspect.Parameter.KEYWORD_ONLY:
                        kwonly.add(name)

            #
            # モデル定義の順番に args を積み、kw-only は kwargs へ
            #
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

        #
        # model_field がないとき
        # === 実体ベース解釈ルート ===
        # かわりにhttp の body 経由でくる request に model_dump/dict 構造があるとき
        # それがないときに　request を生 args とする
        #
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

        Args:
            result: 実処理の戻り値。
            api: ApiSpec。

        Returns:
            response_model 契約に沿った戻り値。

        Raises:
            TypeError:
                多フィールド model に対してスカラーを返した場合。
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

    def _resolve_callable_api(
        self,
        api,
        request,
    ):
        """
        API 名から呼び出し対象オブジェクトを解決する。
        呼び出し名のオブジェクトを取り出している

        Router 自身に存在すれば Router 側を優先。
        無ければ device_instance 側を参照する。

        Args:
            api: ApiSpec。
            request: リクエスト（未使用だが将来拡張用）。

        Returns:
            呼び出し対象（関数またはプロパティ）。

        Raises:
            AttributeError: 対象が存在しない場合。
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
        api: "ApiSpec",
    ):
        """
        Pydantec の ApiSpec 情報から指定の ApiSpec のハンドラーを立ち上げる
        handler 関数を返す

        Args:
            api (ApiSpec):
                 ApiSpec(
                     name="operation",
                     object_name="device",
                     request_model=RequestModel,
                     response_model=ResponseModel,
                     method="post",
                     summary="",
                     description="",
                 ),

        Returns:
            handler:

        """

        async def handler(
            request: api.request_model = None,
            raw_request: Request = None,
        ):
            try:
                self._logger.info(f"[API CALL] {api.name}")

                # I/F未定義キーを明示的に422にする
                req_model = getattr(api, "request_model", None)

                # req_model が存在する時
                # (raw_requestが実質 http通信 でほぼ必ず存在する
                if req_model is not None and raw_request is not None:
                    try:
                        # HTTP body の json
                        # もし {"filename":a.txt} が送られてきたら
                        raw_payload = await raw_request.json()
                    except Exception:
                        raw_payload = None

                    # トップレベルオブジェクトが {} とは限らない
                    # [] の時などに対する対応
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

                # 呼び出し対象の解決（resolve）
                target = self._resolve_callable_api(api, request)

                # 呼び出し用の引数を決定する
                args, kwargs = self._extract_args_kwargs(
                    api,
                    request,
                    target,
                )

                if target is None:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Unknown API member: {api.name}",
                    )

                # 呼び出し対象ハンドラーオブジェクトを実行する
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

            if self._auto_dispatch:
                # 完全動的モードでは機器固有 Router を介さず、
                # Framework が device の public member を直接 dispatch する。
                target = self._get_dynamic_target(method)
                self._logger.info(f"[DeviceCtrl DISPATCH CALL] {method}")
            else:
                # 既存 ApiSpec モードの __dispatch__ の挙動は変更しない。
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
