#!/usr/bin/env python
"""
PYIスタブファイル自動生成 (asyncクライアント用)

Kengo NAKADA:
https://github.com/shimane-dev, https://github.com/kengo-nakada
kengo.nakada@mat.shimane-u.ac.jp, kengo.nakada@gmail.com
"""

from collections import defaultdict
import types

import typing


def _type_to_str(tp) -> str:
    """
    pydantic の field.annotation / outer_type_ から、pyi 用の型文字列を生成する。
    typing.Optional / Union / list[...] などを壊さずに出す。
    """
    if tp is None:
        return "Any"

    if tp is type(None):
        return "type(None)"

    origin = typing.get_origin(tp)
    args = typing.get_args(tp)

    if origin is None:
        if hasattr(types, "UnionType"):
            if isinstance(tp, types.UnionType):
                origin = typing.Union
                args = tp.__args__

    if origin is None:
        if hasattr(tp, "__name__"):
            return tp.__name__
        if hasattr(tp, "_name") and tp._name:
            return tp._name
        s = str(tp)
        s = s.replace("typing.", "")
        return s

    if origin is typing.Union:
        flat = []
        for a in args:
            flat.append(a)

        non_none = []
        none_found = False
        for a in flat:
            if a is type(None):
                none_found = True
            else:
                non_none.append(a)

        if none_found and len(non_none) == 1:
            inner = _type_to_str(non_none[0])
            return f"Optional[{inner}]"

        inner_join = ", ".join(_type_to_str(a) for a in flat)
        return f"Union[{inner_join}]"

    origin_name = getattr(origin, "__name__", None)
    if origin_name is None:
        origin_name = str(origin).replace("typing.", "")

    if args:
        inner_join = ", ".join(_type_to_str(a) for a in args)
        return f"{origin_name}[{inner_join}]"

    return origin_name


def gen_api_method_signatures(api):
    lines = []

    req_model_name = (
        api.request_model.__name__
        if getattr(api, "request_model", None) is not None
        else "Any"
    )

    resp_model_name = "Any"

    if getattr(api, "summary", None):
        s = str(api.summary).replace("\r\n", "\n").replace("\r", "\n")
        summary_line = " ".join(line.strip() for line in s.split("\n") if line.strip())
        lines.append(f"    # {summary_line}")

    if getattr(api, "description", None):
        d = str(api.description).replace("\r\n", "\n").replace("\r", "\n")
        desc_line = " ".join(line.strip() for line in d.split("\n") if line.strip())
        lines.append(f"    # {desc_line}")

    has_req_model = getattr(api, "request_model", None) is not None

    if has_req_model:
        # 1) req: Model
        lines.append("    @overload")
        lines.append(
            f"    async def {api.name}(self, req: {req_model_name}) -> {resp_model_name}: ..."
        )

        # 2) 展開引数（大量に出す）
        args_ = []
        for name, field in api.request_model.__fields__.items():
            if hasattr(field, "annotation") and field.annotation is not None:
                tp = field.annotation
            elif hasattr(field, "outer_type_") and field.outer_type_ is not None:
                tp = field.outer_type_
            else:
                tp = type(field)

            type_str = _type_to_str(tp)
            args_.append(f"{name}: {type_str} = ...")

        if args_:
            args_joined = ", ".join(args_)
            lines.append("    @overload")
            lines.append(
                f"    async def {api.name}(self, {args_joined}) -> {resp_model_name}: ..."
            )

        # 3) params: dict
        lines.append("    @overload")
        lines.append(
            f"    async def {api.name}(self, params: dict) -> {resp_model_name}: ..."
        )

        # 4) 引数なし
        lines.append("    @overload")
        lines.append(f"    async def {api.name}(self) -> {resp_model_name}: ...")

        # 5) **kwargs（keyword 呼び出しを確実に許す）
        lines.append("    @overload")
        lines.append(
            f"    async def {api.name}(self, **kwargs) -> {resp_model_name}: ..."
        )

        # 6) *args, **kwargs（このパターンも残す、との要求）
        lines.append("    @overload")
        lines.append(
            f"    async def {api.name}(self, *args, **kwargs) -> {resp_model_name}: ..."
        )
        return lines

    # request_model なし
    lines.append("    @overload")
    lines.append(f"    async def {api.name}(self) -> {resp_model_name}: ...")

    lines.append("    @overload")
    lines.append(f"    async def {api.name}(self, **kwargs) -> {resp_model_name}: ...")

    lines.append("    @overload")
    lines.append(
        f"    async def {api.name}(self, *args, **kwargs) -> {resp_model_name}: ..."
    )

    return lines


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
    for field in getattr(model, "__fields__", {}).values():
        tps = []
        if hasattr(field, "annotation") and field.annotation is not None:
            tps.append(field.annotation)
        elif hasattr(field, "outer_type_") and field.outer_type_ is not None:
            tps.append(field.outer_type_)
        else:
            tps.append(type(field))
        for tp in tps:
            for mod_name in extract_all_types(tp):
                type_names.add(mod_name)
    return type_names


def make_pyi_async_device_client(
    filename: str, api_spec, class_name="AsyncDeviceClient"
):
    imports = defaultdict(set)
    for api in api_spec:
        model = api.request_model
        if model is not None:
            mod = model.__module__
            name = model.__name__
            imports[mod].add(name)
        for mod, name in collect_type_hints_from_model(model):
            imports[mod].add(name)

    import_lines = [
        # "from typing import Optional, Awaitable, Any, overload, Union, overload",
        "from typing import Optional, Awaitable, Any, overload, Union",
        "import httpx",
        "from httpx import Response",
        "import logging",
        # "from x_logger.x_logger import XLogger",
    ]

    for mod, names in sorted(imports.items()):
        if mod == "builtins":
            names = {n for n in names if n != "NoneType"}
        if not names:
            continue
        import_lines.append(f"from {mod} import {', '.join(sorted(names))}")

    lines = []
    lines.extend(import_lines)
    lines.append(f"class {class_name}:")

    lines.append("    _client: httpx.AsyncClient")
    # lines.append("    _logger: XLogger")
    lines.append("    _logger: Any")
    lines.append("    _base_url: str")
    lines.append("    _api_spec: list = None")

    lines.append(
        "    def __init__(self, config: Any = ..., server_ip: str = ..., server_port: int = ..., base_url: str = ..., api_spec: Optional[list] = None, logger: Optional[Any] = None, log_level: str = ..., object_name: str = ...): ..."
    )

    manual_methods = [
        "    async def _post(self, url, **kwargs) -> Any: ...",
        "    def _register_api_spec_methods(self) -> None: ...",
        "    def _make_api_method(self, api) -> Any: ...",
        "    async def dispatch(self, method: str, *args, **kwargs) -> Any: ...",
    ]
    lines.extend(manual_methods)

    for api in api_spec:
        lines.extend(gen_api_method_signatures(api))

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Created: {filename}")
