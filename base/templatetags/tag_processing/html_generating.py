from django import template
from django.db.models.query import QuerySet
from base.services import utility_service, auth_service, icon_service
from base.models.utility.error import Error
from base.templatetags.tag_processing import supporting_functions as support
from base.context_processors import util as util_context
from django.urls import reverse
from random import randrange
from base.classes.util.env_helper import EnvHelper, Log

log = Log()
env = EnvHelper()


class JsAlert(template.Node):
    def __init__(self, nodelist, tokens):
        self.nodelist = nodelist
        self.tokens = tokens

    def render(self, context):
        attrs, body = support.get_tag_params(self.nodelist, self.tokens, context)
        content = [
            '$.alert({',
                f"""content: `{body}`,""",
                f"""icon: 'bi {attrs.get("icon", "bi-bell")}',""",
                f"""title: '{attrs.get("title", "Alert")}',""",
                f"""backgroundDismiss: {attrs.get("backgroundDismiss", 'true')},""",
        ]
        # Add any other specified attributes
        for kk, vv in attrs.items():
            if kk not in ["icon", "title", "backgroundDismiss"]:
                # jquery uses camelCase, but the base app makes keys lowercase. Convert _ keys to camelCase
                attr_name = utility_service.camelize(kk)
                attr_val = (
                    vv if vv in ["true", "false"] or vv.isnumeric() or kk == "buttons" else f"'{vv}'"
                )
                content.append(
                    f"""{attr_name}: {attr_val},""",
                )
        # Close the $.alert command
        content.append("});")

        return "".join(content)


class JsConfirm(template.Node):
    def __init__(self, nodelist, tokens):
        self.nodelist = nodelist
        self.tokens = tokens

    def render(self, context):
        attrs, body = support.get_tag_params(self.nodelist, self.tokens, context)
        content = [
            '$.confirm({',
                 f"""content: `{body}`,""",
                 f"""icon: 'bi {attrs.get("icon", "bi-bell")}',""",
                 f"""title: '{attrs.get("title", "Alert")}',""",
                 "buttons: {",
                     f"""'{attrs.get("confirm", "Yes")}':""",
                     "{ action: function(){",
                     attrs.get("onconfirm", ""),
                     "},",
                     f"""btnClass: '{attrs.get("confirm_btn_class", "btn-success")}',""",
                     '},',
                     f"""'{attrs.get("cancel", "No")}':""",
                     "{ action: function(){",
                     attrs.get("oncancel", ""),
                     "},",
                     f"""btnClass: '{attrs.get("cancel_btn_class", "btn-danger")}',""",
                     '},',
                 "},",
        ]
        # Add any other specified attributes
        for kk, vv in attrs.items():
            if kk not in [
                "icon",
                "title",
                "confirm",
                "onconfirm",
                "confirm_btn_class",
                "cancel",
                "oncancel",
                "cancel_btn_class",
            ]:
                # jquery uses camelCase, but the base app makes keys lowercase. Convert _ keys to camelCase
                attr_name = utility_service.camelize(kk)
                attr_val = (
                    vv if vv in ["true", "false"] or vv.isnumeric() or kk == "buttons" else f"'{vv}'"
                )
                content.append(
                    f"""{attr_name}: {attr_val},""",
                )
        # Close the $.alert command
        content.append("});")

        return "".join(content)


