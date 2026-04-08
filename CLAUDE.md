# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### 服务管理（使用 supervisorctl）
```bash
sudo supervisorctl status                          # 查看所有服务状态
sudo supervisorctl restart chat2cartoon-backend    # 重启后端
sudo supervisorctl restart chat2cartoon-frontend   # 重启前端
sudo supervisorctl restart chat2cartoon-static     # 重启静态文件服务
sudo supervisorctl restart all                     # 重启所有服务
sudo supervisorctl stop chat2cartoon-backend       # 停止后端
sudo supervisorctl start chat2cartoon-backend      # 启动后端
```

日志文件：
- 后端：`/var/log/supervisor/chat2cartoon-backend.log`
- 前端：`/var/log/supervisor/chat2cartoon-frontend.log`
- 静态：`/var/log/supervisor/chat2cartoon-static.log`

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
Both frontend and backend read from `.env` at the repo root. Copy it to `frontend/` for the dev server. Required vars: `LLM_ENDPOINT_ID`, `VLM_ENDPOINT_ID`, `T2V_ENDPOINT_ID`, `CGT_ENDPOINT_ID`, `API_KEY`, `ARK_API_KEY`, `TOS_*`, `TTS_*`.

## Architecture

### Overview
Chat2Cartoon is a bilingual video generator that takes a user-provided topic and produces an animated story through a **12-phase sequential pipeline**. The homepage offers **6 content modes** selectable as cards.

### Content Modes
All mode constants are in `backend/app/constants.py` and `frontend/src/module/VideoGenerator/constants.ts`.

| Mode key | Name | Pipeline variant |
|---|---|---|
| `children_story` | 儿童故事 | Default (video + storybook film) |
| `insurance_case` | 保险案例 | Default with urban 3D art style, 2-storyboard limit |
| `story_narration` | 港险案例分镜制作 | No video: SkipVideo → StorybookFilmGenerator, 2-storyboard limit |
| `text_to_storyboard` | 原文分镜 | Same as story_narration, preserves original text verbatim, 30-storyboard limit |
| `text_to_video` | 原文视频 | Real video generation, preserves original text verbatim, 30-storyboard limit |
| `text_to_video` (IsRealistic=true) | 原文写实视频 | Same as text_to_video with realistic art style + optional reference image (image-to-image) |

The "原文写实视频" card on the homepage uses `backendMode = "text_to_video"` with `Extra.IsRealistic = true`. The frontend `VideoGenerateFlow` uses `assistantData?.Extra?.IsRealistic` to show the reference image upload UI.

### Request Flow
1. Frontend sends `POST /api/v3/bots/chat/completions` with full conversation history and `metadata: { mode, reference_image? }`.
2. Backend (`index.py → main()`) inspects the last user message to determine `Mode` (CONFIRMATION or REGENERATION), then uses `PhaseFinder` to identify the next phase from conversation history.
3. `GeneratorFactory` maps `(phase, content_mode)` to a generator class and streams the response back via SSE.
4. Frontend state machine in `store/RenderedMessages/provider.tsx` handles each streamed response and advances the UI.

### Phase Pipeline (`backend/app/generators/phases/`)
Phases run in order; each generator reads prior phase outputs from conversation history via `PhaseFinder`:

| Phase | Generator | What it does |
|---|---|---|
| Script, StoryBoard, RoleDescription | `ScriptGenerator` / `StoryBoardGenerator` / `RoleDescriptionGenerator` (direct, no intent classification) | LLM generates content using mode-specific prompt |
| RoleImage | `RoleImageGenerator` | Text-to-image; passes `reference_image` via `extra_body` if provided in metadata |
| FirstFrameDescription | `FirstFrameDescriptionGenerator` | LLM refines descriptions for image prompts |
| FirstFrameImage | `FirstFrameImageGenerator` | Text-to-image (or image-to-image with reference); same `reference_image` logic |
| VideoDescription | `VideoDescriptionGenerator` or `SkipVideoDescriptionGenerator` | LLM generates video motion prompts, or skipped |
| Video | `VideoGenerator` or `SkipVideoGenerator` | Video generation API (`CGT_ENDPOINT_ID`), or skipped |
| Tone | `ToneGenerator` | LLM selects TTS voice; for narration/text modes, overwrites LLM-chosen lines with verbatim StoryBoard text |
| Audio | `AudioGenerator` | TTS synthesis (parallel) |
| Film | `FilmGenerator` or `StorybookFilmGenerator` | ffmpeg assembles final video; `FilmGenerator` uses AI videos + freezes last frame when video < audio duration; `StorybookFilmGenerator` uses static first-frame images |
| FilmInteraction | `FilmInteractionGenerator` | VLM-based Q&A about the generated film |

