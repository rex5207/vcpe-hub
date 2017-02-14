from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER,MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.topology.api import get_switch
from ryu.controller.event import EventBase
from ryu.lib import hub
from ryu.ofproto import ether
from ryu.ofproto import inet
from ryu.app.ofctl.api import get_datapath

from config import forwarding_config,qos_config
from models import flow
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

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        self.monitor_thread = hub.spawn(self._monitor, datapath)

    def _monitor(self, datapath):
        while True:
            parser = datapath.ofproto_parser
            req = parser.OFPFlowStatsRequest(datapath)
            datapath.send_msg(req)
            self.update_app_for_flows(forwarding_config.flow_list)
            hub.sleep(1)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def _flow_stats_reply_handler(self, ev):
        body = ev.msg.body
        for stat in body:
            if stat.match.get('eth_type') == ether.ETH_TYPE_IP:
                key_tuples = str(ev.msg.datapath.id)\
                             + '' or stat.match.get('eth_src')\
                             + stat.match.get('eth_dst')\
                             + stat.match.get('ipv4_src')\
                             + stat.match.get('ipv4_dst')\
                             + str(stat.match.get('ip_proto'))
                # print key_tuples
                if stat.match.get('ip_proto') == inet.IPPROTO_TCP:
                    key_tuples += str(stat.match.get('tcp_src')) + str(stat.match.get('tcp_dst'))
                    # print key_tuples
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
                        forwarding_config.flow_list.update({key_tuples: flow_value})
                    else:
                        flow_value = forwarding_config.flow_list.get(key_tuples)
                        flow_value.byte_count_1 = flow_value.byte_count_2
                        flow_value.byte_count_2 = stat.byte_count
                        flow_value.rate_calculation()
                        flow_value.exist = 1
                    # print "====="
                    # print flow_value.byte_count_1
                    # print flow_value.byte_count_2
                    # print "====="

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
                        forwarding_config.flow_list.update({key_tuples: flow_value})
                    else:
                        flow_value = forwarding_config.flow_list.get(key_tuples)
                        flow_value.byte_count_1 = flow_value.byte_count_2
                        flow_value.byte_count_2 = stat.byte_count
                        flow_value.rate_calculation()
                        flow_value.exist = 1

    def update_app_for_flows(self, flow_list):
        for key in flow_list.keys():
            flow_info = flow_list.get(key)
            if flow_info is not None and flow_info.app == 'Others' and flow_info.src_ip is not None:
                json_data = None
                m = hashlib.sha256()
                m.update(flow_info.src_ip
                         + flow_info.dst_ip
                         + str(flow_info.src_port)
                         + str(flow_info.dst_port)
                         + str(flow_info.ip_proto))
                url = qos_config.get_flowstatistic_info + m.hexdigest()
                response = requests.get(url)
                flow_info.counter = flow_info.counter + 1
                if response.status_code == 200:
                    json_data = response.json()
                else:
                    m = hashlib.sha256()
                    m.update(flow_info.dst_ip
                             + flow_info.src_ip
                             + str(flow_info.dst_port)
                             + str(flow_info.src_port)
                             + str(flow_info.ip_proto))
                    url = qos_config.get_flowstatistic_info + m.hexdigest()
                    response = requests.get(url)
                    if response.status_code == 200:
                        json_data = response.json()

                if json_data is not None:
                    app_name = json_data.get('classifiedResult').get('classifiedName')
                    flow_info.app = app_name
                    ev = APP_UpdateEvent('Update rate for app')
                    self.send_event_to_observers(ev)
