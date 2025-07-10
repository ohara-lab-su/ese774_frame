#!/usr/bin/env python
"""
PYIスタブファイル自動生成 (asyncクライアント用)

Kengo NAKADA:
https://github.com/shimane-dev, https://github.com/kengo-nakada
kengo.nakada@mat.shimane-u.ac.jp, kengo.nakada@gmail.com
"""
from collections import defaultdict


def make_pyi_async_device_client(
    filename: str, api_spec, class_name="AsyncDeviceClient"
):
    # API_SPECSに出現するpydanticモデル類のimport自動生成
    imports = defaultdict(set)
    for api in api_spec:
        for model in [api.request_model, api.response_model]:
            if model is not None:
                mod = model.__module__
                name = model.__name__
                imports[mod].add(name)

    # 共通importとAPI依存import
    import_lines = [
        "from typing import Optional, Awaitable, Any",
        "import httpx",
        "from httpx import Response",
        "from x_logger.x_logger import XLogger",
    ]

    for mod, names in sorted(imports.items()):
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
        "    def __init__(self, server_ip: str = ..., server_port: int = ..., base_url: str = ..., api_spec: Optional[list] = None, logger: Optional[Any] = None): ...",
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

    def python_type_to_str(tp):
        if tp is None:
            return "None"
        if hasattr(tp, "__name__"):
            return tp.__name__
        if hasattr(tp, "_name") and tp._name:
            return tp._name
        return str(tp)

    def gen_func_signature(api):
        sigs = []
        # 1. Pydanticモデル（推奨パターン, 通常1引数）
        if api.request_model:
            sigs.append(
                f"    async def {api.name}(self, req: {api.request_model.__name__}) -> {api.response_model.__name__}: ..."
            )
        # 2. input_types/arg_names組み合わせあり
        if getattr(api, "arg_names", None) and getattr(api, "input_types", None):
            args_ = []
            for n, t in zip(api.arg_names, api.input_types):
                args_.append(f"{n}: {python_type_to_str(t)}")
            args_joined = ", ".join(args_)
            sigs.append(
                f"    async def {api.name}(self, {args_joined}) -> {api.response_model.__name__}: ..."
            )
        # 3. キーワード引数のみ許可
        elif getattr(api, "arg_names", None):
            args_ = ", ".join([f"{n}: Any" for n in api.arg_names])
            sigs.append(
                f"    async def {api.name}(self, {args_}) -> {api.response_model.__name__}: ..."
            )
        # 4. 通常引数がdict型
        sigs.append(
            f"    async def {api.name}(self, params: dict) -> {api.response_model.__name__}: ..."
        )
        # 5. 引数なし
        sigs.append(
            f"    async def {api.name}(self) -> {api.response_model.__name__}: ..."
        )
        # 6. 可変長パターン
        sigs.append(
            f"    async def {api.name}(self, *args, **kwargs) -> {api.response_model.__name__}: ..."
        )
        return "\n".join(sigs)

    for api in api_spec:
        # サマリーコメントも最大限活用
        if getattr(api, "summary", None) or getattr(api, "description", None):
            lines.append(f"    # {api.summary or ''} {api.description or ''}\n")
        lines.append(gen_func_signature(api))

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Created: {filename}")


