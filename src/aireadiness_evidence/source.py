"""Where the metadata comes from, and what dialect it is.

The grader accepts four kinds of input and reduces them all to one JSON
document plus a directory that crate-relative links resolve against:

  crate directory       <dir>/ro-crate-metadata.json (RO-Crate 1.x)
  metadata file         any .json / .jsonld — RO-Crate, Croissant, or plain
                        schema.org JSON-LD
  http(s) URL           fetched once and cached next to the review output
  kaggle:<owner>/<slug> / hf:<org>/<name> — shortcuts for the Croissant
                        exports that Kaggle and Hugging Face publish

Dialect detection is deliberately loose: it only decides how the document is
turned into a flat entity list (see ``crate.flatten_document``) and which
criteria get a "not expressible in this format" note.
"""

import json
import re
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path

USER_AGENT = "fairscape-evidence/0.1 (AI-readiness rubric evidence builder)"

KAGGLE_PAGE_RE = re.compile(r"^https?://(www\.)?kaggle\.com/datasets/([^/?#]+)/([^/?#]+)/?(\?.*)?$")
KAGGLE_EXPORT_RE = re.compile(r"^https?://(www\.)?kaggle\.com/datasets/([^/?#]+)/([^/?#]+)/croissant/download")
HF_PAGE_RE = re.compile(r"^https?://huggingface\.co/datasets/([^/?#]+)/([^/?#]+)/?$")

FORMAT_LABELS = {
    "ro-crate": "RO-Crate",
    "croissant": "Croissant",
    "jsonld": "schema.org JSON-LD",
}


@dataclass
class Source:
    doc: dict
    root_dir: Path        # directory crate-relative paths resolve against
    meta_path: Path       # the JSON file that was read (or written, for URLs)
    label: str            # what the user passed in, for the report header
    format: str           # ro-crate | croissant | jsonld
    remote: bool = False


def expand_shortcut(text):
    """Turn the kaggle:/hf: shortcuts and dataset landing-page URLs into the
    URL of their Croissant export. Anything else is returned unchanged."""
    if text.startswith("kaggle:"):
        owner, slug = text[len("kaggle:"):].strip("/").split("/", 1)
        return f"https://www.kaggle.com/datasets/{owner}/{slug}/croissant/download"
    if text.startswith(("hf:", "huggingface:")):
        ref = text.split(":", 1)[1].strip("/")
        return f"https://huggingface.co/api/datasets/{ref}/croissant"
    m = KAGGLE_PAGE_RE.match(text)
    if m and not text.rstrip("/").endswith("/croissant/download"):
        return f"https://www.kaggle.com/datasets/{m.group(2)}/{m.group(3)}/croissant/download"
    m = HF_PAGE_RE.match(text)
    if m:
        return f"https://huggingface.co/api/datasets/{m.group(1)}/{m.group(2)}/croissant"
    return text


def is_remote(text):
    return isinstance(text, str) and (
        text.startswith(("http://", "https://", "kaggle:", "hf:", "huggingface:")))


def fetch_json(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                               "Accept": "application/ld+json, application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    return json.loads(raw.decode("utf-8"))


def detect_format(doc):
    """ro-crate for a @graph document, croissant when the context or
    conformsTo names the Croissant namespace, jsonld otherwise."""
    if isinstance(doc.get("@graph"), list):
        return "ro-crate"
    conforms = doc.get("conformsTo")
    conforms = conforms if isinstance(conforms, list) else [conforms]
    for c in conforms:
        if isinstance(c, dict):
            c = c.get("@id", "")
        if isinstance(c, str) and "mlcommons.org/croissant" in c:
            return "croissant"
    if "mlcommons.org/croissant" in json.dumps(doc.get("@context", "")):
        return "croissant"
    return "jsonld"


def _cache_name(url):
    m = KAGGLE_EXPORT_RE.match(url)
    if m:
        return f"kaggle-{m.group(2)}-{m.group(3)}.croissant.json"
    m = re.match(r"^https?://huggingface\.co/api/datasets/([^/]+)/([^/]+)/croissant", url)
    if m:
        return f"hf-{m.group(1)}-{m.group(2)}.croissant.json"
    tail = re.sub(r"[^A-Za-z0-9._-]+", "-", url.split("://", 1)[-1]).strip("-")
    return (tail[:80] or "metadata") + ".json"


def resolve_source(source, cache_dir=None):
    """Load `source` (see module docstring) into a Source.

    Remote documents are written to `cache_dir` (a temp dir when None) so the
    review is reproducible and crate-relative links have somewhere to point.
    """
    text = str(source)
    if is_remote(text):
        url = expand_shortcut(text)
        doc = fetch_json(url)
        cache_dir = Path(cache_dir) if cache_dir else Path(tempfile.mkdtemp(prefix="fairscape-evidence-"))
        cache_dir.mkdir(parents=True, exist_ok=True)
        meta_path = cache_dir / _cache_name(url)
        meta_path.write_text(json.dumps(doc, indent=2, ensure_ascii=False))
        return Source(doc=doc, root_dir=cache_dir, meta_path=meta_path,
                      label=url, format=detect_format(doc), remote=True)

    path = Path(text).resolve()
    if path.is_dir():
        meta_path = path / "ro-crate-metadata.json"
        if not meta_path.exists():
            candidates = sorted(p for p in path.glob("*.json*")
                                if p.suffix in (".json", ".jsonld"))
            if len(candidates) == 1:
                meta_path = candidates[0]
            else:
                raise FileNotFoundError(
                    f"no ro-crate-metadata.json in {path}; pass the metadata file directly")
    elif path.is_file():
        meta_path = path
    else:
        raise FileNotFoundError(f"metadata source not found: {source}")
    doc = json.loads(meta_path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError(f"{meta_path} is not a JSON object")
    return Source(doc=doc, root_dir=meta_path.parent, meta_path=meta_path,
                  label=str(path), format=detect_format(doc))
