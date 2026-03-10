import os
import time
import base64
import tempfile
import subprocess
import inspect
from functools import lru_cache
from io import BytesIO

import streamlit as st
import torch
import numpy as np
import librosa
import soundfile as sf
import sys
from resemble_import_shims import apply_resemble_import_shims
from torchaudio_shim import ensure_torchaudio_shim

def _qp_get_str(key, default, allowed=None):
    try:
        value = st.query_params.get(key, default)
    except Exception:
        return default
    if isinstance(value, list):
        value = value[-1] if value else default
    value = str(value)
    if allowed is not None and value not in allowed:
        return default
    return value

def _qp_get_int(key, default, allowed=None):
    try:
        value = int(_qp_get_str(key, str(default)))
    except Exception:
        return default
    if allowed is not None and value not in allowed:
        return default
    return value

def _qp_get_float(key, default, min_value=None, max_value=None):
    try:
        value = float(_qp_get_str(key, str(default)))
    except Exception:
        return default
    if min_value is not None and value < min_value:
        return default
    if max_value is not None and value > max_value:
        return default
    return value

def _qp_get_bool(key, default):
    value = _qp_get_str(key, "1" if default else "0").strip().lower()
    return value in ("1", "true", "yes", "on")

# --- Fix for Resemble Enhance Import ---
# Add the directory containing mock_deepspeed to sys.path
script_dir = os.path.dirname(os.path.abspath(__file__))
resemble_server_path = os.path.join(script_dir, "resemble_testing_server")
if resemble_server_path not in sys.path:
    sys.path.append(resemble_server_path)

# Apply DeepSpeed hack for Mac
try:
    import mock_deepspeed
    mock_deepspeed.apply_mock()
except Exception as e:
    st.warning(f"Failed to apply DeepSpeed mock: {e}")

# --- Robust DeepSpeed Hack for Mac ---
try:
    import mock_deepspeed
    mock_deepspeed.apply_mock()
except ImportError:
    pass

# Mirror resemble_worker import shims so lab and audit behave the same.
apply_resemble_import_shims(emit_tqdm_progress=False, debug=False)

# Keep Resemble import behavior aligned with resemble_worker.py.
ensure_torchaudio_shim(debug=False)

# Try to import Resemble Enhance if available
RESEMBLE_IMPORT_ERROR = None
RESEMBLE_RUN_DIR = None
RESEMBLE_EXPERIMENTAL_MODES = os.environ.get("LAB_EXPERIMENTAL_RESEMBLE_MODES", "").strip().lower() in ("1", "true", "yes", "on")
try:
    import resemble_enhance.enhancer.inference as resemble_inference_module
    from resemble_enhance.enhancer.download import download as resemble_download
    from resemble_enhance.enhancer.train import Enhancer as ResembleEnhancer
    from resemble_enhance.enhancer.train import HParams as ResembleHParams
    from resemble_enhance.enhancer.inference import denoise, enhance
    from resemble_enhance.enhancer.download import REPO_DIR as RESEMBLE_REPO_DIR

    @lru_cache(maxsize=None)
    def _load_enhancer_relaxed(run_dir, device):
        if run_dir is None:
            run_dir = resemble_download()
        hp = ResembleHParams.load(run_dir)
        enhancer = ResembleEnhancer(hp)
        model_path = run_dir / "ds" / "G" / "default" / "mp_rank_00_model_states.pt"
        state_dict = torch.load(model_path, map_location="cpu")["module"]
        enhancer.load_state_dict(state_dict, strict=False)
        enhancer.eval()
        enhancer.to(device)
        return enhancer

    resemble_inference_module.load_enhancer = _load_enhancer_relaxed

    candidate_run_dir = RESEMBLE_REPO_DIR / "enhancer_stage2"
    candidate_weights = candidate_run_dir / "ds" / "G" / "default" / "mp_rank_00_model_states.pt"
    if candidate_weights.exists():
        RESEMBLE_RUN_DIR = candidate_run_dir

    RESEMBLE_AVAILABLE = True
except ImportError as e:
    RESEMBLE_IMPORT_ERROR = str(e)
    RESEMBLE_AVAILABLE = False

# Try to import VoiceFixer if available
try:
    from voicefixer import VoiceFixer
    VOICEFIXER_AVAILABLE = True
except ImportError:
    VOICEFIXER_AVAILABLE = False