class JsPrompt(template.Node):
    def __init__(self, nodelist, tokens):
        self.nodelist = nodelist
        self.tokens = tokens

    def render(self, context):
        attrs, body = support.get_tag_params(self.nodelist, self.tokens, context)
        icon_base = icon_service.clean_icon_class("bi")
        icon = icon_service.clean_icon_class(attrs.get("icon", "bi-bell"))
        # Allow prompt input to be one of several possible element types (input, textarea, select)
        # Assume input to be used will have a bootstrap class attached. Also include selected radio input
        el_selector = "this.$content.find('.form-control').add(this.$content.find('.form-select')).add(this.$content.find('input[type=radio]:checked'))"
        content = [
            "$.confirm({",
            f"""   content: `<form action="" class="prompt_form">{body}</form>`,""",
            f"""   icon: '{icon_base} {icon}',""",
            f"""   title: '{attrs.get("title", "Prompt")}',""",
            "      buttons: {",

            # Submit Button
            "           formSubmit: {",
            f"""            text: '{attrs.get("submit", "Submit")}', """,
            f"""            btnClass: '{attrs.get("submit_btn_class", "btn-info")}', """,
            '               action: function(){',
            f"""                let el = {el_selector}; """,
            """                 let response = el.val(); """,
            """                 if(!response){ return false; }""",
            f"""                {attrs.get("callback", "alert")}(response);""",
            '               }',
            '           },',

            # Cancel Button
            f"""        '{attrs.get("cancel", "Cancel")}': """ + '{',
            "               action: function(){",
            f"""                {attrs.get("oncancel", "")}""",
            "               },",
            f"""            btnClass: '{attrs.get("cancel_btn_class", "btn-danger")}',""",
            "           },",
            '       },',

            # Prevent default form action
            '       onContentReady: function () {',
            """         let jc = this; """,
            """         this.$content.find('form').on('submit', function (e) { """,
            """             e.preventDefault(); """,
            """             jc.$$formSubmit.trigger('click'); """,
            """         }); """,
            f"""        {el_selector}.focus(); """,
            '       },',
        ]
        # Add any other specified attributes
        for kk, vv in attrs.items():
            if kk not in [
                "icon",
                "title",
                "submit",
                "callback",
                "submit_btn_class",
                "cancel",
                "oncancel",
                "cancel_btn_class",
            ]:
                # jquery uses camelCase, but base taglib makes keys lowercase. Convert _ keys to camelCase
                attr_name = utility_service.camelize(kk)
                attr_val = (
                    vv if vv in ["true", "false"] or vv.isnumeric() else f"'{vv}'"
                )
                content.append(
                    f"""{attr_name}: {attr_val},""",
                )
        # Close the $.alert command
        content.append("});")
        return "\n".join(content)


class AccordionItem(template.Node):
    def __init__(self, nodelist, tokens):
        self.nodelist = nodelist
        self.tokens = tokens

    def render(self, context):
        attrs, body = support.get_tag_params(self.nodelist, self.tokens, context)
        accordian_id = attrs.get("accordian_id", f"accordion")
        item_id = attrs.get("item_id", f"collapse-{randrange(1000, 9999)}")
        icon = attrs.get("icon", None)
        heading = attrs.get("heading", 'heading="?"')

        collapsed = attrs.get("collapsed")
        expanded = attrs.get("expanded")
        if collapsed is None and expanded is None:
            collapsed = True
        elif collapsed is not None:
            pass
        elif expanded is not None:
            collapsed = not expanded

        if icon:
            icon = f"""<span class="bi {icon}" style="margin-right:3px;" aria-hidden="true"></span> """

        other_attrs = []
        other_class = ""
        for attr_key, attr_val in attrs.items():
            # Ignore expected attributes (already processed)
            if attr_key in ["accordian_id", "item_id", "icon", "heading", "collapsed"]:
                continue
            elif attr_key == "class":
                other_class = attr_val
            else:
                other_attrs.append(f'{attr_key}="{attr_val}"')
        if other_attrs:
            other_attrs = " ".join(other_attrs)
        else:
            other_attrs = ""

        content = [
            f"""<div class="accordion-item {other_class}" {other_attrs} id="{item_id}">""",
            f"""  <b class="accordion-header">""",
            f"""    <button class="accordion-button {'collapsed' if collapsed else ''}" type="button" data-bs-toggle="collapse" data-bs-target="#{item_id}-dt" aria-expanded="true" aria-controls="{item_id}">""",
            f"""      {icon if icon else ''} {heading}""",
            f"""    </button>""",
            f"""  </b>""",
            f"""  <div id="{item_id}-dt" class="accordion-collapse collapse {'' if collapsed else 'show'}" data-bs-parent="#{accordian_id}">""",
            f"""    <div class="accordion-body">{body}</div>""",
            f"""  </div>""",
            f"""</div>""",
        ]

        return "".join(content)


