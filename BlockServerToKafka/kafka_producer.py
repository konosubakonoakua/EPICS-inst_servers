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
from forwarder_config import ForwarderConfig
from kafka import KafkaProducer
from server_common.utilities import print_and_log


class Producer():
    """ Wrapper class for the kafka producer
    """
    def __init__(self, server, config_topic, data_topic):
        self.topic = config_topic
        self.producer = KafkaProducer(bootstrap_servers=server)
        self.converter = ForwarderConfig(data_topic)

    def add_config(self, pvs):
        """
        Args:
             pvs (string) The Json string with BS configuration to add to topic
        """
        data = self.converter.create_forwarder_configuration(pvs)
        print_and_log("Sending data {}".format(data))
        self.producer.send(self.topic, bytes(data))

    def remove_config(self, pvs):
        """
        Args:
            pvs (string) The json string with old BS configuration to remove from topic
        """
        data = self.converter.remove_forwarder_configuration(pvs)
        for pv in data:
            print_and_log("Sending data {}".format(data))
            self.producer.send(self.topic, bytes(pv))
