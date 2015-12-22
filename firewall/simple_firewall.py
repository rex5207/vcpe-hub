import json
import ryu.app.ofctl.api
# import logging

from ryu.app import simple_switch_13
from webob import Response
# from ryu.controller import ofp_event
# from ryu.controller.handler import CONFIG_DISPATCHER
# from ryu.controller.handler import set_ev_cls
from ryu.app.wsgi import ControllerBase, WSGIApplication, route
from ryu.topology.api import get_switch
# from ryu.lib import dpid as dpid_lib
from ryu.ofproto import ether
from ryu.ofproto import inet

import data

simple_switch_instance_name = 'simple_switch_api_app'
url = '/simpleswitch/mactable/{dpid}'


class SimpleSwitchRest13(simple_switch_13.SimpleSwitch13):

    _CONTEXTS = {'wsgi': WSGIApplication}

    def __init__(self, *args, **kwargs):
        super(SimpleSwitchRest13, self).__init__(*args, **kwargs)
        self.switches = {}
        wsgi = kwargs['wsgi']
        wsgi.register(SimpleSwitchController,
                      {simple_switch_instance_name: self})
        self.topology_api_app = self

    def del_flow(self, datapath, match):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        mod = parser.OFPFlowMod(datapath=datapath,
                                command=ofproto.OFPFC_DELETE,
                                out_port=ofproto.OFPP_ANY,
                                out_group=ofproto.OFPG_ANY,
                                match=match)
        datapath.send_msg(mod)

    def add_block_rule(self, state, src_ip, dst_ip, trans_proto, port):
        switch_list = get_switch(self.topology_api_app, None)
        for switch in switch_list:
            datapath = switch.dp
            parser = datapath.ofproto_parser
            actions = []  # drop

            # initial match field
            match_dict = {'eth_type': ether.ETH_TYPE_IP}

            # fill into the layer3 and layer 4 protocol
            # if port == 0, means block all protocol
            if port > 0:
                if trans_proto == inet.IPPROTO_TCP:
                    match_dict.update({'ip_proto': trans_proto})
                    match_dict.update({'tcp_dst': port})
                else:  # udp
                    match_dict.update({'ip_proto': trans_proto})
                    match_dict.update({'udp_dst': port})

            if len(src_ip) > 0:  # not ''
                match_dict.update({'ipv4_src': src_ip})

            if len(dst_ip) > 0:  # not ''
                match_dict.update({'ipv4_dst': dst_ip})

            match = parser.OFPMatch(**match_dict)
            self.logger.info(match)

            if state == 'on':
                self.add_flow(datapath, 1, match, actions)
            elif state == 'off':  # 'off'
                self.del_flow(datapath, match)


class SimpleSwitchController(ControllerBase):

    def __init__(self, req, link, data, **config):
        super(SimpleSwitchController, self).__init__(req, link, data, **config)
        self.simpl_switch_spp = data[simple_switch_instance_name]

    @route('hello', '/hello/{msg}', methods=['GET'])
    def say_hello(self, req, **kwargs):
        dic = {'message': kwargs['msg']}
        body = json.dumps(dic)
        return Response(content_type='application/json', body=body)

    @route('firewall', '/firewall/acl', methods=['PUT'])
    def block_rule(self, req, **kwargs):
        simple_switch = self.simpl_switch_spp
        content = req.body
        json_data = json.loads(content)

        state = str(json_data.get('state'))
        src_ip = str(json_data.get('srcIP'))
        dst_ip = str(json_data.get('dstIP'))
        protocol = str(json_data.get('protocol'))

        rule = {'state': state}
        rule.update({'src_ip': src_ip})
        rule.update({'dst_ip': dst_ip})
        if protocol == 'HTTP':
            # HTTP -> TCP 80
            rule.update({'trans_proto': inet.IPPROTO_TCP})
            rule.update({'port': 80})
            simple_switch.add_block_rule(**rule)
        elif protocol == 'FTP':
            # FTP -> TCP 20
            rule.update({'trans_proto': inet.IPPROTO_TCP})
            rule.update({'port': 20})
            simple_switch.add_block_rule(**rule)
            # FTP -> TCP 21
            rule.update({'port': 21})
            simple_switch.add_block_rule(**rule)
        elif protocol == 'SSH':
            # SSH -> TCP 22
            rule.update({'trans_proto': inet.IPPROTO_TCP})
            rule.update({'port': 22})
            simple_switch.add_block_rule(**rule)
        elif protocol == 'TELNET':
            # TELNET -> TCP 23
            rule.update({'trans_proto': inet.IPPROTO_TCP})
            rule.update({'port': 23})
            simple_switch.add_block_rule(**rule)
        elif protocol == 'HTTPS':
            # HTTPS -> TCP 443
            rule.update({'trans_proto': inet.IPPROTO_TCP})
            rule.update({'port': 443})
            simple_switch.add_block_rule(**rule)
        elif protocol == 'SMTP':
            # SMTP -> TCP 25
            rule.update({'trans_proto': inet.IPPROTO_TCP})
            rule.update({'port': 25})
            simple_switch.add_block_rule(**rule)
        elif protocol == 'POP3':
            # POP3 -> TCP 110
            rule.update({'trans_proto': inet.IPPROTO_TCP})
            rule.update({'port': 110})
            simple_switch.add_block_rule(**rule)
        elif protocol == 'NTP':
            # NTP -> TCP 123
            rule.update({'port': 123})
            rule.update({'trans_proto': inet.IPPROTO_TCP})
            simple_switch.add_block_rule(**rule)
            # NTP -> UDP 123
            rule.update({'trans_proto': inet.IPPROTO_UDP})
            simple_switch.add_block_rule(**rule)
        elif protocol == 'IMAP':
            # IMAP -> UDP 143
            rule.update({'trans_proto': inet.IPPROTO_TCP})
            rule.update({'port': 143})
            simple_switch.add_block_rule(**rule)
        elif protocol == '':
            # all protocol
            rule.update({'trans_proto': 0})
            rule.update({'port': 0})
            simple_switch.add_block_rule(**rule)

        dic = {}
        body = json.dumps(dic)
        return Response(content_type='application/json', body=body)

    @route('firewall', '/firewall/acl', methods=['GET'])
    def block_test(self, req, **kwargs):
        flowlist = data.blocking_flow
        dic = {'flow': flowlist}
        body = json.dumps(dic)
        return Response(content_type='application/json', body=body)
