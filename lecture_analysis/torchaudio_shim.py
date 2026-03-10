"""Shared lightweight torchaudio shim for environments without torchaudio."""

import sys
from types import ModuleType

import torch
import torch.nn.functional as torch_f


def ensure_torchaudio_shim(debug=False):
    """Provide a minimal torchaudio shim when torchaudio is unavailable."""
    try:
        import torchaudio  # noqa: F401
        return False
    except Exception:
        pass

    if debug:
        print("DEBUG: torchaudio not found; enabling lightweight shim", file=sys.stderr)

    ta_mod = ModuleType("torchaudio")
    ta_mod.__path__ = []
    ta_func = ModuleType("torchaudio.functional")
    ta_transforms = ModuleType("torchaudio.transforms")

    def resample(wav, orig_freq, new_freq, **_kwargs):
        if int(orig_freq) == int(new_freq):
            return wav
        if wav.dim() < 1:
            raise ValueError(f"Expected tensor with at least 1 dim for resample, got shape {tuple(wav.shape)}")
        target_len = max(1, int(round(wav.shape[-1] * float(new_freq) / float(orig_freq))))
        lead_shape = wav.shape[:-1]
        x = wav.reshape(-1, 1, wav.shape[-1])
        y = torch_f.interpolate(x, size=target_len, mode="linear", align_corners=False)
        return y.reshape(*lead_shape, target_len)

    class MelSpectrogram:
        def __init__(
            self,
            sample_rate,
            n_fft,
            win_length=None,
            hop_length=None,
            n_mels=80,
            f_min=0.0,
            f_max=None,
            power=2.0,
            **_kwargs,
        ):
            self.sample_rate = sample_rate
            self.n_fft = n_fft
            self.win_length = win_length or n_fft
            self.hop_length = hop_length or max(1, self.win_length // 4)
            self.n_mels = n_mels
            self.f_min = f_min
            self.f_max = f_max if f_max is not None else sample_rate // 2
            self.power = power

        def __call__(self, wav):
            if wav.dim() < 1:
                raise ValueError(f"Expected tensor with at least 1 dim for MelSpectrogram, got shape {tuple(wav.shape)}")
            lead_shape = wav.shape[:-1]
            flat = wav.reshape(-1, wav.shape[-1])
            window = torch.hann_window(self.win_length, device=wav.device, dtype=wav.dtype)
            mels = []
            for i in range(flat.shape[0]):
                stft = torch.stft(
                    flat[i],
                    n_fft=self.n_fft,
                    hop_length=self.hop_length,
                    win_length=self.win_length,
                    window=window,
                    center=True,
                    return_complex=True,
                ).abs()
                # Approximate mel compression by resizing freq bins to n_mels.
                x = stft[None, None, :, :]
                m = torch_f.interpolate(
                    x,
                    size=(self.n_mels, stft.shape[-1]),
                    mode="bilinear",
                    align_corners=False,
                )[0, 0]
                mels.append(m)
            mel = torch.stack(mels, dim=0)
            return mel.reshape(*lead_shape, self.n_mels, mel.shape[-1])

    ta_func.resample = resample
    ta_transforms.MelSpectrogram = MelSpectrogram
    ta_mod.functional = ta_func
    ta_mod.transforms = ta_transforms

    sys.modules["torchaudio"] = ta_mod
    sys.modules["torchaudio.functional"] = ta_func
    sys.modules["torchaudio.transforms"] = ta_transforms
    return True
