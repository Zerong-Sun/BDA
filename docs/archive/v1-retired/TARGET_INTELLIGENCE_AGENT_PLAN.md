# Target Intelligence Agent Plan

## 1. Product Goal

Target Intelligence Agent is a specialized research agent inside BDA Copilot. It focuses on target-level scientific reasoning for protein design:

1. Resolve a biological target from user input.
2. Retrieve and synthesize traceable literature, structure, sequence, pathway, and user-provided evidence.
3. Identify known or hypothesized hotspot residues, active sites, epitopes, and interface regions.
4. Recommend binder, antibody, or scaffold-design strategies.
5. Generate an auditable BDA workflow route and a high-level validation plan.

The agent should feel independent to users, but it should remain part of the single BDA Copilot runtime described in `COPILOT_TOOLING_LOGIC.md`.

## 2. Non-Negotiable Design Principles

### Citation-Backed RAG

Use the OpenScholar-style principle: every scientific answer must be grounded in retrievable passages, not just paper-level citations.

For each major claim, the agent must preserve:

- source type: literature, PDB, UniProt, Reactome, user file, or curated knowledge;
- identifier: DOI, PMID, PMCID, PDB ID, UniProt accession, or artifact ID;
- title or record name;
- evidence excerpt or structured passage location;
- claim type: reported result, database annotation, structural observation, model prediction, or agent synthesis;
- confidence level and review status.

If the evidence is abstract-only, metadata-only, computational-only, or pending review, the agent must say so explicitly.

### Multi-Agent Research Workflow

Use the FutureHouse-style agent division of labor. The first implementation can run these roles sequentially in one service, but the output schema should keep the roles separate:

- Literature Scout: searches local literature and Europe PMC, prioritizes review articles, primary structural papers, mutagenesis data, and assay papers.
- Structure Analyst: searches RCSB PDB, checks experimental method, resolution, construct, ligand/partner state, interface geometry, and missing regions.
- Target Mapper: resolves UniProt identity, isoform, domain boundaries, functional motifs, PTMs, disulfides, and species context.
- Hotspot Analyst: ranks active-site, epitope, pocket, and interface residues with evidence levels.
- Design Strategist: chooses binder, antibody, peptide, motif-scaffold, or redesign routes and explains method fit.
- Experiment Planner: proposes high-level validation and developability tests without giving unsafe wet-lab operational details.
- Report Writer: emits an auditable dossier with evidence tables, route comparison, risks, and next actions.

### Antibody Route Is First-Class

Antibody design must not be treated as a small variant of generic binder design. The agent must support an antibody-specific route that can include:

- epitope selection and antigen construct assessment;
- antibody-antigen complex search from PDB;
- CDR-focused design or optimization;
- DiffAb-style antigen-specific CDR sequence-structure co-design;
- docking/refinement and developability filters;
- humanization, liability, specificity, and epitope-binning considerations.

The agent should recommend the antibody route when the user asks for antibodies, when the target biology favors extracellular antigens, or when existing antibody/antigen complex evidence is strong.

## 3. Inputs

Minimal input:

- target name, gene, protein name, accession, PDB ID, sequence, or user file;
- objective: binder, antibody, inhibitor, agonist, blocker, stabilizer, degrader-enabling binder, assay reagent, or exploratory;
- organism and disease/application context when available.

Optional constraints:

- desired modality: de novo binder, antibody, peptide, miniprotein, scaffold redesign;
- target region or epitope;
- allowed or disallowed methods;
- construct boundaries;
- expression host;
- assay context;
- delivery, safety, or developability constraints.

## 4. Evidence Workflow

1. Target Resolution
   - Query UniProt first for accession, reviewed status, sequence length, organism, domains, function, and isoforms.
   - Normalize aliases and gene/protein names.

2. Literature Retrieval
   - Search local ingested literature before external sources.
   - Search Europe PMC for target, active site, mutation, epitope, binder, antibody, structure, and assay terms.
   - Prefer primary experimental evidence over review-only summaries.

3. Structure Retrieval
   - Search RCSB PDB by target, UniProt accession, ligand, antibody, receptor, and known complex names.
   - Record method, resolution, release date, construct, partners, ligand state, and citation.

4. Target Mapping
   - Map domains, motifs, active sites, pockets, interfaces, PTMs, disulfides, and known functional regions.
   - Mark structural coverage and missing/flexible regions.

5. Hotspot Inference
   - Level A: direct experimental evidence such as co-structure, alanine scanning, mutagenesis, DMS, or binding assay.
   - Level B: repeated literature or database support.
   - Level C: structure-based inference from conservation, exposure, pocket geometry, or interface contacts.
   - Level D: hypothesis generated by the agent; must be labeled as unvalidated.

## 5. Design Method Matrix

