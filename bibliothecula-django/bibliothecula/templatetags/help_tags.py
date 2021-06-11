from django import template
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def return_item(l, i):
    try:
        return l[i]
    except:
        return None


@register.simple_tag
def section_url(htmlid):
    ret = f"""<a id="header-anchor-{htmlid}" class="header-anchor" aria-hidden="true" href="#{htmlid}"><svg class="octicon octicon-link" viewBox="0 0 16 16" version="1.1" width="16" height="16" aria-hidden="true"><use href="#header-link-svg"></use></svg></a>"""
    return mark_safe(ret)
