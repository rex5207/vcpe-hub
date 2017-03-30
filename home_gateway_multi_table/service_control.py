"""
Service Control
Control service enabled or disabled.
"""
import json
from webob import Response
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.app.wsgi import ControllerBase, WSGIApplication, route
from ryu.topology.api import get_switch
from ryu.ofproto import ofproto_v1_3
from ryu.ofproto import ether
from ryu.ofproto import inet
from ryu.lib.packet import packet, dhcp, udp, ipv4, ethernet
from ryu.lib.packet import ether_types

from route import urls
from helper import ofp_helper
from config import service_config

service_control_instance_name = 'service_control_api_app'


class ServiceControl(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    _CONTEXTS = {'wsgi': WSGIApplication}

    def __init__(self, *args, **kwargs):
        super(ServiceControl, self).__init__(*args, **kwargs)
        wsgi = kwargs['wsgi']
        wsgi.register(ServiceControlController,
                      {service_control_instance_name: self})
        self.topology_api_app = self
        self.service_control_priority = service_config.service_priority['service_control']
        self.packet_in_priority = service_config.service_priority['packet_in']
        self.goto_table_priority = service_config.service_priority['goto_table']

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath

        # init service status
        self.init_service(datapath)
        # init_table_miss
        self.init_table_miss(datapath)
        # init packet in flow entry
        self.init_packet_in_table(datapath)

    def init_table_miss(self, datapath):
        switch_list = get_switch(self.topology_api_app, None)
        parser = datapath.ofproto_parser
        match = parser.OFPMatch()
        experiment_action = [parser.OFPActionOutput(3)]
        # outside - inside (Table 0)
        # ofp_helper.add_flow_with_next(datapath, table_id=0,
        #                               priority=self.goto_table_priority, match=match,
        #                               actions=experiment_action, idle_timeout=0)
        ofp_helper.add_flow_goto_next(datapath, 0, self.goto_table_priority, match)
        ofp_helper.add_flow_goto_next(datapath, 1, self.goto_table_priority, match)
        # ofp_helper.add_flow_with_next(datapath, table_id=1,
        #                               priority=self.goto_table_priority, match=match,
        #                               actions=experiment_action, idle_timeout=0)
        ofp_helper.add_flow_goto_next(datapath, 2, self.goto_table_priority, match)
        ofp_helper.add_flow_goto_next(datapath, 3, self.goto_table_priority, match)

        # ofp_helper.add_flow_goto_next(datapath, 4, self.goto_table_priority, match)

    def init_service(self, datapath):
        service_status = service_config.service_status
        parser = datapath.ofproto_parser
        match = parser.OFPMatch()
        # ofp_helper.add_flow_goto_next(datapath, 0, self.service_control_priority, match)
        # ofp_helper.add_flow_goto_next(datapath, 1, self.service_control_priority, match)
        # ofp_helper.add_flow_goto_next(datapath, 2, self.service_control_priority, match)
        # ofp_helper.add_flow_goto_next(datapath, 4, self.service_control_priority, match)

    def init_packet_in_table(self, datapath):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        ofp_helper.add_flow(datapath, table_id=service_config.service_sequence['nat_egress'],
                            priority=self.packet_in_priority, match=match,
                            actions=actions, idle_timeout=0)

    def update_packet_in_table(self):
        service_status = service_config.service_status
        service_sequence = service_config.service_sequence
        old_packet_in = service_sequence['packet_in']
        if old_packet_in == service_sequence['forwarding'] and service_status['nat']:
            service_sequence['packet_in'] = service_sequence['nat_egress']
            self.add_packet_in_flow(service_sequence['packet_in'])
            self.delete_packet_in_flow(old_packet_in)
        elif old_packet_in == service_sequence['nat_egress'] and not service_status['nat']:
            service_sequence['packet_in'] = service_sequence['forwarding']
            self.add_packet_in_flow(service_sequence['packet_in'])
            self.delete_packet_in_flow(old_packet_in)
        else:
            pass

    def add_packet_in_flow(self, apply_table_id):
        switch_list = get_switch(self.topology_api_app, None)
        for switch in switch_list:
            datapath = switch.dp
            parser = datapath.ofproto_parser
            ofproto = datapath.ofproto
            match = parser.OFPMatch()
            actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                              ofproto.OFPCML_NO_BUFFER)]
            ofp_helper.add_flow(datapath, table_id=apply_table_id,
                                priority=self.packet_in_priority, match=match,
                                actions=actions, idle_timeout=0)

    def delete_packet_in_flow(self, apply_table_id):
        switch_list = get_switch(self.topology_api_app, None)
        for switch in switch_list:
            datapath = switch.dp
            parser = datapath.ofproto_parser
            match = parser.OFPMatch()
            ofp_helper.del_flow(datapath, table_id=apply_table_id,
                                priority=self.packet_in_priority, match=match)

    def add_dhcp_flow(self):
        switch_list = get_switch(self.topology_api_app, None)
        for switch in switch_list:
            datapath = switch.dp
            parser = datapath.ofproto_parser
            ofproto = datapath.ofproto
            match_dhcp_request = parser.OFPMatch(eth_type=ether.ETH_TYPE_IP,
                                                 ip_proto=inet.IPPROTO_UDP,
                                                 udp_src=68, udp_dst=67)
            actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                              ofproto.OFPCML_NO_BUFFER)]
            ofp_helper.add_flow(datapath,
                                table_id=service_config.service_sequence['nat_egress'],
                                priority=service_config.service_priority['dhcp'],
                                match=match_dhcp_request,
                                actions=actions, idle_timeout=0)

    def del_dhcp_flow(self):
        switch_list = get_switch(self.topology_api_app, None)
        for switch in switch_list:
            datapath = switch.dp
            parser = datapath.ofproto_parser
            match_dhcp_request = parser.OFPMatch(eth_type=ether.ETH_TYPE_IP,
                                                 ip_proto=inet.IPPROTO_UDP,
                                                 udp_src=68, udp_dst=67)
        ofp_helper.del_flow(datapath,
                            table_id=service_config.service_sequence['nat_egress'],
                            priority=service_config.service_priority['dhcp'],
                            match=match_dhcp_request)

    def add_passby_flow(self, apply_table_id):
        switch_list = get_switch(self.topology_api_app, None)
        for switch in switch_list:
            datapath = switch.dp
            parser = datapath.ofproto_parser
            match = parser.OFPMatch()
            ofp_helper.add_flow_goto_next(datapath, apply_table_id,
                                          self.service_control_priority, match)

    def delete_passby_flow(self, apply_table_id):
        switch_list = get_switch(self.topology_api_app, None)
        for switch in switch_list:
            datapath = switch.dp
            parser = datapath.ofproto_parser
            match = parser.OFPMatch()
            ofp_helper.del_flow(datapath, apply_table_id, self.service_control_priority, match)

    def enable_service(self, service_name):
        if service_name == 'nat':
            self.delete_passby_flow(service_config.service_sequence['nat_egress'])
            self.delete_passby_flow(service_config.service_sequence['nat_ingress'])
        elif service_name == 'dhcp':
            self.add_dhcp_flow()
        else:
            self.delete_passby_flow(service_config.service_sequence[service_name])

        service_config.service_status[service_name] = True

    def disable_service(self, service_name):
        if service_name == 'nat':
            self.add_passby_flow(service_config.service_sequence['nat_egress'])
            self.add_passby_flow(service_config.service_sequence['nat_ingress'])
        elif service_name == 'dhcp':
            self.del_dhcp_flow()
        else:
            print 'disble ' + service_name
            self.add_passby_flow(service_config.service_sequence[service_name])
        service_config.service_status[service_name] = False


