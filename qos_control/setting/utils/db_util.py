import requests
import hashlib
from route import urls

def update_app_for_flows(flow_list, dp_ip):
    try:
        key_set = flow_list.keys()
        for key in key_set:
            flow_info = flow_list.get(key)
            if flow_info is not None and flow_info.app == 'Others':
                m = hashlib.sha256()
                m.update(flow_info.src_ip + flow_info.dst_ip
                         + str(flow_info.src_port) + str(flow_info.dst_port) + str(flow_info.ip_proto))
                url = 'http://140.114.71.176:2000/api/get/' + m.hexdigest()
                response = requests.get(url)
                str_id = flow_info.src_ip + flow_info.dst_ip + str(flow_info.src_port) + str(flow_info.dst_port) + str(flow_info.ip_proto)
                urls.counter = urls.counter + 1
                print '[INFO] Update app for flows'
                print ' >> counter:', urls.counter
                print ' >>id', str_id, m.hexdigest()

                json_data = None
                if response.status_code == 200:
                    json_data = response.json()
                else:
                    m.update(flow_info.dst_ip + flow_info.src_ip
                             + str(flow_info.dst_port) + str(flow_info.src_port) + str(flow_info.ip_proto))
                    url = 'http://140.114.71.175:2000/api/get/' + m.hexdigest()
                    response = requests.get(url)
                    if response.status_code == 200:
                        json_data = response.json()
                print ' >> json_date', json_data
                if json_data is not None:
                    app_name = json_data.get('classifiedResult').get('classifiedName')
                    print ' >>app name', app_name
                    flow_info.app = app_name
                    key_r = str(flow_info.dst_mac)+str(flow_info.src_mac)+\
                            str(flow_info.dst_ip)+str(flow_info.src_ip)+\
                            str(flow_info.ip_proto)+\
                            str(flow_info.dst_port)+str(flow_info.src_port)
                    flow_info_r = flow_list.get(key_r)
                    if flow_info_r is not None:
                        flow_info_r.app = app_name
    except Exception:
        print 'DB Error'
