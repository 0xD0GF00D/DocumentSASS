# DocumentSASS
The instruction sets for NVIDIA GPUs have a very sparse [official documentation](https://docs.nvidia.com/cuda/cuda-binary-utilities/index.html).

Other projects have worked on examining the instructions mainly through reverse-engineering, such as 
[MaxAs](https://github.com/NervanaSystems/maxas/), [AsFermi](https://github.com/hyqneuron/asfermi), [CuAssembler](https://github.com/cloudcores/CuAssembler),
[TuringAs](https://github.com/daadaada/turingas), [KeplerAs](https://github.com/PAA-NCIC/PPoPP2017_artifact), [Decuda](https://github.com/laanwj/decuda), and the papers [Dissecting the NVidia Turing T4 GPU](https://arxiv.org/abs/1903.07486), [Optimizing Batched Winograd Convolution on GPUs](https://www.cse.ust.hk/~weiwa/papers/yan-ppopp20.pdf).

Since the instructions and architecture change from generation to generation, it is an uphill battle.<br>
**What if a description of the instruction encoding could be found within the tools provided by NVIDIA?**<br>
**What if the instruction latencies could be found inside these as well?**<br>

The answer is **of course they can.** Otherwise, the compiler would do a poor job scheduling instructions. Furthermore, for SASS, it appears that fixed-latency instructions have the number of stall cycles hard-coded into them [[src](https://arxiv.org/pdf/1903.07486.pdf)]. It is just a question of finding where this data is hidden.

It turns out that an extensive description of SASS instructions as well as latencies was contained in two specific strings in `nvdisasm`. Instead of having to write micro-benchmarks to find latencies, or use reverse engineering to make an assembler, one could in theory just consult these files. [Instruction scheduling](https://en.wikipedia.org/wiki/Instruction_scheduling) info is given in the latencies file, with the minimum time for fixed-latency ops. essentially being the latency. See [NOTES](NOTES.md).

## How to run
The easy way is by simply running [this notebook](https://colab.research.google.com/drive/1qjdpjCgozg-yKfW_u9lJfHuxOu0NrnGG) in Google Colab.

Requirements: Python 3 with lz4 (`pip install lz4`) + the CUDA Toolkit. Run `make` to generate the text files describing instructions and latencies. Be sure to update the paths at the beginning of the Makefile if they differ on your system. Tested on CUDA 12.8 by [1 contributor](https://github.com/OPS-NeoRetro).

## How it works
1. `nvcc` compiles `example.cu` to `.cubin` binaries for each supported architecture.
2. `cc` compiles `intercept.c` into a library that hooks `nvdisasm`'s internal decryption routines using a [trampoline](https://en.wikipedia.org/wiki/Trampoline_(computing)).
3. We run `nvdisasm` under `LD_PRELOAD=./intercept.so` to trigger the hook, which captures the cipher state alongside the primary encrypted payload while letting the disassembler continue normally.
4. `extract_sass_docs.py` parses the [S-box](https://en.wikipedia.org/wiki/S-box) from the `nvdisasm` [ELF](https://en.wikipedia.org/wiki/Executable_and_Linkable_Format) binary, decrypts the payload via its [LCG](https://en.wikipedia.org/wiki/Linear_congruential_generator) stream, and unpacks the text buffer using [LZ4](https://github.com/lz4/lz4).
5. The decompressed and decrypted text is routed to `*_latencies.txt` and `*_instructions.txt`.
