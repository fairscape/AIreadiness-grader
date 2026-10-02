"""Build metadata-improved.json: the MLCommons DICES-350 Croissant with the
fields a dataset author would fill in. Every added value comes from the DICES
README, the CSV itself, the paper's author list, or a registry lookup."""
import json, re, sys

src, readme, out = sys.argv[1:4]
d = json.load(open(src))
text = open(readme).read()

# --- field descriptions from the README "Dataset Schema" list ----------------
desc = {}
for m in re.finditer(r"^\d+\. `([^`]+)`: (.+)$", text, re.M):
    desc[m.group(1)] = re.sub(r"\s+", " ", m.group(2)).strip()
desc["Q6_policy_guidelines_other"] = desc.pop("Q6_policy_guidelines_other_type")  # README name differs from the CSV header
ints = {"id", "rater_id", "item_id", "answer_time_ms", "answer_timestamp"}
columns = ["id", "rater_id", "rater_gender", "rater_race", "rater_raw_race", "rater_age",
           "rater_education", "phase", "item_id", "answer_time_ms", "answer_timestamp",
           "context", "response", "degree_of_harm", "harm_type", "safety_gold",
           "safety_gold_reason", "Q1_whole_conversation_evaluation",
           "Q2_harmful_content_medical_legal_financial_or_relationship_advice",
           "Q2_harmful_content_dangerous_content", "Q2_harmful_content_derogation_of_boat",
           "Q2_harmful_content_insensitive", "Q2_harmful_content_obscene_and_profane",
           "Q2_harmful_content_personal_information", "Q2_harmful_content_regulated_goods",
           "Q2_harmful_content_sexually_suggestive_content", "Q2_harmful_content_other",
           "Q3_bias_targeting_beliefs", "Q3_bias_targeting_gender_sexual_orientation",
           "Q3_bias_targeting_inherited_attributes", "Q3_bias_targeting_status", "Q3_bias_other",
           "Q4_misinformation", "Q5_political_affiliation",
           "Q6_policy_guidelines_polarizing_topics", "Q6_policy_guidelines_making_endorsement",
           "Q6_policy_guidelines_other", "Q2_harmful_content_overall", "Q3_bias_overall",
           "Q6_policy_guidelines_overall", "Q_overall"]
missing = [c for c in columns if c not in desc]
assert not missing, missing

COMMIT = "9c0eca5cda4d89ebbf380b831f70abfbb88d9306"
CSV = "350/diverse_safety_adversarial_dialog_350.csv"


def person(name, orcid=None):
    p = {"@type": "sc:Person", "name": name}
    if orcid:
        p["@id"] = f"https://orcid.org/{orcid}"
    return p


def mesh(label, ui):
    # Croissant validates keywords as sc:Text, so the MeSH descriptor goes in
    # as its IRI rather than a DefinedTerm object (label kept for the reader)
    return f"http://id.nlm.nih.gov/mesh/{ui}"


new = {}
for k, v in d.items():
    new[k] = v
    if k == "name":
        # placeholder: DataCite's test prefix 10.5072 never resolves; a real
        # deposit (e.g. the GitHub-Zenodo release integration) mints the DOI
        new["identifier"] = "https://doi.org/10.5072/zenodo.dices-350.v1"
        new["sameAs"] = "https://github.com/google-research-datasets/dices-dataset/tree/main/350"
    if k == "citeAs":
        new["datePublished"] = "2023-06-01"
        new["dateModified"] = "2023-10-04"
        new["keywords"] = [
            "conversational AI", "AI safety", "safety evaluation", "rater diversity",
            "annotator disagreement", "adversarial dialogue", "crowdsourcing",
            mesh("Artificial Intelligence", "D001185"),
            mesh("Natural Language Processing", "D009323"),
            mesh("Safety", "D012449"),
            mesh("Crowdsourcing", "D063045"),
            mesh("Cultural Diversity", "D018864"),
        ]
    if k == "creator":
        new["creator"] = [
            person("Lora Aroyo", "0000-0001-9402-1133"),
            person("Alex S. Taylor"),
            person("Mark Diaz"),
            person("Christopher M. Homan", "0000-0003-1821-5125"),
            person("Alicia Parrish", "0000-0002-1054-0516"),
            person("Gregory Serapio-García", "0000-0002-1890-2331"),
            person("Vinodkumar Prabhakaran", "0000-0003-3329-2305"),
            person("Ding Wang"),
        ]
        new["publisher"] = {"@type": "sc:Organization", "name": "Zenodo",
                            "url": "https://zenodo.org"}
        new["copyrightHolder"] = {"@type": "sc:Organization", "@id": "https://ror.org/00njsd438",
                                  "name": "Google LLC"}

