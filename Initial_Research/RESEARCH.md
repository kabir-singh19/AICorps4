# Three Capstone Options for the TAMU AI Corps Group 4 x City of College Station "AI Consulting Tool"

## TL;DR
- Build a narrow, deep, evaluation-first tool that reproduces ONE class of consultant deliverable, using public College Station documents as ground truth. Do not build a broad "consulting chatbot." The best pick is Option A: an RFP/RFQ response generator plus a consultant-spend "expertise network" built from Open Checkbook. It matches the kickoff mandate directly and has the cleanest ground-truth comparison.
- All three options run on the TAMU AI Chat API (GPT, Claude Sonnet, Gemini through tokens) with a retrieval layer over public data. What sets Group 4 apart from Team 1 is a rigorous, rubric-based blind evaluation harness that compares AI output to real consultant deliverables with known costs.
- The work fits Sept 2026 to spring 2027 if the team locks scope to one deliverable type, collects ground-truth documents in the first month, and designs the evaluation before generating anything.

## Key Findings
- **The city's consultant ecosystem is documented and quantifiable.** Confirmed engagements with public deliverables:
  - Planning NEXT + Kimley-Horn: 2021 Comprehensive Plan, "The Next 10"
  - Freese and Nichols: 2021 Water and Wastewater Impact Fee Update Study (PDF on cstx.gov)
  - Kimley-Horn: Roadway Impact Fee Update
  - ETC Institute: 2025 Citizen Satisfaction Survey
  - Raftelis: water rate modeling
  - Brinkley Sargent Wiginton Architects + BerryDunn: 2025 recreation center feasibility study

  The rec center study contract was approved unanimously in October 2023 for $180,768, following an RFQ that drew five responses. The city interviewed three of those firms before selecting one. The smallest concept facility is now estimated at about $57M for 69,500 sq ft (KBTX, May 2026). Other recent Freese and Nichols contracts include $497,270 for the Well 9 Rehabilitation design (FY2026) and a $1,459,269 amendment for specialized construction inspection.
- **Public data is abundant and structured.**
  - Open Checkbook (checkbook.cstx.gov) publishes every payment, searchable by vendor, department, and expenditure type.
  - Raw check-register downloads are posted for FY2024 and FY2025.
  - The CSTX Open Data portal (data.cstx.gov) exists.
  - The FY2026 adopted budget totals $474,225,698.
  - Bids and solicitations are posted through the Brazos Valley e-Marketplace (Ionwave), with closed-bidding datasets for FY2023 to FY2026.
- **The TAMU AI Chat API is real and usable.** Students get API keys from chat.tamu.ai for OpenAI GPT, Anthropic Claude Sonnet, and Google Gemini. It supports data up to University-Confidential and does not train external models on inputs. A community Python wrapper exists (taugroup/TAMU-Chat-AI), and the docs are at docs.tamus.ai.
- **Evaluation methodology is well established.**
  - Zheng et al. (2023, arXiv:2306.05685) found that strong LLM judges reach over 80% agreement with human preferences, about the same rate at which humans agree with each other.
  - Best practices for LLM judges: randomize answer position, normalize for length, use explicit rubrics, and calibrate against a small human-graded set.
  - Two policy studies use blind expert evaluation of AI versus human outputs. Nzobonimpa et al. (AI & Society, 2025) compared AI and human briefing notes across ten dimensions. Safaei & Longo (DGOV, 2023) found AI briefings useful as a supplement but not sufficient on their own.
- **RAG works for local government, with caveats.** A 2024 Springer study of a local-government RAG system found officers matched manual accuracy (93.3% correct) while cutting working time by 23.6%. Known failure modes: weak retrieval precision and recall, hallucination, and regressions when moving to a new domain, which stay invisible without a per-domain evaluation set.
- **Some deliverables are LLM-reproducible and some are not.**
  - Reproducible with public data: RFP/RFQ narratives, peer-city benchmarking, citizen-survey analysis, grant and CDBG narratives, fee and rate memos.
  - Not reproducible: field-work engineering and PE-stamped work.
  - Impact fee studies are mixed: the narrative is reproducible, but the engineering capital-improvement inputs are not.

