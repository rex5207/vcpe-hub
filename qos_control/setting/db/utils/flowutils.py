from setting.db.data_collection import flow_list

def get_flow_in_dp(dpid):
    flow_list_in_dp = {}
    flow_list_key = flow_list.keys()
    for key in flow_list_key:
        if key.startswith(str(dpid)):
            flow_list_in_dp.update({key: flow_list.get(key)})

    return flow_list_in_dp
