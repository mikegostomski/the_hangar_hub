import random
from base.classes.util.env_helper import EnvHelper, Log

log = Log()
env = EnvHelper()

"""
Some icons exist in one library or the other, with no good overlap.
Use icon-* class to map to seemingly unrelated icons

For example: 
    The "Downtimes" menu item had a bed icon for FA, but BI has no bed icon. BI has a
    sunset icon, but FA does not. It wouldn't make sense to globally map fa-bed to bi-sunset, 
    so the placeholder icon-downtime will map to bed or sunset based on the library in use 
"""
icon_translations = {
    "icon-downtime": {'fa': 'fa-bed', 'bi': 'bi-sunset'},
    "icon-test": {'fa': 'fa-flask', 'bi': 'bi-thermometer-low'},
}
non_icons = [
    "fa", "fa-fw", "fa-2x", "fa-3x", "fa-4x", "fa-5x", "fa-6x", "fa-spin", "fa-pulse",
    "bi", "bi-fw", "bi-2x", "bi-3x", "bi-4x", "bi-5x", "bi-6x", "bi-spin", "bi-pulse",
]
spinning_icons = [
    # Any icon can spin... but these make more sense than others
    "bi-fan",
    "bi-flower1", "bi-flower2", "bi-flower3",
    "bi-cookie", "bi-egg-fried",
    "bi-gear", "bi-gear-fill", "bi-gear-wide",
    "bi-hypnotize", "bi-life-preserver", "bi-radioactive",
    "bi-yin-yang",
    "bi-arrow-clockwise", "bi-arrow-repeat",
]
missing_icon_class = "bi-emoji-frown text-danger"

def get_icon_provider():
    page = env.get_session_variable("icon_provider")
    setting = env.get_setting("ICON_PROVIDER", "BOOTSTRAP_ICONS")
    return page or setting


def set_icon_provider(ip):
    env.set_session_variable("icon_provider", ip.upper().strip() if ip else None)


def get_fa_version():
    # Use session when available in case setting was overridden by a template-tag
    page = env.get_session_variable("fa_version")
    setting = env.get_setting("FONT_AWESOME_VERSION", "4")
    return page or setting


def set_fa_version(v):
    return env.set_session_variable("fa_version", v)


def get_bi_version():
    # Use session when available in case setting was overridden by a template-tag
    page = env.get_session_variable("bi_version")
    setting = env.get_setting("BOOTSTRAP_ICONS_VERSION", "1.11.3")
    return page or setting


def set_bi_version(v):
    return env.set_session_variable("bi_version", v)


def use_font_awesome():
    return get_icon_provider() in ["FONT_AWESOME", "FA"]


def use_bootstrap_icons():
    return get_icon_provider() in ["BOOTSTRAP", "BOOTSTRAP_ICONS", "BI"]


def get_converted_icons():
    return env.get_session_variable("bad_fa_classes") or []


def clear_converted_icons():
    return env.set_session_variable("bad_fa_classes", None)


def save_converted_icons(icon_list):
    env.set_session_variable("bad_fa_classes", list(set(icon_list)))


def add_converted_icon(original, resulting):
    il = get_converted_icons()
    if resulting:
        il.append(f"\n\t- {original} (auto-updated to {resulting})")
    else:
        il.append(f"\n\t- {original} (NEEDS MANUAL REVIEW)")
    save_converted_icons(il)


def translate_icon(class_name):
    if class_name and class_name.startswith("icon-"):
        if class_name in icon_translations:
            k = 'fa' if use_font_awesome() else 'bi'
            class_name = icon_translations.get(class_name).get(k)
    return class_name


def clean_icon_class(class_name):
    if not class_name:
        return ""

    # if multiple classes given, handle that here
    if " " in class_name:
        classes = class_name.split()
        revised = []
        fas = bis = 0
        for cn in classes:
            if cn.startswith("fa-") and cn not in non_icons:
                fas += 1
            elif cn.startswith("bi-") and cn not in non_icons:
                bis += 1

        for cn in classes:
            if cn in non_icons:
                # Convert and use all icon modifiers
                revised.append(clean_icon_class(cn))
            elif not (cn.startswith("fa-") or cn.startswith("bi-")):
                # Use all non-icon classes (i.e. text-danger, text-success) - No conversion needed
                revised.append(cn)

            # If fa- and bi- icons were given
            elif fas and bis:
                if use_font_awesome() and cn.startswith("fa-"):
                    revised.append(clean_icon_class(cn))
                elif use_bootstrap_icons() and cn.startswith("bi-"):
                    revised.append(clean_icon_class(cn))

            # Only one library icon was specified. Convert and use it
            else:
                revised.append(clean_icon_class(cn))

        # If multiple icons were specified, and some were found while others were not, then
        # the missing-icon indicator must be removed (the found icon should be used)
        # FA4 -> FA6+ does not add a missing-icon indicator

        if missing_icon_class in revised:
            found = False
            for cn in revised:
                if cn == missing_icon_class:
                    continue
                elif cn in non_icons:
                    continue
                elif cn.startswith("bi-"):
                    found = True
                    break
            if found:
                revised.remove(missing_icon_class)

        return " ".join(revised)

    if use_font_awesome():
        return clean_fa_class(translate_icon(class_name))

    if use_bootstrap_icons():
        return fa_to_bootstrap(translate_icon(class_name))

    else:
        log.warning(f"Invalid icon library: {get_icon_provider()}")
        return class_name


