import json
import asyncio
import os
import argparse
from pathlib import Path
import edge_tts

# Dil haritası: JSON locale -> Edge TTS voice (Kadın Sesi)
LANGUAGE_MAP = {
    "de-DE": "de-DE-KatjaNeural",       # Almanca - Katja
    "en-US": "en-US-AriaNeural",        # İngilizce - Aria
    "es-ES": "es-ES-ElviraNeural",      # İspanyolca - Elvira (fallback: es-ES-AlvaroNeural)
    "fr-FR": "fr-FR-DeniseNeural",      # Fransızca - Denise (fallback: fr-FR-HenriNeural)
    "it-IT": "it-IT-IsabellaNeural",    # İtalyanca - Isabella
    "tr-TR": "tr-TR-EmelNeural"         # Türkçe - Emel (fallback: tr-TR-AhmetNeural)
}

# Fallback voice'ler (primary çalışmazsa bunu kullan)
FALLBACK_VOICES = {
    "de-DE": "de-DE-ConradNeural",
    "en-US": "en-US-GuyNeural",
    "es-ES": "es-ES-AlvaroNeural",      # Erkek sesi ama çalışan
    "fr-FR": "fr-FR-HenriNeural",       # Erkek sesi ama çalışan
    "it-IT": "it-IT-DiegoNeural",
    "tr-TR": "tr-TR-AhmetNeural"        # Türkçe fallback
}

async def generate_audio(text, language_code, output_path):
    """Metni ses dosyasına dönüştür (fallback voice desteği)"""
    try:
        voice = LANGUAGE_MAP.get(language_code)
        if not voice:
            print(f"⚠️  Dil desteklenmiyor: {language_code}")
            return False
        
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_path)
        return True
    except Exception as e:
        # Fallback voice'i dene
        print(f"⚠️  Fallback voice'e geçiliyor ({language_code})...", end=" ")
        try:
            fallback_voice = FALLBACK_VOICES.get(language_code)
            if fallback_voice and fallback_voice != voice:
                communicate = edge_tts.Communicate(text, fallback_voice)
                await communicate.save(output_path)
                print("✅")
                return True
        except:
            pass
        
        print(f"❌ Hata ({language_code}): {str(e)[:50]}")
        return False

async def process_json(json_file, output_dir):
    """JSON dosyasını oku ve tüm sesler oluştur"""
    
    import time
    start_time = time.time()
    
    script_dir = Path(__file__).resolve().parent
    json_path = Path(json_file)
    if not json_path.is_absolute():
        json_path = script_dir / json_path

    output_path = Path(output_dir)
    if not output_path.is_absolute():
        output_path = script_dir / output_path
    
    if not json_path.exists():
        print(f"❌ Hata: {json_path} bulunamadı!")
        print(f"📁 Lütfen JSON dosyasını bu script ile aynı klasöre koy.")
        return
    
    # Dosyaları oku
    with json_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Eski sesleri ve metadata'yı korumak için ayrı output klasörü kullan.
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Metadata JSON hazırlığı
    audio_metadata = {
        "categories": []
    }
    
    total_files = 0
    processed_files = 0
    
    # Toplam ses sayısını hesapla (progress için)
    for category in data.get("categories", []):
        for activity in category.get("activities", []):
            total_files += len(activity.get("mainWord", {}))
            for sentence in activity.get("dailySentences", []):
                total_files += len(sentence.get("texts", {}))
    
    print(f"🎵 Toplam {total_files} ses dosyası oluşturulacak...")
    print(f"{'='*60}\n")
    
    # Her kategoriyi işle
    for category in data.get("categories", []):
        category_meta = {
            "activities": []
        }
        
        for activity in category.get("activities", []):
            activity_id = activity.get("id", "unknown")
            asset_name = activity.get("assetName", "unknown")
            
            # Aktivite klasörü oluştur
            activity_dir = output_path / activity_id
            activity_dir.mkdir(exist_ok=True)
            
            activity_meta = {
                "id": activity_id,
                "assetName": asset_name,
                "mainWord": activity.get("mainWord", {}),
                "title": activity.get("title", {}),
                "sentences": []
            }
            
            # Ana kelime seslerini oluştur
            print(f"📁 Aktivite: {activity_id}")
            
            for lang_code, word in activity.get("mainWord", {}).items():
                filename = f"mainword_{lang_code}.mp3"
                filepath = activity_dir / filename
                
                processed_files += 1
                progress = (processed_files / total_files) * 100
                elapsed = time.time() - start_time
                eta = (elapsed / processed_files) * (total_files - processed_files) if processed_files > 0 else 0
                
                print(f"  🔊 [{processed_files:4d}/{total_files}] {progress:5.1f}% | ETA: {int(eta):3d}s | {lang_code} - '{word}'...", end=" ")
                
                success = await generate_audio(word, lang_code, str(filepath))
                if success:
                    print("✅")
                else:
                    print("❌")
            
            # Cümleler
            for sentence in activity.get("dailySentences", []):
                sentence_id = sentence.get("id", "unknown")
                sentence_meta = {
                    "id": sentence_id,
                    "audio_files": {}
                }
                
                for lang_code, text in sentence.get("texts", {}).items():
                    filename = f"{sentence_id}_{lang_code}.mp3"
                    filepath = activity_dir / filename
                    
                    processed_files += 1
                    progress = (processed_files / total_files) * 100
                    elapsed = time.time() - start_time
                    eta = (elapsed / processed_files) * (total_files - processed_files) if processed_files > 0 else 0
                    
                    print(f"  🔊 [{processed_files:4d}/{total_files}] {progress:5.1f}% | ETA: {int(eta):3d}s | {sentence_id} - {lang_code}...", end=" ")
                    
                    success = await generate_audio(text, lang_code, str(filepath))
                    if success:
                        print("✅")
                        sentence_meta["audio_files"][lang_code] = filename
                    else:
                        print("❌")
                
                activity_meta["sentences"].append(sentence_meta)
            
            print()  # Satır atla
            category_meta["activities"].append(activity_meta)
        
        audio_metadata["categories"].append(category_meta)
    
    # Metadata JSON kaydet
    metadata_path = output_path / "audio_metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(audio_metadata, f, ensure_ascii=False, indent=2)
    
    # Özet
    elapsed_time = time.time() - start_time
    minutes = int(elapsed_time // 60)
    seconds = int(elapsed_time % 60)
    
    print(f"{'='*60}")
    print(f"✨ TAMAMLANDI!")
    print(f"{'='*60}")
    print(f"📊 Oluşturulan: {processed_files}/{total_files} ses dosyası")
    print(f"⏱️  Süre: {minutes}m {seconds}s")
    print(f"📁 Klasör: {output_path}")
    print(f"📄 Metadata: {metadata_path}")
    print(f"\n✅ Tüm dosyalar {output_dir} içinde!")

def parse_args():
    parser = argparse.ArgumentParser(description="NestLingo aktivite seslerini oluşturur.")
    parser.add_argument(
        "json_file",
        nargs="?",
        default="new_activities_audio_texts.json",
        help="Ses metinlerini içeren JSON dosyası"
    )
    parser.add_argument(
        "--output-dir",
        default="new_activities_audio",
        help="Seslerin ve yeni audio_metadata.json dosyasının yazılacağı klasör"
    )
    return parser.parse_args()


# Çalıştır
args = parse_args()
asyncio.run(process_json(args.json_file, args.output_dir))
