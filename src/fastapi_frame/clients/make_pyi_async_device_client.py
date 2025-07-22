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
    """
    PYIスタブファイル自動生成 (asyncクライアント用)

    Args:
        filename:
        api_spec:
        class_name:

    Returns:

    """
    # API_SPECSに出現するpydanticモデル類のimport自動生成
    from collections import defaultdict
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

    # --- APIごとのメソッド自動生成 ---
    for api in api_spec:
        # Noneチェック追加
        req_model_name = api.request_model.__name__ if getattr(api, "request_model", None) is not None else "Any"
        resp_model_name = api.response_model.__name__ if getattr(api, "response_model", None) is not None else "Any"

        # コメント・サマリーも維持
        if getattr(api, "summary", None):
            lines.append(f"    # {api.summary}")
        if getattr(api, "description", None):
            lines.append(f"    # {api.description}")

        # 1. Pydanticモデル（推奨パターン, 通常1引数）
        if getattr(api, "request_model", None) is not None:
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
                args_.append(f"{name}: {type_str}")
            if args_:
                args_joined = ", ".join(args_)
                lines.append(
                    f"    async def {api.name}(self, {args_joined}) -> {resp_model_name}: ..."
                )
        else:
            # モデルなしAPIも必ず出力する（エラー回避用: 引数なし/戻り値Anyで型注釈）
            lines.append(
                f"    async def {api.name}(self) -> {resp_model_name}: ..."
            )

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Created: {filename}")