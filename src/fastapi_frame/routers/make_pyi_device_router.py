#!/usr/bin/env python
"""
Kengo NAKADA:
https://github.com/shimane-dev, https://github.com/kengo-nakada
kengo.nakada@mat.shimane-u.ac.jp, kengo.nakada@gmail.com

PYIスタブファイル自動生成（Router用）
"""

from collections import defaultdict


def as_one_line_comment(val):
    if isinstance(val, (list, tuple)):
        return " ".join(
            str(v).replace("\r\n", "\n").replace("\r", "\n").replace("\n", " ").strip()
            for v in val
        )
    s = str(val).replace("\r\n", "\n").replace("\r", "\n")
    return " ".join(line.strip() for line in s.split("\n"))


def make_pyi_device_router(
    filename: str,
    api_spec,
    class_name="DeviceRouter",
):
    """
    DeviceRouter 実装に対応する .pyi を生成する。

    方針:
    - api_spec から request_model 型を抽出
    - 実装の手動メソッド（_extract_args_kwargs, _wrap_response など）を明示
    - APIごとの async メソッドシグネチャを出力
    """
    manual_methods = [
        "    @staticmethod",
        "    def _model_field_names(model_cls) -> list[str]: ...",
        "    def _extract_args_kwargs(self, api, request, target_func=None): ...",
        "    def _dispatch_api(self, api, request): ...",
        "    @staticmethod",
        "    def _wrap_response(result, api) -> Any: ...",
        "    def _make_handler(self, api): ...",
        "    async def _dispatch_handler(self, request: dict): ...",
        "    _logger: Any",
        "    router: APIRouter",
    ]

    imports = defaultdict(set)
    for api in api_spec:
        model = getattr(api, "request_model", None)
        if (
            model is not None
            and hasattr(model, "__module__")
            and hasattr(model, "__name__")
        ):
            imports[model.__module__].add(model.__name__)

    import_lines = ["from typing import Optional, Any, Dict, overload"]
    for mod, names in sorted(imports.items()):
        import_lines.append(f"from {mod} import {', '.join(sorted(names))}")
    # import_lines.append("from x_logger.x_logger import XLogger")
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
        "    def __init__(self, device_instance, api_spec, logger: Optional[Any] = None, log_level: str = 'INFO'): ..."
    )
    lines.extend(manual_methods)

    for api in api_spec:
        req = api.request_model.__name__ if getattr(api, "request_model", None) else ""
        orig_types = []

        if getattr(api, "request_model", None):
            fields = getattr(api.request_model, "model_fields", None)
            if isinstance(fields, dict):
                iter_fields = fields.values()
            else:
                iter_fields = getattr(api.request_model, "__fields__", {}).values()

            for field in iter_fields:
                if hasattr(field, "annotation") and field.annotation is not None:
                    t = field.annotation
                elif hasattr(field, "outer_type_") and field.outer_type_ is not None:
                    t = field.outer_type_
                else:
                    t = type(field)

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

        if req_types:
            arg = f"request: Optional[{req_types}] = None"
        else:
            arg = ""

        ret = "Any"

        comment_pieces = []
        if getattr(api, "summary", None):
            s = str(api.summary).replace("\r\n", "\n").replace("\r", "\n")
            comment_pieces.append(
                " ".join(line.strip() for line in s.split("\n") if line.strip())
            )
        if getattr(api, "description", None):
            d = str(api.description).replace("\r\n", "\n").replace("\r", "\n")
            comment_pieces.append(
                " ".join(line.strip() for line in d.split("\n") if line.strip())
            )
        if comment_pieces:
            lines.append(f"    # {' '.join(comment_pieces)}")

        if arg:
            lines.append(f"    async def {api.name}(self, {arg}) -> {ret}: ...")
        else:
            lines.append(f"    async def {api.name}(self) -> {ret}: ...")

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Created: {filename}")
