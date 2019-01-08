"""
Driver for the reflectometry server.
"""
from functools import partial

from pcaspy import Driver, Alarm, Severity

from ReflectometryServer.ChannelAccess.pv_manager import PvSort, BEAMLINE_MODE, VAL_FIELD, BEAMLINE_STATUS, SP_SUFFIX
from ReflectometryServer.parameters import BeamlineParameterType
from server_common.utilities import compress_and_hex


class ReflectometryDriver(Driver):
    """
    The driver which provides an interface for the reflectometry server to channel access by creating PVs and processing
    incoming CA get and put requests.
    """
    def __init__(self, server, beamline, pv_manager):
        """
        The Constructor.
        Args:
            server: The PCASpy server.
            beamline(ReflectometryServer.beamline.Beamline): The beamline configuration.
            pv_manager(ReflectometryServer.ChannelAccess.pv_manager.PVManager): The manager mapping PVs to objects in
                the beamline.
        """
        super(ReflectometryDriver, self).__init__()

        self._beamline = beamline
        self._ca_server = server
        self._pv_manager = pv_manager

        for reason in self._pv_manager.PVDB.keys():
            self.setParamStatus(reason, severity=Severity.NO_ALARM, alarm=Alarm.NO_ALARM)

        self.update_monitors()

        self.add_rbv_param_listeners()
        self.add_trigger_active_mode_change_listener()

    def read(self, reason):
        """
        Processes an incoming caget request.
        :param reason: The PV that is being read.
        :return: The value associated to this PV
        """
        if self._pv_manager.is_param(reason):
            param_name, param_sort = self._pv_manager.get_param_name_and_sort_from_pv(reason)
            param = self._beamline.parameter(param_name)
            value = param_sort.get_from_parameter(param)
            if param.parameter_type == BeamlineParameterType.IN_OUT:
                return 1 if value else 0
            else:
                return value

        elif self._pv_manager.is_beamline_mode(reason):
            return self._beamline_mode_value(self._beamline.active_mode)

        elif self._pv_manager.is_beamline_move(reason):
            return self._beamline.move

        elif self._pv_manager.is_tracking_axis(reason):
            return compress_and_hex(self.getParam(reason))

        elif self._pv_manager.is_beamline_status(reason):
            beamline_status_enums = self._pv_manager.PVDB[BEAMLINE_STATUS]["enums"]
            new_value = beamline_status_enums.index(self._beamline.status.name)
            #  Set the value so that the error condition is set
            self.setParam(reason, new_value)
            return new_value

        elif self._pv_manager.is_beamline_message(reason):
            return self._beamline.message

        else:
            return self.getParam(reason)

    def _beamline_mode_value(self, mode):
        beamline_mode_enums = self._pv_manager.PVDB[BEAMLINE_MODE]["enums"]
        return beamline_mode_enums.index(mode)

    def write(self, reason, value):
        """
        Process an incoming caput request.
        :param reason: The PV that is being written to.
        :param value: The value being written to the PV
        """
        status = True
        if self._pv_manager.is_param(reason):
            param_name, param_sort = self._pv_manager.get_param_name_and_sort_from_pv(reason)
            param = self._beamline.parameter(param_name)
            if param_sort == PvSort.MOVE:
                param.move = 1
            elif param_sort == PvSort.SP:
                param.sp = value
            elif param_sort == PvSort.SET_AND_NO_MOVE:
                param.sp_no_move = value
        elif self._pv_manager.is_beamline_move(reason):
            self._beamline.move = 1
        elif self._pv_manager.is_beamline_mode(reason):
            try:
                beamline_mode_enums = self._pv_manager.PVDB[BEAMLINE_MODE]["enums"]
                self._beamline.active_mode = beamline_mode_enums[value]
                self._update_param(reason, value)
            except ValueError:
                print("Invalid value entered for mode. (Possible modes: {})".format(
                    ",".join(self._beamline.mode_names)))
                status = False
        else:
            print("Error: PV is read only")
            status = False

        if status:
            self.update_monitors()
        return status

    def update_monitors(self):
        """
        Updates the PV values for each parameter so that changes are visible to monitors.
        """
        # with self.monitor_lock:
        for pv_name, (param_name, param_sort) in self._pv_manager.param_names_pvnames_and_sort():
            parameter = self._beamline.parameter(param_name)
            self._update_param(pv_name, param_sort.get_from_parameter(parameter))
        self.updatePVs()

    def _update_param(self, pv_name, value):
        """
        Update a parameter value (both it and .VAL)
        Args:
            pv_name: name of the pv
            value: value of the parameter
        """
        self.setParam(pv_name, value)
        self.setParam(pv_name + VAL_FIELD, value)

    def _update_param_rbv_listener(self, pv_name, value):
        """
        Listener for responding to rbv updates from the command line parameter
        Args:
            pv_name: name of the pv
            value: new value
        """
        self._update_param(pv_name, value)
        self.updatePVs()

    def add_rbv_param_listeners(self):
        """
        Add listeners to beam line parameter readback changes, which update parameters in server
        """
        for pv_name, (param_name, param_sort) in self._pv_manager.param_names_pvnames_and_sort():
            parameter = self._beamline.parameter(param_name)
            if param_sort == PvSort.RBV:
                parameter.add_rbv_change_listener(partial(self._update_param_rbv_listener, pv_name))

    def add_trigger_active_mode_change_listener(self):
        """
        Adds the monitor on the active mode, if this changes a monitor is posted.
        """
        def _bl_mode_change(mode):
            mode_value = self._beamline_mode_value(mode)
            self._update_param(BEAMLINE_MODE, mode_value)
            self._update_param(BEAMLINE_MODE + SP_SUFFIX, mode_value)
            self.updatePVs()
        self._beamline.add_active_mode_change_listener(_bl_mode_change)
