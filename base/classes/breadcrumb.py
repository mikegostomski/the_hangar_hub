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
            log.error(ee)
            return False
    
    def __init__(self, breadcrumb_dict):
        self.label = breadcrumb_dict.get("label", None)
        self.url = breadcrumb_dict.get("url", None)
        self.icon = breadcrumb_dict.get("icon", None)
        self.icon_only = breadcrumb_dict.get("icon_only", False)
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


    @classmethod
    def clear(cls):
        env.set_session_variable("base_breadcrumbs", [])
        env.set_page_scope("base_breadcrumbs_inti", True)

    @classmethod
    def add(
            cls,
            label,
            url=None,
            icon=None, icon_only=False,
            active=False,
            reset=False,
            duplicate=False,
            append_only=False
    ):
        bcs = cls.get()
        if reset or not bcs:
            bcs = []

            # Reset the breadcrumb list (optionally start with a Home link)
            if reset and "home" in str(reset).lower():
                home = {
                    "label": "Home",
                    "url": "/",
                }
                if "icon" in str(reset).lower():  # and
                    home["icon"] = "bi-house"
                    if "only" in str(reset).lower():
                        home["icon_only"] = True
                bcs.append(home)

        if type(url) in [tuple, list] and len(url) > 1:
            url = reverse(url[0], args=url[1:])

        if bcs and not duplicate:
            # If breadcrumb already exists, remove all breadcrumbs after it
            # Assumption: the user has returned to this page from a page represented by a subsequent breadcrumb
            if label in [x.get("label") for x in bcs]:
                revised = []
                for bc in bcs:
                    if bc.get("label") != label:
                        revised.append(bc)
                    else:
                        break
                bcs = revised

        # If append_only, only add the BC if there are existing BCs
        if bcs or not append_only:
            bcs.append({
                "label": label,
                "url": url,
                "active": active,
                "icon": icon,
                "icon_only": icon_only,
            })
        return env.set_session_variable("base_breadcrumbs", bcs)

    @classmethod
    def get(cls):
        init_ind = bool(env.get_page_scope("base_breadcrumbs_inti"))
        bcs = env.get_session_variable("base_breadcrumbs", [])
        if not init_ind:
            ii = 0
            of = len(bcs)
            for bc in bcs:
                ii += 1
                bc["reload_ind"] = f"{ii}/{of}"
        return env.get_session_variable("base_breadcrumbs", [])

