#!/usr/bin/env python
"""
PYIスタブファイル自動生成 (device client: async / sync 共通)

Kengo NAKADA:
https://github.com/shimane-dev, https://github.com/kengo-nakada
kengo.nakada@mat.shimane-u.ac.jp, kengo.nakada@gmail.com
"""

from collections import defaultdict
import types
import typing

# =========================
# 型ユーティリティ（完全共通）
# =========================


def _type_to_str(tp) -> str:
    if tp is None:
        return "Any"

    if tp is type(None):
        return "type(None)"

    origin = typing.get_origin(tp)
    args = typing.get_args(tp)

    if origin is None and hasattr(types, "UnionType"):
        if isinstance(tp, types.UnionType):
            origin = typing.Union
            args = tp.__args__

    if origin is None:
        if hasattr(tp, "__name__"):
            return tp.__name__
        if hasattr(tp, "_name") and tp._name:
            return tp._name
        return str(tp).replace("typing.", "")

    if origin is typing.Union:
        non_none = []
        none_found = False
        for a in args:
            if a is type(None):
                none_found = True
            else:
                non_none.append(a)

        if none_found and len(non_none) == 1:
            return f"Optional[{_type_to_str(non_none[0])}]"

        return f"Union[{', '.join(_type_to_str(a) for a in args)}]"

    origin_name = getattr(origin, "__name__", str(origin).replace("typing.", ""))

    if args:
        return f"{origin_name}[{', '.join(_type_to_str(a) for a in args)}]"

    return origin_name


def _get_model_fields(model):
    v2_fields = getattr(model, "model_fields", None)
    if isinstance(v2_fields, dict):
        return v2_fields
    v1_fields = getattr(model, "__fields__", None)
    if isinstance(v1_fields, dict):
        return v1_fields
    return {}


def _response_ret_type(api) -> str:
    """
    クライアントメソッドの戻り型文字列を決定する。

    - response_model が単一フィールドならフィールド型を返す
    - BaseModel 系で複数フィールドなら Dict[str, Any] を返す
    - それ以外は型表現をそのまま文字列化する
    """
    resp_model = getattr(api, "response_model", None)
    if resp_model is None:
        return "Any"

    fields = _get_model_fields(resp_model)
    if len(fields) == 1:
        field = next(iter(fields.values()))
        tp = getattr(field, "annotation", None)
        if tp is None:
            tp = getattr(field, "outer_type_", None)
        if tp is not None:
            return _type_to_str(tp)

    if hasattr(resp_model, "model_validate") or hasattr(resp_model, "parse_obj"):
        return "Dict[str, Any]"

    return _type_to_str(resp_model)


def extract_all_types(tp):
    if hasattr(tp, "__origin__") and hasattr(tp, "__args__"):
        for sub in tp.__args__:
            yield from extract_all_types(sub)
    elif hasattr(types, "UnionType") and isinstance(tp, types.UnionType):
        for sub in tp.__args__:
            yield from extract_all_types(sub)
    elif (
        hasattr(tp, "__module__")
        and hasattr(tp, "__name__")
        and not tp.__module__.startswith("typing")
    ):
        yield (tp.__module__, tp.__name__)


def collect_type_hints_from_model(model):
    type_names = set()
    if model is None:
        return type_names

    v2_fields = getattr(model, "model_fields", None)
    if isinstance(v2_fields, dict):
        for field in v2_fields.values():
            tp = getattr(field, "annotation", None)
            if tp is None:
                continue
            for mod_name in extract_all_types(tp):
                type_names.add(mod_name)
        return type_names

    for field in getattr(model, "__fields__", {}).values():
        if getattr(field, "annotation", None) is not None:
            tps = [field.annotation]
        elif getattr(field, "outer_type_", None) is not None:
            tps = [field.outer_type_]
        else:
            tps = [type(field)]

        for tp in tps:
            for mod_name in extract_all_types(tp):
                type_names.add(mod_name)

    return type_names


# =========================
# API signature 生成（共通）
# =========================


