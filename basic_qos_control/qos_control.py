"""Prject for Qos Control."""

from ryu.base import app_manager
from ryu.lib import hub
from ryu.topology.api import get_switch
from ryu.controller.event import EventBase
from ryu.controller.handler import set_ev_cls

from setting.ratelimitation.setting import setup
from setting.ratelimitation.utils import control

class Qos_UpdateEvent(EventBase):
    def __init__(self, msg):
        self.msg = msg

class QosControl(app_manager.RyuApp):

    """Qos Control Class."""

    def __init__(self, *args, **kwargs):
        """Initial Setting method."""
        super(QosControl, self).__init__(*args, **kwargs)
        # self.monitor_thread = hub.spawn(self._monitor)
        self.topology_api_app = self
        # hdlr = logging.FileHandler('sdn_log_dynamic_control.log')
        # self.logger.addHandler(hdlr)

    @set_ev_cls(Qos_UpdateEvent)
    def _control_manual(self, ev):
        print ('[INFO QosControl._control_manual] %s' % ev.msg)
        print 'INFO [qos_control._control_manual]\n  >>  manual control begin'
        setting = setup.ratelimite_setup_for_specialcase
        for group in setting.keys():
            for app in setting.get(group).keys():
                if setting.get(group).get(app).get('state') == 'up':
                    control.set_ratelimite_for_app(app, setting.get(group).get(app).get("meter_id"), group, 'up', 'm')
                else:
                    control.set_ratelimite_for_app(app, setting.get(group).get(app).get("meter_id"), group, 'down', 'm')
                    setting.get(group).pop(app)

        setting_m = setup.ratelimite_setup_for_specialcase_member
        for group in setting_m.keys():
            for mac in setting_m.get(group).keys():
                if setting_m.get(group).get(mac).get('state') == 'up':
                    control.set_ratelimite_for_member(mac, setting_m.get(group).get(mac).get("meter_id"), group, 'up', 'm')
                else:
                    control.set_ratelimite_for_member(mac, setting_m.get(group).get(mac).get("meter_id"), group, 'down', 'm')
                    setting_m.get(group).pop(mac)
