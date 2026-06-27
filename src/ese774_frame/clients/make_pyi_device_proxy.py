#!/usr/bin/env python
# -*- coding: utf-8 -*-

from pathlib import Path
from typing import Dict, List, Optional


def make_pyi_device_proxy(
    filename: str,
    import_lines: List[str],
    device_class: str,
    sync_client_class_name: str,
    async_client_class_name: str,
    aliases: Optional[List[str]] = None,
    all_names: Optional[List[str]] = None,
) -> None:
    """DeviceProxy 用 pyi を生成する。

    Args:
        filename: 出力先 pyi ファイル。
        import_lines: 出力する import 行。
        device_class: 登録済み device class 名。
        sync_client_class_name: 同期 client class 名。
        async_client_class_name: 非同期 client class 名。
        aliases: device class の alias 名。
        all_names: __all__ に出力する名前。
    """
    names = [device_class]

    if aliases is not None:
        names.extend(aliases)

    lines = [
        "from typing import Any, Literal, Optional, overload",
        "",
    ]

    lines.extend(import_lines)
    lines.append("")

    for name in names:
        lines.extend(
            [
                "@overload",
                "def DeviceProxy(",
                '    device_class: Literal["%s"],' % name,
                "    *args: Any,",
                "    async_mode: Literal[False] = False,",
                "    **kwargs: Any,",
                ") -> %s: ..." % sync_client_class_name,
                "",
                "@overload",
                "def DeviceProxy(",
                '    device_class: Literal["%s"],' % name,
                "    *args: Any,",
                "    async_mode: Literal[True],",
                "    **kwargs: Any,",
                ") -> %s: ..." % async_client_class_name,
                "",
            ]
        )

    lines.extend(
        [
            "def DeviceProxy(",
            "    device_class: str,",
            "    *args: Any,",
            "    async_mode: Optional[bool] = None,",
            "    **kwargs: Any,",
            ") -> Any: ...",
            "",
        ]
    )

    if all_names is not None:
        lines.append("__all__ = [")
        for name in all_names:
            lines.append('    "%s",' % name)
        lines.append("]")
        lines.append("")

    Path(filename).write_text("\n".join(lines), encoding="utf-8")
