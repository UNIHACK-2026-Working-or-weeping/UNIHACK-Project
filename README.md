# Mascot Passive Aggressive Reminder
## What This Project Is
This project is a desktop mascot that gives passive aggressive reminders when users open distracting websites.

Current idea in one line:
Browser activity triggers mascot mood changes on desktop, so the mascot reacts when you visit non-allowed sites.

## Main Goals (Team Direction)
### Core goals
1. Desktop mascot that can move and detect screens.
2. A page where users can enter non-allowed stuff.
3. Personalization support (name and pronouns).
4. Textbox reminders shown when accessing non-allowed stuff.

### Stretch goals
1. Calendar integration for deadline-based reminders.
2. Manual to-do list for personalized reminder content.
3. Read text aloud from detected/selected screen.
4. Summarize text from detected/selected screen.
5. Different mascot actions for different trigger types.
6. 2-3 mascot designs/themes.

## Current Status Snapshot
### Implemented now
1. Desktop mascot app using `PySide6` with transparent frameless always-on-top window.
2. Mascot is draggable and resizable while preserving image aspect ratio.
3. Pixel-aware click handling (transparent parts do not count as draggable surface).
4. Local API (`FastAPI` on `127.0.0.1:8000`) to control mascot state/image.
5. Chrome extension that detects visits to social media and custom blocked domains.
6. Extension-to-desktop communication via local HTTP requests:
  - Social/disallowed tab active: switch mascot to `teeth` image.
  - Leaving/closing those tabs: switch mascot back to default image.
7. Popup UI to add/remove custom tracked domains.
8. Context menu action in Chrome to add current domain to tracked list.

### Not implemented yet (from goals)
1. User profile fields (name/pronouns).
2. Reminder textbox/message system in UI.
3. Deadline/calendar sync.
4. To-do list integration.
5. Screen text reading/summarization.
6. Trigger-specific action sets beyond image swap.

## High-Level Architecture
1. User opens website in Chrome.
2. Extension service worker checks hostname against default + custom tracked domains.
3. If matched, extension sends `POST /image/teeth` to desktop app API.
4. Desktop app receives command and updates mascot image.
5. When user leaves/closes tracked tab, extension sends `POST /image/default`.
6. Mascot returns to normal expression.

## Repository Structure
```
README.md
chrome_extension/
  background.js
  manifest.json
  popup.html
  popup.js
desktop/
  main.py
  pyproject.toml
  mascot/
   mascot_centre.png
   mascot_cry.png
   mascot_frown.png
   mascot_jump.png
   mascot_left.png
   mascot_right.png
   mascot_smile.png
   neckbreak_1.png
   neckbreak_2.png
  mascot.png
  mascot_1.png
```

## File-by-File: What Exists and How It Is Implemented
### `chrome_extension/manifest.json`
Defines a Manifest V3 extension named `Social Media Tracker`.

Key parts:
1. Service worker: `background.js`.
2. Permissions: `tabs`, `storage`, `contextMenus`.
3. Popup UI: `popup.html`.

### `chrome_extension/background.js`
Main runtime logic for domain tracking and mascot control.

What it does:
1. Has built-in default tracked domains (Facebook, X/Twitter, Instagram, YouTube, etc.).
2. Loads and saves custom domains using `chrome.storage.local`.
3. Adds current site via Chrome context menu (`Add current domain to tracker`).
4. Tracks tab URL state in `tabUrlCache`.
5. On tab load/activation/removal:
  - Calls `http://localhost:8000/image/teeth` when tracked domain is active.
  - Calls `http://localhost:8000/image/default` when leaving tracked tab.

### `chrome_extension/popup.html`
Small popup UI for domain management.

Contains:
1. Input textbox for domain.
2. Add button.
3. Dynamic list of saved custom domains.
4. Remove button per domain.

### `chrome_extension/popup.js`
Popup logic.

