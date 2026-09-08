# Prototype maintenance — 8 September 2026

## Scope
Repairs were applied only to the selected "Agentic AI Negotiation System-Old" copy.
The original dissertation folder was not edited. No commits or pushes were made.
The future FastAPI/LangGraph rebuild is not included.

## Changes
- Conversation logging accepts session paths, uses unique filenames, and writes atomically.
- Agent prompts render readable market context. Exact speaker-prefix removal replaces lstrip.
- Agents share their UI session's market. Prophet switches work; cached forecasts invalidate
  on history or mode changes. Simulation randomness is seeded without changing global RNG state.
- Immutable proposals hold explicit IDs and full transfers. Structured agent approvals are tied
  to the same ID. Prose is never treated as consent. Model format repair is bounded.
- Positive integer quantities, available inventory, remaining needs, duplicate transfers and
  aggregate outgoing amounts are validated before changing any agent. Replays are rejected.
- Directed cycles retain real edge directions and require fresh unanimous cycle approval.
- Auto-accepted and normal bilateral trades, plus complete cycles, all produce records.
- Demand fulfillment replaces the old remaining-needs/inventory utility formula.
  Metrics use structured events and are isolated per run/session.
- RAG is connected to decisions and outcomes. Shared embedding models load lazily; pair
  memory remains session-local and bounded.
- Optional blockchain audit contracts store all transfers and simulated approvals.
  Deployment failures remain distinct from successful off-chain execution.
  Legacy artifacts and records remain readable.
- UI supports offline baseline, LLM mode, optional features, inventory/memory reset,
  current/history records, explicit on-chain verification and stable reruns.
- Experiments use paired seeds, fresh inventories, separate warm-up and saved raw metrics.
  Baseline results do not demonstrate RAG or forecasting quality.
- Fresh .venv, pinned dependency sets, full tested lock, repaired Make targets, portable
  resource paths, setup README and regression tests are included.
- 32 generated files were removed from Git's index only. Local files and old Git history
  are preserved. These removals are staged; source changes are not committed.

## Verification
- Project .venv: Python 3.12.11, macOS arm64.
- Final full regression run: **55 passed, 2 skipped**.
- Real Prophet forecasting: passed.
- FAISS with deterministic embeddings: passed.
- Real all-MiniLM-L6-v2 retrieval and shared model identity: passed.
- In-memory EVM complete-cycle contract deployment/readback: passed.
- Streamlit baseline run and rerun without duplicate execution/persistence: passed.
- Ten seeded baseline runs: completed; mean 2 executed agreements and 16 fulfilled
  units per measured two-agent scenario. This is a mechanical baseline, not model quality.
- Dependency consistency: pip check passed.
- Syntax: all 38 Python source/test files parsed.
- Git whitespace checks: passed.
- Measured statement coverage across agents, negotiation, market, metrics, utils and
  blockchain: 71%; includes retained legacy helpers not exercised by the main application.
  Core transfer validation/execution: 93%; metrics: 100%.

## Remaining live checks and limits
- Ollama/Mistral test skipped: local Ollama was not running (connection refused).
- Live Ganache test skipped: no live deployment was requested during validation; the
  contract was instead tested on the in-memory EVM.
- Real embeddings were downloaded into a temporary test cache. The application may
  download the model into its normal cache on first RAG use.
- No claims that RAG, Prophet or any personality improves outcomes are established.
  Run controlled LLM experiments after starting Ollama.
- The contract is an audit record, not real asset settlement or wallet-signed consent.
- The simulator is sequential; multi-process inventory transactions and file writers
  are outside this prototype's scope.
- Historical figures are retained for provenance and are not validated results.

See [README.md](README.md) for the project overview and [the usage guide](docs/USAGE.md) for setup, feature behavior and commands.

## Conversational UI follow-up

- Restored agent chat bubbles and moved raw protocol details into a separate technical log.
- Added natural-language reply prompts and validated bilateral counteroffers with fresh proposal IDs and unanimous approval.
- Kept multilateral exchanges on explicit accept/reject decisions.
- No additional tests or live runs were performed for this follow-up, as requested. Earlier validation results above predate these changes.

## Negotiation refinements

Rejected proposals where a participant gives and receives the same resource, and filtered
such cycles before proposing them. Response schemas now restrict loops to accept/reject;
repair prompts include validation errors and bilateral counteroffers are checked during
the repair step. Prompts include each agent's own incoming/outgoing terms and ask for
a concrete reason. Dialogue remains model-generated and is not a verified explanation.
Run controls explain continuation versus reset, and errors distinguish invalid responses
from provider failures. No additional live runs or regression suite were run.
