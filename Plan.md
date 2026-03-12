# Process Investigation Copilot - Plan Checklist

## Guiding Statement

**Current goal:** turn the current Streamlit process-mining MVP into a reliable investigation copilot for the benchmark question:

> "Why did processing time increase this month?"

The product should stay deterministic-analysis-first, surface evidence clearly, and avoid unsupported root-cause claims.

---

## 1. MoSCoW Priorities

| Priority | Item | Description | Current status |
|---|---|---|---|
| **Must** | CSV upload + column mapping | Map `case_id`, `activity`, `timestamp` | Done |
| **Must** | Data validation | Missing values, timestamp parsing, duplicates, case/activity count, date range | Done |
| **Must** | Basic process metrics | Total case count, activity count, variant summary, case duration | Done |
| **Must** | Slow-case detection | Top 10% duration-based abnormal group | Done |
| **Must** | Slow vs normal comparison | Compare activity, rework, variants | Done |
| **Must** | Representative benchmark scenario | End-to-end flow for "Why did processing time increase this month?" | Partially done |
| **Must** | Period comparison | Recent period vs previous period duration comparison | Done |
| **Must** | Activity-level delay analysis | Identify which step got slower | Done |
| **Must** | Grounded explanation block | Observation / Evidence / Interpretation / Limitations | Partially done |
| **Must** | Evidence display | Tables, charts, suspicious-factor style signals | Partially done |
| **Must** | Investigation panel | Question input, suggested questions, answer area, evidence area | Partially done |
| **Must** | Deterministic analysis-first structure | Python for computation, explanation layered on top | Done |
| **Must** | README alignment | Problem, solution, features, architecture, limitations | Partially done |
| **Should** | Investigation Answer Composer | Unified answer payload between analysis and UI | Done |
| **Should** | Contradiction handling | Correct false benchmark premises (increase vs decrease/stable) | Done |
| **Should** | Unsupported-claim guardrails | Cautious, limitation-aware wording | Partially done |
| **Should** | Follow-up question suggestions | Suggest next investigation questions from current evidence | Partially done |
| **Should** | Trace / analysis steps | Show analyses, subsets, metrics, evidence path | Partially done |
| **Should** | Suspicious factor ranking | Rank likely drivers of delay | Partially done |
| **Should** | Process View (DFG) | all / slow / non-slow / majority / variant subsets | Done |
| **Should** | Bottleneck mode | Transition-time-based emphasis | Done |
| **Should** | Process View UX polish | Better subset/mode explanations and readability | Done |
| **Should** | Known limitations | Explicitly state what cannot be concluded | Partially done |
| **Should** | PDF report export | Curated business-readable export for current analysis | Partially done |
| **Should** | Report model / markdown-first migration | Payloads -> unified report model -> markdown -> PDF path | Partially done |
| **Should** | Sample dataset explanation | Explain what the sample data contains | Not done |
| **Could** | Process View summary cards | Top transition, slowest transition, bottleneck candidate | Done |
| **Could** | Question templates | Preset investigation questions | Partially done |
| **Could** | Resource / department analysis | Use optional attributes when present | Not done |
| **Could** | Evaluation script | Benchmark questions, groundedness, unsupported claims | Not done |
| **Could** | Latency measurement | Measure response time per question | Not done |
| **Could** | Demo GIF / screenshots | Assets for GitHub and presentation | Not done |
| **Won't (for now)** | Multi-agent | Complex agent orchestration | Excluded |
| **Won't (for now)** | Fancy auth | Authentication / user management | Excluded |
| **Won't (for now)** | Real-time ingestion | Streaming data | Excluded |
| **Won't (for now)** | Full process mining engine | Full discovery + conformance suite | Excluded |
| **Won't (for now)** | BPMN / Petri net full support | Full automatic modeling support | Excluded |
| **Won't (for now)** | Interactive graph renderer replacement | Full zoom/pan renderer replacement | Deferred |
| **Won't (for now)** | Autonomous root-cause claims | Overconfident auto-diagnosis | Excluded |

---

## 2. Execution Checklist

### A. Data foundation
- [x] CSV upload
- [x] Column mapping
- [x] Validation report
- [x] Blocking errors / warnings split
- [x] Timestamp parsing quality
- [x] Dataset profile display
- [x] Active dataset restore after refresh
- [ ] Event-count outlier checks per case
- [ ] Optional-column readiness (`resource`, `department`, `cost`)

### B. Core metrics and dashboard
- [x] Case duration computation
- [x] Event count / unique activity count
- [x] Rework metric
- [x] Top activities
- [x] Top variants (basic)
- [x] Period-based processing-time comparison (recent vs previous)
- [x] Delay-signal summary cards
- [ ] Full trend analysis beyond two-window comparison

### C. Slow-case investigation
- [x] Slow-case definition
- [x] Slow vs non-slow comparison
- [x] Variant comparison
- [x] Rework comparison
- [x] Activity-level time-difference comparison
- [ ] Recent vs previous slow-case comparison
- [ ] Final suspicious factor ranking refinement
- [ ] Final structured benchmark narrative lock

