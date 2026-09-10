/* aireadiness_improve core — inlined into improve.html.j2, also loadable in
 * node for tests (module.exports).
 *
 *   IMPROVE.loadCrate(doc)            -> crate model (root, stats, ...)
 *   IMPROVE.estimateAll(crate)        -> {cid: {score, basis}} mechanical rubric estimates
 *   IMPROVE.aggregate(estimates)      -> points / gates, v1.8 methodology
 *   IMPROVE.validate(schema, data)    -> [] or [{path, message}]
 *   IMPROVE.applyEdits(doc, edits)    -> new document with root/software edits applied
 */
(function (global) {
  'use strict';

  // ------------------------------------------------------------ helpers
  function asList(v) {
    if (v === undefined || v === null) return [];
    return Array.isArray(v) ? v : [v];
  }
  function idsOf(v) {
    var out = [];
    asList(v).forEach(function (x) {
      if (typeof x === 'string') out.push(x);
      else if (x && typeof x === 'object' && x['@id']) out.push(String(x['@id']));
    });
    return out;
  }
  // python truthiness for the values we meet in JSON
  function truthy(v) {
    if (v === undefined || v === null || v === false || v === 0 || v === '') return false;
    if (Array.isArray(v)) return v.length > 0;
    if (typeof v === 'object') return Object.keys(v).length > 0;
    return true;
  }
  function strip(v) { return v === undefined || v === null ? '' : String(v).trim(); }
  function nonblank(v) { return truthy(v) && strip(typeof v === 'object' ? JSON.stringify(v) : v) !== ''; }
  function text(v) {
    if (v === undefined || v === null) return '';
    if (typeof v === 'string') return v;
    if (Array.isArray(v)) return v.map(text).join(' ');
    if (typeof v === 'object') return v.name || v['@id'] || v.url || JSON.stringify(v);
    return String(v);
  }
  function roundHalfEven(x) {
    var f = Math.floor(x), d = x - f;
    if (d > 0.5) return f + 1;
    if (d < 0.5) return f;
    return f % 2 === 0 ? f : f + 1;
  }
  function fmt1(x) { return (Math.round(x * 10) / 10).toFixed(1); }
  function clone(o) { return JSON.parse(JSON.stringify(o)); }

  var CANON = ['Dataset', 'Computation', 'Software', 'Schema', 'Sample', 'Instrument',
    'Experiment', 'Person', 'Organization', 'BioChemEntity', 'Container',
    'CreativeWork', 'DefinedTerm'];

  // crate.py canonical_type
  function canonicalType(entity) {
    var types = asList(entity['@type']).map(String);
    for (var i = 0; i < types.length; i++) if (types[i].indexOf('ROCrate') >= 0) return 'ROCrate';
    for (i = 0; i < types.length; i++) {
      var parts = types[i].split(/[#\/:]/);
      var tok = parts[parts.length - 1];
      if (CANON.indexOf(tok) >= 0) return tok;
    }
    var at = entity.additionalType;
    if (typeof at === 'string' && CANON.indexOf(at) >= 0) return at;
    return 'Other';
  }

  // AIReady.py _get_type: string, or the LAST element of the type list
  function lastType(entity) {
    var t = entity['@type'] || entity.metadataType || [];
    if (typeof t === 'string') return t;
    return t.length ? String(t[t.length - 1]) : '';
  }

  var PROV_LINK_FIELDS = ['generatedBy', 'prov:wasGeneratedBy', 'derivedFrom',
    'prov:wasDerivedFrom', 'derivedTo', 'usedByComputation', 'usedBy',
    'usedByExperiment', 'usedSoftware', 'usedDataset', 'usedSample',
    'usedInstrument', 'usedTreatment', 'usedStain', 'usedContainer',
    'generated', 'prov:used', 'inputs', 'outputs',
    'https://w3id.org/EVI#inputs', 'https://w3id.org/EVI#outputs'];
  var ACTIVITY_INPUT_FIELDS = ['usedDataset', 'usedSample', 'usedInstrument', 'inputs',
    'https://w3id.org/EVI#inputs', 'prov:used'];
  var ACTIVITY_OUTPUT_FIELDS = ['generated', 'outputs', 'https://w3id.org/EVI#outputs'];
  var HASH_FIELDS = ['md5', 'MD5', 'sha256', 'sha-256', 'sha512', 'checksum'];
  var SCHEMA_REF_FIELDS = ['EVI:Schema', 'evi:Schema', 'hasSchema', 'dataSchema'];
  var SUMMARY_STATS_FIELDS = ['hasSummaryStatistics', 'hasSummaryStats'];

  function anyField(e, fields) {
    for (var i = 0; i < fields.length; i++) if (truthy(e[fields[i]])) return true;
    return false;
  }

  // ------------------------------------------------------------ known.py
  var PID_PATTERNS = [
    ['DOI', /(doi\.org\/|^doi:|^10\.\d{4,9}\/)/i],
    ['ARK', /(^ark:|\/ark:)/i],
    ['Handle', /(hdl\.handle\.net\/|^hdl:)/i],
    ['PURL', /purl\.(org|obolibrary\.org)\//i],
    ['w3id', /w3id\.org\//i],
    ['URN', /^urn:/i],
    ['IGSN', /igsn\.org\/|^igsn:/i],
    ['CSTR', /cstr\.cn\/|^cstr:/i]
  ];
  function detectPid(s) {
    s = strip(s);
    if (!s) return null;
    for (var i = 0; i < PID_PATTERNS.length; i++) if (PID_PATTERNS[i][1].test(s)) return PID_PATTERNS[i][0];
    return null;
  }
  var SPECIALIST_REPOS = {
    'massive.ucsd.edu': 'MassIVE (proteomics)', 'massive-ftp.ucsd.edu': 'MassIVE (proteomics)',
    'proteomecentral': 'ProteomeXchange (proteomics)', 'ebi.ac.uk/pride': 'PRIDE (proteomics)',
    'ncbi.nlm.nih.gov/geo': 'GEO (functional genomics)', 'ncbi.nlm.nih.gov/sra': 'SRA (sequence reads)',
    'trace.ncbi.nlm.nih.gov': 'SRA (sequence reads)', 'ncbi.nlm.nih.gov/gap': 'dbGaP (genotype/phenotype)',
    'ebi.ac.uk/ena': 'ENA (nucleotide archive)', 'ebi.ac.uk/biostudies': 'BioStudies',
    'empiar': 'EMPIAR (EM imaging)', 'proteinatlas.org': 'Human Protein Atlas (imaging)',
    'physionet.org': 'PhysioNet (physiologic signals)', 'openneuro.org': 'OpenNeuro (neuroimaging)',
    'idr.openmicroscopy.org': 'IDR (imaging)', 'cellosaurus': 'Cellosaurus (cell lines)',
    'addgene.org': 'Addgene (plasmids)'
  };
  var GENERALIST_REPOS = {
    'dataverse': 'Dataverse', 'zenodo.org': 'Zenodo', 'figshare.com': 'Figshare',
    'datadryad.org': 'Dryad', 'osf.io': 'OSF', 'fairhub.io': 'FAIRhub',
    'dataverse.lib.virginia.edu': 'University of Virginia Dataverse (LibraData)',
    'data.mendeley.com': 'Mendeley Data', 'vivli.org': 'Vivli', 'icpsr.umich.edu': 'ICPSR',
    'ddbj.nig.ac.jp': 'DDBJ'
  };
  var NON_SUSTAINABLE_HOSTS = {
    'amazonaws.com': 'S3 bucket (unmanaged cloud storage)',
    'storage.googleapis.com': 'GCS bucket (unmanaged cloud storage)',
    'storage.cloud.google.com': 'GCS bucket (unmanaged cloud storage)',
    'drive.google.com': 'Google Drive', 'docs.google.com': 'Google Drive/Docs',
    'box.com': 'Box', 'dropbox.com': 'Dropbox', 'onedrive': 'OneDrive'
  };
  var SOFTWARE_ARCHIVE_HOSTS = {
    'zenodo.org': 'Zenodo', 'softwareheritage.org': 'Software Heritage',
    'archive.softwareheritage.org': 'Software Heritage', 'doi.org': 'DOI-registered archive',
    'dataverse': 'Dataverse', 'pypi.org': 'PyPI'
  };
  var CODE_HOSTS = { 'github.com': 'GitHub', 'gitlab.com': 'GitLab', 'bitbucket.org': 'Bitbucket' };
  var ONTOLOGY_HOSTS = {
    'purl.obolibrary.org': 'OBO Foundry PURL', 'meshb.nlm.nih.gov': 'MeSH',
    'id.nlm.nih.gov/mesh': 'MeSH', 'cellosaurus.org': 'Cellosaurus',
    'ebi.ac.uk/ols': 'EBI Ontology Lookup Service', 'bioportal.bioontology.org': 'NCBO BioPortal',
    'identifiers.org': 'identifiers.org', 'uniprot.org': 'UniProt', 'ensembl.org': 'Ensembl',
    'snomed.info': 'SNOMED CT', 'loinc.org': 'LOINC', 'ncithesaurus': 'NCI Thesaurus'
  };
  var STANDARD_NAMESPACES = {
    'schema.org': 'schema.org', 'w3id.org/EVI': 'EVI (Evidence Graph Ontology)',
    'w3.org/ns/prov': 'W3C PROV-O', 'w3.org/ns/dcat': 'W3C DCAT', 'purl.org/dc/': 'Dublin Core',
    'w3id.org/ro/crate': 'RO-Crate', 'mlcommons.org/croissant': 'Croissant', 'bioschemas.org': 'Bioschemas'
  };
  var KNOWN_VALIDATORS = {
    'w3id.org/ro/crate': 'RO-Crate profile — rocrate-validator / ro-crate-py',
    'w3id.org/EVI': 'EVI — fairscape-cli `rocrate validate` (pydantic models)',
    'json-schema.org': 'JSON Schema — any JSON Schema validator',
    'mlcommons.org/croissant': 'Croissant — mlcroissant validator',
    'frictionlessdata.io': 'Frictionless — frictionless-py validate',
    'datapackage.org': 'Frictionless Data Package — frictionless-py validate'
  };
  var LICENSE_NAMES = {
    'creativecommons.org/licenses/by/4.0': 'CC BY 4.0',
    'creativecommons.org/licenses/by-sa/4.0': 'CC BY-SA 4.0',
    'creativecommons.org/licenses/by-nc/4.0': 'CC BY-NC 4.0',
    'creativecommons.org/licenses/by-nc-sa/4.0': 'CC BY-NC-SA 4.0',
    'creativecommons.org/licenses/by-nc-nd/4.0': 'CC BY-NC-ND 4.0',
    'creativecommons.org/publicdomain/zero/1.0': 'CC0 1.0',
    'apache.org/licenses/license-2.0': 'Apache-2.0',
    'opensource.org/licenses/mit': 'MIT',
    'spdx.org/licenses/apache-2.0': 'Apache-2.0',
    'spdx.org/licenses/mit': 'MIT',
    'spdx.org/licenses/cc-by-4.0': 'CC BY 4.0',
    'spdx.org/licenses/cc0-1.0': 'CC0 1.0'
  };
  var HL7_CODES = { u: 'unrestricted', l: 'low', m: 'moderate', n: 'normal', r: 'restricted', v: 'very restricted' };

  function matchHost(s, table) {
    s = strip(s).toLowerCase();
    if (!s) return null;
    for (var k in table) if (s.indexOf(k) >= 0) return { key: k, label: table[k] };
    return null;
  }
  function hl7Code(v) {
    var s = strip(v).toLowerCase();
    if (!s) return null;
    if (HL7_CODES[s]) return { code: s.toUpperCase(), label: HL7_CODES[s] };
    for (var c in HL7_CODES) if (HL7_CODES[c] === s) return { code: c.toUpperCase(), label: s };
    return null;
  }
  var ONTOLOGY_RE = new RegExp(Object.keys(ONTOLOGY_HOSTS).map(function (k) {
    return k.replace(/[.*+?^${}()|[\]\\/]/g, '\\$&');
  }).join('|'), 'gi');

  // ------------------------------------------------------------ crate model
  function findRoot(graph) {
    var descriptor = null, root = null;
    for (var i = 0; i < graph.length; i++) {
      var e = graph[i], id = String(e['@id'] || '');
      if (asList(e['@type']).indexOf('CreativeWork') >= 0 && /ro-crate-metadata\.json$/.test(id)) { descriptor = e; break; }
    }
    if (descriptor) {
      var about = idsOf(descriptor.about);
      for (i = 0; i < graph.length; i++) if (about.indexOf(String(graph[i]['@id'])) >= 0) { root = graph[i]; break; }
    }
    if (!root) for (i = 0; i < graph.length; i++) if (asList(graph[i]['@type']).join(' ').indexOf('ROCrate') >= 0) { root = graph[i]; break; }
    return { descriptor: descriptor, root: root };
  }

  function computeStats(doc, graph, root) {
    var s = {
      typeCounts: {}, entityTotal: 0, entityWithProvLink: 0,
      datasetTotal: 0, datasetWithProv: 0, datasetWithContentUrl: 0, datasetWithRemoteUrl: 0,
      hosts: {}, datasetEmbargoed: 0, datasetWithHash: 0, softwareWithHash: 0,
      datasetWithSchemaRef: 0, datasetImageTotal: 0, datasetSplitCount: 0, splitNames: [],
      exampleDataset: null, formats: {}, summaryStatsTotal: 0,
      softwareTotal: 0, software: [], computationTotal: 0, experimentTotal: 0,
      computationWithSoftware: 0, activityWithIO: 0, activityWithContainer: 0,
      schemaTotal: 0, sampleTotal: 0, instrumentTotal: 0, personIds: [], definedTermTotal: 0,
      subcratesReferenced: 0, vocabHits: {}
    };
    var seen = {};
    var rootId = root ? String(root['@id']) : null;
    graph.forEach(function (e) {
      var id = String(e['@id'] || '');
      var t = canonicalType(e);
      if (anyField(e, SUMMARY_STATS_FIELDS)) s.summaryStatsTotal += 1;
      if (seen[id]) return;
      seen[id] = true;
      if (t === 'ROCrate') {
        if (id !== rootId && e['ro-crate-metadata']) s.subcratesReferenced += 1;
        return;
      }
      if (t === 'CreativeWork') return;
      s.entityTotal += 1;
      s.typeCounts[t] = (s.typeCounts[t] || 0) + 1;
      if (anyField(e, PROV_LINK_FIELDS)) s.entityWithProvLink += 1;
      var fmt = e.format;
      if (t === 'Dataset') {
        s.datasetTotal += 1;
        if (anyField(e, PROV_LINK_FIELDS)) s.datasetWithProv += 1;
        var urls = idsOf(e.contentUrl);
        if (urls.length) {
          s.datasetWithContentUrl += 1;
          var m = /^([a-z][a-z0-9+.-]*):\/\/([^\/?#]+)/i.exec(urls[0]);
          if (m) {
            var scheme = m[1].toLowerCase();
            if (['http', 'https', 'ftp', 'ftps', 's3', 'gs', 'drs'].indexOf(scheme) >= 0) s.datasetWithRemoteUrl += 1;
            var key = scheme + '://' + m[2].toLowerCase();
            s.hosts[key] = (s.hosts[key] || 0) + 1;
          }
        }
        var blob = (urls.join(' ') + ' ' + String(e.description || '').slice(0, 300)).toLowerCase();
        if (blob.indexOf('embargo') >= 0) s.datasetEmbargoed += 1;
        if (anyField(e, HASH_FIELDS)) s.datasetWithHash += 1;
        if (anyField(e, SCHEMA_REF_FIELDS)) s.datasetWithSchemaRef += 1;
        if (fmt && /image\/|jpe?g|png|tiff?\b|gif|bmp/i.test(String(fmt))) s.datasetImageTotal += 1;
        var name = String(e.name || '');
        if (/\b(train(ing)?|test|validation|valid|holdout|hold-out|split)\b/i.test(name)) {
          s.datasetSplitCount += 1;
          if (s.splitNames.length < 8) s.splitNames.push(name);
        }
        if (!s.exampleDataset && /\b(example|synthetic)\b/i.test(name)) s.exampleDataset = { '@id': id, name: name };
      }
      if (t === 'Dataset' || t === 'Software') {
        if (truthy(fmt)) { var f = String(fmt); s.formats[f] = (s.formats[f] || 0) + 1; }
      }
      if (t === 'Software') {
        s.softwareTotal += 1;
        if (anyField(e, HASH_FIELDS)) s.softwareWithHash += 1;
        s.software.push(e);
      }
      if (t === 'Computation' || t === 'Experiment') {
        if (t === 'Computation') { s.computationTotal += 1; if (truthy(e.usedSoftware)) s.computationWithSoftware += 1; }
        else s.experimentTotal += 1;
        if (anyField(e, ACTIVITY_INPUT_FIELDS) && anyField(e, ACTIVITY_OUTPUT_FIELDS)) s.activityWithIO += 1;
        if (truthy(e.usedContainer)) s.activityWithContainer += 1;
      }
      if (t === 'Schema') s.schemaTotal += 1;
      if (t === 'Sample') s.sampleTotal += 1;
      if (t === 'Instrument') s.instrumentTotal += 1;
      if (t === 'Person') s.personIds.push(id);
      if (t === 'DefinedTerm') s.definedTermTotal += 1;
    });
    s.activityTotal = s.computationTotal + s.experimentTotal;
    // ontology hits anywhere in the raw JSON text
    var raw = JSON.stringify(doc);
    var mm, hits = 0;
    ONTOLOGY_RE.lastIndex = 0;
    while ((mm = ONTOLOGY_RE.exec(raw)) !== null) {
      var k = mm[0].toLowerCase();
      s.vocabHits[k] = (s.vocabHits[k] || 0) + 1;
      hits += 1;
    }
    s.vocabHitTotal = hits;
    return s;
  }

  function loadCrate(doc) {
    if (!doc || !Array.isArray(doc['@graph'])) throw new Error('Not an RO-Crate: no @graph array');
    var graph = doc['@graph'];
    var found = findRoot(graph);
    if (!found.root) throw new Error('Root dataset not found (no ro-crate-metadata.json descriptor with an about link)');
    return {
      doc: doc, graph: graph, descriptor: found.descriptor, root: found.root,
      rootIndex: graph.indexOf(found.root),
      stats: computeStats(doc, graph, found.root)
    };
  }

  // ------------------------------------------------------------ rubric estimates
  // Mechanical application of the v1.8 scoring rules to the crate, following
  // aireadiness_evidence.sections.*.estimate_*; null = needs a human read.
  // No network: URL resolution / DOI negotiation checks are not performed.
  function est(score, basis) { return { score: score, basis: basis }; }

  function joinedText(root, fields) {
    return fields.map(function (f) { return text(root[f]); }).join('\n');
  }
  var AI_RE = /(AI\/ML|artificial intelligence|machine[- ]learning|\bAI\b|\bML\b)/i;
  var IRB_RE = /\bIRB\b|\bREC\b|protocol\s*(#|no\.?|number)|institutional review board|ethics (board|committee|review)/i;
  var QC_RE = /quality[- ]control|\bQC\b|quality assessment|outlier|filter(ed|ing)/i;
  var PLACEHOLDER_RE = /^\s*(none|n\/?a|no known \w+\.?)\s*$/i;

  function licenseInfo(root) {
    var lic = root.license, vals = [];
    asList(lic).forEach(function (l) {
      if (typeof l === 'string') vals.push(l);
      else if (l && typeof l === 'object') vals.push(l['@id'] || l.url || l.name || '');
    });
    var joined = vals.join(' ').trim();
    return {
      present: joined !== '',
      value: joined,
      machineReadable: /^https?:\/\/\S+$/.test(joined),
      known: matchHost(joined, LICENSE_NAMES)
    };
  }

  var ESTIMATORS = {
    '0.a': function (c) {
      var root = c.root, pidSrc = root.identifier || root['@id'];
      var pid = detectPid(pidSrc), basis = [];
      var repo = matchHost(root.publisher, SPECIALIST_REPOS) || matchHost(root.publisher, GENERALIST_REPOS);
      var bad = matchHost(root.publisher, NON_SUSTAINABLE_HOSTS);
      if (bad) { basis.push('publisher is unmanaged storage (' + bad.label + ') — not a sustainable repository'); repo = null; }
      if (pid) basis.push('PID present (scheme: ' + pid + ')' + (root.identifier ? '' : ' — from the crate @id; no external identifier set'));
      else basis.push('no recognised persistent identifier');
      if (repo) basis.push('publisher recognised as a sustainable repository (' + repo.label + ')');
      else if (truthy(root.publisher)) basis.push('publisher "' + text(root.publisher) + '" is not a recognised sustainable repository');
      else basis.push('no publisher / repository named');
      basis.push('PID resolution not checked (no network in this page)');
      if (pid && repo) return est(2, basis);
      if (pid || repo) return est(1, basis);
      return est(0, basis);
    },
    '0.b': function (c) {
      var root = c.root, id = strip(root.identifier), basis = [];
      if (/10\.\d{4,9}\//.test(id)) basis.push('DOI present — metadata availability via content negotiation needs a network check (fairscape-evidence)');
      else if (id) basis.push('identifier is not a DOI; independent metadata lookup cannot be verified here');
      else basis.push('no external identifier — set one so descriptive metadata is reachable via PID lookup');
      basis.push('@context declares ' + Object.keys(c.doc['@context'] || {}).length + ' vocabulary bindings (JSON-LD)');
      return est(null, basis);
    },
    '0.c': function (c) {
      var ctx = c.doc['@context'], basis = [];
      var hasCtx = truthy(ctx);
      if (hasCtx) basis.push('metadata is JSON-LD with an @context');
      else basis.push('no @context — metadata is not a formal interoperable specification');
      if (c.stats.vocabHitTotal) basis.push(c.stats.vocabHitTotal + ' standard-vocabulary IRI references (' + Object.keys(c.stats.vocabHits).join(', ') + ')');
      else basis.push('references no standard vocabulary (add ontology IRIs under subject terms)');
      if (c.stats.schemaTotal) basis.push(c.stats.schemaTotal + ' machine-readable schema entities');
      if (hasCtx && c.stats.vocabHitTotal) return est(2, basis);
      if (hasCtx || c.stats.schemaTotal || c.stats.datasetWithSchemaRef) return est(1, basis);
      return est(0, basis);
    },
    '0.d': function (c) {
      var root = c.root, li = licenseInfo(root), basis = [];
      if (!li.present) return est(0, ['no license or DUA linked in the metadata']);
      basis.push(li.machineReadable ? 'machine-readable license linked in the metadata' + (li.known ? ' (' + li.known.label + ')' : '')
        : 'license is not a bare resolvable IRI ("' + li.value.slice(0, 60) + '") — not machine-readable');
      var terms = joinedText(root, ['conditionsOfAccess', 'usageInfo', 'prohibitedUses']);
      if (AI_RE.test(terms)) { basis.push('use terms mention AI/ML — a human must confirm they permit, not prohibit, AI/ML reuse'); return est(null, basis); }
      basis.push('no AI/ML prohibition language found in license or use terms');
      basis.push('license URL resolution not checked (no network)');
      return est(li.machineReadable ? 2 : 1, basis);
    },
    '1.a': function (c) {
      var s = c.stats, root = c.root, basis = [];
      basis.push(s.datasetWithProv + ' of ' + s.datasetTotal + ' datasets carry provenance links');
      var missing = [];
      if (!s.sampleTotal) missing.push('samples');
      if (!s.instrumentTotal) missing.push('instruments');
      if (!s.experimentTotal) missing.push('experiments');
      if (missing.length) basis.push('ground-truth elements missing: ' + missing.join(', ') + ' (need Sample/Instrument/Experiment entities)');
      var named = nonblank(root['rai:dataCollectionRawData']) || nonblank(root['rai:dataCollection']);
      if (named) basis.push('source named in a structured field (rai:dataCollectionRawData / rai:dataCollection)');
      if (s.datasetWithProv && !missing.length) return est(2, basis);
      if (s.datasetWithProv || named) return est(1, basis);
      basis.push('no data source identified');
      return est(0, basis);
    },
    '1.b': function (c) {
      var s = c.stats, root = c.root, basis = [];
      if (!s.activityTotal) return est(0, ['no transformation steps (Computation/Experiment entities) recorded']);
      basis.push(s.activityTotal + ' machine-readable transformation steps');
      var allSw = s.computationTotal > 0 && s.computationWithSoftware === s.computationTotal;
      basis.push(allSw ? 'every computation links its software' : s.computationWithSoftware + ' of ' + s.computationTotal + ' computations link software');
      var gap = /chain[- ]of[- ]custody|provenance gap|missing provenance|collection circumstances|retrospective(ly)? (collected|acquired)|original (collection|source) (records? )?(unavailable|unknown|lost)/i;
      var prose = joinedText(root, ['description', 'rai:dataCollection', 'rai:dataLimitations', 'completeness']);
      basis.push(gap.test(prose) ? 'provenance gaps are disclosed in prose' : 'completeness of the provenance record (or disclosure of known gaps) is a human read');
      return est(allSw ? 2 : 1, basis);
    },
    '1.c': function (c) {
      var s = c.stats, basis = [];
      if (!s.softwareTotal) return est(0, ['no software entities']);
      var archived = 0, code = 0, provider = 0, unhosted = 0;
      s.software.forEach(function (sw) {
        var blob = idsOf(sw.contentUrl).concat(idsOf(sw.codeRepository), idsOf(sw.additionalDocumentation)).join(' ');
        if (matchHost(blob, SOFTWARE_ARCHIVE_HOSTS)) archived += 1;
        else if (matchHost(blob, CODE_HOSTS)) code += 1;
        else if (/https?:\/\//i.test(blob)) provider += 1;
        else unhosted += 1;
      });
      if (archived) basis.push(archived + ' archived with a PID (Zenodo / Software Heritage / DOI / PyPI)');
      if (code) basis.push(code + ' on mutable code hosting only');
      if (provider) basis.push(provider + ' linked to a provider website (proprietary software?) — human call');
      if (unhosted) basis.push(unhosted + ' with no link');
      if (provider) return est(null, basis);
      if (archived === s.softwareTotal) return est(2, basis);
      if (archived || code) return est(1, basis);
      return est(0, basis);
    },
    '1.d': function (c) {
      var root = c.root, s = c.stats, basis = [];
      var authors = asList(root.author), pidd = 0, free = 0;
      authors.forEach(function (a) {
        if (a && typeof a === 'object' && a['@id'] && (String(a['@id']).indexOf('orcid.org') >= 0 || s.personIds.indexOf(String(a['@id'])) >= 0)) pidd += 1;
        else free += 1;
      });
      var orcidInString = authors.some(function (a) { return typeof a === 'string' && /orcid\.org\//i.test(a); });
      if (authors.length) basis.push(pidd + ' of ' + authors.length + ' authors carry a PID; ' + free + ' named in free text only');
      if (orcidInString) basis.push('ORCID URLs inside author strings are kept for readers, but the extractor only credits Person entities with an ORCID @id');
      if (truthy(root.principalInvestigator)) basis.push('principal investigator named');
      var ror = idsOf(root.isPartOf).some(function (i) { return i.indexOf('ror.org') >= 0; });
      if (ror) basis.push('organisation linked by ROR');
      if (authors.length && free === 0) return est(2, basis);
      if (authors.length || truthy(root.principalInvestigator) || truthy(root.publisher)) return est(1, basis);
      return est(0, ['no authors, PI or publisher named']);
    },
    '2.a': function (c) {
      var root = c.root, s = c.stats, basis = [];
      var desc = strip(text(root.description)), kw = asList(root.keywords).filter(nonblank);
      if (!desc) return est(0, ['no description / abstract']);
      basis.push('abstract present (' + desc.length + ' chars)');
      if (!kw.length) { basis.push('no keywords'); return est(null, basis); }
      basis.push(kw.length + ' keywords');
      var aboutIris = idsOf(root.about).filter(function (i) { return matchHost(i, ONTOLOGY_HOSTS); });
      var inlineTerms = asList(root.about).filter(function (t) { return t && typeof t === 'object' && String(t['@type'] || '').indexOf('DefinedTerm') >= 0; }).length;
      if (s.definedTermTotal) basis.push(s.definedTermTotal + ' DefinedTerm entities (controlled vocabulary)');
      else if (aboutIris.length) basis.push(aboutIris.length + ' recognised ontology IRIs under about' + (inlineTerms ? ' (' + inlineTerms + ' as inline DefinedTerm objects)' : '') + ' — credited as vocabulary references for 0.c/2.c/6.a; the 2.a extractor counts DefinedTerm graph entities, so this reads as 1 mechanically and leaves the rest to the grader');
      else basis.push('no controlled-vocabulary terms (free-text keywords only)');
      return est(s.definedTermTotal ? 2 : 1, basis);
    },
    '2.b': function (c) {
      var root = c.root, s = c.stats, basis = [];
      var miss = nonblank(root['rai:dataCollectionMissingData']);
      if (s.summaryStatsTotal) basis.push(s.summaryStatsTotal + ' entities link summary statistics');
      else basis.push('no summary statistics linked (fairscape-cli augment summary-stats)');
      basis.push(miss ? 'missing-value convention documented' : 'missing-value encoding not documented');
      if (s.summaryStatsTotal && miss) return est(2, basis);
      if (miss) return est(1, basis);
      if (s.summaryStatsTotal) return est(null, basis);
      return est(0, basis);
    },
    '2.c': function (c) {
      var s = c.stats, basis = [];
      if (!s.schemaTotal) return est(0, ['no schema entities — no formal schema for any format class']);
      basis.push(s.schemaTotal + ' schema entities; ' + s.datasetWithSchemaRef + ' of ' + Math.max(0, s.datasetTotal - s.datasetImageTotal) + ' non-image datasets reference one');
      if (s.vocabHitTotal) { basis.push('standard-vocabulary references present (' + Object.keys(s.vocabHits).join(', ') + ')'); return est(2, basis); }
      basis.push('no standard-vocabulary binding found (add ontology IRIs under subject terms)');
      return est(1, basis);
    },
    '2.d': function (c) {
      var root = c.root, basis = [];
      var blob = joinedText(root, ['rai:dataBiases', 'rai:dataCollectionMissingData', 'completeness', 'rai:dataLimitations']).trim();
      if (!blob) return est(0, ['no bias, missingness, completeness or limitations statement']);
      var bias = strip(text(root['rai:dataBiases']));
      basis.push(bias ? (bias.length >= 120 && !PLACEHOLDER_RE.test(bias) ? 'bias statement looks substantive (' + bias.length + ' chars)' : 'bias statement is short or a placeholder') : 'no explicit bias statement (only limitations / missingness text)');
      basis.push('substance is a human read (specific sources of bias, missingness reasons, state-vs-control)');
      return est(null, basis);
    },
    '2.e': function (c) {
      var root = c.root, basis = [];
      var coll = strip(text(root['rai:dataCollection']));
      var qc = QC_RE.test(joinedText(root, ['rai:dataCollection', 'rai:dataCollectionMissingData', 'description', 'rai:dataPreprocessingProtocol', 'rai:dataManipulationProtocol']));
      if (!coll && !qc) return est(0, ['no collection / QC procedure described']);
      if (coll) basis.push('collection procedure described');
      basis.push(qc ? 'QC language found' : 'no explicit QC language (quality control, QC, filtering, outliers)');
      var urls = coll.match(/https?:\/\/[^\s"')\]]+/g) || [];
      basis.push(urls.length ? urls.length + ' link(s) in the procedure — resolution not checked here; a dead link scores 0' : 'no link to a protocol or QC software');
      basis.push('domain adequacy (1 vs 2) is an expert read');
      return est(null, basis);
    },
    '3.a': function (c) {
      var root = c.root, basis = [];
      var fields = ['rai:dataCollection', 'rai:dataUseCases', 'rai:dataLimitations', 'rai:dataBiases', 'rai:dataReleaseMaintenancePlan', 'license', 'conditionsOfAccess'];
      var n = fields.filter(function (f) { return nonblank(root[f]); }).length;
      basis.push(n + ' of 7 machine-readable datasheet sections populated');
      var ds = !!c.hasDatasheet;
      basis.push(ds ? 'human-readable datasheet declared present' : 'no human-readable datasheet declared (tick the box if ro-crate-datasheet.html sits beside the crate)');
      if (ds && n >= 5) return est(2, basis);
      if (ds || n) return est(1, basis);
      return est(0, basis);
    },
    '3.b': function (c) {
      var root = c.root, basis = [];
      var uc = nonblank(root['rai:dataUseCases']), lim = nonblank(root['rai:dataLimitations']), pu = nonblank(root.prohibitedUses);
      var pubs = (text(root.associatedPublication).match(/https?:\/\/\S+|\bdoi:\s?\S+|\b10\.\d{4,9}\/\S+/g) || []).length;
      if (uc) basis.push('appropriate uses stated'); else basis.push('no intended-use statement');
      if (lim || pu) basis.push('inappropriate uses / limitations stated'); else basis.push('no limitations or prohibited uses');
      basis.push(pubs ? pubs + ' prior publication link(s)' : 'no prior-analysis links (N/A if newly released)');
      if (uc && (lim || pu)) return est(2, basis);
      if (uc || lim || pu || nonblank(root.usageInfo)) return est(1, basis);
      return est(0, basis);
    },
    '3.c': function (c) {
      var s = c.stats, denom = s.datasetTotal + s.softwareTotal - s.datasetEmbargoed;
      var hashed = s.datasetWithHash + s.softwareWithHash, basis = ['checksums on ' + hashed + ' of ' + denom + ' entities'];
      if (s.datasetEmbargoed) basis.push(s.datasetEmbargoed + ' embargoed datasets excluded');
      if (denom > 0 && hashed >= denom) return est(2, basis);
      if (hashed) return est(1, basis);
      return est(0, basis);
    },
    '4.a': function (c) {
      var root = c.root, basis = [];
      var present = ['rai:dataCollection', 'ethicalReview', 'humanSubjectResearch', 'd4d:humanSubjectResearch', 'humanSubjectExemption', 'd4d:humanSubjectExemption', 'd4d:informedConsent', 'informedConsent', 'd4d:atRiskPopulations', 'atRiskPopulations', 'irb', 'irbProtocolId', 'd4d:irb']
        .filter(function (f) { return nonblank(root[f]); });
      var blob = joinedText(root, ['rai:dataCollection', 'ethicalReview', 'humanSubjectExemption', 'd4d:informedConsent']);
      if (!present.length && !IRB_RE.test(blob)) return est(0, ['no acquisition description, ethical review, consent or IRB reference']);
      basis.push('populated: ' + present.join(', '));
      if (IRB_RE.test(blob)) basis.push('IRB / ethics-committee reference found');
      if (/waiver|exempt\w*|secondary (use|analysis)|retrospective/i.test(blob)) basis.push('waiver / secondary-use basis mentioned');
      if (/AI\/ML|artificial intelligence|machine[- ]learning|commercializ/i.test(blob)) basis.push('consent language mentions AI/ML');
      basis.push(nonblank(root['rai:dataReleaseMaintenancePlan']) ? 'management plan present' : 'no management plan (DMP) linked');
      basis.push('completeness vs. generic is a human read');
      return est(null, basis);
    },
    '4.b': function (c) {
      var root = c.root, basis = [];
      var conf = nonblank(root.confidentialityLevel), psi = nonblank(root['rai:personalSensitiveInformation']), plan = nonblank(root['rai:dataReleaseMaintenancePlan']);
      if (!conf && !psi && !plan) return est(0, ['no sensitivity, privacy or management description']);
      if (conf) basis.push('confidentiality level declared');
      if (psi) basis.push('sensitive-attribute statement present');
      if (nonblank(root.dataGovernanceCommittee)) basis.push('governance committee named');
      if (nonblank(root['d4d:participantPrivacy'])) basis.push('privacy-protection processing described');
      var blob = joinedText(root, ['d4d:participantPrivacy', 'ethicalReview', 'rai:dataReleaseMaintenancePlan', 'rai:personalSensitiveInformation']);
      basis.push(/privacy impact assessment|\bPIA\b|(privacy|disclosure|re[- ]?identification) risk assess\w*/i.test(blob) ? 'privacy impact assessment mentioned' : 'no PIA / risk assessment mentioned');
      basis.push(/(periodic\w*|annual\w*|regular\w*|ongoing) (re[- ]?)?(assess|review|evaluat)\w*|reassess\w*|re[- ]?identification risk/i.test(blob) ? 'periodic reassessment mentioned' : 'no periodic re-identification reassessment plan mentioned');
      return est(null, basis);
    },
    '4.c': function (c) {
      var root = c.root, basis = [], li = licenseInfo(root);
      if (!li.present && !nonblank(root.conditionsOfAccess)) return est(0, ['no license and no access conditions — no ethical terms defined']);
      if (li.present) basis.push('license: ' + li.value.slice(0, 80));
      if (nonblank(root.conditionsOfAccess)) basis.push('access conditions stated');
      if (nonblank(root.prohibitedUses)) basis.push('prohibited uses stated');
      basis.push(nonblank(root.contactEmail) ? 'contact email present (DAC contact if access is controlled)' : 'no contact email (needed if access is controlled)');
      var hr = /\bvoice\b|\bspeech\b|audio recording|genom\w+|whole[- ]genome|\bWGS\b|face|facial|full[- ]head|geolocation|GPS trace|location histor\w+/i;
      if (hr.test(joinedText(root, ['keywords', 'description', 'rai:personalSensitiveInformation']))) basis.push('high-risk modality terms found — modality-specific prohibitions expected');
      basis.push('ethical justification of the terms is a human read');
      return est(null, basis);
    },
    '4.d': function (c) {
      var root = c.root, v = root.confidentialityLevel;
      if (!nonblank(v)) return est(0, ['no security / confidentiality level metadata']);
      var code = hl7Code(text(v));
      if (code) return est(2, ["confidentiality level is an HL7 v3-Confidentiality code ('" + code.code + "' — " + code.label + ')', 'enforcement of the declared level is not verified here']);
      return est(1, ['confidentiality level "' + text(v) + '" is prose, not an HL7 code — pick one of unrestricted/low/moderate/normal/restricted/very restricted']);
    },
    '5.a': function (c) {
      var root = c.root, s = c.stats, basis = [];
      var pid = detectPid(root.identifier || root['@id']);
      basis.push(pid ? 'PID present (scheme: ' + pid + ')' : 'no persistent identifier');
      var archive = matchHost(root.publisher, SPECIALIST_REPOS) || matchHost(root.publisher, GENERALIST_REPOS);
      var hostKeys = Object.keys(s.hosts);
      if (!archive) for (var i = 0; i < hostKeys.length && !archive; i++) archive = matchHost(hostKeys[i], SPECIALIST_REPOS) || matchHost(hostKeys[i], GENERALIST_REPOS);
      if (archive) basis.push('recognised archive: ' + archive.label);
      else basis.push(s.datasetWithContentUrl + ' datasets have a contentUrl but no recognised archive detected');
      var bad = hostKeys.map(function (h) { return matchHost(h, NON_SUSTAINABLE_HOSTS); }).filter(Boolean);
      if (bad.length) basis.push('unmanaged storage hosts present: ' + bad.map(function (b) { return b.label; }).join(', '));
      basis.push(nonblank(root['rai:dataCollectionRawData']) ? 'raw-data preservation described' : 'raw-data preservation not described');
      if (pid && archive) return est(2, basis);
      if (pid || archive || s.datasetWithContentUrl) return est(1, basis);
      return est(0, basis);
    },
    '5.b': function (c) {
      var root = c.root, s = c.stats, basis = [], hostKeys = Object.keys(s.hosts);
      var spec = null, gen = null;
      hostKeys.forEach(function (h) { spec = spec || matchHost(h, SPECIALIST_REPOS); gen = gen || matchHost(h, GENERALIST_REPOS); });
      var pubSpec = matchHost(root.publisher, SPECIALIST_REPOS), pubGen = matchHost(root.publisher, GENERALIST_REPOS);
      if (spec) { basis.push('data hosted at a specialist repository: ' + spec.label); return est(2, basis); }
      if (gen) basis.push('data hosted at a generalist repository: ' + gen.label);
      if (pubSpec || pubGen) basis.push('publisher names ' + (pubSpec || pubGen).label + ' (credit needs the data contentUrl hosts to match too)');
      if (gen || pubSpec || pubGen) { basis.push('whether a specialist repository exists for this data type is a human call'); return est(null, basis); }
      basis.push('no recognised repository host detected among ' + hostKeys.length + ' contentUrl host(s)');
      return est(0, basis);
    },
    '5.c': function (c) {
      var root = c.root, basis = [];
      var plan = strip(text(root['rai:dataReleaseMaintenancePlan'])), gov = nonblank(root.dataGovernanceCommittee);
      if (!plan && !gov) return est(0, ['no maintenance plan and no governance committee']);
      if (plan) {
        basis.push('maintenance plan present (' + plan.length + ' chars)');
        basis.push(/stewardship|long[- ]term|retention|maintenance|policy|sustain\w*|preservation|succession/i.test(plan) ? 'stewardship / policy language found' : 'no stewardship, retention or policy language in the plan');
        basis.push(/https?:\/\//.test(plan) ? 'plan links a document' : 'no DMP link in the plan');
      }
      if (gov) basis.push('governance committee named');
      basis.push('comprehensiveness is a human read');
      return est(null, basis);
    },
    '5.d': function (c) {
      var root = c.root, s = c.stats, basis = [];
      var parts = asList(root.hasPart).length;
      basis.push(parts + ' components listed in hasPart');
      basis.push(s.entityWithProvLink + ' entities carry provenance links');
      if (s.subcratesReferenced) basis.push(s.subcratesReferenced + ' sub-crates referenced — presence on disk not checked here (missing ones score 0)');
      if (s.entityWithProvLink && parts) return est(2, basis.concat(['components associated machine-readably in the archived RO-Crate']));
      if (parts) return est(1, basis);
      return est(0, basis);
    },
    '6.a': function (c) {
      var root = c.root, s = c.stats, basis = [];
      var conf = idsOf(root.conformsTo).concat(c.descriptor ? idsOf(c.descriptor.conformsTo) : []);
      var ctxText = JSON.stringify(c.doc['@context'] || {});
      var blob = conf.join(' ') + ' ' + ctxText + (s.schemaTotal ? ' json-schema.org' : '');
      var validators = Object.keys(KNOWN_VALIDATORS).filter(function (k) { return blob.indexOf(k) >= 0; });
      var namespaces = Object.keys(STANDARD_NAMESPACES).filter(function (k) { return blob.indexOf(k) >= 0; });
      if (conf.length) basis.push('conformsTo: ' + conf.join(', '));
      if (validators.length) basis.push('deterministic validators available: ' + validators.map(function (k) { return KNOWN_VALIDATORS[k]; }).join('; '));
      if (!conf.length && !namespaces.length && !s.schemaTotal) return est(0, ['no declared standard, namespace or schema']);
      if (validators.length && s.vocabHitTotal) return est(2, basis.concat(['populated standard-vocabulary bindings present']));
      basis.push('no populated standard-vocabulary bindings — semantic conformance cannot be validated');
      return est(1, basis);
    },
    '6.b': function (c) {
      var s = c.stats, basis = [];
      if (!s.datasetWithRemoteUrl) return est(0, ['no dataset has a remote distribution link (http/s3/gs/drs) — no programmatic access mechanism visible']);
      basis.push(s.datasetWithRemoteUrl + ' of ' + s.datasetTotal + ' datasets have remote URLs (' + Object.keys(s.hosts).slice(0, 4).join(', ') + ')');
      basis.push('API / documentation quality (1 vs 2) is a human read');
      return est(null, basis);
    },
    '6.c': function (c) {
      var s = c.stats, basis = [];
      var total = s.computationTotal;
      if (total && s.activityWithContainer === total) return est(2, ['all ' + total + ' computations declare a container (usedContainer)']);
      if (s.activityWithContainer) return est(1, ['containers on ' + s.activityWithContainer + ' of ' + total + ' computations']);
      var envSw = s.software.filter(function (sw) { return nonblank(sw.containerImage) || nonblank(sw.softwareRequirements); }).length;
      basis.push('no computation declares a container');
      if (envSw) basis.push(envSw + ' software entities describe a container / requirements (read by the grader as software evidence)');
      basis.push('whether the data needs a specialised environment at all is a human call');
      return est(null, basis);
    },
    '6.d': function (c) {
      var root = c.root, s = c.stats, basis = [];
      var sampling = nonblank(root['d4d:samplingStrategies']) || nonblank(root.samplingStrategies);
      var miss = nonblank(root['rai:dataCollectionMissingData']), prep = nonblank(root['rai:dataPreprocessingProtocol']);
      if (!s.datasetSplitCount && !sampling && !miss && !prep && !s.exampleDataset) return est(0, ['no splits, withheld-information statement, or example data anywhere in the metadata']);
      if (s.datasetSplitCount) basis.push(s.datasetSplitCount + ' split-named datasets');
      if (sampling) basis.push('sampling / withheld data described');
      if (miss) basis.push('missing / withheld information described');
      if (prep) basis.push('preprocessing described');
      basis.push(s.exampleDataset ? 'example / synthetic dataset present' : 'no example or synthetic dataset (a Dataset named "example…"/"synthetic…")');
      if (s.exampleDataset && (miss || prep)) return est(2, basis);
      return est(1, basis);
    }
  };

  function estimateAll(crate, opts) {
    var ctx = { doc: crate.doc, root: crate.root, descriptor: crate.descriptor, stats: crate.stats, hasDatasheet: !!(opts && opts.hasDatasheet) };
    var out = {};
    for (var cid in ESTIMATORS) {
      try { out[cid] = ESTIMATORS[cid](ctx); }
      catch (err) { out[cid] = { score: null, basis: ['estimate failed: ' + err.message] }; }
    }
    // dependency caps: 1.b <= 1.a, 6.a <= 2.c
    [['1.b', '1.a'], ['6.a', '2.c']].forEach(function (d) {
      var a = out[d[0]], b = out[d[1]];
      if (a && b && a.score !== null && b.score !== null && a.score > b.score) {
        a.score = b.score; a.basis = a.basis.concat(['capped at ' + d[1] + "'s score (" + b.score + ') by the dependency rule']);
      }
    });
    return out;
  }

  var GATES = { '0.a': 2, '0.b': 1, '0.c': 1, '0.d': 1, '1.a': 1, '1.b': 1, '1.c': 1, '1.d': 1, '2.c': 1, '4.a': 1, '4.b': 1, '4.c': 1, '4.d': 1 };

  function aggregate(estimates) {
    var sections = {}, gateFailures = [], estimated = 0, human = 0, points = 0;
    for (var cid in estimates) {
      var sec = cid.split('.')[0];
      sections[sec] = sections[sec] || { points: 0, max: 0, estimated: 0, human: 0, total: 0 };
      var e = estimates[cid], s = sections[sec];
      s.total += 1;
      if (e.score === null) { s.human += 1; human += 1; continue; }
      s.estimated += 1; estimated += 1; s.points += e.score; s.max += 2; points += e.score;
      if (GATES[cid] !== undefined && e.score < GATES[cid]) gateFailures.push(cid + ' scored ' + e.score + ' (gate needs ' + (GATES[cid] === 2 ? '2' : '> 0') + ')');
    }
    var pcts = [];
    for (var k in sections) sections[k].pct = sections[k].max ? Math.round(1000 * sections[k].points / sections[k].max) / 10 : null;
    for (k in sections) if (sections[k].pct !== null) pcts.push(sections[k].pct);
    return {
      points: points, max: 2 * estimated, estimated: estimated, human: human,
      pct: estimated ? Math.round(1000 * points / (2 * estimated)) / 10 : null,
      overall: pcts.length ? Math.round(10 * pcts.reduce(function (a, b) { return a + b; }, 0) / pcts.length) / 10 : null,
      sections: sections, gateFailures: gateFailures
    };
  }

  // ------------------------------------------------------------ JSON schema (subset)
  // Covers what fairscape_models' pydantic schemas emit: type, enum, const,
  // pattern, minLength/maxLength, minimum/maximum, items, required,
  // properties, additionalProperties, anyOf/oneOf/allOf, $ref (#/$defs/...).
  function typeOf(v) {
    if (v === null) return 'null';
    if (Array.isArray(v)) return 'array';
    if (typeof v === 'number') return Number.isInteger(v) ? 'integer' : 'number';
    return typeof v;
  }
  function typeMatches(want, v) {
    var t = typeOf(v);
    if (want === 'number') return t === 'number' || t === 'integer';
    return want === t;
  }
  function resolveRef(rootSchema, ref) {
    if (ref.indexOf('#/') !== 0) return null;
    var cur = rootSchema;
    ref.slice(2).split('/').forEach(function (p) { cur = cur ? cur[p.replace(/~1/g, '/').replace(/~0/g, '~')] : undefined; });
    return cur || null;
  }
  function validateNode(rootSchema, schema, v, path, errors) {
    if (!schema || schema === true) return;
    if (schema.$ref) { var r = resolveRef(rootSchema, schema.$ref); if (r) validateNode(rootSchema, r, v, path, errors); return; }
    if (schema.type) {
      var types = asList(schema.type);
      if (!types.some(function (t) { return typeMatches(t, v); })) { errors.push({ path: path, message: 'must be ' + types.join(' or ') + ', got ' + typeOf(v) }); return; }
    }
    if (schema.enum && !schema.enum.some(function (e) { return JSON.stringify(e) === JSON.stringify(v); })) errors.push({ path: path, message: 'must be one of ' + schema.enum.join(', ') });
    if (schema.const !== undefined && JSON.stringify(schema.const) !== JSON.stringify(v)) errors.push({ path: path, message: 'must equal ' + JSON.stringify(schema.const) });
    if (typeof v === 'string') {
      if (schema.minLength !== undefined && v.length < schema.minLength) errors.push({ path: path, message: 'must be at least ' + schema.minLength + ' characters' });
      if (schema.maxLength !== undefined && v.length > schema.maxLength) errors.push({ path: path, message: 'must be at most ' + schema.maxLength + ' characters' });
      if (schema.pattern && !(new RegExp(schema.pattern)).test(v)) errors.push({ path: path, message: 'must match pattern ' + schema.pattern });
    }
    if (typeof v === 'number') {
      if (schema.minimum !== undefined && v < schema.minimum) errors.push({ path: path, message: 'must be >= ' + schema.minimum });
      if (schema.maximum !== undefined && v > schema.maximum) errors.push({ path: path, message: 'must be <= ' + schema.maximum });
    }
    if (Array.isArray(v) && schema.items) v.forEach(function (it, i) { validateNode(rootSchema, schema.items, it, path + '[' + i + ']', errors); });
    if (v && typeof v === 'object' && !Array.isArray(v)) {
      asList(schema.required).forEach(function (req) { if (v[req] === undefined) errors.push({ path: path + '/' + req, message: 'required property missing' }); });
      var props = schema.properties || {};
      for (var k in v) {
        if (props[k]) validateNode(rootSchema, props[k], v[k], path + '/' + k, errors);
        else if (schema.additionalProperties === false) errors.push({ path: path + '/' + k, message: 'additional property not allowed' });
        else if (schema.additionalProperties && typeof schema.additionalProperties === 'object') validateNode(rootSchema, schema.additionalProperties, v[k], path + '/' + k, errors);
      }
    }
    ['anyOf', 'oneOf'].forEach(function (kw) {
      if (!schema[kw]) return;
      var ok = 0, best = null;
      schema[kw].forEach(function (sub) {
        var e = []; validateNode(rootSchema, sub, v, path, e);
        if (!e.length) ok += 1; else if (!best || e.length < best.length) best = e;
      });
      if (!ok || (kw === 'oneOf' && ok !== 1)) {
        var opts = schema[kw].map(function (sub) { return sub.$ref ? sub.$ref.split('/').pop() : (sub.type ? (sub.type + (sub.items ? ' of ' + (sub.items.type || (sub.items.$ref || '').split('/').pop() || 'item') : '')) : 'object'); });
        errors.push({ path: path, message: 'must be ' + opts.join(' | ') + ', got ' + describe(v) });
      }
    });
    asList(schema.allOf).forEach(function (sub) { validateNode(rootSchema, sub, v, path, errors); });
  }
  function describe(v) {
    var t = typeOf(v);
    if (t === 'array') return 'array of ' + (v.length ? typeOf(v[0]) : 'nothing');
    return t;
  }
  function validate(schema, data) {
    var errors = [];
    validateNode(schema, schema, data, '', errors);
    // de-duplicate identical messages
    var seen = {}, out = [];
    errors.forEach(function (e) { var k = e.path + '|' + e.message; if (!seen[k]) { seen[k] = 1; out.push(e); } });
    return out;
  }

  // ------------------------------------------------------------ edits
  // edits = { root: {prop: value|null}, software: {"@id": {prop: value|null}} }
  // null removes the property; undefined/absent leaves it untouched.
  function applyEdits(doc, edits) {
    var out = clone(doc);
    var found = findRoot(out['@graph']);
    if (!found.root) throw new Error('root not found');
    function apply(entity, props) {
      for (var p in props) {
        if (props[p] === undefined) continue;
        if (props[p] === null) delete entity[p];
        else entity[p] = props[p];
      }
    }
    apply(found.root, (edits && edits.root) || {});
    var sw = (edits && edits.software) || {};
    out['@graph'].forEach(function (e) { if (sw[String(e['@id'])]) apply(e, sw[String(e['@id'])]); });
    return out;
  }

  var IMPROVE = {
    asList: asList, idsOf: idsOf, truthy: truthy, nonblank: nonblank, text: text, canonicalType: canonicalType,
    detectPid: detectPid, matchHost: matchHost, hl7Code: hl7Code,
    KNOWN: { SPECIALIST_REPOS: SPECIALIST_REPOS, GENERALIST_REPOS: GENERALIST_REPOS, ONTOLOGY_HOSTS: ONTOLOGY_HOSTS, LICENSE_NAMES: LICENSE_NAMES, HL7_CODES: HL7_CODES },
    loadCrate: loadCrate, computeStats: computeStats, findRoot: findRoot,
    estimateAll: estimateAll, aggregate: aggregate, GATES: GATES,
    validate: validate, applyEdits: applyEdits
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = IMPROVE;
  else global.IMPROVE = IMPROVE;
})(typeof window !== 'undefined' ? window : this);
