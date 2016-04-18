"""Statistic."""

database_app_record = {}
database_flow_record = []
database_member_record = {}
database_group_record = {}


class Application_recored:

    """class for application."""

    def __init__(self, appname, rate):
        """Initial Setting method."""
        self.name = appname
        self.rate = rate
        self.exist = 0


class Memeber_record:

    """class for member record."""

    def __init__(self, id, group):
        """Initial Setting method."""
        self.id = id
        self.group_id = group
        self.flow = []
        self.apprate = {}


class Group_record:

    """class for group record."""

    def __init__(self, group_id):
        """Initial Setting method."""
        self.group_id = group_id
        self.member = {}
        self.apprate = {}
        self.total = 0.0
