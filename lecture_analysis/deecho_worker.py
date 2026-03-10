import argparse
import os
import subprocess
import sys
import tempfile

import numpy as np
import soundfile as sf
from scipy import signal


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


def detect_echo_delay(samples, sr):
    if samples.size < 4096:
        return int(0.08 * sr), 0.0

    x = samples.astype(np.float32)
    x = x - np.mean(x)
    peak = np.max(np.abs(x))
    if peak < 1e-6:
        return int(0.08 * sr), 0.0

    x = x / peak
    corr = signal.fftconvolve(x, x[::-1], mode="full")
    corr = corr[corr.shape[0] // 2 :]

    min_lag = max(1, int(0.04 * sr))
    max_lag = min(int(0.20 * sr), corr.shape[0] - 1)
    if max_lag <= min_lag:
        return int(0.08 * sr), 0.0

    region = corr[min_lag : max_lag + 1]
    idx = int(np.argmax(region))
    lag = min_lag + idx
    confidence = float(max(region[idx], 0.0) / (corr[0] + 1e-8))
    return lag, confidence


def remove_echo(audio, sr, strength):
    strength = float(np.clip(strength, 0.0, 1.0))
    lag, conf = detect_echo_delay(audio, sr)

    # Stage 1: light comb subtraction to suppress dominant delayed reflection.
    alpha = strength * np.clip(conf * 1.8, 0.08, 0.75)
    stage1 = audio.copy()
    if lag > 0 and lag < len(audio):
        stage1[lag:] -= alpha * audio[:-lag]
        lag2 = lag * 2
        if lag2 < len(audio):
            stage1[lag2:] -= 0.45 * alpha * audio[:-lag2]

    # Stage 2: mild late-reverb attenuation in STFT domain.
    nperseg = 1024
    noverlap = 768
    _, _, stft = signal.stft(
        stage1,
        fs=sr,
        window="hann",
        nperseg=nperseg,
        noverlap=noverlap,
        boundary=None,
    )

    mag = np.abs(stft)
    tail_est = np.zeros_like(mag)
    decay = 0.85 + 0.10 * strength
    for i in range(1, mag.shape[1]):
        tail_est[:, i] = decay * tail_est[:, i - 1] + (1.0 - decay) * mag[:, i - 1]

    ratio = tail_est / (mag + 1e-8)
    gain = 1.0 - (0.35 + 0.40 * strength) * ratio
    gain = np.clip(gain, 0.35, 1.0)
    cleaned_stft = stft * gain

    _, stage2 = signal.istft(
        cleaned_stft,
        fs=sr,
        window="hann",
        nperseg=nperseg,
        noverlap=noverlap,
        input_onesided=True,
        boundary=None,
    )

    if stage2.shape[0] < audio.shape[0]:
        stage2 = np.pad(stage2, (0, audio.shape[0] - stage2.shape[0]))
    stage2 = stage2[: audio.shape[0]]

    # Blend to protect timbre at low strengths.
    wet = 0.35 + 0.65 * strength
    out = audio * (1.0 - wet) + stage2.astype(np.float32) * wet

    peak = float(np.max(np.abs(out)))
    if peak > 0.995:
        out = out / peak * 0.995

    return out.astype(np.float32), lag, conf


def process():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--mode", choices=["preview", "full"], default="preview")
    parser.add_argument("--offset", type=float, default=0)
    parser.add_argument("--duration", type=float, default=30)
    parser.add_argument("--bitrate", type=str, default="128")
    parser.add_argument("--echo_strength", type=float, default=0.45)
    parser.add_argument("--volume", type=float, default=1.0)

    args = parser.parse_args()

    temp_segment = os.path.join(tempfile.gettempdir(), f"deecho_seg_{os.getpid()}.wav")
    ffmpeg_cmd = ["ffmpeg", "-y", "-ss", str(args.offset)]
    if args.mode == "preview":
        ffmpeg_cmd.extend(["-t", str(args.duration)])

    ffmpeg_cmd.extend([
        "-i",
        args.input,
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "44100",
        "-ac",
        "1",
        temp_segment,
    ])

    try:
        log(f"Extracting segment: {args.offset}s, duration: {args.duration if args.mode == 'preview' else 'full'}")
        subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        error(f"FFmpeg extraction failed: {e}")
        sys.exit(1)

    try:
        log("PROGRESS: 10")
        audio, sr = sf.read(temp_segment)
        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)
        audio = audio.astype(np.float32)

        if args.volume != 1.0:
            audio *= float(args.volume)

        log("Running Remove Echo...")
        log("PROGRESS: 45")
        cleaned, lag, conf = remove_echo(audio, sr, args.echo_strength)
        log(f"Detected echo lag ~{(lag / sr) * 1000.0:.1f} ms (confidence={conf:.3f})")

        temp_wav = os.path.join(tempfile.gettempdir(), f"deecho_tmp_{os.getpid()}.wav")
        sf.write(temp_wav, cleaned, sr)

        log("PROGRESS: 85")
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
        if "temp_wav" in locals() and os.path.exists(temp_wav):
            os.remove(temp_wav)


if __name__ == "__main__":
    process()
