"""Hard and soft response assertions.

Hard failures mean the run is not measuring what it claims to measure.
Soft failures are recorded as evidence but do not abort: the phase error
tolerance (30% normal, 70% payload) needs a place to live, and that place is
the soft bucket.

Python 3.9 compatible.
"""

from __future__ import annotations

import json
import re

__all__ = [
    "AssertionFailure", "AssertionOutcome", "AssertionReport", "evaluate",
    "evaluate_all", "normalise", "HARD", "SOFT", "SPEC_TYPES",
]

HARD = "hard"
SOFT = "soft"

SPEC_TYPES = (
    "status_equals", "status_in", "status_not_in", "status_class",
    "body_contains", "body_not_contains", "body_regex", "body_equals",
    "body_length_under", "body_length_over",
    "json_has_key", "json_equals", "json_contains", "json_length_under",
    "header_present", "header_absent", "header_equals", "header_contains",
    "latency_under_ms", "latency_over_ms",
    "content_type_contains",
)

class AssertionFailure(Exception):
    def __init__(self, report):
        self.report = report
        Exception.__init__(self, report.summary())

class AssertionOutcome(object):
    __slots__ = ("type", "severity", "ok", "detail", "spec")

    def __init__(self, type_, severity, ok, detail=None, spec=None):
        self.type = type_
        self.severity = severity
        self.ok = bool(ok)
        self.detail = detail
        self.spec = spec

    def to_dict(self):
        return {
            "type": self.type,
            "severity": self.severity,
            "ok": self.ok,
            "detail": self.detail,
        }

    def __repr__(self):
        return "<%s %s ok=%s>" % (self.severity, self.type, self.ok)

class AssertionReport(object):
    def __init__(self, outcomes=None):
        self.outcomes = list(outcomes or [])

    @property
    def hard_failures(self):
        return [o for o in self.outcomes if not o.ok and o.severity == HARD]

    @property
    def soft_failures(self):
        return [o for o in self.outcomes if not o.ok and o.severity == SOFT]

    @property
    def ok(self):
        return not self.hard_failures

    def summary(self):
        passed = sum(1 for o in self.outcomes if o.ok)
        return "%d/%d assertions passed (%d hard, %d soft failures)" % (
            passed, len(self.outcomes), len(self.hard_failures), len(self.soft_failures))

    def to_dict(self):
        return {
            "total": len(self.outcomes),
            "ok": self.ok,
            "hard_failures": [o.to_dict() for o in self.hard_failures],
            "soft_failures": [o.to_dict() for o in self.soft_failures],
        }

    def raise_if_hard(self):
        if self.hard_failures:
            raise AssertionFailure(self)

def _split_path(path):
    text = str(path).strip()
    if text.startswith("$"):
        text = text[1:]
    text = text.replace("[", ".").replace("]", "")
    return [part for part in text.split(".") if part != ""]

def _dig(document, path):
    current = document
    for part in _split_path(path):
        if isinstance(current, dict):
            if part not in current:
                raise KeyError(part)
            current = current[part]
        elif isinstance(current, (list, tuple)):
            current = current[int(part)]
        else:
            raise KeyError(part)
    return current

def _body_text(response):
    text = getattr(response, "text", None)
    if isinstance(text, str):
        return text
    body = getattr(response, "body", None) or b""
    return body.decode("utf-8", "replace")

def _header(response, name, default=None):
    for key, value in (getattr(response, "headers", None) or {}).items():
        if key.lower() == name.lower():
            return value
    return default

def _json_document(response, ctx):
    if ctx is not None and "_json_cache" in ctx:
        return ctx["_json_cache"]
    document = json.loads(_body_text(response) or "null")
    if ctx is not None:
        ctx["_json_cache"] = document
    return document

def _h_status_equals(params, response, elapsed, ctx):
    want = params.get("value")
    got = getattr(response, "status", None)
    return got == want, "status %r == %r" % (got, want)

def _h_status_in(params, response, elapsed, ctx):
    wanted = list(params.get("values") or [])
    got = getattr(response, "status", None)
    return got in wanted, "status %r in %r" % (got, wanted)

def _h_status_not_in(params, response, elapsed, ctx):
    forbidden = list(params.get("values") or [])
    got = getattr(response, "status", None)
    return got not in forbidden, "status %r not in %r" % (got, forbidden)

def _h_status_class(params, response, elapsed, ctx):
    klass = int(params.get("value") or params.get("class") or 2)
    got = getattr(response, "status", None) or 0
    return got // 100 == klass, "status %r is %dxx" % (got, got // 100)

def _h_body_contains(params, response, elapsed, ctx):
    needle = str(params.get("value", ""))
    return needle in _body_text(response), "body contains %r" % needle

def _h_body_not_contains(params, response, elapsed, ctx):
    needle = str(params.get("value", ""))
    return needle not in _body_text(response), "body excludes %r" % needle

def _h_body_equals(params, response, elapsed, ctx):
    want = str(params.get("value", ""))
    return _body_text(response) == want, "body equals %d chars" % len(want)

def _h_body_regex(params, response, elapsed, ctx):
    pattern = params.get("value") or params.get("pattern")
    flags = re.MULTILINE
    if params.get("ignore_case"):
        flags |= re.IGNORECASE
    found = re.search(pattern, _body_text(response), flags) is not None
    return found, "body matches %r" % pattern

def _h_body_length_under(params, response, elapsed, ctx):
    limit = int(params.get("value") or 0)
    length = len(getattr(response, "body", None) or b"")
    return length <= limit, "body length %d <= %d" % (length, limit)

