#!/usr/bin/env python
"""
PYIスタブファイル自動生成（Router用）
DeviceRouter/XXRouter対応、API_SPEC引数で自動切替。
manual_methodsやコメント、型宣言も現行仕様を完全維持。
"""

from collections import defaultdict


def make_pyi_device_router(filename: str, api_spec, class_name="DeviceRouter"):
    """
    DeviceRouter/派生ルーター用 pyiファイル自動生成関数

    Args:
        filename: 出力先ファイル名
        api_spec: API仕様リスト
        class_name: クラス名（"DeviceRouter" or 継承名）

    Returns:

    """
    manual_methods = [
        "    def __getattr__(self, name) -> Any: ...",
        "    def __setattr__(self, name, value): ...",
        "    @staticmethod",
        "    def _ok(result: object) -> object: ...",
        "    @staticmethod",
        "    def _bad_request(msg: str) -> object: ...",
        "    def _make_handler(self, api): ...",
        "    _logger: XLogger",
        "    router: APIRouter",
    ]

    # --- モデルimport ---
    imports = defaultdict(set)
    for api in api_spec:
        for model in [
            getattr(api, "request_model", None),
            getattr(api, "response_model", None),
        ]:
            if (
                model is not None
                and hasattr(model, "__module__")
                and hasattr(model, "__name__")
            ):
                imports[model.__module__].add(model.__name__)

    import_lines = ["from typing import Optional, Any"]
    for mod, names in sorted(imports.items()):
        import_lines.append(f"from {mod} import {', '.join(sorted(names))}")
    import_lines.append("from x_logger.x_logger import XLogger")
    import_lines.append("from fastapi import APIRouter")

    lines = []
    lines.extend(import_lines)
    lines.append(f"class {class_name}:")
    lines.append('    """')
    lines.append("    FastAPI Router動的生成用ベースクラス")
    lines.append("    api_specの内容に応じて動的にhandler/routeを生やす")
    lines.append('    """')
    lines.append("")
    lines.append(
        "    def __init__(self, device_instance, api_spec, logger: Optional[XLogger] = None): ..."
    )
    lines.extend(manual_methods)

    # --- APIごとのメソッド自動生成 ---
    for api in api_spec:
        req = api.request_model.__name__ if getattr(api, "request_model", None) else ""
        orig_types = []

        if getattr(api, "request_model", None):
            for field in api.request_model.__fields__.values():

                # t = field.outer_type_
                if hasattr(field, "annotation") and field.annotation is not None:
                    t = field.annotation
                elif hasattr(field, "outer_type_") and field.outer_type_ is not None:
                    t = field.outer_type_
                else:
                    t = type(field)

                # 型名文字列へ
                if hasattr(t, "__name__"):
                    orig_types.append(t.__name__)
                else:
                    orig_types.append(str(t))

        if req and orig_types:
            req_types = f"{req} | " + " | ".join(orig_types)
        elif req:
            req_types = req
        elif orig_types:
            req_types = " | ".join(orig_types)
        else:
            req_types = ""

        # 引数部
        if req_types:
            arg = f"request: Optional[{req_types}] = None"
        else:
            arg = ""
        ret = "Any"
        # コメント・サマリーも維持
        if getattr(api, "summary", None):
            lines.append(f"    # {api.summary}")
        if getattr(api, "description", None):
            lines.append(f"    # {api.description}")
        if arg:
            lines.append(f"    async def {api.name}(self, {arg}) -> {ret}: ...")
        else:
            lines.append(f"    async def {api.name}(self) -> {ret}: ...")

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Created: {filename}")


