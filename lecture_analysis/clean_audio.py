import os
import sys
import argparse
import json
import subprocess
import logging

try:
    from resemble_enhance.enhancer.inference import enhance as resemble_enhance
except ImportError:
    pass # Will handle gracefully if missing during runtime check

# Configure logging to file - truncate on start to keep it fresh for the modal
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'debug_clean.log')
logging.basicConfig(filename=log_file, level=logging.DEBUG, 
                    format='%(asctime)s %(levelname)s: %(message)s',
                    filemode='w')

def log(msg):
    print(msg)
    sys.stdout.flush()
    logging.info(msg)

def error(msg):
    print(msg, file=sys.stderr)
    logging.error(msg)

def get_bitrate_args(bitrate):
    s = str(bitrate)
    if s.startswith('v'):
        return ["-qscale:a", s[1:]]
    else:
        return ["-b:a", f"{s}k"]

def get_audio_info(input_path):
    """Get original audio sample rate and bitrate using ffprobe"""
    try:
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_streams", "-select_streams", "a:0", input_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        info = json.loads(result.stdout)
        
        if info.get("streams"):
            stream = info["streams"][0]
            sample_rate = int(stream.get("sample_rate", 48000))
            # Bitrate might be in stream or need to be calculated
            bitrate = stream.get("bit_rate")
            if bitrate:
                bitrate = int(bitrate) // 1000  # Convert to kbps
            else:
                # Fallback: try to get from format
                cmd2 = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", input_path]
                result2 = subprocess.run(cmd2, capture_output=True, text=True, check=True)
                fmt = json.loads(result2.stdout)
                if fmt.get("format", {}).get("bit_rate"):
                    bitrate = int(fmt["format"]["bit_rate"]) // 1000
                else:
                    bitrate = 320  # Default to high quality
            
            log(f"Original audio: sample_rate={sample_rate}Hz, bitrate={bitrate}kbps")
            return sample_rate, bitrate
    except Exception as e:
        error(f"Failed to get audio info: {e}")
    
    return 48000, 320  # Safe defaults

def load_audio_optimized(input_path, mode="preview", duration_sec=60, offset_sec=0):
    log(f"Loading optimized (FFmpeg): {input_path}, mode={mode}, offset={offset_sec}, duration={duration_sec}")
    
    temp_wav = f"temp_load_{os.getpid()}.wav"
    
    # Base command: convert to 48kHz Mono PCM
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(offset_sec),
        "-i", input_path,
    ]
    
    # If preview, add duration limit
    if mode == "preview":
        cmd.extend(["-t", str(duration_sec)])
    
    # Common output params: mono, 48k, pcm_s16le
    cmd.extend([
        "-vn", 
        "-acodec", "pcm_s16le",
        "-ar", "48000",
        "-ac", "1",
        temp_wav
    ])
    
    try:
        log(f"Running ffmpeg preparation: {' '.join(cmd)}")
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        log("FFmpeg preparation success")
        return temp_wav, True 
    except subprocess.CalledProcessError as e:
        error(f"FFmpeg preparation failed: {e.stderr.decode() if e.stderr else str(e)}")
        return None, False

