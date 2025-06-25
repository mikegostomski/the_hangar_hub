from base.classes.util.env_helper import EnvHelper, Log
from base.classes.auth.session import Auth

log = Log()
env = EnvHelper()


class Waitlist:
    airport = None
    applications = None

    def num_waiting(self):
        return len(self.applications)

    def current_user_position(self):
        cu = Auth.current_user()
        ii = 0
        for aa in self.applications:
            ii += 1
            if aa.user == cu:
                return ii
        return 0

    def priority_groups(self):
        if not self.applications:
            return {}
        return list(self.applications[0].wl_group_options().keys())

    def applications_per_group(self):
        groups = self.priority_groups()
        counts = {x: 0 for x in groups}
        for aa in self.applications:
            this_group = aa.wl_group_code
            if this_group in groups:
                counts[this_group] += 1
        return counts

    def reindex_applications(self, group_code=None, restore_default=False):
        if not self.applications:
            return

        if restore_default:
            self.applications.sort(key=lambda x: x.wl_reset_sort_string)

        if group_code:
            groups = [group_code]
        else:
            groups = self.priority_groups()

        indexes = {x: 0 for x in groups}
        for aa in self.applications:
            this_group = aa.wl_group_code
            if this_group in groups:
                this_index = indexes[this_group] + 1
                indexes[this_group] += 1
                if aa.wl_index != this_index:
                    aa.wl_index = this_index
                    aa.save()

    def __init__(self, airport):
        log.trace([airport])
        self.airport = airport
        self._query_applications()
        self.reindex_applications()

    def _query_applications(self):
        self.applications = list(self.airport.applications.filter(status_code="L"))
        if self.applications:
            self.applications.sort(key=lambda x: x.wl_sort_string)
