#!/usr/bin/env python
"""
PYIスタブファイル自動生成 (syncクライアント用)

Kengo NAKADA:
https://github.com/shimane-dev, https://github.com/kengo-nakada
kengo.nakada@mat.shimane-u.ac.jp, kengo.nakada@gmail.com
"""
from collections import defaultdict


def gen_func_signature(api):
    sigs = []
    # None安全な型名取得
    req_model_name = api.request_model.__name__ if getattr(api, "request_model", None) is not None else "Any"
    resp_model_name = api.response_model.__name__ if getattr(api, "response_model", None) is not None else "Any"
    # 1. Pydanticモデル（推奨パターン, 通常1引数）
    if api.request_model:
        sigs.append(
            f"    def {api.name}(self, req: {req_model_name}) -> {resp_model_name}: ..."
        )

        # Pydanticモデルのフィールドから分解型引数シグネチャ自動生成（input_types不要）
        args_ = []
        for name, field in api.request_model.__fields__.items():
            # tp = field.outer_type_
            # pydantic v2対応：annotation優先、なければouter_type_、どちらもなければtype(field)
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
            sigs.append(
                f"    def {api.name}(self, {args_joined}) -> {resp_model_name}: ..."
            )

    # 3. キーワード引数のみ許可
    # （arg_names指定がない場合は通常スキップだが、現状維持のため残す）
    elif getattr(api, "arg_names", None):
        args_ = ", ".join([f"{n}: Any" for n in api.arg_names])
        sigs.append(
            f"    def {api.name}(self, {args_}) -> {resp_model_name}: ..."
        )

    # 4. 通常引数がdict型
    sigs.append(
        f"    def {api.name}(self, params: dict) -> {resp_model_name}: ..."
    )
    # 5. 引数なし
    sigs.append(f"    def {api.name}(self) -> {resp_model_name}: ...")
    # 6. 可変長パターン
    sigs.append(
        f"    def {api.name}(self, *args, **kwargs) -> {resp_model_name}: ..."
    )
    return "\n".join(sigs)


def make_pyi_sync_device_client(filename: str, api_spec, class_name="SyncDeviceClient"):
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
        "from typing import Optional, Any",
        "import httpx",
        "from x_logger.x_logger import XLogger",
    ]

    for mod, names in sorted(imports.items()):
        import_lines.append(f"from {mod} import {', '.join(sorted(names))}")

    lines = []
    lines.extend(import_lines)
    lines.append(f"class {class_name}:")

    # インスタンス変数の型宣言
    lines.append("    _client: httpx.Client")
    lines.append("    _logger: XLogger")
    lines.append("    _base_url: str")

    # __init__ の型
    lines.append(
        "    _api_spec: list = None",
    )
    lines.append(
        "    def __init__(self, config: Any = ..., server_ip: str = ..., server_port: int = ..., base_url: str = ..., api_spec: Optional[list] = None, logger: Optional[Any] = None): ..."
    )

    # 動的API生成用内部メソッド類（型補完用スタブのみ/実体は.py側）
    manual_methods = [
        "    def _post(self, url, **kwargs) -> Any: ...",
        "    def _register_api_spec_methods(self) -> None: ...",
        "    def _make_api_method(self, api) -> Any: ...",
        "    def print_response(self, res) -> None: ...",
        "    @staticmethod",
        "    def auto_extract_result(obj) -> Any: ...",
    ]
    lines.extend(manual_methods)

    # def python_type_to_str(tp):
    #     if tp is None:
    #         return "None"
    #     if hasattr(tp, "__name__"):
    #         return tp.__name__
    #     if hasattr(tp, "_name") and tp._name:
    #         return tp._name
    #     return str(tp)

    for api in api_spec:
        # サマリーコメントも最大限活用
        if getattr(api, "summary", None) or getattr(api, "description", None):
            lines.append(f"    # {api.summary or ''} {api.description or ''}\n")
        lines.append(gen_func_signature(api))

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Created: {filename}")

