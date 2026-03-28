# Feature Plan — MiroShark Improvements
<!-- Created 2026-03-28 -->

## Priority 1: Critical UX (must-have)

### F1: Global error toast system
Add a toast notification component that shows errors, successes, and warnings.
Currently errors are set but never rendered — users see red dots with no explanation.
- Files: NEW `components/Toast.vue`, MODIFY `App.vue`, MODIFY all views
- Estimate: 1 commit

### F2: Error display in all views
Render error.value as visible banners in MainView, SimulationView, ReportView.
- Files: MODIFY `MainView.vue`, `SimulationView.vue`, `ReportView.vue`
- Estimate: 1 commit

### F3: LLM retry with exponential backoff
Add retry decorator to llm_client.py — every LLM call currently crashes on transient errors.
- Files: MODIFY `backend/app/utils/llm_client.py`
- Estimate: 1 commit

### F4: Real health check endpoint
/health should check Neo4j + Ollama connectivity, not just return "ok".
- Files: MODIFY `backend/app/__init__.py`
- Estimate: 1 commit

## Priority 2: Export & Sharing

### F5: Report PDF/Markdown export
Add download buttons for simulation reports as PDF or Markdown files.
- Files: NEW `backend/app/api/export.py`, MODIFY `ReportView.vue`
- Estimate: 1 commit

### F6: Graph data export (JSON/CSV)
Export knowledge graph nodes and edges as downloadable JSON or CSV.
- Files: MODIFY `backend/app/api/graph.py`, MODIFY `Step1GraphBuild.vue`
- Estimate: 1 commit

### F7: Decision Lab results export
Export branch comparison and consequence trees as downloadable reports.
- Files: MODIFY `backend/app/api/decision_lab.py`, MODIFY `DecisionLabView.vue`
- Estimate: 1 commit

## Priority 3: Polish & Reliability

### F8: Async ontology generation (refresh-safe)
Make ontology generation a background task like graph build — currently blocks and loses data on refresh.
- Files: MODIFY `backend/app/api/graph.py`, MODIFY `MainView.vue`
- Estimate: 1 commit

### F9: Loading indicators for all operations
Add visible progress/spinner for ontology gen, graph build, profile generation.
- Files: MODIFY `MainView.vue`
- Estimate: 1 commit

### F10: Decision Lab branch retry
If a branch fails during preparation, allow retrying just that branch.
- Files: MODIFY `backend/app/services/decision_lab_manager.py`, MODIFY `DecisionLabView.vue`
- Estimate: 1 commit

## Execution Order
F1 → F2 → F3 → F4 → F5 → F6 → F7 → F8 → F9 → F10
