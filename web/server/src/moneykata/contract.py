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
    # The release is stated by the document but would make every version bump a contract
    # change; the committed file names the series only.
    doc["info"]["version"] = "see web/VERSION"
    return doc


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
