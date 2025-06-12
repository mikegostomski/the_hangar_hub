from . import auth_service
from . import message_service, error_service, date_service
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
# from ..models.email import Email
from ..context_processors import util as util_context, auth as auth_context
from django.urls import reverse
from base.classes.util.caller_data import CallerData
from datetime import datetime, timezone
from base.classes.util.app_data import Log, EnvHelper, AppData

log = Log()
env = EnvHelper()
app = AppData()


def get_context(util=True, auth=True):
    """Get base context to include in all email context"""
    model = {}
    if auth:
        model.update(auth_context(env.request))
    if util:
        model.update(util_context(env.request))
    return model


def get_absolute_url(*args):
    context = get_context(util=True, auth=False)
    if args:
        return f"{context['absolute_root_url']}{reverse(args[0], args=args[1:])}"
    else:
        return context['absolute_root_url']


def set_default_email(default_recipient):
    """
    When non-authenticated in non-production, a default recipient can be specified and stored in the session
    (this helps test emails for non-authenticated situations, like Dual Credit Applications)
    """
    env.set_session_variable("base_default_recipient", default_recipient)


def send(
        subject=None,
        content=None,
        sender=None,  # Can format: "Display Name <someone@pdx.edu>"
        to=None,
        cc=None,
        bcc=None,
        email_template=None,
        context=None,
        max_recipients=10,  # We rarely email more than 10 people. Exceptions should have to specify how many
        suppress_success_message=False,  # Do not notify user on successful send (but notify if send failed)
        suppress_status_messages=False,  # Do not notify user upon successful or failed send
        include_context=True,  # Include context included on all pages (current user, environment, etc)
        sender_display_name=None,  # Shortcut for: "Display Name <someone@pdx.edu>",
    limit_per_second=1,
    limit_per_minute=4,
    limit_per_hour=10,
):
    log.trace([subject])
    invalid = False
    error_message = None

    # ----------------------------------------------------------------
    # RATE LIMITING
    # ----------------------------------------------------------------
    # Rate limited was requested by security team after a pen test in July 2024
    # Rate is limited per session based on the line of code that calls the send function
    # A given line of code may not call send() more than X|Y|Z number of times per second|minute|hour
    # An excessive overage (10x) will result in a ban on the session from sending anything
    # A single request can still send multiple DIFFERENT emails (not in a loop) without hitting limits.
    # Limits can be set via parameters if your function may exceed limits in a single user's session
    # Setting the limit to 0 will eliminate the rate limiting for that duration (H/M/S)
    # Example:
    #   Setting hour and minute limits to 0 would allow unlimited emails, as long as limit_per_second is not exceeded
    # ----------------------------------------------------------------

    # current send attempts are stored in the session
    session_limits = env.get_session_variable("email_rate_limits") or {}
    is_banned = env.get_session_variable("email_rate_limit_ban")

    # Limits apply only to the file.function and line of code that called send()
    caller = CallerData().what_called("email_service.send")
    log.info(f"Email initiated by {caller}")

    if is_banned:
        log.warning("Session is banned from sending emails")
        return False

    # Grab the time that this email attempt was initiated
    now = datetime.now(timezone.utc)
    now_str = now.strftime("%Y-%m-%dT%H:%M:%S.%f")

    # If there are no attempts yet, initialize the list of attempts
    if caller not in session_limits:
        session_limits[caller] = [now_str]
        rate_exceeded = False

    # If there have been previous send attempts, evaluate timestamps
    else:
        # Compare timestamps and group by second/minute/hour
        in_h = []
        in_m = []
        in_s = []
        for date_str in session_limits[caller]:
            this_date = date_service.string_to_date(date_str)
            seconds_ago = (now - this_date).seconds
            if seconds_ago > 60*60:
                continue
            elif seconds_ago > 60:
                in_h.append(date_str)
            elif seconds_ago > 1:
                in_m.append(date_str)
            else:
                in_s.append(date_str)

        # Add up how many have been sent in the last hour/min/second
        sent_s = len(in_s)
        sent_m = sent_s + len(in_m)
        sent_h = sent_m + len(in_h)
        log.info(f"Emails sent by caller in past Hour/Minute/Second: {sent_h}/{sent_m}/{sent_s}")

        # Has the rate been met/exceeded?
        if limit_per_second and sent_s >= limit_per_second:
            rate_exceeded = f"S:{sent_s}/{limit_per_second}"

        elif limit_per_minute and sent_m >= limit_per_minute:
            rate_exceeded = f"M:{sent_m}/{limit_per_minute}"

            # If the per-minute limit is reached without exceeding the per-second limit, it may be an
            # impatient user trying to resend an email a bunch of times.
            # Post an info message asking them to be patient
            if sent_m == limit_per_minute:
                message_service.post_info(f"""
                bi-envelope-exclamation <b>{subject}</b><br>
                There have been too many attempts to send this email in the past minute.<br>
                Emails may take a couple of minutes to appear in your inbox.
                If you have not yet received a copy of this email, please wait a minute and check again.
                """)

        elif limit_per_hour and sent_h >= limit_per_hour:
            rate_exceeded = f"H:{sent_h}/{limit_per_hour}"
        else:
            # Rate not met/exceeded
            rate_exceeded = False

        # If email is not sent, should it still count toward rate limit?
        # I'm going with yes, because if it's running in a loop, it would otherwise continue to send
        # occasional emails as the previously-sent ones age out of the second/minute/hour timeframes
        in_s.append(now_str)

        # Reconstruct the session_limits list
        session_limits[caller] = in_h + in_m + in_s

        # Of course, this could put a huge list of timestamps in the session.
        # At some point, just ban the session from sending anything
        if rate_exceeded:
            # How about if a limit is exceeded by 10x, they get banned?
            if limit_per_second and sent_s >= limit_per_second*10:
                ban = True
            elif limit_per_minute and sent_m >= limit_per_minute*10:
                ban = True
            elif limit_per_hour and sent_h >= limit_per_hour*10:
                ban = True
            else:
                ban = False
            if ban:
                log.error(f"Session has been banned from sending emails due to excessive send attempts ({sent_h})")
                env.set_session_variable("email_rate_limit_ban", True)
                # Ban overrides attempt counts, so may as well free up the memory
                session_limits[caller] = None

    # Save updated rate limit stats
    env.set_session_variable("email_rate_limits", session_limits)

    # if blocked by rate limit
    if rate_exceeded:
        log_msg = f"Email rate limit reached ({rate_exceeded})"

        # If an attacker or bug is causing this to run repeatedly
        logged_errors = env.get_session_variable("email_rate_error", 0)
        if logged_errors:
            log.warning(log_msg)
        else:
            # Only one "error" log message
            log.error(log_msg)

        env.set_session_variable("email_rate_error", logged_errors + 1)
        return False

    # If sender not specified, use the default sender address
    if not sender:
        sender = env.get_setting('DEFAULT_FROM_EMAIL')

    if sender_display_name and "<" not in sender:
        sender = f"{sender_display_name} <{sender}>"

    # Subject should never be empty.  If it is, log an error and exit.
    if not subject:
        error_service.record("Email subject is empty!")
        return False

    # Non-prod emails should always point out that they're from non-prod
    if env.is_nonprod:
        prepend = f"[{env.environment_code}] "
        if not (subject.startswith(env.environment_code) or subject.startswith(prepend)):
            subject = f"{prepend}{subject}"

    to, cc, bcc, num_recipients = _prepare_recipients(to, cc, bcc)

    # Enforce max (and min) recipients
    if num_recipients == 0:
        error_message = f"Email failed validation: No Recipients"
        log.error(error_message)
        invalid = True
    elif num_recipients > max_recipients:
        error_message = f"Email failed validation: Too Many ({num_recipients} of {max_recipients}) Recipients"
        log.error(error_message)
        invalid = True

    # If a template has not been specified, use the base template
    # (Use template=False to not use a template)
    if email_template is None:
        email_template = 'base/emails/standard'
    # Will look for html and txt versions of the template
    template_no_ext = email_template.replace('.html', '').replace('.txt', '')
    template_html = f"{template_no_ext}.html"
    template_txt = f"{template_no_ext}.txt"

    # Standard template uses subject as page title (may not even matter?)
    if not context:
        context = {"subject": subject}
    elif "subject" not in context:
        context["subject"] = subject

    # Standard template will print plain content inside the HTML template
    if content and "content" not in context:
        context["content"] = content

    # Include standard context that base injects into all pages
    if include_context:
        context.update(get_context())

    # Render the template to a string (HTML and plain text)
    html = plain = None
    html_error = txt_error = False
    try:
        if template_html:
            html = render_to_string(template_html, context)
    except Exception as ee:
        log.error(f"Unable to render template: {template_html}")
        log.debug(str(ee))
        html_error = True
    try:
        if template_txt:
            plain = render_to_string(template_txt, context)
    except Exception as ee:
        if content:
            # Render the content as plain text
            plain = content
        else:
            log.warning(f"Unable to render plain-text template: {template_txt}")
            log.debug(str(ee))
            txt_error = True

    # If both templates failed, then email cannot be sent
    if txt_error and html_error:
        invalid = False

    if invalid:
        log.warning(f"Email was not sent: {subject}")

    else:
        try:
            # Build the email
            email = EmailMultiAlternatives(
                subject=subject,
                body=plain,
                from_email=sender,
                to=to,
                cc=cc,
                bcc=bcc
            )

            # If there is an html version, attach it
            if html:
                email.attach_alternative(html, "text/html")

            # Send the email
            email.send()

        except Exception as ee:
            invalid = True
            log.error(ee)
            log.warning(f"Error sending email: {subject}")

    # Log the email
    status = "F" if invalid else "S"
    _record(
        subject=subject,
        content=content,
        sender=sender,
        to=to,
        cc=cc,
        bcc=bcc,
        email_template=email_template,
        context=context,
        max_recipients=max_recipients,
        status=status,
        error_message=error_message,
    )

    # Generate a message, either for posting or logging
    if status == "S":
        msg = ["<b>Email Sent</b><br />"]
    else:
        msg = ["<b>Unable to Send Email</b><br />"]

    msg.append('<div style="padding-left: 20px;">')

    # Include the subject
    msg.append('bi-envelope-check &nbsp;')
    msg.append(f"{subject}<br />")

    # And the recipients (if not too many). Do not display Bcc
    def list_to_str(ll):
        if len(ll) > 3:
            return "(multiple recipients)"
        else:
            return str(ll).replace("'", "").replace("[", '').replace("]", '').strip()
    #
    if to:
        msg.append(f"To: {list_to_str(to)}<br />")
    if cc:
        msg.append(f"Cc: {list_to_str(cc)}<br />")

    msg.append("</div>")

    # Combine to one string
    status_message = "".join(msg)

    if not suppress_status_messages:
        # If success, and not suppressing success messages
        if status == "S" and not suppress_success_message:
            message_service.post_success(status_message)
        elif status != "S":
            message_service.post_warning(status_message)

    else:
        if status == "S":
            log.info(status_message, strip_html=True)
        else:
            log.warning(status_message, strip_html=True)

    return status == "S"


