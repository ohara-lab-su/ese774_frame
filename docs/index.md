# Ese774 Frame 似非774 (FastAPI Frame)

view on [github](https://github.com/ohara-lab-su/ese774_frame/) / [ohara-lab-su (doc)](https://ohara-lab-su.github.io/)

```{toctree}
:maxdepth: 2
:caption: Contents:

api/modules
tutorials/ese774_intro
```

`ese774_frame` は、機器制御クラスを FastAPI 経由で公開し、クライアント側から元の制御クラスに近い形で呼び出すための通信フレームである。

## 透過プロキシ型の通信フレーム

基本構成は以下である。

- 機器制御クラス
- FastAPI router / server
- Sync / Async client
- 機器制御プログラム

サーバー側とクライアント側の通信処理は `ese774_frame` が担当し、利用側では Python のメソッド呼び出しに近い形で制御 API を使う。

## 機器ごとに用意するもの

機器パッケージでは以下を用意する。

- 機器制御クラス
- `ApiSpec`
- Pydantic request model
- router class
- Sync / Async client class
- `.pyi` 生成スクリプト
- `server_fastapi/__init__.py` における `register_device_proxy()` 登録

`ApiSpec` は、どのメソッドを HTTP API として公開するかを定義する。SPring-8 的な用語では、一種の `config.tbl` に近い役割を持つ。

## DeviceProxy と型補完

`DeviceProxy()` は、登録済み device class 名から client 実体を作成するための共通入口である。

```python
from ese774_frame import DeviceProxy

client = DeviceProxy(
    "Xdm1000Ctrl",
    config=config,
    async_mode=False,
)
```

`DeviceProxy()` は registry を使うため、実行時には device class 名から client class を決定できる。一方、静的解析では registry の中身を追えないため、IDE 補完にはデバイス側の `.pyi` が必要となる。

そのため、各デバイスパッケージでは `make_pyi_device_proxy()` を使い、`server_fastapi/__init__.pyi` に `DeviceProxy()` の overload を生成する。

利用側で補完を使う場合は、デバイスパッケージ側の `DeviceProxy` を import する。

```python
from xdm1000.server_fastapi import DeviceProxy

client = DeviceProxy(
    "Xdm1000Ctrl",
    config=config,
    async_mode=False,
)
```

実行時の `DeviceProxy` は `ese774_frame.DeviceProxy` を re-export したものであり、補完用の型情報だけをデバイスパッケージ側の `.pyi` で与える。

## 作者
- 
- Kengo NAKADA
