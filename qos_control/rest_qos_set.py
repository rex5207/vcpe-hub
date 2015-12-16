"""Project for Rest API (Group Setting)."""
import json

from ryu.base import app_manager
from ryu.app.wsgi import ControllerBase, WSGIApplication, route
from webob import Response
from ryu.topology.api import get_switch

from qos_control import Qos_UpdateEvent
from setting.db import data_collection
from setting.ratelimitation.setting import setup
from setting.flowclassification.record import statistic
from setting.utils import ofputils

from route import urls

set_qos_info_instance_name = 'set_qos_info_api_app'

class QosSetup(app_manager.RyuApp):
    _EVENTS = [Qos_UpdateEvent]
    _CONTEXTS = {'wsgi': WSGIApplication}

    def __init__(self, *args, **kwargs):
        """Initial Setting method."""
        super(QosSetup, self).__init__(*args, **kwargs)
        self.topology_api_app = self
        wsgi = kwargs['wsgi']
        wsgi.register(QosSetupRest,
                      {set_qos_info_instance_name: self})
        data_collection.meter_list.update({"drop": "-1"})

    def set_ratelimite_for_app(self, appname, meter_id, group_id, state):
        """Set rate control for applications."""
        if setup.ratelimite_setup_for_specialcase.get(group_id) is not None:
            appset = setup.ratelimite_setup_for_specialcase.get(group_id)
            appset.update({appname: {'state': state, 'meter_id': int(meter_id)}})
        else:
            setup.ratelimite_setup_for_specialcase.update({group_id: {appname: {'state': state, 'meter_id': int(meter_id)}}})
        ev = Qos_UpdateEvent('Update qos for flow')
        self.send_event_to_observers(ev)

    def set_ratelimite_for_mac(self, mac, meter_id, group_id, state):
        """Set rate control for applications."""
        if setup.ratelimite_setup_for_specialcase.get(group_id) is not None:
            memberset = setup.ratelimite_setup_for_specialcase_member.get(group_id)
            memberset.update({mac: {'state': state, 'meter_id': int(meter_id)}})
        else:
            setup.ratelimite_setup_for_specialcase_member.update({group_id: {mac: {'state': state, 'meter_id': int(meter_id)}}})

        ev = Qos_UpdateEvent('Update qos for flow')
        self.send_event_to_observers(ev)

    def set_meter_to_switches(self, meterid, bandwdith, command):
        """Save Member data to database method."""
        switch_list = get_switch(self.topology_api_app, None)
        for dp in switch_list:
            print dp.dp.id, type(meterid), type(bandwdith), int(bandwdith), int(meterid)
            ofputils.set_meter_entry(dp.dp, int(bandwdith), int(meterid), command)

        if command == 'ADD':
            data_collection.meter_list.update({bandwdith: meterid})
        elif command == 'DELETE':
            data_collection.meter_list.pop(bandwdith)

# curl -X PUT http://127.0.0.1:8080/set_qos_info/2
class QosSetupRest(ControllerBase):

    def __init__(self, req, link, data, **config):
        """Initial Setting method."""
        super(QosSetupRest, self).__init__(req, link, data, **config)
        self.get_qos_info = data[set_qos_info_instance_name]

    @route('qos_data', urls.url_qos_app_list_get, methods=['GET'])
    def get_app_list(self, req, **kwargs):
        app_list = statistic.database_app_record.keys()
        dic = {}
        for key in app_list:
            dic.update({key: statistic.database_app_record[key].rate})
        body = json.dumps(dic)
        return Response(content_type='application/json', body=body)

    @route('qos_data', urls.url_qos_meter_list_get, methods=['GET'])
    def get_meter_list(self, req, **kwargs):
        meter_list = data_collection.meter_list.keys()
        dic = {}
        for key in meter_list:
            dic.update({key: data_collection.meter_list.get(key)})
        body = json.dumps(dic)
        return Response(content_type='application/json', body=body)

    @route('flow_data', urls.url_flow, methods=['GET'])
    def get_flow_data(self, req, **kwargs):
        """Get Flow data method."""
        dic = {}
        for key in data_collection.flow_list:
            flow_c = data_collection.flow_list[key]
            if flow_c.counter < 3 and flow_c.app == 'Others':
                continue
            else:
                list_f = {"src_mac": flow_c.src_mac, "dst_mac": flow_c.dst_mac,
                          "src_ip": flow_c.src_ip, "dst_ip": flow_c.dst_ip,
                          "src_port": flow_c.src_port, "dst_port": flow_c.dst_port,
                          "ip_proto": flow_c.ip_proto, "rate": flow_c.rate, "app": flow_c.app}

                dic.update({key: list_f})
        body = json.dumps(dic)
        return Response(content_type='application/json', body=body)

    @route('rate_for_app', urls.url_flow_app, methods=['PUT'])
    def set_flow_for_ratelimite_in_app(self, req, **kwargs):
        app = str(kwargs['appname'])
        content = req.body
        json_link = json.loads(content)
        meter_id = str(json_link.get('meter_id'))
        group_id = str(json_link.get('group_id'))
        state = str(json_link.get('state'))

        self.get_qos_info.set_ratelimite_for_app(app, meter_id, group_id, state)

    @route('rate_for_member', urls.url_flow_member, methods=['PUT'])
    def set_flow_for_ratelimite_for_member(self, req, **kwargs):
        mac = str(kwargs['mac'])
        content = req.body
        json_link = json.loads(content)
        meter_id = str(json_link.get('meter_id'))
        group_id = str(json_link.get('group_id'))
        state = str(json_link.get('state'))

        self.get_qos_info.set_ratelimite_for_mac(mac, meter_id, group_id, state)

    @route('meter_data', urls.url_meter_set, methods=['PUT'])
    def set_meter_data_(self, req, **kwargs):
        """Put Member data method."""
        meterid = str(kwargs['meterid'])
        content = req.body
        print content, meterid
        json_link = json.loads(content)
        bandwidth = str(json_link.get('bandwidth'))
        command = str(json_link.get('command'))
        self.get_qos_info.set_meter_to_switches(meterid, bandwidth, command)
        return Response(content_type='application/json',
                            body=str('Success'))

    @route('member_list_for_app', urls.url_member_list_for_app, methods=['GET'])
    def get_member_list_for_app(self, req, **kwargs):
        app = str(kwargs['app'])
        members = []
        for key in statistic.database_member_record.keys():
            member_data = statistic.database_member_record[key]
            app_list = member_data.apprate.keys()
            if app in app_list:
                m = data_collection.member_list.get(member_data.id)
                member = {}
                member.update({'mac': member_data.id})
                member.update({'ip': m.ip})
                members.append(member)
        dic = {}
        dic.update({app: members})
        body = json.dumps(dic)
        return Response(content_type='application/json', body=body)
