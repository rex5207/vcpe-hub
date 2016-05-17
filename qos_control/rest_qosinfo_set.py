"""Project for Rest API (Group Setting)."""
import json

from ryu.base import app_manager
from ryu.app.wsgi import ControllerBase, WSGIApplication, route
from ryu.topology.api import get_switch
from webob import Response

from setting.db import data_collection
from setting.variable import constant
from setting.flowclassification.record import statistic
from setting.dynamic_qos.utils import rate_setup
from setting.ratelimitation.setting import setup

from route import urls

# url = '/set_qos_info/{capacity}'
set_qos_info_instance_name = 'set_qos_info_api_app'
# app_url = '/get_app_list'
# meter_list_url = '/get_meter_list'


class QosSetup(app_manager.RyuApp):

    _CONTEXTS = {'wsgi': WSGIApplication}

    def __init__(self, *args, **kwargs):
        """Initial Setting method."""
        super(QosSetup, self).__init__(*args, **kwargs)
        self.topology_api_app = self
        wsgi = kwargs['wsgi']
        wsgi.register(QosSetupRest,
                      {set_qos_info_instance_name: self})

    def set_qos_parameter(self, capacity):
        constant.Capacity = int(capacity)
        switch_list = get_switch(self.topology_api_app, None)
        rate_setup.init_meter_setup(constant.Capacity, switch_list)

    def set_qos_parameter_dynamic_en(self, en):
        constant.NeedDynamicQos = int(en)


# curl -X PUT http://127.0.0.1:8080/set_qos_info/2
class QosSetupRest(ControllerBase):

    def __init__(self, req, link, data, **config):
        """Initial Setting method."""
        super(QosSetupRest, self).__init__(req, link, data, **config)
        self.get_qos_info = data[set_qos_info_instance_name]

    @route('qos_data', urls.url_dynamic_en, methods=['PUT'])
    def set_qos_dynamic(self, req, **kwargs):
        dynamic_en = str(kwargs['enable'])
        self.get_qos_info.set_qos_parameter_dynamic_en(dynamic_en)
        return Response(content_type='application/json', body=str('Success'))

    @route('qos_data', urls.url_capacity_set, methods=['PUT'])
    def set_qos_data(self, req, **kwargs):
        capacity = str(kwargs['capacity'])

        self.get_qos_info.set_qos_parameter(capacity)
        return Response(content_type='application/json', body=str('Success'))

    @route('qos_data', urls.url_qos_app_list_get, methods=['GET'])
    def get_app_list(self, req, **kwargs):
        group = str(kwargs['groupid'])
        dic = {}
        if group == 'whole':
            app_list = statistic.database_app_record.keys()
            for key in app_list:
                dic.update({key: statistic.database_app_record[key].rate})
        else:
            for key in statistic.database_group_record[group].apprate:
                dic.update({key: statistic.database_group_record[group].apprate[key]})

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

    @route('qos_policy', urls.url_qos_policy_get, methods=['GET'])
    def get_qos_policy(self, req, **kwargs):
        group = str(kwargs['groupid'])
        dic = {}
        policy = setup.ratelimite_setup_for_specialcase.get(group)
        if policy is not None:
            for app in policy:
                if policy.get(app).get('state') == 'up':
                    speed = 'drop'
                    for sp in data_collection.meter_list:
                        if str(policy.get(app).get('meter_id')) == data_collection.meter_list[sp]:
                            speed = sp
                    dic.update({app: {'meterid': policy.get(app).get('meter_id'), 'speed': speed}})
        body = json.dumps(dic)
        return Response(content_type='application/json', body=body)


    @route('dpid_data', urls.url_dpid_list, methods=['GET'])
    def get_dpid_list(self, req, **kwargs):
        dic = {}
        group_data = data_collection.group_list.get('whole')
        switch_list = group_data.switches
        for dp in switch_list:
            dic.update({dp: dp})
        body = json.dumps(dic)
        return Response(content_type='application/json', body=body)
