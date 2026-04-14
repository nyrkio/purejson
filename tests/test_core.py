import pytest
from purejson import Document, Collection, DotKeyError, PathError


def test_empty_document():
    d = Document()
    assert d == {}
    assert len(d) == 0


def test_basic_get_set():
    d = Document({"a": 1})
    assert d["a"] == 1
    d["b"] = 2
    assert d["b"] == 2


def test_equals_plain_dict():
    assert Document({"a": 1}) == {"a": 1}
    assert Document({"a": 1, "b": {"c": 2}}) == {"a": 1, "b": {"c": 2}}
    assert Document({"a": 1}) != {"a": 2}


def test_equals_plain_list_for_collection():
    assert Collection([{"a": 1}]) == [{"a": 1}]


def test_nested_dict_becomes_document():
    d = Document({"a": {"b": 1}})
    assert isinstance(d["a"], Document)
    assert d["a"]["b"] == 1


def test_nested_list_becomes_collection():
    d = Document({"xs": [{"a": 1}, {"a": 2}]})
    assert isinstance(d["xs"], Collection)
    assert isinstance(d["xs"][0], Document)


def test_dotted_path_read():
    d = Document({"a": {"b": {"c": 5}}})
    assert d["a.b.c"] == 5


def test_dotted_path_write_into_existing():
    d = Document({"a": {"b": {}}})
    d["a.b.c"] = 5
    assert d["a"]["b"]["c"] == 5


def test_dotted_path_write_auto_creates():
    d = Document()
    d["a.b.c"] = 5
    assert d == {"a": {"b": {"c": 5}}}


def test_dotted_path_read_missing_raises():
    d = Document({"a": {}})
    with pytest.raises(PathError):
        _ = d["a.b.c"]


def test_empty_path_segment_rejected():
    d = Document()
    with pytest.raises(DotKeyError):
        d[".leading"] = 1
    with pytest.raises(DotKeyError):
        d["trailing."] = 1
    with pytest.raises(DotKeyError):
        d["a..b"] = 1


def test_dotted_key_in_input_rejected_top_level():
    with pytest.raises(DotKeyError):
        Document({"a.b": 1})


def test_dotted_key_in_input_rejected_nested():
    with pytest.raises(DotKeyError):
        Document({"outer": {"leaf.dot": 1}})


def test_dotted_key_in_input_rejected_inside_collection():
    with pytest.raises(DotKeyError):
        Collection([{"a.b": 1}])
    with pytest.raises(DotKeyError):
        Document({"xs": [{"a.b": 1}]})


def test_contains_supports_path():
    d = Document({"a": {"b": 1}})
    assert "a.b" in d
    assert "a.c" not in d


def test_get_default_on_missing_path():
    d = Document({"a": {}})
    assert d.get("a.b.c", "fallback") == "fallback"
    assert d.get("a.b.c") is None


def test_collection_indexes_via_int_path_segment():
    d = Document({"xs": [{"a": 10}, {"a": 20}]})
    assert d["xs.0.a"] == 10
    assert d["xs.1.a"] == 20


def test_collection_rejects_non_int_segment():
    d = Document({"xs": [{"a": 10}]})
    with pytest.raises(PathError):
        _ = d["xs.foo"]


def test_repr_is_useful():
    d = Document({"a": 1})
    r = repr(d)
    assert "Document" in r and "'a': 1" in r


def test_round_trip_json_like():
    import json
    original = {"a": 1, "b": {"c": [1, 2, {"d": 3}]}}
    d = Document(original)
    # UserDict serializes via its .data — but json needs a plain dict.
    # Document exposes .data; we round-trip through json.dumps(dict(d)) for now.
    # (A custom encoder lives in ExtendedJsonSchema.)
    as_json = json.dumps(d.data, default=lambda o: o.data if hasattr(o, "data") else o)
    assert json.loads(as_json) == original
