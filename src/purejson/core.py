from collections import UserDict, UserList


class DotKeyError(ValueError):
    """Raised when a key containing '.' is inserted."""


class PathError(KeyError):
    """Raised when a dotted path cannot be resolved on read."""


_MISSING = object()


def _check_key(key):
    if isinstance(key, str) and "." in key:
        raise DotKeyError(
            f"keys may not contain '.', got {key!r}. "
            "PureJson reserves '.' for path syntax (matches MongoDB/DocumentDB)."
        )


def _wrap(value):
    if isinstance(value, Document) or isinstance(value, Collection):
        return value
    if isinstance(value, dict):
        return Document(value)
    if isinstance(value, list):
        return Collection(value)
    return value


def _reject_dotted_keys(obj):
    """Recursively reject any dict key containing '.'. Runs at external-data boundaries."""
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


def _walk_get(root, parts):
    node = root
    for i, part in enumerate(parts):
        if isinstance(node, (dict, UserDict)):
            if part not in node:
                raise PathError(".".join(parts[: i + 1]))
            node = node[part]
        elif isinstance(node, (list, UserList)):
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


def _walk_set(root, parts, value):
    node = root
    for part in parts[:-1]:
        if isinstance(node, (dict, UserDict)):
            if part not in node or not isinstance(node[part], (dict, UserDict)):
                node[part] = Document()
            node = node[part]
        else:
            raise PathError(
                f"cannot descend into non-dict at segment {part!r} "
                f"while setting {'.'.join(parts)!r}"
            )
    last = parts[-1]
    _check_key(last)
    node[last] = value


class Document(UserDict):
    """Dict-like document. Supports dotted paths. Forbids '.' in keys.

    d['a.b.c'] == d['a']['b']['c']
    d['a.b.c'] = 5   # auto-creates intermediates
    """

    def __init__(self, data=None, /, **kwargs):
        super().__init__()
        if data is not None:
            _reject_dotted_keys(data)
            if isinstance(data, (dict, UserDict)):
                for k, v in data.items():
                    self.data[k] = _wrap(v)
            else:
                for k, v in dict(data).items():
                    self.data[k] = _wrap(v)
        if kwargs:
            _reject_dotted_keys(kwargs)
            for k, v in kwargs.items():
                self.data[k] = _wrap(v)

    def __setitem__(self, key, value):
        if not isinstance(key, str):
            _check_key(key)
            self.data[key] = _wrap(value)
            return
        if "." in key:
            parts = key.split(".")
            for p in parts:
                if p == "":
                    raise DotKeyError(f"empty path segment in {key!r}")
            _walk_set(self, parts, _wrap(value))
            return
        self.data[key] = _wrap(value)

    def __getitem__(self, key):
        if isinstance(key, str) and "." in key:
            return _walk_get(self, key.split("."))
        try:
            return self.data[key]
        except KeyError:
            raise

    def __contains__(self, key):
        if isinstance(key, str) and "." in key:
            try:
                _walk_get(self, key.split("."))
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
    """List-like collection. First-level entries should be Documents (like MongoDB).

    c[0]['a.b'] works (the element is a Document).
    Indexing with a string segment in a path walk raises PathError unless the segment
    is an integer string.
    """

    def __init__(self, data=None):
        super().__init__()
        if data is not None:
            _reject_dotted_keys(data)
            for item in data:
                self.data.append(_wrap(item))

    def append(self, item):
        self.data.append(_wrap(item))

    def insert(self, i, item):
        self.data.insert(i, _wrap(item))

    def __setitem__(self, i, item):
        self.data[i] = _wrap(item)

    def __repr__(self):
        return f"Collection({self.data!r})"