# --- Progress Tracking Helper ---
class st_tqdm:
    """A simple wrapper to hook tqdm-like loops into streamlit progress bars."""
    def __init__(self, iterable=None, total=None, desc="Processing", status_text=None):
        self.iterable = iterable
        self.total = total or (len(iterable) if iterable is not None else 0)
        self.desc = desc
        self.current = 0
        self.status = status_text
        self.progress_bar = st.progress(0)
        self.start_time = time.time()
        
    def __iter__(self):
        for item in self.iterable:
            yield item
            self.update(1)
            
    def update(self, n=1):
        self.current += n
        if self.total > 0:
            pct = min(1.0, self.current / self.total)
            elapsed = time.time() - self.start_time
            eta = (elapsed / self.current) * (self.total - self.current) if self.current > 0 else 0
            msg = f"{self.desc}: {int(pct*100)}% (ETA: {eta:.1f}s)"
            if self.status:
                self.status.write(msg)
            self.progress_bar.progress(pct, text=msg)

    def close(self):
        self.progress_bar.empty()

# Monkey-patch tqdm in modules if possible, or pass it explicitly

# --- Page Config ---
st.set_page_config(
    page_title="Audio Laboratory",
    page_icon="🔬",
    layout="wide"
)

# --- Global Styles ---
st.markdown("""
<style>
    .stApp {
        background-color: #f8fafc;
    }
    /* Reduce top padding to raise title */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 2rem !important;
    }
    .stSidebar {
        background-color: #f1f5f9 !important;
    }
    /* Lift sidebar content even higher */
    [data-testid="stSidebarContent"] {
        padding-top: 0.5rem !important;
    }
    .stSidebar [data-testid="stVerticalBlock"] {
        gap: 0.5rem !important;
    }
    .stSidebar h1, .stSidebar h2, .stSidebar h3 {
        margin-top: 0 !important;
        margin-bottom: 0.5rem !important;
        padding-top: 0 !important;
    }
    .stButton>button {
        width: 100%;
        border-radius: 12px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1px;
        transition: all 0.2s;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.2);
    }
</style>
""", unsafe_allow_html=True)

