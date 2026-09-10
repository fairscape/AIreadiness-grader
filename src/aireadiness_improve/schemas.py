"""JSON schemas the page validates edits against.

Generated from the fairscape_models pydantic classes at build time — the same
models `fairscape-cli rocrate validate` and the JS `@fairscape/utils`
generators (AJV) use — so a crate the page downloads passes the same checks.
"""

import json


def build_schemas():
    """{"root": <ROCrateMetadataElem schema>, "software": <Software schema>,
    "version": fairscape_models version}. Empty dict if the package is
    missing, in which case the page skips validation and says so."""
    try:
        from fairscape_models.rocrate import ROCrateMetadataElem
        from fairscape_models.software import Software
    except ImportError:
        return {}
    try:
        from importlib.metadata import version
        ver = version("fairscape-models")
    except Exception:  # pragma: no cover - metadata lookup is best-effort
        ver = "unknown"
    root = ROCrateMetadataElem.model_json_schema()
    software = Software.model_json_schema()
    # round-trip through JSON so the template embeds plain data
    return json.loads(json.dumps({"root": root, "software": software, "version": ver}))
