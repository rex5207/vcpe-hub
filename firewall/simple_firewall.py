import json

from webob import Response
from ryu.base import app_manager
from ryu.app.wsgi import ControllerBase, WSGIApplication, route
from ryu.topology.api import get_switch
from ryu.ofproto import ether
from ryu.ofproto import inet

import data
from route import urls

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
                                command=ofproto.OFPFC_DELETE,
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
            # self.logger.info(match)

            if rule_action == 'add':
                self.add_flow(datapath, 32768, match, actions)
            elif rule_action == 'delete':  # 'off'
                self.del_flow(datapath, match)


class SimpleFirewallController(ControllerBase):

    def __init__(self, req, link, data, **config):
        super(SimpleFirewallController, self).__init__(req,
                                                       link, data, **config)
        self.simpl_switch_spp = data[simple_firewall_instance_name]

    @route('firewall', urls.url_set_acl_knownport, methods=['PUT'])
    def block_rule(self, req, **kwargs):
        simple_firewall = self.simpl_switch_spp
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
            # all protocol
            rule.update({'port': -1})
            simple_firewall.add_block_rule(**rule)

        return Response(status=202)

    @route('firewall', urls.url_get_acl, methods=['GET'])
    def get_block_list(self, req, **kwargs):
        flowlist = data.blocking_flow
        dic = {'flow': flowlist}
        body = json.dumps(dic)
        return Response(status=200, content_type='application/json', body=body)
