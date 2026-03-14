# Mascot Passive Aggressive Reminder
Unihack team: Working or weeping

### How to use
TODO: FILL OUT THIS PART OF README

### Developer Setup
#### Download repository
[Instructions](https://docs.github.com/en/repositories/creating-and-managing-repositories/cloning-a-repository)

#### Chrome Extension
1. Go to [`chrome://extensions`](chrome://extensions)
2. Enable Developer Mode by clicking the toggle switch in the top right.
3. Click `Load unpacked` and select the `chrome_extension` directory

#### Desktop Mascot
1. Install UV\
  https://docs.astral.sh/uv/#installation
2. Navigate to desktop folder\
  `cd desktop`
3. Run the program\
    `uv run main.py`

#### Disabling AI Features for local dev
Comment out `name = "llama-cpp-python"` in `pyproject.toml`