What it does:
1. Loads saved custom domains from local storage.
2. Normalizes user input into hostname form.
3. Adds unique domains.
4. Removes domains from saved list.
5. Re-renders list in popup.

### `desktop/main.py`
Desktop app entry point and full mascot/API runtime.

Major components:
1. `MascotWindow`:
  - Frameless, transparent, always-on-top mascot window.
  - Dragging only on opaque pixels.
  - Resize from edges/corners with fixed aspect ratio.
  - Shift+drag scaling behavior.
2. `FastAPIController`:
  - API endpoints to get state and switch mascot image.
3. `MascotApp`:
  - Manages current image (`mascot.png` vs `mascot_1.png`).
  - Runs local API server using `uvicorn` on background thread.
  - Uses `QTimer` command queue so UI updates happen safely on Qt side.
  - Provides tray icon menu for manual swap and app exit.

### `desktop/pyproject.toml`
Python project metadata and dependencies.

Current dependencies:
1. `fastapi`
2. `uvicorn`
3. `pyside6`
4. `pillow`
5. `pydantic`

## Local API Contract (Desktop App)
Base URL: `http://127.0.0.1:8000`

Endpoints:
1. `GET /health` -> health check.
2. `GET /image` -> current image state.
3. `POST /image/toggle` -> toggle default/teeth.
4. `POST /image/default` -> set default image.
5. `POST /image/teeth` and `GET /image/teeth` -> set teeth image.
6. `POST /image/set` with JSON `{ "image": "default" | "teeth" }`.

## Setup and Run
### Prerequisites
1. Python and `uv` package manager.
2. Google Chrome (for extension testing).

### 1) Clone repository
Follow GitHub clone instructions:
https://docs.github.com/en/repositories/creating-and-managing-repositories/cloning-a-repository

### 2) Run desktop mascot app
From project root:
```powershell
cd desktop
uv run main.py
```

Expected:
1. Mascot window appears on desktop.
2. System tray icon appears.
3. Local API starts on `127.0.0.1:8000`.

### 3) Load Chrome extension
1. Open `chrome://extensions`.
2. Enable `Developer mode`.
3. Click `Load unpacked`.
4. Select the `chrome_extension` folder.

### 4) Try the flow
1. Keep desktop app running.
2. Open any default tracked site (for example `youtube.com`).
3. Mascot should switch to aggressive/teeth image.
4. Switch away or close tab, mascot should return to default.

## Known Gaps and Notes
1. `pyproject.toml` currently sets `requires-python = ">=3.14"`.
2. Extension display name is still `Social Media Tracker` and can be renamed to match hack theme.
3. `desktop/mascot/` has many additional sprite images that are not yet wired into runtime actions.
4. Current trigger reaction is image swap only; no text reminders yet.

## Suggested Next Implementation Steps
1. Add reminder content model:
  - Profile fields: `name`, `pronouns`.
  - List of blocked categories/domains and custom messages.
2. Add a small local config UI (desktop or extension popup options page).
3. Extend API with endpoint like `POST /trigger` carrying domain/category metadata.
4. Map trigger types to different mascot expressions/actions using images in `desktop/mascot/`.
5. Add message bubble overlay near mascot for passive aggressive text.
6. Add optional TTS for reminder playback.

## Quick Troubleshooting
1. Extension cannot change mascot:
  - Ensure `uv run main.py` is running.
  - Check if `http://127.0.0.1:8000/health` responds.
2. Domain does not trigger:
  - Confirm domain is in default list or popup custom list.
  - Reload extension after code changes.
3. Mascot not visible:
  - Check system tray icon and ensure app is running.

## Hack Demo Script (Short)
1. Start desktop mascot.
2. Load extension.
3. Visit tracked site -> mascot changes mood.
4. Add a custom domain in popup.
5. Visit custom domain -> mascot reacts.
6. Explain upcoming roadmap: personalized reminders, calendar, to-do, screen-aware actions.
