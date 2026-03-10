import json
import os
import subprocess
import whisper
import Levenshtein
from pathlib import Path

# --- CONFIG ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CANDIDATES_FILE = os.path.join(BASE_DIR, 'candidates.json')
REPORT_FILE = os.path.join(BASE_DIR, 'verification_report.json')
TEMP_DIR = os.path.join(BASE_DIR, 'temp_audio')

# Ensure temp dir exists
os.makedirs(TEMP_DIR, exist_ok=True)

print("Loading Whisper model (base)...")
model = whisper.load_model("base")

def extract_audio(input_path, output_path, duration=120):
    """Extracts the first N seconds using ffmpeg."""
    try:
        subprocess.run([
            "ffmpeg", "-y", "-i", input_path,
            "-t", str(duration),
            "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", # Whisper friendly format
            output_path
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        print(f"Error processing {input_path}: {e}")
        return False

def verify_group(group):
    """Verifies a group of potential duplicates."""
    key = group['key']
    files = group['files']
    
    print(f"\nAnalyzing Group: {key}")
    
    results = []
    
    # Transcribe each file
    transcriptions = []
    for f in files:
        f_path = f['path']
        f_name = f['originalName']
        temp_wav = os.path.join(TEMP_DIR, f"{f_name}.wav")
        
        print(f"  Processing: {f_name}...")
        
        if extract_audio(f_path, temp_wav):
            # Transcribe
            result = model.transcribe(temp_wav)
            text = result["text"].strip()
            transcriptions.append({
                "file": f_name,
                "text": text
            })
            # Cleanup
            os.remove(temp_wav)
        else:
            transcriptions.append({
                "file": f_name,
                "text": "[ERROR_EXTRACTING_AUDIO]"
            })

    # Compare pair-wise
    comparisons = []
    if len(transcriptions) > 1:
        base = transcriptions[0]
        for i in range(1, len(transcriptions)):
            other = transcriptions[i]
            
            # Similarity Ratio
            ratio = Levenshtein.ratio(base['text'], other['text'])
            score = round(ratio * 100, 2)
            
            status = "UNIQUE"
            if score > 90: status = "DUPLICATE"
            elif score > 70: status = "LIKELY_DUPLICATE"
            
            print(f"  vs {other['file']}: {score}% ({status})")
            
            comparisons.append({
                "file1": base['file'],
                "file2": other['file'],
                "score": score,
                "status": status,
                "text_preview_1": base['text'][:100] + "...",
                "text_preview_2": other['text'][:100] + "..."
            })

    return {
        "key": key,
        "comparisons": comparisons
    }

# --- MAIN ---

print(f"Reading candidates from {CANDIDATES_FILE}...")
with open(CANDIDATES_FILE, 'r') as f:
    candidates = json.load(f)

print(f"Found {len(candidates)} groups to verify.")

final_report = []
for group in candidates:
    report = verify_group(group)
    final_report.append(report)

# Save Report
with open(REPORT_FILE, 'w') as f:
    json.dump(final_report, f, indent=2)

print(f"\nVerification Complete. Report saved to {REPORT_FILE}")

# Cleanup temp dir
try:
    os.rmdir(TEMP_DIR)
except:
    pass
