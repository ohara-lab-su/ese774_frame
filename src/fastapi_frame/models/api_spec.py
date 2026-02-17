#!/usr/bin/env pyton
"""

Kengo NAKADA:
https://github.com/shimane-dev, https://github.com/kengo-nakada
kengo.nakada@mat.shimane-u.ac.jp, kengo.nakada@gmail.com
"""

# print(version("cobotta2-system"))

from dataclasses import dataclass
from typing import Any, Type, Optional, Literal, List, Tuple
from pydantic import BaseModel

try:
    from pydantic import TypeAdapter, parse_obj_as
except Exception:
    TypeAdapter = None
    parse_obj_as = None


@dataclass
class ApiSpec:
    request_model: Optional[Type[BaseModel]]
    response_model: Optional[Any]
    name: str
    object_name: str = "cobotta"
    function_name: str = None
    path: Optional[str] = None
    method: str = "post"
    description: str = ""
    summary: Optional[str] = ""

    def __post_init__(self):
        if self.function_name is None:
            self.function_name = self.name
        if self.path is None:
            self.path = f"/instance/{self.object_name}/{self.name}"

    def decode_response(self, payload: Any) -> Any:
        if self.response_model is None:
            return payload

        model_cls = self.response_model

        def _get_model_fields(cls: Any) -> dict:
            v2_fields = getattr(cls, "model_fields", None)
            if isinstance(v2_fields, dict):
                return v2_fields
            v1_fields = getattr(cls, "__fields__", None)
            if isinstance(v1_fields, dict):
                return v1_fields
            return {}

        def _dump_model(model: Any) -> Any:
            if hasattr(model, "model_dump") and callable(model.model_dump):
                return model.model_dump()
            if hasattr(model, "dict") and callable(model.dict):
                return model.dict()
            return model

        # BaseModel class
        if hasattr(model_cls, "model_validate") or hasattr(model_cls, "parse_obj"):
            if hasattr(model_cls, "model_validate"):
                model = model_cls.model_validate(payload)  # pydantic v2
            else:
                model = model_cls.parse_obj(payload)  # pydantic v1

            if hasattr(model, "root"):
                return model.root
            if hasattr(model, "__root__"):
                return model.__root__

            fields = _get_model_fields(model.__class__)
            field_names = list(fields.keys())

            # 1フィールドモデルは透過戻し（例: result ラッパ）
            if len(field_names) == 1:
                return getattr(model, field_names[0])

            return _dump_model(model)

        # built-in / typing (list[...], tuple[...], dict[...], Union など)
        if TypeAdapter is not None:
            try:
                return TypeAdapter(model_cls).validate_python(payload)
            except Exception:
                pass

        if parse_obj_as is not None:
            try:
                return parse_obj_as(model_cls, payload)
            except Exception:
                pass

        return payload
