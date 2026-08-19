"""Evidence items — the building blocks of a criterion's presentation.

Every `present_*` function returns a list of these dicts. Each has a `label`,
a `kind`, and a `value`; the HTML template and the LLM grader both consume the
same structure, so keep kinds to this small set:

  text     free text (may be long; already truncated at build time)
  bool     True / False / None (None renders as "not checked / unknown")
  count    integer, optionally "n of total" via `of`
  percent  0-100 float plus the n/total it came from
  link     href (+ optional display text); hrefs are crate-relative paths
           or absolute URLs
  links    list of {href, text}
  list     list of short strings
  entity   a trimmed JSON-LD entity, shown collapsible in HTML
"""


def text(label, value, detail=None):
    return _item(label, "text", value, detail)


def flag(label, value, detail=None):
    return _item(label, "bool", value, detail)


def count(label, n, of=None, detail=None):
    item = _item(label, "count", n, detail)
    if of is not None:
        item["of"] = of
    return item


def percent(label, n, total, detail=None):
    pct = round(100.0 * n / total, 1) if total else None
    item = _item(label, "percent", pct, detail)
    item["n"] = n
    item["total"] = total
    return item


def link(label, href, display=None, detail=None):
    item = _item(label, "link", href, detail)
    if display:
        item["text"] = display
    return item


def links(label, pairs, detail=None):
    """pairs: list of (href, display) tuples or {href, text} dicts."""
    vals = []
    for p in pairs:
        if isinstance(p, dict):
            vals.append(p)
        else:
            vals.append({"href": p[0], "text": p[1]})
    return _item(label, "links", vals, detail)


def listing(label, values, detail=None):
    return _item(label, "list", list(values), detail)


def entity(label, entity_dict, detail=None):
    return _item(label, "entity", entity_dict, detail)


def _item(label, kind, value, detail):
    item = {"label": label, "kind": kind, "value": value}
    if detail:
        item["detail"] = detail
    return item


# --- shared text helpers ---------------------------------------------------

TRUNCATE_AT = 1500


def clip(value, limit=TRUNCATE_AT):
    """Flatten a metadata value to a display string, truncated with a marker."""
    if value is None:
        return None
    if isinstance(value, list):
        value = "; ".join(str(v) for v in value)
    value = str(value)
    if len(value) > limit:
        return value[:limit].rstrip() + f" …[truncated, {len(value)} chars total]"
    return value


def substantive(value, min_chars=120):
    """The rubric's boilerplate test: present, longer than a one-liner, and not
    a bare "no known bias/issues" disclaimer."""
    s = clip(value, 10_000)
    if not s:
        return False
    import re
    if re.fullmatch(r"\s*(none|n/?a|no known \w+\.?)\s*", s, re.I):
        return False
    return len(s) >= min_chars
