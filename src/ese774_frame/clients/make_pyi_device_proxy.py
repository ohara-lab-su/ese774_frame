#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""DeviceProxy 用 pyi 生成器。

spec / 完全自動のどちらでも公開入口は ``make_pyi_device_proxy`` の1つ。
DeviceProxy の型付けに必要なのは最終的な sync/async client 型なので、
API の定義方法そのものはここでは分岐させない。
"""

from __future__ import annotations

from typing import Iterable, Optional


def _literal_values(values: Iterable[str]) -> str:
    items = [repr(str(value)) for value in values]
    if not items:
        raise ValueError("device_names must not be empty")
    return ", ".join(items)


def make_pyi_device_proxy(
    *,
    filename: str,
    device_names: Iterable[str],
    async_client_module: str,
    async_client_class: str,
    sync_client_module: str,
    sync_client_class: str,
    default_async_mode: bool = True,
    proxy_name: str = "DeviceProxy",
    create_proxy_name: Optional[str] = "create_device_proxy",
) -> None:
    """DeviceProxy の戻り型を登録済み client 型へ結び付ける pyi を生成する。

    ``api_spec`` で client pyi を生成した場合も、``device_class`` から完全自動で
    client pyi を生成した場合も、この関数の呼び方は同じ。
    """
    names = _literal_values(device_names)

    default_client = (
        async_client_class
        if default_async_mode
        else sync_client_class
    )

    lines = [
        "from __future__ import annotations",
        "",
        "from typing import Any, Callable, Literal, overload",
        f"from {async_client_module} import {async_client_class}",
        f"from {sync_client_module} import {sync_client_class}",
        "",
        "@overload",
        (
            f"def {proxy_name}("
            f"device_class: Literal[{names}], "
            "*args: Any, async_mode: Literal[True], **kwargs: Any"
            f") -> {async_client_class}: ..."
        ),
        "@overload",
        (
            f"def {proxy_name}("
            f"device_class: Literal[{names}], "
            "*args: Any, async_mode: Literal[False], **kwargs: Any"
            f") -> {sync_client_class}: ..."
        ),
        "@overload",
        (
            f"def {proxy_name}("
            f"device_class: Literal[{names}], "
            "*args: Any, async_mode: None = None, **kwargs: Any"
            f") -> {default_client}: ..."
        ),
        (
            f"def {proxy_name}("
            "device_class: str, *args: Any, "
            "async_mode: bool | None = None, **kwargs: Any"
            f") -> {async_client_class} | {sync_client_class}: ..."
        ),
    ]

    if create_proxy_name:
        lines.extend(
            [
                "",
                (
                    f"def {create_proxy_name}("
                    f"device_class: Literal[{names}]"
                    ") -> Callable[..., "
                    f"{async_client_class} | {sync_client_class}]: ..."
                ),
            ]
        )

    with open(filename, "w", encoding="utf-8") as file:
        file.write("\n".join(lines) + "\n")

    print(f"Created: {filename}")
