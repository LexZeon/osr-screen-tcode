"""Reproduce the separately distributed optional NeuFlow v2 ONNX artifact.

Developer-only: run in an isolated environment with torch==2.6.0 (CPU build),
onnx==1.17.0, safetensors==0.5.3, huggingface-hub==0.34.4 and numpy==2.2.6.
This tool never installs dependencies or modifies the application's environment.
It downloads pinned, checksum-verified upstream code and safetensors into a
temporary workspace, exports one graph, and records public provenance beside it.
Upstream code/weights: Apache-2.0; see THIRD_PARTY_NOTICES.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from urllib.request import urlopen


CODE_COMMIT = "204b5e3744461d90303b9ff82caa7a1bb56a2ca2"
WEIGHTS_REVISION = "79ae2f4589456d4d369aaef4955c7db5918c3436"
WEIGHTS_SHA256 = "db63964dc403b3ddac1ed3283ab001e36232ac0c8b73b450be722bb398347e4c"
SOURCE_HASHES = {
    "NeuFlow/backbone_v7.py": "06becb2d76b2d27b672654e6140a4a6adc05557762a7f404136a684dbc9154cc",
    "NeuFlow/config.py": "3ef08d2119b3cf24fac2dabfb44e889d7062f38e42bebab378dbe72a413c0c4b",
    "NeuFlow/corr.py": "6d3b7fc2dbfabd54b2cdfa60c617d435a6015cc16879d1642fd84c86610418df",
    "NeuFlow/matching.py": "daac0c5bdb79483155df28dd777bc81d3a0b83f389de07f9b6e990ea3f8c06d4",
    "NeuFlow/neuflow.py": "decc143fd427f7a564c51bb6751febe2381577a7ed8d14481f92ec782a89dbbb",
    "NeuFlow/refine.py": "aefc1410ea21c3d94093fa50cfe62fd095e13e594cd41c5cda48bd9982f0a0d9",
    "NeuFlow/transformer.py": "f2f52b41604976de02ec3f861fc191ff3f3c968ff24968ad8614e8db3a811ca1",
    "NeuFlow/upsample.py": "c7cc150a61aa85f3b2c221386948df0789e4979e8896ea8976d616ae4c496173",
    "NeuFlow/utils.py": "dd00fe3d1f68dc58eb671b124cf8bbf43975a5cc0e07d939708debba85e4049c",
    "LICENSE": "c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4",
}


def fetch_verified(url: str, destination: Path, digest: str, maximum: int) -> None:
    with urlopen(url, timeout=30) as response:
        data = response.read(maximum + 1)
    if len(data) > maximum or hashlib.sha256(data).hexdigest() != digest:
        raise ValueError("Upstream artifact checksum mismatch")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)


def export(destination: Path) -> dict:
    import numpy as np
    import onnx
    import torch
    from safetensors.torch import load_file

    destination = destination.resolve()
    provenance_path = destination.with_suffix(".export.json")
    if destination.exists() or provenance_path.exists():
        raise FileExistsError("Refusing to replace an existing artifact or report")
    if torch.__version__.split("+")[0] != "2.6.0" or onnx.__version__ != "1.17.0":
        raise RuntimeError("Use the pinned isolated export environment")
    destination.parent.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(4)
    torch.manual_seed(0)
    with tempfile.TemporaryDirectory(prefix="osr-neuflow-convert-") as directory:
        workspace = Path(directory)
        for relative, digest in SOURCE_HASHES.items():
            fetch_verified(f"https://raw.githubusercontent.com/neufieldrobotics/NeuFlow_v2/{CODE_COMMIT}/{relative}",
                           workspace / relative, digest, 256 * 1024)
        weights_path = workspace / "model.safetensors"
        fetch_verified(f"https://huggingface.co/Study-is-happy/neuflow-v2/resolve/{WEIGHTS_REVISION}/model.safetensors",
                       weights_path, WEIGHTS_SHA256, 36155296)
        sys.path.insert(0, str(workspace))
        try:
            from NeuFlow.neuflow import NeuFlow

            model = NeuFlow().eval()
            model.load_state_dict(load_file(str(weights_path)), strict=True)
            model.init_bhwd(1, 384, 640, "cpu", amp=False)

            class Wrapper(torch.nn.Module):
                def __init__(self, inner):
                    super().__init__()
                    self.model = inner

                def forward(self, previous_bgr, current_bgr):
                    # Upstream divides its inputs in-place; cloning preserves
                    # the documented caller-owned image buffers.
                    return self.model(previous_bgr.clone(), current_bgr.clone())[-1]

            wrapped = Wrapper(model).eval()
            rng = np.random.default_rng(17)
            first = rng.integers(0, 256, (1, 3, 384, 640), dtype=np.uint8).astype(np.float32)
            second = np.roll(first, 8, axis=3)
            temporary_graph = workspace / "model.onnx"
            torch.onnx.export(wrapped, (torch.from_numpy(first), torch.from_numpy(second)),
                              temporary_graph, opset_version=17, dynamo=False,
                              input_names=["previous_bgr", "current_bgr"], output_names=["flow"])
            graph = onnx.load(temporary_graph)
            graph.producer_name = "OSR NeuFlow v2 export"
            graph.producer_version = "1"
            graph.doc_string = "NeuFlow v2 mixed weights; Apache-2.0; fixed FP32 BGR 384x640; upstream inference unchanged."
            metadata = {
                "license": "Apache-2.0", "source_commit": CODE_COMMIT,
                "weights_revision": WEIGHTS_REVISION, "weights_sha256": WEIGHTS_SHA256,
                "input_format": "BGR float32 NCHW 0..255; normalization inside graph",
                "output_format": "float32 NCHW forward dx,dy in input-image pixels",
                "refinement_iterations": "s16=1,s8=8",
            }
            onnx.helper.set_model_props(graph, metadata)
            onnx.checker.check_model(graph)
            data = graph.SerializeToString()
            with destination.open("xb") as output:
                output.write(data)
        finally:
            sys.path.remove(str(workspace))
    report = {
        "artifact": destination.name, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data),
        "license": "Apache-2.0", "upstream_code": "https://github.com/neufieldrobotics/NeuFlow_v2",
        "source_commit": CODE_COMMIT, "source_file_sha256": SOURCE_HASHES,
        "upstream_weights": "https://huggingface.co/Study-is-happy/neuflow-v2",
        "weights_revision": WEIGHTS_REVISION, "weights_sha256": WEIGHTS_SHA256,
        "export": {"torch": torch.__version__, "onnx": onnx.__version__, "opset": 17,
                   "inputs": ["previous_bgr", "current_bgr"], "input_shape": [1, 3, 384, 640],
                   "output_shape": [1, 2, 384, 640], "dtype": "float32", "channel_order": "BGR",
                   "input_range": [0, 255], "iters_s16": 1, "iters_s8": 8,
                   "modifications": "Fixed batch/spatial shape; clone caller inputs; export final flow only; add provenance. No retraining or quantization."},
    }
    provenance_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export(args.output), indent=2))
