from __future__ import print_function, unicode_literals, division, absolute_import

import json
import sys
import os

from genie_python.genie_cachannel_wrapper import CaChannelWrapper

REMOTE_IOC_CONFIG_NAME = "_REMOTE_IOC_CONFIG"

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))
from server_common.channel_access import ChannelAccess
from server_common.utilities import print_and_log, dehex_and_decompress, waveform_to_string
from BlockServer.config.xml_converter import ConfigurationXmlConverter
from BlockServer.config.ioc import IOC


class _ConfigurationMonitor(object):
    """
    Wrapper around an EPICS configuration monitor.
    """
    def __init__(self, pv):
        self._pv = pv

    def start(self, callback):
        ChannelAccess.add_monitor(self._pv, callback)

    def end(self):
        CaChannelWrapper.get_chan(self._pv).clear_channel()


class ConfigurationMonitor(object):
    """
    Monitors the configuration PV from whichever instrument is controlling this remote IOC.

    Calls back to the RemoteIocServer class on change of config.
    """
    def __init__(self, initial_remote_pv_prefix, restart_iocs_callback):
        self._monitor = None
        self.set_remote_pv_prefix(initial_remote_pv_prefix)
        self.restart_iocs_callback_func = restart_iocs_callback

    def set_remote_pv_prefix(self, remote_pv_prefix):
        self._remote_pv_prefix = remote_pv_prefix
        self._start_monitoring()

    def _start_monitoring(self):
        """
        Monitors the PV and calls the provided callback function when the value changes
        """
        if self._monitor is not None:
            self._monitor.end()
        self._monitor = _ConfigurationMonitor("{}CS:BLOCKSERVER:GET_CURR_CONFIG_DETAILS".format(self._remote_pv_prefix))
        self._monitor.start(callback=self._config_updated)

    def _config_updated(self, value, alarm_severity_ignored, alarm_status_ignored):
        try:
            new_config = dehex_and_decompress(waveform_to_string(value))
            write_new_config_as_xml(new_config)
            self.restart_iocs_callback_func()
        except (TypeError, ValueError, IOError) as e:
            print_and_log("Config JSON from instrument not decoded correctly: {}: {}".format(e.__class__.__name__, e))
            print_and_log("Raw PV value was: {}".format(value))


def write_new_config_as_xml(config_json):
    print_and_log("Got new config monitor.")
    config = json.loads(config_json, "ascii")

    iocs_list = []

    if "component_iocs" in config and config["component_iocs"] is not None:
        for ioc in config["component_iocs"]:
            iocs_list.append(ioc)

    if "iocs" in config and config["iocs"] is not None:
        for ioc in config["iocs"]:
            iocs_list.append(ioc)

    iocs = {}
    for ioc in iocs_list:
        name = ioc["name"]
        iocs[name.upper()] = IOC(
            name=name,
            autostart=ioc["autostart"],
            restart=ioc["restart"],
            component=None,  # We don't care what component it was defined in.
            macros={macro["name"]: {macro["name"]: macro["value"]} for macro in ioc["macros"]},  # This format is what the blockserver wants - despite it being weird
            pvsets={pvset["name"]: {"name": pvset["name"], "value": pvset["value"]} for pvset in ioc["pvsets"]},
            pvs={pv["name"]: {"name": pv["name"], "value": pv["value"]} for pv in ioc["pvs"]},
            simlevel=ioc["simlevel"]
        )

    iocs_xml = ConfigurationXmlConverter.iocs_to_xml(iocs)

    print_and_log("Writing new iocs.xml file")

    config_base = os.path.normpath(os.getenv("ICPCONFIGROOT"))
    config_dir = os.path.join(config_base, "configurations", REMOTE_IOC_CONFIG_NAME)
    if not os.path.exists(config_dir):
        os.mkdir(config_dir)

    with open(os.path.join(config_dir, "iocs.xml"), "w") as f:
        f.write(str(iocs_xml))

    with open(os.path.join(config_base, "last_config.txt"), "w") as f:
        f.write(REMOTE_IOC_CONFIG_NAME)

    print_and_log("Finished writing new iocs.xml file")
