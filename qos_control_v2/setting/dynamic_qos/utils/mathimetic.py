"""Mathemetic Methods."""
from scipy.stats import pearsonr
import numpy as np


def get_similarity_between_members(m1, m2, data):
    """Method for calculate similarity."""
    x_bandwidth_for_app = data.get(m1)
    y_bandwidth_for_app = data.get(m2)
    x = [x_bandwidth_for_app.get(app) for app in x_bandwidth_for_app.keys()]
    y = [y_bandwidth_for_app.get(app) for app in y_bandwidth_for_app.keys()]
    xx = []
    yy = []
    for i in range(len(x)):
        if x[i] != -1 and y[i] != -1:
            xx.append(x[i])
            yy.append(y[i])

    print xx, yy
    r_row, p_value = pearsonr(xx, yy)

    print 'similarity', r_row
    if np.isnan(r_row):
        r_row = 0.0
    return r_row


def normalization_and_average(data_array):
    """Method for Normalization."""
    group_list = data_array.keys()
    group_data_for_nor = {}
    group_data_for_av = {}
    group_data_for_setup = {}
    for group in group_list:
        member_list = data_array.get(group).keys()
        member_data_for_normalization = {}
        member_data_for_average = {}
        member_data_for_setup = {}
        for member in member_list:
            data = {}
            app_list = data_array.get(group).get(member)
            list_ori = [data_array.get(group).get(member).get(app) for app in app_list]
            setting_list = [sum(list_ori)]
            if sum(list_ori) > 0.0:
                list_av = [rate/sum(list_ori) for rate in list_ori]
                list_nor = [av/max(list_av)*10 for av in list_av]
                setting_list.append(max(list_av))
            else:
                list_av = [0.0 for rate in list_ori]
                list_nor = [0.0 for av in list_av]
                setting_list.append(0.0)

            average = round(np.mean(list_nor), 2)
            data.update({'app_list': app_list})
            data.update({'app_data': list_nor})
            member_data_for_normalization.update({member: data})
            member_data_for_average.update({member: average})
            member_data_for_setup.update({member: setting_list})
        group_data_for_nor.update({group: member_data_for_normalization})
        group_data_for_av.update({group: member_data_for_average})
        group_data_for_setup.update({group: member_data_for_setup})
    return group_data_for_nor, group_data_for_av, group_data_for_setup
