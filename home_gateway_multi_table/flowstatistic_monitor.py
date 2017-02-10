from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.topology.api import get_switch
from ryu.controller.event import EventBase
from ryu.lib import hub
from ryu.ofproto import ether
from ryu.ofproto import inet

from config import forwarding_config
from models import flow


class flowstatistic_monitor(app_manager.RyuApp):

    def __init__(self, *args, **kwargs):
        """Initial Setting method."""
        super(flowstatistic_monitor, self).__init__(*args, **kwargs)
        self.topology_api_app = self
        self.monitor_thread = hub.spawn(self._monitor)
        self.flow_list_tmp = {}

    def _monitor(self):
        while True:
            switch_list = get_switch(self.topology_api_app, None)
            for dp in switch_list:
                # if str(dp.dp.id) == constant.Detect_switch_DPID:
                self._request_stats(dp.dp)
                # break
            hub.sleep(1)

    def _request_stats(self, datapath):
        parser = datapath.ofproto_parser

        req = parser.OFPFlowStatsRequest(datapath)
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def _flow_stats_reply_handler(self, ev):
        self.flow_list_tmp = {}
        body = ev.msg.body
        for stat in body:
            if stat.match.get('eth_type') == ether.ETH_TYPE_IP:
                key_tuples = str(ev.msg.datapath.id)\
                             + stat.match.get('eth_src')\
                             + stat.match.get('eth_dst')\
                             + stat.match.get('ipv4_src')\
                             + str(stat.match.get('ip_proto'))\

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
                        forwarding_config.flow_list.update({key_tuples: flow_value})
                    else:
                        flow_value = forwarding_config.flow_list.get(key_tuples)
                        flow_value.byte_count_1 = flow_value.byte_count_2
                        flow_value.byte_count_2 = stat.byte_count
                        flow_value.rate_calculation()
                        flow_value.exist = 1
                    self.flow_list_tmp.update({key_tuples: flow_value})