# --- Common Helpers ---
def get_bitrate(file_path):
    try:
        cmd = [
            "ffprobe", "-v", "error", "-select_streams", "a:0",
            "-show_entries", "stream=bit_rate", "-of",
            "default=noprint_wrappers=1:nokey=1", file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        br = result.stdout.strip()
        if not br or br == 'N/A':
            return "128k"
        return f"{int(br)//1000}k"
    except:
        return "128k"

def wav_to_mp3(wav_bytes, bitrate_str):
    if not wav_bytes: return None
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as twav:
        twav.write(wav_bytes)
        twav_path = twav.name
    
    tmp_mp3 = twav_path.replace(".wav", ".mp3")
    try:
        subprocess.run([
            "ffmpeg", "-y", "-i", twav_path, "-codec:a", "libmp3lame", "-b:a", bitrate_str, tmp_mp3
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with open(tmp_mp3, "rb") as f:
            data = f.read()
        return data
    except Exception as e:
        st.error(f"FFmpeg Error: {e}")
        return wav_bytes
    finally:
        if os.path.exists(twav_path): os.remove(twav_path)
        if os.path.exists(tmp_mp3): os.remove(tmp_mp3)

def get_bytes(wav_arr, rate):
    with BytesIO() as buffer:
        sf.write(buffer, wav_arr.T, rate, format="WAV")
        return buffer.getvalue()

def render_comparison_player(original_bytes, versions: dict):
    """
    Renders a player that can switch between Original and multiple processed versions.
    versions: dict { 'key': {'label': 'Label', 'bytes': b'...', 'color': '#hex'} }
    """
    import base64
    
    # Encode Original
    original_b64 = base64.b64encode(original_bytes).decode()
    
    # Prepare sources and buttons logic
    js_sources = f"'original': 'data:audio/wav;base64,{original_b64}',"
    js_labels = "'original': 'ORIGINAL',"
    
    buttons_html = f"""
    <button id="btn-original" onclick="switchTo('original')" 
        style="flex: 1; padding: 15px; border-radius: 12px; border: none; background: #e2e8f0; color: #475569; font-weight: bold; cursor: pointer; transition: 0.2s;">
        (A) ORIGINAL
    </button>
    """
    
    # Track the first valid processed version to set as default
    default_key = 'original'
    
    valid_versions = {}
    
    idx = 0
    chars = ['B', 'C', 'D', 'E', 'F']
    
    for key, data in versions.items():
        if data.get('bytes') is None: continue
        
        b64 = base64.b64encode(data['bytes']).decode()
        valid_versions[key] = data
        
        js_sources += f"'{key}': 'data:audio/wav;base64,{b64}',"
        js_labels += f"'{key}': '{data['label'].upper()}',"
        
        # Color logic
        color = data.get('color', '#3b82f6')
        label_char = chars[idx] if idx < len(chars) else '?'
        
        buttons_html += f"""
        <button id="btn-{key}" onclick="switchTo('{key}')" 
            style="flex: 1; padding: 15px; border-radius: 12px; border: none; background: #e2e8f0; color: #475569; font-weight: bold; cursor: pointer; transition: 0.2s;">
            ({label_char}) {data['label']}
        </button>
        """
        
        if default_key == 'original':
            default_key = key
        
        idx += 1

    player_html = f"""
    <div style="background: #ffffff; padding: 30px; border-radius: 20px; border: 1px solid #e2e8f0; margin-top: 30px; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05);">
        <div style="display: flex; flex-direction: column; gap: 20px; align-items: center;">
            <audio id="main-player" controls style="width: 100%; height: 50px;"></audio>
            
            <div style="display: flex; gap: 10px; width: 100%; flex-wrap: wrap;">
                {buttons_html}
            </div>
            
            <div style="width: 100%; text-align: center; color: #64748b; font-family: sans-serif; font-size: 14px; font-weight: bold; padding: 10px; background: #f1f5f9; border-radius: 10px;">
                Currently Playing: <span id="status-label" style="color: #3b82f6;">...</span>
            </div>
        </div>
    </div>

    <script>
        const audio = document.getElementById('main-player');
        const label = document.getElementById('status-label');
        
        const sources = {{ {js_sources} }};
        const labels = {{ {js_labels} }};
        
        let currentMode = '{default_key}';
        
        // Init
        audio.src = sources[currentMode];
        updateUI(currentMode);
        
        function switchTo(mode) {{
            if (currentMode === mode) return;
            const time = audio.currentTime;
            const isPaused = audio.paused;
            
            currentMode = mode;
            audio.src = sources[mode];
            audio.currentTime = time;
            if (!isPaused) audio.play();
            
            updateUI(mode);
        }}
        
        function updateUI(mode) {{
            // Reset all buttons
            const allBtns = document.querySelectorAll('button[id^="btn-"]');
            allBtns.forEach(btn => {{
                btn.style.background = '#e2e8f0';
                btn.style.color = '#475569';
                btn.style.boxShadow = 'none';
            }});
            
            // Highlight active
            const activeBtn = document.getElementById('btn-' + mode);
            if (activeBtn) {{
                activeBtn.style.background = '#3b82f6';
                activeBtn.style.color = 'white';
                activeBtn.style.boxShadow = '0 4px 14px rgba(59, 130, 246, 0.3)';
            }}
            
            label.innerText = labels[mode] || mode;
            label.style.color = (mode === 'original') ? '#64748b' : '#3b82f6';
        }}
        
        // Initial set
        updateUI(currentMode);
    </script>
    """
    st.components.v1.html(player_html, height=len(versions)*10 + 350) # dynamic height adjustment

# --- VoiceFixer Logic ---
@st.cache_resource
def init_voicefixer():
    if not VOICEFIXER_AVAILABLE:
        return None
    return VoiceFixer()

def restore_inmem_compat(v_fixer, audio_in, mode, use_gpu, tqdm_factory=None):
    kwargs = {"mode": mode, "cuda": use_gpu}
    try:
        if tqdm_factory and "tqdm" in inspect.signature(v_fixer.restore_inmem).parameters:
            kwargs["tqdm"] = tqdm_factory
    except (TypeError, ValueError):
        pass
    try:
        return v_fixer.restore_inmem(audio_in, **kwargs)
    except RuntimeError as e:
        if kwargs.get("cuda") and "no cuda device found" in str(e).lower():
            kwargs["cuda"] = False
            return v_fixer.restore_inmem(audio_in, **kwargs)
        raise

# --- Resemble Logic ---
@st.cache_resource
def get_resemble_device():
    if torch.cuda.is_available():
        return "cuda"
    elif torch.backends.mps.is_available():
        return "mps"
    return "cpu"

def process_resemble(input_path, gain, mix, re_mode="denoise"):
    if not RESEMBLE_AVAILABLE:
        raise RuntimeError("Resemble Enhance is unavailable in this environment.")

    device = get_resemble_device()
    audio_np, sr = sf.read(input_path)
    if audio_np.dtype != np.float32:
        audio_np = audio_np.astype(np.float32)
    if audio_np.ndim > 1:
        audio_np = np.mean(audio_np, axis=1)
    
    dwav = torch.from_numpy(audio_np)
    if gain != 1.0:
        dwav = dwav * gain
    
    with torch.no_grad():
        # --- MONKEY PATCH RESEMBLE TRANGE ---
        import resemble_enhance.inference as res_inf
        orig_trange = res_inf.trange
        res_inf.trange = lambda *args, **kwargs: st_tqdm(range(*args), desc="Resemble Enhance")
        
        try:
            if re_mode == "enhance":
                if RESEMBLE_RUN_DIR is not None:
                    denoised_wav, new_sr = enhance(dwav, sr, device, run_dir=RESEMBLE_RUN_DIR)
                else:
                    denoised_wav, new_sr = enhance(dwav, sr, device)
            elif re_mode == "denoise_enhance":
                if RESEMBLE_RUN_DIR is not None:
                    denoised_wav, new_sr = denoise(dwav, sr, device, run_dir=RESEMBLE_RUN_DIR)
                    denoised_wav, new_sr = enhance(denoised_wav, new_sr, device, run_dir=RESEMBLE_RUN_DIR)
                else:
                    denoised_wav, new_sr = denoise(dwav, sr, device)
                    denoised_wav, new_sr = enhance(denoised_wav, new_sr, device)
            else:
                if RESEMBLE_RUN_DIR is not None:
                    denoised_wav, new_sr = denoise(dwav, sr, device, run_dir=RESEMBLE_RUN_DIR)
                else:
                    denoised_wav, new_sr = denoise(dwav, sr, device)
        finally:
            # Restore original trange
            res_inf.trange = orig_trange
    
    denoised_wav = denoised_wav.cpu()
    if denoised_wav.ndim > 1:
        denoised_wav = denoised_wav.squeeze()

    if mix < 1.0:
        min_len = min(dwav.shape[0], denoised_wav.shape[0])
        mixed_wav = denoised_wav[:min_len] * mix + dwav[:min_len] * (1 - mix)
        return mixed_wav.numpy(), new_sr
    
    return denoised_wav.numpy(), new_sr

# --- Main App ---
st.title("🔬 Audio Laboratory")
st.markdown("##### High-Fidelity Speech Restoration & Optimization Suite")

# --- Sidebar Navigation ---
with st.sidebar:
    st.title("Navigation")
    module_options = ["🔊 VoiceFixer", "🧪 Resemble Enhance"]
    module_choice_saved = _qp_get_str("module", module_options[0], allowed=module_options)
    module_choice = st.radio(
        "Choose Module:",
        options=module_options,
        index=module_options.index(module_choice_saved)
    )
    st.markdown("---")

# --- Content Logic ---
if "VoiceFixer" in module_choice or "Resemble" in module_choice:
    v_fixer_avail = VOICEFIXER_AVAILABLE
    resemble_avail = RESEMBLE_AVAILABLE
    
    st.header(f"{module_choice}", help="Toggle 'Compare Models' in the sidebar to run both VoiceFixer and Resemble side-by-side.")
    if "Resemble" in module_choice and not resemble_avail:
        st.error("Resemble Enhance is unavailable: required dependencies are not installed in this environment.")
    
    with st.sidebar:
        vf_mode = 0
        compare_all_modes = False
        re_mode = "denoise"
        re_gain = 1.0
        re_mix = 100
        do_compare = False
        
        if "Voice" in module_choice:
            st.markdown("### VoiceFixer Settings")
            vf_mode_default = _qp_get_int("vf_mode", 0, allowed=[0, 1, 2])
            vf_mode = st.radio(
                "VF Quality Mode:", 
                [0, 1, 2], 
                format_func=lambda x: ["Standard (0)", "Enhanced (1)", "Deep (2)"][x],
                index=[0, 1, 2].index(vf_mode_default)
            )
            compare_all_modes_default = _qp_get_bool("vf_all_modes", False)
            compare_all_modes = st.checkbox(
                "🎛️ Compare All Modes (0, 1, 2)", 
                value=compare_all_modes_default,
                help="Process and compare results from all three VoiceFixer modes."
            )
        else:
            st.markdown("### Resemble Settings")
            re_mode_saved = _qp_get_str("re_mode", "denoise", allowed=["denoise", "enhance", "denoise_enhance"])
            if RESEMBLE_EXPERIMENTAL_MODES:
                re_mode = st.selectbox(
                    "RE Mode",
                    options=["denoise", "enhance", "denoise_enhance"],
                    format_func=lambda x: {
                        "denoise": "Denoise",
                        "enhance": "Enhance",
                        "denoise_enhance": "Denoise + Enhance"
                    }[x],
                    index=["denoise", "enhance", "denoise_enhance"].index(re_mode_saved)
                )
            else:
                re_mode = "denoise"
            re_gain_default = _qp_get_float("re_gain", 1.0, min_value=0.5, max_value=3.0)
            re_mix_default = _qp_get_int("re_mix", 100)
            if re_mix_default < 0 or re_mix_default > 100:
                re_mix_default = 100
            re_gain = st.slider("RE Input Gain", 0.5, 3.0, float(re_gain_default), 0.1)
            re_mix = st.slider("RE Mix (Wet)", 0, 100, int(re_mix_default))
        
        st.markdown("---")
        st.markdown("### Hardware")
        vf_dev_options = ["Auto", "CPU 🐌", "GPU (MPS/CUDA) 🚀"]
        vf_dev_default = _qp_get_str("device", "Auto", allowed=vf_dev_options)
        vf_dev_label = st.selectbox(
            "Device:", 
            vf_dev_options,
            index=vf_dev_options.index(vf_dev_default)
        )
        if vf_dev_label == "Auto":
            if torch.cuda.is_available(): vf_device = "cuda"
            elif torch.backends.mps.is_available(): vf_device = "mps"
            else: vf_device = "cpu"
        elif "CPU" in vf_dev_label: vf_device = "cpu"
        else: vf_device = "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")
        
        if vf_device == "mps": st.success("Using Apple MPS ✅")
        elif vf_device == "cuda": st.success("Using NVIDIA CUDA ✅")
        else: st.info("Using CPU 🐌")

        st.markdown("---")
        st.markdown("### Comparison & Mode")
        do_compare_default = _qp_get_bool("compare", False)
        do_compare = st.checkbox(
            "🧪 Compare with Resemble" if "Voice" in module_choice else "🔊 Compare with VoiceFixer",
            value=do_compare_default,
            help="Process the file with BOTH models to compare quality.",
            disabled=("Voice" in module_choice and not resemble_avail)
        )
        if "Voice" in module_choice and not resemble_avail:
            st.caption("Resemble disabled: missing dependencies in current venv.")

        # Persist current UI choices across page refresh via URL query params.
        st.query_params["module"] = module_choice
        st.query_params["device"] = vf_dev_label
        st.query_params["compare"] = "1" if do_compare else "0"
        st.query_params["vf_mode"] = str(vf_mode)
        st.query_params["vf_all_modes"] = "1" if compare_all_modes else "0"
        st.query_params["re_mode"] = re_mode
        st.query_params["re_gain"] = str(re_gain)
        st.query_params["re_mix"] = str(re_mix)

    # Main Area Logic (Dedent)
    vf_file = st.file_uploader("Upload audio to Laboratory", type=["wav", "mp3", "m4a", "flac"], key="lab_upload")
    auto_process = st.checkbox("⚡ Auto-process on upload", value=True, help="Immediately start processing as soon as a file is uploaded.")
    
    if vf_file:
        # Smart trigger: only auto-run if file is new
        file_key = f"last_file_{vf_file.name}_{vf_file.size}"
        is_new_file = st.session_state.get("last_file_processed") != file_key
        
        process_clicked = st.button("🚀 Process & Compare" if do_compare else "🚀 Run Processing", type="primary")
        
        if process_clicked or (auto_process and is_new_file):
            st.session_state["last_file_processed"] = file_key
            with st.status("🛠️ Processing...", expanded=True) as status:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_in:
                    tmp_in.write(vf_file.getvalue())
                    tmp_path = tmp_in.name
                
                target_br = get_bitrate(tmp_path)
                audio_orig, _ = librosa.load(tmp_path, sr=44100, mono=True)
                use_gpu = (vf_device == "cuda" and torch.cuda.is_available())
                
                try:
                    main_model = "VF" if "Voice" in module_choice else "RE"
                    processed_versions = {} # Dict for 'render_comparison_player'
                    
                    v_fixer = init_voicefixer()
                    
                    # Logic Branch: Compare All Modes vs Standard
                    if compare_all_modes and "Voice" in module_choice:
                        # --- COMPARE ALL MODES (0/1/2) ---
                        st.write("🏃 Running Multi-Mode Comparison...")
                        
                        modes_to_run = [0, 1, 2]
                        audio_in = audio_orig.astype(np.float32)
                        
                        for m in modes_to_run:
                            st.write(f"Processing Mode {m}...")
                            t_start = time.time()
                            # Reset model state just in case
                            v_fixer._model = v_fixer._model.float()
                            pred_vf = restore_inmem_compat(
                                v_fixer,
                                audio_in,
                                mode=m,
                                use_gpu=use_gpu,
                                tqdm_factory=lambda x: st_tqdm(x, desc=f"VF Mode {m}")
                            )
                            bytes_vf = get_bytes(pred_vf, 44100)
                            t_end = time.time() - t_start
                            
                            processed_versions[f'mode{m}'] = {
                                'label': f'VF Mode {m}',
                                'bytes': bytes_vf,
                                'time': t_end,
                                'color': ['#3b82f6', '#8b5cf6', '#ec4899'][m] # Different colors for modes
                            }

                    else:
                        # --- STANDARD / CROSS-MODEL COMPARISON ---
                        
                        # Process B (VoiceFixer)
                        if main_model == "VF" or do_compare:
                            st.write("🏃 Running VoiceFixer...")
                            t_start = time.time()
                            audio_in = audio_orig.astype(np.float32)
                            pred_vf = restore_inmem_compat(
                                v_fixer,
                                audio_in,
                                mode=vf_mode,
                                use_gpu=use_gpu,
                                tqdm_factory=lambda x: st_tqdm(x, desc="VoiceFixer")
                            )
                            res_b_bytes = get_bytes(pred_vf, 44100)
                            t_b = time.time() - t_start
                            
                            processed_versions['vf'] = {
                                'label': 'VoiceFixer',
                                'bytes': res_b_bytes,
                                'time': t_b
                            }
                            
                        # Process C (Resemble)
                        if main_model == "RE" or do_compare:
                            st.write("🏃 Running Resemble Enhance...")
                            t_start = time.time()
                            res_re, sr = process_resemble(tmp_path, re_gain, re_mix / 100.0, re_mode=re_mode)
                            res_re_bytes = get_bytes(res_re, sr)
                            t_c = time.time() - t_start
                            
                            processed_versions['re'] = {
                                'label': 'Resemble',
                                'bytes': res_re_bytes,
                                'time': t_c,
                                'color': '#10b981' # Green for Resemble
                            }

                    st.write("✅ Ready!")
                    status.update(label="Processing Complete!", state="complete", expanded=True)
                    
                    # Stats Display
                    cols = st.columns(len(processed_versions))
                    for idx, (key, data) in enumerate(processed_versions.items()):
                        if idx < len(cols):
                            cols[idx].metric(f"{data['label']} Time", f"{data['time']:.2f}s")
                    
                    # Dynamic Player
                    render_comparison_player(vf_file.getvalue(), processed_versions)
                    
                    # Downloads
                    st.markdown("### 💾 Download Results (MP3)")
                    dcols = st.columns(len(processed_versions))
                    for idx, (key, data) in enumerate(processed_versions.items()):
                        if idx < len(dcols):
                            mp3_data = wav_to_mp3(data['bytes'], target_br)
                            fname = f"{key}_{vf_file.name.rsplit('.', 1)[0]}.mp3"
                            dcols[idx].download_button(f"Download {data['label']} (MP3)", mp3_data, fname)                        
                except Exception as e:
                    st.error(f"Error: {e}")
                    st.exception(e)
                finally:
                    if os.path.exists(tmp_path): os.remove(tmp_path)
