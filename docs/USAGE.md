# Setup and usage guide

A local service-barter simulation with explicit proposals, LLM or rule-based decisions,
optional pair-specific RAG, market forecasting, and optional blockchain audit records.
This is the existing prototype repaired for correctness and repeatable experiments.
The FastAPI/LangGraph production rebuild is a separate future project.

## Run locally

Tested on Python 3.12 and macOS arm64. Use the new `.venv`, not the copied `venv`.

```bash
source .venv/bin/activate
make run
```

For a new checkout:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
make test
make run
```

Choose **Deterministic baseline** in the sidebar for an offline demonstration.
Leave RAG, Prophet, and Ganache unchecked initially. It requires no model downloads
or blockchain service. This baseline accepts valid need-fulfilling proposals and is
a mechanics check, not evidence of agent intelligence.

For all optional features and the exact macOS test environment:

```bash
.venv/bin/python -m pip install -r requirements-lock.txt
```

The smaller `requirements-optional.txt` installs runtime features; the full lock
also contains the in-memory blockchain testing backend. The lock is a snapshot
tested on this platform, not a promise that all wheels exist for older operating systems.
Do not copy virtual environments between folders or machines; recreate them.

## Ollama

Start Ollama, install Mistral if necessary, then choose **Ollama / Mistral**:

```bash
ollama serve
# In another terminal:
ollama pull mistral
```

The adapter uses Ollama's local HTTP API and schema-constrained JSON output directly.
The old unused/deprecated LangChain and OpenAI wrappers were removed, so the core
simulation can import without loading models. To override the defaults, set
`OLLAMA_URL` or `OLLAMA_MODEL` in the shell before starting Streamlit.
Model calls use temperature 0, a seed, bounded timeouts, and one JSON-format repair.
Network/model errors are reported and never interpreted as consent.

Reference: [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs).

## What an agreement means

1. The engine constructs immutable transfer terms and a unique proposal ID.
2. Each participant accepts, rejects, or (for bilateral exchanges) submits a structured counteroffer. A valid counteroffer gets a new proposal ID and requires fresh approval from both participants.
3. Every outgoing amount is checked against starting inventory; every incoming amount
   is checked against remaining demand. Quantities must be positive integers.
4. Only unanimous, current approvals allow execution. Every new inventory/need/history
   state is prepared before any participant is changed.
5. Executed proposal IDs cannot be executed again.

Initial offers are engine-generated. LLMs can change bilateral terms through validated
structured counteroffers; free-form prose never controls transfers. Counteroffers count
toward the proposal limit. Rejection can lead to another proposal in a later round.
The optional tolerance policy applies to the accepting agent's incoming quantities
and does not bypass other participants' approval.

Directed cycles are deduplicated by rotation only. Previous bilateral approvals
never authorise additional cycle transfers. All cycle participants approve the complete
new transfer set. This is a single-process simulation; it is not a concurrent exchange
or real asset settlement service.

## Market and memory

Each UI session owns a market instance shared by its agents.
Prophet on/off switches forecasting, not all market information:
off uses the existing recent-price trend fallback. Forecast results are cached by
resource, horizon, history fingerprint, and mode. Market randomness uses a local seed.

RAG retrieves previous pair-specific exchange summaries into the decision prompt and
stores executed/rejected outcomes. The embedding model loads lazily and is shared
within the process. Pair memory is bounded and lives in the session; resetting agents
clears it. It is not a durable vector database. The first real memory operation may
download the public `all-MiniLM-L6-v2` model. Retrieved text is labelled untrusted data.

Reference: [Sentence Transformers encoding](https://www.sbert.net/docs/package_reference/sentence_transformer/model.html).

## Blockchain recording

Ganache is optional, normally at `http://127.0.0.1:7545`; override with `GANACHE_URL`.
The compiled `blockchain/TradeRecord.json` is included. To rebuild it:

```bash
.venv/bin/python -m blockchain.compile_contract --install
```

Each new trade gets one audit contract storing the full transfer set and simulated
approvals, including all cycle participants. The contract also stores a payload hash.
These are simulated agent approvals, not authenticated wallet signatures. The contract
records an agreement; it does not enforce service delivery or settle assets.

Trade execution, local persistence, and blockchain recording have separate statuses.
A deployment failure leaves the executed trade visible with `blockchain_status=failed`;
it never repeats the transfers. Retrying a timed-out deployment automatically is
deliberately unsupported because submission may already have succeeded.

Legacy `TradeAgreement.sol/json` and historical records remain readable.
New records are persisted once by the protocol; the UI no longer duplicates them.

## Measurements and experiments