## Shared Technical Architecture
- **Models:** the TAMU AI Chat API through tokens, not the web UI. Send heavy reasoning to a frontier model and use a cheaper model for extraction and drafting.
- **Retrieval:** ingest public city corpora into a vector store. Chunk documents hierarchically and combine dense and keyword retrieval. Keep a per-source evaluation set to catch regressions.
- **Orchestration:** plan, retrieve, draft, self-check against the rubric, then cite. Every claim must map to a retrieved chunk.
- **Evaluation harness (the differentiator):**
  - A fixed rubric covering analysis, coverage, grounding, actionability, presentation, and scope compliance.
  - An LLM judge with randomized answer positions and length normalization, calibrated against grades from city staff or faculty.
  - A blind A/B comparison against the real consultant deliverable.
  - Token cost per deliverable compared against the consultant fee.

## Option A: RFP/RFQ Response Generator + Consultant-Spend Expertise Network (RECOMMENDED)
- **Pitch:** Mine Open Checkbook and the check registers to map which firms the city pays, in which service categories, and how much. Then pick 2-3 recurring, narrative-heavy solicitations. Have the tool generate a consulting-style response for each and compare it against the awarded proposal or the actual deliverable. This covers everything the kickoff asked for: the consultant budget, the expertise network, RFP responses written the way a firm would, and the side-by-side comparison.
- **Deliverables targeted:** RFP/RFQ narrative responses (qualifications, approach, work plan, team narrative) and a consultant-spend analytics report.
- **Data:** Open Checkbook and check registers, Ionwave closed-bid datasets, intent-to-award items in council agendas, posted consultant deliverables, and the FY2026 budget.
- **Architecture:** the shared stack plus a pandas pipeline that sorts vendors into service lines and ranks their spend. Retrieval runs over prior solicitations. Generation is held to each solicitation's evaluation criteria, like a compliance matrix.
- **Evaluation:** blind rubric grading of the AI response against the awarded proposal or the scope of work, plus token cost against contract value. RFP-automation vendors claim 70-90% time savings. Those are marketing figures, useful as context only.
- **Feasibility:** high. The spend map is a fall deliverable; RFP generation and evaluation happen in spring.
- **Risks and mitigations:**
  - Awarded proposals may not be public. Use scopes of work as the comparison target instead, or file public-information requests early.
  - Vendor categorization will be noisy. Use LLM-assisted classification with manual spot-checks.
  - The model may invent firm credentials. Template the factual firm and city data, and restrict the model to the methodology narrative.
- **Why it beats Team 1:** it is the only option that delivers both artifacts the city named, with a hard dollar comparison.

## Option B: Peer-City Benchmarking + Citizen-Survey Analysis Report Generator
- **Pitch:** Reproduce the analytical reports the city buys. ETC's 2025 survey (margin of error +/- 4.8% at 95% confidence) rated College Station significantly above national benchmarks in 21 of 23 areas and above state benchmarks in 22 of 23. 84% of residents rated the city excellent or good as a place to live. The rec center study benchmarked College Station against other university towns and found it had fewer recreation facilities than those peers.
- **Deliverables targeted:** survey analysis, peer benchmarking, and the analytical sections of feasibility studies.
- **Data:** current and prior survey results, the rec center study, peer-city budgets, ACS/Census data, and the CSTX Open Data portal.
- **Architecture:** the shared stack plus statistical summarization, chart generation, and structured comparison tables.
- **Evaluation:** blind grading against the ETC and feasibility deliverables, plus numeric verification of every statistic. The $180,768 study fee serves as the cost anchor.
- **Feasibility:** medium-high. The main constraint is that raw survey microdata may not be public; the published cross-tabs are the fallback.
- **Risks:** interpretation can be reproduced, but survey weighting cannot. Peer-data availability varies. Every statistic needs verification.
- **Why it beats Team 1:** the strongest quantitative rigor and visual polish of the three.

