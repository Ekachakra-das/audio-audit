import os
import sys
import argparse
import tempfile
import subprocess

import numpy as np
import soundfile as sf
import torch
import torchaudio

try:
    from LavaSR.model import LavaEnhance2
except ImportError as e:
    print(f"Error: Failed to import LavaSR. {e}", file=sys.stderr)
    sys.stderr.flush()
    sys.exit(1)


def log(msg):
    print(msg)
    sys.stdout.flush()


def error(msg):
    print(msg, file=sys.stderr)
    sys.stderr.flush()


def get_bitrate_args(bitrate):
    s = str(bitrate)
    if s.startswith("v"):
        return ["-q:a", s[1:]]
    return ["-b:a", f"{s}k"]


def select_device():
    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def mix_signals(dry_audio, dry_sr, wet_audio, wet_sr, wet_mix):
    wet_mix = float(np.clip(wet_mix, 0.0, 1.0))
    if wet_mix >= 0.999:
        return wet_audio, wet_sr
    if wet_mix <= 0.001:
        return dry_audio, dry_sr

    dry = torch.as_tensor(dry_audio, dtype=torch.float32).reshape(1, -1)
    wet = torch.as_tensor(wet_audio, dtype=torch.float32).reshape(1, -1)

    target_sr = int(wet_sr)
    if int(dry_sr) != target_sr:
        dry = torchaudio.functional.resample(dry, int(dry_sr), target_sr)

    n = min(dry.shape[-1], wet.shape[-1])
    if n <= 0:
        return wet_audio, wet_sr

    dry = dry[..., :n]
    wet = wet[..., :n]
    mixed = dry * (1.0 - wet_mix) + wet * wet_mix
    return mixed.reshape(-1).cpu().numpy().astype(np.float32, copy=False), target_sr


def process():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--mode", choices=["preview", "full"], default="preview")
    parser.add_argument("--offset", type=float, default=0)
    parser.add_argument("--duration", type=float, default=30)
    parser.add_argument("--bitrate", type=str, default="128")
    parser.add_argument("--denoise", type=int, default=1)
    parser.add_argument("--superres", type=int, default=1)
    parser.add_argument("--input_sr", type=int, default=16000)
    parser.add_argument("--batch", type=int, default=0)

    # Ignored bridge args for compatibility with the generic cleanup route.
    parser.add_argument("--gain", type=float, default=1.0)
    parser.add_argument("--mix", type=float, default=1.0)
    parser.add_argument("--volume", type=float, default=None)
    parser.add_argument("--method")
    parser.add_argument("--vf_mode", type=int, default=0)

    args = parser.parse_args()

    device = select_device()
    log(f"Device: {device}")

    temp_segment = os.path.join(tempfile.gettempdir(), f"lavasr_seg_{os.getpid()}.wav")
    temp_wav = os.path.join(tempfile.gettempdir(), f"lavasr_tmp_{os.getpid()}.wav")
    temp_gain_segment = os.path.join(tempfile.gettempdir(), f"lavasr_gain_{os.getpid()}.wav")

    ffmpeg_cmd = ["ffmpeg", "-y", "-ss", str(args.offset)]
    if args.mode == "preview":
        ffmpeg_cmd.extend(["-t", str(args.duration)])

    ffmpeg_cmd.extend(
        [
            "-i",
            args.input,
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "48000",
            "-ac",
            "1",
            temp_segment,
        ]
    )

    try:
        log("Extracting segment...")
        subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        log("PROGRESS: 10")
        log("Initializing LavaSR...")
        lava = LavaEnhance2(device=device)

        log("PROGRESS: 25")
        use_denoise = bool(args.denoise)
        use_superres = bool(args.superres)
        wet_mix = float(np.clip(args.mix, 0.0, 1.0))
        input_gain = float(max(0.1, args.gain))
        input_sr = int(np.clip(args.input_sr, 8000, 48000))
        batch_mode = bool(args.batch)
        model_input_path = temp_segment
        dry_audio, dry_sr = sf.read(temp_segment)
        if isinstance(dry_audio, np.ndarray) and dry_audio.ndim > 1:
            dry_audio = np.mean(dry_audio, axis=1)
        dry_audio = np.asarray(dry_audio, dtype=np.float32).reshape(-1)
        if abs(input_gain - 1.0) > 1e-6:
            gained_audio = np.clip(dry_audio * input_gain, -1.0, 1.0)
            sf.write(temp_gain_segment, gained_audio, int(dry_sr))
            model_input_path = temp_gain_segment
        input_audio, _ = lava.load_audio(model_input_path, input_sr=input_sr)

        log("Running LavaSR enhancement...")
        if use_denoise or use_superres:
            output_audio = lava.enhance(
                input_audio,
                enhance=use_superres,
                denoise=use_denoise,
                batch=batch_mode,
            )
            output_sr = 48000
            if not use_superres:
                output_audio = torchaudio.functional.resample(
                    output_audio.reshape(1, -1),
                    48000,
                    16000,
                ).reshape(-1)
                output_sr = 16000
        else:
            output_audio = torch.from_numpy(np.asarray(dry_audio, dtype=np.float32).reshape(-1))
            output_sr = int(dry_sr)

        log("PROGRESS: 80")
        output_audio = output_audio.detach().cpu().numpy().astype(np.float32, copy=False).reshape(-1)
        output_audio, output_sr = mix_signals(dry_audio, int(dry_sr), output_audio, int(output_sr), wet_mix)
        sf.write(temp_wav, output_audio, output_sr)

        log("PROGRESS: 90")
        log(f"Encoding to MP3: {args.bitrate}")
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            temp_wav,
            "-i",
            args.input,
            "-map",
            "0:a",
            "-map_metadata",
            "1",
            "-codec:a",
            "libmp3lame",
            "-id3v2_version",
            "3",
            "-write_id3v1",
            "1",
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
        if os.path.exists(temp_segment):
            os.remove(temp_segment)
        if os.path.exists(temp_wav):
            os.remove(temp_wav)
        if os.path.exists(temp_gain_segment):
            os.remove(temp_gain_segment)


if __name__ == "__main__":
    process()