class Popup(template.Node):
    def __init__(self, nodelist, tokens):
        self.nodelist = nodelist
        self.tokens = tokens

    def render(self, context):
        attrs, body = support.get_tag_params(self.nodelist, self.tokens, context)
        smokescreen = attrs.get("smokescreen", True)
        classes = attrs.get('class', '')
        hidden = False
        if "hidden" in classes:
            hidden = True
            classes = classes.replace("hidden", "").strip()
        hidden = "hidden" if attrs.get("hidden", hidden) else ""

        # Add any specified attributes to the div tag
        div_attrs = []
        for kk, vv in attrs.items():
            if kk not in ['class', 'smokescreen', 'onclick', 'hidden']:
                div_attrs.append(f'{kk}="{vv}"')
        if div_attrs:
            div_attrs = " ".join(div_attrs)
        else:
            div_attrs = ""

        if smokescreen:
            popup = f"""<div class="popup {classes}" {div_attrs}>{body}</div>"""
            hide = "$(this).addClass('hidden');"
            return f"""<div class="smokescreen {hidden}" onclick="{hide}">{popup}</div>"""
        else:
            return f"""<div class="popup {classes} {hidden}" {div_attrs}>{body}</div>"""


class SelectNode(template.Node):
    """Generates a select menu with automated option selection"""
    def __init__(self, args):
        self.args = args

    def render(self, context):
        # Prepare attributes
        attrs = support.process_args(self.args, context)

        # Attributes that need special processing are 'options' and 'value'
        options = value = None

        # Make nullable by default
        nullable = True
        if "nullable" in attrs:
            nullable_str = str(attrs.get("nullable")).lower()
            # Menus may be nullable only until a value is selected
            if "null" in nullable_str:  # when_null, if_null, on_null, etc...
                val = str(attrs.get("value")).strip()
                nullable = val in ["None", ""]
            else:
                nullable = nullable_str not in ["n", "no", "false", "none"]

        # Allow default null label to be overwritten
        null_label = (
            attrs.get("null_label") if "null_label" in attrs else "Select an Option"
        )

        # Expect options to be provided
        if 'options' in attrs:
            options = attrs.get('options')
        else:
            log.error("You must provide a dict of options for the select menu")
            options = {}

        # Could be multiple-select
        multiple = str(attrs.get("multiple")).lower() in ["multiple", "true", "y"]
        # Expect a value or values to be provided
        value = attrs.get("value")
        values = attrs.get("values")

        # Remove special attrs that should not appear in the HTML element
        for ii in ["multiple", "values", "value", "null_label", "nullable", "options"]:
            if ii in attrs:
                del attrs[ii]

        pieces = ["<select"]
        for attr_key, attr_val in attrs.items():
            # Data attributes need the '_' converted to '-'
            if attr_key.startswith("data_"):
                pieces.append(f'{attr_key.replace("data_", "data-")}="{attr_val}"')
            elif attr_key.startswith("aria_"):
                pieces.append(f'{attr_key.replace("aria_", "aria-")}="{attr_val}"')
            else:
                pieces.append(f'{attr_key}="{attr_val}"')
        if multiple:
            pieces.append("multiple")
        pieces.append(">")

        # Options must be a dict. Convert some other common types.
        if not options:
            options = {}
        elif options and type(options) is not dict:
            if type(options) is QuerySet:
                options = list(options)

            if type(options) is list:
                # Convert the list a dict
                # Sample the first item to see if it contains an ID attribute
                try:
                    if hasattr(options[0], "id"):
                        options = {x.id: str(x) for x in options}
                    else:
                        options = {x: x for x in options}
                except Exception as ee:
                    log.debug("Error converting list to dict for select menu")
                    log.error(ee)

        # Accept strings that refer to common option sets
        if type(options) is str:
            # Yes-No menus in each order (for defaulting to Y or N)
            if options.upper() == "YN":
                options = {"Y": "Yes", "N": "No"}
            elif options.upper() == "NY":
                options = {"N": "No", "Y": "Yes"}

            # True/False menus in each order (for defaulting to True or False)
            elif options.upper() in ["TF", 'BOOL', 'BOOLEAN']:
                options = {"True": "True", "False": "False"}
            elif options.upper() == "FT":
                options = {"False": "False", "True": "True"}

            # Ranges of numbers
            elif ".." in options:
                ll = options.split("..")
                if len(ll) == 2 and ll[0].isnumeric() and ll[1].isnumeric():
                    n1 = int(ll[0])
                    n2 = int(ll[1])
                    rev = n2 < n1
                    if rev:
                        options = {str(ii): str(ii) for ii in reversed(range(n2 + 1, n1))}
                    else:
                        options = {str(ii): str(ii) for ii in range(n1, n2 + 1)}

            # Pipe-delimited lists
            elif "|" in options:
                # left|right|center --> {left: left, right: right, center: center}
                # left:Left|right:Apple --> {left: Left, right: Apple}
                dd = {}
                for li in options.split("|"):
                    if ":" in li:
                        pp = li.split(":")
                        dd[pp[0]] = pp[1].replace("_", " ")
                    else:
                        dd[li] = li.replace("_", " ")
                options = dd

            # If still a string, there will be issues. (this should be caught during development)
            if type(options) is str:
                Error.record(f"Invalid options given to %select_menu% tag", debug_info=options)

        if nullable:
            pieces.append(
                f"<option value=\"\">{null_label if null_label else 'Select One'}</option>"
            )

        # If options were provided (not options=None)
        if options is not None:
            str_values = [str(x) for x in values] if values else None
            for option_key, option_val in options.items():
                pieces.append(f'<option value="{option_key}"')
                if str(value) == str(option_key):
                    pieces.append("selected")
                elif multiple and str_values and str(option_key) in str_values:
                    pieces.append("selected")
                pieces.append(f">{option_val}</option>")

        pieces.append("</select>")

        return " ".join(pieces)


