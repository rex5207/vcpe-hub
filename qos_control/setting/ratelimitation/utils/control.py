from ryu.ofproto import ether, inet

from setting.utils import ofputils
from setting.db import data_collection


def set_ratelimite_for_app(appname, meter_id, group, state, d_or_m):
        """Set rate control for applications."""
        flow_to_be_handle = []
        key_set = data_collection.flow_list.keys()
        memberlist = data_collection.group_list.get(group).members
        for key in key_set:
            flow_info = data_collection.flow_list[key]
            if flow_info.app == appname:
                if flow_info.src_mac in memberlist or flow_info.dst_mac in memberlist:
                    if state == 'up':
                        if flow_info.limited == 0:
                            flow_info.limited = 1
                            flow_to_be_handle.append(flow_info)
                    else:
                        if flow_info.limited == 1:
                            flow_info.limited = 0
                            flow_to_be_handle.append(flow_info)

        for flow in flow_to_be_handle:
            datapath = data_collection.member_list.get(flow.dst_mac).datapath
            out_port = data_collection.member_list.get(flow.dst_mac).port

            parser = datapath.ofproto_parser
            actions = [parser.OFPActionOutput(out_port)]
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
            priority = 20
            if d_or_m == 'm':
                priority = 30
            elif d_or_m == 'o':
                priority = 10

            ofputils.add_flow_for_ratelimite(datapath, priority, match,
                                             actions, meter_id, state)

def set_ratelimite_for_member(member, meter_id, group, state, d_or_m):
    """Set rate control for members."""
    flow_to_be_handle = []
    key_set = data_collection.flow_list.keys()
    memberlist = data_collection.group_list.get(group).members
    for key in key_set:
        flow_info = data_collection.flow_list[key]
        if flow_info.src_mac == member or flow_info.dst_mac == member:
            if flow_info.src_mac in memberlist or flow_info.dst_mac in memberlist:
                if state == 'up':
                    if flow_info.limited == 0:
                        flow_info.limited = 1
                        flow_to_be_handle.append(flow_info)
                else:
                    if flow_info.limited == 1:
                        flow_info.limited = 0
                        flow_to_be_handle.append(flow_info)

    for flow in flow_to_be_handle:
        datapath = data_collection.member_list.get(flow.dst_mac).datapath
        out_port = data_collection.member_list.get(flow.dst_mac).port

        parser = datapath.ofproto_parser
        actions = [parser.OFPActionOutput(out_port)]
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
        priority = 20
        if d_or_m == 'm':
            priority = 30
        elif d_or_m == 'o':
            priority = 10

        ofputils.add_flow_for_ratelimite(datapath, priority, match,
                                         actions, meter_id, state)
