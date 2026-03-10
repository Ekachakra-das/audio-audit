# Audio Optimizer

Audio restoration and analysis tooling. The app combines a Svelte popup UI, a Node bridge server, and multiple Python workers for cleanup, comparison, duplicate checks, and batch export.

## Features
- Audio cleanup with `VoiceFixer`, `Resemble-Enhance`, `DeepFilter`, `Denoiser`, `Remove Echo`, and `LavaSR`
- Audio Enhancement Lab popup with preview, A/B comparison, and per-model controls
- Batch optimization with bitrate recommendations
- Duplicate detection across lecture folders
- Finder / Audacity / RX integration from the desktop workflow 

## Practical Recommendation

- Based on hands-on project usage, the `Resemble` pipeline has generally delivered the best results for noise reduction in recordings.

## Setup

### Frontend and bridge
```bash
npm install
cd lecture_analysis/ui
npm install
npm run build
cd ../..
```

### Python environments

Two Python environments are used because the model stacks have conflicting dependencies.

```bash
# Core environment: analysis, DeepFilter, Denoiser, VoiceFixer 1
python -m venv lecture_analysis/venv
source lecture_analysis/venv/bin/activate
pip install -r requirements.txt
deactivate

# Enhanced environment: Resemble, LavaSR, and lab tooling
python -m venv lecture_analysis/venv_vf2
source lecture_analysis/venv_vf2/bin/activate
pip install -r requirements_vf2.txt
deactivate
```

## Run

1. Start the main optimizer UI with `./audit.command`.
2. Start the Streamlit laboratory with `./lab.command`.
3. The static lecture report remains at `lecture_analysis/index.html`.

## Notes
- The bridge server is `lecture_analysis/bridge.js`.
- Audio routes are in `lecture_analysis/routes/audio.js`.
- `requirements.txt` is for the core environment.
- `requirements_vf2.txt` is for the enhanced environment, including `Resemble` and `LavaSR`.

## Platform Support

- This project is developed and tested on **macOS (MacBook)**.
- Some workflows are macOS-specific (AppleScript, Finder integration, desktop app launch commands).
- **Windows/Linux are not officially supported yet** and may require additional adaptation.

## Public Demo Mode (Deploy-safe UI)

Use a separate environment profile for deployed demo builds:

- Frontend env:
  - `VITE_DEMO_MODE=true`
  - `VITE_BRIDGE_BASE_URL=https://your-bridge-host` (optional; defaults to `http://localhost:3000`)
- Backend env (only if you deploy the bridge):
  - `DEMO_MODE=true`

When demo mode is enabled:
- UI shows a public demo banner.
- Processing and local machine actions are blocked in the frontend.
- Bridge endpoints for processing/local actions return `403` when `DEMO_MODE=true`.

Local workflow remains unchanged by default because both flags are `false` unless explicitly set.