class FaNode(template.Node):
    """Handles the FontAwesome icon-generating tag"""
    def __init__(self, args):
        self.args = args

    def render(self, context):
        attrs = support.process_args(self.args, context)
        # The Bootstrap Icons (bi) classes are expected to be given first, without key="val" formatting
        # Collect all assumed bi classes first
        icon_classes = {k: v for k, v in attrs.items() if k == v}

        # If a icon_class needs to be added via a context variable, use `icon_class=variable_name`
        if 'icon_class' in attrs:
            icon_class = attrs.get('icon_class')
            icon_classes[icon_class] = icon_class
            del attrs['icon_class']

        # Everything else should have been in key="value" format
        other_attributes = {k: v for k, v in attrs.items() if k != v}
        title = other_attributes.get("title")

        # Determine screen reader text
        if other_attributes.get("aria-hidden", "false").lower() == "true":
            aria_text = ""
        elif other_attributes.get("aria-label"):
            aria_text = other_attributes.get("aria-label")
            del other_attributes["aria-label"]
        elif title:
            aria_text = title
        else:
            aria_text = ""
        # If screen reader text was found, put it in a visually-hidden span
        if aria_text:
            aria_text = f'<span class="visually-hidden">{aria_text}</span>'

        # Icon will be wrapped in a button if it has an onclick action
        onclick = other_attributes.get('onclick')
        classes = other_attributes.get('class')
        if onclick:
            del other_attributes['onclick']
            if classes:
                del other_attributes['class']
            else:
                classes = ""
            icon = [f'<button type="button" onclick="{onclick}" class="btn btn-icon {classes}"']
        else:
            icon = ["<span"]

        for kk, vv in other_attributes.items():
            if kk == "title":
                # Title will be on the icon and in the visually-hidden span
                continue
            if kk == "style" and "background-color" not in vv:
                vv = f"background-color:transparent;{vv}"
            icon.append(f' {kk}="{vv}"')

        if "style" not in other_attributes.items():
            icon.append(' style="background-color:transparent;"')

        icon.append(">")

        # Build a basic FA icon inside the div or button
        icon.append('<span class="')

        if not any(x in ['fas', 'far', 'fal', 'fad'] for x in icon_classes):
            icon.append(f"fa")

        for fa_class in icon_classes:
            icon.append(f" {fa_class}")
        icon.append('"')
        if title:
            icon.append(f' title="{title}"')
        # Icon should always be aria-hidden, since title/label was printed in a visually-hidden span
        icon.append(' aria-hidden="true"')
        icon.append("></span>")

        # Append hidden screen reader text, if present
        icon.append(aria_text)

        # Close the button or span wrapper
        if onclick:
            icon.append("</button>")
        else:
            icon.append("</span>")

        return "".join(icon)


