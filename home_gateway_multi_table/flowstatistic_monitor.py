from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.topology.api import get_switch
from ryu.controller.event import EventBase
from ryu.lib import hub
from ryu.ofproto import ether
from ryu.ofproto import inet
from ryu.app.ofctl.api import get_datapath
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types
from ryu.lib.packet import arp
from ryu.lib.packet import ipv4
from ryu.lib.packet import tcp
from ryu.lib.packet import udp
from ryu.lib.packet import dhcp

from config import forwarding_config, qos_config
from models import flow
from models.member import Member

from qos import APP_UpdateEvent

import requests
import hashlib
import logging


class flowstatistic_monitor(app_manager.RyuApp):

    _EVENTS = [APP_UpdateEvent]

    def __init__(self, *args, **kwargs):
        """Initial Setting method."""
        super(flowstatistic_monitor, self).__init__(*args, **kwargs)
        self.topology_api_app = self
        logging.getLogger("requests").setLevel(logging.WARNING)
        self.flow_list_tmp = {}

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        self.monitor_thread = hub.spawn(self._monitor, datapath)

    def _monitor(self, datapath):
        while True:
            key_set = forwarding_config.flow_list.keys()
            for key in key_set:
                flow = forwarding_config.flow_list[key]
                if flow.exist == 0:
                    forwarding_config.flow_list.pop(key)
                else:
                    forwarding_config.flow_list[key].exist = 0
            parser = datapath.ofproto_parser
            req = parser.OFPFlowStatsRequest(datapath)
            datapath.send_msg(req)
            self.update_app_for_flows(forwarding_config.flow_list)
            hub.sleep(1)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def _flow_stats_reply_handler(self, ev):
        self.flow_list_tmp = {}
        body = ev.msg.body
        for stat in body:
            if stat.match.get('eth_type') == ether.ETH_TYPE_IP:
                key_tuples = str(ev.msg.datapath.id)\
                             + '' or stat.match.get('eth_src')\
                             + stat.match.get('eth_dst')\
                             + stat.match.get('ipv4_src')\
                             + stat.match.get('ipv4_dst')\
                             + str(stat.match.get('ip_proto'))

                if stat.match.get('ip_proto') == inet.IPPROTO_TCP:
                    key_tuples += str(stat.match.get('tcp_src')) + str(stat.match.get('tcp_dst'))

                    if forwarding_config.flow_list.get(key_tuples) is None:
                        flow_value = flow.Flow(ev.msg.datapath.id,
                                               stat.match.get('eth_src'),
                                               stat.match.get('eth_dst'),
                                               stat.match.get('ipv4_src'),
                                               stat.match.get('ipv4_dst'),
                                               stat.match.get('ip_proto'),
                                               stat.match.get('tcp_src'),
                                               stat.match.get('tcp_dst'),
                                               stat.byte_count, 1)
                        flow_value.rate_calculation()
                        forwarding_config.flow_list.update({key_tuples: flow_value})
                    else:
                        flow_value = forwarding_config.flow_list.get(key_tuples)
                        flow_value.byte_count_1 = flow_value.byte_count_2
                        flow_value.byte_count_2 = stat.byte_count
                        flow_value.rate_calculation()
                        flow_value.exist = 1
                    self.flow_list_tmp.update({key_tuples: flow_value})

                elif stat.match.get('ip_proto') == inet.IPPROTO_UDP:
                    key_tuples += str(stat.match.get('udp_src'))\
                                      + str(stat.match.get('udp_dst'))
                    if forwarding_config.flow_list.get(key_tuples) is None:
                        flow_value = flow.Flow(ev.msg.datapath.id,
                                               stat.match.get('eth_src'),
                                               stat.match.get('eth_dst'),
                                               stat.match.get('ipv4_src'),
                                               stat.match.get('ipv4_dst'),
                                               stat.match.get('ip_proto'),
                                               stat.match.get('udp_src'),
                                               stat.match.get('udp_dst'),
                                               stat.byte_count, 1)
                        flow_value.rate_calculation()
                        forwarding_config.flow_list.update({key_tuples: flow_value})
                    else:
                        flow_value = forwarding_config.flow_list.get(key_tuples)
                        flow_value.byte_count_1 = flow_value.byte_count_2
                        flow_value.byte_count_2 = stat.byte_count
                        flow_value.rate_calculation()
                        flow_value.exist = 1
                    self.flow_list_tmp.update({key_tuples: flow_value})

    def update_app_for_flows(self, flow_list):
        for key in flow_list.keys():
            flow_info = flow_list.get(key)
            if flow_info is not None and flow_info.app == 'Others' and flow_info.src_ip is not None:
                json_data = None
                m = hashlib.sha256()
                m.update(flow_info.src_ip +
                         flow_info.dst_ip +
                         str(flow_info.src_port) +
                         str(flow_info.dst_port) +
                         str(flow_info.ip_proto))
                url = qos_config.get_flowstatistic_info + m.hexdigest()
                response = requests.get(url)
                flow_info.counter = flow_info.counter + 1
                if response.status_code == 200:
                    json_data = response.json()
                else:
                    m = hashlib.sha256()
                    m.update(flow_info.dst_ip +
                             flow_info.src_ip +
                             str(flow_info.dst_port) +
                             str(flow_info.src_port) +
                             str(flow_info.ip_proto))
                    url = qos_config.get_flowstatistic_info + m.hexdigest()
                    response = requests.get(url)
                    if response.status_code == 200:
                        json_data = response.json()

                if json_data is not None:
                    app_name = json_data.get('classifiedResult').get('classifiedName')
                    flow_info.app = app_name
        ev = APP_UpdateEvent('Update rate for app')
        self.send_event_to_observers(ev)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        # retrieve packet
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']
        dpid = datapath.id
        pkt = packet.Packet(msg.data)
        pkt_eth = pkt.get_protocols(ethernet.ethernet)[0]
        pkt_ipv4 = pkt.get_protocol(ipv4.ipv4)
        pkt_arp = pkt.get_protocol(arp.arp)
        pkt_dhcp = pkt.get_protocol(dhcp.dhcp)

        if pkt_dhcp:
            for options in pkt_dhcp.options.option_list:
                if(options.tag == 12):
                    if forwarding_config.member_list.get(pkt_dhcp.chaddr) is not None:
                        member = forwarding_config.member_list.get(pkt_dhcp.chaddr)
                    else:
                        forwarding_config.member_list.setdefault(pkt_dhcp.chaddr,
                                                                 Member(pkt_dhcp.chaddr))
                        forwarding_config.member_list[pkt_dhcp.chaddr].datapath = datapath
                        forwarding_config.member_list[pkt_dhcp.chaddr].port = in_port
                    forwarding_config.member_list[pkt_dhcp.chaddr].hostname = options.value

        if pkt_arp:
            self._handle_arp(msg, in_port, pkt_eth, pkt_arp)
        elif pkt_ipv4:
            self._handle_ipv4(msg, in_port, pkt, pkt_eth, pkt_ipv4)

    def _handle_arp(self, msg, in_port, pkt_eth, pkt_arp):
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        eth_src = pkt_eth.src

        # update member(host) in member_list
        member_list = forwarding_config.member_list
        member_list.setdefault(eth_src, Member(eth_src))
        member_list[eth_src].datapath = datapath
        member_list[eth_src].port = in_port

    def _handle_ipv4(self, msg, in_port, pkt, pkt_ethernet, pkt_ipv4):
        datapath = msg.datapath
        eth_src = pkt_ethernet.src

        # update ip info for members in member_list
        member_list = forwarding_config.member_list
        member_list.setdefault(eth_src, Member(eth_src))
        src_member = member_list[pkt_ethernet.src]
        src_member.ip = pkt_ipv4.src
        src_member.port = in_port
        src_member.datapath = datapath
