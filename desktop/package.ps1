uv run pyinstaller -D --add-data models:models --add-data mascot:mascot --add-binary sox.exe:. --add-binary test_voice.mp3:. --contents-directory "." --hidden-import ai_inference --hidden-import idle --hide-console hide-early --noconfirm --name ResponsibilityMascot main.py

# Copy llama_cpp and qwen_tts manually from venv (PyInstaller has issues with these)
Copy-Item -Path ".venv\Lib\site-packages\llama_cpp" -Destination "dist\ResponsibilityMascot\llama_cpp" -Recurse -Force
Copy-Item -Path ".venv\Lib\site-packages\qwen_tts" -Destination "dist\ResponsibilityMascot\qwen_tts" -Recurse -Force

7z a -tzip mascot_app.zip .\dist\ResponsibilityMascot\
