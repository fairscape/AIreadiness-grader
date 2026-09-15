"""fairscape-review-bundle: the zip must carry every locally linked page and the
review's links must be rewritten to point inside the zip."""

import re
import zipfile

from aireadiness_evidence.bundle import bundle_review, collect_links


def _crate(tmp_path):
    crate = tmp_path / "my-crate"
    (crate / "sub").mkdir(parents=True)
    (crate / "ro-crate-metadata.json").write_text("{}")
    (crate / "ro-crate-datasheet.html").write_text(
        '<a href="sub/ro-crate-preview.html">sub</a> <a href="mailto:x@y">m</a>'
        ' <a href="https://doi.org/10.1/x">doi</a> <a href="missing.html">gone</a>')
    (crate / "sub" / "ro-crate-preview.html").write_text(
        '<a href="ro-crate-prov-graph.html">graph</a> <a href="big.bin">data</a>')
    (crate / "sub" / "ro-crate-prov-graph.html").write_text("<p>graph</p>")
    (crate / "sub" / "big.bin").write_bytes(b"\0" * 10)
    out = tmp_path / "review"
    out.mkdir()
    (out / "ai-ready-evidence.json").write_text("{}")
    html = out / "ai-ready-review.html"
    html.write_text(
        '<a href="#sec1">toc</a> <a href="../my-crate/ro-crate-datasheet.html">ds</a>'
        ' <a href="../my-crate/sub/ro-crate-prov-graph.html">g</a>'
        ' <a href="../my-crate/sub/ro-crate-prov-graph.html">g again</a>'
        ' <a href="https://example.org/">remote</a>')
    return crate, html


def test_collect_links_follows_pages_but_not_data(tmp_path):
    crate, html = _crate(tmp_path)
    found = {p.relative_to(crate).as_posix() for p in collect_links(html)}
    assert found == {"ro-crate-datasheet.html", "sub/ro-crate-preview.html",
                     "sub/ro-crate-prov-graph.html"}


def test_bundle_rewrites_links_and_zips_files(tmp_path):
    crate, html = _crate(tmp_path)
    zip_path = tmp_path / "share.zip"
    written = bundle_review(html, zip_path)
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
        page = zf.read("ai-ready-review.html").decode()
    assert names == set(written) == {
        "ai-ready-review.html", "ai-ready-evidence.json",
        "crate/ro-crate-datasheet.html", "crate/sub/ro-crate-preview.html",
        "crate/sub/ro-crate-prov-graph.html"}
    assert '"../my-crate/' not in page
    assert page.count('href="crate/sub/ro-crate-prov-graph.html"') == 2
    assert 'href="#sec1"' in page and 'href="https://example.org/"' in page
    # every relative link inside the zip resolves to a zipped file
    for name in names:
        if not name.endswith(".html"):
            continue
        with zipfile.ZipFile(zip_path) as zf:
            text = zf.read(name).decode()
        base = name.rsplit("/", 1)[0] + "/" if "/" in name else ""
        for href in re.findall(r'href="([^"#][^"]*)"', text):
            if "://" in href or href.startswith("mailto:"):
                continue
            if href in ("missing.html", "big.bin"):
                continue  # deliberately absent from the fixture / not bundled
            assert base + href in names, (name, href)


def test_no_follow_keeps_only_direct_links(tmp_path):
    crate, html = _crate(tmp_path)
    zip_path = tmp_path / "flat.zip"
    written = bundle_review(html, zip_path, follow=False)
    assert "crate/sub/ro-crate-preview.html" not in written
    assert "crate/ro-crate-datasheet.html" in written