class IconNode(template.Node):
    """
    Handles the icon-generating tag for FontAwesome and Bootstrap Icons
    This lets pus-plugins support both libraries, so apps can choose to use either
    """
    def __init__(self, args):
        self.args = args

    def render(self, context):
        attrs = support.process_args(self.args, context)

        icon_provider = icon_service.get_icon_provider()

        # The icon classes are expected to be given first, without key="val" formatting
        # Collect all assumed icon classes first
        icon_classes = {k: v for k, v in attrs.items() if k == v}

        # Everything else should have been in key="value" format
        other_attributes = {k: v for k, v in attrs.items() if k != v}
        title = other_attributes.get("title")

        # icon class may be contained in a variable, in which case it can be provided via "icon_class" attr
        icon_class = other_attributes.get("icon_class") or other_attributes.get("fa_class")
        if icon_class:
            if " " in icon_class:
                for ic in icon_class.split():
                    icon_classes[ic] = ic
            else:
                icon_classes[icon_class] = icon_class


        # Library-specific processing...
        # ==============================

        if icon_service.use_bootstrap_icons():
            library_base_class = "bi"

            bi_clean = {}
            for k, v in icon_classes.items():
                class_name = icon_service.fa_to_bootstrap(v)
                bi_clean[class_name] = class_name
            icon_classes = bi_clean

        # elif icon_provider == "BOX":
        #     library_base_class = "bx"

        else:
            Error.record(
                f"Invalid Icon Library: {icon_provider}"
            )
            return ""

        # Remaining code is the same for all font libraries...
        # ====================================================

        # Determine screen reader text
        if other_attributes.get("aria-hidden", "false").lower() == "true":
            aria_text = ""
        elif other_attributes.get("aria-label"):
            aria_text = other_attributes.get("aria-label")
            del other_attributes["aria-label"]
        elif title:
            aria_text = title
        else:
            aria_text = ""
        # If screen reader text was found, put it in a visually-hidden span
        if aria_text:
            aria_text = f'<span class="visually-hidden">{aria_text}</span>'

        # Icon will be wrapped in a button if it has an onclick action
        onclick = other_attributes.get("onclick")
        classes = other_attributes.get("class")
        if onclick:
            del other_attributes["onclick"]
            if classes:
                del other_attributes["class"]
            else:
                classes = ""
            icon = [
                f'<button type="button" onclick="{onclick}" class="btn btn-icon {classes}"'
            ]
        else:
            icon = ["<span"]

        for kk, vv in other_attributes.items():
            if kk == "title":
                # Title will be on the icon and in the visually-hidden span
                continue
            if kk == "style" and "background-color" not in vv:
                vv = f"background-color:transparent;{vv}"

            # Data attributes need the '_' converted to '-'
            if kk.startswith("data_"):
                icon.append(f'{kk.replace("data_", "data-")}="{vv}"')
            elif kk.startswith("aria_"):
                icon.append(f'{kk.replace("aria_", "aria-")}="{vv}"')
            else:
                icon.append(f' {kk}="{vv}"')

        if "style" not in other_attributes.items():
            icon.append(' style="background-color:transparent;"')

        icon.append(">")

        # Build a basic FA icon inside the div or button
        icon.append(f'<span class="{library_base_class}')
        for this_class in icon_classes:
            icon.append(f" {this_class}")
        icon.append('"')
        if title:
            icon.append(f' title="{title}"')
        # Icon should always be aria-hidden, since title/label was printed in a visually-hidden span
        icon.append(' aria-hidden="true"')
        icon.append(' style="background-color:transparent;"')
        icon.append("></span>")

        # Append hidden screen reader text, if present
        icon.append(aria_text)

        # Close the button or span wrapper
        if onclick:
            icon.append("</button>")
        else:
            icon.append("</span>")

        return "".join(icon)


class ImageNode(template.Node):
    def __init__(self, args):
        self.args = args

    def render(self, context):
        # Prepare attributes
        attrs = {}
        for arg in self.args[1:]:
            key = val = None
            if "=" in arg:
                key, val = arg.split("=")
            else:
                log.warn(
                    f"Ignoring invalid argument for image tag: {arg}. Arguments must be in 'key=\"value\" format"
                )
                continue

            if val.startswith('"'):
                val = val.strip('"')
            else:
                val_str = template.Variable(val)
                val = val_str.resolve(context)

            # Allow src attribute to be called other things in this case
            if key.lower() in ["src", "source", "image", "file", "path", "filename"]:
                key = "src"

            attrs[key.lower()] = val

        # Prepend the static content url to the src
        if 'src' in attrs:
            attrs['src'] = f"{env.static_content_url}/images/{attrs['src']}"
        # If no src was given, log warning and use empty src (for broken image indicator)
        else:
            log.warn("No image file name was provided as 'src' in the 'image' taglib")
            attrs["src"] = ""

        pieces = [f"<img"]
        for attr_key, attr_val in attrs.items():
            pieces.append(f'{attr_key}="{attr_val}"')
        pieces.append("/>")

        return " ".join(pieces)


