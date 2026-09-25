"""fairscape-evidence: collect AI-readiness evidence from dataset metadata.

    fairscape-evidence /path/to/crate -o out/            # RO-Crate directory
    fairscape-evidence metadata.json -o out/             # Croissant / JSON-LD file
    fairscape-evidence kaggle:owner/slug -o out/         # Kaggle Croissant export
    fairscape-evidence hf:org/name -o out/               # Hugging Face Croissant
    fairscape-evidence https://…/croissant.json -o out/  # any URL

Remote documents are cached in the output directory.

Writes ai-ready-evidence.json (evidence for the LLM grader) and
ai-ready-review.html (the human review page). Links to datasheets and
evidence graphs are resolved relative to the output directory.
"""

import argparse
import json
import os
import sys
from pathlib import Path

from .pipeline import build_presentation
from .render import render_review
from .source import is_remote


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="fairscape-evidence", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("crate", help="RO-Crate directory, metadata file (RO-Crate, "
                                      "Croissant or schema.org JSON-LD), URL, or "
                                      "kaggle:owner/slug / hf:org/name")
    parser.add_argument("-o", "--out", default="ai-ready-review",
                        help="output directory (default: ./ai-ready-review)")
    parser.add_argument("--no-network", action="store_true",
                        help="skip URL resolution / registry lookups")
    parser.add_argument("--json-only", action="store_true",
                        help="write the evidence JSON but not the HTML")
    parser.add_argument("--zip", metavar="ZIP",
                        help="also write a shareable zip of the review page plus every "
                             "datasheet, preview and graph it links to")
    parser.add_argument("-q", "--quiet", action="store_true")
    args = parser.parse_args(argv)

    source = args.crate if is_remote(args.crate) else Path(args.crate).resolve()
    if not is_remote(args.crate) and not source.exists():
        parser.error(f"not found: {source}")
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    progress = (lambda msg: None) if args.quiet else \
        (lambda msg: print(msg, file=sys.stderr))

    try:
        presentation = build_presentation(
            source, network=not args.no_network, progress=progress, cache_dir=out_dir)
    except (FileNotFoundError, ValueError) as err:
        parser.error(str(err))
    crate_dir = Path(presentation["crate"]["path"])

    json_path = out_dir / "ai-ready-evidence.json"
    json_path.write_text(json.dumps(presentation, indent=2, ensure_ascii=False))
    print(json_path)

    if not args.json_only:
        link_base = os.path.relpath(crate_dir, out_dir).replace(os.sep, "/")
        html_path = out_dir / "ai-ready-review.html"
        html_path.write_text(render_review(presentation, link_base=link_base))
        print(html_path)
        if args.zip:
            from .bundle import bundle_review
            bundle_review(html_path, args.zip, crate_dir=crate_dir, progress=progress)
            print(Path(args.zip).resolve())


if __name__ == "__main__":
    main()
