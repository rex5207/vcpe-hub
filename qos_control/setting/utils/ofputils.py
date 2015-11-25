"""Methods for flow & meter entries setup."""


def add_flow(datapath, priority, match, actions, buffer_id=None):
    """Add flows."""
    # print 'add flows'
    ofproto = datapath.ofproto
    parser = datapath.ofproto_parser

    inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]

    if buffer_id:
        mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                priority=priority, match=match,
                                idle_timeout=10, instructions=inst)
    else:
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                idle_timeout=10, match=match, instructions=inst)
    datapath.send_msg(mod)


def set_meter_entry(datapath, bandwidth, id, mod):
        """Set meter entries."""
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        command = None
        if mod == 'ADD':
            command = ofproto.OFPMC_ADD
            # add_flow_meta(datapath, 10, id, id)
        elif mod == 'MODIFY':
            command = ofproto.OFPMC_MODIFY
            # add_flow_meta(datapath, 10, id, id)
        elif mod == 'DELETE':
            command = ofproto.OFPMC_DELETE
            # del_flow_meta(datapath, 10, id, id)

        # Policing for Scavenger class
        band = parser.OFPMeterBandDrop(rate=bandwidth,
                                       burst_size=1024)
        req = parser.OFPMeterMod(datapath, command,
                                 ofproto.OFPMF_KBPS, id, [band])
        datapath.send_msg(req)

        # if mod == 'ADD':
        #     add_flow_meta(datapath, 10, id, id)


def add_flow_for_ratelimite(datapath, priority, match, actions, meter, state, buffer_id=None):
    """add flows for rate control."""
    ofproto = datapath.ofproto
    parser = datapath.ofproto_parser
    inst = []
    timeout = 10
    if state == 'up':
        if meter == -1:
            timeout = 0
            actions = []
            inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        else:
            inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions),
                    parser.OFPInstructionMeter(meter)]
    else:
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]

    if buffer_id:
        mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                priority=priority, match=match,
                                idle_timeout=timeout, instructions=inst)
        if state == 'down':
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                    priority=priority, match=match,
                                    idle_timeout=timeout, hard_timeout=10,
                                    instructions=inst)
    else:
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                idle_timeout=timeout, match=match, instructions=inst)
        if state == 'down':
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    idle_timeout=timeout, hard_timeout=10,
                                    match=match, instructions=inst)
    datapath.send_msg(mod)


def add_flow_meta(datapath, priority, meta, meter_id, buffer_id=None):
        """Add meta data in table 1."""
        parser = datapath.ofproto_parser
        match = parser.OFPMatch(metadata = meta)
        inst = [parser.OFPInstructionMeter(meter_id)]
        if buffer_id:
            mod = parser.OFPFlowMod(datapath=datapath, table_id=1, buffer_id=buffer_id,
                                    priority=priority, match=match,
                                    instructions=inst)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, table_id=1, priority=priority,
                                    match=match, instructions=inst)
        datapath.send_msg(mod)

def del_flow_meta(datapath, priority, meta, meter_id, buffer_id=None):
        """Del meta data in table 1."""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        match = parser.OFPMatch(metadata = meta)
        inst = [parser.OFPInstructionMeter(meter_id)]
        if buffer_id:
            mod = parser.OFPFlowMod(datapath=datapath, table_id=1, buffer_id=buffer_id,
                                    priority=priority, match=match,
                                    command=ofproto.OFPFC_DELETE,
                                    instructions=inst)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, table_id=1, priority=priority,
                                    command=ofproto.OFPFC_DELETE_STRICT, match=match,
                                    instructions=inst)
        datapath.send_msg(mod)
