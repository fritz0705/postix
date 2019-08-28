from django import template

register = template.Library()


def _urlreplace(dict_, *pairs):
    key = None
    for p in pairs:
        if key is None:
            key = p
        else:
            if p == "":
                if key in dict_:
                    del dict_[key]
            else:
                dict_[key] = p
            key = None
    return dict_


@register.simple_tag
def urlreplace(request, *pairs):
    return _urlreplace(request.GET.copy(), *pairs).urlencode(safe="[]")
