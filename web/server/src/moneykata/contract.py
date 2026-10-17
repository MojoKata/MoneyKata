"""The generated contract (requirements R3.9, S17.5): the OpenAPI document comes from the
routes, and the browser app's JSDoc types come from it. `web/check` fails when either file is
out of date.

    python -m moneykata.contract write    regenerate both files
    python -m moneykata.contract check    fail if either differs from what the routes give
"""

import json
import re
import sys
from pathlib import Path

from . import paths

OPENAPI_FILE = paths.UI / "api" / "openapi.json"
TYPES_FILE = paths.UI / "api" / "types.js"


def openapi_document() -> dict:
    from fastapi.openapi.utils import get_openapi

    from .app import Server, create_app
    from .config import Config

    config = Config(
        name="contract",
        mode="proxy",
        data_dir=Path("/nonexistent/data"),
        backup_dir=Path("/nonexistent/backups"),
    )
    app = create_app(Server(config=config))
    doc = get_openapi(
        title="MoneyKata",
        version=app.version,
        routes=app.routes,
        description="The browser app's API, /ui/api (requirements S13.8). It is "
        "served with the app and carries no version of its own.",
    )
    # The release, from web/VERSION (S13.8.9): a version bump changes the document too.
    _problems(doc)
    _created(doc)
    return doc


PROBLEM_CALLS = {"Problem", "refuse", "FieldError", "_send_problem"}


def problem_codes() -> list[str]:
    """Every stable code the server answers a problem with (S13.8.3), read from its source:
    the second argument of Problem(), refuse(), FieldError() and the middleware's problems."""
    import ast

    codes: set[str] = set()
    for path in paths.PACKAGE.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, ast.Call) or len(node.args) < 2:
                continue
            f = node.func
            name = (
                f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
            )
            arg = node.args[1]
            if (
                name in PROBLEM_CALLS
                and isinstance(arg, ast.Constant)
                and isinstance(arg.value, str)
            ):
                codes.add(arg.value)
    return sorted(codes)


def _problems(doc: dict) -> None:
    """The problem document (RFC 9457) as a schema, its codes listed, and as every
    operation's default response."""
    codes = problem_codes()
    schemas = doc.setdefault("components", {}).setdefault("schemas", {})
    schemas["ProblemFieldError"] = {
        "type": "object",
        "required": ["field", "code", "message"],
        "properties": {
            "field": {"type": ["string", "null"]},
            "code": {"type": "string", "enum": codes},
            "message": {"type": "string"},
        },
    }
    schemas["Problem"] = {
        "type": "object",
        "description": "A refusal (S13.8.3): its code is one of those listed, and stable.",
        "required": ["type", "title", "status", "detail", "code", "errorId", "errors"],
        "properties": {
            "type": {"type": "string", "format": "uri"},
            "title": {"type": "string"},
            "status": {"type": "integer"},
            "detail": {"type": "string"},
            "code": {"type": "string", "enum": codes},
            "errorId": {"type": "string"},
            "errors": {
                "type": "array",
                "items": {"$ref": "#/components/schemas/ProblemFieldError"},
            },
        },
    }
    doc["components"].setdefault("responses", {})["Problem"] = {
        "description": "A refusal, as application/problem+json.",
        "content": {
            "application/problem+json": {"schema": {"$ref": "#/components/schemas/Problem"}}
        },
    }
    for ops in doc.get("paths", {}).values():
        for op in ops.values():
            if isinstance(op, dict) and "responses" in op:
                op["responses"].setdefault("default", {"$ref": "#/components/responses/Problem"})


def _created(doc: dict) -> None:
    """Every 201 names what it made in `Location` (S13.8.4)."""
    for ops in doc.get("paths", {}).values():
        for op in ops.values():
            made = op.get("responses", {}).get("201") if isinstance(op, dict) else None
            if made is not None:
                made.setdefault("headers", {})["Location"] = {
                    "description": "Where what was made is read.",
                    "schema": {"type": "string"},
                }


def openapi_json(doc: dict | None = None) -> str:
    return (
        json.dumps(doc or openapi_document(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    )


def _js_type(schema: dict) -> str:
    if "$ref" in schema:
        return _ident(schema["$ref"].rsplit("/", 1)[-1])
    if "const" in schema:
        return json.dumps(schema["const"])
    if "enum" in schema:
        return "(" + " | ".join(json.dumps(v) for v in schema["enum"]) + ")"
    for key in ("anyOf", "oneOf"):
        if key in schema:
            parts = []
            for s in schema[key]:
                t = _js_type(s)
                if t not in parts:
                    parts.append(t)
            return "(" + " | ".join(parts) + ")" if len(parts) > 1 else parts[0]
    if "allOf" in schema and len(schema["allOf"]) == 1:
        return _js_type(schema["allOf"][0])
    t = schema.get("type")
    if t == "number" and schema.get("format") in ("money", "decimal"):
        # An exact number (S13.8.2): the client decodes it as a Dec, never a float.
        return "import('../app/dec.js').Dec"
    if t == "string":
        return "string"
    if t in ("integer", "number"):
        return "number"
    if t == "boolean":
        return "boolean"
    if t == "null":
        return "null"
    if t == "array":
        return f"Array<{_js_type(schema.get('items', {}))}>"
    if t == "object":
        extra = schema.get("additionalProperties")
        if isinstance(extra, dict):
            return f"Object<string, {_js_type(extra)}>"
        return "Object<string, unknown>"
    return "unknown"


def _ident(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_$]", "_", name)


def types_js(doc: dict | None = None) -> str:
    doc = doc or openapi_document()
    lines = [
        "// Generated from the API's OpenAPI document by `python -m moneykata.contract write`.",
        "// Do not edit: web/check fails when this file differs from what the routes give.",
        "",
    ]
    schemas = doc.get("components", {}).get("schemas", {})
    for name in sorted(schemas):
        schema = schemas[name]
        lines.append("/**")
        if schema.get("description"):
            for d in schema["description"].strip().splitlines():
                lines.append(f" * {d}".rstrip())
        if schema.get("type") == "object" or "properties" in schema:
            lines.append(f" * @typedef {{Object}} {_ident(name)}")
            required = set(schema.get("required", []))
            for prop, ps in schema.get("properties", {}).items():
                optional = prop not in required
                label = f"[{prop}]" if optional else prop
                lines.append(f" * @property {{{_js_type(ps)}}} {label}")
        else:
            lines.append(f" * @typedef {{{_js_type(schema)}}} {_ident(name)}")
        lines.append(" */")
        lines.append("")
    lines.append("export {};")
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    command = argv[1] if len(argv) > 1 else ""
    doc = openapi_document()
    wanted = {OPENAPI_FILE: openapi_json(doc), TYPES_FILE: types_js(doc)}
    if command == "write":
        for path, text in wanted.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        return 0
    if command == "check":
        stale = [p for p, text in wanted.items() if not p.exists() or p.read_text() != text]
        for p in stale:
            print(
                f"{p.relative_to(paths.ROOT)} is out of date: run "
                "`python -m moneykata.contract write`",
                file=sys.stderr,
            )
        return 1 if stale else 0
    print(__doc__.strip())
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
