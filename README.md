# LLM4AD NBN Visualization

An English-first web interface for exploring LLM4AD experiment workspaces, NBN (Nearest-Better Network) search landscapes, and 3D MDS semantic spaces.

The UI is translated at render time. Existing experiment records and API payloads are left unchanged, so an English UI can be used with research data originally produced in Chinese.

## Included

- Workspace and revision browser
- Job monitoring and graph-artifact views
- Interactive 3D NBN and MDS visualizations
- A read-only bundled demo snapshot
- English-first browser localization in `visual_platform/static/i18n-en.js`
- Research History: linked prompts, selected programs/NBN nodes, generated source, evaluation outcomes, configuration changes, and JSON export

Local databases, embedding caches, credentials, and model weights are intentionally excluded. Selected frozen research records and verification evidence are preserved under `research/`.

The current history-tracking implementation and verification status is documented in [History tracking readiness — 2026-10-31](research/circle_packing_prompt_study_20261026/history_tracking_readiness_20261031/HISTORY_TRACKING_READINESS.md). Open the bundled `research_history_review.html` directly in a browser to inspect the saved real-study history without a server connection.

## Quick start

Use Python 3.10 or later in a virtual environment.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
python -m visual_platform.app
```

Open `http://127.0.0.1:5000` in a browser. The application binds to the loopback address by default because some experiment endpoints execute submitted code. Do not expose it publicly without authentication and a reverse proxy.

To use another port:

```bash
VP_PORT=5001 python -m visual_platform.app
```

On Windows PowerShell:

```powershell
$env:VP_PORT = '5001'
python -m visual_platform.app
```

## Data and models

The visualizer writes local data under `visual_platform/.local/` by default. Set `VISUAL_PLATFORM_LOCAL_DATA_DIR` to keep runtime data elsewhere. Some semantic-space features require a locally available CodeT5 embedding model; model weights are not included in this repository.

## License

See [LICENSE](LICENSE) and [NOTICE](NOTICE).
