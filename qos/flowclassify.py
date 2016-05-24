"""Prject for Flow Statistic."""
from ryu.base import app_manager
from ryu.controller.handler import set_ev_cls

from setting.variable import constant
from setting.db import data_collection
from setting.db.utils import flowutils
from setting.utils import db_util
from setting.flowclassification.utils import evaluator
from setting.flowclassification.record import statistic
from qos_control import Qos_UpdateEvent
from flowstatistic_monitor import APP_UpdateEvent

import logging
import time, datetime


class flowclassify(app_manager.RyuApp):

    """Flow Statistic Class."""

    _EVENTS = [APP_UpdateEvent]
    _EVENTS = [Qos_UpdateEvent]

    def __init__(self, *args, **kwargs):
        """Initial Setting method."""
        super(flowclassify, self).__init__(*args, **kwargs)
        self.topology_api_app = self
        self.flow_list_re = {}
        hdlr = logging.FileHandler('sdn_log_app_rate.log')
        self.logger.addHandler(hdlr)

    @set_ev_cls(APP_UpdateEvent)
    def app_event_handler(self, ev):
        print ('[INFO FlowClassify.app_event_handler] %s' % ev.msg)
        t1 = time.time()
        st = datetime.datetime.fromtimestamp(t1).strftime('%Y-%m-%d %H:%M:%S')
        self.logger.info('timestamp = %s', st)
        flow_list_in_dp = flowutils.get_flow_in_dp(constant.Detect_switch_DPID)
        db_util.update_app_for_flows(data_collection.flow_list, constant.FlowClassification_IP, constant.db_method)
        evaluator.app_evaluation(flow_list_in_dp)
        evaluator.member_evaluation(flow_list_in_dp, data_collection.member_list)
        # print '[INFO FlowClassify._monitor]Flow Statistic Class\n>> member'
        # for key in statistic.database_member_record:
        #     print " >", key, statistic.database_member_record[key]
        #     for key2 in statistic.database_member_record[key].apprate:
        #         print " >", key2, statistic.database_member_record[key].apprate[key2]

        evaluator.group_evaluation(statistic.database_member_record, data_collection.group_list)
        print '[INFO FlowClassify._monitor]Flow Statistic Class\n>> group'
        self.logger.info('[INFO FlowClassify._monitor]Flow Statistic Class\n>> group')
        for key in statistic.database_group_record:
            print " >", key, statistic.database_group_record[key], statistic.database_group_record[key].member.keys()
            v = 0.0
            for key2 in statistic.database_group_record[key].apprate:
                print " >", key2, statistic.database_group_record[key].apprate[key2]
                self.logger.info('%s %f', key2, statistic.database_group_record[key].apprate[key2])
                v += statistic.database_group_record[key].apprate[key2]
            statistic.database_group_record[key].total = v
            print ' > total bandwidth: ', statistic.database_group_record[key].total
            self.logger.info(' > total bandwidth: %f', statistic.database_group_record[key].total)

        ev = Qos_UpdateEvent('Update qos for flow')
        self.send_event_to_observers(ev)
