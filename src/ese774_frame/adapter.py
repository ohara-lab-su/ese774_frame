#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Kengo NAKADA:
https://github.com/shimane-dev, https://github.com/kengo-nakada
kengo.nakada@mat.shimane-u.ac.jp, kengo.nakada@gmail.com

FastAPI frame adapter.

責務:
- 通信境界(JSON)で Python 値を安全に往復させる
- tuple を JSON で失わないようにマーカー化して復元する
- bytes/bytearray を base64 へ変換して復元する
- dispatch 経路の args/kwargs/result を pack/unpack する

注意:
- 現行フローは JSON ベース。
- pickle 系ヘルパーは互換のため残っているが、通常経路では使わない。
"""

from __future__ import annotations
from typing import Any, Dict, Tuple, Optional
import base64
import json
import pickle

# payload 形式の識別キーと値
_FRAME_KEY = "__frame__"
_FRAME_JSON = "json"
_FRAME_PICKLE = "pickle"

# tuple を JSON で失わないためのマーカー
_TUPLE_MAGIC_KEY = "__frame_tuple__"


class _BytesJsonEncoder(json.JSONEncoder):
    """bytes/bytearray を base64 にして JSON 化する Encoder。"""

    def default(
        self,
        obj: Any,
    ) -> Any:
        # bytes は JSON で直接扱えないため base64 化して辞書化
        if isinstance(obj, (bytes, bytearray)):
            b64: str = base64.b64encode(bytes(obj)).decode("ascii")
            return {"__bytes__": b64}
        return json.JSONEncoder.default(self, obj)


def _bytes_json_object_hook(
    d: Dict[str, Any],
) -> Any:
    """json.loads の object_hook: __bytes__ を bytes に戻す。"""
    # JSON 復元時に bytes マーカーを検出したら bytes に戻す
    if "__bytes__" in d:
        b64 = d["__bytes__"]
        if isinstance(b64, str):
            return base64.b64decode(b64.encode("ascii"))
    return d


def _contains_non_json(
    obj: Any,
) -> bool:
    """
    JSON で表現しにくい要素が含まれるかを判定する。

    - tuple は JSON で list になってしまうため特殊扱い
    - dict
    """
    # JSON が素直に扱える型は False
    if isinstance(obj, (str, int, float, bool, type(None))):
        return False
    if isinstance(obj, (bytes, bytearray)):
        return True
    # tuple は JSON で失われるので中身も再帰チェック
    if isinstance(obj, tuple):
        #  return True
        return any(_contains_non_json(x) for x in obj)
    # list は中身を再帰チェック
    if isinstance(obj, list):
        return any(_contains_non_json(x) for x in obj)
    # dict は key が str でないと JSON 互換ではない
    if isinstance(obj, dict):
        for k, v in obj.items():
            if not isinstance(k, str):
                return True
            if _contains_non_json(v):
                return True
        return False
    # その他の型は JSON で表せない
    return True


def _prepare_json(obj: Any) -> Any:
    """
    JSON で情報が落ちる要素を前処理する。

    - tuple は {_TUPLE_MAGIC_KEY: [...]} 形式で保持
    """
    # tuple はマーカー付き dict に変換して情報を保持
    if isinstance(obj, tuple):
        return {_TUPLE_MAGIC_KEY: [_prepare_json(x) for x in obj]}
    # list/dict は中身を再帰的に処理
    if isinstance(obj, list):
        return [_prepare_json(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _prepare_json(v) for k, v in obj.items()}
    return obj


def _restore_json(obj: Any) -> Any:
    """
    _prepare_json で変換された JSON を元の Python 表現に戻す。

    - __bytes__ は bytes に復元
    - _TUPLE_MAGIC_KEY は tuple に復元
    """
    # dict を走査して bytes/tuple のマーカーを復元
    if isinstance(obj, dict):
        if "__bytes__" in obj:
            b64 = obj["__bytes__"]
            if isinstance(b64, str):
                return base64.b64decode(b64.encode("ascii"))

        if _TUPLE_MAGIC_KEY in obj:
            items = obj[_TUPLE_MAGIC_KEY]
            if isinstance(items, list):
                return tuple(_restore_json(x) for x in items)
            if isinstance(items, tuple):
                return tuple(_restore_json(x) for x in items)
        return {k: _restore_json(v) for k, v in obj.items()}

    # list も再帰復元
    if isinstance(obj, list):
        return [_restore_json(x) for x in obj]
    return obj


def _pack_json(
    obj: Any,
) -> Any:
    """JSON で表現できるかを確認して、そのまま返す。"""
    json.dumps(
        obj,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return obj


def _pack_pickle(
    obj: Any,
) -> Dict[str, Any]:
    """pickle 形式で pack する（base64 で JSON に載せる）。"""
    # pickle バイト列を base64 化して JSON に載せる
    b = pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)
    b64 = base64.b64encode(b).decode("ascii")
    return {_FRAME_KEY: _FRAME_PICKLE, "payload": b64}


def pack_result(
    obj: Any,
) -> Any:
    """
    結果を pack する。
    JSON で表現できることだけ保証し、そのまま返す。
    """
    # JSON 化できるかだけ確認（例外が出れば呼び出し側で問題に気付ける）
    json.dumps(
        _prepare_json(obj),
        cls=_BytesJsonEncoder,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return _prepare_json(obj)


def unpack_result(
    payload: Any,
) -> Any:
    """
    JSON で届いた payload を Python に戻す。
    """
    if payload is None:
        return None
    return _restore_json(payload)


def pack_args(
    args: Tuple[Any, ...],
) -> Dict[str, Any]:
    """args を pack する（list 化して pack_result に委譲）。"""
    # args は JSON 化しやすい list に変換して pack
    return pack_result(list(args))


def unpack_args(
    payload: Any,
) -> Tuple[Any, ...]:
    """pack_args の逆変換。"""
    obj = unpack_result(payload)
    if obj is None:
        return tuple()
    if isinstance(obj, list):
        return tuple(obj)
    raise TypeError("args は list として復元される必要があります。")


def pack_kwargs(
    kwargs: Dict[str, Any],
) -> Dict[str, Any]:
    """kwargs を pack する（dict のまま pack_result に委譲）。"""
    # kwargs は dict のまま pack
    return pack_result(kwargs)


def unpack_kwargs(
    payload: Any,
) -> Dict[str, Any]:
    """pack_kwargs の逆変換。"""
    obj = unpack_result(payload)
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    raise TypeError("kwargs は dict として復元される必要があります。")
