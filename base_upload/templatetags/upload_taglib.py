from django import template
from django.utils.html import mark_safe
from base.classes.util.env_helper import Log, EnvHelper
from base.templatetags.tag_processing import supporting_functions as support
from django.urls import reverse
from base_upload.services import upload_service
from base.models.utility.error import Error
from django.urls.exceptions import NoReverseMatch
import base64

register = template.Library()
log = Log()
env = EnvHelper()


@register.tag()
def file_link(parser, token):
    return FileLinkNode(token.split_contents())


@register.tag()
def file_preview(parser, token):
    return FilePreviewNode(token.split_contents())

@register.tag()
def display_image(parser, token):
    return DisplayImageNode(token.split_contents())


class FileLinkNode(template.Node):
    """Generates a link to an uploaded file"""

    def __init__(self, args):
        self.args = args

    def render(self, context):
        # Prepare attributes
        attrs = support.process_args(self.args, context)
        log.trace(attrs, function_name="upload_taglib.FileLinkNode")

        # File (base_upload.models.UploadedFile|DatabaseFile) is required
        file_instance = attrs.get("file")
        if not file_instance:
            log.error("No file instance was given. Unable to render link to file")
            return ""

        # Attrs with defaults
        target = attrs.get("target", "_blank")
        icon = attrs.get("icon", True)
        size = attrs.get("size", False)
        original_name = attrs.get("original_name", False)
        html_class = attrs.get("class", "")

        # Remove special attrs that should not appear in the HTML element or that are handled above
        for ii in ["file", "target", "icon", "size", "class"]:
            if ii in attrs:
                del attrs[ii]

        icon_class_str = None
        if icon:
            # Default icon
            icon_class_str = file_instance.icon_class()
            # If an actual class was specified
            if type(icon) is str and icon.lower() not in [
                "y",
                "yes",
                "n",
                "no",
                "true",
                "false",
                "none",
            ]:
                icon_class_str = icon
            # If string is something negative, no icon
            elif type(icon) is str and icon.lower() in ["n", "no", "false", "none"]:
                icon = False
            # otherwise, use default icon

            icon = f"""<span class="{icon_class_str} upload-link upload-link-icon" aria-hidden="true"></span> """

        pieces = [f"""<span class="upload-link upload-link-container {html_class}" """]

        # Append any other attrs (id, style, etc)
        for attr_key, attr_val in attrs.items():
            pieces.append(f'{attr_key}="{attr_val}"')

        # Close container tag
        pieces.append(">")

        # Add link
        if upload_service.using_s3():
            pieces.append(
                f"""<a href="{file_instance.file.url}" class="upload-link upload-link-a" target="{target}">"""
            )
        else:
            try:
                file_url = reverse("upload:linked_file", args=[file_instance.id])
                # In order for the link to work, the ID must exist in the session
                allowed_files = env.get_session_variable("allowed_file_ids", [])
                allowed_files.append(file_instance.id)
                env.set_session_variable(
                    "allowed_file_ids", list(set(allowed_files))
                )

            except Exception as ee:
                Error.record(ee, f"Could not link to file: {file_instance.id}")
                file_url = "#"
            pieces.append(
                f"""<a href="{file_url}" class="upload-link upload-link-a" target="{target}">"""
            )

        # If including an icon
        if icon:
            pieces.append(icon)

        # File name
        if original_name:
            name = file_instance.original_name
        else:
            name = file_instance.basename

        pieces.append(f"""<span class="upload-link upload-link-name">{name}</span>""")

        # End the link
        pieces.append("</a>")

        # If displaying the file size (not part of click-able link)
        if size:
            if type(size) is str and size.lower() in ["n", "no", "false", "none"]:
                pass
            else:
                pieces.append(
                    f""" <span class="upload-link upload-link-size">{file_instance.readable_size()}</span>"""
                )

        # End container
        pieces.append("</span>")

        # Return full HTML
        return mark_safe(" ".join(pieces))