### D. Process View
- [x] DFG generation
- [x] all / slow / non-slow
- [x] majority_cases
- [x] top_variant / top_3 / top_5
- [x] Top-to-bottom layout
- [x] Bottleneck mode
- [x] Density-aware rendering
- [x] Process View summary cards
- [x] Subset explanation polish
- [x] Bottleneck interpretation guidance polish

### E. Investigation panel
- [x] Suggested question entry points
- [x] Question classification and routing (initial)
- [x] Unified answer payload
- [x] Investigation Answer Composer integration
- [x] Benchmark question contradiction handling
- [x] Answer area with grounded sections
- [x] Evidence display blocks/tables
- [x] Follow-up question suggestions (rule-based)
- [x] Readable trace summary (analyses / subsets / metrics)
- [ ] Finalized question-input UX
- [ ] Finalized trace transparency UX
- [ ] Final benchmark answer wording/ranking pass

### F. Grounded explanation layer
- [x] Observation block
- [x] Evidence block
- [x] Interpretation block
- [x] Limitation / uncertainty block
- [x] Explicit unsupported-case handling
- [x] Basic unsupported-claim guardrails in composer
- [ ] Broader unsupported-claim hardening across all question types

### G. Report export
- [x] Single user-facing report export action
- [x] Curated report assembly logic
- [x] Business-readable section formatting
- [x] Separate report-only process snapshot mode
- [x] Investigation answer + limitations restored in PDF
- [x] Initial report model / markdown renderer
- [ ] Final report completeness and section polish
- [ ] Final process snapshot / label readability polish
- [ ] PDF rendering driven primarily from unified report model

### H. Productization
- [x] Core analysis tests
- [x] Investigation answer composer tests
- [x] Report markdown pipeline test
- [ ] 20 benchmark questions
- [ ] Groundedness check script
- [ ] Unsupported-claim check script
- [ ] Latency measurement
- [ ] Known failure cases documentation
- [ ] Sample dataset explanation
- [ ] Demo screenshots / GIF

---

## 3. Current-State Summary

### Areas close to complete
- Data foundation and active-dataset persistence
- Core case / slow-case / period comparison analysis backbone
- Activity-delay analysis and grounded explanation scaffolding
- Process-aware visualization (DFG + subsets + bottleneck mode)
- Investigation Answer Composer and unified answer payload

### Areas improved but still rough
- Benchmark investigation answer quality and contradiction handling
- Trace transparency and follow-up question usefulness
- PDF report structure and report-only process snapshot
- Report-model / markdown-first export architecture

### Areas still significantly incomplete
- Final benchmark investigation UX polish end-to-end
- Final suspicious-factor ranking and narrative refinement
- Optional-attribute analysis (`resource`, `department`, `cost`)
- Evaluation / groundedness / failure-case package
- Final report completeness and business-facing polish

---

## 4. Most Recent Work (2026-03-12)

Completed today:
1. Added `InvestigationAnswerPayload` and `Investigation Answer Composer`.
2. Wired the Investigation panel to render from a unified payload instead of fragmented pieces.
3. Improved benchmark-question handling:
   - explicit overall-change classification
   - contradiction handling when the benchmark premise is false
   - more cautious unsupported-claim wording
4. Improved Investigation panel support features:
   - evidence-driven follow-up questions
   - readable trace transparency
5. Started report-architecture migration:
   - added typed report model
   - added report composer
   - added markdown renderer
   - kept existing ReportLab PDF export active
6. Iterated on report process snapshot rendering with a separate report-only snapshot mode.

---

## 5. Priority Reminder

### Most important next Must items
1. Fully lock the benchmark flow for "Why did processing time increase this month?"
2. Finalize Investigation panel interaction quality and answer hierarchy
3. Tighten unsupported-claim prevention beyond the benchmark route
4. Finish report completeness and process snapshot readability in the exported PDF

### Next Should items
1. Refine suspicious factor ranking and explanation wording
2. Continue report-model -> markdown -> PDF migration
3. Add lightweight evaluation coverage for groundedness and failure modes
4. Add sample dataset explanation and demo assets

### Intentionally deferred for now
1. Full graph renderer replacement
2. BPMN / Petri net support
3. Multi-agent system
4. Product features unrelated to the core scenario

---

## 6. Original MVP Reminder

### One-line MVP definition
A small web app where a user uploads an event-log CSV and asks:

> "Why did processing time increase this month?"

The system should:
- compute case performance metrics
- find slow cases
- compare against normal cases
- show activity-level differences
- generate a grounded explanation

### Core benchmark flow
1. Read uploaded event log
2. Compute case durations
3. Compare recent period vs previous period
4. Extract slow-case subset
5. Compare activity-level time / frequency / rework differences
6. Identify suspicious factors
7. Show grounded explanation with supporting evidence

This flow remains the main benchmark for MVP completeness.
