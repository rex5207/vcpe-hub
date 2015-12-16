"""Project for Forwarding."""

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.ofproto import ether, inet
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ipv4
from ryu.lib.packet import tcp
from ryu.lib.packet import udp
from ryu.topology.api import get_switch
from ryu.lib.packet import arp
from ryu.lib import mac

from setting.utils import ofputils
from setting.db import data_collection
from setting.db import collection
import networkx as nx
from setting.detect_gateway import utils as gateway_utils

import logging
import time
import datetime

class forwarding(app_manager.RyuApp):

    """forwarding Class."""

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        """Initial Setting method."""
        super(forwarding, self).__init__(*args, **kwargs)
        self.topology_api_app = self
        self.broadip = '255.255.255.255'
        self.broadip2 = '0.0.0.0'
        hdlr = logging.FileHandler('flow_statistic.log')
        self.logger.addHandler(hdlr)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):

        msg = ev.msg

        datapath = msg.datapath
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        pkt_eth = pkt.get_protocols(ethernet.ethernet)[0]
        pkt_ipv4 = pkt.get_protocol(ipv4.ipv4)
        pkt_arp = pkt.get_protocol(arp.arp)
        if pkt_arp:
            self._handle_arp(msg, datapath, in_port, pkt_eth, pkt_arp)

        elif pkt_ipv4:
            gateway_utils.detect_gateway_main(pkt, datapath, in_port, data_collection.member_list)
            if (pkt_eth.dst == mac.BROADCAST):
                self._broadcast_pkt(msg)
            elif (pkt_ipv4.dst == self.broadip) or (pkt_ipv4.dst == self.broadip2):
                self._broadcast_pkt(msg)
            else:
                check = 'whole'
                self._handle_ipv4(msg, datapath, in_port, pkt_eth,
                                  pkt_ipv4, pkt, pkt_eth.dst, check)
        else:
            self._broadcast_pkt(msg)

    def _handle_ipv4(self, msg, datapath, port, pkt_ethernet, pkt_ipv4, pkt,
                     dst_mac, group_id):
        parser = datapath.ofproto_parser
        group = data_collection.group_list.get(group_id)
        net = group.topology
        m_dst = data_collection.member_list.get(dst_mac)
        if m_dst is not None:
            ipv4_path = self._generate_path(net,
                                            pkt_ethernet.src, pkt_ethernet.dst,
                                            port, m_dst.port,
                                            datapath.id, m_dst.datapath.id)
            for next_n in ipv4_path:
                index = ipv4_path.index(next_n)
                if index != 0 and index != len(ipv4_path)-1:
                    out_port = None
                    net = group.topology
                    if index == len(ipv4_path)-2:
                        out_port = m_dst.port
                    else:
                        out_port = net[next_n][ipv4_path[index+1]]['port']

                    if index == 1:
                        out_port2 = port
                    else:
                        # print index, pkt_ethernet.dst, pkt_ethernet.src
                        # print ipv4_path[index+1], next_n
                        out_port2 = net[next_n][ipv4_path[index-1]]['port']


                    actions = [parser.OFPActionOutput(out_port)]
                    actions2 = [parser.OFPActionOutput(out_port2)]
                    # print 'switch!!', next_n
                    out_datapath = get_switch(self.topology_api_app, dpid=next_n)
                    # print pkt_ethernet.src,pkt_ethernet.dst,out_datapath, out_port, out_port2
                    if pkt_ipv4.proto == inet.IPPROTO_TCP:
                        pkt_tcp = pkt.get_protocol(tcp.tcp)
                        match = parser.OFPMatch(eth_src=pkt_ethernet.src,
                                                eth_dst=pkt_ethernet.dst,
                                                eth_type=ether.ETH_TYPE_IP,
                                                ipv4_src=pkt_ipv4.src,
                                                ipv4_dst=pkt_ipv4.dst,
                                                ip_proto=pkt_ipv4.proto,
                                                tcp_src=pkt_tcp.src_port,
                                                tcp_dst=pkt_tcp.dst_port)
                        match2 = parser.OFPMatch(eth_src=pkt_ethernet.dst,
                                                 eth_dst=pkt_ethernet.src,
                                                 eth_type=ether.ETH_TYPE_IP,
                                                 ipv4_src=pkt_ipv4.dst,
                                                 ipv4_dst=pkt_ipv4.src,
                                                 ip_proto=pkt_ipv4.proto,
                                                 tcp_src=pkt_tcp.dst_port,
                                                 tcp_dst=pkt_tcp.src_port)
                        ts = time.time()
                        st = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
                        self.logger.info('%s %s %s %s %s %s',
                                         pkt_ipv4.src, str(pkt_tcp.src_port),
                                         pkt_ipv4.dst, str(pkt_tcp.dst_port),
                                         pkt_ipv4.proto, st)

                    elif pkt_ipv4.proto == inet.IPPROTO_UDP:
                        pkt_udp = pkt.get_protocol(udp.udp)
                        match = parser.OFPMatch(eth_src=pkt_ethernet.src,
                                                eth_dst=pkt_ethernet.dst,
                                                eth_type=ether.ETH_TYPE_IP,
                                                ipv4_src=pkt_ipv4.src,
                                                ipv4_dst=pkt_ipv4.dst,
                                                ip_proto=pkt_ipv4.proto,
                                                udp_src=pkt_udp.src_port,
                                                udp_dst=pkt_udp.dst_port)
                        match2 = parser.OFPMatch(eth_src=pkt_ethernet.dst,
                                                 eth_dst=pkt_ethernet.src,
                                                 eth_type=ether.ETH_TYPE_IP,
                                                 ipv4_src=pkt_ipv4.dst,
                                                 ipv4_dst=pkt_ipv4.src,
                                                 ip_proto=pkt_ipv4.proto,
                                                 udp_src=pkt_udp.dst_port,
                                                 udp_dst=pkt_udp.src_port)
                        ts = time.time()
                        st = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
                        self.logger.info('%s %s %s %s %s %s',
                                         pkt_ipv4.src, str(pkt_udp.src_port),
                                         pkt_ipv4.dst, str(pkt_udp.dst_port),
                                         pkt_ipv4.proto, st)
                    else:
                        match = parser.OFPMatch(eth_src=pkt_ethernet.src,
                                                eth_dst=pkt_ethernet.dst,
                                                eth_type=ether.ETH_TYPE_IP,
                                                ipv4_src=pkt_ipv4.src,
                                                ipv4_dst=pkt_ipv4.dst)
                        match2 = parser.OFPMatch(eth_src=pkt_ethernet.dst,
                                                 eth_dst=pkt_ethernet.src,
                                                 eth_type=ether.ETH_TYPE_IP,
                                                 ipv4_src=pkt_ipv4.dst,
                                                 ipv4_dst=pkt_ipv4.src)

                    ofputils.add_flow(out_datapath[0].dp, 10, match, actions)
                    ofputils.add_flow(out_datapath[0].dp, 10, match2, actions2)
            actions_o = [parser.OFPActionOutput(m_dst.port)]
            datapath_o = m_dst.datapath
            out = parser.OFPPacketOut(datapath=datapath_o,
                                      buffer_id=msg.buffer_id,
                                      in_port=msg.match['in_port'],
                                      actions=actions_o,
                                      data=msg.data)
            datapath.send_msg(out)
        else:
            self._broadcast_pkt(msg)


    def _handle_arp(self, msg, datapath, port, pkt_ethernet, pkt_arp):
        """Handle ARP Setting method."""
        tuple_m = (datapath.id, port)
        if tuple_m not in data_collection.switch_inner_port:
            self._handle_member_info(datapath, port, pkt_ethernet, pkt_arp)
        parser = datapath.ofproto_parser
        if pkt_arp.opcode == arp.ARP_REPLY:
            group = data_collection.group_list.get('whole')
            net = group.topology
            dst = data_collection.member_list.get(pkt_arp.dst_mac)
            if dst is not None:
                arp_path = self._generate_path(net, pkt_ethernet.src,
                                               pkt_ethernet.dst, port,
                                               dst.port, datapath.id,
                                               dst.datapath.id)
                for next_n in arp_path:
                    index = arp_path.index(next_n)
                    if index != 0 and index != len(arp_path)-1:
                        out_port = None
                        if index == len(arp_path)-2:
                            out_port = dst.port
                        else:
                            out_port = net[next_n][arp_path[index+1]]['port']
                        actions = [datapath.ofproto_parser.
                                   OFPActionOutput(out_port)]
                        out_datapath = get_switch(self.topology_api_app,
                                                  dpid=next_n)
                        match = parser.OFPMatch(eth_src=pkt_ethernet.src,
                                                eth_dst=pkt_ethernet.dst,
                                                eth_type=ether.ETH_TYPE_ARP,
                                                arp_op=arp.ARP_REPLY)
                        ofputils.add_flow(out_datapath[0].dp, 10, match,
                                          actions)
                actions_o = [parser.OFPActionOutput(dst.port)]
                datapath_o = dst.datapath
                out = parser.OFPPacketOut(datapath=datapath_o,
                                          buffer_id=msg.buffer_id,
                                          in_port=msg.match['in_port'],
                                          actions=actions_o,
                                          data=msg.data)
                datapath.send_msg(out)
            else:
                self._broadcast_pkt(msg)
        else:
            self._broadcast_pkt(msg)

    def _generate_path(self, topo, src_mac, dst_mac, src_port,
                       dst_port, src_dpid, dst_dpid):
        """Generate path method."""
        net = nx.DiGraph(data=topo)
        net.add_node(src_mac)
        net.add_node(dst_mac)
        net.add_edge(int(src_dpid), src_mac, {'port': int(src_port)})
        net.add_edge(src_mac, int(src_dpid))
        net.add_edge(int(dst_dpid), dst_mac, {'port': int(dst_port)})
        net.add_edge(dst_mac, int(dst_dpid))
        try:
            path = nx.shortest_path(net, src_mac, dst_mac)
        except Exception:
            path = None
        return path

    def _handle_member_info(self, datapath, port, pkt_ethernet, pkt_arp):
        if data_collection.member_list.get(pkt_ethernet.src) is not None:
            member = data_collection.member_list.get(pkt_ethernet.src)
            member.datapath = datapath
            member.port = port
            member.ip = pkt_arp.src_ip
            group = data_collection.group_list.get(member.group_id)
            if pkt_ethernet.src not in group.members:
                group.members.append(pkt_ethernet.src)
        else:
            member = collection.Member(pkt_ethernet.src, "whole")
            member.datapath = datapath
            member.port = port
            member.ip = pkt_arp.src_ip
            data_collection.member_list.update({pkt_ethernet.src: member})
            data_collection.group_list.get('whole').members.append(pkt_ethernet.src)

    def _broadcast_pkt(self, msg):
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        actions = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
        out = parser.OFPPacketOut(datapath=datapath,
                                  buffer_id=msg.buffer_id,
                                  in_port=msg.match['in_port'],
                                  actions=actions,
                                  data=data)
        datapath.send_msg(out)
