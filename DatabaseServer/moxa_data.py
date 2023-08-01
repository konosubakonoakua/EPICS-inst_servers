import os
from collections import OrderedDict
from typing import Dict, Tuple, List
import socket

from server_common.utilities import print_and_log, SEVERITY

REG_KEY_NPDRV = r"SYSTEM\\CurrentControlSet\\Services\\npdrv\\Parameters"
REG_DIR_NPDRV2 = r"SYSTEM\\CurrentControlSet\\Enum\\ROOT\\PORTS"
GET_MOXA_IPS = """
SELECT moxa_name, moxa_ip
FROM moxa_details.moxa_ips;
"""

GET_MOXA_MAPPINGS_FOR_MOXA_NAME = """
SELECT moxa_port, com_port
FROM moxa_details.port_mappings
WHERE moxa_name = %s;
"""

INSERT_TO_IPS = """
INSERT INTO moxa_details.moxa_ips (moxa_name, moxa_ip) VALUES (%s, %s);
"""

INSERT_TO_PORTS = """
INSERT INTO moxa_details.port_mappings (moxa_name, moxa_port, com_port) VALUES (%s, %s, %s);"""

DELETE_IPS = """
DELETE FROM moxa_details.moxa_ips;"""

DELETE_PORTS = """
DELETE FROM moxa_details.port_mappings;"""

class MoxaDataSource(object):
    """
    A source for IOC data from the database
    """
    def __init__(self, mysql_abstraction_layer):
        """
        Constructor.

        Args:
            mysql_abstraction_layer(genie_python.mysql_abstraction_layer.AbstractSQLCommands): contact database with sql
        """
        self.mysql_abstraction_layer = mysql_abstraction_layer

    def _query_and_normalise(self, sqlquery, bind_vars=None):
        """
        Executes the given query to the database and converts the data in each row from bytearray to a normal string.

        Args:
            sqlquery: The query to execute.
            bind_vars: Any variables to bind to query. Defaults to None.

        Returns:
            A list of lists of strings, representing the data from the table.
        """
        # Get as a plain list of lists
        values = [list(element) for element in self.mysql_abstraction_layer.query(sqlquery, bind_vars)]

        # Convert any bytearrays
        for i, pv in enumerate(values):
            for j, element in enumerate(pv):
                if type(element) == bytearray:
                    values[i][j] = element.decode("utf-8")
        return values
    
    def _delete_all(self):
        self.mysql_abstraction_layer.update(DELETE_PORTS)
        self.mysql_abstraction_layer.update(DELETE_IPS)

    """
    Iterates through the map of ip to hostname and physical port to COM ports and inserts the mappings into the sql instance. 

    Args:
        moxa_ip_name_dict: The map of IP addresses to hostnames of Moxa Nports
        moxa_ports_dict: The map of IP addresses to physical and COM port mappings
    """
    def insert_mappings(self, moxa_ip_name_dict, moxa_ports_dict):
        print_and_log("inserting moxa mappings to SQL")
        self._delete_all()
        for moxa_name, moxa_ip in moxa_ip_name_dict.items():
            print_and_log(f"moxa name: {moxa_name} - IP: {moxa_ip}")
            self.mysql_abstraction_layer.update(INSERT_TO_IPS, (moxa_name, moxa_ip))

        for moxa_name, ports in moxa_ports_dict.items():           
            for phys_port, com_port in ports:
            # phys_port = ports[0]
            # com_port = ports[1]
                print_and_log(f"moxa name: {moxa_name}, phys port: {phys_port}, com_port: {com_port}")
                self.mysql_abstraction_layer.update(INSERT_TO_PORTS, (moxa_name, str(phys_port), str(com_port)))