def gen_api_method_signatures(
    api,
    *,
    async_mode: bool,
):
    """
    1 API 分の overload シグネチャを生成する。

    生成順:
    - req: Model
    - 展開キーワード引数
    - params: dict
    - no-arg
    - **kwargs
    - *args, **kwargs
    """
    lines = []

    prefix = "async def" if async_mode else "def"
    # ret = "Any"
    ret = _response_ret_type(api)

    req_model = getattr(api, "request_model", None)
    req_model_name = req_model.__name__ if req_model is not None else "Any"

    if getattr(api, "summary", None):
        s = str(api.summary).replace("\r\n", "\n").replace("\r", "\n")
        lines.append(
            f"    # {' '.join(l.strip() for l in s.splitlines() if l.strip())}"
        )

    if getattr(api, "description", None):
        d = str(api.description).replace("\r\n", "\n").replace("\r", "\n")
        lines.append(
            f"    # {' '.join(l.strip() for l in d.splitlines() if l.strip())}"
        )

    if req_model is not None:
        # 1) req: Model
        lines += [
            "    @overload",
            f"    {prefix} {api.name}(self, req: {req_model_name}) -> {ret}: ...",
        ]

        # 2) 展開 keyword 引数
        args_ = []
        v2_fields = getattr(req_model, "model_fields", None)
        if isinstance(v2_fields, dict):
            for name, field in v2_fields.items():
                tp = getattr(field, "annotation", typing.Any)
                args_.append(f"{name}: {_type_to_str(tp)} = ...")
        else:
            for name, field in req_model.__fields__.items():
                tp = (
                    field.annotation
                    if getattr(field, "annotation", None) is not None
                    else getattr(field, "outer_type_", type(field))
                )
                args_.append(f"{name}: {_type_to_str(tp)} = ...")

        if args_:
            lines += [
                "    @overload",
                f"    {prefix} {api.name}(self, {', '.join(args_)}) -> {ret}: ...",
            ]

        # 3) params dict
        lines += [
            "    @overload",
            f"    {prefix} {api.name}(self, params: dict) -> {ret}: ...",
        ]

        # 4) no-arg
        lines += ["    @overload", f"    {prefix} {api.name}(self) -> {ret}: ..."]

        # 5) **kwargs（keyword-only 呼び出し用）
        lines += [
            "    @overload",
            f"    {prefix} {api.name}(self, **kwargs) -> {ret}: ...",
        ]

        # 6) *args, **kwargs（最終フォールバック）
        lines += [
            "    @overload",
            f"    {prefix} {api.name}(self, *args, **kwargs) -> {ret}: ...",
        ]

        return lines

    # request_model なし
    lines += [
        "    @overload",
        f"    {prefix} {api.name}(self) -> {ret}: ...",
        "    @overload",
        f"    {prefix} {api.name}(self, **kwargs) -> {ret}: ...",
        "    @overload",
        f"    {prefix} {api.name}(self, *args, **kwargs) -> {ret}: ...",
    ]

    return lines



def gen_api_property_signatures(api):
    """ApiSpec(kind="property") 1件分の property stub を生成する。"""
    lines = []
    ret = _response_ret_type(api)

    if getattr(api, "summary", None):
        text = str(api.summary).replace("\r\n", "\n").replace("\r", "\n")
        lines.append(f"    # {' '.join(l.strip() for l in text.splitlines() if l.strip())}")
    if getattr(api, "description", None):
        text = str(api.description).replace("\r\n", "\n").replace("\r", "\n")
        lines.append(f"    # {' '.join(l.strip() for l in text.splitlines() if l.strip())}")

    lines += [
        "    @property",
        f"    def {api.name}(self) -> {ret}: ...",
    ]

    if bool(getattr(api, "writable", False)):
        value_type = "Any"
        req_model = getattr(api, "request_model", None)
        fields = _get_model_fields(req_model) if req_model is not None else {}
        if len(fields) == 1:
            field = next(iter(fields.values()))
            tp = getattr(field, "annotation", None)
            if tp is None:
                tp = getattr(field, "outer_type_", None)
            if tp is not None:
                value_type = _type_to_str(tp)
        lines += [
            f"    @{api.name}.setter",
            f"    def {api.name}(self, value: {value_type}) -> None: ...",
        ]

    return lines

# =========================
# エントリポイント（唯一）
# =========================


def make_pyi_device_client(
    *,
    filename: str,
    api_spec,
    class_name: str,
    async_mode: bool,
):
    imports = defaultdict(set)

    for api in api_spec:
        for model in (
            getattr(api, "request_model", None),
            getattr(api, "response_model", None),
        ):
            if model is None:
                continue

            if hasattr(model, "__module__") and hasattr(model, "__name__"):
                imports[model.__module__].add(model.__name__)

            for mod, name in collect_type_hints_from_model(model):
                imports[mod].add(name)

    import_lines = [
        "from typing import Optional, Any, Dict, overload, Union",
        "import httpx",
    ]

    if async_mode:
        import_lines.append("from httpx import Response")

    for mod, names in sorted(imports.items()):
        if mod == "builtins":
            names = {n for n in names if n != "NoneType"}
        if names:
            import_lines.append(f"from {mod} import {', '.join(sorted(names))}")

    lines = []
    lines.extend(import_lines)
    lines.append(f"class {class_name}:")

    lines.append(
        "    _client: httpx.AsyncClient" if async_mode else "    _client: httpx.Client"
    )
    lines += [
        "    _logger: Any",
        "    _base_url: str",
        "    _api_spec: list = None",
        "    def __init__(self, config: Any = ..., server_ip: str = ..., server_port: int = ..., base_url: str = ..., api_spec: Optional[list] = None, logger: Optional[Any] = None, log_level: str = ..., object_name: str = ...): ...",
    ]

    if async_mode:
        lines += [
            "    async def _post(self, url, **kwargs) -> Any: ...",
            "    async def dispatch(self, method: str, *args, **kwargs) -> Any: ...",
        ]
    else:
        lines += [
            "    def _post(self, url, **kwargs) -> Any: ...",
            "    def dispatch(self, method: str, *args, **kwargs) -> Any: ...",
        ]

    lines += [
        "    def _register_api_spec_methods(self) -> None: ...",
        "    def _make_api_method(self, api) -> Any: ...",
        "    def _decode_response_legacy(self, api: Any, payload: Any) -> Any: ...",
        "    @staticmethod",
        "    def auto_extract_result(obj: Any) -> Any: ...",
    ]

    for api in api_spec:
        if getattr(api, "kind", "method") == "property":
            lines.extend(gen_api_property_signatures(api))
        else:
            lines.extend(gen_api_method_signatures(api, async_mode=async_mode))

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Created: {filename}")
