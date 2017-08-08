# This file is part of the ISIS IBEX application.
# Copyright (C) 2012-2016 Science & Technology Facilities Council.
# All rights reserved.
#
# This program is distributed in the hope that it will be useful.
# This program and the accompanying materials are made available under the
# terms of the Eclipse Public License v1.0 which accompanies this distribution.
# EXCEPT AS EXPRESSLY SET FORTH IN THE ECLIPSE PUBLIC LICENSE V1.0, THE PROGRAM
# AND ACCOMPANYING MATERIALS ARE PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES
# OR CONDITIONS OF ANY KIND.  See the Eclipse Public License v1.0 for more details.
#
# You should have received a copy of the Eclipse Public License v1.0
# along with this program; if not, you can obtain a copy from
# https://www.eclipse.org/org/documents/epl-v10.php or
# http://opensource.org/licenses/eclipse-1.0.php

# Add root path for access to server_commons
import os
import sys

sys.path.insert(0, os.path.abspath(os.environ["MYDIRBLOCK"]))

# Standard imports
from pcaspy import Driver
from time import sleep
import argparse
from server_common.utilities import compress_and_hex, print_and_log, set_logger, convert_to_json, dehex_and_decompress
from server_common.channel_access_server import CAServer
from server_common.constants import IOCS_NOT_TO_STOP
from server_common.ioc_data import IOCData
from exp_data import ExpData
import json
from threading import Thread, RLock
from procserv_utils import ProcServWrapper
from options_holder import OptionsHolder
from options_loader import OptionsLoader
from mocks.mock_procserv_utils import MockProcServWrapper

MACROS = {
    "$(MYPVPREFIX)": os.environ['MYPVPREFIX'],
    "$(EPICS_KIT_ROOT)": os.environ['EPICS_KIT_ROOT'],
    "$(ICPCONFIGROOT)": os.environ['ICPCONFIGROOT']
}

LOG_TARGET = "DBSVR"
INFO_MSG = "INFO"
MAJOR_MSG = "MAJOR"


