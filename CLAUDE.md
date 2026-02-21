# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Backend
```bash
cd backend
.venv/bin/python index.py         # Start server on port 8890
.venv/bin/pytest                   # Run all tests
.venv/bin/pytest tests/test_foo.py::test_bar  # Run single test
```

### Frontend
```bash
cd frontend
cp ../.env ./                      # Copy env vars
npm run dev                        # Dev server on port 8081
npm run build                      # Production build
npm run lint                       # Biome linter
```

### Environment
Both frontend and backend read from `.env` at the repo root. Copy it to `frontend/` for the dev server. Required vars: `LLM_ENDPOINT_ID`, `VLM_ENDPOINT_ID`, `T2V_ENDPOINT_ID`, `API_KEY`, `ARK_API_KEY`, `TOS_*`, `TTS_*`.

## Architecture

### Overview
Chat2Cartoon is a bilingual video generator that takes a user-provided topic and produces an animated story through a **12-phase sequential pipeline**. It supports two content modes: **children_story** (default) and **insurance_case**, selected on the homepage.

### Request Flow
1. Frontend sends `POST /api/v3/bots/chat/completions` with full conversation history and optional `metadata: { mode }`.
2. Backend (`index.py → main()`) inspects the last user message to determine `Mode` (CONFIRMATION or REGENERATION), then uses `PhaseFinder` to identify the next phase from conversation history.
3. `GeneratorFactory` maps the phase to a generator class and streams the response back via SSE.
4. Frontend state machine (XState, in `WatchAndChat/`) handles each streamed response and advances the UI.

### Phase Pipeline (`backend/app/generators/phases/`)
Phases run in order; each generator reads prior phase outputs from conversation history via `PhaseFinder`:

| Phase | Generator | What it does |
|---|---|---|
| Script, StoryBoard, RoleDescription | `InitiationGenerator` → routes to specific generator | LLM classifies user intent then generates content |
| RoleImage, FirstFrameImage | `RoleImageGenerator`, `FirstFrameImageGenerator` | Text-to-image API calls (parallel) |
| FirstFrameDescription, VideoDescription | Dedicated generators | LLM refines descriptions for image/video prompts |
| Video | `VideoGenerator` | Video generation API |
| Tone | `ToneGenerator` | LLM selects TTS voices per character |
| Audio | `AudioGenerator` | TTS synthesis |
| Film | `FilmGenerator` | MoviePy assembles final video with subtitles |
| FilmInteraction | `FilmInteractionGenerator` | VLM-based Q&A about the generated film |

### Multi-Mode System
- Mode is passed as `request.metadata["mode"]` from the frontend.
- Each phase generator reads `content_mode = request.metadata.get("mode", "")` in `__init__` and selects between the children story prompt (default, defined in the phase file) and the insurance case prompt (from `backend/app/generators/prompts/insurance_case.py`).
- Mode constants live in `backend/app/constants.py` (`MODE_CHILDREN_STORY`, `MODE_INSURANCE_CASE`) and `frontend/src/module/VideoGenerator/constants.ts` (`MODE_CONFIG`).
- Frontend attaches `metadata` in `ChatWindowV2/index.tsx → startReply()` via `assistant.Extra.Mode`.

### Message Protocol
- **Assistant messages** are prefixed: `phase=Script`, `phase=StoryBoard`, etc. `PhaseFinder` scans conversation history for these prefixes to reconstruct state.
- **User messages** for phase advancement: plain text (CONFIRMATION mode) or prefixed with `REGENERATION` + JSON payload (REGENERATION mode).
- REGENERATION messages carry a JSON blob with existing assets so only missing ones are re-generated.

### UI 细节

#### UserMessage 步骤标题
- 步骤标签文字：`frontend/src/module/VideoGenerator/components/UserMessage/index.tsx` 第 16 行的 `STEP_LABELS` 数组
- 圆形数字图标样式：`frontend/src/module/VideoGenerator/components/UserMessage/index.module.less` 的 `.stepIndex` 类
  - `width` / `height`：圆圈尺寸（当前 32px）
  - `font-size`：圆圈内数字大小（当前 18px）

### Frontend Structure
- `src/routes/page.tsx` — Homepage with mode selection cards; renders `VideoGenerator` with the chosen mode's config.
- `src/module/VideoGenerator/` — Main module; `store/RenderedMessages/provider.tsx` drives the phase-by-phase UI flow by calling `sendMessageImplicitly` / `startReply`.
- `src/components/ChatWindowV2/` — SSE streaming, message state management; `index.tsx` builds the request body including `metadata`.
- `src/module/WatchAndChat/` — XState machine for the film interaction (watch + chat) phase after video is generated.
- Dev proxy in `modern.config.ts`: `/api/v3/bots` → `http://localhost:8890`, `/api/v3/contents/generations/tasks` → Volcengine cloud.
