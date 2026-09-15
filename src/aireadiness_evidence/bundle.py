"""fairscape-review-bundle: zip a review page together with everything it links to.

    fairscape-review-bundle review/ai-ready-review.html -o review.zip

The review page links to datasheets, previews and provenance graphs that live
inside the crate, usually via a relative path (``../my-crate/...``). Emailing
the HTML alone breaks those links. This walks every local link — recursively
through the linked HTML pages, which link on to sub-crate previews and graphs —
and writes a zip holding the review page, its presentation JSON, and the linked
files under ``crate/`` with their relative layout preserved, so every link keeps
working after unzipping anywhere.

Bundle a page written by the review's "Save review as HTML" button and the
scores travel with it.
"""

import argparse
import os
import re
import sys
import zipfile
from pathlib import Path
from urllib.parse import unquote

_LOCAL_LINK_RE = re.compile(r'\b(href|src)="([^"#][^"]*)"')
_REMOTE_PREFIXES = ("mailto:", "data:", "javascript:", "tel:", "doi:", "ark:")
# an html page's own links are only followed for these extensions — a preview
# may link to gigabytes of raw data; the reviewer wants the pages, not the data
_FOLLOW_SUFFIXES = {".html", ".htm", ".css", ".js", ".json", ".svg", ".png",
                    ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".md", ".txt"}


def _local_targets(html_path):
    """(match, target path) for every relative href/src in `html_path`."""
    text = html_path.read_text(encoding="utf-8", errors="replace")
    for m in _LOCAL_LINK_RE.finditer(text):
        raw = m.group(2)
        if "://" in raw or raw.startswith(_REMOTE_PREFIXES) or raw.startswith("//"):
            continue
        rel = unquote(raw.split("#", 1)[0].split("?", 1)[0])
        if not rel:
            continue
        yield raw, (html_path.parent / rel).resolve()


def collect_links(html_path, follow=True, max_bytes=None):
    """Return {resolved file path: set(raw hrefs)} for every existing local file
    reachable from `html_path`. Pages are followed transitively."""
    html_path = Path(html_path).resolve()
    found, queue, seen = {}, [html_path], {html_path}
    while queue:
        page = queue.pop()
        for raw, target in _local_targets(page):
            if not target.is_file():
                continue
            if page is not html_path and target.suffix.lower() not in _FOLLOW_SUFFIXES:
                continue
            if max_bytes is not None and target.stat().st_size > max_bytes:
                continue
            found.setdefault(target, set()).add(raw if page == html_path else None)
            if follow and target not in seen and target.suffix.lower() in (".html", ".htm"):
                seen.add(target)
                queue.append(target)
    return found


def bundle_review(html_path, zip_path, crate_dir=None, follow=True,
                  extra=(), progress=None):
    """Write `zip_path`. Returns the list of archive names written."""
    html_path = Path(html_path).resolve()
    say = progress or (lambda msg: None)
    links = collect_links(html_path, follow=follow)
    if crate_dir is None:
        crate_dir = _guess_crate_dir(html_path, links)
    crate_dir = Path(crate_dir).resolve()

    # rewrite the page's own links from "<rel>/<crate path>" to "crate/<crate path>"
    text = html_path.read_text(encoding="utf-8")
    rewrites = {}
    for target, raws in links.items():
        try:
            inside = target.relative_to(crate_dir).as_posix()
        except ValueError:
            inside = None
        for raw in raws:
            if raw is None:
                continue
            if inside is not None:
                rewrites[raw] = "crate/" + inside
            else:  # linked file outside the crate: keep it next to the page
                rewrites[raw] = "linked/" + target.name
    for raw, new in rewrites.items():
        text = text.replace(f'href="{raw}"', f'href="{new}"')
        text = text.replace(f'src="{raw}"', f'src="{new}"')

    written = []
    zip_path = Path(zip_path)
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(html_path.name, text)
        written.append(html_path.name)
        sidecars = [html_path.with_name(n) for n in
                    ("ai-ready-evidence.json", "ai-ready-presentation.json")]
        for f in [*sidecars, *map(Path, extra)]:
            if f.is_file() and f.resolve() != html_path:
                zf.write(f, f.name)
                written.append(f.name)
        for target in sorted(links):
            try:
                name = "crate/" + target.relative_to(crate_dir).as_posix()
            except ValueError:
                name = "linked/" + target.name
            zf.write(target, name)
            written.append(name)
            say(f"  + {name} ({target.stat().st_size:,} bytes)")
    return written


def _guess_crate_dir(html_path, links):
    """The crate root is the directory holding ro-crate-metadata.json above the
    linked files; fall back to their common parent."""
    paths = [p for p in links if p.suffix.lower() in (".html", ".htm")] or list(links)
    if not paths:
        return html_path.parent
    common = Path(os.path.commonpath([str(p.parent) for p in paths]))
    for d in [common, *common.parents]:
        if (d / "ro-crate-metadata.json").exists():
            return d
    return common


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="fairscape-review-bundle", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("html", help="ai-ready-review.html (or a saved copy of it)")
    parser.add_argument("-o", "--out", help="zip to write (default: <html dir name>.zip)")
    parser.add_argument("--crate", help="crate root (default: found from the links)")
    parser.add_argument("--no-follow", action="store_true",
                        help="bundle only the page's direct links, not the pages they link to")
    parser.add_argument("--extra", action="append", default=[],
                        help="additional file to put next to the page (repeatable)")
    parser.add_argument("-q", "--quiet", action="store_true")
    args = parser.parse_args(argv)

    html_path = Path(args.html).resolve()
    if not html_path.is_file():
        parser.error(f"not a file: {html_path}")
    out = Path(args.out) if args.out else html_path.parent.with_name(
        html_path.parent.name + ".zip")
    say = (lambda msg: None) if args.quiet else (lambda msg: print(msg, file=sys.stderr))
    written = bundle_review(html_path, out, crate_dir=args.crate,
                            follow=not args.no_follow, extra=args.extra, progress=say)
    say(f"{len(written)} files, {out.stat().st_size:,} bytes")
    print(out)


if __name__ == "__main__":
    main()
