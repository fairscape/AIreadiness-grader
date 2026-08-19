"""Build a self-contained, emailable zip of an AI-readiness review.

    python3 examples/make_bundle.py examples/cm4ai-june-2026 /path/to/crate

Layout inside the zip (all links valid after unpacking):

    <name>/
      ai-ready-review.html       review page, links rewritten to crate/...
      ai-ready-presentation.json
      crate/                     datasheet, prov/evidence graphs, previews,
                                 and any local file the datasheet links,
                                 at their original crate-relative paths

The full data crate is NOT included — only the HTML artifacts and small
files the pages reference.
"""

import json
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from fairscape_evidence.render import render_review  # noqa: E402

LOCAL_HREF_RE = re.compile(r'href="([^"]+)"')


def collect_artifacts(presentation, crate_dir):
    """Crate-relative paths of every artifact the review links, plus every
    local file those pages reference themselves."""
    rels = set(presentation["artifacts"]["datasheets"])
    rels |= {g["href"] for g in presentation["artifacts"]["evidence_graphs"]}
    for sub in presentation["inventory"]["sub_crates"]:
        rels |= set(sub["prov_graphs"])
        if sub["preview"]:
            rels.add(sub["preview"])

    # datasheets link crate-relative previews/prov-graphs/score files
    for sheet in list(rels):
        path = crate_dir / sheet
        if not path.exists() or path.suffix != ".html":
            continue
        for href in LOCAL_HREF_RE.findall(path.read_text()):
            if href.startswith(("http://", "https://", "mailto:", "#", "data:")):
                continue
            if (crate_dir / href).is_file():
                rels.add(href)

    return sorted(r for r in rels if (crate_dir / r).is_file())


def main():
    review_dir = Path(sys.argv[1])
    crate_dir = Path(sys.argv[2])
    presentation = json.loads((review_dir / "ai-ready-presentation.json").read_text())

    name = review_dir.name + "-review"
    zip_path = review_dir / f"{name}.zip"
    html = render_review(presentation, link_base="crate")
    artifacts = collect_artifacts(presentation, crate_dir)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{name}/ai-ready-review.html", html)
        zf.write(review_dir / "ai-ready-presentation.json",
                 f"{name}/ai-ready-presentation.json")
        for rel in artifacts:
            zf.write(crate_dir / rel, f"{name}/crate/{rel}")

    print(f"{zip_path}  ({zip_path.stat().st_size / 1e6:.1f} MB, "
          f"{len(artifacts)} artifacts)")


if __name__ == "__main__":
    main()
