from .core import Document, Collection, DotKeyError, PathError
from .query import query, find_one

# Lower-case aliases that mirror dict()/list() ergonomics.
doc = Document
col = Collection

__all__ = [
    "Document", "Collection", "doc", "col",
    "DotKeyError", "PathError",
    "query", "find_one",
]
