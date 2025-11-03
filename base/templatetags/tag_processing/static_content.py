from django import template
from django.utils.html import format_html, mark_safe
from base.services import icon_service
from base.classes.util.app_data import EnvHelper, Log, AppData

log = Log()
env = EnvHelper()
app = AppData()


def image_url():
    return f"{env.static_content_url}/images"


def lib_url():
    return f"{env.static_content_url}/lib"


def app_url(version='v1'):
    return f"{env.static_content_url}/{version}"


def jquery(*args, **kwargs):
    return format_html(f"""
    <script
      src="https://code.jquery.com/jquery-3.7.1.min.js"
      integrity="sha256-/JqT3SQfawRcv/BIHPThkBvs0OEvtFFmqPF/lYI/Cxo="
      crossorigin="anonymous"></script>
    """)


def wysiwyg(*args, **kwargs):
    ready = '$(document).ready(function(){ prepare_wysiwyg(); });'
    return mark_safe(f"""
    <link href="https://cdn.quilljs.com/1.3.6/quill.snow.css" rel="stylesheet">
    <script src="https://cdn.quilljs.com/1.3.6/quill.js"></script>
    <script type="text/javascript">
        {ready}
    </script>
    """)


def bootstrap(*args, **kwargs):
    css = f"https://stackpath.bootstrapcdn.com/bootstrap/{kwargs.get('version', '5.3.0')}/css/bootstrap.min.css"
    js = f"https://stackpath.bootstrapcdn.com/bootstrap/{kwargs.get('version', '5.3.0')}/js/bootstrap.min.js"
    return format_html(
        f"""
        <script src="https://cdnjs.cloudflare.com/ajax/libs/popper.js/2.9.2/umd/popper.min.js" integrity="sha512-2rNj2KJ+D8s1ceNasTIex6z4HWyOnEYLVC3FigGOmyQCZc2eBXKgOxQmo3oKLHyfcj53uz4QMsRCWNbLd32Q1g==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.6/dist/css/bootstrap.min.css" rel="stylesheet" integrity="sha384-4Q6Gf2aSP4eDXB8Miphtr37CMZZQ5oXLH2yaXMJ2w8e2ZtHTl7GptT4jmndRuHDT" crossorigin="anonymous">
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.6/dist/js/bootstrap.bundle.min.js" integrity="sha384-j1CDi7MgGQ12Z7Qab0qlWQ/Qqz24Gc6BM0thvEMVjHnfYGF0rmFCozFSxQBxwHKO" crossorigin="anonymous"></script>
        """
    )


def datatables(*args, **kwargs):
    return format_html(
        f"""
        <link rel="stylesheet" href="https://cdn.datatables.net/2.3.1/css/dataTables.dataTables.min.css" />
        <script src="https://cdn.datatables.net/2.3.1/js/dataTables.min.js"></script>
        """
    )


def jquery_confirm(*args, **kwargs):
    defaults = """
        <script type="text/javascript">
            jconfirm.defaults = {
                title: false,
                content: 'Are you sure?',
                contentLoaded: function(){},
                icon: '',
                confirmButton: 'Okay',
                cancelButton: 'Cancel',
                confirmButtonClass: 'btn-default',
                cancelButtonClass: 'btn-default',
                theme: 'modern',
                animation: 'Rotate',
                closeAnimation: 'scale',
                animationSpeed: 500,
                animationBounce: 1.2,
                keyboardEnabled: true,
                rtl: false,
                confirmKeys: [13], // ENTER key
                cancelKeys: [27], // ESC key
                container: 'body',
                confirm: function () {},
                cancel: function () {},
                backgroundDismiss: false,
                autoClose: false,
                closeIcon: null,
                columnClass: 'col-md-4 col-md-offset-4 col-sm-6 col-sm-offset-3 col-xs-10 col-xs-offset-1',
                onOpen: function(){},
                onClose: function(){},
                onAction: function(){}
            };
        </script>
    """
    js = f"""<script src="https://cdnjs.cloudflare.com/ajax/libs/jquery-confirm/{kwargs.get('version', '3.3.4')}/jquery-confirm.min.js" integrity="sha512-zP5W8791v1A6FToy+viyoyUUyjCzx+4K8XZCKzW28AnCoepPNIXecxh9mvGuy3Rt78OzEsU+VCvcObwAMvBAww==" crossorigin="anonymous"></script>"""
    css = f"""<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/jquery-confirm/{kwargs.get('version', '3.3.4')}/jquery-confirm.min.css" integrity="sha512-0V10q+b1Iumz67sVDL8LPFZEEavo6H/nBSyghr7mm9JEQkOAm91HNoZQRvQdjennBb/oEuW+8oZHVpIKq+d25g==" crossorigin="anonymous" />"""
    return f"""
    {js}
    {css}
    {defaults}
    """


def chosen(*args, **kwargs):
    return format_html(
        f"""
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/chosen/1.8.7/chosen.min.css" 
            integrity="sha512-yVvxUQV0QESBt1SyZbNJMAwyKvFTLMyXSyBHDO4BG5t7k/Lw34tyqlSDlKIrIENIzCl+RVUNjmCPG+V/GMesRw==" 
            crossorigin="anonymous" />
        <script src="https://cdnjs.cloudflare.com/ajax/libs/chosen/1.8.7/chosen.jquery.min.js" 
            integrity="sha512-rMGGF4wg1R73ehtnxXBt5mbUfN9JUJwbk21KMlnLZDJh7BkPmeovBuddZCENJddHYYMkCh9hPFnPmS9sspki8g==" 
            crossorigin="anonymous"></script>
        <script src="{app_url()}/js/chosen-apply.js"></script>
        """
    )


