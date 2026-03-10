import json
import sys
import os
import time
import subprocess

def print_progress(percent, message):
    print(json.dumps({"status": "progress", "progress": percent, "message": message}), flush=True)

def get_duration_fast(filepath):
    try:
        cmd = [
            'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1', filepath
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
        if result.returncode == 0:
            return float(result.stdout.strip())
    except:
        pass
    
    # Fallback to librosa - import only when needed
    import librosa
    return librosa.get_duration(path=filepath)

def analyze_audio_file(filepath, full_scan=False, offset_arg=None, duration_arg=None, zoom_mode=False):
    print_progress(1, "Starting analysis process...")
    
    # Delayed imports to speed up initialization
    import librosa
    import numpy as np
    
    try:
        print_progress(5, "Checking file duration...")
        total_duration = get_duration_fast(filepath)
        
        offset = offset_arg if offset_arg is not None else 0.0
        duration = duration_arg if duration_arg is not None else 30
        
        # Ensure offset is safe
        if offset >= total_duration:
            offset = max(0, total_duration - 5)
        
        if full_scan:
            duration = min(600, total_duration)
            offset = 0.0
            sample_points = [0.0]
        elif offset_arg is not None:
            offset = offset_arg
            duration = duration_arg if duration_arg is not None else 30
            sample_points = [offset]
        else:
            import random
            sample_duration = 10.0
            usable_start = total_duration * 0.05
            usable_end = total_duration * 0.95
            usable_len = usable_end - usable_start
            
            sample_points = []
            if usable_len > sample_duration * 6:
                segment_len = usable_len / 6
                for i in range(6):
                    window_start = usable_start + (i * segment_len)
                    window_end = window_start + segment_len - sample_duration
                    p = random.uniform(window_start, window_end)
                    sample_points.append(p)
            else:
                sample_points = [0.0]
            duration = sample_duration

        # --- Zoom Mode Speed Optimization ---
        if zoom_mode and offset_arg is not None:
            import tempfile
            import matplotlib
            matplotlib.use('Agg')  # Non-interactive backend
            import matplotlib.pyplot as plt
            import librosa.display
            import io
            import base64
            
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
                temp_wav = tf.name
            
            try:
                # Use duration_arg if available, else fallback to 30
                current_duration = duration_arg if duration_arg is not None else 30
                print_progress(10, f"Extracting {current_duration}s fragment at {offset_arg:.1f}s...")
                cmd = [
                    'ffmpeg', '-y', 
                    '-ss', str(offset_arg), 
                    '-i', filepath,
                    '-t', str(current_duration), 
                    '-vn', '-acodec', 'pcm_s16le', '-ar', '22050', '-ac', '1',
                    temp_wav
                ]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True, timeout=30)
                
                print_progress(40, "Loading fragment for analysis...")
                y, sr = librosa.load(temp_wav, sr=None)
                
                print_progress(70, "Generating spectrogram image...")
                n_fft = 2048
                hop_length = 512
                D = np.abs(librosa.stft(y, n_fft=n_fft, hop_length=hop_length))
                S_dB = librosa.amplitude_to_db(D, ref=np.max)
                
                plt.figure(figsize=(12, 4))
                librosa.display.specshow(S_dB, sr=sr, hop_length=hop_length, x_axis='time', y_axis='linear', cmap='magma')
                plt.axis('off')
                plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
                
                buf = io.BytesIO()
                plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0, transparent=True, dpi=100)
                buf.seek(0)
                img_base64 = base64.b64encode(buf.read()).decode('utf-8')
                plt.close()
                
                print_progress(100, "Done!")
                return {
                    "status": "success",
                    "spectrogram_image": f"data:image/png;base64,{img_base64}",
                    "offset": offset,
                    "duration": duration
                }
            except subprocess.CalledProcessError as e:
                return {"status": "error", "error": f"FFmpeg extraction failed: {e.stderr.decode()}"}
            finally:
                if os.path.exists(temp_wav):
                    os.remove(temp_wav)

        max_freqs = []
        noises = []
        
        for i, start_p in enumerate(sample_points):
            if not full_scan and len(sample_points) > 1:
                print_progress(10 + i * 15, f"Analyzing fragment {i+1}/{len(sample_points)}...")
            
            y, sr = librosa.load(filepath, sr=None, duration=duration, offset=start_p)
            if len(y) == 0: continue
            
            n_fft = 2048
            D = np.abs(librosa.stft(y, n_fft=n_fft))
            S_dB = librosa.amplitude_to_db(D, ref=n_fft/2)
            freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)
            mean_db = np.mean(S_dB, axis=1)
            
            threshold_db = -60
            db_mask = mean_db > threshold_db
            if np.any(db_mask):
                f_idx = np.where(db_mask)[0][-1]
                max_freqs.append(float(freqs[f_idx] / 1000))
            else:
                max_freqs.append(0.0)
            
            noise_floor = np.percentile(mean_db, 10)
            noises.append(float(noise_floor))

        if not max_freqs:
            raise Exception("Could not analyze any audio fragments")

        avg_max_freq = float(np.mean(max_freqs))
        peak_max_freq = float(np.max(max_freqs))
        avg_noise = float(np.mean(noises))
        
        if peak_max_freq < 6:
            base_br = 64
            quality = "Extremely Low (Old Tape/Poor Lo-Fi)"
        elif peak_max_freq < 10:
            base_br = 96
            quality = "Very Low (Voice/Dictaphone)"
        elif peak_max_freq < 13:
            base_br = 112
            quality = "Low"
        elif peak_max_freq < 15:
            base_br = 128
            quality = "Medium-Low"
        elif peak_max_freq < 17:
            base_br = 160
            quality = "Medium"
        elif peak_max_freq < 19:
            base_br = 192
            quality = "High"
        else:
            base_br = 256
            quality = "Excellent"

        bitrates = [64, 96, 112, 128, 160, 192, 256, 320]
        if avg_noise > -45 and base_br > 96:
            current_idx = bitrates.index(base_br)
            recommended_bitrate = int(bitrates[max(0, current_idx - 1)])
            quality += " (Noisy)"
        else:
            recommended_bitrate = int(base_br)

        file_size = os.path.getsize(filepath)
        channels = 0
        current_bitrate = 0
        try:
            from mutagen.mp3 import MP3
            audio = MP3(filepath)
            current_bitrate = int(audio.info.bitrate / 1000)
            channels = int(audio.info.channels)
        except:
            pass

        print_progress(100, "Done!")
        return {
            "status": "success",
            "max_frequency": round(float(peak_max_freq), 1),
            "avg_max_frequency": round(float(avg_max_freq), 1),
            "noise_floor": round(float(avg_noise), 1),
            "quality": quality,
            "recommended_bitrate": int(recommended_bitrate),
            "current_bitrate": int(current_bitrate),
            "channels": int(channels),
            "file_size": int(file_size),
            "duration": float(total_duration),
            "is_full_scan": bool(full_scan),
            "sample_points": [round(float(p), 1) for p in sample_points]
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

if __name__ == "__main__":
    def clean_json(obj):
        import numpy as np
        if isinstance(obj, dict):
            return {k: clean_json(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [clean_json(v) for v in obj]
        elif isinstance(obj, (float, np.floating)):
            if np.isinf(obj) or np.isnan(obj):
                return 0.0
            return float(obj)
        elif isinstance(obj, (int, np.integer)):
            return int(obj)
        return obj

    try:
        if len(sys.argv) < 2:
            print(json.dumps({"status": "error", "error": "No file path provided"}))
            sys.exit(1)
        
        filepath = sys.argv[1]
        full_scan = "--full" in sys.argv
        
        offset_arg = None
        duration_arg = None
        
        try:
            if "--offset" in sys.argv:
                idx = sys.argv.index("--offset")
                offset_arg = float(sys.argv[idx + 1])
                
            if "--duration" in sys.argv:
                idx = sys.argv.index("--duration")
                duration_arg = float(sys.argv[idx + 1])
        except (ValueError, IndexError) as e:
            print(json.dumps({"status": "error", "error": f"Invalid arguments: {str(e)}"}))
            sys.exit(1)
        
        zoom_mode = "--zoom" in sys.argv
            
        result = analyze_audio_file(filepath, full_scan, offset_arg, duration_arg, zoom_mode)
        print(json.dumps(clean_json(result)), flush=True)
    except Exception as e:
        print(json.dumps({"status": "error", "error": f"CRASH: {str(e)}"}), flush=True)
        sys.exit(1)
