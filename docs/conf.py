# sphinx_docs/conf.py
import os, sys

sys.path.insert(0, os.path.abspath("../src"))
sys.path.insert(0, os.path.abspath("../../x_logger/src"))

project = "Project"
language = "ja"


extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",  # google style
]

# Markdown を有効化
extensions = list(set(extensions + ["myst_parser"]))

# .rst と .md の両方を読む
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

# MyST のオプション（軽め）
myst_enable_extensions = [
    "deflist",
    "attrs_block",
    "substitution",
    "colon_fence",
    "linkify",
]
myst_linkify_fuzzy_links = True
myst_heading_anchors = 3


# autosummary で目録ページを自動生成
autosummary_generate = True

# 型ヒント参照で失敗した時の警告を抑制する
nitpick_ignore = [
    ("py:class", "fastapi_frame.clients.async_device_client.AsyncDeviceClient"),
    ("py:class", "fastapi_frame.clients.sync_device_client.SyncDeviceClient"),
    ("py:class", "fastapi_frame.routers.device_router.DeviceRouter"),
    ("py:class", "x_logger.x_logger.XLogger"),
    ("py:class", "Path"),
    ("py:class", "pathlib.Path"),
    ("py:class", "direction"),
    ("py:class", "pydantic.main.BaseModel"),
    ("py:class", "ConfigDict"),
    ("py:class", "enum.Enum"),
    # 必要な型は全てここに追記
]

# 追加で推奨: 型エイリアス
autodoc_type_aliases = {
    "XLogger": "x_logger.x_logger.XLogger",
    "Path": "pathlib.Path",
    "BaseModel": "pydantic.main.BaseModel",
    "ConfigDict": "pydantic.config.ConfigDict",
    "Enum": "enum.Enum",
}

# autodoc の既定オプション：これが無いと“中身が出ない”ことがある
autodoc_default_options = {
    "members": True,
    "undoc-members": True,  # docstring が無いメンバも列挙
    "show-inheritance": True,
    # 必要に応じて:
    # "inherited-members": True,
    # "private-members": True,
}

# 読みやすさ
add_module_names = False
autodoc_typehints = "description"
autodoc_preserve_defaults = True
set_type_checking_flag = True

# CIで重い依存が import できないならここでモック（必要に応じて追記）
autodoc_mock_imports = [
    # "torch", "opencv", "tensorflow", ...
    "win32com",
    "pythoncom",
    "x_logger",
]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "pydantic": ("https://docs.pydantic.dev/latest/", None),
    "fastapi": ("https://fastapi.tiangolo.com/", None),
    # x_logger のようなローカル/私家版はインベントリが無いので参照解決不可
}

# テーマ
html_theme = "sphinx_rtd_theme"  # pip install sphinx-rtd-theme
html_static_path = ["_static"]
