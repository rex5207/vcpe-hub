meter_and_group = {}
have_control = 0
'''
group - "meter_list":[11,12,...]
      - "Meter_setup":[[Meter_setup], [Meter_setup], ....]
'''
class Meter_setup:

    """class for member record."""

    def __init__(self, rate, app, group, meter_id):
        """Initial Setting method."""
        self.app = app
        self.group_id = group
        self.meter = meter_id
        self.apprate = rate
