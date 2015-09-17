"""Detect Gateway."""
from ryu.lib.packet import ethernet
from ryu.lib.packet import ipv4
from ryu.lib.packet import udp, tcp
from ryu.ofproto import inet

from setting.db.data_collection import switch_inner_port
from setting.variables import constant


def dectect_by_dhcp(pkt, datapath, in_port):
    """Detect gateway by dhcp."""
    return_value = [-1, -1]
    pkt_eth = pkt.get_protocols(ethernet.ethernet)[0]
    pkt_ipv4 = pkt.get_protocol(ipv4.ipv4)
    if pkt_ipv4.proto == inet.IPPROTO_UDP:
        pkt_udp = pkt.get_protocol(udp.udp)
        udp_src = pkt_udp.src_port
        udp_dst = pkt_udp.dst_port

        switch_tuple = (datapath.id, in_port)

        if udp_src == 67 and udp_dst == 68:
            if switch_tuple not in switch_inner_port:
                # gateway dpid / gateway mac
                return_value = [datapath.id, pkt_eth.src]

    return return_value


def detect_by_flow(pkt, member_list):
    """Detect gateway by flows."""
    return_value = [-1, -1]
    pkt_ipv4 = pkt.get_protocol(ipv4.ipv4)
    pkt_eth = pkt.get_protocols(ethernet.ethernet)[0]

    member_s = member_list.get(pkt_eth.src)
    member_t = member_list.get(pkt_eth.dst)
    print '[INFO] pkt >> \n'
    print '  >>', pkt_eth.src, pkt_eth.dst
    print '  >>', pkt_ipv4.src, pkt_ipv4.dst
    if member_s is not None and member_t is not None:
        if member_s.ip != pkt_ipv4.src:
            return_value = [member_s.datapath.id, pkt_eth.src]
        if member_t.ip != pkt_ipv4.dst:
            return_value = [member_t.datapath.id, pkt_eth.dst]

        print '  >>', member_s.ip, member_t.ip


    return return_value


def detect_gateway_main(pkt, datapath, in_port, member_list):
    """Main method for Detect gateway."""
    if constant.Detect_switch_DPID_check != 2:
        ans1 = dectect_by_dhcp(pkt, datapath, in_port)
        ans2 = detect_by_flow(pkt, member_list)

        if ans2 != [-1, -1]:
            constant.Detect_switch_DPID_check = 2
            constant.Detect_switch_DPID = str(ans2[0])
            constant.Gateway_Mac = str(ans2[1])
            if member_list.get(ans2[1]) is not None:
                constant.Gateway_IP = str(member_list[ans2[1]].ip)
        else:
            if ans1 != [-1, -1]:
                constant.Detect_switch_DPID_check = 1
                constant.Detect_switch_DPID = str(ans1[0])
                constant.Gateway_Mac = str(ans1[1])
                if member_list.get(ans1[1]) is not None:
                    constant.Gateway_IP = str(member_list[ans1[1]].ip)

        print '[INFO] Gateway detection >>\n'
        print '  >> ', constant.Detect_switch_DPID_check, '\n'
        print '  >> ', constant.Detect_switch_DPID, '\n'
        print '  >> ', constant.Gateway_Mac
        print '  >> ', constant.Gateway_IP
        print '  >> ', constant.Controller_IP
