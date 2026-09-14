---
name: ethics-questionnaire
description: Post-grade improvement skill for rubrics 4.a (Ethically Acquired), 4.b (Ethically Managed), and 4.d (Secure). One-question-at-a-time interview that fills the root entity fields the ethics extractors read — ethicalReview, humanSubjectResearch, informedConsent, atRiskPopulations, irb / irbProtocolId, dataGovernanceCommittee, rai:personalSensitiveInformation, confidentialityLevel (HL7 code), deidentified, rai:dataReleaseMaintenancePlan. Validates against fairscape_models.rocrate.ROCrateV1_2 before writing.
---

# Ethics questionnaire — rubrics 4.a, 4.b, 4.d

Three rubrics in the Ethics criterion regularly score Partial across the surveyed crates. They each look at the root Dataset's fields:

- **4.a Ethically Acquired** — needs `rai:dataCollection` narrative, `ethicalReview` text, `humanSubjectResearch`, `informedConsent`, `atRiskPopulations`, an IRB / consent reference, and `rai:dataReleaseMaintenancePlan`.
- **4.b Ethically Managed** — needs `ethicalReview`, `dataGovernanceCommittee`, privacy-protection signal (text or `rai:personalSensitiveInformation`), and `confidentialityLevel` (HL7 code).
- **4.d Secure** — needs `confidentialityLevel` (HL7 code), `rai:personalSensitiveInformation`, `deidentified` (bool).

All three are root-level fields. This skill walks the user through them in one sitting; the user can `skip` any individual field.

## What to tell the user

> *"This skill targets three rubrics — Ethically Acquired (4.a), Ethically Managed (4.b), and Secure (4.d). They're all about ethics fields on the root of the crate: who reviewed it, what consent was obtained, what privacy-protection processing was applied, what the HL7 confidentiality classification is. I'll ask one question at a time — `skip` is fine on anything you don't have an answer for, but every field you do fill in helps the score. The fields go onto the root entity of `ro-crate-metadata.json`. Validated against the fairscape_models schema before write."*


> `<crate>` is the `ro-crate-metadata.json` to edit and `<crate_dir>` its directory. Resolve them from the path the user gave, else `ro-crate-metadata.json` in the working directory, else `state.crate_path` if a `.fairscape-state.json` wizard state file is present. Ask if none resolve.

## 1. Read the crate, identify what's already set

`Read` `<crate>`. Find the root Dataset entity. Note which of these fields already have a non-null value so you don't ask about them again:

- `rai:dataCollection`, `rai:dataReleaseMaintenancePlan`, `rai:personalSensitiveInformation`
- `ethicalReview`, `humanSubjectResearch`, `informedConsent`, `atRiskPopulations`
- `irb`, `irbProtocolId`, `humanSubjectExemption`, `fdaRegulated`
- `dataGovernanceCommittee`
- `confidentialityLevel`, `deidentified`

If a field is already set, surface it once at the start (*"You already have `<field>: <value>`. I'll skip that unless you want to revise it — say `revise <field>` any time to revisit."*) and don't ask about it.

## 2. Ask, one field at a time

Walk the buckets in rubric order. Stop asking and exit early if the user says `done` or `enough`.

### 4.a — Ethically Acquired

1. **`humanSubjectResearch`** *(string)*
   > *"Does this dataset involve human subjects? `yes` / `no` / a short description of involvement — or `skip`."*
   The pydantic field type is `Optional[str]` (the description in the model says "Indicate Yes/No and describe"). Pass the user's literal answer.

2. **`informedConsent`** *(string or bool — `extra="allow"` on the model, but the rubric extractor accepts either shape)*
   Skip if `humanSubjectResearch` is `no` or `skip`. Otherwise:
   > *"Informed consent: `written` / `verbal` / `waived` / `none` — or paste a longer narrative on the consent process / scope."*

3. **`ethicalReview`** *(string, top-level field on `ROCrateMetadataElem`)*
   > *"Short narrative of the ethical-review process — which IRB / framework / committee reviewed this, when, what they approved. `skip` to leave blank."*

4. **`irb` / `irbProtocolId`** — only if `humanSubjectResearch` is non-skip:
   > *"IRB approval number or protocol ID? (e.g. `IRB-2023-04521`). And the IRB name if it's not implied by the protocol ID. `skip` for either."*
   `irb` accepts `Union[str, IRB]` — pass the IRB name as the string form (the structured IRB model is overkill for the questionnaire). `irbProtocolId` is a separate string field.

5. **`atRiskPopulations`** *(string or array — `extra="allow"`)*
   > *"Any at-risk populations represented — children, prisoners, indigenous communities, pregnant women, etc.? List them, or `none` if explicitly none, or `skip`."*
   `none` is informative (the 4.a rubric explicitly says explicit "none" is a meaningful signal). Set the field to the literal string `"none"` if the user said so.

