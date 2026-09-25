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

## Portable Windows dependency license supplements

The test.26 Windows package includes pySerial 3.5 and Tcl 8.6.12. The installed
pySerial wheel does not contain a separate license file for the packaging helper
to copy, so its full upstream license is reproduced below. The bundled Tcl DLL
reports version 8.6.12. Python's license file only references a separate Tcl/Tk
license; the Tcl core notice is included here in full.

Tk's separate license is already retained as `_internal/_tk_data/license.terms`
in the Windows package and was checked against the official Tk 8.6.12 text:
https://raw.githubusercontent.com/tcltk/tk/core-8-6-12/license.terms .

### pySerial 3.5

License source: https://raw.githubusercontent.com/pyserial/pyserial/v3.5/LICENSE.txt

```text
Copyright (c) 2001-2020 Chris Liechti <cliechti@gmx.net>
All Rights Reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are
met:

  * Redistributions of source code must retain the above copyright
    notice, this list of conditions and the following disclaimer.

  * Redistributions in binary form must reproduce the above
    copyright notice, this list of conditions and the following
    disclaimer in the documentation and/or other materials provided
    with the distribution.

  * Neither the name of the copyright holder nor the names of its
    contributors may be used to endorse or promote products derived
    from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

---------------------------------------------------------------------------
Note:
Individual files contain the following tag instead of the full license text.

    SPDX-License-Identifier:    BSD-3-Clause

This enables machine processing of license information based on the SPDX
License Identifiers that are here available: http://spdx.org/licenses/
```

### Tcl 8.6.12

License source: https://raw.githubusercontent.com/tcltk/tcl/core-8-6-12/license.terms

```text
This software is copyrighted by the Regents of the University of
California, Sun Microsystems, Inc., Scriptics Corporation, ActiveState
Corporation and other parties.  The following terms apply to all files
associated with the software unless explicitly disclaimed in
individual files.

The authors hereby grant permission to use, copy, modify, distribute,
and license this software and its documentation for any purpose, provided
that existing copyright notices are retained in all copies and that this
notice is included verbatim in any distributions. No written agreement,
license, or royalty fee is required for any of the authorized uses.
Modifications to this software may be copyrighted by their authors
and need not follow the licensing terms described here, provided that
the new terms are clearly indicated on the first page of each file where
they apply.

IN NO EVENT SHALL THE AUTHORS OR DISTRIBUTORS BE LIABLE TO ANY PARTY
FOR DIRECT, INDIRECT, SPECIAL, INCIDENTAL, OR CONSEQUENTIAL DAMAGES
ARISING OUT OF THE USE OF THIS SOFTWARE, ITS DOCUMENTATION, OR ANY
DERIVATIVES THEREOF, EVEN IF THE AUTHORS HAVE BEEN ADVISED OF THE
POSSIBILITY OF SUCH DAMAGE.

THE AUTHORS AND DISTRIBUTORS SPECIFICALLY DISCLAIM ANY WARRANTIES,
INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE, AND NON-INFRINGEMENT.  THIS SOFTWARE
IS PROVIDED ON AN "AS IS" BASIS, AND THE AUTHORS AND DISTRIBUTORS HAVE
NO OBLIGATION TO PROVIDE MAINTENANCE, SUPPORT, UPDATES, ENHANCEMENTS, OR
MODIFICATIONS.

GOVERNMENT USE: If you are acquiring this software on behalf of the
U.S. government, the Government shall have only "Restricted Rights"
in the software and related documentation as defined in the Federal
Acquisition Regulations (FARs) in Clause 52.227.19 (c) (2).  If you
are acquiring the software on behalf of the Department of Defense, the
software shall be classified as "Commercial Computer Software" and the
Government shall have only "Restricted Rights" as defined in Clause
252.227-7014 (b) (3) of DFARs.  Notwithstanding the foregoing, the
authors grant the U.S. Government and others acting in its behalf
permission to use and distribute the software in accordance with the
terms specified in this license.
```

### OpenSSL 3.5.8

The bundled Python TLS implementation uses `libssl-3-x64.dll` and
`libcrypto-3-x64.dll`. Both bundled DLLs report product version **3.5.8**.
OpenSSL is licensed under Apache-2.0. Its version-specific upstream license
and author acknowledgements are reproduced below; these do not replace the
licenses of the other bundled components.

License source: https://raw.githubusercontent.com/openssl/openssl/openssl-3.5.8/LICENSE.txt

