#!/usr/bin/env python3
"""
Device Server for Cobotta

Kengo NAKADA:
https://github.com/shimane-dev, https://github.com/kengo-nakada
kengo.nakada@mat.shimane-u.ac.jp, kengo.nakada@gmail.com
"""
# import asyncio
# import multiprocessing
import sys
import os
import json
import random
import logging
import time
import copy
import traceback

from enum import IntEnum

# noinspection PyUnresolvedReferences
import tango
from tango.server import Device, attribute, command, pipe, device_property
from tango.server import PipeWriteType
from tango.server import AttrWriteType

from cobotta2.config import Config
from cobotta2.cobotta_ctrl import CobottaCtrl

from x_logger.x_logger import XLogger
from x_logger.util import *


class DsCobotta(Device):
    # green_mode = tango.GreenMode.Asyncio
    # host = device_property(str, default_value='144.213.136.137')

    _logger = None
    log_level = "info"
    log_mode = "default"
    log_name = "log/cobotta_log"
    logger_name = "CO"

    def __init__(self, tango_class_obj, name):
        Device.__init__(self, tango_class_obj, name)
        self._version = None
        self._cobotta = None
        self._cobotta_ctrl = None

    def delete_device(self):
        self.stop_logging()
        return True

    def init_device(self):
        # super().init_device()
        Device.init_device(self)
        self.set_state(tango.DevState.ON)
        self.init_logger()
        self.start_logging()

        # self._logger = logging.getLogger(__name__)
        self._logger = XLogger(
            log_level=self.log_level,
            log_mode=self.log_mode,
            log_name=self.log_name,
            logger_name=self.logger_name,
        )

        self._logger.info(f"== DsCobottaCtrl()")
        self._logger.info(f"  Python version  = {sys.version}")
        self._logger.info(f"  pyTANGO version = {tango.__version__}")
        self._logger.info(f"  DS version      = %s" % __version__)

        try:
            self._logger.info("== create CobottaCtrl instance ")
            self._logger.info("  cobotta_ip = %s" % Config.COBOTTA1_IP)
            self._version = __version__
            self._cobotta_ctrl = CobottaCtrl(
                cobotta_ip=Config.COBOTTA1_IP, logger=_logger
            )

        except Exception as e:
            self._logger.error("**Error**: Exception, CobottaCtrl instance: %s" % e)
            # traceback.print_exc()
            error_message = traceback.format_exc()
            self._logger.error(error_message)
            sys.exit(-1)

        self.debug_stream("init: debug stream")
        self.info_stream("init: info stream")
        self.warn_stream("init: warn stream")
        self.error_stream("init: error stream")
        self.fatal_stream("init: fatal stream")

        self.start_logging()
        self.set_state(tango.DevState.STANDBY)
        self._logger.info(f"END of init_device(): {self.get_state()}")
        self._logger.info("")

    #
    #
    #

    @command()
    async def delete(self):
        self._cobotta_ctrl.delete()

    @command()
    async def disconnect(self):
        self._cobotta_ctrl.disconnect()

    #
    # state
    #

    # @attribute(dtype=str)
    # def version(self) -> str:
    #     return self._version

    # @command(dtype_in=str)
    # def set_sample_id(self, sample_id: str):
    #     """meta情報(doc) に sample_id を追加する"""
    #     current_val = copy.deepcopy(self._emstat.data["doc"])
    #     current_val.update({"sample_id": f"{sample_id}"})
    #     self._emstat.data["doc"] = current_val
    # print(json.dumps(self._emstat.data['doc'], indent=4))

    # @command(dtype_out=str)
    # def get_sample_id(self):
    #     """meta情報(doc) の sample_id を返す。sample_id キーがないときは None を返す"""
    #     return self._emstat.data["doc"].get("sample_id", "None")

    # sample_id = attribute(dtype=str)

    # @sample_id.read
    # def sample_id(self):
    #     return self.get_sample_id()

    # @sample_id.write
    # def sample_id(self, val: str):
    #     self.set_sample_id(val)

    # data_EIS = pipe(label="EIS_script")

    # @pipe(label='EIS_script')
    # def data_EIS(self):
    # def read_pipe_data_EIS(self):
    #     return "script", self._emstat.data["EIS"]

    # @attribute(dtype=str, access=AttrWriteType.READ)
    # def device_type(self):
    #     return self._emstat.device_type

    # @command
    # def reset(self):
    #     return self._emstat.reset()

    # @command(dtype_out=bool)
    # def start(self):
    #     return self.start_script()

    # @command(dtype_in=(str, str, str, str, str, str), dtype_out=bool)
    # def set_meas_loop_eis(self, v):
    #     """LOW LEVEL API を直接実行"""
    #     msg = "== set_meas_loop_eis()"
    #     self._logger.info(msg)
    #     self.info_stream(msg)

    #     return True

    # @command(dtype_out=str)
    # def try1(self):
    #     print("AAAAA")
    #     return "AAAAA"


if __name__ == "__main__":
    instance_name = sys.argv[1]
    cell_no = instance_name

    dev_info = tango.DbDevInfo()
    dev_info.server = "DsCobotta/%s" % instance_name
    dev_info._class = "DsCobotta"
    dev_info.name = "elves/pstat/%s" % cell_no

    print("add device")
    db = tango.Database()
    db.add_device(dev_info)

    # log_level = 'info'
    log_level = "DEBUG"
    log_mode = "default"
    # log_mode = "rotating"

    # log_name = 'log/cobotta_log'
    if os.name == "nt":
        log_name = f"c:/tango_log/emstat4m{cell_no}_log"
    elif os.name == "posix":
        # log_name = f'/opt/elves/log/emstat4m{cell_no}_log'
        log_name = f"/opt/tango_log/cobotta_log"
    else:
        print("Unsupported operating system")
        sys.exit(-1)

    logger_name = f"PS{cell_no}"
    logger = XLogger(
        log_level=log_level,
        log_mode=log_mode,
        log_name=log_name,
        logger_name=logger_name,
    )

    logger.info("-------------------")
    logger.info("Instance Name    = %s" % instance_name)
    logger.info("Server Name      = %s" % dev_info.server)
    logger.info("DeviceClass Name = %s" % dev_info._class)
    logger.info("Device Name      = %s" % dev_info.name)
    logger.info("-------------------")

    # CELL番号に対応させる
    if cell_no == str(1):
        device_port = "/dev/ttyACM0"
    elif cell_no == str(2):
        device_port = "/dev/ttyACM2"
    else:
        logger.error(f"**Error**: Unsupported cell_no ({cell_no})")
        sys.exit(-1)

    logger.info(f"Device Port      = {device_port}")
    logger.info(f"Cell No          = {cell_no}")
    logger.info("-------------------")

    DsCobotta._logger = logger
    DsCobotta.log_level = log_level
    DsCobotta.log_mode = log_mode
    DsCobotta.log_name = log_name
    DsCobotta.logger_name = logger_name
    DsCobotta.device_port = device_port
    DsCobotta.cell_no = cell_no
    DsCobotta.run_server()
