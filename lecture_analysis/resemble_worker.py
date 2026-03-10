import os
import sys
print("DEBUG: Resemble worker script starting...", file=sys.stderr)
sys.stderr.flush()
print("DEBUG: Resemble worker started", file=sys.stderr)
import argparse
print("DEBUG: Importing torch...", file=sys.stderr)
import torch
print("DEBUG: Importing numpy...", file=sys.stderr)
import numpy as np
import tempfile
import soundfile as sf
import subprocess
from functools import lru_cache
from resemble_import_shims import apply_resemble_import_shims
from torchaudio_shim import ensure_torchaudio_shim

apply_resemble_import_shims(emit_tqdm_progress=True, debug=False)
ensure_torchaudio_shim(debug=True)

RESEMBLE_IMPORT_ERROR = None
resemble_denoise = None
RESEMBLE_RUN_DIR = None
try:
    print("DEBUG: Importing resemble_enhance...", file=sys.stderr)
    import resemble_enhance.enhancer.inference as resemble_inference_module
    from resemble_enhance.enhancer.download import download as resemble_download
    from resemble_enhance.enhancer.train import Enhancer as ResembleEnhancer
    from resemble_enhance.enhancer.train import HParams as ResembleHParams
    from resemble_enhance.enhancer.inference import denoise as resemble_denoise
    from resemble_enhance.enhancer.download import REPO_DIR as RESEMBLE_REPO_DIR

    @lru_cache(maxsize=None)
    def _load_enhancer_relaxed(run_dir, device):
        if run_dir is None:
            run_dir = resemble_download()
        hp = ResembleHParams.load(run_dir)
        enhancer = ResembleEnhancer(hp)
        model_path = run_dir / "ds" / "G" / "default" / "mp_rank_00_model_states.pt"
        state_dict = torch.load(model_path, map_location="cpu")["module"]
        missing, unexpected = enhancer.load_state_dict(state_dict, strict=False)
        if unexpected:
            print(f"DEBUG: Relaxed load ignored {len(unexpected)} unexpected keys", file=sys.stderr)
        if missing:
            print(f"DEBUG: Relaxed load missing {len(missing)} keys", file=sys.stderr)
        enhancer.eval()
        enhancer.to(device)
        return enhancer

    resemble_inference_module.load_enhancer = _load_enhancer_relaxed

    candidate_run_dir = RESEMBLE_REPO_DIR / "enhancer_stage2"
    candidate_weights = candidate_run_dir / "ds" / "G" / "default" / "mp_rank_00_model_states.pt"
    if candidate_weights.exists():
        RESEMBLE_RUN_DIR = candidate_run_dir
        print(f"DEBUG: Using local ReSemble model at {RESEMBLE_RUN_DIR}", file=sys.stderr)
    else:
        print("DEBUG: Local ReSemble model not found; inference may attempt download", file=sys.stderr)
    print("DEBUG: Import successful", file=sys.stderr)
except ImportError as e:
    RESEMBLE_IMPORT_ERROR = str(e)
    print(f"WARN: Failed to import resemble_enhance ({e}). Will use fallback denoise.", file=sys.stderr)

def log(msg):
    print(msg)
    sys.stdout.flush()

def error(msg):
    print(msg, file=sys.stderr)
    sys.stderr.flush()

def get_bitrate_args(bitrate):
    s = str(bitrate)
    if s.startswith('v'):
        return ["-qscale:a", s[1:]]
    else:
        return ["-b:a", f"{s}k"]


