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
from ryu.ofproto import ofproto_v1_3
import pprint

from route import urls
from helper import ofp_helper
from models import firewall_settings

simple_firewall_instance_name = 'simple_firewall_api_app'


class SimpleFirewall(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    _CONTEXTS = {'wsgi': WSGIApplication}

    def __init__(self, *args, **kwargs):
        super(SimpleFirewall, self).__init__(*args, **kwargs)
        self.switches = {}
        wsgi = kwargs['wsgi']
        wsgi.register(SimpleFirewallController,
                      {simple_firewall_instance_name: self})
        self.topology_api_app = self

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

            settings = firewall_settings.load()
            fw_priority = settings['priority']
            if rule_action == 'add':
                ofp_helper.add_flow(datapath, fw_priority, match, actions)
            elif rule_action == 'delete':  # 'off'
                ofp_helper.del_flow(datapath, match, fw_priority)

            self._request_stats(datapath)  # update flow list

    def _request_stats(self, datapath):
        self.logger.debug('send stats request: %016x', datapath.id)
        # ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        req = parser.OFPFlowStatsRequest(datapath)
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def _flow_stats_reply_handler(self, ev):
        settings = firewall_settings.load()
        settings['blocking_rule'] = []

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
                settings['blocking_rule'].append(flow)

        firewall_settings.save(settings)


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

    @route('firewall', urls.url_fw_config_init, methods=['PUT'])
    def set_fw_priority(self, req, **kwargs):
        content = req.body
        save_dict = {}
        save_dict['priority'] = 0
        save_dict['blocking_rule'] = {}

        if firewall_settings.save(save_dict):
            pp = pprint.PrettyPrinter(indent=2)
            pp.pprint(save_dict)
            return Response(status=202)
        else:
            return Response(status=400)

    @route('firewall', urls.url_get_acl, methods=['GET'])
    def get_block_list(self, req, **kwargs):
        settings = firewall_settings.load()
        blocking_rule = settings['blocking_rule']
        dic = {'blocking_rule': blocking_rule}
        body = json.dumps(dic)
        return Response(status=200, content_type='application/json', body=body)
