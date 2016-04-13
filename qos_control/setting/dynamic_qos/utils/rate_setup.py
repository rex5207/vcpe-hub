"""Mehthod for rate control in dynamic qos."""
from setting.dynamic_qos.setup import meter_mapping
from setting.ratelimitation.utils import control
from setting.utils import ofputils
import time


def init_meter_setup(capacity, switch_list):
    interval = capacity*8/10
    for dp in switch_list:
        for i in range(10):
            j = i+1
            ofputils.set_meter_entry(dp.dp, int(j*interval), int(j), 'ADD')


def rate_control_for_apps(rate_list, group_total_list, group_list,
                          ratio_app, switch_list, capacity, logger):
    """Handle rate control for apps."""
    if sum(group_total_list) != 0:
        group_total_list = [i/sum(group_total_list) for i in group_total_list]
    print 'INFO [dynamic_qos.rate_control_for_apps]\n  >>'
    print 'the used bandwidth =>', sum(rate_list)
    print 'maximum we can used =>', 0.9 * capacity * 1024
    index = 0
    for group_id in group_list:
        if group_id != 'whole' and capacity > 0:
            # index = (group_list.index(group_id)+1)*10
            # print 'index', index, group_list.index(group_id), ratio_app[group_id]
            for app in ratio_app.get(group_id).keys():
                # print 'app meter', index, app
                if ratio_app[group_id].get(app) > 0:

                        value_ratio = group_total_list[index] * ratio_app[group_id].get(app)

                        meter_id = int(value_ratio*10)
                        if meter_id < 1:
                            meter_id = 1
                        print 'app rate', app, meter_id

                        if sum(rate_list) >= 0.9 * capacity * 1024:
                            if meter_mapping.have_control == 0:
                                meter_mapping.have_control = 1
                            control.set_ratelimite_for_app(app, meter_id, group_id, 'up', 'd')
                            logger.info('1 app rate %s %d %f', app, meter_id, sum(rate_list))
                        else:
                            if meter_mapping.have_control == 1:
                                meter_mapping.have_control = 0
                            control.set_ratelimite_for_app(app, meter_id, group_id, 'down', 'd')
                            logger.info('0 app rate %s %d %f', app, meter_id, sum(rate_list))
            index += 1
