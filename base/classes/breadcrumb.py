from ..services import error_service
from django.urls import reverse
from base.classes.util.env_helper import EnvHelper, Log

log = Log()
env = EnvHelper()


class Breadcrumb:
    label = None
    url = None
    icon = None
    icon_only = None
    active_flag = None

    def is_active(self):
        try:
            if self.url:
                return self.url == env.request.path
            else:
                return False
        except Exception as ee:
            error_service.record(ee)
            return False
    
    def __init__(self, breadcrumb_dict):
        self.label = breadcrumb_dict.get("label", None)
        self.url = breadcrumb_dict.get("url", None)
        self.icon = breadcrumb_dict.get("icon", None)
        self.icon_only = breadcrumb_dict.get("icon_only", None)
        self.active_flag = breadcrumb_dict.get("active", False)

        # Breadcrumbs marked as active will lose their active flag on subsequent load if not last in list
        try:
            reload_ind = breadcrumb_dict.get("reload_ind")
            if reload_ind:
                ii, of = reload_ind.split("/")
                if ii != of:
                    self.active_flag = False
        except:
            pass

        # Turn named URL into actual URL
        if self.url:

            if "/" not in self.url:
                self.url = reverse(self.url)


