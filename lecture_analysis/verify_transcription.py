
import sys
import json
import os

# Disable implicit HF token to avoid 401s if token is expired/invalid for public models
os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
os.environ["HF_TOKEN"] = ""
os.environ["HUGGING_FACE_HUB_TOKEN"] = ""
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"

import subprocess
import mlx_whisper
import warnings
import difflib

# Suppress warnings
warnings.filterwarnings("ignore")

import uuid

def extract_audio_segment(input_path, duration=120, start_time=0):
    """Extracts the first 'duration' seconds of audio to a unique temp wav file."""
    unique_id = uuid.uuid4().hex
    temp_path = f"temp_{unique_id}.wav"
    
    command = [
        "ffmpeg", "-y",
        "-ss", str(start_time),
        "-i", input_path,
        "-t", str(duration),
        "-ac", "1", # Mono
        "-ar", "16000", # 16kHz for Whisper
        "-vn", # No video
        temp_path
    ]
    try:
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if not os.path.exists(temp_path) or os.path.getsize(temp_path) < 1000:
            if os.path.exists(temp_path): os.remove(temp_path)
            return None
        return temp_path
    except subprocess.CalledProcessError:
        return None

def calculate_similarity(text1, text2):
    """Calculates similarity ratio between two texts."""
    return difflib.SequenceMatcher(None, text1, text2).quick_ratio()

def main():
    try:
        # Read file paths from stdin
        input_data = sys.stdin.read()
        if not input_data:
            print(json.dumps({"error": "No input data provided"}))
            return

        request = json.loads(input_data)
        file_paths = request.get("files", [])
        # Duration from request (in minutes), default to 2
        duration_mins = request.get("duration", 2)
        offset_mins = request.get("offset", 0)
        
        duration_secs = duration_mins * 60
        offset_secs = offset_mins * 60

        if len(file_paths) < 2:
            print(json.dumps({"error": "Need at least 2 files to compare"}))
            return

        # Prepare results placeholder
        results_map = {f: {"path": f} for f in file_paths}
        
        def extract_job(file_path):
            if not os.path.exists(file_path):
                return file_path, None, "File not found"
            
            temp_wav = extract_audio_segment(file_path, duration=duration_secs, start_time=offset_secs)
            if not temp_wav:
                return file_path, None, "FFmpeg extraction failed (file too short or corrupted)"
                
            return file_path, temp_wav, None

        # 1. Parallel Extraction
        import concurrent.futures
        temp_files = [] 
        
        # Log start
        print(json.dumps({"type": "progress", "message": f"Extracting audio..."}), flush=True)

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(extract_job, f): f for f in file_paths}
            for future in concurrent.futures.as_completed(futures):
                path, temp_wav, error = future.result()
                if error:
                    results_map[path]["error"] = error
                else:
                    results_map[path]["temp_wav"] = temp_wav
                    temp_files.append((path, temp_wav))

        # MLX Whisper - optimized for Apple Silicon
        print(json.dumps({"type": "progress", "message": "🚀 Using MLX Whisper (Apple Silicon Optimized)"}), flush=True)
        
        # MLX model path (will be downloaded on first use)
        # Available: whisper-tiny-mlx, whisper-small-mlx, whisper-large-v3-turbo-mlx
        MLX_MODEL = "mlx-community/whisper-small-mlx"
        
        # Sort to match original order
        temp_files.sort(key=lambda x: file_paths.index(x[0]) if x[0] in file_paths else 999)

        for i, (path, temp_wav) in enumerate(temp_files):
            try:
                fname = os.path.basename(path)
                # DEBUG: Check file size to ensure audio is different
                fsize = os.path.getsize(temp_wav)
                print(json.dumps({"type": "progress", "message": f"Transcribing ({i+1}/{len(temp_files)}): {fname} (Size: {fsize/1024:.1f}KB)"}), flush=True)
                
                # MLX Whisper transcribe call
                result = mlx_whisper.transcribe(
                    temp_wav,
                    path_or_hf_repo=MLX_MODEL,
                    language="en",
                    condition_on_previous_text=False,
                    temperature=0.0
                )
                results_map[path]["text"] = result["text"].strip()
                results_map[path]["language"] = "en"
            except Exception as e:
                results_map[path]["error"] = f"Whisper failed: {str(e)}"
            finally:
                # Cleanup
                if os.path.exists(temp_wav):
                    os.remove(temp_wav)

        # Build final results list in original order
        results = [results_map[f] for f in file_paths]
        transcribed_texts = [r.get("text", "") for r in results if "text" in r]

        # 3. Calculate Similarity
        similarity = 0.0
        if len(transcribed_texts) >= 2:
            similarity = calculate_similarity(transcribed_texts[0], transcribed_texts[1])

        final_response = {
            "similarity": similarity,
            "results": results
        }
        
        # Emit final result event
        print(json.dumps({"type": "result", "data": final_response}), flush=True)

    except Exception as e:
        print(json.dumps({"error": str(e)}))

if __name__ == "__main__":
    main()
