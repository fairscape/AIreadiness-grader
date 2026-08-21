"""fairscape-evidence: build the AI-readiness presentation for an RO-Crate.

    fairscape-evidence /path/to/crate -o out/

Writes ai-ready-presentation.json (evidence for the LLM grader) and
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


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="fairscape-evidence", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("crate", help="directory containing ro-crate-metadata.json")
    parser.add_argument("-o", "--out", default="ai-ready-review",
                        help="output directory (default: ./ai-ready-review)")
    parser.add_argument("--no-network", action="store_true",
                        help="skip URL resolution / registry lookups")
    parser.add_argument("--json-only", action="store_true",
                        help="write the presentation JSON but not the HTML")
    parser.add_argument("-q", "--quiet", action="store_true")
    args = parser.parse_args(argv)

    crate_dir = Path(args.crate).resolve()
    if not (crate_dir / "ro-crate-metadata.json").exists():
        parser.error(f"no ro-crate-metadata.json in {crate_dir}")
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    progress = (lambda msg: None) if args.quiet else \
        (lambda msg: print(msg, file=sys.stderr))

    presentation = build_presentation(
        crate_dir, network=not args.no_network, progress=progress)

    json_path = out_dir / "ai-ready-presentation.json"
    json_path.write_text(json.dumps(presentation, indent=2, ensure_ascii=False))
    print(json_path)

    if not args.json_only:
        link_base = os.path.relpath(crate_dir, out_dir).replace(os.sep, "/")
        html_path = out_dir / "ai-ready-review.html"
        html_path.write_text(render_review(presentation, link_base=link_base))
        print(html_path)


if __name__ == "__main__":
    main()
