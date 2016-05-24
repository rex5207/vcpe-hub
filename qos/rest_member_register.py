"""Project for Rest API (Group Setting)."""
import json

from ryu.base import app_manager
from ryu.app.wsgi import ControllerBase, WSGIApplication, route
from webob import Response

from setting.db import data_collection
from setting.db import collection

from route import urls

url = '/handle_member_info/member/{memberid}'
get_member_info_instance_name = 'get_member_info_api_app'


class member_register(app_manager.RyuApp):

    """Get_Member_Info class."""

    _CONTEXTS = {'wsgi': WSGIApplication}

    def __init__(self, *args, **kwargs):
        """Initial Setting method."""
        super(member_register, self).__init__(*args, **kwargs)
        self.switches = {}
        wsgi = kwargs['wsgi']
        wsgi.register(member_register_rest,
                      {get_member_info_instance_name: self})

    def save_member_to_database(self, memberid, groupid):
        """Save Member data to database method."""
        if data_collection.member_list.get(memberid) is None:
            print 1
            member = collection.Member(memberid, groupid)
            data_collection.member_list.update({memberid: member})
            data_collection.group_list.get(groupid).members.append(memberid)
            print member.name, member.group_id
        else:
            print 2
            member = data_collection.member_list.get(memberid)
            member.name = memberid
            if member.group_id != groupid:
                if member.group_id != "whole":
                    data_collection.group_list.get(member.group_id).members.remove(memberid)
                member.group_id = groupid
                data_collection.group_list.get(groupid).members.append(memberid)
            print member.name, member.group_id


# curl -X PUT -d '{"group_id" : "group_1"}'
#                http://127.0.0.1:8080/handle_member_info/member/user1
class member_register_rest(ControllerBase):

    """Get_Member_Info_Rest class."""

    def __init__(self, req, link, data, **config):
        """Initial Setting method."""
        super(member_register_rest, self).__init__(req, link, data, **config)
        self.get_member_info = data[get_member_info_instance_name]

    @route('member_data', url, methods=['PUT'])
    def put_member_data_(self, req, **kwargs):
        """Put Member data method."""
        memberid = str(kwargs['memberid'])
        group_id = req.body
        json_link = json.loads(group_id)
        groupid = str(json_link.get('group_id'))
        if data_collection.group_list.get(groupid) is None:
            return Response(status=404, body=str('not ok'))
        else:
            self.get_member_info.save_member_to_database(memberid, groupid)
            return Response(content_type='application/json',
                            body=str('Success'))

    @route('member_list', urls.url_member_list, methods=['PUT'])
    def get_member_list(self, req, **kwargs):
        dic = {}
        for key in data_collection.member_list.keys():
            member_info = {}
            member_data = data_collection.member_list[key]
            member_info.update({'IP': member_data.ip})
            member_info.update({'MAC': key})
            member_info.update({'Group': member_data.group_id})

            dic.update({key: member_info})
        body = json.dumps(dic)
        return Response(content_type='application/json', body=body)
