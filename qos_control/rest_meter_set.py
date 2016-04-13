"""Project for Rest API (Group Setting)."""
import json

from ryu.base import app_manager
from ryu.app.wsgi import ControllerBase, WSGIApplication, route
from webob import Response
from ryu.topology.api import get_switch

from setting.db import data_collection
from setting.utils import ofputils, log

from route import urls

#url = '/set_meter_info/{meterid}'
set_meter_info_instance_name = 'set_meter_info_api_app'


class MeterSetup(app_manager.RyuApp):

    """Get_Member_Info class."""

    _CONTEXTS = {'wsgi': WSGIApplication}

    def __init__(self, *args, **kwargs):
        """Initial Setting method."""
        super(MeterSetup, self).__init__(*args, **kwargs)
        self.topology_api_app = self
        wsgi = kwargs['wsgi']
        wsgi.register(MeterSetupRest,
                      {set_meter_info_instance_name: self})
        data_collection.meter_list.update({"drop": "-1"})

    def set_meter_to_switches(self, meterid, bandwdith, command):
        """Save Member data to database method."""
        switch_list = get_switch(self.topology_api_app, None)
        for dp in switch_list:
            print dp.dp.id, type(meterid), type(bandwdith), int(bandwdith), int(meterid)
            ofputils.set_meter_entry(dp.dp, int(bandwdith), int(meterid), command)

        if command == 'ADD':
            data_collection.meter_list.update({bandwdith: meterid})
        elif command == 'DELETE':
            data_collection.meter_list.pop(bandwdith)

        # log.log_backup_w('datacollection_meterlist.pkl', data_collection.meter_list)


# curl -X PUT -d '{"bandwidth" : "8192", "command": "ADD"}'
#               http://127.0.0.1:8080/set_meter_info/2
class MeterSetupRest(ControllerBase):

    """Get_Member_Info_Rest class."""

    def __init__(self, req, link, data, **config):
        """Initial Setting method."""
        super(MeterSetupRest, self).__init__(req, link, data, **config)
        self.get_member_info = data[set_meter_info_instance_name]

    @route('meter_data', urls.url_meter_set, methods=['PUT'])
    def set_meter_data_(self, req, **kwargs):
        """Put Member data method."""
        meterid = str(kwargs['meterid'])
        content = req.body
        json_link = json.loads(content)
        bandwidth = str(json_link.get('bandwidth'))
        command = str(json_link.get('command'))
        self.get_member_info.set_meter_to_switches(meterid, bandwidth, command)
        return Response(content_type='application/json',
                            body=str('Success'))
