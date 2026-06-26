#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Type

from ese774_frame.clients.async_device_client import AsyncDeviceClient
from ese774_frame.clients.sync_device_client import SyncDeviceClient


@dataclass
class DeviceProxyEntry:
    device_class: str
    async_client_cls: Optional[Type[Any]] = None
    sync_client_cls: Optional[Type[Any]] = None
    api_spec: Optional[list] = None
    object_name: Optional[str] = None
    default_async_mode: bool = True


_DEVICE_PROXY_REGISTRY: Dict[str, DeviceProxyEntry] = {}


def register_device_proxy(
    device_class: str,
    *,
    async_client_cls: Optional[Type[Any]] = None,
    sync_client_cls: Optional[Type[Any]] = None,
    api_spec: Optional[list] = None,
    object_name: Optional[str] = None,
    default_async_mode: bool = True,
    aliases: Optional[List[str]] = None,
) -> None:
    if not device_class:
        raise ValueError("device_class is required")

    if async_client_cls is None and sync_client_cls is None and api_spec is None:
        raise ValueError("async_client_cls, sync_client_cls, or api_spec is required")

    entry = DeviceProxyEntry(
        device_class=device_class,
        async_client_cls=async_client_cls,
        sync_client_cls=sync_client_cls,
        api_spec=api_spec,
        object_name=object_name,
        default_async_mode=default_async_mode,
    )

    names = [device_class]
    if aliases:
        names.extend(aliases)

    for name in names:
        _DEVICE_PROXY_REGISTRY[name] = entry


def unregister_device_proxy(device_class: str) -> None:
    _DEVICE_PROXY_REGISTRY.pop(device_class, None)


def get_device_proxy_entry(device_class: str) -> DeviceProxyEntry:
    if device_class not in _DEVICE_PROXY_REGISTRY:
        raise KeyError(
            f"DeviceProxy is not registered: {device_class}. "
            "Call register_device_proxy(...) first."
        )
    return _DEVICE_PROXY_REGISTRY[device_class]


def list_device_proxies() -> List[str]:
    return sorted(_DEVICE_PROXY_REGISTRY.keys())


def _resolve_object_name(entry: DeviceProxyEntry) -> str:
    if entry.object_name:
        return entry.object_name
    if entry.api_spec:
        return entry.api_spec[0].object_name
    return "device"


def DeviceProxy(
    device_class: str,
    *args,
    async_mode: Optional[bool] = None,
    **kwargs,
) -> Any:
    """
    device_class から client 実体を生成する。

    async_mode:
        True  -> async client
        False -> sync client
        None -> register_device_proxy(..., default_async_mode=...) に従う

    async_mode 以外の *args/**kwargs は client class へ完全転送する。
    """
    entry = get_device_proxy_entry(device_class)

    if async_mode is None:
        async_mode = entry.default_async_mode

    if async_mode:
        if entry.async_client_cls is not None:
            return entry.async_client_cls(*args, **kwargs)

        if entry.api_spec is None:
            raise ValueError(f"async client is not registered: {device_class}")

        kwargs.setdefault("api_spec", entry.api_spec)
        kwargs.setdefault("object_name", _resolve_object_name(entry))
        return AsyncDeviceClient(*args, **kwargs)

    if entry.sync_client_cls is not None:
        return entry.sync_client_cls(*args, **kwargs)

    if entry.api_spec is None:
        raise ValueError(f"sync client is not registered: {device_class}")

    kwargs.setdefault("api_spec", entry.api_spec)
    kwargs.setdefault("object_name", _resolve_object_name(entry))
    return SyncDeviceClient(*args, **kwargs)


def create_device_proxy(device_class: str):
    """device_class を固定した DeviceProxy を作成する。

    instance = DiceProxy("device_class") でinstance を作ると
    instance.pyi での補完が機能しない問題に対処しやすいように
    フレーム側でのサポート関数

    Args:
        device_class: 登録済み device class 名。

    Returns:
        device_class を固定した proxy 関数。
    """

    def proxy(
        *args,
        async_mode: Optional[bool] = None,
        **kwargs,
    ) -> Any:
        return DeviceProxy(
            device_class,
            *args,
            async_mode=async_mode,
            **kwargs,
        )

    return proxy
