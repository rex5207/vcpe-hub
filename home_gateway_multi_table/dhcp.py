"""
 Simple DHCP Server
"""
# import logging

from ryu.ofproto import ether
from ryu.ofproto import inet
from ryu.ofproto import ofproto_v1_3
from ryu.base import app_manager
from ryu.lib.packet import packet, dhcp, udp, ipv4, ethernet
from ryu.controller.handler import set_ev_cls
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller import ofp_event
from ryu.lib import addrconv

from config import service_config
from models import nat_settings
from helper import ofp_helper


class SimpleDHCPServer(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SimpleDHCPServer, self).__init__(*args, **kwargs)
        self.table_id = service_config.service_sequence['dhcp']
        self.service_priority = service_config.service_priority['dhcp']

        self.dhcp_msg_type_code = {
            1: 'DHCP_DISCOVER',
            2: 'DHCP_OFFER',
            3: 'DHCP_REQUEST',
            4: 'DHCP_DECLINE',
            5: 'DHCP_ACK',
            6: 'DHCP_NAK',
            7: 'DHCP_RELEASE',
            8: 'DHCP_INFORM',
        }

        dhcp_settings = nat_settings.load()
        self.private_gateway = dhcp_settings['private_gateway']
        self.broadcast_ip = dhcp_settings['broadcast_ip']
        self.private_subnetwork = dhcp_settings['private_subnetwork']
        self.ip_pool_list = list(self.private_subnetwork)

        print self.ip_pool_list
        print self.broadcast_ip

        self.dns_ip = dhcp_settings['dns_ip']
        self.mac_on_dhcp = dhcp_settings['mac_on_dhcp']
        self.mac_to_client_ip = {}
        assert self.private_gateway in self.ip_pool_list

        # self.ip_pool_list.remove(self.private_gateway)
        self.ip_pool_list.remove(self.private_gateway)
        self.ip_pool_list.remove(self.broadcast_ip)
        self.ip_pool_list.remove(self.private_subnetwork[0])

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # install DHCP request packets flow entry
        # and dhcp dont need to go to next table
        match_dhcp_request = parser.OFPMatch(eth_type=ether.ETH_TYPE_IP,
                                             ip_proto=inet.IPPROTO_UDP,
                                             udp_src=68, udp_dst=67)
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        ofp_helper.add_flow(datapath, table_id=self.table_id,
                            priority=self.service_priority, match=match_dhcp_request,
                            actions=actions, idle_timeout=0)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        if not service_config.service_status['dhcp']:
            return

        msg = ev.msg
        datapath = msg.datapath
        # ofproto = datapath.ofproto
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        dhcpPacket = pkt.get_protocol(dhcp.dhcp)

        if not dhcpPacket:
            return

        if dhcpPacket:
            msgType = ord(dhcpPacket.options.option_list[0].value)
            try:
                self.logger.info("Receive DHCP message type %s" %
                                 (self.dhcp_msg_type_code[msgType]))
            except KeyError:
                self.logger.info("Receive UNKNOWN DHCP message type %d" %
                                 (msgType))

            if msgType == dhcp.DHCP_DISCOVER:
                self.handle_dhcp_discover(dhcpPacket, datapath, in_port)
            elif msgType == dhcp.DHCP_REQUEST:
                self.handle_dhcp_request(dhcpPacket, datapath, in_port)
                self.logger.info(self.mac_to_client_ip)
            else:
                pass

    def handle_dhcp_discover(self, dhcp_pkt, datapath, port):
        # Choose a IP form IP pool list
        client_ip_addr = str(self.ip_pool_list.pop())
        self.mac_to_client_ip[dhcp_pkt.chaddr] = client_ip_addr

        # send dhcp_offer message.
        dhcp_offer_msg_type = '\x02'
        self.logger.info("Send DHCP message type %s" %
                         (self.dhcp_msg_type_code[ord(dhcp_offer_msg_type)]))

        msg_option = dhcp.option(tag=dhcp.DHCP_MESSAGE_TYPE_OPT,
                                 value=dhcp_offer_msg_type)
        options = dhcp.options(option_list=[msg_option])
        hlen = len(addrconv.mac.text_to_bin(dhcp_pkt.chaddr))

        dhcp_pkt = dhcp.dhcp(hlen=hlen,
                             op=dhcp.DHCP_BOOT_REPLY,
                             chaddr=dhcp_pkt.chaddr,
                             yiaddr=client_ip_addr,
                             giaddr=dhcp_pkt.giaddr,
                             xid=dhcp_pkt.xid,
                             options=options)

        self._send_dhcp_packet(datapath, dhcp_pkt, port)

    def handle_dhcp_request(self, dhcp_pkt, datapath, port):
        # send dhcp_ack message.
        dhcp_ack_msg_type = '\x05'
        self.logger.info("Send DHCP message type %s" %
                         (self.dhcp_msg_type_code[ord(dhcp_ack_msg_type)]))

        subnet_option = dhcp.option(tag=dhcp.DHCP_SUBNET_MASK_OPT,
                                    value=addrconv.ipv4.text_to_bin(self.private_subnetwork.netmask))
        gw_option = dhcp.option(tag=dhcp.DHCP_GATEWAY_ADDR_OPT,
                                value=addrconv.ipv4.text_to_bin(self.private_gateway))
        dns_option = dhcp.option(tag=dhcp.DHCP_DNS_SERVER_ADDR_OPT,
                                 value=addrconv.ipv4.text_to_bin(self.dns_ip))
        time_option = dhcp.option(tag=dhcp.DHCP_IP_ADDR_LEASE_TIME_OPT,
                                  value='\xFF\xFF\xFF\xFF')
        msg_option = dhcp.option(tag=dhcp.DHCP_MESSAGE_TYPE_OPT,
                                 value=dhcp_ack_msg_type)
        id_option = dhcp.option(tag=dhcp.DHCP_SERVER_IDENTIFIER_OPT,
                                value=addrconv.ipv4.text_to_bin(self.private_gateway))

        options = dhcp.options(option_list=[msg_option, id_option,
                               time_option, subnet_option,
                               gw_option, dns_option])
        hlen = len(addrconv.mac.text_to_bin(dhcp_pkt.chaddr))

        # Look up IP by using client mac address
        client_ip_addr = self.mac_to_client_ip[dhcp_pkt.chaddr]

        dhcp_pkt = dhcp.dhcp(op=dhcp.DHCP_BOOT_REPLY,
                             hlen=hlen,
                             chaddr=dhcp_pkt.chaddr,
                             yiaddr=client_ip_addr,
                             giaddr=dhcp_pkt.giaddr,
                             xid=dhcp_pkt.xid,
                             options=options)

        self._send_dhcp_packet(datapath, dhcp_pkt, port)

    def _send_dhcp_packet(self, datapath, dhcp_pkt, port):
        pkt = packet.Packet()
        pkt.add_protocol(ethernet.ethernet
                         (src=self.mac_on_dhcp,
                          dst="ff:ff:ff:ff:ff:ff"))
        pkt.add_protocol(ipv4.ipv4
                         (src=self.private_gateway,
                          dst="255.255.255.255",
                          proto=17))
        pkt.add_protocol(udp.udp(src_port=67, dst_port=68))
        pkt.add_protocol(dhcp_pkt)

        self._send_packet(datapath, pkt, port)

    def _send_packet(self, datapath, pkt, port):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        pkt.serialize()
        # self.logger.info("packet-out %s" % (pkt,))
        data = pkt.data
        actions = [parser.OFPActionOutput(port=port)]
        out = parser.OFPPacketOut(datapath=datapath,
                                  buffer_id=ofproto.OFP_NO_BUFFER,
                                  in_port=ofproto.OFPP_CONTROLLER,
                                  actions=actions,
                                  data=data)
        datapath.send_msg(out)
