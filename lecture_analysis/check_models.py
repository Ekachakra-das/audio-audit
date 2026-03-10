
from denoiser import pretrained
try:
    model = pretrained.dns48()
    print(f"dns48 sample_rate: {model.sample_rate}")
except Exception as e:
    print(f"dns48 failed: {e}")

try:
    model = pretrained.dns64()
    print(f"dns64 sample_rate: {model.sample_rate}")
except Exception as e:
    print(f"dns64 failed: {e}")
