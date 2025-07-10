#!/usr/bin/env python3
"""
Device Server for Cobotta [Dynamic/Auto-mapping Version]
"""
import sys
import os
import traceback
import inspect
import types

import tango
from tango.server import Device, command, attribute, device_property, AttrWriteType

from cobotta2.config import Config
from cobotta2.cobotta_ctrl import CobottaCtrl

from x_logger.x_logger import XLogger


# -- 自動生成 DeviceServerクラスのメタファクトリ --
def build_dynamic_cobotta_ds():
    ctrl = CobottaCtrl(
        cobotta_ip=Config.COBOTTA1_IP,
        logger=XLogger(log_level="debug", logger_name="DynamicCobottaDS"),
    )
    methods = {}
    # -- コマンド自動生成 --
    for name, func in inspect.getmembers(ctrl, predicate=inspect.ismethod):
        if name.startswith("_"):
            continue
        sig = inspect.signature(func)
        n_args = len(sig.parameters) - 1  # self省く
        if n_args == 0:
            # 引数無し
            def make_cmd(fname):
                @command(dtype_out=object)
                def cmd(self):
                    return getattr(self._cobotta_ctrl, fname)()

                return cmd

            methods[name] = make_cmd(name)
        else:
            # 引数1つ (多引数も対応できるがCobottaCtrlは基本1引数)
            def make_cmd(fname):
                @command(dtype_in=object, dtype_out=object)
                def cmd(self, arg):
                    return getattr(self._cobotta_ctrl, fname)(arg)

                return cmd

            methods[name] = make_cmd(name)

    # -- propertyをアトリビュート自動生成 --
    for name, prop in inspect.getmembers(
        type(ctrl), predicate=lambda x: isinstance(x, property)
    ):
        rw = AttrWriteType.READ_WRITE if prop.fset else AttrWriteType.READ

        def make_attr(aname, rw):
            @attribute(dtype=object, access=rw)
            def attr(self):
                return getattr(self._cobotta_ctrl, aname)

            if rw == AttrWriteType.READ_WRITE:

                @attr.write
                def attr(self, value):
                    setattr(self._cobotta_ctrl, aname, value)

            return attr

        methods[name] = make_attr(name, rw)
    # -- 必要な内部stateなども登録
    methods["_cobotta_ctrl"] = None
    methods["_logger"] = None

    # -- 動的にクラス生成
    return type("DynamicCobottaDS", (Device,), methods)


DynamicCobottaDS = build_dynamic_cobotta_ds()


# -- DeviceServer本体: __init__, logger, config等
class DsCobotta(DynamicCobottaDS):
    def __init__(self, cl, name):
        super().__init__(cl, name)
        self._logger = None
        self._cobotta_ctrl = None

    def init_device(self):
        Device.init_device(self)
        # ロガー構築
        if self._logger is None:
            # ログファイル名等は現状のまま自動
            if os.name == "nt":
                log_name = "c:/tango_log/cobotta_log"
            else:
                log_name = "/opt/tango_log/cobotta_log"
            self._logger = XLogger(
                log_level="debug", log_name=log_name, logger_name="COBOTTA_DS"
            )
        # CobottaCtrl インスタンス
        try:
            self._logger.info("== Create CobottaCtrl instance")
            self._cobotta_ctrl = CobottaCtrl(
                cobotta_ip=Config.COBOTTA1_IP, logger=self._logger
            )
            self.set_state(tango.DevState.ON)
        except Exception as e:
            self._logger.error(f"Exception in CobottaCtrl: {e}")
            self._logger.error(traceback.format_exc())
            self.set_state(tango.DevState.FAULT)
            raise

    def delete_device(self):
        if self._cobotta_ctrl:
            self._cobotta_ctrl.disconnect()
        self._logger.info("Device deleted")
        return True


if __name__ == "__main__":
    # Device名等は現状流用
    instance_name = sys.argv[1] if len(sys.argv) > 1 else "1"
    dev_info = tango.DbDevInfo()
    dev_info.server = f"DsCobotta/{instance_name}"
    dev_info._class = "DsCobotta"
    dev_info.name = f"elves/cobotta/{instance_name}"

    db = tango.Database()
    db.add_device(dev_info)

    # logger configは上と同じ
    DsCobotta.run_server()