def tom_select(*args, **kwargs):
    url = env.static_content_url
    v = kwargs["version"] if "version" in kwargs else "2.3.1"
    tom_dir = f"{url}/wdt/tom_select/{v}"


    return mark_safe(
        f"""
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/tom-select/2.4.3/css/tom-select.bootstrap5.min.css" integrity="sha512-gKMzEZw+6phm9jAZ9p9x0MdnT2I8U+cv68/UFA0y/RhG4zh2OKSCW4jkjGTzSXvS9oxxKzJD1Om9VD6xKf8y0A==" crossorigin="anonymous" referrerpolicy="no-referrer" />
        <script src="https://cdnjs.cloudflare.com/ajax/libs/tom-select/2.4.3/js/tom-select.complete.js" integrity="sha512-cv8SyZZkoW3eB3rWs0JsM/wNxKZe59+tMN8ewVIu24I1EAeBOT6lqkdty/iMxo3OJGvrFRYIrrGwM5BJqAXsYw==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>
        """ +
        """
        <script type="text/javascript">
            var tom_selects = {};
            function activate_tom_selects(){
                var tom_select_counter = 0;
                $("select.tom-select").each(function(){
                    tom_select_counter += 1;
                    let el = $(this);
                    let id = el.attr("id");
                    if(typeof id === "undefined"){
                        id = `auto-ts-${tom_select_counter}`;
                        el.attr("id", id);
                    }
                    tom_selects[id] = new TomSelect(el, {maxOptions: null});
                });
            }
            function reset_tom_select(id_or_el, clear_selected){
                let ts_id;
                if(typeof id_or_el === "object"){
                    ts_id = id_or_el.attr("id");
                }
                else{
                    ts_id = id_or_el;
                }
                if(typeof clear_selected === "undefined"){
                    clear_selected = false;
                }
                try{
                    let ts = tom_selects[ts_id];
                    if(clear_selected){
                        ts.clear();
                    }
                    ts.clearOptions();
                    ts.sync();
                }
                catch(ee){
                    console.log(ee);
                }
            }
            $(document).ready(function(){activate_tom_selects();});
        </script>
        """
    )


def font_awesome(*args, **kwargs):
    version = kwargs.get('version', 'current')
    url = f"{lib_url()}/fontawesome/{version}"

    # FontAwesome 4 is CSS rather than SVG
    if version == '4':
        return format_html(
            f"""<link rel="stylesheet" href="{url}/css/font-awesome.min.css" />"""
        )

    else:
        return format_html(
            f"""<script defer src="{url}/js/all.js"></script>"""
        )

def icon_library(*args, **kwargs):
    return mark_safe(
        f"""<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/bootstrap-icons/1.11.3/font/bootstrap-icons.min.css" integrity="sha512-dPXYcDub/aeb08c63jRq/k6GaKccl256JQy/AnOq7CAnEZ9FzSL9wSbcZkMp4R26vBsMLFYH4kQ67/bbV8XaCQ==" crossorigin="anonymous" referrerpolicy="no-referrer" />""" +
        """
        <style>
        .bi-fw{display:inline-block;width: 1em; height:1em;}
        .bi-2x{font-size:2em;}
        .bi-3x{font-size:3em;}
        .bi-4x{font-size:4em;}
        .bi-5x{font-size:5em;}
        .bi-6x{font-size:6em;}
        .bi-spin {
          display: inline-block;
          width: auto !important;
          height: auto !important;
          -webkit-animation: bi-spin 2s infinite linear;
          animation: bi-spin 2s infinite linear;
        }
        .bi-pulse {
          display: inline-block;
          width: auto !important;
          height: auto !important;
          -webkit-animation: bi-spin 1s infinite steps(8);
          animation: bi-spin 1s infinite steps(8);
        }
        @-webkit-keyframes bi-spin {
          0% {
            -webkit-transform: rotate(0deg);
            transform: rotate(0deg);
          }
          100% {
            -webkit-transform: rotate(359deg);
            transform: rotate(359deg);
          }
        }
        @keyframes bi-spin {
          0% {
            -webkit-transform: rotate(0deg);
            transform: rotate(0deg);
          }
          100% {
            -webkit-transform: rotate(359deg);
            transform: rotate(359deg);
          }
        }
        </style>
        """
    )


def cdn_css(*args, **kwargs):
    version = kwargs.get('version', 'v1')
    url = f"{app_url(version)}/css"
    v = app.get_app_version()
    def vv(css):
        return css if "?" in css else f"{css}?v={v}"
    return format_html("\n".join([f"""<link rel="stylesheet" href="{url}/{vv(css)}" />""" for css in args]))


def cdn_js(*args, **kwargs):
    version = kwargs.get('version', 'v1')
    url = f"{app_url(version)}/js"
    v = app.get_app_version()
    def vv(js):
        return js if "?" in js else f"{js}?v={v}"
    return format_html("\n".join([f"""<script src="{url}/{vv(js)}"></script>""" for js in args]))