class DatabaseServer(Driver):
    """The class for handling all the static PV access and monitors etc.
    """
    def __init__(self, ca_server, dbid, options_folder, blockserver_prefix, test_mode=False):
        """Constructor.

        Args:
            ca_server (CAServer): The CA server used for generating PVs on the fly
            dbid (string): The id of the database that holds IOC information.
            options_folder (string): The location of the folder containing the config.xml file that holds IOC options
        """
        self._blockserver_prefix = blockserver_prefix
        if test_mode:

            ps = MockProcServWrapper()
        else:
            super(DatabaseServer, self).__init__()
            ps = ProcServWrapper()
        self._ca_server = ca_server
        self._options_holder = OptionsHolder(options_folder, OptionsLoader())

        self._pv_info = self._generate_pv_acquisition_info()

        # Initialise database connection
        try:
            self._db = IOCData(dbid, ps, MACROS["$(MYPVPREFIX)"])
            print_and_log("Connected to database", INFO_MSG, LOG_TARGET)
        except Exception as e:
            self._db = None
            print_and_log("Problem initialising DB connection: %s" % e, MAJOR_MSG, LOG_TARGET)

        # Initialise experimental database connection
        try:
            self._ed = ExpData(MACROS["$(MYPVPREFIX)"])
            print_and_log("Connected to experimental details database", INFO_MSG, LOG_TARGET)
        except Exception as e:
            self._ed = None
            print_and_log("Problem connecting to experimental details database: %s" % e, MAJOR_MSG, LOG_TARGET)

        if self._db is not None and not test_mode:
            # Start a background thread for keeping track of running IOCs
            self.monitor_lock = RLock()
            monitor_thread = Thread(target=self._update_ioc_monitors, args=())
            monitor_thread.daemon = True  # Daemonise thread
            monitor_thread.start()

    def _generate_pv_acquisition_info(self):
        """
        Generates information needed to get the data for the DB PVs.

        Returns:
            Dictionary : Dictionary containing the information to get the information for the PVs
        """
        enhanced_info = DatabaseServer.generate_pv_info()

        def add_get_method(pv, get_function):
            enhanced_info[pv]['get'] = get_function

        add_get_method('IOCS', self._get_iocs_info)
        add_get_method('PVS:INTEREST:HIGH', self._get_high_interest_pvs)
        add_get_method('PVS:INTEREST:MEDIUM', self._get_medium_interest_pvs)
        add_get_method('PVS:INTEREST:FACILITY', self._get_facility_pvs)
        add_get_method('PVS:ACTIVE', self._get_active_pvs)
        add_get_method('PVS:ALL', self._get_all_pvs)
        add_get_method('SAMPLE_PARS', self._get_sample_par_names)
        add_get_method('BEAMLINE_PARS', self._get_beamline_par_names)
        add_get_method('USER_PARS', self._get_user_par_names)
        add_get_method('IOCS_NOT_TO_STOP', DatabaseServer._get_iocs_not_to_stop)

        return enhanced_info

    @staticmethod
    def generate_pv_info():
        """
        Generates information needed to construct PVs. Must be consumed by Server before
        DatabaseServer is initialized so must be static

        Returns:
            Dictionary : Dictionary containing the information to construct PVs
        """
        pv_size_64k = 64000
        pv_size_10k = 10000

        # Helper to consistently create pvs
        def create_pvdb_entry(count):
            return {'type': 'char', 'count': count, 'value': [0]}

        return {
            'IOCS': create_pvdb_entry(pv_size_64k),
            'PVS:INTEREST:HIGH': create_pvdb_entry(pv_size_64k),
            'PVS:INTEREST:MEDIUM': create_pvdb_entry(pv_size_64k),
            'PVS:INTEREST:FACILITY': create_pvdb_entry(pv_size_64k),
            'PVS:ACTIVE': create_pvdb_entry(pv_size_64k),
            'PVS:ALL': create_pvdb_entry(pv_size_64k),
            'SAMPLE_PARS': create_pvdb_entry(pv_size_10k),
            'BEAMLINE_PARS': create_pvdb_entry(pv_size_10k),
            'USER_PARS': create_pvdb_entry(pv_size_10k),
            'IOCS_NOT_TO_STOP': create_pvdb_entry(pv_size_64k),
        }

    def read(self, reason):
        """A method called by SimpleServer when a PV is read from the DatabaseServer over Channel Access.

        Args:
            reason (string): The PV that is being requested (without the PV prefix)

        Returns:
            string : A compressed and hexed JSON formatted string that gives the desired information based on reason.
        """
        if reason in self._pv_info.keys():
            encoded_data = DatabaseServer._encode_for_return(self._pv_info[reason]['get']())
            self._check_pv_capacity(reason, len(encoded_data), self._blockserver_prefix)
        else:
            encoded_data = self.getParam(reason)
        return encoded_data

    def write(self, reason, value):
        """A method called by SimpleServer when a PV is written to the DatabaseServer over Channel Access.

        Args:
            reason (string): The PV that is being requested (without the PV prefix)
            value (string): The data being written to the 'reason' PV

        Returns:
            bool : True
        """
        status = True
        try:
            if reason == 'ED:RBNUMBER:SP':
                # print_and_log("Updating to use experiment ID: " + value, INFO_MSG, LOG_LOCATION)
                self._ed.updateExperimentID(value)
            elif reason == 'ED:USERNAME:SP':
                self._ed.updateUsername(dehex_and_decompress(value))
        except Exception as e:
            value = compress_and_hex(convert_to_json("Error: " + str(e)))
            print_and_log(str(e), MAJOR_MSG)
        # store the values
        if status:
            self.setParam(reason, value)
        return status

    def _update_ioc_monitors(self):
        """Updates all the PVs that hold information on the IOCS and their associated PVs
        """
        while True:
            if self._db is not None:
                self._db.update_iocs_status()
                for pv in ["IOCS", "PVS:ALL", "PVS:ACTIVE", "PVS:INTEREST:HIGH", "PVS:INTEREST:MEDIUM",
                           "PVS:INTEREST:FACILITY"]:
                    encoded_data = DatabaseServer._encode_for_return(self._pv_info[pv]['get']())
                    self._check_pv_capacity(pv, len(encoded_data), self._blockserver_prefix)
                    self.setParam(pv, encoded_data)
                # Update them
                with self.monitor_lock:
                    self.updatePVs()
            sleep(1)

    def _check_pv_capacity(self, pv, size, prefix):
        """
        Check the capacity of a PV and write to the log if it is too small
        
        Args:
            pv (string): The PV that is being requested (without the PV prefix)
            size (int): The required size
            prefix (string): The PV prefix
        """
        if size > self._pv_info[pv]['count']:
            print_and_log("Too much data to encode PV {0}. Current size is {1} characters but {2} are required"
                          .format(prefix + pv, self._pv_info[pv]['count'], size),
                          MAJOR_MSG, LOG_TARGET)

    @staticmethod
    def _encode_for_return(data):
        """Converts data to JSON, compresses it and converts it to hex.

        Args:
            data (string): The data to encode

        Returns:
            string : The encoded data
        """
        return compress_and_hex(json.dumps(data).encode('ascii', 'replace'))

    def _get_iocs_info(self):
        iocs = self._db.get_iocs()
        options = self._options_holder.get_config_options()
        for iocname in iocs.keys():
            if iocname in options:
                iocs[iocname].update(options[iocname])
        return iocs

    def _get_pvs(self, get_method, replace_pv_prefix, *get_args):
        if self._db is not None:
            pv_data = get_method(*get_args)
            if replace_pv_prefix:
                pv_data = [p.replace(MACROS["$(MYPVPREFIX)"], "") for p in pv_data]
            return pv_data
        else:
            return list()

    def _get_high_interest_pvs(self):
        return self._get_interesting_pvs("HIGH")

    def _get_medium_interest_pvs(self):
        return self._get_interesting_pvs("MEDIUM")

    def _get_facility_pvs(self):
        return self._get_interesting_pvs("FACILITY")

    def _get_all_pvs(self):
        return self._get_interesting_pvs("")

    def _get_interesting_pvs(self, level):
        return self._get_pvs(self._db.get_interesting_pvs, False, level)

    def _get_active_pvs(self):
        return self._get_pvs(self._db.get_active_pvs, False)

    def _get_sample_par_names(self):
        """Returns the sample parameters from the database, replacing the MYPVPREFIX macro

        Returns:
            list : A list of sample parameter names, an empty list if the database does not exist
        """
        return self._get_pvs(self._db.get_sample_pars, True)

    def _get_beamline_par_names(self):
        """Returns the beamline parameters from the database, replacing the MYPVPREFIX macro

        Returns:
            list : A list of beamline parameter names, an empty list if the database does not exist
        """
        return self._get_pvs(self._db.get_beamline_pars, True)

    def _get_user_par_names(self):
        """Returns the user parameters from the database, replacing the MYPVPREFIX macro

        Returns:
            list : A list of user parameter names, an empty list if the database does not exist
        """
        return self._get_pvs(self._db.get_user_pars, True)

    @staticmethod
    def _get_iocs_not_to_stop():
        """
        Returns: 
            list: A list of IOCs not to stop
        """
        return IOCS_NOT_TO_STOP