def _prepare_recipients(to, cc, bcc):
    """
    Used by send() to prepare the recipients in a unit-testable way
    """
    # Recipients should be in list format
    if type(to) is not list:
        to = [to]
    if type(cc) is not list:
        cc = [cc]
    if type(bcc) is not list:
        bcc = [bcc]

    def clean(address):
        return address.lower().replace(' ', '+')

    # Recipient lists should be unique. To assist with this, make all emails lowercase
    to = list(set([clean(address) for address in to if address]))
    cc = list(set([clean(address) for address in cc if address and clean(address) not in to]))
    bcc = list(set([clean(aa) for aa in bcc if aa and clean(aa) not in to and clean(aa) not in cc]))

    # Get the total number of recipients
    num_recipients = len(to) if to else 0
    num_recipients += len(cc) if cc else 0
    # BCC recipients are not counted unless there are no TO/CC recipients
    # Reason: User should not see any indication of BCC recipients
    if num_recipients == 0:
        num_recipients += len(bcc) if bcc else 0

    # If this is non-production, remove any non-allowed addresses
    # Always include the logged-in user's email address fron the non-prods
    if env.is_nonprod and num_recipients > 0:

        # In DEV, never send to anyone other than the default recipient
        if env.is_development:
            testing_emails = []  # No allowed testing emails
        # In STAGE (and unit tests), use defined testers
        else:
            testing_emails = env.nonprod_email_addresses

        default_recipient = env.nonprod_default_recipient
        allowed_to = [aa for aa in to if aa in testing_emails or aa == default_recipient]
        allowed_cc = [aa for aa in cc if aa in testing_emails or aa == default_recipient]
        allowed_bcc = [aa for aa in bcc if aa in testing_emails or aa == default_recipient]

        # Get the total number of allowed recipients
        num_allowed_recipients = len(allowed_to) if allowed_to else 0
        num_allowed_recipients += len(allowed_cc) if allowed_cc else 0

        # BCC does not count toward the total, unless there is no default recipient and no allowed recipients
        if num_allowed_recipients == 0 and not default_recipient:
            num_allowed_recipients += len(allowed_bcc) if allowed_bcc else 0

        if num_allowed_recipients < num_recipients:
            not_allowed = {
                "to": [aa for aa in to if aa not in allowed_to],
                "cc": [aa for aa in cc if aa not in allowed_cc],
                "bcc": [aa for aa in bcc if aa not in allowed_bcc],
            }
            log.info(f"The following recipients were removed from the recipient list:\n{not_allowed}")

        if num_allowed_recipients == 0 and default_recipient:
            message_service.post_info(f"No allowed non-prod recipients. Redirecting to {default_recipient}.")
            allowed_to = [default_recipient]
            num_allowed_recipients = 1

        # If there were allowed recipients, make sure current user is one of them
        # If not, BCC the current user on this non-prod email
        elif default_recipient and default_recipient not in allowed_to + allowed_cc + allowed_bcc:
            allowed_bcc.append(default_recipient)
            message_service.post_info(
                f"For non-prod testing, {default_recipient} has been added to the BCC list"
            )

        return allowed_to, allowed_cc, allowed_bcc, num_allowed_recipients

    else:
        return to, cc, bcc, num_recipients


def _record(subject, content, sender, to, cc, bcc, email_template, context, max_recipients, status=None, error_message=None):
    """
    Used by send() to record emails with enough data to be able to re-send them later if needed
    """
    log.trace()
    # ToDo: Record email attempts

    # email_instance = Email(
    #     app_code=app.get_app_code(),
    #     url=env.request.path,
    #     initiator=auth_service.get_auth_object().sso_user.username if auth_service.is_logged_in() else None,
    #     status=status,
    #     error_message=error_message[:128] if error_message else error_message,
    #     subject=subject[:128] if subject else subject,
    #     content=content[:4000] if content else content,
    #     sender=sender[:128] if sender else sender,
    #     to=str(to)[:4000] if to else None,
    #     cc=str(cc)[:4000] if cc else None,
    #     bcc=str(bcc)[:4000] if bcc else None,
    #     email_template=email_template[:128] if email_template else email_template,
    #     context=str(context)[:4000] if context else None,
    #     max_recipients=max_recipients
    # )
    # email_instance.save()
