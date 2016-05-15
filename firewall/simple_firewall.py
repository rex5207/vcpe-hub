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

import block_data
from route import urls
from config import settings

simple_firewall_instance_name = 'simple_firewall_api_app'


class SimpleFirewall(app_manager.RyuApp):

    _CONTEXTS = {'wsgi': WSGIApplication}

    def __init__(self, *args, **kwargs):
        super(SimpleFirewall, self).__init__(*args, **kwargs)
        self.switches = {}
        wsgi = kwargs['wsgi']
        wsgi.register(SimpleFirewallController,
                      {simple_firewall_instance_name: self})
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

    def add_block_rule(self, rule_action, src_ip, dst_ip, trans_proto, port):
        switch_list = get_switch(self.topology_api_app, None)
        for switch in switch_list:
            datapath = switch.dp
            parser = datapath.ofproto_parser
            actions = []  # drop

            # initial match field
            match_dict = {'eth_type': ether.ETH_TYPE_IP}

            # fill into the layer3 and layer 4 protocol
            # if port == 0, means block all protocol
            if port >= 0:
                if trans_proto == inet.IPPROTO_TCP:
                    match_dict.update({'ip_proto': trans_proto,
                                       'tcp_dst': port})
                else:  # udp
                    match_dict.update({'ip_proto': trans_proto,
                                       'udp_dst': port})

            if len(src_ip) > 0:  # not ''
                match_dict.update({'ipv4_src': src_ip})

            if len(dst_ip) > 0:  # not ''
                match_dict.update({'ipv4_dst': dst_ip})

            match = parser.OFPMatch(**match_dict)
            fw_priority = settings.firewall_priority
            if rule_action == 'add':
                self.add_flow(datapath, fw_priority, match, actions)
            elif rule_action == 'delete':  # 'off'
                self.del_flow(datapath, match)

            self._request_stats(datapath)  # update flow list in data.py

    def _request_stats(self, datapath):
        self.logger.debug('send stats request: %016x', datapath.id)
        # ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        req = parser.OFPFlowStatsRequest(datapath)
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def _flow_stats_reply_handler(self, ev):
        block_data.blocking_flow = []
        body = ev.msg.body
        for stat in body:
            flow = {}
            if (stat.instructions == []):
                flow.update({'srcIP': stat.match.get('ipv4_src')})
                flow.update({'dstIP': stat.match.get('ipv4_dst')})
                if (stat.match.get('ip_proto') == inet.IPPROTO_TCP):
                    flow.update({'tranPort': stat.match.get('tcp_dst')})
                    flow.update({'tranProtocol': 'TCP'})
                elif (stat.match.get('ip_proto') == inet.IPPROTO_UDP):
                    flow.update({'tranPort': stat.match.get('udp_dst')})
                    flow.update({'tranProtocol': 'UDP'})
                else:
                    flow.update({'tranPort': ''})
                    flow.update({'tranProtocol': ''})
                block_data.blocking_flow.append(flow)


class SimpleFirewallController(ControllerBase):

    def __init__(self, req, link, data, **config):
        super(SimpleFirewallController, self).__init__(req,
                                                       link, data, **config)
        self.simple_firewall_spp = data[simple_firewall_instance_name]

    @route('firewall', urls.url_set_acl_knownport, methods=['PUT'])
    def block_rule_knownport(self, req, **kwargs):
        simple_firewall = self.simple_firewall_spp
        content = req.body
        json_data = json.loads(content)

        rule_action = str(json_data.get('ruleAction'))
        src_ip = str(json_data.get('srcIP'))
        dst_ip = str(json_data.get('dstIP'))
        protocol = str(json_data.get('protocol'))

        rule = {'rule_action': rule_action}
        rule.update({'src_ip': src_ip, 'dst_ip': dst_ip})
        if protocol == 'HTTP':
            # HTTP -> TCP 80
            rule.update({'trans_proto': inet.IPPROTO_TCP, 'port': 80})
            simple_firewall.add_block_rule(**rule)
        elif protocol == 'FTP':
            # FTP -> TCP 20
            rule.update({'trans_proto': inet.IPPROTO_TCP, 'port': 20})
            simple_firewall.add_block_rule(**rule)
            # FTP -> TCP 21
            rule.update({'port': 21})
            simple_firewall.add_block_rule(**rule)
        elif protocol == 'SSH':
            # SSH -> TCP 22
            rule.update({'trans_proto': inet.IPPROTO_TCP, 'port': 22})
            simple_firewall.add_block_rule(**rule)
        elif protocol == 'TELNET':
            # TELNET -> TCP 23
            rule.update({'trans_proto': inet.IPPROTO_TCP, 'port': 23})
            simple_firewall.add_block_rule(**rule)
        elif protocol == 'HTTPS':
            # HTTPS -> TCP 443
            rule.update({'trans_proto': inet.IPPROTO_TCP, 'port': 443})
            simple_firewall.add_block_rule(**rule)
        elif protocol == 'SMTP':
            # SMTP -> TCP 25
            rule.update({'trans_proto': inet.IPPROTO_TCP, 'port': 25})
            simple_firewall.add_block_rule(**rule)
        elif protocol == 'POP3':
            # POP3 -> TCP 110
            rule.update({'trans_proto': inet.IPPROTO_TCP, 'port': 110})
            simple_firewall.add_block_rule(**rule)
        elif protocol == 'NTP':
            # NTP -> TCP 123
            rule.update({'trans_proto': inet.IPPROTO_TCP, 'port': 123})
            simple_firewall.add_block_rule(**rule)
            # NTP -> UDP 123
            rule.update({'trans_proto': inet.IPPROTO_UDP})
            simple_firewall.add_block_rule(**rule)
        elif protocol == 'IMAP':
            # IMAP -> UDP 143
            rule.update({'trans_proto': inet.IPPROTO_TCP, 'port': 143})
            simple_firewall.add_block_rule(**rule)
        elif protocol == '':
            # all protocol, these two attr are don't care
            rule.update({'trans_proto': -1, 'port': -1})
            simple_firewall.add_block_rule(**rule)

        return Response(status=202)

    @route('firewall', urls.url_set_acl_customport, methods=['PUT'])
    def block_rule_customport(self, req, **kwargs):
        simple_firewall = self.simple_firewall_spp
        content = req.body
        json_data = json.loads(content)

        rule_action = str(json_data.get('ruleAction'))
        src_ip = str(json_data.get('srcIP'))
        dst_ip = str(json_data.get('dstIP'))
        tran_port = json_data.get('tranPort')
        tran_protocol = str(json_data.get('tranProtocol'))

        if tran_port < 0:
            return Response(status=400)

        if tran_protocol == 'TCP':
            protocol = inet.IPPROTO_TCP
        elif (tran_protocol == 'UDP'):
            protocol = inet.IPPROTO_UDP
        else:
            # let the block function know this two attr are don't care
            protocol = -1
            tran_port = -1

        simple_firewall.add_block_rule(rule_action, src_ip, dst_ip,
                                       protocol, tran_port)
        return Response(status=202)

    @route('firewall', urls.url_get_acl, methods=['GET'])
    def get_block_list(self, req, **kwargs):
        flowlist = block_data.blocking_flow
        dic = {'flow': flowlist}
        body = json.dumps(dic)
        return Response(status=200, content_type='application/json', body=body)