```text

                                 Apache License
                           Version 2.0, January 2004
                        https://www.apache.org/licenses/

   TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

   1. Definitions.

      "License" shall mean the terms and conditions for use, reproduction,
      and distribution as defined by Sections 1 through 9 of this document.

      "Licensor" shall mean the copyright owner or entity authorized by
      the copyright owner that is granting the License.

      "Legal Entity" shall mean the union of the acting entity and all
      other entities that control, are controlled by, or are under common
      control with that entity. For the purposes of this definition,
      "control" means (i) the power, direct or indirect, to cause the
      direction or management of such entity, whether by contract or
      otherwise, or (ii) ownership of fifty percent (50%) or more of the
      outstanding shares, or (iii) beneficial ownership of such entity.

      "You" (or "Your") shall mean an individual or Legal Entity
      exercising permissions granted by this License.

      "Source" form shall mean the preferred form for making modifications,
      including but not limited to software source code, documentation
      source, and configuration files.

      "Object" form shall mean any form resulting from mechanical
      transformation or translation of a Source form, including but
      not limited to compiled object code, generated documentation,
      and conversions to other media types.

      "Work" shall mean the work of authorship, whether in Source or
      Object form, made available under the License, as indicated by a
      copyright notice that is included in or attached to the work
      (an example is provided in the Appendix below).

      "Derivative Works" shall mean any work, whether in Source or Object
      form, that is based on (or derived from) the Work and for which the
      editorial revisions, annotations, elaborations, or other modifications
      represent, as a whole, an original work of authorship. For the purposes
      of this License, Derivative Works shall not include works that remain
      separable from, or merely link (or bind by name) to the interfaces of,
      the Work and Derivative Works thereof.

      "Contribution" shall mean any work of authorship, including
      the original version of the Work and any modifications or additions
      to that Work or Derivative Works thereof, that is intentionally
      submitted to Licensor for inclusion in the Work by the copyright owner
      or by an individual or Legal Entity authorized to submit on behalf of
      the copyright owner. For the purposes of this definition, "submitted"
      means any form of electronic, verbal, or written communication sent
      to the Licensor or its representatives, including but not limited to
      communication on electronic mailing lists, source code control systems,
      and issue tracking systems that are managed by, or on behalf of, the
      Licensor for the purpose of discussing and improving the Work, but
      excluding communication that is conspicuously marked or otherwise
      designated in writing by the copyright owner as "Not a Contribution."

      "Contributor" shall mean Licensor and any individual or Legal Entity
      on behalf of whom a Contribution has been received by Licensor and
      subsequently incorporated within the Work.

   2. Grant of Copyright License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      copyright license to reproduce, prepare Derivative Works of,
      publicly display, publicly perform, sublicense, and distribute the
      Work and such Derivative Works in Source or Object form.

   3. Grant of Patent License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      (except as stated in this section) patent license to make, have made,
      use, offer to sell, sell, import, and otherwise transfer the Work,
      where such license applies only to those patent claims licensable
      by such Contributor that are necessarily infringed by their
      Contribution(s) alone or by combination of their Contribution(s)
      with the Work to which such Contribution(s) was submitted. If You
      institute patent litigation against any entity (including a
      cross-claim or counterclaim in a lawsuit) alleging that the Work
      or a Contribution incorporated within the Work constitutes direct
      or contributory patent infringement, then any patent licenses
      granted to You under this License for that Work shall terminate
      as of the date such litigation is filed.

   4. Redistribution. You may reproduce and distribute copies of the
      Work or Derivative Works thereof in any medium, with or without
      modifications, and in Source or Object form, provided that You
      meet the following conditions:

      (a) You must give any other recipients of the Work or
          Derivative Works a copy of this License; and

      (b) You must cause any modified files to carry prominent notices
          stating that You changed the files; and

      (c) You must retain, in the Source form of any Derivative Works
          that You distribute, all copyright, patent, trademark, and
          attribution notices from the Source form of the Work,
          excluding those notices that do not pertain to any part of
          the Derivative Works; and

      (d) If the Work includes a "NOTICE" text file as part of its
          distribution, then any Derivative Works that You distribute must
          include a readable copy of the attribution notices contained
          within such NOTICE file, excluding those notices that do not
          pertain to any part of the Derivative Works, in at least one
          of the following places: within a NOTICE text file distributed
          as part of the Derivative Works; within the Source form or
          documentation, if provided along with the Derivative Works; or,
          within a display generated by the Derivative Works, if and
          wherever such third-party notices normally appear. The contents
          of the NOTICE file are for informational purposes only and
          do not modify the License. You may add Your own attribution
          notices within Derivative Works that You distribute, alongside
          or as an addendum to the NOTICE text from the Work, provided
          that such additional attribution notices cannot be construed
          as modifying the License.

      You may add Your own copyright statement to Your modifications and
      may provide additional or different license terms and conditions
      for use, reproduction, or distribution of Your modifications, or
      for any such Derivative Works as a whole, provided Your use,
      reproduction, and distribution of the Work otherwise complies with
      the conditions stated in this License.

   5. Submission of Contributions. Unless You explicitly state otherwise,
      any Contribution intentionally submitted for inclusion in the Work
      by You to the Licensor shall be under the terms and conditions of
      this License, without any additional terms or conditions.
      Notwithstanding the above, nothing herein shall supersede or modify
      the terms of any separate license agreement you may have executed
      with Licensor regarding such Contributions.

   6. Trademarks. This License does not grant permission to use the trade
      names, trademarks, service marks, or product names of the Licensor,
      except as required for reasonable and customary use in describing the
      origin of the Work and reproducing the content of the NOTICE file.

   7. Disclaimer of Warranty. Unless required by applicable law or
      agreed to in writing, Licensor provides the Work (and each
      Contributor provides its Contributions) on an "AS IS" BASIS,
      WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
      implied, including, without limitation, any warranties or conditions
      of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A
      PARTICULAR PURPOSE. You are solely responsible for determining the
      appropriateness of using or redistributing the Work and assume any
      risks associated with Your exercise of permissions under this License.

   8. Limitation of Liability. In no event and under no legal theory,
      whether in tort (including negligence), contract, or otherwise,
      unless required by applicable law (such as deliberate and grossly
      negligent acts) or agreed to in writing, shall any Contributor be
      liable to You for damages, including any direct, indirect, special,
      incidental, or consequential damages of any character arising as a
      result of this License or out of the use or inability to use the
      Work (including but not limited to damages for loss of goodwill,
      work stoppage, computer failure or malfunction, or any and all
      other commercial damages or losses), even if such Contributor
      has been advised of the possibility of such damages.

   9. Accepting Warranty or Additional Liability. While redistributing
      the Work or Derivative Works thereof, You may choose to offer,
      and charge a fee for, acceptance of support, warranty, indemnity,
      or other liability obligations and/or rights consistent with this
      License. However, in accepting such obligations, You may act only
      on Your own behalf and on Your sole responsibility, not on behalf
      of any other Contributor, and only if You agree to indemnify,
      defend, and hold each Contributor harmless for any liability
      incurred by, or claims asserted against, such Contributor by reason
      of your accepting any such warranty or additional liability.

   END OF TERMS AND CONDITIONS
```

