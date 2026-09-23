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
JSON_PATH = SCRIPT_DIR / "discovery_audio_texts.json"


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


def planned_files(data):
    """(folder, filename, language_code, text) for every file this should produce.

    Two shapes, matching how `SpeechService` indexes them: one word per
    discovery game under its own folder, and the two shared phrases the game
    screen offers alongside every word under `discovery_shared`.
    """
    for folder, by_language in data["words"].items():
        for lang_code, text in by_language.items():
            yield folder, f"mainword_{lang_code}.mp3", lang_code, text
    for folder, sentences in data["phrases"].items():
        for index, by_language in enumerate(sentences, start=1):
            for lang_code, text in by_language.items():
                yield folder, f"sentence_{index}_{lang_code}.mp3", lang_code, text


async def main():
    with JSON_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    files = list(planned_files(data))
    total = len(files)
    done = 0
    written = 0
    skipped = 0
    failed = []
    start = time.time()

    for folder, filename, lang_code, text in files:
        out_dir = SCRIPT_DIR / folder
        out_dir.mkdir(exist_ok=True)
        filepath = out_dir / filename
        done += 1

        # Re-running is cheap and safe: an already recorded file is left alone.
        if filepath.exists() and filepath.stat().st_size > 0:
            skipped += 1
            continue

        elapsed = time.time() - start
        eta = (elapsed / max(done - skipped, 1)) * (total - done)
        print(f"[{done:3d}/{total}] ETA {int(eta):3d}s | {folder}/{filename}: '{text}'...", end=" ")
        if await generate_audio(text, lang_code, str(filepath)):
            written += 1
            print("OK")
        else:
            failed.append(f"{folder}/{filename}")
            print("FAILED")

    print(f"\nWritten {written}, skipped {skipped}, failed {len(failed)} of {total} in {int(time.time() - start)}s")
    for name in failed:
        print("  failed:", name)


if __name__ == "__main__":
    asyncio.run(main())
