import json
import asyncio
import time
from pathlib import Path
import edge_tts

# Kept in sync with generate_audio.py's maps.
LANGUAGE_MAP = {
    "de-DE": "de-DE-KatjaNeural",
    "en-US": "en-US-AriaNeural",
    "es-ES": "es-ES-ElviraNeural",
    "fr-FR": "fr-FR-DeniseNeural",
    "it-IT": "it-IT-IsabellaNeural",
    "tr-TR": "tr-TR-EmelNeural",
}
FALLBACK_VOICES = {
    "de-DE": "de-DE-ConradNeural",
    "en-US": "en-US-GuyNeural",
    "es-ES": "es-ES-AlvaroNeural",
    "fr-FR": "fr-FR-HenriNeural",
    "it-IT": "it-IT-DiegoNeural",
    "tr-TR": "tr-TR-AhmetNeural",
}

SCRIPT_DIR = Path(__file__).resolve().parent
JSON_PATH = SCRIPT_DIR / "everyday_phrases_audio_texts.json"


async def generate_audio(text, language_code, output_path):
    voice = LANGUAGE_MAP.get(language_code)
    if not voice:
        print(f"unsupported language: {language_code}")
        return False
    try:
        await edge_tts.Communicate(text, voice).save(output_path)
        return True
    except Exception as e:
        fallback = FALLBACK_VOICES.get(language_code)
        if fallback and fallback != voice:
            try:
                await edge_tts.Communicate(text, fallback).save(output_path)
                return True
            except Exception as e2:
                print(f"failed ({language_code}), primary+fallback: {e2}")
                return False
        print(f"failed ({language_code}): {e}")
        return False


async def main():
    with JSON_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    total = sum(len(sentences) * len(LANGUAGE_MAP) for sentences in data.values())
    done = 0
    start = time.time()

    for folder_key, sentences in data.items():
        out_dir = SCRIPT_DIR / folder_key
        out_dir.mkdir(exist_ok=True)
        for index, sentence in enumerate(sentences, start=1):
            for lang_code, text in sentence.items():
                filepath = out_dir / f"sentence_{index}_{lang_code}.mp3"
                done += 1
                elapsed = time.time() - start
                eta = (elapsed / done) * (total - done) if done else 0
                print(f"[{done:3d}/{total}] ETA {int(eta):3d}s | {folder_key} sentence_{index} {lang_code}: '{text}'...", end=" ")
                success = await generate_audio(text, lang_code, str(filepath))
                print("OK" if success else "FAILED")

    print(f"\nDone: {done}/{total} files in {int(time.time() - start)}s")


if __name__ == "__main__":
    asyncio.run(main())
