#!/ bin/bash
ryu-manager l2switch.py SlaveApp.py --wsapi-port 5555 --ofp-tcp-listen-port 4444 --observe-links --verbose
