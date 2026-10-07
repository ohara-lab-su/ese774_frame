# Tutorial

This tutorial describes the basic v0.6.1 usage of `ese774_frame`.

The primary configuration now uses fully automatic dispatch with `api_spec=None`. Pydantic request models and `ApiSpec`
are optional and are used when an explicit HTTP/OpenAPI contract is required.

## Create the device-control class

```python
#!/usr/bin/env python
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class SimpleStatus:
    name: str
    counter: int


class SimpleCtrl:
    def __init__(self, name: str = "simple", logger: Optional[Any] = None):
        self._name = name
        self._counter = 0
        self._logger = logger

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        self._name = value

    def ping(self) -> str:
        return "pong"

    def add(self, a: int, b: int) -> int:
        return a + b

    def echo(self, msg: str) -> str:
        return msg

    def sum_list(self, values: List[float]) -> float:
        return float(sum(values))

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

    def make_tuple(self, a: int, b: str) -> Tuple[int, str]:
        return (a, b)

    def make_dict(self, key: str, value: Any) -> Dict[str, Any]:
        return {key: value}

    def maybe(self, x: Optional[int] = None) -> Optional[int]:
        return x

    def get_state(self) -> SimpleStatus:
        self._counter += 1
        return SimpleStatus(name=self._name, counter=self._counter)

    def general(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return {"args": list(args), "kwargs": dict(kwargs)}
```

Public methods and static properties are exposed by automatic dispatch. Members whose names start with `_` are not
exposed. A dataclass such as `SimpleStatus` can be reconstructed on the client when the method has a return annotation.

## Start the server

The basic automatic configuration does not require Pydantic models, `ApiSpec`, or a device-specific Router.

```python
#!/usr/bin/env python

from ese774_frame.api_server import FastApiServer

from ctrl import SimpleCtrl
from x_logger.x_logger import XLogger

if __name__ == "__main__":
    logger = XLogger(log_level="debug", logger_name="SimpleServer")

    server = FastApiServer(
        device_cls=SimpleCtrl,
        router_cls=None,
        config=None,
        api_spec=None,
        device_kwargs={"name": "simple"},
        logger=logger,
        logger_name="SimpleServer",
        lifespan_msg_prefix="SIMPLE",
        object_name="simple",
    )

    server.run(host="127.0.0.1", port=8000)
```

With both `router_cls=None` and `api_spec=None`, the framework uses its standard `DeviceRouter`.

Use `dispatch_exclude` for public APIs that must not be exposed.

## Call the device from a client

Synchronous client:

```python
from ese774_frame.clients import SyncDeviceClient

client = SyncDeviceClient(
    server_ip="127.0.0.1",
    server_port=8000,
    object_name="simple",
)

print(client.ping())
print(client.add(1, 2))
print(client.get_state())

print(client.name)
client.name = "renamed"
```

Asynchronous client methods are awaited:

```python
from ese774_frame.clients import AsyncDeviceClient

client = AsyncDeviceClient(
    server_ip="127.0.0.1",
    server_port=8000,
    object_name="simple",
)

print(await client.ping())
print(await client.add(1, 2))
print(await client.get_state())
```

Properties still use normal attribute syntax with the asynchronous client.

## Generate client `.pyi` files

Automatic dispatch resolves methods at runtime, so generate client stubs from the device class for IDE completion.

```python
#!/usr/bin/env python

from pathlib import Path

from ese774_frame.clients.make_pyi_device_client import make_pyi_device_client

from ctrl import SimpleCtrl


def main() -> None:
    root = Path(__file__).resolve().parent

    make_pyi_device_client(
        filename=str(root / "clients" / "async_simple_client.pyi"),
        class_name="AsyncSimpleClient",
        async_mode=True,
        device_class=SimpleCtrl,
    )

    make_pyi_device_client(
        filename=str(root / "clients" / "sync_simple_client.pyi"),
        class_name="SyncSimpleClient",
        async_mode=False,
        device_class=SimpleCtrl,
    )


if __name__ == "__main__":
    main()
```

`api_spec` and `device_class` must not be supplied together. `make_pyi_device_router()` is for ApiSpec mode and is not
required for the basic automatic-dispatch path.

## Register DeviceProxy

```python
from ese774_frame import DeviceProxy
from ese774_frame.clients import register_device_proxy

register_device_proxy(
    "SimpleCtrl",
    api_spec=None,
    object_name="simple",
    default_async_mode=False,
    aliases=["simple"],
)
```

Client code:

```python
from server import DeviceProxy

client = DeviceProxy(
    "SimpleCtrl",
    server_ip="127.0.0.1",
    server_port=8000,
    async_mode=False,
)

print(client.ping())
print(client.add(1, 2))
```

Device-specific client classes can still be registered through `sync_client_cls` / `async_client_cls`. If they are
omitted, the framework standard clients are used.

## Use a device-specific Router when necessary

A custom Router can be used for APIs with special server-side behavior while all other APIs continue to use automatic
dispatch.

```python
from ese774_frame.routers import DeviceRouter


class SimpleRouter(DeviceRouter):
    pass
```

Pass this class as `router_cls=SimpleRouter` while keeping `api_spec=None`.

## Use ApiSpec/Pydantic when an explicit contract is required

```python
from pydantic import BaseModel
from ese774_frame.models.api_spec import ApiSpec


class AddRequest(BaseModel):
    a: int
    b: int


simple_api_spec = [
    ApiSpec(
        name="add",
        object_name="simple",
        request_model=AddRequest,
        response_model=None,
        method="post",
        summary="add",
        description="a + b",
    ),
]
```

Use `kind="property"` for an explicitly specified property and `writable=True` when it is writable. ApiSpec mode
requires a Router class. Client and Router `.pyi` files can be generated from `api_spec` as before.

## Author

- Kengo NAKADA