class ServiceControlController(ControllerBase):
    def __init__(self, req, link, data, **config):
        super(ServiceControlController, self).__init__(req,
                                                       link, data, **config)
        self.service_control_spp = data[service_control_instance_name]

    # GET '/service-control/sequence'
    @route('service-control', urls.get_sc_sequence, methods=['GET'])
    def get_sc_sequence(self, req, **kwargs):
        dic = service_config.service_sequence
        body = json.dumps(dic)
        return Response(status=200, content_type='application/json', body=body)

    # GET '/service-control/priority'
    @route('service-control', urls.get_sc_priority, methods=['GET'])
    def get_sc_priority(self, req, **kwargs):
        dic = service_config.service_priority
        body = json.dumps(dic)
        return Response(status=200, content_type='application/json', body=body)

    # GET '/service-control/status'
    @route('service-control', urls.get_sc_status, methods=['GET'])
    def get_sc_status(self, req, **kwargs):
        dic = service_config.service_status
        body = json.dumps(dic)
        return Response(status=200, content_type='application/json', body=body)

    # PUT '/service-control/enable'
    @route('service-control', urls.put_service_enable, methods=['PUT'])
    def put_service_enable(self, req, **kwargs):
        service_control = self.service_control_spp
        content = req.body
        json_data = json.loads(content)
        service_name = str(json_data.get('service_name'))

        service_control.enable_service(service_name)
        service_control.update_packet_in_table()
        return Response(status=202, content_type='application/json')

    # PUT '/service-control/disable'
    @route('service-control', urls.put_service_disable, methods=['PUT'])
    def put_service_disable(self, req, **kwargs):
        service_control = self.service_control_spp
        content = req.body
        json_data = json.loads(content)
        service_name = str(json_data.get('service_name'))

        service_control.disable_service(service_name)
        service_control.update_packet_in_table()
        return Response(status=202, content_type='application/json')