if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('-bs', '--blockserver_prefix', nargs=1, type=str,
                        default=[MACROS["$(MYPVPREFIX)"]+'CS:BLOCKSERVER:'],
                        help='The prefix for PVs served by the blockserver(default=%MYPVPREFIX%CS:BLOCKSERVER:)')

    parser.add_argument('-od', '--options_dir', nargs=1, type=str, default=['.'],
                        help='The directory from which to load the configuration options(default=current directory)')

    parser.add_argument('-f', '--facility', nargs=1, type=str, default=['ISIS'],
                        help='Which facility is this being run for (default=ISIS)')

    args = parser.parse_args()

    FACILITY = args.facility[0]
    if FACILITY == "ISIS":
        from server_common.loggers.isis_logger import IsisLogger
        set_logger(IsisLogger())
    print_and_log("FACILITY = %s" % FACILITY, INFO_MSG, LOG_TARGET)

    BLOCKSERVER_PREFIX = args.blockserver_prefix[0]
    if not BLOCKSERVER_PREFIX.endswith(':'):
        BLOCKSERVER_PREFIX += ":"
    BLOCKSERVER_PREFIX = BLOCKSERVER_PREFIX.replace('%MYPVPREFIX%', MACROS["$(MYPVPREFIX)"])
    print_and_log("BLOCKSERVER PREFIX = %s" % BLOCKSERVER_PREFIX, INFO_MSG, LOG_TARGET)

    OPTIONS_DIR = os.path.abspath(args.options_dir[0])
    print_and_log("OPTIONS DIRECTORY = %s" % OPTIONS_DIR, INFO_MSG, LOG_TARGET)
    if not os.path.isdir(os.path.abspath(OPTIONS_DIR)):
        # Create it then
        os.makedirs(os.path.abspath(OPTIONS_DIR))

    SERVER = CAServer(BLOCKSERVER_PREFIX)
    SERVER.createPV(BLOCKSERVER_PREFIX, DatabaseServer.generate_pv_info())
    SERVER.createPV(MACROS["$(MYPVPREFIX)"], ExpData.EDPV)
    DRIVER = DatabaseServer(SERVER, "iocdb", OPTIONS_DIR, BLOCKSERVER_PREFIX)

    # Process CA transactions
    while True:
        try:
            SERVER.process(0.1)
        except Exception as err:
            print_and_log(err, MAJOR_MSG)
            break