6. **`rai:dataCollection`** *(string, the `rai_data_collection` field aliased `rai:dataCollection`)*
   Only ask if it's empty. (On crates built by the RO-Crate wizard this is the field its AI-Ready enrichment step would have filled — don't double-ask.)
   > *"One or two sentences on how the data was collected (instruments, protocols, sources). `skip` if not relevant."*

7. **`rai:dataReleaseMaintenancePlan`** *(string)*
   > *"Management plan — who maintains this dataset, how often it's updated, what the deprecation policy is. `skip` if not yet defined."*

### 4.b — Ethically Managed

8. **`dataGovernanceCommittee`** *(string or reference stub or inline Person)*
   > *"Name of the data governance committee (or the person responsible). `skip` if none."*
   Plain string is fine; the field accepts `Union[str, IdentifierValue, Person]`.

9. **`rai:personalSensitiveInformation`** *(string or list)*
   > *"What sensitive content is present? — e.g. race, biometrics, geolocation, genomic data, behavioral health. List them, or `none`, or `skip`."*
   This is what both 4.b's `privacy_protection_text` extractor and 4.d's `rai_personalSensitiveInformation` extractor read. Important for both rubrics.

   Also add to `ethicalReview` (already collected above) a sentence on the privacy-protection method if the user mentions one — e.g. *"Safe Harbor de-identification per HIPAA, expert determination, k-anonymity at k=5, differential privacy with ε=…"*. The 4.b rubric calls out "named de-identification method" as the difference between Partial and Substantive. There is no separate `deidentificationMethod` field on the model — it lives in narrative. Ask:
   > *"De-identification method used (Safe Harbor / Expert Determination / k-anonymity / differential privacy / other / none / skip)?"*
   If the user names one, append to `ethicalReview`: `"De-identification: <method>."`

### 4.d — Secure

10. **`confidentialityLevel`** *(string, HL7 code)*
    Show the user the valid codes:
    > *"HL7 confidentiality classification — pick one or `skip`:
    >   - `unrestricted` — no confidentiality requirement
    >   - `low`          — minimal sensitivity
    >   - `moderate`     — moderate sensitivity
    >   - `normal`       — standard healthcare data
    >   - `restricted`   — restricted access required
    >   - `very restricted` — strictest controls"*
    The model field is free-text but the rubric extractor checks for the HL7 vocabulary. Reject anything not in the list and ask again (or `skip`).

11. **`deidentified`** *(bool)*
    > *"Has the data been de-identified? `true` / `false` / `skip`."*
    Cast literal `"true"`/`"false"` to Python `True`/`False`. The field is `Optional[bool]`.

## 3. Show the user the proposed diff

Render concisely — only fields that will change:

```
Proposed root-entity additions:
  humanSubjectResearch:        "Yes — patients with sleep disorders, n=312"
  informedConsent:             "written"
  ethicalReview:               "Reviewed by UVA IRB ... De-identification: Safe Harbor."
  irbProtocolId:               "IRB-2023-04521"
  irb:                         "University of Virginia Institutional Review Board"
  atRiskPopulations:           "none"
  rai:personalSensitiveInformation: ["medical conditions", "demographics"]
  rai:dataReleaseMaintenancePlan:   "Maintained quarterly by lab; deprecation announced 6 months ahead."
  dataGovernanceCommittee:     "Tim Clark"
  confidentialityLevel:        "restricted"
  deidentified:                true

Untouched: rai:dataCollection (already filled), 2 other fields you said skip on.
```

Ask: *"Apply, or revise something?"*

## 4. Validate before writing

Same contract: build mutated dict, write to `<crate_path>.proposed`, run:

```bash
python -c '
import json, sys
from fairscape_models.rocrate import ROCrateV1_2
ROCrateV1_2.model_validate(json.load(open(sys.argv[1])))
print("OK")
' <crate_path>.proposed
```

On success: `os.replace`. On failure: surface stderr (likely culprit is a typed-field violation — e.g. `deidentified` got a string `"yes"` instead of bool `true`; coerce and retry), delete the proposed file, ask retry or skip.

## 5. State write

```json
{
  "improvements": {"ran": [..., "ethics-questionnaire"]},
  "history": [..., {"ts": "...", "skill": "ethics-questionnaire",
                    "summary": "filled N ethics fields on root (4.a/4.b/4.d)"}]
}
```

Tell the user: *"Done. Filled `<N>` root ethics fields. Crate validated. Rubrics 4.a/4.b/4.d should move on rescore."*

## Don't

- Don't synthesize answers the user didn't give. Empty / null is honest; fabrication breaks the rubric's intent.
- Don't use the string `"unvalidated"` or similar judgments in field text — see memory `feedback_assumption_framing.md`.
- Don't write `confidentialityLevel` as anything other than the HL7 vocabulary listed above. The 4.d rubric explicitly downgrades non-recognized values to Partial.
- Don't ask about every field if the user says `done` mid-interview. Save what they filled and move on.
- Don't write to `ro-crate-metadata.json` until validation succeeds.
- Don't overwrite a non-null existing field without asking the user `revise <field>` first.