def estimate_mix_alignment_shift(reference, target, sr, max_shift_ms=80):
    """Estimate sample shift needed to align target to reference.
    Returns (shift_samples, confidence).
    """
    if sr <= 0:
        return 0, 0.0

    n = min(int(reference.shape[0]), int(target.shape[0]))
    if n < int(sr * 0.25):
        return 0, 0.0

    win_len = min(n, int(sr * 2.0))  # Analyze up to 2-second windows
    starts = [0]
    if n > win_len * 2:
        starts.append((n - win_len) // 2)
    if n > win_len * 3:
        starts.append(n - win_len)
    starts = sorted(set(starts))

    ds = max(1, int(sr / 4000))  # Downsample for cheap correlation
    max_lag_ds = max(1, int((max_shift_ms / 1000.0) * sr / ds))

    lags = []
    scores = []

    for st in starts:
        ref = reference[st : st + win_len : ds].astype(np.float32, copy=False)
        tgt = target[st : st + win_len : ds].astype(np.float32, copy=False)
        if ref.shape[0] < 64 or tgt.shape[0] < 64:
            continue

        ref = ref - float(ref.mean())
        tgt = tgt - float(tgt.mean())
        ref_std = float(ref.std())
        tgt_std = float(tgt.std())
        if ref_std < 1e-6 or tgt_std < 1e-6:
            continue
        ref = ref / ref_std
        tgt = tgt / tgt_std

        corr = np.correlate(tgt, ref, mode="full")
        center = ref.shape[0] - 1
        lo = max(0, center - max_lag_ds)
        hi = min(corr.shape[0], center + max_lag_ds + 1)
        region = corr[lo:hi]
        if region.size == 0:
            continue

        best_idx = int(np.argmax(region))
        lag_ds = (lo + best_idx) - center
        lags.append(int(lag_ds * ds))
        scores.append(float(max(region[best_idx], 1e-6)))

    if not lags:
        return 0, 0.0

    shift = int(round(np.average(np.asarray(lags), weights=np.asarray(scores))))
    max_shift = int((max_shift_ms / 1000.0) * sr)
    shift = int(np.clip(shift, -max_shift, max_shift))
    conf = float(np.mean(scores) / max(1.0, float(win_len / ds)))
    conf = float(np.clip(conf, 0.0, 1.0))
    return shift, conf


def apply_sample_shift_np(signal_1d, shift_samples):
    if shift_samples == 0:
        return signal_1d

    n = int(signal_1d.shape[0])
    out = np.zeros_like(signal_1d)
    if shift_samples > 0:
        if shift_samples < n:
            out[: n - shift_samples] = signal_1d[shift_samples:]
    else:
        delay = -shift_samples
        if delay < n:
            out[delay:] = signal_1d[: n - delay]
    return out


def adaptive_aligned_mix(dry_np, wet_np, mix, sr):
    """Chunk-wise alignment + weighted overlap-add mix to reduce local echo artifacts."""
    n = min(int(dry_np.shape[0]), int(wet_np.shape[0]))
    if n <= 0:
        return np.asarray([], dtype=np.float32), []

    dry_np = dry_np[:n].astype(np.float32, copy=False)
    wet_np = wet_np[:n].astype(np.float32, copy=False)

    win = int(max(sr * 2.0, min(sr * 8.0, n)))  # 2s..8s
    hop = max(1, win // 2)

    acc = np.zeros(n, dtype=np.float32)
    weight = np.zeros(n, dtype=np.float32)

    # Use a smooth window for overlap-add.
    if win > 8:
        ola = np.hanning(win).astype(np.float32)
        ola = np.clip(ola, 1e-3, None)
    else:
        ola = np.ones(win, dtype=np.float32)

    shift_logs = []
    pos = 0
    while pos < n:
        end = min(n, pos + win)
        cur_len = end - pos
        dry_seg = dry_np[pos:end]
        wet_seg = wet_np[pos:end]

        shift, conf = estimate_mix_alignment_shift(
            dry_seg,
            wet_seg,
            sr,
            max_shift_ms=130,
        )
        wet_aligned = apply_sample_shift_np(wet_seg, shift)

        # If local match is weak, reduce dry contribution to avoid comb/echo artifacts.
        local_mix = float(mix)
        if conf < 0.18:
            local_mix = min(1.0, max(local_mix, 0.93))
        elif conf < 0.28:
            local_mix = min(1.0, max(local_mix, 0.88))

        mixed = dry_seg * (1.0 - local_mix) + wet_aligned * local_mix
        w = ola[:cur_len]
        acc[pos:end] += mixed * w
        weight[pos:end] += w

        shift_logs.append((pos, shift, conf, local_mix))
        if end == n:
            break
        pos += hop

    out = acc / np.maximum(weight, 1e-6)
    return out.astype(np.float32), shift_logs

def process():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--mode", choices=["preview", "full"], default="preview")
    parser.add_argument("--offset", type=float, default=0)
    parser.add_argument("--duration", type=float, default=30)
    parser.add_argument("--gain", type=float, default=1.0)
    parser.add_argument("--mix", type=float, default=1.0)
    parser.add_argument("--bitrate", type=str, default="128")
    parser.add_argument("--volume", type=float, default=None, help="Alias for gain")
    
    args = parser.parse_args()
    
    if args.volume is not None:
        args.gain = args.volume
    
    forced_device = (os.environ.get("RESEMBLE_DEVICE") or "").strip().lower()
    if forced_device in {"cpu", "mps", "cuda"}:
        if forced_device == "mps" and not (hasattr(torch.backends, "mps") and torch.backends.mps.is_available()):
            error("RESEMBLE_DEVICE=mps requested but MPS is unavailable; falling back to auto.")
            forced_device = ""
        elif forced_device == "cuda" and not torch.cuda.is_available():
            error("RESEMBLE_DEVICE=cuda requested but CUDA is unavailable; falling back to auto.")
            forced_device = ""

    if forced_device:
        device = forced_device
    else:
        # Prefer Apple Silicon GPU on Mac, then CUDA, then CPU.
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            device = "mps"
        elif torch.cuda.is_available():
            device = "cuda"
        else:
            device = "cpu"
    log(f"Device: {device}")
    
    # 1. Загрузка и подготовка сегмента через FFmpeg
    temp_segment = os.path.join(tempfile.gettempdir(), f"resemble_seg_{os.getpid()}.wav")
    
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

    # 2. Обработка Resemble
    try:
        audio_np, sr = sf.read(temp_segment)
        if audio_np.dtype != np.float32:
            audio_np = audio_np.astype(np.float32)

        # Convert to tensor (Time)
        audio = torch.from_numpy(audio_np)
        
        # Apply Gain
        if args.gain != 1.0:
            audio = audio * args.gain
            
        log("PROGRESS: 10")
        log("Running Denoise...")
        
        # For full mode, show intermediate progress during denoise
        # (even though we can't track real progress, this shows it's working)
        if args.mode == "full":
            log("PROGRESS: 20")
            log("Processing full file - this may take several minutes...")
        
        denoised_tensor = None
        new_sr = sr
        resemble_failed = None

        if resemble_denoise is not None:
            try:
                with torch.no_grad():
                    if RESEMBLE_RUN_DIR is not None:
                        denoised_tensor, new_sr = resemble_denoise(audio, sr, device, run_dir=RESEMBLE_RUN_DIR)
                    else:
                        denoised_tensor, new_sr = resemble_denoise(audio, sr, device)
            except Exception as e:
                resemble_failed = str(e)
                error(f"Resemble inference failed: {e}. Falling back to scipy Wiener denoise.")
        else:
            resemble_failed = RESEMBLE_IMPORT_ERROR or "Unknown import error"
            error(f"Resemble import unavailable: {resemble_failed}. Falling back to scipy Wiener denoise.")

        if denoised_tensor is None:
            try:
                from scipy.signal import wiener
                fallback_np = wiener(audio.cpu().numpy(), mysize=7)
                fallback_np = np.nan_to_num(fallback_np, nan=0.0, posinf=0.0, neginf=0.0)
                denoised_tensor = torch.from_numpy(np.asarray(fallback_np, dtype=np.float32))
                new_sr = sr
                log("Fallback denoise applied (scipy Wiener).")
            except Exception as fallback_e:
                error(f"Fallback denoise failed: {fallback_e}. Using original audio.")
                denoised_tensor = audio.detach().cpu()
                new_sr = sr
        
        denoised_tensor = denoised_tensor.cpu()
        log("PROGRESS: 70")

        # Mix (Denoised vs Original)
        if args.mix < 1.0:
            try:
                mixed_np, shift_logs = adaptive_aligned_mix(
                    audio.detach().cpu().numpy(),
                    denoised_tensor.detach().cpu().numpy(),
                    float(args.mix),
                    int(new_sr),
                )
                if mixed_np.size > 0:
                    denoised_tensor = torch.from_numpy(mixed_np)
                if shift_logs:
                    # Keep logs concise: show first/mid/last windows.
                    idxs = sorted(set([0, len(shift_logs) // 2, len(shift_logs) - 1]))
                    samples = [shift_logs[i] for i in idxs]
                    sample_msg = ", ".join(
                        f"@{int(p / max(new_sr,1))}s shift={s} ({(s / max(new_sr,1))*1000:.1f}ms) conf={c:.2f} mix={m:.2f}"
                        for (p, s, c, m) in samples
                    )
                    log(f"Adaptive mix alignment: {sample_msg}")
            except Exception as e:
                error(f"Adaptive mix alignment failed: {e}. Falling back to basic mix.")
                min_len = min(len(audio), len(denoised_tensor))
                audio_clip = audio[:min_len]
                denoised_clip = denoised_tensor[:min_len]
                final_audio = (audio_clip * (1 - args.mix)) + (denoised_clip * args.mix)
            else:
                final_audio = denoised_tensor
        else:
            final_audio = denoised_tensor

        # Save to temp WAV
        temp_wav = os.path.join(tempfile.gettempdir(), f"resemble_tmp_{os.getpid()}.wav")
        sf.write(temp_wav, final_audio.numpy(), new_sr)
        
        log("PROGRESS: 90")
        
        # 3. Конвертация в MP3 с заданным битрейтом
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
            "-f", "mp3"
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
