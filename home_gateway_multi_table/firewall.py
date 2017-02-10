"""
 Simple Firewall
"""
import json
from webob import Response
from ryu.base import app_manager
from ryu.app.wsgi import ControllerBase, WSGIApplication, route
from ryu.topology.api import get_switch
from ryu.ofproto import ether
from ryu.ofproto import inet
from ryu.controller import ofp_event
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER

from config import service_config, firewall_config
from helper import ofp_helper
from route import urls


simple_firewall_instance_name = 'simple_firewall_api_app'


class SimpleFirewall(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    _CONTEXTS = {'wsgi': WSGIApplication}

    def __init__(self, *args, **kwargs):
        super(SimpleFirewall, self).__init__(*args, **kwargs)
        wsgi = kwargs['wsgi']
        wsgi.register(SimpleFirewallController,
                      {simple_firewall_instance_name: self})
        self.topology_api_app = self
        self.switches = {}
        self.table_id = service_config.service_sequence['firewall']
        self.service_priority = service_config.service_priority['firewall']
        self.goto_table_priority = service_config.service_priority['goto_table']

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # update flow list
        self._request_flow_stats(datapath)

        # Table miss flow, if not match firewall rule, go to next table
        # Otherwise, drop it
        # match = parser.OFPMatch()
        # ofp_helper.add_flow_goto_next(datapath, table_id=self.table_id,
        #                               priority=self.goto_table_priority, match=match)

    def _request_flow_stats(self, datapath):
        # to get firewall rules
        parser = datapath.ofproto_parser
        req = parser.OFPFlowStatsRequest(datapath)
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def _flow_stats_reply_handler(self, ev):
        firewall_config.rules = []

        body = ev.msg.body
        for stat in body:
            if stat.table_id == self.table_id and stat.instructions == []:
                # get drop rules in firewall service table
                flow = {}
                flow.update({'src_ip': stat.match.get('ipv4_src')})
                flow.update({'dst_ip': stat.match.get('ipv4_dst')})
                if stat.match.get('ip_proto') == inet.IPPROTO_TCP:
                    flow.update({'port': stat.match.get('tcp_dst')})
                    flow.update({'ip_proto': 'TCP'})
                elif stat.match.get('ip_proto') == inet.IPPROTO_UDP:
                    flow.update({'port': stat.match.get('udp_dst')})
                    flow.update({'ip_proto': 'UDP'})
                else:
                    flow.update({'port': ''})
                    flow.update({'ip_proto': ''})
                firewall_config.rules.append(flow)

    def match_mapping(self, src_ip, dst_ip, ip_proto, port):
        # initial match field
        match_dict = {'eth_type': ether.ETH_TYPE_IP}

        # fill into the layer3 and layer 4 protocol
        # if port == 0, means block all protocol
        if port >= 0:
            if ip_proto == inet.IPPROTO_TCP:
                match_dict.update({'ip_proto': ip_proto,
                                   'tcp_dst': port})
            else:  # udp
                match_dict.update({'ip_proto': ip_proto,
                                   'udp_dst': port})

        if len(src_ip) > 0:  # not ''
            match_dict.update({'ipv4_src': src_ip})

        if len(dst_ip) > 0:  # not ''
            match_dict.update({'ipv4_dst': dst_ip})

        return match_dict

    def add_firewall_rule(self, src_ip, dst_ip, ip_proto, port):
        switch_list = get_switch(self.topology_api_app, None)
        for switch in switch_list:
            datapath = switch.dp
            parser = datapath.ofproto_parser
            ofproto = datapath.ofproto
            match_mapping = self.match_mapping(src_ip, dst_ip, ip_proto, port)
            match = parser.OFPMatch(**match_mapping)

            actions = []  # drop
            ofp_helper.add_flow(datapath, table_id=self.table_id,
                                priority=self.service_priority, match=match,
                                actions=actions)
            self._request_flow_stats(datapath)  # update flow list

    def delete_firewall_rule(self, src_ip, dst_ip, ip_proto, port):
        switch_list = get_switch(self.topology_api_app, None)
        for switch in switch_list:
            datapath = switch.dp
            parser = datapath.ofproto_parser
            ofproto = datapath.ofproto
            match_mapping = self.match_mapping(src_ip, dst_ip, ip_proto, port)
            match = parser.OFPMatch(**match_mapping)

            actions = []  # drop
            ofp_helper.del_flow(datapath, table_id=self.table_id,
                                priority=self.service_priority, match=match)

            self._request_flow_stats(datapath)  # update flow list


class SimpleFirewallController(ControllerBase):
    def __init__(self, req, link, data, **config):
        super(SimpleFirewallController, self).__init__(req,
                                                       link, data, **config)
        self.simple_firewall_spp = data[simple_firewall_instance_name]

    @route('firewall', urls.get_fw_rules, methods=['GET'])
    def get_fw_rules(self, req, **kwargs):
        dic = {'rules': firewall_config.rules}
        body = json.dumps(dic)
        return Response(status=200, content_type='application/json', body=body)

    @route('firewall', urls.put_fw_knownport_add, methods=['PUT'])
    def put_fw_knownport_add(self, req, **kwargs):
        simple_firewall = self.simple_firewall_spp
        content = req.body
        json_data = json.loads(content)

        src_ip = str(json_data.get('src_ip'))
        dst_ip = str(json_data.get('dst_ip'))
        protocol = str(json_data.get('protocol'))

        if src_ip == '' and dst_ip == '' and protocol == '':
            return Response(status=400)

        rules = self.known_port_mapping(protocol)
        if len(rules) == 0:
            return Response(status=400)

        for rule in rules:
            simple_firewall.add_firewall_rule(src_ip, dst_ip, rule['ip_proto'], rule['port'])

        return Response(status=202)

    @route('firewall', urls.put_fw_knownport_delete, methods=['PUT'])
    def put_fw_knownport_delete(self, req, **kwargs):
        simple_firewall = self.simple_firewall_spp
        content = req.body
        json_data = json.loads(content)

        src_ip = str(json_data.get('src_ip'))
        dst_ip = str(json_data.get('dst_ip'))
        protocol = str(json_data.get('protocol'))

        if src_ip == '' and dst_ip == '' and protocol == '':
            return Response(status=400)

        rules = self.known_port_mapping(protocol)
        if len(rules) == 0:
            return Response(status=400)

        for rule in rules:
            simple_firewall.delete_firewall_rule(src_ip, dst_ip, rule['ip_proto'], rule['port'])

        return Response(status=202)

    @route('firewall', urls.put_fw_customport_add, methods=['PUT'])
    def put_fw_customport_add(self, req, **kwargs):
        simple_firewall = self.simple_firewall_spp
        content = req.body
        json_data = json.loads(content)

        src_ip = str(json_data.get('src_ip'))
        dst_ip = str(json_data.get('dst_ip'))
        ip_proto = str(json_data.get('ip_proto'))
        port = json_data.get('port')

        if ip_proto == 'TCP':
            simple_firewall.add_firewall_rule(src_ip, dst_ip, inet.IPPROTO_TCP, port)
        elif ip_proto == 'UDP':
            simple_firewall.add_firewall_rule(src_ip, dst_ip, inet.IPPROTO_UDP, port)
        else:
            # let the block function know last two attr are don't care
            simple_firewall.add_firewall_rule(src_ip, dst_ip, -1, -1)

        return Response(status=202)

    @route('firewall', urls.put_fw_customport_delete, methods=['PUT'])
    def put_fw_customport_delete(self, req, **kwargs):
        simple_firewall = self.simple_firewall_spp
        content = req.body
        json_data = json.loads(content)

        src_ip = str(json_data.get('src_ip'))
        dst_ip = str(json_data.get('dst_ip'))
        ip_proto = str(json_data.get('ip_proto'))
        port = json_data.get('port')

        if src_ip == '' and dst_ip == '' and ip_proto == '':
            return Response(status=400)

        if (port and ip_proto == '') or port < 0:
            return Response(status=400)

        if ip_proto == 'TCP':
            simple_firewall.delete_firewall_rule(src_ip, dst_ip, inet.IPPROTO_TCP, port)
        elif (ip_proto == 'UDP'):
            simple_firewall.delete_firewall_rule(src_ip, dst_ip, inet.IPPROTO_UDP, port)
        else:
            # let the block function know this two attr are don't care
            simple_firewall.delete_firewall_rule(src_ip, dst_ip, -1, -1)

        return Response(status=202)

    def known_port_mapping(self, protocol):
        result = []
        if protocol == 'HTTP':
            # HTTP -> TCP 80
            result.append({'ip_proto': inet.IPPROTO_TCP, 'port': 80})
        elif protocol == 'FTP':
            # FTP -> TCP 20, 21
            result.append({'ip_proto': inet.IPPROTO_TCP, 'port': 20})
            result.append({'ip_proto': inet.IPPROTO_TCP, 'port': 21})
        elif protocol == 'SSH':
            # SSH -> TCP 22
            result.append({'ip_proto': inet.IPPROTO_TCP, 'port': 22})
        elif protocol == 'TELNET':
            # TELNET -> TCP 23
            result.append({'ip_proto': inet.IPPROTO_TCP, 'port': 23})
        elif protocol == 'HTTPS':
            # HTTPS -> TCP 443
            result.append({'ip_proto': inet.IPPROTO_TCP, 'port': 443})
        elif protocol == 'SMTP':
            # SMTP -> TCP 25
            result.append({'ip_proto': inet.IPPROTO_TCP, 'port': 25})
        elif protocol == 'POP3':
            # POP3 -> TCP 110
            result.append({'ip_proto': inet.IPPROTO_TCP, 'port': 110})
        elif protocol == 'NTP':
            # NTP -> TCP 123, UDP 123
            result.append({'ip_proto': inet.IPPROTO_TCP, 'port': 123})
            result.append({'ip_proto': inet.IPPROTO_UDP, 'port': 123})
        elif protocol == 'IMAP':
            # IMAP -> UDP 143
            result.append({'ip_proto': inet.IPPROTO_TCP, 'port': 143})
        elif protocol == '':
            # all protocol for certain src ip or dst ip,
            # these two attr are don't care
            result.append({'ip_proto': -1, 'port': -1})
        else:
            pass

        return result
