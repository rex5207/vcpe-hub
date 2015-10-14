import netaddr

wan_port = 1

gateway = '127.0.0.254'

nat_public_ip = '127.0.0.1'
nat_private_ip = '192.168.8.1'
nat_private_network = '192.168.8.0'
private_subnetwork = netaddr.IPNetwork('192.168.8.0/24')
nat_subnetwork = netaddr.IPNetwork('127.0.0.0/24')


MAC_ON_WAN = '00:0e:c6:87:a6:fb'
MAC_ON_LAN = '00:0e:c6:87:a6:fa'
IDLE_TIME = 30