# class PhotoNode(template.Node):
#     def __init__(self, args):
#         self.args = args
# 
#     def render(self, context):
#         attrs = support.process_args(self.args, context)
# 
#         # A user object must be provided
#         user_instance = attrs.get("user")
#         if not user_instance:
#             log.warn("No user attribute was provided. ID photo cannot be displayed")
# 
#         # Does the user have a photo?
#         if user_instance and user_instance.id_photo:
#             src = user_instance.id_photo
#             default_alt = f"ID photo of {user_instance.display_name}"
#             has_img = True
#         elif user_instance and user_instance.enhanced_privacy:
#             src = f"{env.static_content_url}/images/user-shield.png"
#             default_alt = "ID photo not shown"
#             has_img = False
#             if user_instance and user_instance.display_name:
#                 default_alt += f" for {user_instance.display_name}"
#         else:
#             src = f"{env.static_content_url}/images/no-id-photo.png"
#             default_alt = "Missing ID photo"
#             has_img = False
#             if user_instance and user_instance.display_name:
#                 default_alt += f" for {user_instance.display_name}"
# 
#         # Prepare attributes
#         nvl = False
#         for key, val in attrs.items():
#             if key.lower() == "src":
#                 log.warn(
#                     "Ignoring src attribute in id_photo tag. The src is determined automatically."
#                 )
#             elif key.lower() == "nvl":
#                 # Any value means True, except false or no
#                 nvl = str(val).lower() not in ["false", "no", "n"]
# 
#         # If alt not provided, use default
#         if "alt" not in attrs:
#             attrs["alt"] = default_alt
# 
#         # If no classes provided, use default class
#         if "class" not in attrs:
#             attrs["class"] = "id_photo"
# 
#         # If a valid user has no image, and using nvl, render their initials instead of a picture
#         if user_instance and user_instance.is_mvp() and (not has_img) and nvl:
#             del attrs["alt"]  # No alt text needed, since this is not an image
#             pieces = [f"<span"]
#             for attr_key, attr_val in attrs.items():
#                 if attr_key in ["user", "nvl"]:
#                     continue
#                 pieces.append(f'{attr_key}="{attr_val}"')
#             pieces.append(">")
#             pieces.append(
#                 f'<div class="id_photo-nvl" aria-hidden="true">{user_instance.first_name[:1]}</div>'
#             )
#             pieces.append("</span>")
#         else:
#             pieces = [f'<img src="{src}"']
#             for attr_key, attr_val in attrs.items():
#                 if attr_key in ["user", "nvl"]:
#                     continue
#                 pieces.append(f'{attr_key}="{attr_val}"')
#             pieces.append("/>")
# 
#         return " ".join(pieces)


class HeaderNavTab(template.Node):
    def __init__(self, args):
        self.args = args

    def render(self, context):
        attrs = support.process_args(self.args, context)

        # A URL and label must be provided
        url = attrs.get("url")
        url_arg = attrs.get("url_arg")
        label = attrs.get("label")
        icon = attrs.get("icon")
        icon_only = icon and attrs.get("icon_only")
        optional = attrs.get("optional")
        active_only = attrs.get("active_only")

        # Item is allowed for everyone if no authorities are specified
        allowed = True

        # A list of required authorities may be provided
        authorities = attrs.get("authorities", None)
        if type(authorities) is str:
            authorities = utility_service.csv_to_list(authorities)
        elif authorities and type(authorities) is not list:
            allowed = False
            log.warn(f"Invalid authority list was provided. Menu item will not be displayed: {url}")

        if authorities and allowed:
            allowed = auth_service.has_authority(authorities)

        # If feature is specified, then feature must be enabled (skip check if already not allowed)
        if allowed:
            feature_code = attrs.get("feature", None)
            # If feature was specified, and is not active
            if feature_code and not utility_service.feature_is_enabled(feature_code):
                allowed = False

        # If not allowed, do not print the link
        if not allowed:
            return ""

        path = None
        is_active = False

        # If no URL was given
        if not url:
            log.warn("No URL was provided. Menu item cannot be marked active")

        # If root path is given
        elif url == "/":
            path = util_context(context.request).get("home_url")
            is_active = path == context.request.path

        # If using current path
        elif url == "#":
            path = context.request.path
            is_active = True

        # Named URL was probably given
        elif "/" not in url:
            try:
                if url_arg:
                    path = reverse(url, args=[url_arg])
                else:
                    path = reverse(url)
                is_active = path == context.request.path
            except Exception as ee:
                log.debug(f"Path comparison error: {str(ee)}")

        # Otherwise, maybe an actual URL was given
        else:
            path = url
            is_active = path == context.request.path

        if is_active:
            classes = "nav-item header-nav-item header-nav-item-active"
        elif active_only:
            return ""
        elif optional:
            classes = "nav-item header-nav-item header-nav-item-optional"
        else:
            classes = "nav-item header-nav-item"

        # By default, show loading div when a tab is clicked
        if "onclick" in attrs:
            onclick = attrs.get("onclick")
        else:
            onclick = "setPageLoadIndicatorUnlessCtrlClick(event);"

        pieces = [f"""<li class="{classes}"><a href="{path}" onclick="{onclick}">"""]

        if icon_only:
            pieces.append(f"""<span class="bi {icon}" aria-hidden="true" title="{label}"> </span>""")
            pieces.append(f"""<span class="visually-hidden">{label}</span>""")
        elif icon:
            pieces.append(f"""<span class="bi {icon}" aria-hidden="true"> </span>""")
            pieces.append(label)
        else:
            pieces.append(label)

        pieces.append("</a></li>")
        return " ".join(pieces)


