# AI vendor comparison deck (biomedicine, EU-minded company)

PowerPoint comparison of **Anthropic (Claude)**, **OpenAI (GPT)**, **Microsoft Copilot** (as a
platform) and **Mistral AI** across:

- environmental impact — global (IEA/LBNL data-centre growth) and local (estimated footprint
  for a 350-employee company, base vs heavy AI-usage scenarios, by hosting region)
- data residency & law — EU Data Boundary, AWS Bedrock / Vertex EU regions, CLOUD Act exposure,
  GDPR Art. 9 (health data), EU AI Act (GPAI Code of Practice, Art. 55 systemic risk)
- societal / moral / ethical posture and **existential-risk stance** (safety frameworks,
  published p(doom) statements, what a buyer can actually do)
- **whistleblower signals** — OpenAI SEC/NDA complaint (2024), safety-staff resignations
  (Leike, Kokotajlo), "Pacing the Frontier" (2026), Coxon resignation + Hubinger's >10%
  x-risk post (2026), AIWI NDA-carve-out scorecard, and legal protections (EU AI Act Art. 87 /
  Whistleblower Directive 2019/1937, CA SB 53, NY RAISE Act)
- model performance — coding/agentic (SWE-bench Verified, HumanEval), biomedicine (MedQA,
  HealthBench) and office/knowledge work (MMLU, GPQA, OSWorld)
- cost for 350 employees (seats vs API tokens)

## Files

- `AI_Vendor_Comparison_Biomedicine.pptx` — the deck (16 slides, 16:9)
- `build_deck.py` — regenerates charts and deck: `pip install python-pptx matplotlib && python3 build_deck.py`
- `charts/` — generated PNG charts

## Key assumptions (editable in `build_deck.py`)

- 140 of 350 employees AI-active; 50 heavy users × 150 queries/day, 90 light × 20/day; 250 workdays → 2.33 M queries/yr
- Energy: 0.5 Wh/query base; heavy users 5 Wh (reasoning/agentic), light 0.4 Wh → 1.16 vs 9.56 MWh/yr
- Water: ~30 mL/query; grid intensity: US ~380, EU ~210, Germany ~380, France ~50, Sweden ~40 g CO2e/kWh
- API cost: 500 in/500 out tokens per query (base), 3k in/1k out (heavy)

## Main sources

IEA *Energy and AI* (2025); Communications Sustainability (2026); LBNL US Data Center Energy
Usage Report (2024); Google arXiv:2508.15734 (0.24 Wh median prompt); Epoch AI; Mistral/ADEME/Carbone 4
LCA (2025); Ember/EPA eGRID/ADEME grid intensities; Microsoft Environmental Sustainability Reports
2024/2025; Microsoft Learn (Copilot EUDB); AWS Bedrock/Vertex EU docs; Mistral docs; EU AI Act
GPAI Code of Practice (Jul 2025) & Art. 55; swebench.com; Nature Medicine (2026) MedQA/HealthBench eval;
vendor model cards; Axios (Sep 2025) Amodei p(doom); OpenAI Preparedness Framework v2; vendor pricing
pages. Full list on the last slide of the deck.