class FilePreviewNode(template.Node):
    """Display an image file from the database (in an <img /> tag) or a link to a non-image file"""

    def __init__(self, args):
        self.args = args

    def render(self, context):
        # Prepare attributes
        attrs = support.process_args(self.args, context)

        # File (base_upload.models.DatabaseFile) is required
        file_instance = attrs.get("file")
        if not file_instance:
            log.error("No file instance was given. Unable to render image")
            return ""

        is_image = "image" in file_instance.content_type

        if is_image:
            pieces = [f"""<img """]
            b64img = base64.b64encode(file_instance.file).decode()
            pieces.append(
                f"""src = "data:{file_instance.content_type};base64,{b64img}" """
            )
            content = ""

        else:
            pieces = [f"""<span """]
            # Add some overridable style
            style = "display:inline-block;width:100%;padding:5px;border-radius:3px;border:1px solid #AAA;text-align:center;"
            attrs["style"] = f"{style}{attrs.get('style', '')}"
            icon = f"""<span class="{file_instance.icon_class()}" style="font-size:18pt;"></span>"""
            size = f"""<span style="font-family:arial, sans-serif;font-size:8pt;"><br />{file_instance.readable_size()}</span>"""
            content = f"""{icon}{size}"""

        # Append any other attrs (id, style, etc)
        for attr_key, attr_val in attrs.items():
            if attr_key in ["file", "target", "link_class", "link"]:
                continue
            pieces.append(f'{attr_key}="{attr_val}"')

        # Close container tag
        if is_image:
            pieces.append(" />")
        else:
            pieces.append(f">{content}</span>")

        # Combine pieces into an HTML tag
        preview = " ".join(pieces)

        # Add link
        if attrs.get("link", True):
            file_url = None
            if upload_service.using_s3():
                file_url = file_instance.file.url
            else:
                try:
                    file_url = reverse("upload:linked_file", args=[file_instance.id])
                    # In order for the link to work, the ID must exist in the session
                    allowed_files = env.get_session_variable(
                        "allowed_file_ids", []
                    )
                    allowed_files.append(file_instance.id)
                    env.set_session_variable(
                        "allowed_file_ids", list(set(allowed_files))
                    )

                except NoReverseMatch as ee:
                    log.warning(
                        "Linked file does not exist. It was probably deleted during this request."
                    )
                    file_url = None

                except Exception as ee:
                    Error.record(
                        ee, f"Could not link to file: {file_instance.id}"
                    )
                    file_url = None

            if file_url:
                target = attrs.get("target", "_blank")
                link_class = attrs.get("link_class", "upload-link upload-link-a")
                preview = f"""<a href="{file_url}" class="{link_class}" target="{target}">{preview}</a>"""

        return mark_safe(preview)

class DisplayImageNode(template.Node):
    """Display an image file from the database (in an <img /> tag)"""

    def __init__(self, args):
        self.args = args

    def render(self, context):
        # Prepare attributes
        attrs = support.process_args(self.args, context)

        # File (base_upload.models.DatabaseFile) is required
        file_instance = attrs.get("file")
        if not file_instance:
            log.error("No file instance was given. Unable to render image")
            return ""

        is_image = "image" in file_instance.content_type

        if not is_image:
            log.error(f"Unable to display non-image file: {file_instance.content_type}")
            return ""

        pieces = [f"""<img """]
        b64img = base64.b64encode(file_instance.file).decode()
        pieces.append(
            f"""src = "data:{file_instance.content_type};base64,{b64img}" """
        )

        # Append any other attrs (id, style, etc)
        for attr_key, attr_val in attrs.items():
            if attr_key in ["file", "target", "link_class", "link"]:
                continue
            pieces.append(f'{attr_key}="{attr_val}"')

        # Close container tag
        pieces.append(" />")

        return mark_safe(" ".join(pieces))