def clean_with_denoiser(input_path, output_path, mode="preview", offset_sec=0, target_bitrate=None, volume=1.0, duration=60):
    log(f"Starting Denoiser Clean: {input_path} -> {output_path} (offset={offset_sec})")
    
    # Get original audio parameters BEFORE processing
    orig_sample_rate, orig_bitrate = get_audio_info(input_path)
    if target_bitrate is None: target_bitrate = orig_bitrate
    
    # Lazy imports
    try:
        log("Importing torch components...")
        import torch
        import torchaudio
        from denoiser import pretrained
        from denoiser.dsp import convert_audio
    except Exception as e:
        error(f"Import failed: {e}")
        return False
        
    effective_input, is_temp = load_audio_optimized(input_path, mode, offset_sec=offset_sec, duration_sec=duration)
    if not effective_input: 
        error("Load failed")
        return False
    
    try:
        log("Loading Denoiser model (dns48 - 16kHz)...")
        model = pretrained.dns48().cpu()  # dns48 is 16kHz (hidden=48), not 48kHz
        model.eval()
        

        # Load WAV using soundfile (the file pre-processed by load_audio_optimized)
        log(f"Reading wav with soundfile: {effective_input}")
        
        # We need soundfile/numpy here too
        import soundfile as sf
        import numpy as np
        
        data, sample_rate = sf.read(effective_input)
             
        # Convert numpy array to torch tensor (channels, time)
        # soundfile returns (time, channels) or (time,)
        if len(data.shape) == 1:
            data = data.reshape(-1, 1) # Make it (time, 1)
        
        # Transpose to (channels, time) -> (1, time)
        wav = torch.from_numpy(data.T).float()
        sr = sample_rate

        log("Converting audio format...")
        wav = convert_audio(wav, sr, model.sample_rate, model.chin)

        log("Running inference...")
        with torch.no_grad():
            # If full mode OR long preview, use chunked processing to report progress
            if mode == "full" or wav.shape[-1] > model.sample_rate * 30:
                chunk_size = model.sample_rate * 60 if mode == "full" else model.sample_rate * 10
                total_chunks = (wav.shape[-1] + chunk_size - 1) // chunk_size
                denoised_chunks = []
                for idx, i in enumerate(range(0, wav.shape[-1], chunk_size)):
                    progress = int(((idx + 1) / total_chunks) * 100)
                    log(f"PROGRESS: {progress}%")
                    chunk = wav[:, i:i+chunk_size]
                    denoised_chunk = model(chunk[None])[0]
                    denoised_chunks.append(denoised_chunk)
                denoised = torch.cat(denoised_chunks, dim=-1)
            else:
                log("PROGRESS: 50%")
                denoised = model(wav[None])[0]
                log("PROGRESS: 90%")

        log("Saving output with original quality...")
        temp_save = f"temp_save_{os.getpid()}.wav"
        
        # Convert tensor to numpy for soundfile
        # Tensor is (channels, time), soundfile wants (time, channels)
        output_np = denoised.cpu().detach().numpy().T
        sf.write(temp_save, output_np, model.sample_rate)
        
        # Resample to original sample rate and save with original bitrate
        # Use the lower of: original sample rate or model sample rate (don't upsample beyond what we have)
        target_sample_rate = min(orig_sample_rate, model.sample_rate)
        log(f"Encoding: target_sr={target_sample_rate}Hz, bitrate={target_bitrate}kbps")
        
        cmd = [
            "ffmpeg", "-y", "-i", temp_save,
            "-i", input_path,
            "-map", "0:a",
            "-map_metadata", "1",
            "-ar", str(target_sample_rate),
            "-codec:a", "libmp3lame",
            "-filter:a", f"volume={volume}",
            "-id3v2_version", "3",
            "-write_id3v1", "1",
        ]
        cmd.extend(get_bitrate_args(target_bitrate))
        cmd.append(output_path)
        
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        if os.path.exists(temp_save): os.remove(temp_save)
        log("Denoiser cleanup complete.")
        
    except Exception as e:
        error(f"Denoiser exception: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return False
    finally:
        if is_temp and os.path.exists(effective_input):
            os.remove(effective_input)
            
    return True


def clean_with_noisereduce(input_path, output_path, mode="preview", offset_sec=0, noise_start=None, noise_end=None, target_bitrate=None, nr_amount=1.0, nr_sensitivity=1.5, volume=1.0, duration=60):
    log(f"Starting NoiseReduce: {input_path} -> {output_path} (noise: {noise_start}-{noise_end})")
    
    log("PROGRESS: 10%")
    orig_sample_rate, orig_bitrate = get_audio_info(input_path)
    if target_bitrate is None: target_bitrate = orig_bitrate
    
    effective_input, is_temp = load_audio_optimized(input_path, mode, offset_sec=offset_sec, duration_sec=duration)
    if not effective_input: return False

    try:
        import noisereduce as nr
        import soundfile as sf
        import numpy as np

        data, sr = sf.read(effective_input)
        
        # If noise range is provided, extract the profile
        noise_clip = None
        if noise_start is not None and noise_end is not None:
            s_idx = int(noise_start * sr)
            e_idx = int(noise_end * sr)
            if s_idx < len(data) and e_idx <= len(data):
                noise_clip = data[s_idx:e_idx]
                log(f"Extracted noise profile: {noise_clip.shape}")

        log("Running noisereduce...")
        if noise_clip is not None:
            # prop_decrease: 0.0 to 1.0 (amount of noise to remove)
            # n_std_thresh_stationary: Threshold for considering a frequency bin as noise (sensitivity)
            reduced = nr.reduce_noise(y=data, sr=sr, y_noise=noise_clip, prop_decrease=nr_amount, n_std_thresh_stationary=nr_sensitivity)
        else:
            # Automatic (stationary)
            reduced = nr.reduce_noise(y=data, sr=sr, prop_decrease=nr_amount, n_std_thresh_stationary=nr_sensitivity)
            
        temp_out = f"temp_nr_out_{os.getpid()}.wav"
        sf.write(temp_out, reduced, sr)
        
        log("PROGRESS: 90%")
        log("PROGRESS: 95%")
        # Convert to MP3
        cmd = [
            "ffmpeg", "-y", "-i", temp_out,
            "-i", input_path,
            "-map", "0:a",
            "-map_metadata", "1",
            "-ar", str(orig_sample_rate),
            "-codec:a", "libmp3lame",
            "-filter:a", f"volume={volume}",
            "-id3v2_version", "3",
            "-write_id3v1", "1",
        ]
        cmd.extend(get_bitrate_args(target_bitrate))
        cmd.append(output_path)
        
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log("PROGRESS: 100%")
        
        if os.path.exists(temp_out): os.remove(temp_out)
        return True
    except Exception as e:
        error(f"NoiseReduce failed: {e}")
        return False
    finally:
        if is_temp and os.path.exists(effective_input):
            os.remove(effective_input)

def clean_with_deepfilter(input_path, output_path, mode="preview", offset_sec=0, target_bitrate=None, volume=1.0, duration=60):
    """Clean audio using DeepFilterNet - optimized for speech enhancement."""
    log(f"Starting DeepFilterNet: {input_path} -> {output_path} (offset={offset_sec})")
    
    # Get original audio parameters
    orig_sample_rate, orig_bitrate = get_audio_info(input_path)
    if target_bitrate is None: target_bitrate = orig_bitrate
    
    effective_input, is_temp = load_audio_optimized(input_path, mode, offset_sec=offset_sec, duration_sec=duration)
    if not effective_input: 
        return False
    
    try:
        # Lazy imports - avoid df.io which uses torchaudio.backend
        import soundfile as sf
        import numpy as np
        import torch
        
        # Monkey-patch for torchaudio 2.10+ compatibility with deepfilternet
        import torchaudio
        if not hasattr(torchaudio, 'backend'):
            # Create fake backend module for compatibility
            from types import SimpleNamespace, ModuleType
            import sys
            
            # Create AudioMetaData class
            class AudioMetaData:
                def __init__(self, sample_rate=48000, num_frames=0, num_channels=1, 
                             bits_per_sample=16, encoding='PCM_S'):
                    self.sample_rate = sample_rate
                    self.num_frames = num_frames
                    self.num_channels = num_channels
                    self.bits_per_sample = bits_per_sample
                    self.encoding = encoding
            
            # Create fake backend.common module
            backend_common = ModuleType('torchaudio.backend.common')
            backend_common.AudioMetaData = AudioMetaData
            backend = ModuleType('torchaudio.backend')
            backend.common = backend_common
            torchaudio.backend = backend
            sys.modules['torchaudio.backend'] = backend
            sys.modules['torchaudio.backend.common'] = backend_common
            
            # Add torchaudio.info function if missing
            def fake_info(path, **kwargs):
                data, sr = sf.read(path)
                frames = len(data) if len(data.shape) == 1 else data.shape[0]
                channels = 1 if len(data.shape) == 1 else data.shape[1]
                return AudioMetaData(sample_rate=sr, num_frames=frames, num_channels=channels)
            
            if not hasattr(torchaudio, 'info'):
                torchaudio.info = fake_info
        
        from df.enhance import enhance, init_df
        
        log("Initializing DeepFilterNet model...")
        model, df_state, _ = init_df()
        target_sr = df_state.sr()  # DeepFilterNet expects 48000Hz
        
        log(f"Loading audio with soundfile (sr={target_sr})...")
        # Read the preprocessed WAV file
        audio_data, file_sr = sf.read(effective_input)
        
        # Convert to tensor format expected by DeepFilterNet: (channels, samples)
        if len(audio_data.shape) == 1:
            audio_tensor = torch.from_numpy(audio_data.astype(np.float32)).unsqueeze(0)
        else:
            audio_tensor = torch.from_numpy(audio_data.T.astype(np.float32))
        
        log("PROGRESS: 50%")
        log(f"Enhancing audio (shape={audio_tensor.shape}, sr={target_sr})...")
        enhanced = enhance(model, df_state, audio_tensor)
        
        log("PROGRESS: 80%")
        log("Saving output...")
        temp_out = f"temp_df_out_{os.getpid()}.wav"
        
        # Convert back to numpy and save
        if isinstance(enhanced, torch.Tensor):
            enhanced_np = enhanced.cpu().numpy()
        else:
            enhanced_np = enhanced
            
        # Transpose if needed (soundfile expects samples, channels)
        if len(enhanced_np.shape) > 1 and enhanced_np.shape[0] < enhanced_np.shape[1]:
            enhanced_np = enhanced_np.T
            
        sf.write(temp_out, enhanced_np, target_sr)
        
        log("PROGRESS: 90%")
        # Convert to MP3 with original quality
        target_sample_rate = min(orig_sample_rate, target_sr)
        log(f"Encoding: target_sr={target_sample_rate}Hz, bitrate={orig_bitrate}kbps")
        
        cmd = [
            "ffmpeg", "-y", "-i", temp_out,
            "-i", input_path,
            "-map", "0:a",
            "-map_metadata", "1",
            "-ar", str(target_sample_rate),
            "-codec:a", "libmp3lame",
            "-id3v2_version", "3",
            "-write_id3v1", "1",
        ]
        cmd.extend(get_bitrate_args(orig_bitrate))
        cmd.append(output_path)

        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                       
        if os.path.exists(temp_out): 
            os.remove(temp_out)
        log("DeepFilterNet complete.")
        
    except Exception as e:
        error(f"DeepFilterNet exception: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return False
    finally:
        if is_temp and os.path.exists(effective_input):
             os.remove(effective_input)
             
    return True



def clean_with_resemble(input_path, output_path, mode="preview", offset_sec=0, target_bitrate=None, volume=1.0, duration=60):
    log(f"Starting Resemble Enhance: {input_path} -> {output_path}")
    
    # Get original audio parameters
    orig_sample_rate, orig_bitrate = get_audio_info(input_path)
    if target_bitrate is None: target_bitrate = orig_bitrate
    
    # Resemble Enhance works best with 44.1k/48k. 
    effective_input, is_temp = load_audio_optimized(input_path, mode, offset_sec=offset_sec, duration_sec=duration)
    if not effective_input: 
        return False
        
    try:
        import torch
        import torchaudio
        import soundfile as sf
        from resemble_enhance.enhancer.inference import enhance as resemble_enhance
        
        forced_device = (os.environ.get("RESEMBLE_DEVICE") or "").strip().lower()
        if forced_device in {"cpu", "mps", "cuda"}:
            if forced_device == "mps" and not (hasattr(torch.backends, "mps") and torch.backends.mps.is_available()):
                log("RESEMBLE_DEVICE=mps requested but unavailable; using auto device")
                forced_device = ""
            elif forced_device == "cuda" and not torch.cuda.is_available():
                log("RESEMBLE_DEVICE=cuda requested but unavailable; using auto device")
                forced_device = ""

        if forced_device:
            device = forced_device
        else:
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                device = "mps"
            elif torch.cuda.is_available():
                device = "cuda"
            else:
                device = "cpu"
        log(f"Using device: {device}")
        
        # Load audio with soundfile instead of torchaudio to avoid TorchCodec errors
        data, sample_rate = sf.read(effective_input)
        if len(data.shape) == 1:
            data = data.reshape(-1, 1) # (time, 1)
        
        # Resemble Enhance expects (channels, time) tensor
        audio = torch.from_numpy(data.T).float()
        sr = sample_rate
        
        # Resemble Enhance expects 44100 usually, but let's see. 
        # The library signature: enhance(audio, sr, device, nfe=64, solver='midpoint', lambd=0.5, tau=0.5)
        
        if audio.shape[0] > 1:
            # mix to mono and make 1D
            audio = audio.mean(dim=0)
        else:
            # make 1D
            audio = audio.squeeze(0)
            
        audio = audio.to(device)
        
        log("Running Resemble Enhance inference (Heavy!)...")
        log("PROGRESS: 10%")
        
        with torch.no_grad():
            # nfe=64 is default high quality. Lowering to 32 might speed up but let's stick to quality.
            enhanced_audio, new_sr = resemble_enhance(audio, sr, device, nfe=64, solver='midpoint', lambd=0.5, tau=0.5)
            
        log("PROGRESS: 90%")
        log("Saving output...")
        
        temp_out = f"temp_resemble_out_{os.getpid()}.wav"
        
        # Save using soundfile
        # enhanced_audio is likely on GPU and is (channels, time)
        # soundfile wants (time, channels)
        save_audio = enhanced_audio.cpu().detach().numpy().T
        sf.write(temp_out, save_audio, new_sr)
        
        # Convert to MP3
        target_sample_rate = min(orig_sample_rate, new_sr)
        log(f"Encoding: target_sr={target_sample_rate}Hz, bitrate={target_bitrate}kbps")
        
        cmd = [
            "ffmpeg", "-y", "-i", temp_out,
            "-i", input_path,
            "-map", "0:a",
            "-map_metadata", "1",
            "-ar", str(target_sample_rate),
            "-codec:a", "libmp3lame",
            "-filter:a", f"volume={volume}",
            "-id3v2_version", "3",
            "-write_id3v1", "1",
        ]
        cmd.extend(get_bitrate_args(target_bitrate))
        cmd.append(output_path)
        
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        if os.path.exists(temp_out): os.remove(temp_out)
        log("Resemble Enhance complete.")
        
    except Exception as e:
        error(f"Resemble Enhance exception: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return False
    finally:
        if is_temp and os.path.exists(effective_input):
            os.remove(effective_input)
            
    return True


def clean_with_remove_echo(input_path, output_path, mode="preview", offset_sec=0, target_bitrate=None, volume=1.0, duration=60, echo_strength=0.45):
    log(f"Starting Remove Echo: {input_path} -> {output_path}")

    orig_sample_rate, orig_bitrate = get_audio_info(input_path)
    if target_bitrate is None:
        target_bitrate = orig_bitrate

    effective_input, is_temp = load_audio_optimized(input_path, mode, offset_sec=offset_sec, duration_sec=duration)
    if not effective_input:
        return False

    try:
        import numpy as np
        import soundfile as sf
        from scipy import signal

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
            region = corr[min_lag:max_lag + 1]
            idx = int(np.argmax(region))
            lag = min_lag + idx
            conf = float(max(region[idx], 0.0) / (corr[0] + 1e-8))
            return lag, conf

        data, sr = sf.read(effective_input)
        if data.ndim > 1:
            data = np.mean(data, axis=1)
        audio = data.astype(np.float32)

        if volume != 1.0:
            audio = audio * float(volume)

        strength = float(np.clip(echo_strength, 0.0, 1.0))
        lag, conf = detect_echo_delay(audio, sr)
        log(f"Echo estimate: lag={(lag / sr) * 1000.0:.1f}ms conf={conf:.3f}")
        log("PROGRESS: 45%")

        alpha = strength * np.clip(conf * 1.8, 0.08, 0.75)
        stage1 = audio.copy()
        if lag > 0 and lag < len(audio):
            stage1[lag:] -= alpha * audio[:-lag]
            lag2 = lag * 2
            if lag2 < len(audio):
                stage1[lag2:] -= 0.45 * alpha * audio[:-lag2]

        nperseg = 1024
        noverlap = 768
        _, _, stft = signal.stft(
            stage1, fs=sr, window="hann", nperseg=nperseg, noverlap=noverlap, boundary=None
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
        stage2 = stage2[:audio.shape[0]].astype(np.float32)

        wet = 0.35 + 0.65 * strength
        out = audio * (1.0 - wet) + stage2 * wet
        peak = float(np.max(np.abs(out)))
        if peak > 0.995:
            out = out / peak * 0.995

        temp_out = f"temp_deecho_out_{os.getpid()}.wav"
        sf.write(temp_out, out, sr)
        log("PROGRESS: 90%")

        cmd = [
            "ffmpeg", "-y", "-i", temp_out,
            "-i", input_path,
            "-map", "0:a",
            "-map_metadata", "1",
            "-ar", str(min(orig_sample_rate, sr)),
            "-codec:a", "libmp3lame",
            "-id3v2_version", "3",
            "-write_id3v1", "1",
        ]
        cmd.extend(get_bitrate_args(target_bitrate))
        cmd.append(output_path)
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        if os.path.exists(temp_out):
            os.remove(temp_out)
        log("Remove Echo complete.")
        return True
    except Exception as e:
        error(f"Remove Echo failed: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return False
    finally:
        if is_temp and os.path.exists(effective_input):
            os.remove(effective_input)


if __name__ == "__main__":
    try:
        log(f"Script starting... PID={os.getpid()}")
        parser = argparse.ArgumentParser()
        parser.add_argument("--input", required=True)
        parser.add_argument("--output", required=True)
        parser.add_argument("--mode", choices=["preview", "full"], default="preview")
        parser.add_argument("--method", choices=["denoiser", "deepfilter", "resemble", "manual", "remove_echo"], default="denoiser")
        parser.add_argument("--offset", type=int, default=0, help="Offset in seconds")
        parser.add_argument("--noise_start", type=float, help="Noise profile start (sec)")
        parser.add_argument("--noise_end", type=float, help="Noise profile end (sec)")
        parser.add_argument("--bitrate", type=str, help="Target bitrate (kbps or v0-v9)")
        parser.add_argument("--nr_amount", type=float, default=1.0, help="Noise reduction amount (0.0-1.0)")
        parser.add_argument("--nr_sensitivity", type=float, default=1.5, help="Noise sensitivity (n_std_thresh_stationary)")
        parser.add_argument("--volume", type=float, default=1.0, help="Volume gain multiplier")
        parser.add_argument("--duration", type=float, default=60.0, help="Preview duration")
        parser.add_argument("--echo_strength", type=float, default=0.45, help="Echo reduction strength (0.0-1.0)")
        
        args = parser.parse_args()
        log(f"Args: {args}")
        
        success = False
        if args.method == "denoiser":
            success = clean_with_denoiser(args.input, args.output, args.mode, args.offset, target_bitrate=args.bitrate, volume=args.volume, duration=args.duration)
        elif args.method == "deepfilter":
            success = clean_with_deepfilter(args.input, args.output, args.mode, args.offset, target_bitrate=args.bitrate, volume=args.volume, duration=args.duration)
        elif args.method == "resemble":
            success = clean_with_resemble(args.input, args.output, args.mode, args.offset, target_bitrate=args.bitrate, volume=args.volume, duration=args.duration)
        elif args.method == "manual":
            success = clean_with_noisereduce(args.input, args.output, args.mode, args.offset, args.noise_start, args.noise_end, target_bitrate=args.bitrate, nr_amount=args.nr_amount, nr_sensitivity=args.nr_sensitivity, volume=args.volume, duration=args.duration)
        elif args.method == "remove_echo":
            success = clean_with_remove_echo(args.input, args.output, args.mode, args.offset, target_bitrate=args.bitrate, volume=args.volume, duration=args.duration, echo_strength=args.echo_strength)
            
        if success:
            log("PROGRESS: 100%")
            log("DONE")
        else:
            sys.exit(1)
    except Exception as e:
        error(f"Main exception: {e}")
        sys.exit(1)
