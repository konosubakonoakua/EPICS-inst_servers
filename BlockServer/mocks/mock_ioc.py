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


class MockIoc(object):
    def __init__(self, name="NEWIOC", autostart=True, restart=True, macros=None, pvs=None, pvsets=None, component=None,
                 simlevel='none'):
        self.name = name
        self.autostart = autostart
        self.restart = restart
        if macros is None:
            macros = []
        self.macros = macros
        if pvs is None:
            pvs = []
        self.pvs = pvs
        if pvsets is None:
            pvsets = []
        self.pvsets = pvsets
        self.component = component
        self.simlevel = simlevel

    def get(self, name):
        return self.__getattribute__(name)

    def __getitem__(self, name):
        return self.__getattribute__(name)
