#!/usr/bin/env python
from typing import List, Optional, Any
from pydantic import BaseModel


class AddRequest(BaseModel):
    a: int
    b: int


class EchoRequest(BaseModel):
    msg: str


class SumListRequest(BaseModel):
    values: List[float]


class MixRequest(BaseModel):
    a: int
    b: int = 1
    scale: float = 1.0
    tag: Optional[str] = None


class TupleRequest(BaseModel):
    a: int
    b: str


class DictRequest(BaseModel):
    key: str
    value: Any


class MaybeRequest(BaseModel):
    x: Optional[int] = None


class SetNameRequest(BaseModel):
    name: str