### Adding a New Mode
1. `backend/app/constants.py` — add `MODE_*` constant and `MAX_STORY_BOARD_NUMBER_*` if needed
2. `backend/app/generators/prompts/` — create new prompt file with all phase prompts
3. `backend/app/generators/factory.py` — add a generator map and a branch in `get_generator()`
4. Each phase generator (`script.py`, `storyboard.py`, `role_description.py`, `first_frame_description.py`, `tone.py`, `role_image.py`, `first_frame_image.py`) — add an `elif content_mode == MODE_*` branch
5. `frontend/src/module/VideoGenerator/constants.ts` — add mode constant and `MODE_CONFIG` entry
6. `frontend/src/routes/page.tsx` — add entry to `modes` array

### Multi-Mode Prompt System
Each phase generator imports mode-specific prompts at the top and selects via `content_mode` in `__init__`. Prompts live in `backend/app/generators/prompts/<mode_name>.py`. The default (children_story) prompt is defined inline in the phase file itself.

### Reference Image (写实风格)
- Frontend: `ChatWindowV2/index.tsx` maintains `referenceImage` state; `updateReferenceImage()` is exposed via `ChatWindowContext`. `startReply()` includes it as `metadata.reference_image` (base64).
- Backend: `RoleImageGenerator` and `FirstFrameImageGenerator` read `request.metadata.get("reference_image")` and pass it to `T2IClient.image_generation()` via `extra_body={"reference_image": base64}`.
- Upload UI appears in `VideoGenerateFlow/index.tsx` when `assistantData?.Extra?.IsRealistic === true`.

### Message Protocol
- **Assistant messages** are prefixed: `phase=Script`, `phase=StoryBoard`, etc. `PhaseFinder` scans conversation history for these prefixes to reconstruct state.
- **User messages**: plain text (CONFIRMATION) or `REGENERATION phase=<X> {JSON}` with existing assets so only missing ones are re-generated.
- `tone.py` special case: for `story_narration`, `text_to_storyboard`, `text_to_video` modes, Tone.line/line_en are forcibly overwritten with verbatim StoryBoard text after LLM inference to ensure audio matches original text exactly.

### Film Assembly (`FilmGenerator` vs `StorybookFilmGenerator`)
- `FilmGenerator`: uses AI-generated videos per storyboard. Audio is authoritative for duration — if video is shorter than audio, the last frame is frozen (`tpad=stop_mode=clone`) to cover remaining audio.
- `StorybookFilmGenerator`: uses static first-frame images looped for audio duration. Both burn bilingual ASS subtitles via ffmpeg.

### Frontend Structure
- `src/routes/page.tsx` — Homepage with mode selection cards; `modes` array defined early in the component (before any early returns); `backendMode` strips `_realistic` suffix before passing to `Extra.Mode`.
- `src/module/VideoGenerator/` — Main module; `store/RenderedMessages/provider.tsx` drives phase-by-phase UI flow.
- `src/components/ChatWindowV2/` — SSE streaming, message state, `metadata` construction, `referenceImage` state.
- `src/module/VideoGenerator/components/VideoGenerateFlow/index.tsx` — Per-phase UI cards; reference image upload shown when `Extra.IsRealistic`.
- `src/module/WatchAndChat/` — XState machine for film interaction phase.
- Dev proxy in `modern.config.ts`: `/api/v3/bots` → `http://localhost:8890`.

### UI Details
- Step label text: `frontend/src/module/VideoGenerator/components/UserMessage/index.tsx` line 16 `STEP_LABELS` array
- `isVideoSkipped` flag in `VideoGenerateFlow`: true for `story_narration` and `text_to_storyboard` — hides the video generation step in the UI flow
