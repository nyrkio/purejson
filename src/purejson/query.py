"""MongoDB-style query over Collections of plain dicts.

Filter syntax:
  {"field": value}                       # equality
  {"dotted.path": value}                 # nested equality
  {"field": {"$gte": 10, "$lt": 100}}    # operator clauses

Supported operators: $eq $ne $gt $gte $lt $lte $in $nin.

Returns a fresh Collection view; element references are shared with the source
(mutations on a matched element write back), but the result list itself is
independent (append/remove does not touch the source).
"""
from .core import Document, Collection, _walk_get, PathError


_MISSING = object()

_OPS = {
    "$eq": lambda a, b: a == b,
    "$ne": lambda a, b: a != b,
    "$gt": lambda a, b: a > b,
    "$gte": lambda a, b: a >= b,
    "$lt": lambda a, b: a < b,
    "$lte": lambda a, b: a <= b,
    "$in": lambda a, b: a in b,
    "$nin": lambda a, b: a not in b,
}


def _path_get(obj, key):
    if isinstance(obj, (Document, Collection)):
        obj = obj.data
    if not isinstance(obj, (dict, list)):
        return _MISSING
    try:
        return _walk_get(obj, key.split(".") if "." in key else [key])
    except (PathError, KeyError):
        return _MISSING


def _is_operator_clause(v):
    return isinstance(v, dict) and v and all(
        isinstance(k, str) and k.startswith("$") for k in v
    )


def _matches(doc, filter_):
    for k, expected in filter_.items():
        actual = _path_get(doc, k)
        if _is_operator_clause(expected):
            if actual is _MISSING:
                return False
            for op, operand in expected.items():
                fn = _OPS.get(op)
                if fn is None:
                    raise ValueError(f"unknown query operator {op!r}")
                try:
                    if not fn(actual, operand):
                        return False
                except TypeError:
                    return False
        else:
            if actual is _MISSING or actual != expected:
                return False
    return True


def _sort_key(d, path):
    v = _path_get(d, path)
    # Missing values sort after present ones; keeps sort total even with mixed shapes.
    return (1, None) if v is _MISSING else (0, v)


def query(collection, filter_=None, sort=None, limit=None):
    """Filter a Collection. Returns a new Collection view over matched elements."""
    filter_ = filter_ or {}
    items = collection.data if isinstance(collection, Collection) else list(collection)
    hits = [d for d in items if _matches(d, filter_)]
    if sort:
        for key, direction in reversed(list(sort.items())):
            hits.sort(key=lambda d, k=key: _sort_key(d, k), reverse=(direction == -1))
    if limit is not None:
        hits = hits[:limit]
    return Collection._view(hits)


def find_one(collection, filter_=None):
    """Return the first element matching `filter_`, or None."""
    filter_ = filter_ or {}
    items = collection.data if isinstance(collection, Collection) else list(collection)
    for d in items:
        if _matches(d, filter_):
            return Document._view(d) if isinstance(d, dict) else d
    return None
