#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Kengo NAKADA:
https://github.com/shimane-dev, https://github.com/kengo-nakada
kengo.nakada@mat.shimane-u.ac.jp, kengo.nakada@gmail.com

FastAPI 用 adapter
- pydantic は I/F 定義・検証のみ
- 実体は Python を透過
- args/kwargs/result を一元的にパック/アンパック
"""

from __future__ import annotations
from typing import Any, Dict, Tuple
import base64
import json
import pickle

_FRAME_KEY = "__frame__"
_FRAME_JSON = "json"
_FRAME_PICKLE = "pickle"


class _BytesJsonEncoder(json.JSONEncoder):
    def default(
        self,
        obj: Any,
    ) -> Any:
        if isinstance(obj, (bytes, bytearray)):
            b64: str = base64.b64encode(bytes(obj)).decode("ascii")
            return {"__bytes__": b64}
        return json.JSONEncoder.default(self, obj)


def _bytes_json_object_hook(
    d: Dict[str, Any],
) -> Any:
    """"""
    if "__bytes__" in d:
        b64 = d["__bytes__"]
        if isinstance(b64, str):
            return base64.b64decode(b64.encode("ascii"))
    return d


def _contains_non_json(
    obj: Any,
) -> bool:
    """"""
    if isinstance(obj, (str, int, float, bool, type(None))):
        return False
    if isinstance(obj, (bytes, bytearray)):
        return False
    if isinstance(obj, tuple):
        return True
    if isinstance(obj, list):
        return any(_contains_non_json(x) for x in obj)
    if isinstance(obj, dict):
        for k, v in obj.items():
            if not isinstance(k, str):
                return True
            if _contains_non_json(v):
                return True
        return False
    return True


def _pack_json(
    obj: Any,
) -> Dict[str, Any]:
    """"""
    s = json.dumps(
        obj,
        cls=_BytesJsonEncoder,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    payload = json.loads(s, object_hook=_bytes_json_object_hook)
    return {_FRAME_KEY: _FRAME_JSON, "payload": payload}


def _pack_pickle(
    obj: Any,
) -> Dict[str, Any]:
    """"""
    b = pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)
    b64 = base64.b64encode(b).decode("ascii")
    return {_FRAME_KEY: _FRAME_PICKLE, "payload": b64}


def pack_result(
    obj: Any,
) -> Dict[str, Any]:
    """"""
    if _contains_non_json(obj):
        return _pack_pickle(obj)
    return _pack_json(obj)


def unpack_result(
    payload: Any,
) -> Any:
    """"""
    if payload is None:
        return None

    if isinstance(payload, dict) and payload.get(_FRAME_KEY) == _FRAME_JSON:
        return payload.get("payload")

    if isinstance(payload, dict) and payload.get(_FRAME_KEY) == _FRAME_PICKLE:
        b64 = payload.get("payload")
        if isinstance(b64, str):
            raw = base64.b64decode(b64.encode("ascii"))
            return pickle.loads(raw)

    return payload


def pack_args(
    args: Tuple[Any, ...],
) -> Dict[str, Any]:
    """"""
    return pack_result(list(args))


def unpack_args(
    payload: Any,
) -> Tuple[Any, ...]:
    """"""
    obj = unpack_result(payload)
    if obj is None:
        return tuple()
    if isinstance(obj, list):
        return tuple(obj)
    raise TypeError("args は list として復元される必要があります。")


def pack_kwargs(
    kwargs: Dict[str, Any],
) -> Dict[str, Any]:
    """"""
    return pack_result(kwargs)


def unpack_kwargs(
    payload: Any,
) -> Dict[str, Any]:
    """"""
    obj = unpack_result(payload)
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    raise TypeError("kwargs は dict として復元される必要があります。")
