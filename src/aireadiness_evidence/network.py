"""Optional network checks used by the transformation stage.

Everything here degrades gracefully: with `enabled=False` (the `--no-network`
flag) every call returns `checked: False`, and the presentation records the
check as not performed rather than failed. Results are cached per URL.
"""

import json
import re
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = "fairscape-evidence/0.1 (AI-readiness rubric evidence builder)"


class Network:
    def __init__(self, enabled=True, timeout=8):
        self.enabled = enabled
        self.timeout = timeout
        self._cache = {}

    # -- generic URL resolution ---------------------------------------------

    def check_url(self, url):
        """HEAD (falling back to GET) an http(s) URL.

        Returns {url, checked, ok, status, note}.
        """
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            return {"url": url, "checked": False, "ok": None,
                    "note": "not an http(s) URL"}
        if not self.enabled:
            return {"url": url, "checked": False, "ok": None,
                    "note": "network checks disabled"}
        if url in self._cache:
            return self._cache[url]

        result = {"url": url, "checked": True, "ok": False, "status": None, "note": ""}
        for method in ("HEAD", "GET"):
            try:
                req = urllib.request.Request(url, method=method,
                                             headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    result["status"] = resp.status
                    result["ok"] = 200 <= resp.status < 400
                    break
            except urllib.error.HTTPError as err:
                result["status"] = err.code
                # some hosts reject HEAD; retry with GET
                if method == "HEAD" and err.code in (403, 405, 501):
                    continue
                if err.code in (429, 502, 503, 504):
                    # rate-limited / transient upstream — inconclusive, like a timeout
                    result["ok"] = None
                    result["note"] = f"HTTP {err.code} — inconclusive"
                else:
                    result["note"] = f"HTTP {err.code}"
                break
            except TimeoutError:
                # inconclusive, not a failure — slow hosts often resolve fine
                result["ok"] = None
                result["note"] = "timed out — inconclusive"
                break
            except Exception as err:  # DNS, TLS, connection refused
                if "timed out" in str(err).lower():
                    result["ok"] = None
                    result["note"] = "timed out — inconclusive"
                else:
                    result["note"] = type(err).__name__
                break
        self._cache[url] = result
        return result

    def resolve_pid(self, identifier):
        """Resolve a PID string through its resolver (doi.org, n2t.net for ARKs)."""
        if not isinstance(identifier, str):
            return {"url": identifier, "checked": False, "ok": None,
                    "note": "no identifier"}
        url = identifier
        if identifier.lower().startswith("doi:"):
            url = "https://doi.org/" + identifier[4:]
        elif re.match(r"^10\.\d{4,9}/", identifier):
            url = "https://doi.org/" + identifier
        elif identifier.startswith("ark:"):
            url = "https://n2t.net/" + identifier
        return self.check_url(url)

    # -- registry / metadata lookups ----------------------------------------

    def re3data_search(self, query):
        """Search the re3data registry (https://www.re3data.org/api/beta) for
        repositories matching `query`. Returns {checked, query, matches}."""
        if not query:
            return {"checked": False, "query": query, "matches": []}
        if not self.enabled:
            return {"checked": False, "query": query, "matches": [],
                    "note": "network checks disabled"}
        key = ("re3data", query)
        if key in self._cache:
            return self._cache[key]

        url = ("https://www.re3data.org/api/beta/repositories?query="
               + urllib.parse.quote(query))
        result = {"checked": True, "query": query, "matches": []}
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read(512_000).decode("utf-8", "replace")
            result["matches"] = re.findall(r"<name>([^<]+)</name>", body)[:10]
        except Exception as err:
            result["note"] = type(err).__name__
        self._cache[key] = result
        return result

    def fetch_pid_metadata(self, identifier):
        """Fetch descriptive metadata for a DOI via content negotiation
        (https://citation.crosscite.org/docs.html). Proves rubric 0.b's
        'metadata available via PID lookup independently of the dataset'."""
        if not self.enabled:
            return {"checked": False, "note": "network checks disabled"}
        if not isinstance(identifier, str):
            return {"checked": False, "note": "no identifier"}
        m = re.search(r"(10\.\d{4,9}/\S+)", identifier)
        if not m:
            return {"checked": False, "note": "not a DOI — no metadata resolver tried"}

        url = "https://doi.org/" + m.group(1).rstrip("/")
        for accept in ("application/ld+json",
                       "application/vnd.citationstyles.csl+json"):
            try:
                req = urllib.request.Request(
                    url, headers={"User-Agent": USER_AGENT, "Accept": accept})
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    body = resp.read(200_000).decode("utf-8", "replace")
                meta = json.loads(body)
                return {"checked": True, "ok": True, "format": accept,
                        "metadata": meta}
            except Exception:
                continue
        return {"checked": True, "ok": False,
                "note": "no machine-readable metadata returned for the DOI"}
