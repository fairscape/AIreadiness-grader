"""ARK GUID generation for the FAIRSCAPE RO-Crate wizard.

Used by emitted build_rocrate.py scripts. Produces GUIDs of the form
``ark:59853/<prefix>-<slug>-<squid>`` (e.g. ``ark:59853/dataset-raw-images-1a2b3c4d5e``).
"""

from __future__ import annotations

import datetime
import random
import re

NAAN = "59853"


def _squid() -> str:
    ts = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
    rand = random.randint(0, 99999)
    return f"{ts:x}{rand:04x}"


def slugify(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"\s+", "-", s)
    s = s.replace(".", "-").replace("/", "-")
    s = re.sub(r"[^a-z0-9-]", "", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "entity"


def generate_guid(prefix: str, name: str = "") -> str:
    """Return ``ark:59853/<prefix>-<slug>-<squid>`` (slug omitted if name is empty)."""
    squid = _squid()
    if name:
        return f"ark:{NAAN}/{prefix}-{slugify(name)}-{squid}"
    return f"ark:{NAAN}/{prefix}-{squid}"
