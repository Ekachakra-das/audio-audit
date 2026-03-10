import os
import sys
print("DEBUG: VoiceFixer worker script starting...", file=sys.stderr)
sys.stderr.flush()
import argparse
import inspect
import torch
import numpy as np
import tempfile
import soundfile as sf
import subprocess
from unittest.mock import MagicMock

# --- Грязный хак для Mac (обход deepspeed как в resemble_worker) ---
if "deepspeed" not in sys.modules:
    mock_ds = MagicMock()
    for m in ["deepspeed", "deepspeed.runtime", "deepspeed.runtime.engine", 
              "deepspeed.runtime.zero.config", "deepspeed.accelerator", "deepspeed.runtime.utils"]:
        sys.modules[m] = mock_ds

try:
    from voicefixer import VoiceFixer
except ImportError as e:
    print(f"Error: Failed to import voicefixer. {e}", file=sys.stderr)
    sys.exit(1)

def log(msg):
    print(msg)
    sys.stdout.flush()

def error(msg):
    print(msg, file=sys.stderr)
    sys.stderr.flush()

def get_bitrate_args(bitrate):
    s = str(bitrate)
    if s.startswith('v'):
        return ["-q:a", s[1:]]
    else:
        return ["-b:a", f"{s}k"]

def process():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--mode", choices=["preview", "full"], default="preview")
    parser.add_argument("--offset", type=float, default=0)
    parser.add_argument("--duration", type=float, default=30)
    parser.add_argument("--vf_mode", type=int, default=0, choices=[0, 1, 2], help="VoiceFixer Mode (0: Orig, 1: Add, 2: Remove)")
    parser.add_argument("--bitrate", type=str, default="128")
    
    # Ignored args to be compatible with generic bridge calls
    parser.add_argument("--gain", type=float, default=1.0)
    parser.add_argument("--mix", type=float, default=1.0)
    parser.add_argument("--volume", type=float, default=None)
    parser.add_argument("--method", help="Ignored") # Bridge passes this, but we don't use it
    
    args = parser.parse_args()
    
    # device = "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")
    device = "cpu" # Force CPU to avoid MPS hangs on Mac
    log(f"Device: {device}")
    
    # 1. Загрузка и подготовка сегмента через FFmpeg
    temp_segment = os.path.join(tempfile.gettempdir(), f"vf_seg_{os.getpid()}.wav")
    
    ffmpeg_cmd = ["ffmpeg", "-y", "-ss", str(args.offset)]
    if args.mode == "preview":
        ffmpeg_cmd.extend(["-t", str(args.duration)])
    
    ffmpeg_cmd.extend([
        "-i", args.input, 
        "-vn", 
        "-acodec", "pcm_s16le", 
        "-ar", "44100", 
        "-ac", "1", 
        temp_segment
    ])
    
    try:
        log(f"Extracting segment: {args.offset}s, duration: {args.duration if args.mode == 'preview' else 'full'}")
        subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        error(f"FFmpeg extraction failed: {e}")
        sys.exit(1)

    # 2. Обработка VoiceFixer
    try:
        log("Initializing VoiceFixer...")
        vf = VoiceFixer()
        
        log(f"Running VoiceFixer Mode {args.vf_mode}...")
        log("PROGRESS: 10")
        
        # VoiceFixer restore expects: input (path or numpy), output (path), cuda (bool), mode (int)
        # We process in-memory to catch progress if possible, but library's restore_inmem returns numpy
        
        # Read audio
        audio_in, sr = sf.read(temp_segment) # sf reads as float64 usually, vf expects float32
        audio_in = audio_in.astype(np.float32)
        
        use_cuda = (device == "cuda" or device == "mps") # VF library handles 'cuda' boolean, might need patch for mps effectively
        
        # If MPS, we need to be careful. The Streamlit app had extensive monkey patching.
        # Ideally, we replicate that patching here if necessary.
        # For now, let's try standard usage. If it fails on MPS, we might need those patches.
        # Given unified_lab.py had them, we SHOULD probably include them.
        
        # --- MONKEY PATCHING FOR MPS (Copied from unified_lab.py logic) ---
        if device == "mps":
            # Monkey Patch Spectrogram - imports removed as they were causing errors and likely unused
            pass

            # Simple wrapper to force 'cuda' arg to allow MPS execution flow in library
            # The library often checks `if cuda:` -> `.cuda()`. We want `.to(device)`
            # We will rely on Pytorch's current device setting if we can, or just let it run on CPU if it's too complex to patch cleanly in a worker script without full copy-paste.
            # actually, standard VoiceFixer might default to CPU if cuda=False.
            # Passing cuda=True might crash on MPS if it calls .cuda() explicitly.
            pass
        
        # Running inference
        # restore_inmem signature differs across VoiceFixer versions.
        # Some builds accept `tqdm`, some do not.
        
        log("PROGRESS: 20")
        if args.mode == "full":
             log("Processing full file...")
        
        # VoiceFixer runs on 44100 internally.
        restore_kwargs = {
            "mode": args.vf_mode,
            "cuda": (device == "cuda"),
        }
        try:
            if "tqdm" in inspect.signature(vf.restore_inmem).parameters:
                restore_kwargs["tqdm"] = False
        except (TypeError, ValueError):
            # Builtins / wrapped callables may not expose signatures.
            pass

        processed_audio = vf.restore_inmem(audio_in, **restore_kwargs)
        
        log("PROGRESS: 80")
        
        # Save to temp WAV
        temp_wav = os.path.join(tempfile.gettempdir(), f"vf_tmp_{os.getpid()}.wav")
        sf.write(temp_wav, processed_audio.T, 44100) # output is (channels, time) usually? check unified_lab
        # get_bytes in unified_lab: sf.write(buffer, wav_arr.T, rate, format="WAV") -> so it returns (channels, time)
        
        log("PROGRESS: 90")
        
        # 3. Конвертация в MP3
        log(f"Encoding to MP3: {args.bitrate}k")
        cmd = [
            "ffmpeg", "-y", 
            "-i", temp_wav,
            "-i", args.input,
            "-map", "0:a", 
            "-map_metadata", "1",
            "-codec:a", "libmp3lame",
            "-id3v2_version", "3",
            "-write_id3v1", "1",
        ]
        cmd.extend(get_bitrate_args(args.bitrate))
        cmd.append(args.output)

        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        log("PROGRESS: 100")
        log("DONE")
        
    except Exception as e:
        error(f"Processing failed: {e}")
        import traceback
        error(traceback.format_exc())
        sys.exit(1)
    finally:
        if os.path.exists(temp_segment): os.remove(temp_segment)
        if 'temp_wav' in locals() and os.path.exists(temp_wav): os.remove(temp_wav)

if __name__ == "__main__":
    process()