class HeaderNavMenuItem(template.Node):
    def __init__(self, args):
        self.args = args

    def render(self, context):
        attrs = support.process_args(self.args, context)

        # A map of attributes may be accepted in place of individual attributes
        attributes = attrs.get("attributes")
        if attributes:
            attrs.update(attributes)

        # A URL and label must be provided
        url = attrs.get("url")
        label = attrs.get("label", url)
        icon = attrs.get("icon", "bi-link-45deg")

        # Item is allowed for all admins and developers if no authorities are specified
        allowed = auth_service.has_authority("~power_user")

        # A list of required authorities may be provided
        authorities = attrs.get("authorities")

        # Turn authorities into a list
        if authorities and type(authorities) is not list:
            authorities = utility_service.csv_to_list(authorities)

        # If authorities were given and a list could not be generated from it
        if authorities and type(authorities) is not list:
            allowed = False
            log.warn(f"Invalid authority list was provided. Menu item will not be displayed: {label}")

        if authorities:
            allowed = auth_service.has_authority(authorities)

        # If feature is specified, then feature must be enabled (skip check if already not allowed)
        if allowed:
            feature_code = attrs.get("feature")
            # If feature was specified, and is not active
            if feature_code and not utility_service.feature_is_enabled(feature_code):
                allowed = False

        # If not allowed, do not print the link
        if not allowed:
            return ""

        # If marked as non-prod only, do not include in prod
        if attrs.get("nonprod_only", False) and env.is_prod:
            return ""

        path = None
        is_active = False

        # If no URL was given
        if not url:
            log.warn("No URL was provided. Menu item cannot be marked active")

        # If root path is given
        elif url == "/":
            path = util_context(context.request).get("home_url")
            is_active = path == context.request.path

        # Assume named URL was given
        else:
            try:
                path = reverse(url)
                is_active = path == context.request.path
            except Exception as ee:
                log.debug(f"Path comparison error: {str(ee)}")

        if is_active:
            classes = "header-menu-item header-menu-item-active"
        else:
            classes = "header-menu-item"

        # By default, close menu and show loading div when an admin menu item is clicked
        if "onclick" in attrs:
            onclick = attrs.get("onclick")
        else:
            onclick = "$(this).closest('.dropdown').find('.dropbtn').trigger('click');setPageLoadIndicatorUnlessCtrlClick(event);"

        pieces = [f"""<li><a class="dropdown-item {classes}" href="{path}" onclick="{onclick}">"""]

        if icon:
            pieces.append(f"""<span class="bi {icon}" aria-hidden="true" style="background-color:transparent;"> </span>""")

        pieces.append(label)
        pieces.append("</a></li>")
        return " ".join(pieces)


