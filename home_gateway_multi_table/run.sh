#!/ bin/bash
ryu-manager base.py service_control.py firewall.py qos.py forwarding.py dhcp.py nat.py --observe-links --verbose
