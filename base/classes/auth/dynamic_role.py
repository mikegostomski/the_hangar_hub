from base.classes.util.env_helper import EnvHelper

env = EnvHelper()

security_admin_roles = ['developer', 'security']

power_user_roles = ['developer', 'admin']
super_user_roles = ['developer']

proxy_roles = ['proxy']

impersonation_roles_stage = ['developer', 'admin', 'security']
impersonation_roles_prod = ['developer']

contact_admin_roles = ['developer', 'admin', 'contact_admin']


class DynamicRole:

    @staticmethod
    def get(role_string):
        if '~' not in role_string:
            return [role_string]

        if 'power' in role_string:
            return power_user_roles

        if 'super' in role_string:
            return super_user_roles

        if 'imperson' in role_string:
            if env.is_prod:
                return impersonation_roles_prod
            else:
                return impersonation_roles_stage
        if 'contact' in role_string:
            return contact_admin_roles
        if 'security' in role_string:
            return security_admin_roles
        if 'proxy' in role_string:
            return proxy_roles

        return []

    def __init__(self):
        pass
