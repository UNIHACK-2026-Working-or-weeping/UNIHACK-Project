# Mascot Passive Aggressive Reminder
Unihack team: Working or weeping

### How to use
1. Go to [releases](https://github.com/UNIHACK-2026-Working-or-weeping/UNIHACK-Project/releases)
2. Download the Chrome or Firefox extensions
3. Unzip and install your extension
   - [(Chrome Instructions)](https://github.com/UNIHACK-2026-Working-or-weeping/UNIHACK-Project?tab=readme-ov-file#chrome-extension)
   - [(Firefox Instructions)](https://github.com/UNIHACK-2026-Working-or-weeping/UNIHACK-Project?tab=readme-ov-file#firefox-extension)
4. Download and unzip mascot application [Link](https://drive.google.com/open?id=1ikFSik6M24o9wmHfc9GsfM3qHv4cYE-h&usp=drive_fs)
5. Run standalone executable `ResponsibilityMascot.exe`

Note: Application cold start time can take awhile with no user facing response, as it has to load the AI dependencies, please be patient.

### Developer Setup

#### Chrome Extension
1. Go to [`chrome://extensions`](chrome://extensions)
2. Enable Developer Mode by clicking the toggle switch in the top right.
3. Click `Load unpacked` and select the `chrome_extension` directory

#### Firefox Extension
1. Go to [`about:debugging#/runtime/this-firefox`](about:debugging#/runtime/this-firefox)
2. Click "Load Temporary Add-on"
3. Select the `manifest.json` file in the `firefox_extension` directory

#### Desktop Mascot
1. Install UV\
  https://docs.astral.sh/uv/#installation
2. Navigate to desktop folder\
  `cd desktop`
3. Download tts model
  `uv run huggingface-cli download Qwen/Qwen3-TTS-12Hz-0.6B-Base --local-dir ./models/Qwen3-TTS-12Hz-0.6B-Base`
4. Run the program (LLM model should auto download on first run)\
  `uv run main.py` 


#### Disabling AI Features for local dev
The AI inference server (llama-cpp-python) will take quite a while to install on first run as it has to compile `llama-cpp`\
If you do not need it to develop your features, comment out `name = "llama-cpp-python"` in `pyproject.toml`
