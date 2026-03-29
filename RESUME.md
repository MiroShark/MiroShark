# miro_shark - Resume

## Project Timeline
- Mar 25: Project initialized, MiroShark cloned and running locally (G1 complete)
- Mar 26: Added URL input, fixed axios/CORS, audited codebase, designed Decision Lab
- Mar 27: Built Decision Lab foundation (G3), consequence engine (G4), autonomous optimizer (G5), topic research agent
- Mar 28: Built intent-guided research, AI-suggested prompts, nav tabs, 10-feature improvement plan (F1-F10), ran ER-100 gene therapy full pipeline
---

## Current Task
All major goals (G1-G5) and improvement features (F1-F10) complete. Ready for next direction.

## Blockers
None.

## Next Steps
- Mark G2 complete (G2.3-G2.5 were implemented as F3, F4, F8)
- Test ER-100 Decision Lab branches (were preparing last session)
- Decide next feature direction

## What's Been Built
- **Core platform**: Flask backend + Vue frontend + Neo4j + Ollama (qwen2.5:32b)
- **URL input**: Paste URLs instead of uploading files
- **Topic research agent**: Type a topic → LLM generates queries → DDG searches → fetches sources
- **Intent-guided research**: Gap analysis between content and user intent → targeted searches
- **AI-suggested prompts**: Auto-generate simulation requirements from context
- **Decision Lab**: Multi-branch parallel simulation with comparison + consequence trees
- **Consequence extractor**: 3-stage causal chain extraction (event graph → LLM scoring → tree)
- **Autonomous optimizer**: Autoresearch-inspired loop that proposes/tests/refines strategies overnight
- **Global toast system**: Error/success notifications visible to users
- **LLM retry**: Exponential backoff on all LLM calls
- **Health checks**: /health verifies Neo4j + Ollama connectivity
- **Async ontology**: Background task with polling (refresh-safe)
- **Export**: Download reports, graphs, and Decision Lab data as JSON
- **Branch retry**: Retry failed Decision Lab branches
- **Nav tabs**: Pipeline | Decision Lab tabs on project pages

## Commits (25+)
See `git log --oneline` for full history.