def HeaderNavSubMenu(submenu):

    # A map of attributes may be accepted in place of individual attributes
    attributes = submenu.get("attributes")
    if attributes:
        submenu.update(attributes)

    # A list of items must be provided
    label = submenu.get("label", "Submenu")
    menu = submenu.get("menu")
    if not menu:
        log.warning(f"Empty submenu will not be displayed: {label}")
        return {"submenu_allowed": False}

    # Sort submenu items
    submenu["menu"] = sorted(menu, key=lambda i: i["label"])

    # Item is allowed for all admins and developers if no authorities are specified
    allowed = auth_service.has_authority("~power_user")

    # A list of required authorities may be provided
    authorities = submenu.get("authorities")

    # Turn authorities into a list
    if authorities and type(authorities) is not list:
        authorities = utility_service.csv_to_list(authorities)

    # If authorities were given and a list could not be generated from it
    if authorities and type(authorities) is not list:
        allowed = False
        log.warn(
            f"Invalid authority list was provided. Menu item will not be displayed: {label}"
        )

    if authorities:
        allowed = auth_service.has_authority(authorities)

    # If feature is specified, then feature must be enabled (skip check if already not allowed)
    if allowed:
        feature_code = submenu.get("feature")
        # If feature was specified, and is not active
        if feature_code and not utility_service.feature_is_enabled(feature_code):
            allowed = False

    # If marked as non-prod only, do not include in prod
    if submenu.get("nonprod_only", False) and env.is_prod:
        allowed = False

    submenu["submenu_allowed"] = allowed
    return submenu


def pagination(paginated_results):
    """Example: {%pagination polls%}"""
    if paginated_results:
        # Show three pages on either side of the current page
        current_page = paginated_results.number     # 10    2
        min_page = current_page - 3                 # 7     -1
        max_page = current_page + 3                 # 13    5

        # If starting before page 1, shift min and max to be higher
        while min_page < 1:
            min_page += 1
            max_page += 1

        # If Extending past the last page, shift min and max lower
        while max_page > paginated_results.paginator.num_pages:
            min_page -= 1
            max_page -= 1

        # If shifting resulted in page less than 1, set it to page 1
        if min_page < 1:
            min_page = 1
    else:
        current_page = 1
        min_page = 1
        max_page = 1

    # Show dots to indicate pages not displayed?
    if paginated_results:
        dots_before = bool(min_page > 1)
        dots_after = bool(max_page < paginated_results.paginator.num_pages)
    else:
        dots_before = dots_after = False

    if paginated_results:
        start_item = paginated_results.start_index
        end_item = paginated_results.end_index
        num_items = paginated_results.paginator.count
    else:
        start_item = end_item = num_items = 0

    return {
        "paginated_results": paginated_results,
        "min_page": min_page,
        "max_page": max_page,
        "dots_before": dots_before,
        "dots_after": dots_after,
        "start_item": start_item,
        "end_item": end_item,
        "num_items": num_items,
    }


class SortableThNode(template.Node):
    """Create a sortable <th> for server-side pagination"""
    def __init__(self, args):
        self.args = args

    def render(self, context):
        attrs = support.process_args(self.args, context)

        # The column and heading can be specified under various keywords for convenience
        column = None
        for cv in ["col", "column", "property", "attr", "sort", "sortby", "sort_by"]:
            if cv in attrs:
                column = attrs[cv]
                break

        heading = column.replace('_', ' ').title() if column else None
        for hv in ['heading', 'label']:
            if hv in attrs:
                heading = attrs[hv]
                break

        # Last-sorted column was saved in utility_service.pagination_sort_info()
        # This assumes only one sorted dataset is being displayed at a time
        sorted_col = env.get_session_variable('baseapp_last_sorted_column')
        sorted_secondary_col = env.get_session_variable('baseapp_last_secondary_sorted_column')
        sorted_dir = env.get_session_variable('baseapp_last_sorted_direction')

        bi = title = None
        if sorted_col and sorted_dir:
            if column == sorted_col:
                bi = f"bi-sort-alpha-{'up-alt' if sorted_dir == 'desc' else 'down'}"
                title = "Primary sort column"
            elif column == sorted_secondary_col:
                bi = f"bi-sort-{'up' if sorted_dir == 'desc' else 'down'} text-muted"
                title = "Secondary sort column"

        pieces = [
            """<th scope="col">""",
            f"""<a href="?sort={column}">{heading}</a>""",
            f"""&nbsp;<span class="{bi}" aria-hidden="true" title="{title}"></span>""" if bi else '',
            """</th>"""
        ]

        return "".join(pieces)