class MoxaData():

    MDPV = {
        "UPDATE_MM": {'type': 'int'}
    }

    def __init__(self, data_source, prefix):
        """Constructor

        Args:
            data_source (IocDataSource): The wrapper for the database that holds IOC information
            procserver (ProcServWrapper): An instance of ProcServWrapper, used to start and stop IOCs
            prefix (string): The pv prefix of the instrument the server is being run on
        """
        self._moxa_data_source = data_source
        self._prefix = prefix
        self.moxa_map = OrderedDict()
        # insert mappings initially
        self.update_mappings()

    """
    Gets the mappings and inserts them into SQL
    """
    def update_mappings(self):
        print_and_log("updating moxa mappings")
        self._mappings = self._get_mappings()
        self._moxa_data_source.insert_mappings(*self._get_mappings())

    """
    Returns the IP to hostname and IP to port mappings as a string representation for use with the MOXA_MAPPINGS PV
    """
    def _get_mappings_str(self):
        #it is much easier to parse the mappings if they just look like a key:{key, val} list, so lets do that now rather than in the GUI
        newmap = dict()
        for hostname, mappings in self._mappings[1].items():
            ip_addr = self._mappings[0][hostname]
            newkey = f"{hostname}({ip_addr})"
            newmap[newkey] = []
            for map in mappings:
                newmap[newkey].append([str(map[0]), f"COM{map[1]}"])
        return newmap
    
    def _get_moxa_num(self):
        return str(len(self._mappings[0].keys()))
    
    def _get_hostname(self, ip_addr):
        try:
            return socket.gethostbyaddr(ip_addr)[0]
        except socket.herror:
            return "unknown"
        


    def _get_mappings(self) -> Tuple[Dict[str, str], Dict[int, List[Tuple[int, int]]]]:
        # moxa_name_ip_dict: HOSTNAME:IPADDR
        # moxa_ports_dict: HOSTNAME:[(PHYSPORT:COMPORT),...]
        moxa_name_ip_dict = dict()
        moxa_ports_dict = dict()
        if os.name == "nt":
            import winreg as wrg

            location = wrg.HKEY_LOCAL_MACHINE

            using_npdrv2 = False
            ports_count = 0
            try: 
                # Try and find whether the npdrv2 subkey exists to determine whether we are using 
                # the Nport Driver manager as opposed to Nport Administrator
                ports_path = wrg.OpenKeyEx(location,REG_DIR_NPDRV2)
                using_npdrv2 = True
                ports_count = wrg.QueryInfoKey(ports_path)[0]
            except FileNotFoundError: 
                print_and_log("using old style registry for moxas", severity=SEVERITY.MINOR)
            try:
                if using_npdrv2:
                    # This is what Nport Windows Driver manager uses. It uses a subkey for each port mappping,
                    # each of which has an ip address referenced. It doesn't seem to have a physical port number
                    # as the ports are added individually, so we have to modulo the port number. 
                    for port_num in range(0, ports_count):
                        port_subkey = f"{port_num:04d}"
                        port_reg = wrg.OpenKeyEx(ports_path, port_subkey)
                        device_params = wrg.OpenKeyEx(port_reg, "Device Parameters")
                        ip_addr = wrg.QueryValueEx(device_params, "IPAddress1")[0]
                        com_num = wrg.QueryValueEx(device_params, "COMNO")[0]
                        hostname = self._get_hostname(ip_addr)

                        moxa_name_ip_dict[hostname] = ip_addr

                        if hostname not in moxa_ports_dict.keys():
                            moxa_ports_dict[hostname] = list()
                        # Modulo by 16 here as we want the 2nd moxa's first port_num to be 1 rather
                        # than 17 as it's the first port on the second moxa
                        port_num_respective = port_num % 16 
                        moxa_ports_dict[hostname].append((port_num_respective + 1, com_num))

                else: 
                    # This is what Nport Administrator uses. It lays out each Moxa that is added to "Servers" which contains a few bytes
                    # and lays things out in a subkey for each.
                    params = wrg.OpenKeyEx(location,REG_KEY_NPDRV)
                    server_count = wrg.QueryValueEx(params, "Servers")[0]

                    for server_num in range(1, server_count+1):
                        soft = wrg.OpenKeyEx(location,f"{REG_KEY_NPDRV}\\Server{server_num}")
                        ip_addr_bytes = wrg.QueryValueEx(soft,"IPAddress")[0].to_bytes(4)
                        ip_addr = ".".join([str(int(x)) for x in ip_addr_bytes])
                        hostname = self._get_hostname(ip_addr)
                        moxa_name_ip_dict[hostname] = ip_addr
                        print_and_log(f"IP {ip_addr} hostname {hostname}")
                        start_num_com = 1
                        com_nums = enumerate(wrg.QueryValueEx(soft,"COMNO")[0], start_num_com)
                        moxa_ports_dict[hostname] = list(com_nums)
                        for count, value in com_nums: 
                            print_and_log(f"physical port {count} COM number {value}")
            except FileNotFoundError as e:
                print_and_log(f"Error reading registry for moxa mapping information: {str(e)}", severity=SEVERITY.MAJOR)

        return moxa_name_ip_dict, moxa_ports_dict

