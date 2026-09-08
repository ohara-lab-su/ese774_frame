#!/usr/bin/env python
"""
PYIスタブファイル自動生成 (device client: async / sync 共通)

Kengo NAKADA:
https://github.com/shimane-dev, https://github.com/kengo-nakada
kengo.nakada@mat.shimane-u.ac.jp, kengo.nakada@gmail.com
"""

from collections import defaultdict
import inspect
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
# 完全自動 dispatch 用 signature 生成
# =========================


def _annotation_to_str(annotation) -> str:
    """inspect.Signature の annotation を pyi 用文字列へ変換する。"""
    if annotation is inspect.Signature.empty:
        return "Any"

    if isinstance(annotation, str):
        return annotation

    return _type_to_str(annotation)


def _format_parameter(param: inspect.Parameter) -> str:
    """inspect.Parameter を pyi の引数表現へ変換する。"""
    annotation = ""
    if param.annotation is not inspect.Signature.empty:
        annotation = f": {_annotation_to_str(param.annotation)}"

    default = ""
    if param.default is not inspect.Signature.empty:
        default = " = ..."

    if param.kind == inspect.Parameter.VAR_POSITIONAL:
        return f"*{param.name}{annotation}"

    if param.kind == inspect.Parameter.VAR_KEYWORD:
        return f"**{param.name}{annotation}"

    return f"{param.name}{annotation}{default}"


def _signature_parameters(sig: inspect.Signature, drop_first: bool) -> list[str]:
    """inspect.Signature から self を除いた pyi 引数列を作る。"""
    params = list(sig.parameters.values())

    if drop_first and params:
        params = params[1:]

    result = []
    keyword_only_started = False

    for param in params:
        if (
            param.kind == inspect.Parameter.KEYWORD_ONLY
            and not keyword_only_started
        ):
            result.append("*")
            keyword_only_started = True

        result.append(_format_parameter(param))

        if param.kind == inspect.Parameter.VAR_POSITIONAL:
            keyword_only_started = True

    return result


def _get_callable_signature(member):
    """descriptor を評価せず callable とその signature を取得する。"""
    drop_first = False

    if isinstance(member, staticmethod):
        target = member.__func__

    elif isinstance(member, classmethod):
        target = member.__func__
        drop_first = True

    else:
        target = member
        drop_first = inspect.isfunction(target)

    if not callable(target):
        return None

    try:
        sig = inspect.signature(target)
    except (TypeError, ValueError):
        sig = inspect.Signature()

    return sig, drop_first


def _collect_auto_members(device_class):
    """完全自動 dispatch と同じ基準で public method/property を収集する。"""
    methods = []
    properties = []

    for name in dir(device_class):
        if name.startswith("_"):
            continue

        try:
            member = inspect.getattr_static(device_class, name)
        except Exception:
            continue

        if isinstance(member, property):
            properties.append((name, member))
            continue

        item = _get_callable_signature(member)
        if item is None:
            continue

        sig, drop_first = item
        methods.append((name, sig, drop_first))

    methods.sort(key=lambda item: item[0])
    properties.sort(key=lambda item: item[0])

    return methods, properties


def gen_auto_method_signature(
    name: str,
    sig: inspect.Signature,
    *,
    async_mode: bool,
    drop_first: bool,
):
    """完全自動 dispatch の public method 1件分の stub を生成する。"""
    prefix = "async def" if async_mode else "def"

    params = _signature_parameters(sig, drop_first=drop_first)
    args = ["self"]
    args.extend(params)

    ret = _annotation_to_str(sig.return_annotation)

    return [
        f"    {prefix} {name}({', '.join(args)}) -> {ret}: ...",
    ]


def gen_auto_property_signature(name: str, prop: property):
    """完全自動 dispatch の public property 1件分の stub を生成する。"""
    lines = []

    ret = "Any"
    if prop.fget is not None:
        try:
            ret = _annotation_to_str(
                inspect.signature(prop.fget).return_annotation
            )
        except (TypeError, ValueError):
            pass

    lines += [
        "    @property",
        f"    def {name}(self) -> {ret}: ...",
    ]

    if prop.fset is not None:
        value_type = "Any"
        try:
            sig = inspect.signature(prop.fset)
            params = list(sig.parameters.values())
            if len(params) >= 2:
                value_type = _annotation_to_str(params[1].annotation)
        except (TypeError, ValueError):
            pass

        lines += [
            f"    @{name}.setter",
            f"    def {name}(self, value: {value_type}) -> None: ...",
        ]

    return lines


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
    class_name: str,
    async_mode: bool,
    api_spec=None,
    device_class=None,
):
    """device client 用 pyi を生成する。

    公開対象の定義方法は Framework の2方式に対応する。

    - api_spec を指定:
        spec に定義された API から生成する。
    - device_class を指定:
        完全自動 dispatch と同じく public method/property を
        device class から収集して生成する。

    api_spec と device_class は同時には指定しない。
    """
    if api_spec is not None and device_class is not None:
        raise ValueError("api_spec and device_class are mutually exclusive")

    if api_spec is None and device_class is None:
        raise ValueError("api_spec or device_class is required")

    imports = defaultdict(set)

    if api_spec is not None:
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
        "from typing import Optional, Any, Dict, List, Tuple, Sequence, "
        "Mapping, Callable, Type, Literal, overload, Union",
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
        "    _api_spec: Optional[list] = None",
        "    def __init__(self, config: Any = ..., server_ip: str = ..., "
        "server_port: int = ..., base_url: str = ..., "
        "api_spec: Optional[list] = None, logger: Optional[Any] = None, "
        "log_level: str = ..., object_name: str = ...): ...",
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

    if api_spec is not None:
        for api in api_spec:
            if getattr(api, "kind", "method") == "property":
                lines.extend(gen_api_property_signatures(api))
            else:
                lines.extend(
                    gen_api_method_signatures(
                        api,
                        async_mode=async_mode,
                    )
                )

    else:
        methods, properties = _collect_auto_members(device_class)

        for name, sig, drop_first in methods:
            lines.extend(
                gen_auto_method_signature(
                    name,
                    sig,
                    async_mode=async_mode,
                    drop_first=drop_first,
                )
            )

        for name, prop in properties:
            lines.extend(
                gen_auto_property_signature(
                    name,
                    prop,
                )
            )

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Created: {filename}")

