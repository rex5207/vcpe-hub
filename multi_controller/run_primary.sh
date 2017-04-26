#!/ bin/bash
ryu-manager l2switch.py MasterApp.py --wsapi-port 7777 --ofp-tcp-listen-port 6666 --observe-links --verbose
