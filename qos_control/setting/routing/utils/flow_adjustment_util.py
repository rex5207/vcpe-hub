from ryu.ofproto import ether, inet
from setting.utils.ofputils import add_flow

def flow_adjust(net, path, flow):
    for node in path:

        index = path.index(node)
        if index != 0 and index != len(path)-1 and index != len(path)-2:
            print node
            parser = node.ofproto_parser
            if flow.ip_proto == inet.IPPROTO_TCP:
                match = parser.OFPMatch(eth_src=flow.src_mac,
                                        eth_dst=flow.dst_mac,
                                        eth_type=ether.ETH_TYPE_IP,
                                        ipv4_src=flow.src_ip,
                                        ipv4_dst=flow.dst_ip,
                                        ip_proto=flow.ip_proto,
                                        tcp_src=flow.src_port,
                                        tcp_dst=flow.dst_port)
            else:
                match = parser.OFPMatch(eth_src=flow.src_mac,
                                        eth_dst=flow.dst_mac,
                                        eth_type=ether.ETH_TYPE_IP,
                                        ipv4_src=flow.src_ip,
                                        ipv4_dst=flow.dst_ip,
                                        ip_proto=flow.ip_proto,
                                        udp_src=flow.src_port,
                                        udp_dst=flow.dst_port)
            priority = 10
            out_port = net[node.id][path[index+1].id]['port']
            actions = [parser.OFPActionOutput(out_port)]
            add_flow(node, priority, match, actions)
