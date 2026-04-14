"""Root-anchor wrappers over plain dict/list.

Storage is always plain dict / list. `Document` and `Collection` are anchors
that add dotted-path semantics and key-validation at the root. Nested dicts
and lists are *not* wrapped in storage; on read, they are returned as fresh
Document/Collection views that alias the same underlying object (mutations
through the view propagate to storage, since `.data` is a reference, not a copy).

    d = Document()
    d["a.b.c.d"] = 1
    repr(d) == "Document({'a': {'b': {'c': {'d': 1}}}})"
    isinstance(d["a"], Document)  # True, but it's a view over the inner dict
"""
from collections import UserDict, UserList


class DotKeyError(ValueError):
    """Raised when a key containing '.' is inserted."""


class PathError(KeyError):
    """Raised when a dotted path cannot be resolved on read."""


def _check_segment(key):
    if isinstance(key, str) and "." in key:
        raise DotKeyError(
            f"keys may not contain '.', got {key!r}. "
            "PureJson reserves '.' for path syntax (matches MongoDB/DocumentDB)."
        )


def _reject_dotted_keys(obj):
    """Recursively reject any dict key containing '.'. Runs at the Document/Collection
    boundary — once data is admitted, storage is known clean."""
    if isinstance(obj, (dict, UserDict)):
        for k, v in obj.items():
            if isinstance(k, str) and "." in k:
                raise DotKeyError(
                    f"key {k!r} contains '.'; PureJson forbids dots in keys "
                    "(matches MongoDB/DocumentDB). Dotted paths are the runtime API only."
                )
            _reject_dotted_keys(v)
    elif isinstance(obj, (list, UserList)):
        for v in obj:
            _reject_dotted_keys(v)


def _unwrap(v):
    """Strip a Document/Collection wrapper to its underlying dict/list."""
    if isinstance(v, (Document, Collection)):
        return v.data
    return v


def _to_plain(obj):
    """Deep-copy to plain dict/list, unwrapping any Document/Collection along the way.
    Called at admission boundaries so storage never contains wrapper instances."""
    if isinstance(obj, (Document, Collection)):
        obj = obj.data
    if isinstance(obj, dict):
        return {k: _to_plain(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_plain(v) for v in obj]
    return obj


def _view(v):
    """Wrap a plain dict/list as a fresh view; pass other values through."""
    if isinstance(v, dict):
        return Document._view(v)
    if isinstance(v, list):
        return Collection._view(v)
    return v


def _walk_get(root, parts):
    node = root
    for i, part in enumerate(parts):
        if isinstance(node, dict):
            if part not in node:
                raise PathError(".".join(parts[: i + 1]))
            node = node[part]
        elif isinstance(node, list):
            try:
                idx = int(part)
            except ValueError:
                raise PathError(".".join(parts[: i + 1]))
            try:
                node = node[idx]
            except IndexError:
                raise PathError(".".join(parts[: i + 1]))
        else:
            raise PathError(".".join(parts[: i + 1]))
    return node


def _walk_set(root_data, parts, value):
    node = root_data
    for part in parts[:-1]:
        if isinstance(node, dict):
            if part not in node or not isinstance(node[part], dict):
                node[part] = {}
            node = node[part]
        else:
            raise PathError(
                f"cannot descend into non-dict at segment {part!r} "
                f"while setting {'.'.join(parts)!r}"
            )
    last = parts[-1]
    _check_segment(last)
    node[last] = value


class Document(UserDict):
    """Dict-like root anchor. Supports dotted paths. Forbids '.' in stored keys."""

    def __init__(self, data=None, /, **kwargs):
        if data is None:
            self.data = {}
        else:
            _reject_dotted_keys(data)
            plain = _to_plain(data)
            if not isinstance(plain, dict):
                plain = dict(plain)
            self.data = plain
        if kwargs:
            _reject_dotted_keys(kwargs)
            self.data.update({k: _to_plain(v) for k, v in kwargs.items()})

    @classmethod
    def _view(cls, raw_dict):
        """Construct a view Document that aliases an already-validated dict (no re-check)."""
        inst = cls.__new__(cls)
        inst.data = raw_dict
        return inst

    def __setitem__(self, key, value):
        if isinstance(value, (dict, list, Document, Collection)):
            _reject_dotted_keys(value)
            value = _to_plain(value)
        if not isinstance(key, str):
            self.data[key] = value
            return
        if "." in key:
            parts = key.split(".")
            for p in parts:
                if p == "":
                    raise DotKeyError(f"empty path segment in {key!r}")
            _walk_set(self.data, parts, value)
            return
        self.data[key] = value

    def __getitem__(self, key):
        if isinstance(key, str) and "." in key:
            return _view(_walk_get(self.data, key.split(".")))
        return _view(self.data[key])

    def __contains__(self, key):
        if isinstance(key, str) and "." in key:
            try:
                _walk_get(self.data, key.split("."))
                return True
            except PathError:
                return False
        return key in self.data

    def get(self, key, default=None):
        try:
            return self[key]
        except (KeyError, PathError):
            return default

    def __repr__(self):
        return f"Document({self.data!r})"


class Collection(UserList):
    """List-like root anchor. Elements stay plain in storage; reads return views."""

    def __init__(self, data=None):
        if data is None:
            self.data = []
        else:
            _reject_dotted_keys(data)
            plain = _to_plain(data)
            if not isinstance(plain, list):
                plain = list(plain)
            self.data = plain

    @classmethod
    def _view(cls, raw_list):
        inst = cls.__new__(cls)
        inst.data = raw_list
        return inst

    def _admit(self, item):
        if isinstance(item, (dict, list, Document, Collection)):
            _reject_dotted_keys(item)
            return _to_plain(item)
        return item

    def append(self, item):
        self.data.append(self._admit(item))

    def insert(self, i, item):
        self.data.insert(i, self._admit(item))

    def __setitem__(self, i, item):
        self.data[i] = self._admit(item)

    def __getitem__(self, i):
        if isinstance(i, slice):
            return Collection._view(self.data[i])
        return _view(self.data[i])

    def __iter__(self):
        for v in self.data:
            yield _view(v)

    def query(self, filter_=None, sort=None, limit=None):
        from .query import query as _query
        return _query(self, filter_, sort, limit)

    def find_one(self, filter_=None):
        from .query import find_one as _find_one
        return _find_one(self, filter_)

    def __repr__(self):
        return f"Collection({self.data!r})"
