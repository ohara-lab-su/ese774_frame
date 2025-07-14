#!/usr/bin/env pyton
"""

Kengo NAKADA:
https://github.com/shimane-dev, https://github.com/kengo-nakada
kengo.nakada@mat.shimane-u.ac.jp, kengo.nakada@gmail.com
"""

# print(version("cobotta2-system"))

from dataclasses import dataclass
from typing import Type, Optional, Literal, List, Tuple
from pydantic import BaseModel


@dataclass
class ApiSpec:
    request_model: Optional[Type[BaseModel]]
    response_model: Optional[Type[BaseModel]]
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
