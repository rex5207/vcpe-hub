"""Prject for Flow Statistic."""
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.topology.api import get_switch
from ryu.controller.event import EventBase
from ryu.lib import hub
from ryu.ofproto import ether
from ryu.ofproto import inet

from setting.db import data_collection
from qos_control import Qos_UpdateEvent
from setting.db import collection


class APP_UpdateEvent(EventBase):
    def __init__(self, msg):
        self.msg = msg


class flowstatistic_monitor(app_manager.RyuApp):
    _EVENTS = [APP_UpdateEvent]
    _EVENTS = [Qos_UpdateEvent]
    """Flow Statistic Class."""

    def __init__(self, *args, **kwargs):
        """Initial Setting method."""
        super(flowstatistic_monitor, self).__init__(*args, **kwargs)
        self.topology_api_app = self
        self.monitor_thread = hub.spawn(self._monitor)
        self.flow_list_re = {}

    def _monitor(self):
        while True:
            print '[INFO flowstatistic_monitor._monitor] Flows >'
            key_set = data_collection.flow_list.keys()
            for key in key_set:
                flow = data_collection.flow_list[key]
                if flow.exist == 0:
                    data_collection.flow_list.pop(key)
                else:
                    if self.flow_list_re.get(key) is not None:
                        data_collection.flow_list[key].app = self.flow_list_re[key].app
                    data_collection.flow_list[key].exist = 0
                    print key, flow.rate, flow.app
            ev = APP_UpdateEvent('Update app for flow')
            self.send_event_to_observers(ev)
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
        self.flow_list_re = {}
        for stat in ev.msg.body:
            if stat.match.get('eth_type') == ether.ETH_TYPE_IP:
                key_tuples = str(ev.msg.datapath.id)\
                             + stat.match.get('eth_src')\
                             + stat.match.get('eth_dst')\
                             + stat.match.get('ipv4_src')\
                             + stat.match.get('ipv4_dst')\
                             + str(stat.match.get('ip_proto'))\

                if stat.match.get('ip_proto') == inet.IPPROTO_TCP:
                    key_tuples += str(stat.match.get('tcp_src')) + str(stat.match.get('tcp_dst'))
                    # print key_tuples
                    if data_collection.flow_list.get(key_tuples) is None:
                        flow_value = collection.Flow(ev.msg.datapath.id,
                                                     stat.match.get('eth_src'),
                                                     stat.match.get('eth_dst'),
                                                     stat.match.get('ipv4_src'),
                                                     stat.match.get('ipv4_dst'),
                                                     stat.match.get('ip_proto'),
                                                     stat.match.get('tcp_src'),
                                                     stat.match.get('tcp_dst'),
                                                     stat.byte_count, 1)
                        data_collection.flow_list.update({key_tuples: flow_value})

                    else:
                        flow_value = data_collection.flow_list.get(key_tuples)
                        flow_value.byte_count_1 = flow_value.byte_count_2
                        flow_value.byte_count_2 = stat.byte_count
                        flow_value.rate_calculation()
                        flow_value.exist = 1
                    self.flow_list_re.update({key_tuples: flow_value})

                elif stat.match.get('ip_proto') == inet.IPPROTO_UDP:
                    key_tuples += str(stat.match.get('udp_src'))\
                                      + str(stat.match.get('udp_dst'))
                    if data_collection.flow_list.get(key_tuples) is None:
                        flow_value = collection.Flow(ev.msg.datapath.id,
                                                     stat.match.get('eth_src'),
                                                     stat.match.get('eth_dst'),
                                                     stat.match.get('ipv4_src'),
                                                     stat.match.get('ipv4_dst'),
                                                     stat.match.get('ip_proto'),
                                                     stat.match.get('udp_src'),
                                                     stat.match.get('udp_dst'),
                                                     stat.byte_count, 1)
                        data_collection.flow_list.update({key_tuples: flow_value})
                    else:
                        flow_value = data_collection.flow_list.get(key_tuples)
                        flow_value.byte_count_1 = flow_value.byte_count_2
                        flow_value.byte_count_2 = stat.byte_count
                        flow_value.rate_calculation()
                        flow_value.exist = 1
                    self.flow_list_re.update({key_tuples: flow_value})