def replace_with_spinner(icon_classes, message="Loading..."):
    """
    As-of 8.0.3, this is likely not needed anymore.
    """
    text_classes = [x for x in icon_classes if x.startswith("text-")]
    text_class = text_classes[0] if text_classes else ""

    return f"""
    <div class="spinner-border {text_class}" role="status">
        <span class="visually-hidden">{message or ""}</span>
    </div>
    """


def clean_fa_class(class_name):
    fa_version = get_fa_version()

    # Conversion only needed for versions other than 4
    if fa_version == "4":
        return class_name

    if not class_name:
        return ""

    if class_name in ["bi", "fa"]:
        return "fa"

    ocn = class_name

    # Some classes no longer exist
    class_name = {
        "fa-bitbucket-square": "fa-bitbucket",
        "fa-cc": "fa-closed-captioning",
        "fa-circle-thin": "fa-circle",
        "fa-facebook-official": "fa-facebook",
        "fa-file-movie-o": "fa-file-video",
        "fa-file-photo-o": "fa-file-image",
        "fa-file-picture-o": "fa-file-image",
        "fa-file-sound-o": "fa-file-audio",
        "fa-file-zip-o": "fa-file-zipper",
        "fa-files-o": "fa-file-lines",
        "fa-flash": "fa-bolt",
        "fa-floppy-o": "fa-floppy-disk",
        "fa-glass": "fa-martini-glass",
        "fa-group": "fa-users",
        "fa-hand-o-down": "fa-hand-point-down",
        "fa-hand-o-left": "fa-hand-point-left",
        "fa-hand-o-right": "fa-hand-point-right",
        "fa-hand-o-up": "fa-hand-point-up",
        "fa-hand-stop-o": "fa-hand",
        "fa-hard-of-hearing": "fa-ear-deaf",
        "fa-intersex": "fa-transgender",
        "fa-life-bouy": "fa-life-ring",
        "fa-life-saver": "fa-life-ring",
        "fa-linkedin-square": "fa-linkedin",
        "fa-money": "fa-money-bill-1",
        "fa-pencil-square-o": "fa-pen-to-square",
        "fa-photo": "fa-image",
        "fa-picture-o": "fa-image",
        "fa-s15": "fa-bath",
        "fa-send": "fa-paper-plane",
        "fa-send-o": "fa-paper-plane",
        "fa-sign-out": "fa-arrow-right-from-bracket",
        "fa-star-half-empty": "fa-star-half-stroke",
        "fa-star-half-full": "fa-star-half-stroke",
        "fa-support": "fa-life-ring",
        "fa-toggle-down": "fa-square-carat-down",
        "fa-toggle-left": "fa-square-carat-left",
        "fa-toggle-right": "fa-square-carat-right",
        "fa-toggle-up": "fa-square-carat-up",
        "fa-trash-o": "fa-trash-can",
        "fa-youtube-play": "fa-youtube",
    }.get(class_name, class_name)

    # -o is no longer used in any class names
    if class_name.endswith("-o"):
        class_name = class_name[:-2]

    if ocn != class_name:
        add_converted_icon(ocn, class_name)

    return class_name


