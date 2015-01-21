"""Contains string constants used by the modules of the config package"""
GRP_NONE = "NONE"

TAG_NAME = 'name'
TAG_VALUE = 'value'

TAG_BLOCKS = 'blocks'
TAG_GROUPS = 'groups'
TAG_IOCS = 'iocs'
TAG_SUBCONFIGS = 'components'
TAG_MACROS = 'macros'
TAG_PVS = 'pvs'
TAG_PVSETS = 'pvsets'

TAG_BLOCK = 'block'
TAG_GROUP = 'group'
TAG_IOC = 'ioc'
TAG_SUBCONFIG = 'component'
TAG_MACRO = 'macro'
TAG_PV = 'pv'
TAG_PVSET = 'pvset'

TAG_LOCAL = 'local'
TAG_READ_PV = 'read_pv'
TAG_VISIBLE = 'visible'
TAG_RUNCONTROL = 'rc_save'
TAG_RUNCONTROL_ENABLED = 'rc_enabled'
TAG_RUNCONTROL_LOW = 'rc_lowlimit'
TAG_RUNCONTROL_HIGH = 'rc_highlimit'

AUTOSAVE_NAME = 'autosave'


TAG_AUTOSTART = 'autostart'
TAG_RESTART = 'restart'
TAG_SIMLEVEL = 'simlevel'

TAG_RC_LOW = ":RC:LOW"
TAG_RC_HIGH = ":RC:HIGH"
TAG_RC_ENABLE = ":RC:ENABLE"
TAG_RC_OUT_LIST = "CS:RC:OUT:LIST"

SIMLEVELS = ['recsim', 'devsim']

IOCS_NOT_TO_STOP = ('INSTETC', 'PSCTRL', 'ISISDAE', 'BLOCKSVR', 'ARINST', 'ARBLOCK', 'GWBLOCK', 'RUNCTRL')

CONFIG_DIRECTORY = "/configurations/"
COMPONENT_DIRECTORY = "/components/"
RUNCONTROL_SETTINGS = "/rc_settings.cmd"
RUNCONTROL_IOC = "RUNCTRL_01"

FILENAME_BLOCKS = "blocks.xml"
FILENAME_GROUPS = "groups.xml"
FILENAME_IOCS = "iocs.xml"
FILENAME_SUBCONFIGS = "components.xml"
FILENAME_META = "meta.xml"

VALID_FILENAMES = [FILENAME_BLOCKS, FILENAME_GROUPS, FILENAME_IOCS, FILENAME_META, FILENAME_SUBCONFIGS]