import json
from webob import Response
from ryu.base import app_manager
from ryu.app.wsgi import ControllerBase, WSGIApplication, route
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types
from ryu.lib.packet import udp

# store which url is blocking
import data
from route import urls

parental_control_instance_name = 'parental_control_api_app'


class ParentalControl(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    _CONTEXTS = {'wsgi': WSGIApplication}

    def __init__(self, *args, **kwargs):
        super(ParentalControl, self).__init__(*args, **kwargs)
        self.switches = {}
        self.mac_to_port = {}
        wsgi = kwargs['wsgi']
        wsgi.register(ParentalControlController,
                      {parental_control_instance_name: self})
        self.topology_api_app = self

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

        # foward DNS packet to controller
        match = parser.OFPMatch({'udp_dst': 53})
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 100, match, actions)

    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]
        if buffer_id:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                    priority=priority, match=match,
                                    instructions=inst)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, instructions=inst)
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        if ev.msg.msg_len < ev.msg.total_len:
            self.logger.debug("packet truncated: only %s of %s bytes",
                              ev.msg.msg_len, ev.msg.total_len)
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            # ignore lldp packet
            return
        dst = eth.dst
        src = eth.src

        dpid = datapath.id
        self.mac_to_port.setdefault(dpid, {})

        # learn a mac address to avoid FLOOD next time.
        self.mac_to_port[dpid][src] = in_port

        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            out_port = ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]

        # install a flow to avoid packet_in next time
        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst)
            # verify if we have a valid buffer_id, if yes avoid to send both
            # flow_mod & packet_out
            if msg.buffer_id != ofproto.OFP_NO_BUFFER:
                self.add_flow(datapath, 1, match, actions, msg.buffer_id)
                return
            else:
                self.add_flow(datapath, 1, match, actions)

        # parse DNS packet to get protocol
        udp_info = pkt.get_protocols(udp.udp)
        is_DNS = udp_info and (udp_info[0].dst_port == 53)
        if is_DNS:
            pkt.serialize()
            dns_msg = msg.data[54:].encode("hex")
            dns_msg = dns_msg[:-10]
            request_url = self.parse_DNS(dns_msg)
            print 'DNS packet: ' + request_url

        if not is_DNS or (is_DNS and request_url not in data.blocking_url):
            # send packet back
            if is_DNS:
                print 'send DNS back to switch'
            data = None
            if msg.buffer_id == ofproto.OFP_NO_BUFFER:
                data = msg.data

                out = parser.OFPPacketOut(datapath=datapath,
                                          buffer_id=msg.buffer_id,
                                          in_port=in_port,
                                          actions=actions,
                                          data=data)
                datapath.send_msg(out)

    # DNS packet parser
    def parse_DNS(self, hex_data):
        # convert hex to integer array
        iter_hex_data = iter(hex_data)
        hex_to_int = []
        for x in iter_hex_data:
            hex_to_int.append(int(x+next(iter_hex_data), 16))

        # traslate integer array to string
        url = ''
        iter_int_data = iter(hex_to_int)
        for num in iter_int_data:
            count = num
            while (count > 0):
                url += chr(next(iter_int_data))
                count = count-1
            url += '.'

        return url[:-1]


class ParentalControlController(ControllerBase):
    def __init__(self, req, link, data, **config):
        super(ParentalControlController, self).__init__(req,
                                                        link, data, **config)
        self.parental_control_spp = data[parental_control_instance_name]

    @route('firewall', urls.url_get_prnt_ctrl, methods=['GET'])
    def get_block_url(self, req, **kwargs):
        dic = {'block_url': data.blocking_url}
        body = json.dumps(dic)
        return Response(status=200, content_type='application/json', body=body)

    @route('firewall', urls.url_set_prnt_ctrl, methods=['PUT'])
    def update_block_url(self, req, **kwargs):
        content = req.body
        json_data = json.loads(content)

        if 'option' not in json_data or 'url' not in json_data:
            return Response(status=400)

        option = str(json_data.get('option'))
        url = str(json_data.get('url'))

        if option == 'add':
            if url not in data.blocking_url:
                data.blocking_url.append(url)
            return Response(status=202)
        elif option == 'delete':
            if url in data.blocking_url:
                data.blocking_url.remove(url)
                return Response(status=202)

        return Response(status=400)