def fa_to_bootstrap(class_name):
    if not class_name:
        return ""

    if class_name in ["bi", "fa"]:
        return "bi"

    if class_name == "bi-random-spinner":
        return random.choice(spinning_icons)

    # Only need to convert fa- classes
    if class_name.startswith("fa-"):
        ocn = class_name

        # -o is no longer used in any class names
        if class_name.endswith("-o"):
            class_name = class_name[:-2]

        # Convert any FA classes used by the psu-plugins so that they will work with either icon library
        class_name = {
            # Non-Icon Classes
            "fa-2x": "bi-2x",
            "fa-3x": "bi-3x",
            "fa-4x": "bi-4x",
            "fa-5x": "bi-5x",
            "fa-6x": "bi-6x",
            "fa-fw": "bi-fw",
            "fa-pulse": "bi-pulse",
            "fa-spin": "bi-spin",

            # Icon Classes
            "fa-address-card-o": "bi-person-vcard",
            "fa-address-card": "bi-person-vcard-fill",
            "fa-angle-right": "bi-chevron-right",
            "fa-angle-left": "bi-chevron-left",
            "fa-angle-up": "bi-chevron-up",
            "fa-angle-down": "bi-chevron-down",
            "fa-angle-double-right": "bi-chevron-double-right",
            "fa-angle-double-left": "bi-chevron-double-left",
            "fa-angle-double-up": "bi-chevron-double-up",
            "fa-angle-double-down": "bi-chevron-double-down",
            "fa-arrows-h": "bi-arrows",
            "fa-bars": "bi-list",
            "fa-bullhorn": "bi-megaphone",
            "fa-caret-square-o-up": "bi-caret-up-square",
            "fa-caret-square-o-right": "bi-caret-right-square",
            "fa-caret-square-o-down": "bi-caret-down-square",
            "fa-caret-square-o-left": "bi-caret-left-square",
            "fa-circle-check": "bi-check-circle-fill",
            "fa-circle-check-o": "bi-check-circle",
            "fa-cog": "bi-gear",
            "fa-comment": "bi-chat",
            "fa-commenting": "bi-chat-dots",
            "fa-close": "bi-x",
            "fa-cube": "bi-box",
            "fa-cubes": "bi-boxes",
            "fa-edit": "bi-pencil-square",
            "fa-exchange": "bi-arrow-left-right",
            "fa-external-link": "bi-box-arrow-up-right",
            "fa-frown": "bi-emoji-frown",
            "fa-globe": "bi-globe-americas",
            "fa-graduation-cap": "bi-mortarboard-fill",
            "fa-hashtag": "bi-hash",
            "fa-history": "bi-clock-history",
            "fa-home": "bi-house-door",
            "fa-hourglass-end": "bi-hourglass-bottom",
            "fa-hourglass-half": "bi-hourglass-split",
            "fa-hourglass-start": "bi-hourglass-top",
            "fa-id-badge": "bi-person-vcard",
            "fa-id-card": "bi-person-vcard",
            "fa-list-alt": "bi-card-list",
            "fa-map-marker": "bi-geo-alt",
            "fa-medkit": "bi-heart-pulse",
            "fa-microchip": "bi-cpu",
            "fa-minus-circle": "bi-dash-circle-fill",
            "fa-minus-square": "bi-dash-square",
            "fa-money": "bi-cash",
            "fa-object-group": "bi-easel",
            "fa-paper-plane": "bi-send",
            "fa-power-off": "bi-power",
            "fa-print": "bi-printer",
            "fa-quote-left": "bi-quote",
            "fa-quote-right": "bi-quote",
            "fa-refresh": "bi-arrow-repeat",
            "fa-remove": "bi-x",
            "fa-shield": "bi-shield-shaded",
            "fa-shopping-cart": "bi-cart",
            "fa-sign-in": "bi-box-arrow-in-right",
            "fa-sign-out": "bi-box-arrow-right",
            "fa-smile": "bi-emoji-smile",
            "fa-snowflake-o": "bi-snow3",
            "fa-sort-amount-desc": "bi-sort-numeric-down-alt",
            "fa-sort-amount-asc": "bi-sort-numeric-up-alt",
            "fa-spinner": "bi-hypnotize",
            "fa-thumbs-o-down": "bi-hand-thumbs-down",
            "fa-thumbs-o-up": "bi-hand-thumbs-up",
            "fa-times-circle": "bi-x-circle-fill",
            "fa-times-circle-o": "bi-x-circle",
            "fa-undo": "bi-arrow-counterclockwise",
            "fa-unlock-alt": "bi-unlock",
            "fa-usd": "bi-cash",
            "fa-user": "bi-person",
            "fa-user-circle": "bi-person-circle",
            "fa-user-secret": "bi-incognito",
            "fa-users": "bi-people",
            "fa-video-camera": "bi-camera-reels",
            "fa-window-close": "bi-x-square",
        }.get(class_name, class_name)

        # No need to log or do further processing for mapped conversions
        if class_name.startswith("bi") and ocn != class_name:
            return class_name

        # Swap fa- with bi- and see if it is a valid icon
        if class_name.startswith("fa-"):
            class_name = f"bi-{class_name[3:]}"

        if env.is_development and class_name.startswith("bi-"):
            if class_name not in non_icons:
                from base.fixtures.bi_icons import bi_classes
                if class_name not in bi_classes:
                    class_name = missing_icon_class

        if ocn != class_name:
            add_converted_icon(ocn, class_name if class_name != missing_icon_class else None)

    return class_name
