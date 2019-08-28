import pytest

from postix.core.templatetags.urlreplace import _urlreplace


@pytest.mark.parametrize(
    "pairs,expected",
    (
        ({"pairs": ["a", "b"]}, {"a": "b", "b": "b", "c": "c"}),
        ({"pairs": ["b", ""]}, {"a": "a", "c": "c"}),
    ),
)
def test_core_urlreplace(pairs, expected):
    assert _urlreplace({"a": "a", "b": "b", "c": "c"}, *pairs["pairs"]) == expected
