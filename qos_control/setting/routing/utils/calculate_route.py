def calculate_least_cost_path(path_list, switch_stats, net):
    target_path = None
    target_cost = -1
    print path_list
    for path in path_list:
        path_index = path_list.index(path)
        # print 'path_index', path_index, path
        cost = 0
        for node in path:
            index = path.index(node)
            # print 'index', index, node
            if index != 0 and index < len(path)-2:

                port = switch_stats.get(node)
                # print 'port', port
                if port is not None:
                    port_stats = switch_stats.get(node).get('weight')
                    port_stats_2 = switch_stats.get(path[index+1]).get('weight')

                    if port_stats is not None:
                        tar_port = net[node][path[index+1]]['port']
                        # print 'tar_port', tar_port
                        # for port in port_stats.keys():

                        counter_list = port_stats.get(tar_port)
                        # print 'tar_port', counter_list
                        if counter_list is not None:
                            if cost < (counter_list[1]+counter_list[0]):
                                cost = counter_list[1]+counter_list[0]
                            # if cost < counter_list[0]:
                            #     cost = counter_list[0]
                            # cost = counter_list[1] + counter_list[0] + cost

                        tar_port = net[path[index+1]][node]['port']
                        # print 'tar_port2', tar_port
                        counter_list = port_stats_2.get(tar_port)
                        # print 'counter_list2', counter_list
                        if counter_list is not None:
                            if cost < (counter_list[1]+counter_list[0]):
                                cost = counter_list[1]+counter_list[0]
                            # if cost < counter_list[0]:
                            #     cost = counter_list[0]
                            # cost = counter_list[1] + counter_list[0] + cost


        # print '@@@@@', path_index, cost
        if cost < target_cost:
            target_path = path_index
            target_cost = cost
        elif cost == target_cost:
            target_path_length = len(path_list[target_path])
            path_length = len(path)
            if path_length < target_path_length:
                target_path = path_index
                target_cost = cost
        elif target_cost == -1:
            target_path = path_index
            target_cost = cost

        print '@@@', target_path
    return target_path, target_cost

def check_switch_load(switch_list, switch_stats, limitation):
    valid = 0
    target_switch_list = []
    for switch in switch_list:
        port = switch_stats.get(switch)
        # print 'p', port
        if port is not None:
            # print 'pp'
            port_stats = switch_stats.get(switch).get('weight')
            # print 'pp', port_stats
            if port_stats is not None:
                for port in port_stats.keys():
                    counter_list = port_stats.get(port)
                    if counter_list[0] > limitation:
                        valid = 1
                    elif counter_list[1] > limitation:
                        valid = 1
                    else:
                        if counter_list[2] > 0:
                            valid = 1
                    if valid == 1:
                        target_switch_list.append(switch)
                        break
    print 'valid', valid
    return target_switch_list
