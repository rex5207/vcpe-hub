from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.lib import hub
from ryu.ofproto import inet

import data


class SimpleMonitor(app_manager.RyuApp):
    def __init__(self, *args, **kwargs):
        super(SimpleMonitor, self).__init__(*args, **kwargs)
        self.datapaths = {}
        self.monitor_thread = hub.spawn(self._monitor)

    @set_ev_cls(ofp_event.EventOFPStateChange,
                [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def _state_change_handler(self, ev):
        datapath = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            if datapath.id not in self.datapaths:
                self.logger.debug('register datapath: %016x', datapath.id)
                self.datapaths[datapath.id] = datapath
        elif ev.state == DEAD_DISPATCHER:
            if datapath.id in self.datapaths:
                self.logger.debug('unregister datapath: %016x', datapath.id)
                del self.datapaths[datapath.id]

    def _monitor(self):
        while True:
            for dp in self.datapaths.values():
                self._request_stats(dp)
            hub.sleep(3)

    def _request_stats(self, datapath):
        self.logger.debug('send stats request: %016x', datapath.id)
        # ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        req = parser.OFPFlowStatsRequest(datapath)
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def _flow_stats_reply_handler(self, ev):
        data.blocking_flow = []
        body = ev.msg.body
        for stat in body:
            flow = {}
            if (stat.instructions == []):
                flow.update({'ipSrc': stat.match.get('ipv4_src')})
                flow.update({'ipDst': stat.match.get('ipv4_dst')})
                if (stat.match.get('ip_proto') == inet.IPPROTO_TCP):
                    flow.update({'tranPort': stat.match.get('tcp_dst')})
                    flow.update({'tranProtocol': 'TCP'})
                else:
                    flow.update({'tranPort': stat.match.get('udp_dst')})
                    flow.update({'tranProtocol': 'UDP'})

                data.blocking_flow.append(flow)