Author acknowledgements: https://raw.githubusercontent.com/openssl/openssl/openssl-3.5.8/AUTHORS.md

```text
Authors

This is the list of OpenSSL authors for copyright purposes.
It does not necessarily list everyone who has contributed code,
since in some cases, their employer may be the copyright holder.
To see the full list of contributors, see the revision history in
source control.

Groups
------

 * OpenSSL Software Services, Inc.
 * OpenSSL Software Foundation, Inc.
 * Google LLC

Individuals
-----------

 * Andy Polyakov
 * Ben Laurie
 * Ben Kaduk
 * Bernd Edlinger
 * Bodo Möller
 * David Benjamin
 * David von Oheimb
 * Dmitry Belyavskiy (Дмитрий Белявский)
 * Emilia Käsper
 * Eric Young
 * Geoff Thorpe
 * Holger Reif
 * Kurt Roeckx
 * Lutz Jänicke
 * Mark J. Cox
 * Matt Caswell
 * Matthias St. Pierre
 * Nicola Tuveri
 * Nils Larsch
 * Patrick Steuer
 * Paul Dale
 * Paul C. Sutton
 * Paul Yang
 * Ralf S. Engelschall
 * Rich Salz
 * Richard Levitte
 * Shane Lontis
 * Stephen Henson
 * Steve Marquess
 * Tim Hudson
 * Tomáš Mráz
 * Ulf Möller
 * Valerii Krygin
 * Viktor Dukhovni
```

### libffi runtime

The portable Python runtime includes `libffi-8.dll`. Its Windows file/product
version fields are empty, and its bytes differ from the official CPython
`libffi-3.4.4/amd64/libffi-8.dll` examined during packaging. The exact build
version of this bundled DLL has **not been confirmed**; the filename alone is
not a version determination.

The MIT permission and attribution below are taken from upstream libffi 3.4.4,
which is the libffi dependency named in CPython 3.12.14's Windows build metadata.
This records the licensing reference and does not identify the bundled binary
as that exact build. The DLL is included unchanged from the Python environment.

CPython dependency reference:
https://github.com/python/cpython/blob/v3.12.14/PCbuild/get_externals.bat

Compared upstream binary reference:
https://github.com/python/cpython-bin-deps/tree/libffi-3.4.4/amd64

License source: https://raw.githubusercontent.com/libffi/libffi/v3.4.4/LICENSE

```text
libffi - Copyright (c) 1996-2022  Anthony Green, Red Hat, Inc and others.
See source files for details.

Permission is hereby granted, free of charge, to any person obtaining
a copy of this software and associated documentation files (the
``Software''), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to
the following conditions:

The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED ``AS IS'', WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
```
