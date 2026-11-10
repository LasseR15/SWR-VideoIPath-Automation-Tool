import pytest

from videoipath_automation_tool.utils import cross_app_utils
from videoipath_automation_tool.utils.cross_app_errors import ApiQueryTooLongError


def test_encode_preserves_grammar_characters_and_encodes_quotes_and_spaces() -> None:
    encoded = cross_app_utils.encode_req_path("/a b/*/x,y/'z'/\"q\"")
    assert "%20" in encoded  # space encoded
    assert "%22" in encoded  # double-quote encoded
    assert "/*/" in encoded  # star preserved
    assert "'z'" in encoded  # single-quote preserved

def test_query_too_long_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cross_app_utils, "MAX_QUERY_LENGTH", 10)
    with pytest.raises(ApiQueryTooLongError):
        cross_app_utils.encode_req_path("demo-url-to-encode-and-throw-error")
