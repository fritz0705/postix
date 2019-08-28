from functools import partial

try:
    from rest_framework.decorators import action

    detail_route = partial(action, detail=True)
    list_route = partial(action, detail=False)
except ImportError:
    from rest_framework.decorators import detail_route, list_route  # noqa
