import pytest
from purejson import Collection, Document, doc, col, query, find_one


def _sample():
    return col([
        doc(name="a", score=10, tags=["x"], attrs={"k": 1}),
        doc(name="b", score=20, tags=["x", "y"], attrs={"k": 2}),
        doc(name="c", score=30, tags=["y"], attrs={"k": 3}),
    ])


def test_query_equality():
    c = _sample()
    r = c.query({"name": "b"})
    assert len(r) == 1
    assert r[0]["name"] == "b"


def test_query_dotted_path():
    c = _sample()
    r = c.query({"attrs.k": 2})
    assert len(r) == 1
    assert r[0]["name"] == "b"


def test_query_operators():
    c = _sample()
    r = c.query({"score": {"$gte": 20}})
    assert [d["name"] for d in r] == ["b", "c"]

    r = c.query({"score": {"$gt": 10, "$lt": 30}})
    assert [d["name"] for d in r] == ["b"]


def test_query_in():
    c = _sample()
    r = c.query({"name": {"$in": ["a", "c"]}})
    assert [d["name"] for d in r] == ["a", "c"]


def test_query_missing_field_no_match():
    c = _sample()
    assert len(c.query({"nope": 1})) == 0
    assert len(c.query({"nope": {"$gte": 1}})) == 0


def test_query_unknown_operator_raises():
    c = _sample()
    with pytest.raises(ValueError):
        c.query({"score": {"$weird": 1}})


def test_query_sort_asc_desc():
    c = _sample()
    r = c.query({}, sort={"score": -1})
    assert [d["name"] for d in r] == ["c", "b", "a"]
    r = c.query({}, sort={"score": 1})
    assert [d["name"] for d in r] == ["a", "b", "c"]


def test_query_limit():
    c = _sample()
    r = c.query({}, sort={"score": 1}, limit=2)
    assert [d["name"] for d in r] == ["a", "b"]


def test_find_one_returns_first_match_or_none():
    c = _sample()
    d = c.find_one({"name": "b"})
    assert d is not None
    assert d["name"] == "b"
    assert c.find_one({"name": "missing"}) is None


def test_query_result_shares_element_references():
    c = _sample()
    r = c.query({"name": "b"})
    # Mutating a matched element writes back to the source collection.
    r[0]["score"] = 999
    assert c.find_one({"name": "b"})["score"] == 999


def test_query_result_list_is_independent():
    c = _sample()
    r = c.query({})
    r.data.clear()
    assert len(c) == 3  # source untouched


def test_query_module_level_helpers():
    c = _sample()
    assert len(query(c, {"score": {"$gte": 20}})) == 2
    assert find_one(c, {"name": "a"})["score"] == 10


def test_query_operator_handles_incomparable_types():
    c = col([doc(v=1), doc(v="two"), doc(v=3)])
    # str vs int comparison should not crash, just not match.
    r = c.query({"v": {"$gte": 2}})
    assert [d["v"] for d in r] == [3]
