import json

from webob import Response
from ryu.base import app_manager
from ryu.app.wsgi import ControllerBase, WSGIApplication, route
from ryu.topology.api import get_switch
from ryu.ofproto import ether
from ryu.ofproto import inet
from ryu.controller import ofp_event
from ryu.controller.handler import set_ev_cls
from ryu.controller.handler import MAIN_DISPATCHER
import ryu.app.ofctl.api

import mirror_data
from route import urls

mirror_control_instance_name = 'mirror_control_api_app'

class MirrorControl(app_manager.RyuApp):

    _CONTEXTS = {'wsgi': WSGIApplication}

    def __init__(self, *args, **kwargs):
        super(MirrorControl, self).__init__(*args, **kwargs)
        self.switches = {}
        wsgi = kwargs['wsgi']
        wsgi.register(MirrorControlController,
                      {mirror_control_instance_name: self})
        self.topology_api_app = self


    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]
        if buffer_id:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                    priority=priority, match=match,
                                    instructions=inst)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, instructions=inst)
        datapath.send_msg(mod)

    def del_flow(self, datapath, match):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        mod = parser.OFPFlowMod(datapath=datapath,
                                command=ofproto.OFPFC_DELETE_STRICT,
                                out_port=ofproto.OFPP_ANY,
                                out_group=ofproto.OFPG_ANY,
                                match=match)
        datapath.send_msg(mod)

    def add_mirror_rule(self, rule_action, mirror_port, trans_proto):
        switch_list = get_switch(self.topology_api_app, None)
        for switch in switch_list:
            datapath = switch.dp
            parser = datapath.ofproto_parser

            match = parser.OFPMatch(ip_proto = trans_proto)

            actions = [parser.OFPActionOutput(mirror_port)]

            if rule_action == 'add':
                self.add_flow(datapath, 1, match, actions)
            elif rule_action == 'delete':
                self.del_flow(datapath, match)

            #self._request_stats(datapath)  # update flow list in data.py
            # self.send_set_config(datapath) # Set switch config request message

    # def send_set_config(self, datapath):
    #     ofp = datapath.ofproto
    #     ofp_parser = datapath.ofproto_parser
    #
    #     req = ofp_parser.OFPSetConfig(datapath, ofp.OFPC_FRAG_NORMAL, 256)
    #     datapath.send_msg(req)


    def _request_stats(self, datapath):
        self.logger.debug('send stats request: %016x', datapath.id)
        # ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        req = parser.OFPFlowStatsRequest(datapath)
        datapath.send_msg(req)


    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        pass

class SimpleFirewallController(ControllerBase):

    def __init__(self, req, link, data, **config):
        super(MirrorControlController, self).__init__(req, link, data, **config)
        self.mirror_control_spp = data[mirror_control_instance_name]

    @route('network_tap', urls.url_set_mirror_port, methods=['PUT'])
    def mirror_rule_protocolport(self, req, **kwargs):
        simple_firewall = self.simple_firewall_spp
        content = req.body
        json_data = json.loads(content)

        rule_action = str(json_data.get('ruleAction'))
        mirror_port = json_data.get('mirrorPort')
        tran_protocol = str(json_data.get('tranProtocol'))


        if tran_protocol == 'TCP':
            protocol = inet.IPPROTO_TCP
        elif tran_protocol == 'UDP':
            protocol = inet.IPPROTO_UDP
        elif tran_protocol == 'ICMP':
            protocol = inet.IPPROTO_ICMP

        mirror_control.add_mirror_rule(rule_action, protocol, tran_port)
