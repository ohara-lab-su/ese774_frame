# ese774_frame — 似非774（FastAPI 通信フレーム）

[![en](https://img.shields.io/badge/lang-en-red.svg)](https://ohara-lab-su.github.io/ese774_frame/en/index.html) [![ja](https://img.shields.io/badge/lang-ja-blue.svg)](https://ohara-lab-su.github.io/ese774_frame/ja/index.html)

[GitHub リポジトリ](https://github.com/ohara-lab-su/ese774_frame/) · [プロジェクト一覧](https://ohara-lab-su.github.io/)

`ese774_frame` は、サーバー側の機器制御クラスを FastAPI 経由で公開し、同期・非同期 Python クライアントから元の制御クラスに近い形で操作するための通信フレームである。

現行の基本方式は `api_spec=None` による完全自動 dispatch であり、公開メソッドごとの Pydantic request model や `ApiSpec` は必須ではない。明示的な HTTP/OpenAPI 契約が必要な場合には `ApiSpec` と Pydantic を利用できる。必要に応じて機器固有の Router や Client を定義する。

```{toctree}
:maxdepth: 2
:caption: マニュアル

tutorials/ese774_intro
```

```{toctree}
:maxdepth: 2
:caption: APIリファレンス

api/index
```

## DeviceProxy と型補完

`DeviceProxy` は登録済みの機器クライアントを生成する共通入口である。実行時の登録情報と、IDE 補完のために自動生成する機器固有 `.pyi` を区別する。完全自動 dispatch、`DeviceProxy` の登録、必要に応じた `ApiSpec` モードについてはチュートリアルを参照。

## 作者

Kengo NAKADA
