import json
import os
import threading
from typing import Optional
from urllib.request import urlretrieve

import soundfile as sf
import torch
from llama_cpp import Llama
from playsound3 import playsound
from qwen_tts import Qwen3TTSModel


def ensure_model_exists(
    model_path: str = "./models/Qwen3.5-0.8B-IQ4_XS.gguf",
    model_url: str = "https://huggingface.co/unsloth/Qwen3.5-0.8B-GGUF/resolve/5aea8824cba95d22990acc6ea66c2c1909530650/Qwen3.5-0.8B-IQ4_XS.gguf",
) -> None:
    """
    Check if the model file exists in the specified path.
    If it doesn't exist, download it from the given URL.

    Args:
        model_path: Local path where the model should be stored
        model_url: URL to download the model from if it doesn't exist
    """
    # Check if model already exists
    if os.path.exists(model_path):
        print(f"✓ Model found at: {model_path}")
        return

    # Create models directory if it doesn't exist
    model_dir = os.path.dirname(model_path)
    if model_dir and not os.path.exists(model_dir):
        print(f"Creating directory: {model_dir}")
        os.makedirs(model_dir, exist_ok=True)

    # Download the model
    print(f"Model not found. Downloading from: {model_url}")
    print(f"Saving to: {model_path}")
    print("This may take a while...")

    try:
        # Download with progress reporting
        def report_progress(block_num, block_size, total_size):
            """Callback to show download progress"""
            downloaded = block_num * block_size
            if total_size > 0:
                percent = min(downloaded / total_size * 100, 100)
                # Print progress on the same line
                print(
                    f"\rProgress: {percent:.1f}% ({downloaded / (1024 * 1024):.1f} MB / {total_size / (1024 * 1024):.1f} MB)",
                    end="",
                    flush=True,
                )

        urlretrieve(model_url, model_path, reporthook=report_progress)
        print("\n✓ Model downloaded successfully!")

    except Exception as e:
        print(f"\n✗ Failed to download model: {e}")
        raise


def submit_best_response(response: str, confidence: Optional[float] = None) -> str:
    """
    Local handler for the tool the model must call.
    Replace this with your persistence / API submission logic as needed.
    """
    payload = {
        "tool": "submit_best_response",
        "response": response.strip(),
    }
    print("\n[TOOL EXECUTED]")
    print(json.dumps(payload, indent=2))
    return payload["response"]


def getMessage(domain: str, event: Optional[str] = None) -> str:
    llm = Llama(
        model_path="./models/Qwen3.5-0.8B-IQ4_XS.gguf",
        # n_gpu_layers=-1,  # Uncomment to use GPU acceleration
        # seed=1337,         # Uncomment to set a specific seed
        # n_ctx=2048,        # Uncomment to increase the context window
        verbose=False,
    )

    system_prompt = (
        "You are a reliable motivational coach assistant that is trying to be funny operating in a tool-enabled environment. "
        "Your primary objective is to produce the best possible final response for the user "
        "and then submit that response by calling the provided function. "
        "Always provide a polished, direct answer suitable for end users. "
        "Your answer must be at maximum 20 words"
        "When a function is available for final submission, prefer the function call format "
        "instead of plain text. Ensure the 'response' argument contains the complete final answer. "
    )

    if event is not None:
        user_prompt = f"Create an extremely passive aggressive message to encourage a user to stop browsing {domain}"
    else:
        user_prompt = f"Create an extremely passive aggressive message to encourage a user to stop browsing {domain}, at the same time remind them that their next task is {event}"

    tools = [
        {
            "type": "function",
            "function": {
                "name": "submit_best_response",
                "description": "Submit the assistant's best final response to the user.",
                "parameters": {
                    "type": "object",
                    "title": "SubmitBestResponseArgs",
                    "properties": {
                        "response": {
                            "type": "string",
                            "title": "Response",
                            "description": "The final user-facing response text.",
                        },
                    },
                    "required": ["response"],
                },
            },
        }
    ]

    completion = llm.create_chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        tools=tools,
        tool_choice={
            "type": "function",
            "function": {"name": "submit_best_response"},
        },
        temperature=0.2,
        max_tokens=1024,
    )

    # print("\n[RAW COMPLETION]")
    # print(json.dumps(completion, indent=2))

    choice = completion["choices"][0]["message"]

    tool_calls = choice.get("tool_calls", [])
    if not tool_calls:
        # Fallback in case model returns plain text despite tool_choice
        content = choice.get("content", "")
        print("\n[WARN] No tool call returned. Fallback content:")
        print(content)
    else:
        call = tool_calls[0]
        fn_name = call["function"]["name"]
        args_raw = call["function"].get("arguments", "{}")

        try:
            args = json.loads(args_raw)
        except json.JSONDecodeError:
            print("\n[ERROR] Tool arguments were not valid JSON:")
            print(args_raw)
            args = {}

        if fn_name == "submit_best_response":
            return submit_best_response(
                response=args.get("response", ""),
                confidence=args.get("confidence"),
            )

        else:
            print(f"\n[ERROR] Unexpected tool name: {fn_name}")

    # Fallback Passive aggressive quote
    return "Don't you have anything better to do"


def generateAndPlaySound(message: str):
    """
    Vivian 	Bright, slightly edgy young female voice. 	Chinese
    Serena 	Warm, gentle young female voice. 	Chinese
    Uncle_Fu 	Seasoned male voice with a low, mellow timbre. 	Chinese
    Dylan 	Youthful Beijing male voice with a clear, natural timbre. 	Chinese (Beijing Dialect)
    Eric 	Lively Chengdu male voice with a slightly husky brightness. 	Chinese (Sichuan Dialect)
    Ryan 	Dynamic male voice with strong rhythmic drive. 	English
    Aiden 	Sunny American male voice with a clear midrange. 	English
    Ono_Anna 	Playful Japanese female voice with a light, nimble timbre. 	Japanese
    Sohee 	Warm Korean female voice with rich emotion. 	Korean
    """
    model = Qwen3TTSModel.from_pretrained(
        "models/Qwen3-TTS-12Hz-0.6B-Base",
        device_map="auto",
        dtype=torch.bfloat16,
        # attn_implementation="flash_attention_2",
    )
    ref_audio = "test_voice.mp3"
    ref_text = "Imagine a dark place. Or a suspensful situation, or imagine your own scenario for my voice."

    # single inference
    wavs, sr = model.generate_voice_clone(
        text=message,
        language="English",
        ref_audio=ref_audio,
        ref_text=ref_text,
        # speaker=speaker,
        # instruct="Sound like a high pitched jolly fun mascot",  # Omit if not needed.
    )
    sf.write("output_custom_voice.wav", wavs[0], sr)
    playsound("output_custom_voice.wav")
    # sound_thread = threading.Thread(
    #     target=playsound, args=("output_custom_voice.wav",), daemon=True
    # )
    # sound_thread.start()


if __name__ == "__main__":
    ensure_model_exists()
    # Testing
    message = getMessage("facebook")
    generateAndPlaySound(message)
