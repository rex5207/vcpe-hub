"""Prject for Qos Control."""

from ryu.base import app_manager
from ryu.lib import hub
from ryu.topology.api import get_switch
from ryu.controller.event import EventBase
from ryu.controller.handler import set_ev_cls

from setting.ratelimitation.setting import setup
from setting.ratelimitation.utils import control
from setting.flowclassification.record import statistic
from setting.db import data_collection
from setting.dynamic_qos.utils import mathimetic
from setting.dynamic_qos.utils import rate_setup
from setting.dynamic_qos.db import history
from setting.variable import constant

import numpy
import math
import time, datetime
import copy

import logging

class Qos_UpdateEvent(EventBase):
    def __init__(self, msg):
        self.msg = msg

class QosControl(app_manager.RyuApp):

    """Qos Control Class."""

    def __init__(self, *args, **kwargs):
        """Initial Setting method."""
        super(QosControl, self).__init__(*args, **kwargs)
        self.monitor_thread = hub.spawn(self._monitor)
        self.topology_api_app = self
        hdlr = logging.FileHandler('sdn_log_dynamic_control.log')
        self.logger.addHandler(hdlr)

    def _monitor(self):
        # f = open("record_20150831.txt",  "rw+")
        t0 = 0
        while True:
            self.logger.info('---------------------')
            t1 = time.time()
            st = datetime.datetime.fromtimestamp(t1).strftime('%Y-%m-%d %H:%M:%S')
            self.logger.info('timestamp = %s', st)
            # self._control_manual()
            if constant.NeedDynamicQos == 1:
                self._control_dynamic(t0, t1)
            self.logger.info('---------------------')
            hub.sleep(5)
            t0 = t1


    @set_ev_cls(Qos_UpdateEvent)
    def _control_manual(self, ev):
        print ('[INFO QosControl._control_manual] %s' % ev.msg)
        print 'INFO [qos_control._control_manual]\n  >>  manual control begin'
        setting = setup.ratelimite_setup_for_specialcase
        for group in setting.keys():
            for app in setting.get(group).keys():
                if setting.get(group).get(app).get('state') == 'up':
                    control.set_ratelimite_for_app(app, setting.get(group).get(app).get("meter_id"), group, 'up', 'm')
                else:
                    control.set_ratelimite_for_app(app, setting.get(group).get(app).get("meter_id"), group, 'down', 'm')
                    setting.get(group).pop(app)

        setting_m = setup.ratelimite_setup_for_specialcase_member
        for group in setting_m.keys():
            for mac in setting_m.get(group).keys():
                if setting_m.get(group).get(mac).get('state') == 'up':
                    control.set_ratelimite_for_member(mac, setting_m.get(group).get(mac).get("meter_id"), group, 'up', 'm')
                else:
                    control.set_ratelimite_for_member(mac, setting_m.get(group).get(mac).get("meter_id"), group, 'down', 'm')
                    setting_m.get(group).pop(mac)

    def _control_dynamic(self, timestamp0, timestamp1):
        print 'INFO [qos_control._control_dynamic]\n  >>  dynamic control begin'
        group_list = data_collection.group_list.keys()

        # get whole data array
        # then calculate normalization & average data
        original_data = self._get_all_data_from_db()
        normalize_d, mean_d, var_setup = mathimetic.normalization_and_average(original_data)

        whole_predict_data = {}
        ratio_app = {}
        group_total_list = []
        for group_id in group_list:
            if group_id != 'whole':
                if statistic.database_group_record.get(group_id) is not None:
                    group_total_list.append(statistic.database_group_record[group_id].total)
                else:
                    group_total_list.append(0.0)

                # predict the unknown bandwidth for apps & return the real
                data, data_un, r1, r2 = self._predict(group_id, mean_d, normalize_d, timestamp0)
                his_data = {timestamp1: data_un}
                if history.history_list.get(group_id) is None:
                    history.history_list.update({group_id: his_data})
                else:
                    ori_his_data = history.history_list[group_id]
                    up_data = ori_his_data.update(his_data)
                    print up_data
                    history.history_list.update({group_id: his_data})
                # print 'history >', history.history_list, his_data

                # file.write(str(timestamp1)+', '+str(r1)+', '+str(r2)+'\n')
                data = self._return_to_real_num(data, var_setup.get(group_id))
                whole_predict_data.update({group_id: data})

                # claculate the ratio between apps
                app_list = statistic.database_app_record.keys()
                member_list = data.keys()
                ratio = []
                ratio_a = {}
                ratio_c = {}

                for app in app_list:
                    tmp = 0.0
                    app_rate_list = []
                    for member in member_list:
                        tmp += data.get(member).get(app)
                        app_rate_list.append(data.get(member).get(app))
                    divide = len(member_list)
                    if numpy.std(app_rate_list) > numpy.average(app_rate_list):
                        divide = 1
                    ratio_a.update({app: tmp})
                    ratio_c.update({app: divide})
                    ratio.append(tmp)

                keys_r = ratio_a.keys()
                for d in keys_r:
                    if sum(ratio) > 0:
                        ratio_a[d] = ratio_a.get(d)/sum(ratio)
                        ratio_a[d] = ratio_a[d] / ratio_c.get(d)
                    else:
                        ratio_a[d] = 0.0
                ratio_app.update({group_id: ratio_a})

        # control bandwidth between apps
        rate_list = [statistic.database_app_record[key].rate for key in statistic.database_app_record]
        switch_list = get_switch(self.topology_api_app, None)
        rate_setup.rate_control_for_apps(rate_list, group_total_list, group_list,
                                         ratio_app, switch_list, constant.Capacity, self.logger)

    def _get_all_data_from_db(self):
        group_list = data_collection.group_list.keys()
        all_data = {}
        for group_id in group_list:
            app_list = statistic.database_app_record.keys()
            if group_id != 'whole':
                group = data_collection.group_list.get(group_id)
                members = group.members
                member_data = {}
                for member in members:
                    a = {}
                    for app in app_list:
                        print member
                        if member in statistic.database_member_record.keys():
                            m = statistic.database_member_record.get(member)
                            if m.apprate.get(app) is not None:
                                a.update({app: m.apprate.get(app)})
                    member_data.update({member: a})
                all_data.update({group_id: member_data})
        return all_data

    def _get_array_for_group(self, group_id, whole_data):

        group_data = whole_data.get(group_id)
        if group_data is not None:
            for key in group_data.keys():
                app_list = group_data.get(key).get('app_list').keys()
                for i in range(len(app_list)):
                    value = group_data.get(key).get('app_data')
                    data = group_data.get(key).get('app_list')
                    data[app_list[i]] = value[i]
                group_data[key] = group_data.get(key).get('app_list')
        app_list = statistic.database_app_record.keys()
        member_list = group_data.keys()
        if member_list is not None:
            for member in member_list:
                app_list_m = group_data.get(member).keys()
                member = group_data[member]
                for app in app_list:
                    if app not in app_list_m:
                        member.update({app: -1.0})
        return group_data

    def _predict(self, group_id, mean_value_for_group, data_ori, t0):
        r1 = 0.0
        r2 = 0.0
        print 'INFO [qos_control._predict]\n  >>  predict begin'
        data = self._get_array_for_group(group_id, data_ori)
        print '  >> orginal data =>', data
        data_ans = {}

        # Using Collabrative filtering to predict
        if data is not None:
            data_ans = copy.deepcopy(data)
            data_m = data.keys()
            for m in data_m:
                m_d = data.get(m)
                app = m_d.keys()
                for a in app:
                    # if m == 'ac:22:0b:d7:0b:ca' and a == 'facebook':
                    if m_d.get(a) == -1.0:
                        p1 = mean_value_for_group.get(group_id).get(m)
                        p2_u = 0.0
                        p2_d = 0.0
                        for pm in data_m:
                            if pm != m:
                                if data.get(pm).get(a) != -1:
                                    t = data.get(pm).get(a) - mean_value_for_group.get(group_id).get(pm)
                                    t = t*mathimetic.get_similarity_between_members(m, pm, data)
                                    p2_u += t
                                    p2_d += math.fabs(mathimetic.get_similarity_between_members(m,pm,data))
                        if p2_d > 0.0:
                            gg = data_ans.get(m)
                            gg[a] = round(p2_u / p2_d + p1, 2)

                        r1 = data[m].get(a)
                        his_app = 0.0
                        if t0 != 0:
                            g_his_data = history.history_list[group_id].get(t0)
                            if g_his_data is not None:
                                if g_his_data.get(m) is not None:
                                    if g_his_data[m].get(a) is not None:
                                        his_app = g_his_data[m].get(a)

                        if his_app < 0:
                            his_app = 0
                        g_m = data_ans.get(m)
                        g_m[a] = 0.9*his_app + 0.1*g_m[a]
                        r2 = g_m[a]

        print '  >>  data after predicting & real =>', data_ans, data
        return data_ans, data, str(r1), str(r2)

    def _return_to_real_num(self, data, setup_list):
        for member in data.keys():
            list = setup_list.get(member)
            member = data[member]
            for app in member.keys():
                member[app] = member[app] / 10.0
                member[app] *= list[1]
                member[app] *= list[0]
                if member[app] <= 0.0:
                    member[app] = 0.0
        return data