## Option C: Grant / CDBG Narrative + Policy-Memo Drafting Assistant
- **Pitch:** Draft the HUD CDBG Consolidated Plan, Annual Action Plan, and CAPER narratives plus council policy memos, then compare them against the adopted versions.
- **Data:** the 2020-2024 Consolidated Plan and Annual Action Plans, CDBG allocations (FY2021 $1,219,430; FY2022 $1,181,121), HUD templates, and ACS data.
- **Architecture:** retrieval over HUD rules and prior plans, generation constrained to the template sections, and a compliance self-check.
- **Evaluation:** blind rubric grading against the adopted plans, a HUD compliance checklist, and a staff-time cost comparison.
- **Feasibility:** high. Everything is public and heavily templated.
- **Risks:** much CDBG work is done by staff, not outside consultants, which weakens the "reduce consultant reliance" framing. Compliance errors carry real stakes, so keep a human in the loop.
- **Why it beats Team 1:** the earliest working pipeline and the cleanest ground truth.

## Cost Framing
The anchors:
- Rec center study: $180,768
- Typical municipal water rate study: about $55,000
- Comparable Texas impact fee study: $118,000

Token cost per deliverable will be a few dollars to low tens of dollars, so the cost gap is obvious. The real question the evaluation has to answer honestly is the quality gap.

## Recommendation and Plan
**Pick Option A.**

1. **Weeks 1-4:** lock scope; pull Open Checkbook and register data; collect 3-5 ground-truth deliverable or proposal pairs; set up API access.
   - Go/no-go: with fewer than 3 usable pairs, compare against scopes of work instead, or switch to Option C.
2. **Weeks 5-10:** build the spend-map analytics and the first RFP pipeline. Design the rubric and harness before mass generation.
3. **Fall / City Hall:** present the spend map plus one worked comparison.
4. **Spring:** scale to 2-3 comparisons, run calibrated blind grading, and present the quality and cost gaps to Council.

## Caveats
- Confirmed contract amounts: the rec center study, Well 9, and the Freese and Nichols amendment. Amounts for the ETC survey, the comprehensive plan, the roadway impact fee study, and Raftelis were not found; they need agenda packets or Open Checkbook.
- The $55K and $118K study figures come from other cities. Treat them as benchmarks.
- RFP-automation savings figures are vendor claims.
- LLM judges have known biases toward verbosity, their own outputs, and answer position. Do not treat judge scores as ground truth.
- The biggest execution risk is whether awarded proposals and survey microdata are actually available. Confirm this in month one.
- Warrants and emergency-call data are excluded, as the kickoff specified.

## Sources
- College Station Impact Fees: https://www.cstx.gov/business-development/engineering/impact-fees/
- College Station Contracts and Procurement: https://www.cstx.gov/your-government/budget-and-finance/financial-transparency/contracts-and-procurement/
- CSTX Open Data: https://data.cstx.gov/
- WTAW Council Recap 07/23/2026: https://wtaw.com/college-station-city-council-meeting-recap-07-23-2026/
- TAMU AI Chat (BETA): https://www.it.tamu.edu/services/services-by-category/communication-and-collaboration/tamu-ai-chat.html
- TAMU AI Chat, Student Affairs IT: https://dsait.tamu.edu/news/2026/08/31/tamu-ai-chat/
- TAMU-Chat-AI wrapper: https://github.com/taugroup/TAMU-Chat-AI
- 2020-2024 Consolidated Plan: https://www.cstx.gov/media/mmtdib4f/2020-2024-consolidated-plan.pdf
- Annual Action Plan notice: https://www.cstx.gov/media/gl5l3osv/annual-action-plan-public-notice-english.pdf
- Westlake impact fee study (Community Impact): https://communityimpact.com/dallas-fort-worth/keller-roanoke-northeast-fort-worth/government/2024/10/22/freese-and-nichols-to-conduct-impact-fee-study-for-westlake/
- RAGAL (government RAG): https://arxiv.org/html/2607.18756v1
- Zheng et al., Judging LLM-as-a-Judge: https://arxiv.org/abs/2306.05685
