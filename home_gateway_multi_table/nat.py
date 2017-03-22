import json

from ryu.base import app_manager
from ryu.app.wsgi import ControllerBase, WSGIApplication, route
from webob import Response
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.ofproto import ether
from ryu.ofproto import inet
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ipv4
from ryu.lib.packet import tcp
from ryu.lib.packet import udp
from ryu.lib.packet import arp
from ryu.lib.packet import ether_types
from netaddr import IPNetwork, IPAddress
import pprint

from config import service_config, forwarding_config
from models import nat_settings
from helper import ofp_helper, nat_helper
from route import urls

IP_TO_MAC_TABLE = {}
# a.k.a arp table

nat_instance_name = 'nat_instance_api_app'


class SNAT(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    _CONTEXTS = {'wsgi': WSGIApplication}

    def __init__(self, *args, **kwargs):
        super(SNAT, self).__init__(*args, **kwargs)
        wsgi = kwargs['wsgi']
        wsgi.register(SNATRest, {nat_instance_name: self})

        self.ingress_table_id = service_config.service_sequence['nat_ingress']
        self.egress_table_id = service_config.service_sequence['nat_egress']
        self.forward_table_id = service_config.service_sequence['forwarding']
        self.goto_table_priority = service_config.service_priority['goto_table']
        self.service_priority = service_config.service_priority['nat']

        settings = nat_settings.load()
        self.wan_port = settings['wan_port']
        self.public_ip = str(settings['public_ip'])
        self.public_gateway = str(settings['public_gateway'])
        self.public_ip_subnetwork = settings['public_ip_subnetwork']
        self.private_gateway = settings['private_gateway']
        self.private_subnetwork = settings['private_subnetwork']
        self.mac_on_wan = settings['mac_on_wan']
        self.mac_on_lan = settings['mac_on_lan']

        self.IDLE_TIME = 100
        self.port_counter = -1
        self.ports_pool = range(2000, 65536)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # # Table Miss, forward packet to next table
        # match = parser.OFPMatch()
        # ofp_helper.add_flow_goto_next(datapath, table_id=self.egress_table_id,
        #                               priority=self.goto_table_priority, match=match)
        # ofp_helper.add_flow_goto_next(datapath, table_id=self.ingress_table_id,
        #                               priority=self.goto_table_priority, match=match)

    @set_ev_cls(ofp_event.EventOFPFlowRemoved, MAIN_DISPATCHER)
    def flow_removed_handler(self, ev):
        """
        Flow-Removed message.
        When switch send flow-Removed message to controller,
        controller will release tcp/udp port which is not in use,
        putting it back to ports-pool.
        """
        print '[*] Flow-Removed EVENT'
        msg = ev.msg

        tcp_port = msg.match.get('tcp_dst')
        udp_port = msg.match.get('udp_dst')

        if tcp_port:
            print '[*] Available TCP port %d' % tcp_port
            self.ports_pool.append(tcp_port)
            self.ports_pool.sort()
        elif udp_port:
            print '[*] Available UDP port %d' % udp_port
            self.ports_pool.append(udp_port)
            self.ports_pool.sort()

    def _send_packet_to_port(self, datapath, port, data):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        actions = [parser.OFPActionOutput(port=port)]
        out = parser.OFPPacketOut(datapath=datapath,
                                  buffer_id=ofproto.OFP_NO_BUFFER,
                                  in_port=ofproto.OFPP_CONTROLLER,
                                  actions=actions,
                                  data=data)
        datapath.send_msg(out)

    def _arp_request_handler(self, pkt_arp):
        """
        Handle ARP request packets.
        When controller get an ARP request packet,
        it will reply someone who want to ask NAT's MAC address.
        (Probably under NAT's LAN or WAN)
        """
        data = None

        if pkt_arp.opcode != arp.ARP_REQUEST:
            print '[WARRING] Wrong ARP opcode!'
            return None

        if pkt_arp.dst_ip == str(self.private_gateway):
            # What's the MAC address of NAT Private IP? In other word,
            # What's the MAC address of Gateway in this private network?
            # Who ask this is must from LAN (Private Network Host)
            # So we reply fake MAC address define in `mac_on_lan`
            data = nat_helper.arp_reply(src_mac=self.mac_on_lan,
                                        src_ip=str(self.private_gateway),
                                        target_mac=pkt_arp.src_mac,
                                        target_ip=pkt_arp.src_ip)

        elif pkt_arp.dst_ip == self.public_ip:
            # What's the MAC address of NAT Public IP?
            # Who ask this is must from WAN (Extranet Network Host)
            # So we reply fake MAC address defined in `mac_on_lan`
            data = nat_helper.arp_reply(src_mac=self.mac_on_wan,
                                        src_ip=self.public_ip,
                                        target_mac=pkt_arp.src_mac,
                                        target_ip=pkt_arp.src_ip)

        return data

    def _arp_reply_handler(self, pkt_arp):
        """
        Handle ARP reply packets.
        When controller get an ARP reply packet, it will update ARP table.
        """
        if pkt_arp.opcode != arp.ARP_REPLY:
            print '[WARRING] Wrong ARP opcode!'
            return None

        if pkt_arp.dst_ip == self.public_ip:
            IP_TO_MAC_TABLE[pkt_arp.src_ip] = pkt_arp.src_mac

    def _get_available_port(self):
        """
        Getting port number sequential increase.
        """
        self.port_counter += 1
        p = self.ports_pool.pop(self.port_counter)
        return p

    def _in_public_ip_subnetwork(self, ip):
        ip = IPAddress(ip)
        return ip in self.public_ip_subnetwork

    def _in_private_subnetwork(self, ip):
        ip = IPAddress(ip)
        return ip in self.private_subnetwork

    def _is_public(self, ip):
        ip = IPAddress(ip)
        return ip.is_unicast() and not ip.is_private()

    def _private_to_public(self, datapath, buffer_id, data, in_port, out_port,
                           pkt_ip, pkt_ethernet, pkt_tcp=None, pkt_udp=None,
                           pkt_icmp=None):
        if pkt_ip is None:
            return

        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        eth_dst = pkt_ethernet.dst
        eth_src = pkt_ethernet.src
        ipv4_src = pkt_ip.src
        ipv4_dst = pkt_ip.dst

        nat_port = self._get_available_port()

        if (self._is_public(ipv4_dst) and not self._in_public_ip_subnetwork(ipv4_dst)):
            target_ip = self.public_gateway
        elif self._in_public_ip_subnetwork(ipv4_dst):
            target_ip = ipv4_dst
        elif self._in_private_subnetwork(ipv4_dst):
            return

        if pkt_tcp:
            # Install TCP Flow Entry
            tcp_src = pkt_tcp.src_port
            tcp_dst = pkt_tcp.dst_port
            # egress
            match = parser.OFPMatch(in_port=in_port,
                                    eth_type=ether.ETH_TYPE_IP,
                                    ip_proto=inet.IPPROTO_TCP,
                                    ipv4_src=ipv4_src,
                                    ipv4_dst=ipv4_dst,
                                    tcp_src=tcp_src,
                                    tcp_dst=tcp_dst)
            actions = [parser.OFPActionSetField(eth_dst=IP_TO_MAC_TABLE[target_ip]),
                       parser.OFPActionSetField(ipv4_src=self.public_ip),
                       parser.OFPActionSetField(tcp_src=nat_port)]
            forward_actions = [parser.OFPActionOutput(out_port)]

            # ingress
            match_back = parser.OFPMatch(eth_type=ether.ETH_TYPE_IP,
                                         ip_proto=inet.IPPROTO_TCP,
                                         ipv4_src=ipv4_dst,
                                         ipv4_dst=self.public_ip,
                                         tcp_src=tcp_dst,
                                         tcp_dst=nat_port)

            actions_back = [parser.OFPActionSetField(eth_dst=eth_src),
                            parser.OFPActionSetField(ipv4_dst=ipv4_src),
                            parser.OFPActionSetField(tcp_dst=tcp_src)]
            forward_match_back = parser.OFPMatch(eth_type=ether.ETH_TYPE_IP,
                                                 ip_proto=inet.IPPROTO_TCP,
                                                 ipv4_src=ipv4_dst,
                                                 ipv4_dst=ipv4_src,
                                                 tcp_src=tcp_dst,
                                                 tcp_dst=tcp_src)
            forward_actions_back = [parser.OFPActionOutput(in_port)]

        elif pkt_udp:
            # Install UDP Flow Entry
            udp_src = pkt_udp.src_port
            udp_dst = pkt_udp.dst_port

            # egress, inside-to-outside
            match = parser.OFPMatch(in_port=in_port,
                                    eth_type=ether.ETH_TYPE_IP,
                                    ip_proto=inet.IPPROTO_UDP,
                                    ipv4_src=ipv4_src,
                                    ipv4_dst=ipv4_dst,
                                    udp_src=udp_src,
                                    udp_dst=udp_dst)
            actions = [parser.OFPActionSetField(eth_dst=IP_TO_MAC_TABLE[target_ip]),
                       parser.OFPActionSetField(ipv4_src=self.public_ip),
                       parser.OFPActionSetField(udp_src=nat_port)]
            forward_actions = [parser.OFPActionOutput(out_port)]

            # ingress, outside-to-inside
            match_back = parser.OFPMatch(eth_type=ether.ETH_TYPE_IP,
                                         ip_proto=inet.IPPROTO_UDP,
                                         ipv4_src=ipv4_dst,
                                         ipv4_dst=self.public_ip,
                                         udp_src=udp_dst,
                                         udp_dst=nat_port)
            actions_back = [parser.OFPActionSetField(eth_dst=eth_src),
                            parser.OFPActionSetField(ipv4_dst=ipv4_src),
                            parser.OFPActionSetField(udp_dst=udp_src)]

            forward_match_back = parser.OFPMatch(eth_type=ether.ETH_TYPE_IP,
                                                 ip_proto=inet.IPPROTO_UDP,
                                                 ipv4_src=ipv4_dst,
                                                 ipv4_dst=ipv4_src,
                                                 udp_src=udp_dst,
                                                 udp_dst=udp_src)
            forward_actions_back = [parser.OFPActionOutput(in_port)]
        else:
            pass
        # outside - inside set-filed (Table 0)
        ofp_helper.add_flow_with_next(datapath, table_id=self.ingress_table_id,
                                      priority=self.service_priority, match=match_back,
                                      actions=actions_back, idle_timeout=self.IDLE_TIME)
        # inside - outside go-to-next (Table 0)
        ofp_helper.add_flow_goto_next(datapath, table_id=self.ingress_table_id,
                                      priority=self.service_priority, match=match,
                                      idle_timeout=self.IDLE_TIME)
        # outside - inside out-port (Table 3)
        ofp_helper.add_flow(datapath, table_id=self.forward_table_id,
                            priority=self.service_priority, match=forward_match_back,
                            actions=forward_actions_back, idle_timeout=self.IDLE_TIME)
        # inside - outside write-out-port(Table 3)
        ofp_helper.add_write_flow_with_next(datapath, table_id=self.forward_table_id,
                                            priority=self.service_priority, match=match,
                                            actions=forward_actions, idle_timeout=self.IDLE_TIME)
        # inside - outside set-field( Table 4)
        ofp_helper.add_flow(datapath, table_id=self.egress_table_id,
                            priority=self.service_priority, match=match,
                            actions=actions, idle_timeout=self.IDLE_TIME)

        # send first packet back to switch
        d = None
        if buffer_id == ofproto.OFP_NO_BUFFER:
            d = data
        out = parser.OFPPacketOut(datapath=datapath, buffer_id=buffer_id,
                                  in_port=in_port, actions=actions, data=d)
        datapath.send_msg(out)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        if not service_config.service_status['nat']:
            return

        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']
        pkt = packet.Packet(msg.data)

        pkt_ethernet = pkt.get_protocol(ethernet.ethernet)
        pkt_arp = pkt.get_protocol(arp.arp)
        pkt_ip = pkt.get_protocol(ipv4.ipv4)
        pkt_tcp = pkt.get_protocol(tcp.tcp)
        pkt_udp = pkt.get_protocol(udp.udp)

        # if IP_TO_MAC_TABLE:
        #     print IP_TO_MAC_TABLE

        if in_port == self.wan_port:
            # Packets from WAN port
            if pkt_arp:
                if pkt_arp.opcode == arp.ARP_REQUEST:
                    arp_reply_pkt = self._arp_request_handler(pkt_arp)
                    if arp_reply_pkt is not None:
                        self._send_packet_to_port(datapath, in_port, arp_reply_pkt)
                    else:
                        # if arp_reply_pkt havent been generate, no need to send
                        pass
                elif pkt_arp.opcode == arp.ARP_REPLY:
                    self._arp_reply_handler(pkt_arp)
            else:
                # DNAT Part
                pass
        else:
            # Packets from LAN port
            if pkt_ip:
                if (self._in_private_subnetwork(pkt_ip.dst) and
                        pkt_ip.dst != str(self.private_gateway)):
                    # These packets are just in private network
                    # l2switch will handle it
                    return

                ip_dst = pkt_ip.dst
                if (self._is_public(ip_dst) and not
                        self._in_public_ip_subnetwork(ip_dst)):
                    # If the ip_dst of packet is public ip and on Internet
                    target_ip = self.public_gateway
                elif self._in_public_ip_subnetwork(ip_dst):
                    # If the ip_dst of packet is in public subnetwork of NAT
                    target_ip = ip_dst
                else:
                    return

                # Sending ARP request to Gateway
                arp_req_pkt = nat_helper.broadcast_arp_request(src_mac=self.mac_on_wan,
                                                               src_ip=self.public_ip,
                                                               target_ip=target_ip)
                self._send_packet_to_port(datapath, self.wan_port, arp_req_pkt)

                if pkt_tcp:
                    if target_ip in IP_TO_MAC_TABLE:
                        self._private_to_public(datapath=datapath,
                                                buffer_id=msg.buffer_id,
                                                data=msg.data,
                                                in_port=in_port,
                                                out_port=self.wan_port,
                                                pkt_ethernet=pkt_ethernet,
                                                pkt_ip=pkt_ip,
                                                pkt_tcp=pkt_tcp)
                elif pkt_udp:
                    if target_ip in IP_TO_MAC_TABLE:
                        self._private_to_public(datapath=datapath,
                                                buffer_id=msg.buffer_id,
                                                data=msg.data,
                                                in_port=in_port,
                                                out_port=self.wan_port,
                                                pkt_ethernet=pkt_ethernet,
                                                pkt_ip=pkt_ip,
                                                pkt_udp=pkt_udp)
            elif pkt_arp:
                if pkt_arp.opcode == arp.ARP_REQUEST:
                    arp_reply_pkt = self._arp_request_handler(pkt_arp)
                    self._send_packet_to_port(datapath, in_port, arp_reply_pkt)
                elif pkt_arp.opcode == arp.ARP_REPLY:
                    pass


class SNATRest(ControllerBase):
    def __init__(self, req, link, data, **config):
        super(SNATRest, self).__init__(req, link, data, **config)
        self.snat_app = data[nat_instance_name]

    @route('post_nat_config_init', urls.post_nat_config_init, methods=['POST'])
    def nat_config_init(self, req, **kwargs):
        save_dict = {}

        save_dict['wan_port'] = 1
        save_dict['public_ip'] = IPAddress('192.168.2.144')
        save_dict['public_gateway'] = IPAddress('192.168.2.1')
        save_dict['public_ip_subnetwork'] = IPNetwork('192.168.2.0/24')

        network = '192.168.8.0/24'
        save_dict['private_subnetwork'] = IPNetwork(network)
        save_dict['private_gateway'] = IPNetwork(network)[1]

        save_dict['broadcast_ip'] = IPAddress('192.168.8.255')
        save_dict['dns_ip'] = IPAddress('8.8.8.8')

        save_dict['mac_on_dhcp'] = '08:00:27:b8:0f:8d'
        save_dict['mac_on_wan'] = '00:0e:c6:87:a6:fb'
        save_dict['mac_on_lan'] = '00:0e:c6:87:a6:fa'

        if nat_settings.save(save_dict):
            pp = pprint.PrettyPrinter(indent=2)
            pp.pprint(save_dict)
            return Response(status=200)
        else:
            return Response(status=400)

    @route('put_nat_config_save', urls.put_nat_config_save, methods=['PUT'])
    def nat_config_save(self, req, **kwargs):
        json_body = json.loads(req.body)

        save_dict = nat_settings.load()
        if save_dict is None:
            save_dict = {}

        save_dict['wan_port'] = json_body.get('wanPort')
        save_dict['public_ip'] = IPAddress(json_body.get('publicIP'))

        public_gateway = IPAddress(json_body.get('publicGateway'))
        save_dict['public_gateway'] = IPAddress(public_gateway)
        save_dict['public_ip_subnetwork'] = IPNetwork(public_gateway + '/24')

        net = json_body.get('privateNetwork') + '/24'
        save_dict['private_subnetwork'] = IPNetwork(net)
        save_dict['private_gateway'] = IPNetwork(net)[1]

        save_dict['broadcast_ip'] = IPNetwork(net)[255]
        save_dict['dns_ip'] = IPAddress('8.8.8.8')

        save_dict['mac_on_dhcp'] = '08:00:27:b8:0f:8d'
        save_dict['mac_on_wan'] = '00:0e:c6:87:a6:fb'
        save_dict['mac_on_lan'] = '00:0e:c6:87:a6:fa'

        if nat_settings.save(save_dict):
            pp = pprint.PrettyPrinter(indent=2)
            pp.pprint(save_dict)
            return Response(status=200)
        else:
            return Response(status=400)

    @route('get_nat_config', urls.get_nat_config, methods=['GET'])
    def nat_config_get(self, req, **kwargs):
        settings = nat_settings.load()
        dic = {}
        # local network
        ip = settings['private_subnetwork'].ip
        mask = settings['private_subnetwork'].netmask
        mask_len = mask.bits().replace('.', '').find('0')
        dic['privateNetwork'] = str(ip) + '/' + str(mask_len)

        dic['wanPort'] = settings['wan_port']
        dic['publicGateway'] = str(settings['public_gateway'])
        dic['publicIP'] = str(settings['public_ip'])

        body = json.dumps(dic)
        return Response(status=200, content_type='application/json', body=body)

    @route('get_dhcp_config', urls.get_dhcp_config, methods=['GET'])
    def dhcp_config_get(self, req, **kwargs):
        dhcp_settings = nat_settings.load()
        dic = {}

        dic['privateGateway'] = str(dhcp_settings['private_gateway'])
        dic['broadcastIP'] = str(dhcp_settings['broadcast_ip'])
        dic['dnsIP'] = str(dhcp_settings['dns_ip'])
        dic['macDhcp'] = str(dhcp_settings['mac_on_dhcp'])

        body = json.dumps(dic)
        return Response(status=200, content_type='application/json', body=body)
