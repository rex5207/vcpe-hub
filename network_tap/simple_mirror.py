# Copyright (C) 2011 Nippon Telegraph and Telephone Corporation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import json

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types
from ryu.lib.packet import ipv4
from ryu.lib.packet import tcp
from ryu.lib.packet import udp
from ryu.lib.packet import icmp
from ryu.topology.api import get_switch, get_host, get_link
from webob import Response
from ryu.app.wsgi import ControllerBase, WSGIApplication, route
from ryu.ofproto import ether
from ryu.ofproto import inet
import ryu.app.ofctl.api

import mirror_data
from route import urls

simple_mirror_instance_name = 'simple_mirror_api_app'

class SimpleMirror(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    _CONTEXTS = {'wsgi': WSGIApplication}

    def __init__(self, *args, **kwargs):
        super(SimpleMirror, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        mirror_data.mirror_table = []

        wsgi = kwargs['wsgi']
        wsgi.register(MirrorControlController,
                      {simple_mirror_instance_name: self})
        self.topology_api_app = self
        self.IDLE_TIME = 100

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        match = parser.OFPMatch()

        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions, idle_timeout = 0)



    def add_flow(self, datapath, priority, match, actions, idle_timeout=0, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]
        if buffer_id:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                    priority=priority, match=match,
                                    instructions=inst, idle_timeout=idle_timeout)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, instructions=inst,
                                    idle_timeout=idle_timeout)
        datapath.send_msg(mod)

    def del_flow(self, datapath, match, priority):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        mod = parser.OFPFlowMod(datapath=datapath,
                                command=ofproto.OFPFC_DELETE_STRICT,
                                out_port=ofproto.OFPP_ANY,
                                out_group=ofproto.OFPG_ANY,
                                priority=priority,
                                match=match)
        datapath.send_msg(mod)

    def add_mirror_rule(self, rule_action, mirror_port, host_port):
        switch_list = get_switch(self.topology_api_app, None)
        for switch in switch_list:
            datapath = switch.dp
            parser = datapath.ofproto_parser

            if rule_action == 'add':
                #add mirror flow by host port
                for i in range(len(mirror_data.mirror_table)):
                    if host_port == mirror_data.mirror_table[i]['out_port']:
                        match_del = parser.OFPMatch(eth_dst=mirror_data.mirror_table[i]['dst'])
                        self.del_flow(datapath, match_del, mirror_data.mirror_table[i]['priority'])
                        mirror_data.mirror_table[i]['mirror_port'] = mirror_port
                        mirror_data.mirror_table[i]['priority'] = 100
                        match_add = parser.OFPMatch(eth_dst=mirror_data.mirror_table[i]['dst'])
                        actions = [parser.OFPActionOutput(mirror_data.mirror_table[i]['out_port']), parser.OFPActionOutput(mirror_data.mirror_table[i]['mirror_port'])]
                        self.add_flow(datapath, mirror_data.mirror_table[i]['priority'], match_add, actions, idle_timeout = 0) #refresh mirror get higher priority

            elif rule_action == 'delete':
                for i in range(len(mirror_data.mirror_table)):
                    if host_port == mirror_data.mirror_table[i]['out_port']:
                        match_del = parser.OFPMatch(eth_dst=mirror_data.mirror_table[i]['dst'])
                        self.del_flow(datapath, match_del, mirror_data.mirror_table[i]['priority'])
                        mirror_data.mirror_table[i]['mirror_port'] = mirror_data.default_mirror_port
                        mirror_data.mirror_table[i]['priority'] = 1
                        match_add = parser.OFPMatch(eth_dst=mirror_data.mirror_table[i]['dst'])
                        actions = [parser.OFPActionOutput(mirror_data.mirror_table[i]['out_port']), parser.OFPActionOutput(mirror_data.mirror_table[i]['mirror_port'])]
                        self.add_flow(datapath, mirror_data.mirror_table[i]['priority'], match_add, actions, idle_timeout = 0) #refresh mirror get higher priority

            self._request_stats(datapath)  # update flow list in data.py
            #self.send_set_config(datapath) # Set switch config request message

    def _request_stats(self, datapath):
        self.logger.debug('send stats request: %016x', datapath.id)
        # ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        req = parser.OFPFlowStatsRequest(datapath)
        datapath.send_msg(req)

    def send_set_config(self, datapath):
        ofp = datapath.ofproto
        ofp_parser = datapath.ofproto_parser

        req = ofp_parser.OFPSetConfig(datapath, ofp.OFPC_FRAG_NORMAL, 256)
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']


        if in_port == mirror_data.default_mirror_port:
            return

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        dst = eth.dst
        src = eth.src

        dpid = datapath.id
        self.mac_to_port.setdefault(dpid, {})

        # learn a mac address to avoid FLOOD next time.
        self.mac_to_port[dpid][src] = in_port

        #add the src to table
        flag = False #avoid add rule again (src)
        for data in mirror_data.mirror_table:
            if src in data['dst']:
                flag = True
                break
        if flag == False:
            if in_port != mirror_data.default_DataPlane_port:
                mirror_rule = {}
                mirror_rule.update({'dst':src, 'out_port':in_port, 'mirror_port':mirror_data.default_mirror_port, 'priority': 1})
                mirror_data.mirror_table.append(mirror_rule)
                match_src = parser.OFPMatch(eth_dst=src)
                actions_src = [parser.OFPActionOutput(in_port), parser.OFPActionOutput(mirror_data.default_mirror_port)]
                self.add_flow(datapath, 1, match_src, actions_src, idle_timeout = 0)
            else: # data out port -> add flow but don't add the mirror data
                match_src = parser.OFPMatch(eth_dst=src)
                actions_src = [parser.OFPActionOutput(in_port), parser.OFPActionOutput(mirror_data.default_mirror_port)]
                self.add_flow(datapath, 1, match_src, actions_src, idle_timeout = self.IDLE_TIME)

        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
            #add the dst to table
            if out_port != mirror_data.default_DataPlane_port:
                mirror_rule = {}
                mirror_rule.update({'dst':dst, 'out_port':out_port, 'mirror_port':mirror_data.default_mirror_port, 'priority': 1})
                mirror_data.mirror_table.append(mirror_rule)
            actions = [parser.OFPActionOutput(out_port), parser.OFPActionOutput(mirror_data.default_mirror_port)]

        else:
            out_port = ofproto.OFPP_FLOOD
            actions = [parser.OFPActionOutput(out_port)]

        # install a flow to avoid packet_in next time
        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(eth_dst=dst) #just use dst to set flow
            self.add_flow(datapath, 1, match, actions, idle_timeout = 0)

        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)

class MirrorControlController(ControllerBase):

    def __init__(self, req, link, data, **config):
        super(MirrorControlController, self).__init__(req, link, data, **config)
        self.simple_mirror_spp = data[simple_mirror_instance_name]

    @route('network_tap', urls.url_set_mirror_port, methods=['PUT'])
    def mirror_rule_hostMirror(self, req, **kwargs):
        simple_mirror = self.simple_mirror_spp
        content = req.body
        json_data = json.loads(content)

        rule_action = str(json_data.get('ruleAction'))
        mirror_port = int(json_data.get('mirrorPort'))
        host_port = int(json_data.get('hostPort'))

        simple_mirror.add_mirror_rule(rule_action, mirror_port, host_port)

    @route('network_tap', urls.url_get_mirror_list, methods=['GET'])
    def get_mirror_list(self, req, **kwargs):
        dic = {'Mirror_rule': mirror_data.mirror_table}
        body = json.dumps(dic)
        return Response(status=200, content_type='application/json', body=body)
