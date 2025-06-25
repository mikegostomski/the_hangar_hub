from django.db import models
from base.classes.util.env_helper import EnvHelper, Log
from base.classes.util.caller_data import CallerData
from django.utils.html import mark_safe
from base.services import validation_service, message_service
import traceback

log = Log()
env = EnvHelper()


class Error(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)

    """Record an unexpected error"""
    path = models.CharField(
        max_length=128,
        blank=False,
        null=False,
    )

    parameters = models.CharField(
        max_length=500,
        blank=True,
        null=True,
    )

    code_detail = models.CharField(
        max_length=128,
        help_text="file, function, and line number of error",
        blank=True,
        null=True,
    )

    # Associated user account
    user = models.ForeignKey("auth.User", models.SET_NULL, related_name="errors", blank=True, null=True)
    auth_description = models.CharField(max_length=80)

    status_code = models.CharField(
        max_length=1,
        blank=False,
        null=False,
        default="N",
    )

    error_friendly = models.CharField(
        max_length=128, help_text="Error that the user saw", blank=True, null=True
    )
    error_system = models.CharField(
        max_length=128, help_text="Actual system error", blank=True, null=True
    )
    debug_info = models.CharField(
        max_length=128, help_text="Additional debug info", blank=True, null=True
    )
    stacktrace = models.TextField(help_text="StackTrace", blank=True, null=True)
    browser = models.CharField(
        max_length=200, help_text="Browser info", blank=True, null=True
    )



    def error_friendly_bi(self):
        # Convert bi- to icon when displayed on screen (admin error page)
        if self.error_friendly:
            words = []
            for ww in self.error_friendly.split():
                if ww.startswith("bi-"):
                    if ww not in ["bi-spin", "bi-pulse"]:
                        words.append(f"""<span class="bi {ww}" aria-hidden="true"></span>""")
                else:
                    words.append(ww)
            return " ".join(words)
        return self.error_friendly

    def stacktrace_html(self):
        if self.stacktrace:
            trace_lines = self.stacktrace.splitlines()
            if len(trace_lines) > 1:
                lines = [
                    f"<b>{trace_lines[0]}</b>",
                    f"""<i style="color:blue;cursor:pointer;" onclick="$('#e-st-{self.id}').removeClass('hidden');">""",
                    f"""show stacktrace</i>"""
                    f'<ul class="list-group hidden" id="e-st-{self.id}">',
                ]
                for ll in trace_lines[1:]:
                    lines.append(f"""<li class="list-group-item">{ll}</li>""")
                lines.append("</ul>")
                return "".join(lines)
        return self.stacktrace if self.stacktrace else ""

    def parameters_html(self):
        if self.parameters:
            if validation_service.has_unlikely_characters(self.parameters, unlikely_characters="`=\\<>;"):
                return self.parameters
            else:
                pp = self.parameters.strip("{}").replace("', '", "',<br /> '")
                return mark_safe(pp)
        return None

    @classmethod
    def record(cls, ee, debug_info=None):
        """Shortcut for when you want a detailed log of the error without posting an error message"""

        # During local development, post the error so it doesn't get overlooked
        if env.is_development:
            cls.unexpected(f"bi-bug Bug recorded: {ee}", ee, debug_info)
        else:
            cls.unexpected(None, ee, debug_info)

    @classmethod
    def unexpected(cls, error_display=None, error_system=None, debug_info=None):
        """
        Logs the error in the db, the log file, and posts an error on-screen
        """

        # Gather data
        src = CallerData().what_called("error")
        # if src == "decorators._wrapped_view()":
        #     src = CallerData().what_called("error")

        request = env.request
        path = request.path if request else '?'
        method = request.method if request else None

        try:
            browser = request.META["HTTP_USER_AGENT"]
        except:
            browser = "Unknown"

        # Don't record health-check errors
        if env.is_health_check:
            if error_display:
                log.error(f"HealthCheck: {error_display}", trace_error=False)
            if error_system:
                log.error(f"HealthCheck: {error_system}", trace_error=False)
            return

        # Include parameters in error log
        parameters = dict(env.parameters)
        if not parameters:
            parameters = None  # To avoid "{}"

        # Prevent logging of certain parameters
        else:
            # Mask out anything that we would never want auto-logged
            for kk in ["ssn", "password"]:
                if parameters.get(kk):
                    parameters[kk] = '*' * len(str(parameters.get(kk)))

        # Get user authentication description (logged-in, impersonated, proxied)
        user_label = env.get_session_variable("auth_user_description")

        # Get stacktrace
        stacktrace = traceback.format_exc(limit=10)

        # Log error in log file
        log.error(
            f"""\n
    \t*** UNEXPECTED ERROR ***
    \tSystem Error:   {error_system}
    \tFriendly Error: {error_display}
    \tDebug Info: {debug_info}
    \tBrowser: {browser}
    \tUser: {user_label}
    \tRequest Path:   {f"[{method}] " if method else ''}{path}
    \tParameters:     {parameters}
    \tRaised From:    {src}
    {stacktrace}
            """,
            trace_error=False,
        )

        # Log error in database
        try:
            ee = cls()
            ee.path = str(path)[:128] if path else path
            ee.parameters = str(parameters)[:500] if parameters else parameters
            ee.code_detail = str(src)[:128] if src else src
            ee.user = request.user
            ee.auth_description = env.get_session_variable("auth_user_description")
            ee.browser = browser[:200] if browser else browser
            ee.error_friendly = str(error_display)[:128] if error_display else error_display
            ee.error_system = str(error_system)[:128] if error_system else error_system
            ee.debug_info = str(debug_info)[:128] if debug_info else debug_info
            ee.stacktrace = stacktrace
            ee.save()
        except Exception as ee:
            log.warning(f"Unexpected error was not saved in database: {str(ee)}")

        # Post the friendly error to the screen
        if error_display:
            message_service.post_error(error_display)
