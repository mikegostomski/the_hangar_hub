from base.services import utility_service
from base.models.utility.error import Error, Log, EnvHelper
from base_infotext.models import Infotext
from ast import literal_eval
import re

log = Log()


def get_infotext(code, alt_text, **kwargs):
    content = alt_text
    if not code:
        log.error("Missing infotext code")
        return ""

    try:
        # Get current app name
        app = utility_service.get_app_code()

        # Use/generate auto-prefix?
        auto_prefix = str(kwargs.get("auto_prefix", True)).lower() not in [
            "false",
            "no",
            "n",
        ]

        if auto_prefix:
            # Get relative path (url)
            request = utility_service.get_request()
            # uc = util_context(request)
            # uc['absolute_root_url']
            relative_url = request.get_full_path()

            # If at root, call it root
            if relative_url == "/":
                prefix = "root"
            else:
                # Remove query string, if present
                if "?" in relative_url:
                    relative_url = relative_url.split("?")[0]

                # Convert slashes to dots
                prefix = relative_url.replace("/", ".").lower() + "."
                # If path contains an ID (pdx.edu/details/10), strip out the id
                prefix = re.sub(r"\.\d+\.?", ".id.", prefix).strip(".")

            # If prefix does not start with app name, prepend app name to the prefix
            if not prefix.startswith(app):
                prefix = f"{app}.{prefix}"

            # Determine full text_code. Convert to lowercase for case insensitivity.
            infotext_code = f"{prefix}.{code}".strip().lower()

        else:
            infotext_code = code.strip().lower()

        # Get group title, if provided
        group_title = kwargs.get("group_title")

        # Look for instance in database
        result = Infotext.objects.filter(app_code=app.upper()).filter(
            text_code=infotext_code
        )

        # If not found, add it
        if not result:
            instance = Infotext(
                app_code=app.upper(),
                text_code=infotext_code,
                content=alt_text,
                group_title=group_title,
            )
            instance.save()

        else:
            instance = result[0]

        # Compare unedited text content to the coded value, and update if the coded content changed
        if instance.user_edited == "N" and instance.content != alt_text:
            instance.content = alt_text
            instance.save()

        # If user-edited text has been updated in the code (or restored by user), remove user-edited indicator
        elif instance.user_edited == "Y" and instance.content == alt_text:
            instance.user_edited = "N"
            instance.save()

        # If user-edited text differs from coded content in development environment, log it as warning
        elif instance.user_edited == "Y" and utility_service.is_development():
            log.warn(f"{infotext_code} has been updated by users and differs from hard-coded content")

        # If group_title has changed, update it
        if group_title and group_title != instance.group_title:
            instance.group_title = group_title
            instance.save()

        # Get text content
        content = instance.content
    except Exception as ee:
        Error.record(ee, "Unable to retrieve infotext")

    try:
        # Process any replacements
        if "replacements" in kwargs:
            replacements = kwargs["replacements"]
            # Note: replacements could be a string that is formatted like a dict
            if type(replacements) is str:
                for key, val in literal_eval(replacements).items():
                    content = content.replace(key, val)
            elif type(replacements) is dict:
                for key, val in replacements.items():
                    content = content.replace(key, val)
    except Exception as ee:
        Error.record(ee, "Unable to process infotext replacements")

    return content
