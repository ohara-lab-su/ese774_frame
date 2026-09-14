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
from typing import Any, Dict, Tuple, Optional, get_args, get_origin, get_type_hints, Union
from dataclasses import fields, is_dataclass
import importlib
import types
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
    # bytes/bytearray は base64 マーカー付き dict に変換する。
    # JSONResponse/httpx の json= は標準 JSON encoder を使うため、
    # 検査時だけ Encoder に任せず返却 payload 自体を JSON 互換にする。
    if isinstance(obj, (bytes, bytearray)):
        b64 = base64.b64encode(bytes(obj)).decode("ascii")
        return {"__bytes__": b64}

    # dataclass は公開フィールドを JSON 互換 dict に変換する。
    # 型の復元は戻り値アノテーション由来の metadata を使用するため、
    # payload 自体には Python class 情報を埋め込まない。
    if is_dataclass(obj) and not isinstance(obj, type):
        return {
            field.name: _prepare_json(getattr(obj, field.name))
            for field in fields(obj)
        }

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


def type_annotation_to_descriptor(annotation: Any) -> Optional[Dict[str, Any]]:
    """Python 型アノテーションを JSON 互換の型記述へ変換する。

    完全自動 dispatch の戻り値型を client へ伝えるために使用する。
    dataclass、Union/Optional、list、tuple、dict を再帰的に記述する。
    """
    if annotation is None or annotation is inspect_empty():
        return None

    if annotation is Any:
        return {"kind": "any"}

    if annotation is type(None):
        return {"kind": "none"}

    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin in (Union, types.UnionType):
        return {
            "kind": "union",
            "args": [type_annotation_to_descriptor(arg) for arg in args],
        }

    if origin is list:
        item_type = args[0] if args else Any
        return {
            "kind": "list",
            "item": type_annotation_to_descriptor(item_type),
        }

    if origin is tuple:
        return {
            "kind": "tuple",
            "items": [type_annotation_to_descriptor(arg) for arg in args],
        }

    if origin is dict:
        key_type = args[0] if len(args) >= 1 else Any
        value_type = args[1] if len(args) >= 2 else Any
        return {
            "kind": "dict",
            "key": type_annotation_to_descriptor(key_type),
            "value": type_annotation_to_descriptor(value_type),
        }

    if isinstance(annotation, type) and is_dataclass(annotation):
        try:
            field_hints = get_type_hints(annotation)
        except Exception:
            field_hints = getattr(annotation, "__annotations__", {}) or {}

        return {
            "kind": "dataclass",
            "module": annotation.__module__,
            "qualname": annotation.__qualname__,
            "fields": {
                field.name: type_annotation_to_descriptor(
                    field_hints.get(field.name, Any)
                )
                for field in fields(annotation)
            },
        }

    if isinstance(annotation, type):
        return {
            "kind": "type",
            "module": annotation.__module__,
            "qualname": annotation.__qualname__,
        }

    return {"kind": "any"}


def inspect_empty() -> Any:
    """inspect.Signature.empty を遅延 import で返す。"""
    import inspect
    return inspect.Signature.empty


def _import_qualified_type(module_name: str, qualname: str) -> Any:
    """module + qualname から Python 型を取得する。"""
    module = importlib.import_module(module_name)
    value = module
    for part in qualname.split("."):
        value = getattr(value, part)
    return value


def _restore_typed(obj: Any, descriptor: Optional[Dict[str, Any]]) -> Any:
    """型記述に従って JSON 復元値を Python 型へ戻す。"""
    if descriptor is None or not isinstance(descriptor, dict):
        return obj

    kind = descriptor.get("kind")

    if kind in (None, "any"):
        return obj

    if kind == "none":
        return None

    if kind == "union":
        if obj is None:
            return None
        for item in descriptor.get("args", []):
            if isinstance(item, dict) and item.get("kind") == "none":
                continue
            try:
                return _restore_typed(obj, item)
            except (TypeError, ValueError, ImportError, AttributeError):
                continue
        return obj

    if kind == "list":
        if not isinstance(obj, list):
            return obj
        item_desc = descriptor.get("item")
        return [_restore_typed(value, item_desc) for value in obj]

    if kind == "tuple":
        if not isinstance(obj, (list, tuple)):
            return obj
        item_descs = descriptor.get("items", [])
        if len(item_descs) == 2 and item_descs[1] is not None:
            second = item_descs[1]
            if isinstance(second, dict) and second.get("kind") == "type" and second.get("qualname") == "Ellipsis":
                return tuple(_restore_typed(value, item_descs[0]) for value in obj)
        return tuple(
            _restore_typed(value, item_descs[index] if index < len(item_descs) else None)
            for index, value in enumerate(obj)
        )

    if kind == "dict":
        if not isinstance(obj, dict):
            return obj
        value_desc = descriptor.get("value")
        return {key: _restore_typed(value, value_desc) for key, value in obj.items()}

    if kind == "dataclass":
        if not isinstance(obj, dict):
            return obj
        cls = _import_qualified_type(
            descriptor["module"],
            descriptor["qualname"],
        )
        if not is_dataclass(cls):
            return obj
        field_descs = descriptor.get("fields", {})
        values = {
            key: _restore_typed(value, field_descs.get(key))
            for key, value in obj.items()
        }
        return cls(**values)

    return obj


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
    type_descriptor: Optional[Dict[str, Any]] = None,
) -> Any:
    """
    JSON で届いた payload を Python に戻す。

    type_descriptor が指定された場合は、完全自動 dispatch の
    戻り値アノテーションに従って dataclass 等を再構築する。
    """
    if payload is None:
        return None
    restored = _restore_json(payload)
    return _restore_typed(restored, type_descriptor)


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
