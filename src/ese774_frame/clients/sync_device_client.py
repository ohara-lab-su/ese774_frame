#!/usr/bin/env python
"""
FastAPI 用の汎用 sync クライアント。

- api_spec からメソッドを動的生成
- HTTP で device API を呼び出し
- adapter で args/kwargs/result を pack/unpack

Kengo NAKADA:
https://github.com/shimane-dev, https://github.com/kengo-nakada
kengo.nakada@mat.shimane-u.ac.jp, kengo.nakada@gmail.com
"""

import httpx
from typing import Any, Optional

from ese774_frame import adapter


class SyncDeviceClient:
    """
    api_spec 駆動の同期クライアント。

    役割:
    - 呼び出し引数を request_model に合わせて正規化・検証
    - 同期 HTTP 呼び出し実行
    - レスポンスを ApiSpec.decode_response（または互換復元）で
      プレーン Python に戻して返す
    - __dispatch__ 経路では adapter で args/kwargs/result を透過運搬
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
        timeout_sec: float = 60.0,
    ):
        if logger is None:
            import logging

            log_level = log_level or "INFO"
            logging.basicConfig(level=log_level.upper())
            logger = logging.getLogger(__name__)

        self._logger = logger
        self._base_url = base_url or f"http://{server_ip}:{server_port}"
        self._timeout_sec = timeout_sec
        self._client = httpx.Client(timeout=self._timeout_sec)
        self._object_name = object_name

        if api_spec:
            self._object_name = api_spec[0].object_name

        self._logger.info(f"[SERVER IP] {server_ip}")
        self._logger.info(f"[SERVER PORT] {server_port}")
        self._logger.info(f"[BASE URL] {base_url}")
        self._logger.info(f"[TIMEOUT] {self._timeout_sec}")

        self._api_spec = api_spec
        self._auto_dispatch = not bool(api_spec)
        self._remote_properties = {}
        self._remote_methods = {}
        self._property_meta_loaded = False
        if api_spec:
            for api in api_spec:
                if getattr(api, "kind", "method") == "property":
                    self._remote_properties[api.name] = {
                        "readable": True,
                        "writable": bool(getattr(api, "writable", False)),
                    }
            self._property_meta_loaded = True
            self._register_api_spec_methods()

    def _ensure_remote_property_meta(self) -> None:
        """dynamic mode の静的 property metadata を遅延取得する。"""
        if self.__dict__.get("_property_meta_loaded", False):
            return
        if "_base_url" not in self.__dict__ or "_object_name" not in self.__dict__:
            return
        url = f"{self._base_url}/instance/{self._object_name}/__meta__"
        resp = self._client.get(url)
        resp.raise_for_status()
        data = resp.json()
        props = data.get("properties", {}) if isinstance(data, dict) else {}
        methods = data.get("methods", {}) if isinstance(data, dict) else {}
        object.__setattr__(self, "_remote_properties", dict(props))
        object.__setattr__(self, "_remote_methods", dict(methods))
        object.__setattr__(self, "_property_meta_loaded", True)

    def _get_remote_property(self, name: str) -> Any:
        url = f"{self._base_url}/instance/{self._object_name}/__property__/{name}"
        resp = self._client.get(url)
        resp.raise_for_status()
        return adapter.unpack_result(resp.json())

    def _set_remote_property(self, name: str, value: Any) -> None:
        url = f"{self._base_url}/instance/{self._object_name}/__property__/{name}"
        resp = self._client.put(url, json={"value": adapter.pack_result(value)})
        resp.raise_for_status()

    def __setattr__(self, name: str, value: Any) -> None:
        if isinstance(name, str) and not name.startswith("_") and "_remote_properties" in self.__dict__:
            if self.__dict__.get("_auto_dispatch", False) and not self.__dict__.get("_property_meta_loaded", False):
                self._ensure_remote_property_meta()
            info = self.__dict__.get("_remote_properties", {}).get(name)
            if info is not None:
                if not info.get("writable", False):
                    raise AttributeError(f"remote property is read-only: {name}")
                self._set_remote_property(name, value)
                return
        object.__setattr__(self, name, value)

    def __getattr__(self, name: str) -> Any:
        """
        ApiSpec を使わない完全自動 dispatch モードの動的 API 解決。

        - foo(...)      -> remote foo(...)
        - _foo_raw(...) -> client-side override を迂回して remote foo(...)
        - '_' で始まる通常名は公開 API として解決しない

        専用 client class に同名メソッドが定義されている場合は、
        Python の通常の属性解決が先に働くため local override が優先される。
        """
        if self.__dict__.get("_auto_dispatch", False):
            self._ensure_remote_property_meta()
            info = self.__dict__.get("_remote_properties", {}).get(name)
            if info is not None:
                if not info.get("readable", True):
                    raise AttributeError(f"remote property is not readable: {name}")
                return self._get_remote_property(name)
        else:
            info = self.__dict__.get("_remote_properties", {}).get(name)
            if info is not None:
                if not info.get("readable", True):
                    raise AttributeError(f"remote property is not readable: {name}")
                return self._get_remote_property(name)
            raise AttributeError(name)

        remote_name = name
        if name.startswith("_") and name.endswith("_raw") and len(name) > 5:
            remote_name = name[1:-4]
        elif name.startswith("_"):
            raise AttributeError(name)

        def remote_method(*args, **kwargs):
            return self.dispatch(remote_name, *args, **kwargs)

        remote_method.__name__ = name
        return remote_method

    def _register_api_spec_methods(self) -> None:
        """
        api_spec に基づいてクライアントメソッドを動的生成する。

        各 ApiSpec ごとに _make_api_method でメソッドを生成し、
        インスタンスへ動的に setattr する。
        """

        self._logger.debug("[CLIENT REGISTER] API_SPEC")

        for api in self._api_spec or []:
            if getattr(api, "kind", "method") == "property":
                name = api.name
                self._logger.debug(f"[CLIENT REGISTER PROPERTY] {name}")

                def raw_get(_name=name):
                    return self._get_remote_property(_name)

                setattr(self, f"_{name}_raw", raw_get)

                if bool(getattr(api, "writable", False)):
                    def raw_set(value, _name=name):
                        return self._set_remote_property(_name, value)
                    setattr(self, f"_set_{name}_raw", raw_set)
                continue

            self._logger.debug(f"[CREATE METHOD FROM API_SPEC] {api.name}")
            method = self._make_api_method(api)

            if not hasattr(self, api.name):
                self._logger.debug(f"[CLIENT REGISTER] {api.name}")
                setattr(self, api.name, method)

            raw_name = f"_{api.name}_raw"
            self._logger.debug(f"[CLIENT REGISTER(row)] {raw_name}")
            setattr(self, raw_name, method)

    def _make_api_method(
        self,
        api: Any,
    ) -> Any:
        """
        api_spec 1件から同期呼び出しメソッドを生成する。

        主要処理:
        - args/kwargs -> request payload へ正規化
        - request_model で入力検証・型変換
        - サーバ呼び出し
        - decode_response 優先で復元（旧互換フォールバックあり）
        """

        def method(*args, **kwargs):
            self._logger.debug(f"[CLIENT CALL] {api.name} args={args} kwargs={kwargs}")

            model_fields = []
            req_model = getattr(api, "request_model", None)

            if req_model is not None:
                v2_fields = getattr(req_model, "model_fields", None)
                if isinstance(v2_fields, dict):
                    model_fields = list(v2_fields.keys())
                else:
                    model_fields = list(getattr(req_model, "__fields__", {}).keys())

            if req_model is not None:
                if len(args) == 1 and isinstance(args[0], dict):
                    req_data = dict(args[0])
                    req_data.update(kwargs)
                elif (
                    len(args) == 1
                    and hasattr(args[0], "model_dump")
                    and callable(args[0].model_dump)
                ):
                    req_data = args[0].model_dump()
                    req_data.update(kwargs)
                elif (
                    len(args) == 1
                    and hasattr(args[0], "dict")
                    and callable(args[0].dict)
                ):
                    req_data = args[0].dict()
                    req_data.update(kwargs)
                elif model_fields and args:
                    if len(args) > len(model_fields):
                        raise TypeError(
                            f"{api.name}: too many positional args ({len(args)}), "
                            f"expected <= {len(model_fields)}"
                        )

                    req_data = {name: arg for name, arg in zip(model_fields, args)}
                    duplicated = sorted(set(req_data.keys()) & set(kwargs.keys()))

                    if duplicated:
                        raise TypeError(
                            f"{api.name}: duplicated args/kwargs keys: {duplicated}"
                        )
                    req_data.update(kwargs)
                elif not args:
                    req_data = dict(kwargs)
                else:
                    raise TypeError(f"{api.name}: unsupported args/kwargs pattern")

                if not isinstance(req_data, dict):
                    raise TypeError(
                        f"{api.name}: request payload must be dict for request_model"
                    )

                unknown = sorted(set(req_data.keys()) - set(model_fields))
                if unknown:
                    raise ValueError(
                        f"{api.name}: unknown request keys not defined in "
                        f"request_model: {unknown}"
                    )

                if hasattr(req_model, "model_validate"):
                    req_data = req_model.model_validate(req_data).model_dump()
                else:
                    req_data = req_model.parse_obj(req_data).dict()

            else:
                if len(args) == 1 and not kwargs:
                    req_data = args[0]
                elif not args and kwargs:
                    req_data = dict(kwargs)
                elif not args and not kwargs:
                    req_data = None
                else:
                    raise TypeError(f"{api.name}: unsupported args/kwargs pattern")

            self._logger.info(f"[CLIENT REQUEST] {api.name} req_data={req_data}")

            try:
                url = f"{self._base_url}/instance/{api.object_name}/{api.name}"
                resp = self._post(url, json=req_data)
                self._logger.debug(f"[CLIENT RESPONSE] {api.name} resp={resp}")

                if resp is None:
                    return None

                payload = adapter.unpack_result(resp.json())

                # 従来 ApiSpec server の response_model 形式を優先して復元する。
                # api_spec=None の動的 server は model wrapper を持たず device の
                # 戻り値を直接返すため、decode_response が成立しない場合だけ
                # その raw result をそのまま返す。これにより機器別 client は
                # server が spec mode / dynamic mode のどちらでも同じまま使える。
                if hasattr(api, "decode_response") and callable(api.decode_response):
                    try:
                        return api.decode_response(payload)
                    except Exception:
                        # dynamic server は response_model を持たないため、
                        # 単一フィールド response model の wrapper が存在しない。
                        # その場合だけ raw result を互換値として返す。
                        resp_model = getattr(api, "response_model", None)
                        fields = getattr(resp_model, "model_fields", None)
                        if not isinstance(fields, dict):
                            fields = getattr(resp_model, "__fields__", None)
                        if isinstance(fields, dict) and len(fields) == 1:
                            field_name = next(iter(fields.keys()))
                            if not isinstance(payload, dict) or field_name not in payload:
                                return payload
                        raise
                return self._decode_response_legacy(api, payload)

            except Exception as e:
                self._logger.error(f"[CLIENT ERROR] {api.name} error: {e}")
                raise

        method.__name__ = api.name
        return method

    def _decode_response_legacy(self, api: Any, payload: Any) -> Any:
        """
        レスポンス復元ロジック。

        api.decode_response が無い spec でも response_model から復元する。
        """
        resp_model = getattr(api, "response_model", None)
        if resp_model is None:
            return payload

        try:
            if hasattr(resp_model, "model_validate"):
                model = resp_model.model_validate(payload)
            elif hasattr(resp_model, "parse_obj"):
                model = resp_model.parse_obj(payload)
            else:
                return payload
            return self.auto_extract_result(model)
        except Exception:
            return payload

    @staticmethod
    def auto_extract_result(obj: Any) -> Any:
        """
        BaseModel または dict を自動アンラップする。

        BaseModel/辞書の1フィールドを自動アンラップし、
        複数フィールドは dict で返す。
        """
        if hasattr(obj, "model_dump") and callable(obj.model_dump):
            data = obj.model_dump()
        elif hasattr(obj, "dict") and callable(obj.dict):
            data = obj.dict()
        elif isinstance(obj, dict):
            data = obj
        else:
            return obj

        if len(data) == 1:
            return next(iter(data.values()))
        return data

    def dispatch(
        self,
        method: str,
        *args,
        **kwargs,
    ) -> Any:
        """
        一般形ディスパッチ (*args, **kwargs) を同期実行する。
        """
        payload = {
            "method": method,
            "args": adapter.pack_args(args),
            "kwargs": adapter.pack_kwargs(kwargs),
        }
        url = f"{self._base_url}/instance/{self._object_name}/__dispatch__"
        resp = self._post(url, json=payload)
        if resp is None:
            return None

        if self._auto_dispatch and not self._property_meta_loaded:
            self._ensure_remote_property_meta()
        method_info = self._remote_methods.get(method, {})
        return_type = method_info.get("return") if isinstance(method_info, dict) else None
        return adapter.unpack_result(
            resp.json(),
            type_descriptor=return_type,
        )

    def _post(
        self,
        url: str,
        **kwargs,
    ) -> Any:
        """
        HTTP POST を同期実行する内部メソッド。
        """
        try:
            res = self._client.post(url, **kwargs)
            res.raise_for_status()
            return res

        except httpx.HTTPStatusError as e:
            body = e.response.text if e.response is not None else ""
            code = e.response.status_code if e.response is not None else "?"
            self._logger.error(f"HTTP error {code} POST {url} body={body}")
            raise
        except Exception:
            self._logger.exception(f"POST failed: {url}")
            raise

    def set_timeout(
        self,
        timeout_sec: float,
    ) -> None:
        """
        HTTP 通信の timeout 秒数を変更する。

        既存の同期 HTTP client を閉じ、
        次回以降の request から新しい timeout を使う。
        """
        self._client.close()
        self._timeout_sec = timeout_sec
        self._client = httpx.Client(timeout=self._timeout_sec)
        self._logger.info(f"[TIMEOUT] {self._timeout_sec}")

    def close(self) -> None:
        """
        HTTP client を同期的に閉じる。
        """
        self._client.close()

    def close_client(self) -> None:
        """
        既存の同期クライアント互換名で HTTP client を閉じる。
        """
        self.close()

    def __enter__(self) -> Any:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def local_echo(
        self,
        message: str = "local method ok",
    ) -> str:
        """
        API spec や Pydantic を使わない、クライアントローカル確認用メソッド。
        """
        print(message)
        self._logger.info(f"[LOCAL ECHO] {message}")
        return message
