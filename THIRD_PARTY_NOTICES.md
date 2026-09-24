# Third Party Notices

This app includes the standalone 3D OSR simulator HTML from
`nbnb9527/nb-3d-simulator`.

- Source: https://github.com/nbnb9527/nb-3d-simulator
- License stated by upstream README: MIT

Additional acknowledgements:

- OpenCV DIS optical flow and pyramidal Lucas–Kanade tracking: https://docs.opencv.org/4.x/de/d4f/classcv_1_1DISOpticalFlow.html and https://github.com/opencv/opencv/blob/4.x/samples/python/lk_track.py . Test.23 uses APIs from the existing `opencv-python>=4.9` dependency (OpenCV 4.5+ is Apache-2.0; https://github.com/opencv/opencv/blob/4.x/LICENSE). The new `regional_flow.py` is independently written, inspired by the project's released v1 ROI flow and distributed tracking/forward-backward validation; no upstream tracker implementation or example source is bundled.
- Zdenek Kalal, Krystian Mikolajczyk and Jiri Matas, "Forward-Backward Error: Automatic Detection of Tracking Failures", ICPR 2010: https://dspace.cvut.cz/bitstream/handle/10467/9553/2010-forward-backward-error-automatic-detection-of-tracking-failures.pdf . Conceptual reference for multi-point tracking and failure validation, not copied source code or bundled data.

- One Euro filter: Gery Casiez, Nicolas Roussel and Daniel Vogel, CHI 2012, https://gery.casiez.net/publications/CHI2012-casiez.pdf . `output_curve.py` implements the published speed-adaptive filtering equations for six normalized output values; no upstream source code is bundled.

- ONNX Runtime: https://github.com/microsoft/onnxruntime (MIT). The optional GPU check embeds the tiny arithmetic-only `datasets/mul_1.onnx` diagnostic graph as bytes, not a trained pose model. No `.onnx` files are shipped. GPU installation follows https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html .
- pip: https://github.com/pypa/pip (MIT). The portable build includes pip and its vendored license notices solely as tooling for isolated optional-runtime installation. Installed GPU components remain outside the application folder. Additional packaged dependency licenses are in `licenses/` in the Windows distribution.
- NVIDIA CUDA/cuDNN runtime wheels: downloaded optionally from PyPI via ONNX Runtime's `cuda,cudnn` extras. These NVIDIA components have their own license terms; they are not bundled with source or portable packages. Installation preserves package license/metadata files in the private runtime overlay.
- ONNX Runtime DirectML: https://onnxruntime.ai/docs/execution-providers/DirectML-ExecutionProvider.html . Optional `onnxruntime-directml` wheel from PyPI; ONNX Runtime is MIT, and its DirectML components have their own license terms. Package metadata/licenses are retained. The adapter reuses rtmlib preprocessing and decoding without copying or changing those algorithms. No DirectML binary is bundled in source or portable packages.

- Eroscripts/osr-emu: https://github.com/Eroscripts/osr-emu . Underlying OSR / SR6 emulator referenced by the existing standalone preview. Other device shapes are explicitly marked as different.

- `nbnb9527/PoseFunscripter`: referenced conceptually for pose/skeleton motion analysis ideas. No code from that repository is intentionally copied here.
- FunGen / FunGen2, OpenFunscripter, TCode and OSR community projects: referenced as part of the broader realtime scripting and TCode workflow ecosystem.

## Bundled simulator license texts

The bundled `src/osr_screen_tcode/assets/osr_emu_standalone.html` contains the
nb-3d-simulator standalone adapter, OSR emulator code and Three.js. These
components retain their MIT terms below; the repository's Apache-2.0 license
does not replace them. Host-specific changes add device context, final-command
streaming and preview integration.

### nb-3d-simulator standalone adapter

Upstream: https://github.com/nbnb9527/nb-3d-simulator

License declaration: https://github.com/nbnb9527/nb-3d-simulator/blob/master/README.md#许可证

Attribution: nbnb9527/nb-3d-simulator contributors. The upstream README declares
MIT, but does not supply a separate license file or a copyright year. No
copyright year is inferred here. The MIT permission and disclaimer are
reproduced below.

```text
MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### OSR emulator

Original upstream: https://github.com/ayvasoftware/osr-emu

Referenced fork: https://github.com/Eroscripts/osr-emu

License source: https://raw.githubusercontent.com/ayvasoftware/osr-emu/master/LICENSE

```text
MIT License

Copyright (c) 2021 ayvajs

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### Three.js r127

The embedded renderer identifies its revision as `127` through
`window.__THREE__`. This notice comes from that release's `r127` tag.

License source: https://raw.githubusercontent.com/mrdoob/three.js/r127/LICENSE

```text
The MIT License

Copyright © 2010-2021 three.js authors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
```

## Embedded ONNX Runtime diagnostic graph

`gpu_runtime.py` embeds the 130-byte arithmetic-only `mul_1.onnx` GPU diagnostic
graph. Its bytes were verified against the official ONNX Runtime `v1.21.0`
source below. It is not a trained pose model or a bundled runtime.

Graph source: https://raw.githubusercontent.com/microsoft/onnxruntime/v1.21.0/onnxruntime/python/datasets/mul_1.onnx

License source: https://raw.githubusercontent.com/microsoft/onnxruntime/v1.21.0/LICENSE

```text
MIT License

Copyright (c) Microsoft Corporation

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
