#!/usr/bin/env python
"""
PYIスタブファイル自動生成 (asyncクライアント用)

Kengo NAKADA:
https://github.com/shimane-dev, https://github.com/kengo-nakada
kengo.nakada@mat.shimane-u.ac.jp, kengo.nakada@gmail.com
"""
from collections import defaultdict
import types


def gen_api_method_signatures(api):
    """
    API specから1API分のスタブシグネチャ行リストを返す
    コメント・docstring・型注釈もすべて保持
    """
    lines = []
    req_model_name = api.request_model.__name__ if getattr(api, "request_model", None) is not None else "Any"
    resp_model_name = api.response_model.__name__ if getattr(api, "response_model", None) is not None else "Any"

    # コメント・サマリーも維持
    if getattr(api, "summary", None):
        lines.append(f"    # {api.summary}")
    if getattr(api, "description", None):
        lines.append(f"    # {api.description}")

    # 1. Pydanticモデル（推奨パターン, 通常1引数）
    if getattr(api, "request_model", None) is not None:
        lines.append("    @overload")
        lines.append(
            f"    async def {api.name}(self, req: {req_model_name}) -> {resp_model_name}: ..."
        )
        # Pydanticモデルから分解型引数シグネチャ自動生成（input_types不要）
        args_ = []
        for name, field in api.request_model.__fields__.items():
            # 型の抽出（pydantic v2優先、なければv1、どちらもなければtype保険）
            if hasattr(field, "annotation") and field.annotation is not None:
                tp = field.annotation
            elif hasattr(field, "outer_type_") and field.outer_type_ is not None:
                tp = field.outer_type_
            else:
                tp = type(field)

            if hasattr(tp, "__name__"):
                type_str = tp.__name__
            elif hasattr(tp, "_name") and tp._name:
                type_str = tp._name
            else:
                type_str = str(tp)

            if type_str == "NoneType":
                type_str = "type(None)"

            args_.append(f"{name}: {type_str}")
        if args_:
            # args_joined = ", ".join(args_)
            args_joined = ", ".join(f"{a} = ..." for a in args_)
            lines.append("    @overload")
            lines.append(
                f"    async def {api.name}(self, {args_joined}) -> {resp_model_name}: ..."
            )
    else:
        # モデルなしAPIも必ず出力する（エラー回避用: 引数なし/戻り値Anyで型注釈）
        lines.append("    @overload")
        lines.append(
            f"    async def {api.name}(self) -> {resp_model_name}: ..."
        )

    lines.append("    @overload")
    lines.append(
        f"    async def {api.name}(self, *args, **kwargs) -> {resp_model_name}: ..."
    )

    return lines


def extract_all_types(tp):
    """任意の型からUnionTypeやネストを再帰して実体型(module, name)タプル列挙"""
    # typing.UnionやOptional（typing.*由来）
    if hasattr(tp, "__origin__") and hasattr(tp, "__args__"):
        for sub in tp.__args__:
            yield from extract_all_types(sub)
    # Python 3.10+ の UnionType (例: int | str)
    elif hasattr(types, "UnionType") and isinstance(tp, types.UnionType):
        for sub in tp.__args__:
            yield from extract_all_types(sub)
    # 通常の型
    elif hasattr(tp, "__module__") and hasattr(tp, "__name__") and not tp.__module__.startswith("typing"):
        yield (tp.__module__, tp.__name__)


def collect_type_hints_from_model(model):
    """pydanticモデルのフィールド型・ネスト型も再帰的にimport対象を抽出"""
    type_names = set()
    if model is None:
        return type_names
    for field in getattr(model, "__fields__", {}).values():
        tps = []
        # v2優先
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
    """
    PYIスタブファイル自動生成 (asyncクライアント用)

    Args:
        filename:
        api_spec:
        class_name:

    Returns:

    """
    # API_SPECSに出現するpydanticモデル類のimport自動生成
    imports = defaultdict(set)
    for api in api_spec:
        for model in [api.request_model, api.response_model]:
            if model is not None:
                mod = model.__module__
                name = model.__name__
                imports[mod].add(name)
            # 型ヒント分も再帰的にimport
            for mod, name in collect_type_hints_from_model(model):
                imports[mod].add(name)

    # 共通importとAPI依存import
    import_lines = [
        "from typing import Optional, Awaitable, Any, overload, Union",
        "import httpx",
        "from httpx import Response",
        "from x_logger.x_logger import XLogger",
    ]

    for mod, names in sorted(imports.items()):
        # NoneTypeはimport不要
        if mod == "builtins":
            names = {n for n in names if n != "NoneType"}
        if not names:
            continue
        import_lines.append(f"from {mod} import {', '.join(sorted(names))}")

    lines = []
    lines.extend(import_lines)
    lines.append(f"class {class_name}:")

    # インスタンス変数の型宣言
    lines.append("    _client: httpx.AsyncClient")
    lines.append("    _logger: XLogger")
    lines.append("    _base_url: str")

    # __init__ の型
    lines.append(
        "    _api_spec: list = None",
    )
    lines.append(
        "    def __init__(self, config: Any = ..., server_ip: str = ..., server_port: int = ..., base_url: str = ..., api_spec: Optional[list] = None, logger: Optional[Any] = None): ...",
    )

    # 動的API生成用内部メソッド類（型補完用スタブのみ/実体は.py側）
    manual_methods = [
        "    async def _post(self, url, **kwargs) -> Any: ...",
        "    def _register_api_spec_methods(self, base_url) -> None: ...",
        "    def _make_api_method(self, api, base_url) -> Any: ...",
        "    @staticmethod",
        "    def auto_extract_result(obj) -> Any: ...",
    ]
    lines.extend(manual_methods)

    # --- APIごとのメソッド自動生成（分離関数を利用） ---
    for api in api_spec:
        lines.extend(gen_api_method_signatures(api))

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Created: {filename}")
