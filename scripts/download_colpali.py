"""Download and cache ColPali model weights (~6GB).

Downloads:
  1. vidore/colpali-v1.2 (LoRA adapter + processor configs)
  2. vidore/colpaligemma-3b-pt-448-base (Base model weights ~6GB)
Then verifies the model can be loaded successfully.
"""

import os
import sys
import time

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

print("=" * 60)
print("Starting ColPali Model Download")
print("=" * 60)

try:
    from huggingface_hub import snapshot_download
except ImportError:
    print("ERROR: huggingface_hub is not installed.")
    sys.exit(1)

start_time = time.time()

# 1. Download adapter
print("\n[1/3] Downloading vidore/colpali-v1.2 (adapter & configs)...")
adapter_path = snapshot_download(
    repo_id="vidore/colpali-v1.2",
)
print(f"  -> Adapter cached at: {adapter_path}")

# 2. Download base model (~6GB)
print("\n[2/3] Downloading vidore/colpaligemma-3b-pt-448-base (~6GB)...")
print("  This may take a few moments (resuming from previously cached files)...")
base_path = snapshot_download(
    repo_id="vidore/colpaligemma-3b-pt-448-base",
)
print(f"  -> Base model cached at: {base_path}")

elapsed = time.time() - start_time
print(f"\nDownload completed in {elapsed:.1f} seconds ({elapsed / 60:.2f} minutes).")

# 3. Verify loading
print("\n[3/3] Verifying model loading via colpali-engine...")
try:
    import torch
    from colpali_engine.models import ColPali, ColPaliProcessor

    print("  Loading processor...")
    processor = ColPaliProcessor.from_pretrained("vidore/colpali-v1.2")
    print("  Processor loaded successfully.")

    print("  Loading model...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.bfloat16
    print(f"  Using device={device}, dtype={dtype}")

    model = ColPali.from_pretrained(
        "vidore/colpali-v1.2",
        torch_dtype=dtype,
        device_map=device,
        low_cpu_mem_usage=True,
    ).eval()
    print("  ColPali model loaded successfully into memory!")
    print("\n" + "=" * 60)
    print("ALL DONE! ColPali is fully downloaded and verified.")
    print("=" * 60)
except Exception as e:
    print(f"\nModel verification warning (weights are downloaded): {e}")
