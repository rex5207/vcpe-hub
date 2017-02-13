import json
import time, datetime
from webob import Response
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.app.wsgi import ControllerBase, WSGIApplication, route
from ryu.topology.api import get_switch, get_host
from ryu.ofproto import ofproto_v1_3
from ryu.ofproto import ether, inet
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types

from route import urls
from helper import ofp_helper
from config import forwarding_config, qos_config, service_config
qos_instance_name = 'qos_api_app'


class QosControl(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    _CONTEXTS = {'wsgi': WSGIApplication}

    def __init__(self, *args, **kwargs):
        super(QosControl, self).__init__(*args, **kwargs)
        wsgi = kwargs['wsgi']
        wsgi.register(QosControlController,
                      {qos_instance_name: self})

        self.topology_api_app = self
        self.table_id = service_config.service_sequence['qos']
        self.member_limit_priority = service_config.service_priority['host_rate_limit']
        self.app_limit_priority = service_config.service_priority['app_rate_limit']
        self.goto_table_priority = service_config.service_priority['goto_table']

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # update meter list
        self._request_meter_config_stats(datapath)

        # # Table Miss, forward packet to next table
        # match = parser.OFPMatch()
        # ofp_helper.add_flow_goto_next(datapath, table_id=self.table_id,
        #                               priority=self.goto_table_priority, match=match)

    def rate_limit_for_member(self, mac, bandwidth):
        meter_id = qos_config.meter[str(bandwidth)]
        forwarding_config.member_list.get(mac).meter_id = meter_id
        datapath = forwarding_config.member_list.get(mac).datapath
        out_port = forwarding_config.member_list.get(mac).port
        parser = datapath.ofproto_parser
        actions = [parser.OFPActionOutput(out_port)]
        match = parser.OFPMatch(eth_src=mac)
        ofp_helper.add_flow_rate_limit(datapath=datapath,
                                       table_id=self.table_id,
                                       priority=self.member_limit_priority,
                                       match=match,
                                       meter_id=meter_id,
                                       idle_timeout=10)

    # meter
    def _request_meter_config_stats(self, datapath):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        req = parser.OFPMeterConfigStatsRequest(datapath, 0, ofproto.OFPM_ALL)
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPMeterConfigStatsReply, MAIN_DISPATCHER)
    def _meter_config_stats_reply_handler(self, ev):
        qos_config.meter = {'drop': -1 , 'unlimit': 0}
        body = ev.msg.body
        for stat in body:
            rate = str(stat.bands[0].rate)
            qos_config.meter.update({rate: stat.meter_id})

    def add_meter(self, bandwidth, id):
        switch_list = get_switch(self.topology_api_app, None)
        for switch in switch_list:
            datapath = switch.dp
            parser = datapath.ofproto_parser
            ofp_helper.add_meter(datapath, bandwidth, id)
            self._request_meter_config_stats(datapath)

    def delete_meter(self, bandwidth, id):
        switch_list = get_switch(self.topology_api_app, None)
        for switch in switch_list:
            datapath = switch.dp
            parser = datapath.ofproto_parser
            ofp_helper.delete_meter(datapath, bandwidth, id)
        qos_config.meter.pop(bandwidth)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        if not service_config.service_status['qos']:
            return


class QosControlController(ControllerBase):
    def __init__(self, req, link, data, **config):
        super(QosControlController, self).__init__(req, link, data, **config)
        self.qos_control_spp = data[qos_instance_name]

    @route('qos', urls.get_qos_meter, methods=['GET'])
    def get_qos_meter(self, req, **kwargs):
        body = json.dumps(qos_config.meter)
        return Response(status=200, content_type='application/json', body=body)

    @route('qos', urls.put_qos_meter_add, methods=['PUT'])
    def put_qos_meter_add(self, req, **kwargs):
        qos_control = self.qos_control_spp

        content = req.body
        json_data = json.loads(content)
        bandwidth = int(json_data.get('bandwidth'))
        id = int(json_data.get('id'))

        qos_control.add_meter(bandwidth, id)
        return Response(status=202)

    @route('qos', urls.put_qos_meter_delete, methods=['PUT'])
    def put_qos_meter_delete(self, req, **kwargs):
        qos_control = self.qos_control_spp

        content = req.body
        json_data = json.loads(content)
        bandwidth = int(json_data.get('bandwidth'))
        id = int(json_data.get('id'))

        qos_control.delete_meter(bandwidth, id)
        return Response(status=202)

    @route('qos', urls.get_qos_topology, methods=['GET'])
    def get_qos_topology(self, req, **kwargs):
        qos_control = self.qos_control_spp
        hosts = get_host(qos_control, None)
        body = json.dumps([host.to_dict() for host in hosts])
        return Response(content_type='application/json', body=body)

    @route('flow_data', urls.get_flow_info, methods=['GET'])
    def get_flow_data(self, req, **kwargs):
        dic = []
        for key,value in forwarding_config.flow_list.iteritems():
            flow = {"src_mac": value.src_mac, "dst_mac": value.dst_mac,
                      "src_ip": value.src_ip, "dst_ip": value.dst_ip,
                      "src_port": value.src_port, "dst_port": value.dst_port,
                      "ip_proto": value.ip_proto, "rate": value.rate, "app": value.app}
            dic.append({key: flow})
        body = json.dumps(dic)
        return Response(content_type='application/json', body=body)

    @route('member_data', urls.get_member_info, methods=['GET'])
    def get_member_data(self, req, **kwargs):
        dic = []
        for key,value in forwarding_config.member_list.iteritems():
            member = {"hostname": value.hostname, "ip": value.ip,
                      "mac": value.mac, "datapath": value.datapath.id,
                      "port": value.port, "meter_id": value.meter_id}
            dic.append({key: member})
        body = json.dumps(dic)
        return Response(content_type='application/json', body=body)

    @route('ratelimit_for_member', urls.put_qos_rate_limit_member, methods=['PUT'])
    def set_flow_for_ratelimite_for_member(self, req, **kwargs):
        qos_control = self.qos_control_spp

        mac = str(kwargs['mac'])
        json_data = json.loads(req.body)
        bandwidth = str(json_data.get('bandwidth'))
        qos_control.rate_limit_for_member(mac,bandwidth)
        return Response(status=202)