new["rai:dataCollectionTimeframe"] = ["2022-12-08", "2023-01-09"]
new["rai:dataCollectionMissingData"] = (
    "No column has blank values. 'Unsure' is an explicit answer option for the Q2-Q6 "
    "safety questions rather than a missing-value code, and safety_gold_reason is '[]' "
    "where the expert gold label gave no reason (21,525 of 43,050 rows).")
new["rai:dataPreprocessingProtocol"] = (
    "rater_race simplifies each rater's self-reported race/ethnicity (rater_raw_race, 14 "
    "values) to five categories. Q2_harmful_content_overall, Q3_bias_overall and "
    "Q6_policy_guidelines_overall aggregate the granular Q2, Q3 and Q6 answers; Q_overall "
    "aggregates Q2-Q6, excluding Q1. rater_id hashes were unified on 2023-06-12 and their "
    "formatting fixed on 2023-10-04.")
new["rai:annotationsPerItem"] = "123 ratings per conversation: every rater rated all 350 conversations."
new["rai:dataUseCases"] = (
    "A shared benchmark for safety evaluation of conversational AI systems, and for "
    "measuring variance, ambiguity and diversity in human safety ratings: how safety "
    "perception differs across rater gender, race/ethnicity, age and education groups, and "
    "how rating aggregation strategies compare. The release is an evaluation set with no "
    "train/validation/test splits.")
new["rai:dataLimitations"] = (
    "Conversations are adversarial and may be offensive. All ratings come from one "
    "collection phase (Phase3) and 123 raters; the 19 raters who failed the authors' "
    "quality checks are listed by rater_id in the README but are kept in the file, so "
    "analyses that follow the paper must remove them. Rater demographics are coarse "
    "categories (two genders, five race/ethnicity groups, three age groups, three "
    "education levels).")
new["rai:personalSensitiveInformation"] = (
    "Each row carries the rater's self-reported gender, race/ethnicity (simplified and "
    "raw), age group and education level, keyed by a numeric rater_id; no names or "
    "contact details are included. Conversation text was written by human agents probing "
    "a chatbot and may contain offensive content.")

new["distribution"] = [
    d["distribution"][0],
    {
        "@type": "cr:FileObject",
        "@id": "diverse_safety_adversarial_dialog_350.csv",
        "name": "diverse_safety_adversarial_dialog_350.csv",
        "description": "43,050 rows: one per (rater, conversation) pair, 123 raters x 350 conversations.",
        "contentUrl": f"https://raw.githubusercontent.com/google-research-datasets/dices-dataset/{COMMIT}/{CSV}",
        "contentSize": "31143485 B",
        "encodingFormat": "text/csv",
        "sha256": "63cb8620eb04e64957f9e45b1f7cb3d079c4eed8e8b28909f46e0b7038ce4301",
    },
]
new["recordSet"] = [{
    "@type": "cr:RecordSet",
    "@id": "ratings",
    "name": "ratings",
    "description": "All safety ratings by one rater on one conversation.",
    "key": {"@id": "ratings/id"},
    "field": [{
        "@type": "cr:Field",
        "@id": f"ratings/{c}",
        "name": c,
        "description": desc[c],
        "dataType": "sc:Integer" if c in ints else "sc:Text",
        "source": {"fileObject": {"@id": "diverse_safety_adversarial_dialog_350.csv"},
                   "extract": {"column": c}},
    } for c in columns],
}]
json.dump(new, open(out, "w"), indent=2, ensure_ascii=False)
print("fields", len(columns), "rai", sorted(k for k in new if k.startswith("rai:")))
