"""constant Setting."""
import socket

FlowClassification_IP = "192.168.0.174"
Detect_switch_DPID_check = 0
Detect_switch_DPID = 1
Gateway_IP = "192.168.0.1"
Gateway_Mac = None
Controller_IP = socket.gethostbyname(socket.gethostname())
NeedToAuth = 0

# KB/s
Capacity = -1
enable_ns = 0

# spanning_tree
ccc = None
load_limitation = 10000000000

NeedDynamicQos = 0
db_method = 'cloud'
