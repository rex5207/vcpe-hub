"""Project For Port Monitor on switches."""

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.topology.api import get_switch
from ryu.controller.handler import set_ev_cls
from ryu.controller.handler import MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.lib import hub

from ryu.app.wsgi import ControllerBase, WSGIApplication, route
from webob import Response

import json

from route import urls

port_monitor_instance_name = 'simple_switch_api_app'


class PortStatMonitor(app_manager.RyuApp):

    """Class for Port Monitor."""

    _CONTEXTS = {'wsgi': WSGIApplication}

    def __init__(self, *args, **kwargs):
        """Initial method."""
        super(PortStatMonitor, self).__init__(*args, **kwargs)
        self.sw_port_stat = {}
        self.datapaths = {}
        self.dpid_list = []
        self.current_rate = 0.0
        self.topology_api_app = self
        self.monitor_thread = hub.spawn(self._monitor)

        wsgi = kwargs['wsgi']
        wsgi.register(PortStatisticRest, {port_monitor_instance_name: self})

    @set_ev_cls(ofp_event.EventOFPStateChange,
                [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def _state_change_handler(self, ev):
        datapath = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            if datapath.id not in self.datapaths:
                self.logger.debug('register datapath: %016x', datapath.id)
                self.datapaths[datapath.id] = datapath
                self.dpid_list.append(datapath.id)
        elif ev.state == DEAD_DISPATCHER:
            if datapath.id in self.datapaths:
                self.logger.debug('unregister datapath: %016x', datapath.id)
                del self.datapaths[datapath.id]
                self.dpid_list.remove(datapath.id)

    def _monitor(self):
        while True:
            switch_list = get_switch(self.topology_api_app, None)
            for datapath in switch_list:
                if self.sw_port_stat.get(datapath.dp.id) is None:
                    port_stat = {}
                    self.sw_port_stat.update({datapath.dp.id: port_stat})
                # print 'rate:', self.current_rate
                self._request_stats(datapath.dp)
            hub.sleep(5)

    def _request_stats(self, datapath):
        """Send PortStatsRequest method."""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        req = parser.OFPPortStatsRequest(datapath, 0, ofproto.OFPP_ANY)
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def _port_stats_reply_handler(self, ev):
        """Handle PortStatsReply from switches method."""
        sw_dpid = ev.msg.datapath.id
        rate = 0
        for stat in ev.msg.body:
            counter_list = [stat.port_no, stat.rx_bytes, stat.tx_bytes]

            p_r = 0
            p_t = 0

            if self.sw_port_stat.get(sw_dpid).get(stat.port_no) is not None:
                his_stat = self.sw_port_stat.get(sw_dpid).get(stat.port_no)
                p_r = (counter_list[1] - his_stat[1])/5
                p_t = (counter_list[2] - his_stat[2])/5

                rate = rate + p_r + p_t
            counter_list.append(p_r)
            counter_list.append(p_t)
            port_stat = {stat.port_no: counter_list}
            self.sw_port_stat.get(sw_dpid).update(port_stat)
        # print '@', rate
        self.current_rate = rate*8/1024


class PortStatisticRest(ControllerBase):

    def __init__(self, req, link, data, **config):
        super(PortStatisticRest, self).__init__(req, link, data, **config)
        self.simpl_port_app = data[port_monitor_instance_name]

    @route('simpleswitch', urls.url_switches, methods=['GET'])
    def get_switches_list(self, req, **kwargs):
        sorted(self.simpl_port_app.dpid_list)
        tmp = {'dpid': sorted(self.simpl_port_app.dpid_list)}
        dpid_content = []
        for dp in tmp['dpid']:
            dpid_content.append(str(dp))
        dpid_list = {'dpid': dpid_content}
        body = json.dumps(dpid_list)
        return Response(content_type='application/json', body=body)

    @route('simpleswitch', urls.url_portstats, methods=['GET'])
    def get_port_info(self, req, **kwargs):
        dpid = str(kwargs['dpid'])
        status_list = self.simpl_port_app.sw_port_stat.get(int(dpid))

        total = 0
        rx = 0
        tx = 0
        if status_list is not None:
            for port in status_list:
                if port != 4294967294:
                    statistic = status_list.get(port)
                    total += statistic[3] + statistic[4]
                    rx += statistic[3]
                    tx += statistic[4]

        print total, tx, rx
        # all_port_rate = {'kbps': self.simpl_port_app.current_rate}
        all_port_rate = {'total': total*8/1024,
                         'rx': rx*8/1024,
                         'tx': tx*8/1024}
        body = json.dumps(all_port_rate)
        return Response(content_type='application/json', body=body)