def _h_body_length_over(params, response, elapsed, ctx):
    limit = int(params.get("value") or 0)
    length = len(getattr(response, "body", None) or b"")
    return length >= limit, "body length %d >= %d" % (length, limit)

def _h_json_has_key(params, response, elapsed, ctx):
    path = params.get("path") or params.get("value")
    _dig(_json_document(response, ctx), path)
    return True, "json has %s" % path

def _h_json_equals(params, response, elapsed, ctx):
    path = params.get("path")
    want = params.get("value")
    got = _dig(_json_document(response, ctx), path)
    return got == want, "json %s == %r" % (path, want)

def _h_json_contains(params, response, elapsed, ctx):
    path = params.get("path")
    want = params.get("value")
    container = _dig(_json_document(response, ctx), path) if path else _json_document(response, ctx)
    if isinstance(container, str):
        found = str(want) in container
    elif isinstance(container, dict):
        found = want in container or want in container.values()
    else:
        found = want in container
    return found, "json %s contains %r" % (path, want)

def _h_json_length_under(params, response, elapsed, ctx):
    path = params.get("path")
    limit = int(params.get("value") or 0)
    container = _dig(_json_document(response, ctx), path) if path else _json_document(response, ctx)
    length = len(container)
    return length <= limit, "json %s length %d <= %d" % (path, length, limit)

def _h_header_present(params, response, elapsed, ctx):
    name = params.get("name") or params.get("value")
    value = _header(response, name)
    return value is not None, "header %s present" % name

def _h_header_absent(params, response, elapsed, ctx):
    name = params.get("name") or params.get("value")
    return _header(response, name) is None, "header %s absent" % name

def _h_header_equals(params, response, elapsed, ctx):
    name = params.get("name")
    want = str(params.get("value", ""))
    got = _header(response, name)
    return got == want, "header %s == %r" % (name, want)

def _h_header_contains(params, response, elapsed, ctx):
    name = params.get("name")
    needle = str(params.get("value", ""))
    got = _header(response, name) or ""
    return needle in got, "header %s contains %r" % (name, needle)

def _h_latency_under(params, response, elapsed, ctx):
    limit = float(params.get("value") or 0)
    measured = elapsed if elapsed is not None else (getattr(response, "elapsed_ms", None) or 0.0)
    return measured <= limit, "latency %.1fms <= %.1fms" % (measured, limit)

def _h_latency_over(params, response, elapsed, ctx):
    limit = float(params.get("value") or 0)
    measured = elapsed if elapsed is not None else (getattr(response, "elapsed_ms", None) or 0.0)
    return measured >= limit, "latency %.1fms >= %.1fms" % (measured, limit)

def _h_content_type_contains(params, response, elapsed, ctx):
    needle = str(params.get("value", "")).lower()
    got = (_header(response, "content-type") or "").lower()
    return needle in got, "content-type %r contains %r" % (got, needle)

_HANDLERS = {
    "status_equals": _h_status_equals,
    "status_in": _h_status_in,
    "status_not_in": _h_status_not_in,
    "status_class": _h_status_class,
    "body_contains": _h_body_contains,
    "body_not_contains": _h_body_not_contains,
    "body_equals": _h_body_equals,
    "body_regex": _h_body_regex,
    "body_length_under": _h_body_length_under,
    "body_length_over": _h_body_length_over,
    "json_has_key": _h_json_has_key,
    "json_equals": _h_json_equals,
    "json_contains": _h_json_contains,
    "json_length_under": _h_json_length_under,
    "header_present": _h_header_present,
    "header_absent": _h_header_absent,
    "header_equals": _h_header_equals,
    "header_contains": _h_header_contains,
    "latency_under_ms": _h_latency_under,
    "latency_over_ms": _h_latency_over,
    "content_type_contains": _h_content_type_contains,
}

def normalise(spec):
    """Return ``(type, severity, params)``.

    Severity is SOFT when any of these is true: ``{"soft": true}``,
    ``{"severity": "soft"}``, type starts with ``soft.``, or type starts
    with ``soft_``.
    """
    if isinstance(spec, str):
        head, _, tail = spec.partition(":")
        spec = {"type": head.strip()}
        if tail:
            spec["value"] = tail.strip()
    if not isinstance(spec, dict):
        raise ValueError("assertion must be a mapping or string, got %r" % (spec,))

    type_ = str(spec.get("type") or "").strip()
    severity = HARD
    if spec.get("soft") is True or str(spec.get("severity", "")).lower() == SOFT:
        severity = SOFT
    if type_.startswith("soft."):
        severity = SOFT
        type_ = type_[5:]
    elif type_.startswith("soft_"):
        severity = SOFT
        type_ = type_[5:]

    if type_ not in _HANDLERS:
        raise ValueError("unknown assertion type: %r" % type_)
    return type_, severity, spec

def evaluate(spec, response, elapsed_ms=None, ctx=None):
    type_, severity, params = normalise(spec)
    handler = _HANDLERS[type_]
    try:
        ok, detail = handler(params, response, elapsed_ms, ctx)
    except Exception as exc:
        ok, detail = False, "%s: %s" % (type(exc).__name__, exc)
    return AssertionOutcome(type_, severity, ok, detail, params)

def evaluate_all(specs, response, elapsed_ms=None, ctx=None):
    return AssertionReport([evaluate(spec, response, elapsed_ms, ctx) for spec in (specs or [])])
