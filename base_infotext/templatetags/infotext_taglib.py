from django import template
from base.classes.util.log import Log
from base.templatetags.tag_processing import supporting_functions as support
from django.utils.safestring import mark_safe
from django.template import TemplateSyntaxError
from base_infotext.services import infotext_service

register = template.Library()
log = Log()


@register.simple_tag(takes_context=True)
def infotext(context, code, alt, replacements=None, auto_prefix=True, group_title=None):
    """
    Render user-editable text content
    """
    attrs = {"code": code, "alt": alt, "auto_prefix": str(auto_prefix)}
    if replacements:
        attrs["replacements"] = replacements
    if group_title:
        attrs["group_title"] = group_title

    return prepare_infotext(attrs, alt)


@register.filter
def itext(code, alt=""):
    """
    Filter that returns infotext

        Use case: HTML around infotext content only to be rendered if infotext content exists

        {%with text_content="my_text_code|itext"%}
            {%if text_content%}
            ...
    """
    return mark_safe(infotext_service.get_infotext(code, alt))


@register.tag()
def infotext_block(parser, token):
    """
    Render user-editable text content
    """
    tokens = token.split_contents()
    try:
        nodelist = parser.parse((f"end_{tokens[0]}",))
        parser.delete_first_token()
    except TemplateSyntaxError:
        nodelist = None

    return InfotextNode(nodelist, tokens)


class InfotextNode(template.Node):
    def __init__(self, nodelist, tokens):
        self.nodelist = nodelist
        self.tokens = tokens

    def render(self, context):
        attrs, body = support.get_tag_params(self.nodelist, self.tokens, context)
        return prepare_infotext(attrs, body)


def prepare_infotext(attrs, alt_text):
    """
    Prepare infotext for both tags (inline and block)
    """
    # Do not include "code" in the attrs, it's a positional argument
    code = attrs.get("code")
    if code:
        del attrs["code"]

    # Remove indenting from the infotext_block tag
    if alt_text:
        new_lines = []
        lines = alt_text.splitlines()

        # Find the first line with actual content
        first_line = ""
        for ll in lines:
            if ll.strip():
                first_line = ll
                break

        # Determine base indentation of content block
        base_indent = len(first_line) - len(first_line.lstrip())

        # Strip base indent from each line (for display in textarea when editing via UI)
        for ll in lines:
            indent = len(ll) - len(ll.lstrip())
            sp = indent - base_indent
            new_lines.append(f"{' ' * sp}{ll.strip()}")
        alt_text = "\n".join(new_lines)
        del new_lines
        del lines

    return mark_safe(infotext_service.get_infotext(code, alt_text, **attrs))
