# Process Investigation Copilot - Plan Checklist

## Guiding Statement

**Current goal:** evolve from a strong DFG app into an investigation copilot MVP that can answer a concrete question with period comparison, abnormal-vs-normal comparison, and grounded explanation.

---

## 1. MoSCoW Priorities

| Priority | Item | Description | Current status |
|---|---|---|---|
| **Must** | CSV upload + column mapping | Map `case_id`, `activity`, `timestamp` | Done |
| **Must** | Data validation | Missing values, timestamp parsing, duplicates, case/activity count, date range | Done |
| **Must** | Basic process metrics | Total case count, activity count, variant summary, case duration | Done |
| **Must** | Slow-case detection | Top 10% duration-based abnormal group | Done |
| **Must** | Slow vs normal comparison | Compare activity, rework, variants | Done |
| **Must** | Representative scenario | End-to-end flow for "Why did processing time increase this month?" | Partially done |
| **Must** | Period comparison | Recent period vs previous period duration comparison | Done |
| **Must** | Activity-level delay analysis | Identify which step got slower | Done |
| **Must** | Grounded explanation block | Observation / Evidence / Interpretation / Limitations | Partially done |
| **Must** | Evidence display | Tables, charts, suspicious-factor style signals | Partially done |
| **Must** | Investigation panel | Question input, suggested questions, answer area, evidence area | Partially done |
| **Must** | Deterministic analysis-first structure | Python for computation, explanation layered on top | Done |
| **Must** | README alignment | Problem, solution, features, architecture, limitations | Done |
| **Should** | Suspicious factor ranking | Rank likely drivers of delay | Partially done |
| **Should** | Follow-up question suggestions | Suggest next analysis questions | Partially done |
| **Should** | Process View (DFG) | all / slow / non-slow / majority / variant subsets | Done |
| **Should** | Bottleneck mode | Transition-time-based emphasis | Done |
| **Should** | Process View UX polish | Better subset/mode explanations and readability | Done |
| **Should** | Trend / bottleneck / variant routing | Route question types to analysis functions | Partially done |
| **Should** | Trace / analysis steps | Show functions/subsets/evidence used | Partially done |
| **Should** | Known limitations | Explicitly state what cannot be concluded | Partially done |
| **Should** | Sample dataset explanation | Explain what the synthetic or sample data contains | Not done |
| **Could** | Process View summary cards | Top transition, slowest transition, bottleneck candidate | Done |
| **Could** | Resource / department analysis | Use optional attributes when present | Not done |
| **Could** | Question templates | Preset investigation questions | Partially done |
| **Could** | Evaluation script | Benchmark questions, groundedness, unsupported claims | Not done |
| **Could** | Latency measurement | Measure response time per question | Not done |
| **Could** | Demo GIF / screenshots | Assets for GitHub and presentation | Not done |
| **Should** | PDF report export | Curated business-readable export for current analysis | Done |
| **Won't (for now)** | Multi-agent | Complex agent orchestration | Excluded |
| **Won't (for now)** | Fancy auth | Authentication / user management | Excluded |
| **Won't (for now)** | Real-time ingestion | Streaming data | Excluded |
| **Won't (for now)** | Full process mining engine | Full discovery + conformance suite | Excluded |
| **Won't (for now)** | BPMN / Petri net full support | Full automatic modeling support | Excluded |
| **Won't (for now)** | Interactive graph refactor now | Full zoom/pan renderer replacement | Deferred |
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
- [ ] Final structured "why slower?" narrative lock

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
- [x] Structured result payload (initial)
- [x] Answer area with grounded blocks
- [x] Evidence display blocks/tables
- [x] Follow-up question suggestions (initial)
- [ ] Finalized question-input UX
- [ ] Finalized trace transparency UX

### F. Grounded explanation layer
- [x] Observation block
- [x] Evidence block
- [x] Interpretation block
- [x] Limitation / uncertainty block
- [x] Explicit unsupported-case handling
- [ ] Unsupported-claim prevention hardening

### G. Report export
- [x] Single user-facing report export action
- [x] Curated report assembly logic
- [x] Business-readable section formatting
- [x] Process snapshot visual (DFG-style compact rendering)
- [x] Next-steps section
- [ ] Optional deeper branding/template pass

### H. Productization
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
- Data foundation and persistence
- Core case/slow-case analysis backbone
- Period comparison and activity-delay analysis
- Process-aware visualization (DFG + subsets + bottleneck mode)
- Curated PDF report export

### Areas still significantly incomplete
- Fully complete representative investigation scenario end-to-end UX
- Final investigation panel polish (trace + interaction flow)
- Evaluation and benchmarking package
- Optional-attribute analysis (`resource`, `department`, `cost`)

---

## 4. Most Recent Work (2026-03-09)

Completed today:
1. Simplified report export UX to one clear user action (single report mode).
2. Implemented and polished curated PDF report output:
   - cover + executive summary + data readiness + performance summary + delay drivers + process snapshot + investigation + next steps
   - consistent number formatting and business-readable copy
   - compact DFG-style process snapshot visual in report
   - conditional section inclusion to avoid empty report sections
3. Added persistent active-dataset restoration across refresh with user feedback.
4. Applied broad UI consistency polish across Home/Upload/Dashboard/Process View/Investigation.

---

## 5. Priority Reminder

### Most important next Must items
1. Fully lock the representative flow for "Why did processing time increase this month?"
2. Finalize investigation panel interaction quality (input, trace clarity, evidence hierarchy)
3. Tighten unsupported-claim prevention and explicit uncertainty handling
4. Add lightweight evaluation coverage for groundedness and failure modes

### Next Should items
1. Suspicious factor ranking refinement
2. Follow-up suggestion quality improvement
3. Sample dataset explanation and demo assets

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
