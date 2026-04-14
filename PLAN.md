# PureJson — PLAN

## Purpose
End-to-end dict/list data structures. No dataclasses, no pydantic, no homegrown classes between HTTP, python middleware, and DocumentDB persistence.

## Core types
- `Document` — root is dict. Subclass of `UserDict`.
- `Collection` — root is list, first-level entries must be Documents (mirrors MongoDB). Subclass of `UserList`.
- Both serialize as plain dict/list. `o["key"]` works; `o.key` is banned (no `__getattr__` shadowing).

## Path access
- `d["a.b.c"]` ≡ `d["a"]["b"]["c"]` — unambiguous because **dots in keys are forbidden** (matches MongoDB/DocumentDB, which forbid them anyway).
- `d["d.e.f"] = 5` auto-creates intermediates.
- Setting a key containing `.` raises `ValueError` at insert time. Same on `loads()` — refuse to parse JSON with dotted keys, with a clear error pointing at the offending key.

## Query layer
MongoDB aggregation-pipeline-like API on Collections:
```python
c.filter([{"$match": {"d.e.f": 5}}, {"$unwind": "x.y.z"}])
```
**Open question:** which name? Master plan suggests `aggregate` / `find` / `get` / `search` / `filter`. Recommend `query()` as the primary, with `filter()` as a thin alias for the common `$match`-only case (matches python's `filter()` mental model).

<<< Answer; query is fine. filter and anything else that is in the basic functions in python should be reserved for that use: get, map, filter, keys, etc...

## Class = Document + JSON Schema
Schema can be:
- standard JSON Schema, or
- a query expression ("anything matching this filter").

Schema attachment lives in PureJson but the schema *types* live in ExtendedJsonSchema (dependency).

<<< Clarification: By ExtendedJsonSchema I mean that we take the standard jsonschema and extend it. Preferably by a mechanism like subclassing, but seeing it is not object oriented, then we can make extended json schema a facade that replicates the jsonschema api fully, and simply delegates/passthru to jsonschema for existing functionality, and replaces or adds its own.
<<< In other words the user always does:

    import extjsonschema

or even

    import extjsonschema as jsonschema


## Debugging
- `__repr__` and `_repr_pretty_` (IPython) show full dict state, no truncation by default.
- `pprint(doc)` must Just Work.

## Non-goals
- Async iterators in v1 — sync only. Add later if profiling shows need.
- No magical attribute access. Ever.

## Dependencies
- python stdlib only. (`UserDict`, `UserList`, `collections.abc`.)

<<< And jsonschema


## Resolved
1. **Equality with plain dicts:** `Document({"a":1}) == {"a":1}` is true (UserDict default). Same for Collection vs list.
2. **Mutation tracking:** not in v1. Add only if/when JsonEE's DocumentDB persistence layer needs change-set diffs for efficient updates.
3. **Thread safety:** explicitly not provided. Documented in the README — single-threaded use, or caller-managed locks.
