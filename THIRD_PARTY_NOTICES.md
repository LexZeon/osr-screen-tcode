# Third Party Notices

This app includes the standalone 3D OSR simulator HTML from
`nbnb9527/nb-3d-simulator`.

- Source: https://github.com/nbnb9527/nb-3d-simulator
- License stated by upstream README: MIT

Additional acknowledgements:

- ONNX Runtime: https://github.com/microsoft/onnxruntime (MIT). The optional GPU check embeds the tiny arithmetic-only `datasets/mul_1.onnx` diagnostic graph as bytes, not a trained pose model. No `.onnx` files are shipped. GPU installation follows https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html .
- pip: https://github.com/pypa/pip (MIT). The portable build includes pip and its vendored license notices solely as tooling for isolated optional-runtime installation. Installed GPU components remain outside the application folder. Additional packaged dependency licenses are in `licenses/` in the Windows distribution.
- NVIDIA CUDA/cuDNN runtime wheels: downloaded optionally from PyPI via ONNX Runtime's `cuda,cudnn` extras. These NVIDIA components have their own license terms; they are not bundled with source or portable packages. Installation preserves package license/metadata files in the private runtime overlay.
- ONNX Runtime DirectML: https://onnxruntime.ai/docs/execution-providers/DirectML-ExecutionProvider.html . Optional `onnxruntime-directml` wheel from PyPI; ONNX Runtime is MIT, and its DirectML components have their own license terms. Package metadata/licenses are retained. The adapter reuses rtmlib preprocessing and decoding without copying or changing those algorithms. No DirectML binary is bundled in source or portable packages.

- Buttplug protocol v3: https://buttplug.io/docs/spec-v3/ . The test output adapter implements the documented JSON protocol over the existing `websockets` dependency. Buttplug/Intiface binaries are not bundled.
- Intiface Central: https://intiface.com/ . Optional external device server for supported commercial hardware; users install it separately.
- Eroscripts/osr-emu: https://github.com/Eroscripts/osr-emu . Underlying OSR / SR6 emulator referenced by the existing standalone preview. Other device shapes are explicitly marked as different.
- Autoblow API: https://developers.autoblow.com/reference/http-api-v1-autoblow/ . Evaluated only; Autoblow output is not enabled in 2.0.0-test.3.

- `nbnb9527/PoseFunscripter`: referenced conceptually for pose/skeleton motion analysis ideas. No code from that repository is intentionally copied here.
- FunGen / FunGen2, OpenFunscripter, TCode and OSR community projects: referenced as part of the broader realtime scripting and TCode workflow ecosystem.