| Method | Best Fit | Model/Training Character | Agent Guidance |
|---|---|---|---|
| RFdiffusion | De novo binders, motif scaffolding, topology generation | Diffusion over protein structures/backbones | Use when an experimental target structure and clear epitope/pocket are available. Pair with ProteinMPNN and structure prediction filters. |
| RFdiffusionAA / RFD3-style all-atom route | Ligand, cofactor, nucleic acid, or precise pocket interactions | All-atom biomolecular diffusion | Use for atom-level interaction design when target context requires ligands or non-protein molecules. |
| ProteinMPNN | Sequence design for fixed or generated backbones | Message-passing neural network for sequence recovery/design | Use after backbone generation or scaffold selection; generate sequence diversity and rescue designs. |
| AlphaFold / AF-Multimer / AF3 | Fold and complex plausibility checks | Structure prediction | Use as ranking or plausibility evidence, never as proof of binding or activity. |
| Rosetta relax/docking/interface scoring | Refinement and physics-style scoring | Statistical/physics energy functions | Use for local refinement, clash removal, and interface score comparison. |
| DiffAb / CDR design | Antibody CDR generation or optimization against antigen structure | Diffusion/equivariant sequence-structure co-design for antibody CDRs | Use for antibody route when antigen structure or epitope is known. Combine with liability, developability, and specificity checks. |
| Docking/pocket scoring | Pose comparison and pocket triage | Sampling plus scoring | Use only as weak computational evidence unless experimentally validated. |
| DMS/ML surrogate | Optimization with sequence-function data | Supervised or active-learning sequence-function model | Use when project-specific experimental data exists. |

## 6. Output Schema

The agent should return a structured dossier:

```json
{
  "target": {
    "name": "string",
    "organism": "string",
    "uniprot_accession": "string",
    "construct_recommendation": "string",
    "confidence": "high|medium|low"
  },
  "evidence": [
    {
      "source_type": "literature|pdb|uniprot|reactome|user_file|knowledge",
      "identifier": "string",
      "title": "string",
      "claim": "string",
      "excerpt": "string",
      "url": "string",
      "evidence_level": "A|B|C|D",
      "review_status": "accepted|pending_review|rejected|unreviewed"
    }
  ],
  "hotspots": [
    {
      "residue": "string",
      "region": "active_site|epitope|interface|pocket|motif|unknown",
      "rationale": "string",
      "evidence_level": "A|B|C|D",
      "sources": ["string"]
    }
  ],
  "design_routes": [
    {
      "route_id": "string",
      "label": "string",
      "fit": "high|medium|low",
      "methods": ["string"],
      "why": "string",
      "risks": ["string"],
      "recommended_next_action": "string"
    }
  ],
  "experiment_plan": {
    "binding_validation": ["string"],
    "specificity": ["string"],
    "developability": ["string"],
    "mutation_or_epitope_validation": ["string"]
  },
  "audit": {
    "agent_roles": ["string"],
    "llm_provider": "string",
    "created_workflow_id": "string|null",
    "limitations": ["string"]
  }
}
```

## 7. Backend Implementation Plan

### PR 1: Schema and Persistence

Add tables:

- `target_intelligence_runs`
- `target_evidence_items`
- `target_hotspots`
- `target_design_routes`
- `target_agent_reports`

Add Pydantic schemas for target intake, evidence item, hotspot, design route, experiment plan, and report.

### PR 2: Agent Service

Add:

- `backend/app/copilot/target_agent.py`
- `backend/app/services/target_intelligence_service.py`

Core service functions:

- `analyze_target(payload)`
- `retrieve_target_evidence(target)`
- `map_target_context(evidence)`
- `infer_hotspots(target_map, evidence)`
- `select_design_routes(target_map, hotspots, objective)`
- `generate_experiment_plan(routes, target_context)`
- `build_research_dossier(...)`

### PR 3: Tool Registry

Extend `backend/app/copilot/tools.py` with controlled tools:

- `resolve_target_identity`
- `search_target_literature`
- `search_target_structures`
- `map_target_hotspots`
- `recommend_design_methods`
- `create_target_design_workflow`

Tools must return structured JSON and must not directly execute shell commands or submit compute jobs.

### PR 4: API

Add endpoints:

- `POST /api/v1/copilot/target-intelligence/analyze`
- `GET /api/v1/copilot/target-intelligence/runs/{run_id}`
- `POST /api/v1/copilot/target-intelligence/runs/{run_id}/apply-route`
- `POST /api/v1/copilot/target-intelligence/runs/{run_id}/export`

### PR 5: Frontend

Add a `Target Intelligence` view under the existing Research/Copilot experience:

- target input;
- evidence table;
- structure/PDB panel;
- hotspot table;
- design route comparison;
- antibody-specific route panel;
- experiment validation plan;
- export dossier;
- create workflow action.

## 8. Safety and Scientific Boundaries

- Do not present AlphaFold, docking, Rosetta, RFdiffusion, DiffAb, or LLM output as validated binding or activity.
- Do not claim a hotspot is experimentally proven unless evidence supports that exact claim.
- Do not provide operational wet-lab protocols, exact transformation/culture conditions, dosing procedures, or hazardous optimization details.
- Always separate reported findings, database annotations, computational predictions, and agent synthesis.
- Cluster jobs remain draft-only until user confirmation.

## 9. Acceptance Criteria

1. A user can enter a target name and objective, and the agent returns a target dossier.
2. Every major scientific claim links to a passage, excerpt, or structured source record.
3. The report clearly distinguishes known active sites from hypothesized hotspots.
4. The agent can recommend generic binder routes and antibody-specific routes.
5. DiffAb/CDR design appears as a dedicated antibody method option when appropriate.
6. The design route recommendation explains why each method fits or does not fit the target.
7. The agent can create a BDA workflow route but cannot submit compute without confirmation.
8. The system still degrades gracefully without an LLM API key by using local knowledge, rule-based routing, and retrieved structured evidence.
