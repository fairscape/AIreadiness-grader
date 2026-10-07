"""Root `about` entries count as subject terms for 2.a alongside DefinedTerm
graph entities: bare ontology IRIs, references to graph DefinedTerms, and
inline DefinedTerm objects (which a flat RO-Crate @graph never lists)."""

from aireadiness_evidence.crate import subject_terms

MESH = "http://id.nlm.nih.gov/mesh/D002477"
NCIT = "http://purl.obolibrary.org/obo/NCIT_C12345"


def test_about_forms_and_graph_terms_are_merged():
    graph = [
        {"@id": "#ds", "@type": "Dataset"},
        {"@id": NCIT, "@type": "DefinedTerm", "name": "Tumor"},
        {"@id": "#local-term", "@type": "DefinedTerm", "name": "Local"},
    ]
    root = {"about": [
        MESH,                                                   # bare IRI
        {"@id": NCIT},                                          # ref to graph term
        {"@id": "https://example.org/t/1", "@type": "DefinedTerm",
         "name": "Inline"},                                     # inline object
        {"@id": "#ds"},                                         # not a term
        "cancer",                                               # free text
    ]}
    terms = {t["@id"]: t for t in subject_terms(root, graph)}
    assert set(terms) == {MESH, NCIT, "https://example.org/t/1", "#local-term"}
    assert terms[MESH]["ontology"] == "MeSH" and terms[MESH]["source"] == "about"
    assert terms[NCIT]["name"] == "Tumor" and terms[NCIT]["source"] == "about"
    assert terms["#local-term"]["source"] == "graph"
    assert terms["https://example.org/t/1"]["ontology"] is None


def test_no_about_falls_back_to_graph_terms():
    graph = [{"@id": MESH, "@type": "DefinedTerm", "name": "Cells"}]
    assert [t["@id"] for t in subject_terms({}, graph)] == [MESH]
