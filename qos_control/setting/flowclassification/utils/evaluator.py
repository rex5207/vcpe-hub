"""Method for evaluation."""
from setting.flowclassification.record import statistic
from setting.variables.var import constant


def app_evaluation(flow_list):
    """Method for app evaluation."""
    tmp_apprate = {}
    for key in flow_list:
        flow_info = flow_list[key]
        app_name = flow_info.app
        if app_name in tmp_apprate:
            tmp_apprate[app_name] += flow_info.rate
        else:
            tmp_apprate.update({app_name: flow_info.rate})

    for key in tmp_apprate:
        if key in statistic.database_app_record:
            tmp_object = statistic.database_app_record[key]
            tmp_object.rate = tmp_apprate[key]
            tmp_object.exist = 1
        else:
            flow = statistic.Application_recored(key, tmp_apprate[key])
            flow.exist = 1
            statistic.database_app_record.update({key: flow})

    key_set = statistic.database_app_record.keys()
    for key in key_set:
        flow = statistic.database_app_record[key]
        if flow.exist == 0:
            statistic.database_app_record.pop(key)
        else:
            statistic.database_app_record[key].exist = 0
            print key, flow.rate


def member_evaluation(flow_list, member_list):
    """Method for member evaluation."""
    tmp_member_rate = {}
    for key in flow_list:
        flow_info = flow_list[key]
        tmp = None
        if flow_info.src_mac == constant.Gateway_Mac:
            tmp = flow_info.dst_mac
        else:
            tmp = flow_info.src_mac
        # print flow_info.dst_mac, flow_info.src_mac
        if member_list.get(tmp) is not None:
            if tmp in tmp_member_rate:
                tmp_apprate = tmp_member_rate.get(tmp).apprate
                app_name = flow_info.app
                if app_name in tmp_apprate:
                    tmp_apprate[app_name] += flow_info.rate
                else:
                    tmp_apprate.update({app_name: flow_info.rate})
            else:
                print tmp, member_list.get(tmp)
                group_id = member_list.get(tmp).group_id
                if group_id is not None:
                    print "group_id", group_id, "name", tmp
                    tmp_member_rate.update({tmp: statistic.Memeber_record(tmp, group_id)})
                    tmp_apprate = tmp_member_rate.get(tmp).apprate
                    tmp_apprate.update({flow_info.app: flow_info.rate})

            tmp_member_rate.get(tmp).flow.append(flow_info)

    statistic.database_member_record = tmp_member_rate


def group_evaluation(member_list, group_list):
    """Method for group evaluation."""
    tmp_group = {}
    for key in group_list:
        tmp_group.update({key: statistic.Group_record(key)})
        print key, group_list.get(key).members
        for member in group_list.get(key).members:
            tmp_group.get(key).member.update({member: member_list.get(member)})
            print member, type(member_list.get(member))
            if member_list.get(member) is not None:
                m_app = member_list.get(member).apprate
                for app in m_app:
                    if app in tmp_group.get(key).apprate:
                        tmp_group.get(key).apprate[app] += m_app.get(app)
                    else:
                        tmp_group.get(key).apprate.update({app: m_app.get(app)})

    statistic.database_group_record = tmp_group