Needs are outstanding demand, separate from initial transferable inventory.
Utility means demand fulfilled: initial need minus remaining need.
It is measured in resource units, not money, and assumes units are comparable.
It is not price-weighted economic utility. Receiving units fulfills demand even if
those units are later transferred onward.

Run metrics use executed transactions and structured events, not phrases:
agreement rate, bilateral/loop counts, transferred units, fulfillment gain,
normalized fulfillment, fairness of gains, proposal rounds, decision messages,
errors, and recording failures. Runs do not share a global metrics accumulator.
An all-zero fulfillment outcome is not labelled perfect fairness.

```bash
make benchmark
.venv/bin/python -m experiments.benchmark --runs 10 --seed 42 --output experiments/results/baseline.json
.venv/bin/python -m experiments.benchmark --engine ollama --memory --runs 10
.venv/bin/python -m experiments.benchmark --engine ollama --prophet --runs 10
.venv/bin/python -m experiments.loop_metrics_analysis
```

Scenarios use fixed dates, paired seeds, fresh inventories, and a separate warm-up
episode. RAG conditions retain that episode's memory for the measured episode.
Timing separates warm-up from measured negotiation; allocation measurements cover
Python allocations only, not full native-model RAM. Raw per-run JSON and mean/sample
standard deviation are saved. The model/runtime version can still change LLM output;
a seed does not guarantee deterministic model responses.

The rule baseline cannot establish RAG benefit. The tests establish functionality,
not that RAG/Prophet/aggressive styles necessarily improve outcomes. Historical charts
under `experiments/figures` predate the repairs and must not be treated as validated
results; new output goes under `experiments/results`.

## Tests

```bash
make test
make test-all
make test-coverage
# Optional explicit live checks:
EMBEDDINGS_OK=1 .venv/bin/python -m pytest -m embeddings
OLLAMA_OK=1 .venv/bin/python -m pytest -m llm
GANACHE_OK=1 make test-ganache
```

Core tests cover exact consent, stale/replayed approvals, invalid quantities,
resource conservation, cycle direction, utility, logging, cache invalidation,
memory prompt integration, experiments, and Streamlit reruns. Optional tests exercise
real FAISS/Prophet, real embeddings, and a local in-memory EVM. Live Ganache tests deploy
a contract and require the explicit environment opt-in above.

## Files

- `agents/base_agent.py`: agent state, prompt, local decision clients
- `negotiation/trades.py`: immutable terms, validation, execution
- `negotiation/protocol.py`: approvals, runs, recording coordination
- `negotiation/loop_trader.py`: directed cycles
- `negotiation/rag_memory.py`: bounded pair memory
- `market/service.py`: shared session market and cached forecasts
- `metrics/evaluation.py`: isolated run metrics
- `blockchain/`: new audit contract plus legacy compatibility
- `ui_app.py`: Streamlit controls and rendering
- `tests/`: regression and optional integration tests

Resource files are resolved relative to the checkout, not the terminal directory.
Generated caches/logs are ignored. Existing generated files were removed from Git's
index only; the local files and earlier Git history are preserved.
JSON storage is atomically replaced under a process-local lock; concurrent writers
from separate processes are not supported.

[Back to the project README](../README.md)

## Agent conversation view

The Agent conversations panel displays offers, replies, and counteroffers in chat bubbles.
Offer quantities come directly from the structured proposal; reply wording comes from
the selected decision provider. Technical log contains raw proposal IDs, JSON, and errors.
Conversations appear after the run finishes; replies are not streamed word by word.

After updating the application, refresh the page and reset inventories and memory to
load the new prompt. Select Ollama and disable automatic acceptance to let the model
respond to each proposal. Keep Ollama running with the configured model installed.
The deterministic baseline and tolerance policy use fixed replies instead of model-generated dialogue.

## Switching model providers

Choose Ollama / Mistral, OpenAI / GPT, or Deterministic baseline in the sidebar.
Both model providers have an editable model name. OpenAI defaults to gpt-5, matching
the original prototype's commented configuration; availability depends on your API account.
Enter an API key in the masked sidebar field or set OPENAI_API_KEY before launching.
The app keeps entered keys in session memory, not in conversation logs or project files.
Changing provider/model resets inventories and memory. OpenAI uses strict structured
responses and the same local trade validation. No new Python dependency is required.
Reference: https://developers.openai.com/api/docs/guides/structured-outputs

To run Ganache without the desktop application, use a separate terminal:

```bash
npx --yes ganache@7.9.2 --server.host 127.0.0.1 --server.port 7545 --database.dbPath "$HOME/.ganache-negotiation"
```

Keep this terminal running, then enable recording on Ganache in the app. The database
path preserves the local chain between launches. This is a local test chain.
