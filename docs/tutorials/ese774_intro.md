# チュートリアル

このセクションでは ese774_frame の使い方を段階的に説明します。

## フレームに食わせる制御クラスを用意する

```python
#!/usr/bin/env python
from typing import Any, Dict, List, Optional, Tuple


class SimpleCtrl:
    """
    フレームワークテスト用の最小 Ctrl
    - 引数/戻り値パターンの検証用
    """

    def __init__(self, name: str = "simple", logger: Optional[Any] = None):
        self._name = name
        self._counter = 0
        self._logger = logger

    # property (属性)
    @property
    def name(self) -> str:
        return self._name

    # 戻り値: str
    def ping(self) -> str:
        return "pong"

    # 引数2つ -> int
    def add(self, a: int, b: int) -> int:
        return a + b

    # 引数1つ -> str
    def echo(self, msg: str) -> str:
        return msg

    # list -> float
    def sum_list(
        self,
        values: List[float],
    ) -> float:
        return float(sum(values))

    # kwargs混在 -> dict
    def mix(
        self,
        a: int,
        b: int = 1,
        *,
        scale: float = 1.0,
        tag: Optional[str] = None,
    ) -> Dict[str, Any]:
        val = (a + b) * scale
        return {"value": val, "tag": tag}

    # tuple 戻り
    def make_tuple(
        self,
        a: int,
        b: str,
    ) -> Tuple[int, str]:
        return (a, b)

    # dict 戻り
    def make_dict(self, key: str, value: Any) -> Dict[str, Any]:
        return {key: value}

    # Optional -> Optional
    def maybe(
        self,
        x: Optional[int] = None,
    ) -> Optional[int]:
        return x

    # None 戻り
    def set_name(
        self,
        name: str,
    ) -> None:
        self._name = name

    # 状態取得
    def get_state(self) -> Dict[str, Any]:
        self._counter += 1
        return {"name": self._name, "counter": self._counter}

    # 一般形の引数 (*args, **kwargs)
    def general(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        return {"args": list(args), "kwargs": dict(kwargs)}

```

## 公開APIを定義する
pydantec として SPEC と model の二つを用意します

### spec
関数名や動作などを定義するリストを作ります。
この定義は OpenAPI として公開ます。

```python
#!/usr/bin/env python
from ese774_frame.models.api_spec import ApiSpec

from server.models import (
    AddRequest,
    EchoRequest,
    SumListRequest,
    MixRequest,
    TupleRequest,
    DictRequest,
    MaybeRequest,
    SetNameRequest,
)

# response_model は None（pydanticはI/F定義のみ。戻り値は純粋Pythonを透過）
simple_api_spec = [
    ApiSpec(
        name="ping",
        object_name="simple",
        request_model=None,
        response_model=None,
        method="post",
        summary="ping",
        description="return 'pong'",
    ),
    ApiSpec(
        name="add",
        object_name="simple",
        request_model=AddRequest,
        response_model=None,
        method="post",
        summary="add",
        description="a + b",
    ),
    ApiSpec(
        name="echo",
        object_name="simple",
        request_model=EchoRequest,
        response_model=None,
        method="post",
        summary="echo",
        description="echo msg",
    ),
    ApiSpec(
        name="sum_list",
        object_name="simple",
        request_model=SumListRequest,
        response_model=None,
        method="post",
        summary="sum_list",
        description="sum(values)",
    ),
    ApiSpec(
        name="mix",
        object_name="simple",
        request_model=MixRequest,
        response_model=None,
        method="post",
        summary="mix",
        description="(a+b)*scale",
    ),
    ApiSpec(
        name="make_tuple",
        object_name="simple",
        request_model=TupleRequest,
        response_model=None,
        method="post",
        summary="make_tuple",
        description="return tuple",
    ),
    ApiSpec(
        name="make_dict",
        object_name="simple",
        request_model=DictRequest,
        response_model=None,
        method="post",
        summary="make_dict",
        description="return dict",
    ),
    ApiSpec(
        name="maybe",
        object_name="simple",
        request_model=MaybeRequest,
        response_model=None,
        method="post",
        summary="maybe",
        description="optional return",
    ),
    ApiSpec(
        name="set_name",
        object_name="simple",
        request_model=SetNameRequest,
        response_model=None,
        method="post",
        summary="set_name",
        description="set name",
    ),
    ApiSpec(
        name="get_state",
        object_name="simple",
        request_model=None,
        response_model=None,
        method="post",
        summary="get_state",
        description="state dict",
    ),
    ApiSpec(
        name="name",
        object_name="simple",
        request_model=None,
        response_model=None,
        method="post",
        summary="name (property)",
        description="property access",
    ),
]

```

### mode
定義で用いている引数や戻り値の形を定義したクラスです。

```python
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

```

## 制御クラスをサーバーメソッドにいくわせてサーバーを起動する
基本的に、使う人は「制御クラス」を指定するだけで
あとは何もしません

```python
#!/usr/bin/env python
"""
K.NAKADA, kengo.nakada@gmail.com, kengo.nakada@mat.shimane-u.ac.jp
"""

from typing import Optional, Any, Callable

from ese774_frame.api_server import FastApiServer
from ese774_frame.routers.device_router import DeviceRouter

from ctrl import SimpleCtrl
from server.spec import simple_api_spec

from x_logger.x_logger import XLogger

import logging

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

if __name__ == "__main__":
    logger = XLogger(log_level="debug", logger_name="SimpleServer")
    server = FastApiServer(
        device_cls=SimpleCtrl,
        router_cls=DeviceRouter,
        config=None,
        api_spec=simple_api_spec,
        device_kwargs={"name": "simple"},
        logger=logger,
        logger_name="SimpleServer",
        lifespan_msg_prefix="SIMPLE",
    )
    server.run(host="127.0.0.1", port=8000)

```
## クライアントクラスを Frame を継承して作る

## クライアントで制御プログラムを書く