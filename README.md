# DocumentSASS
The instruction sets for NVIDIA GPUs have a very sparse [official documentation](https://docs.nvidia.com/cuda/cuda-binary-utilities/index.html).

Other projects have worked on examining the instructions mainly through reverse-engineering, such as 
[MaxAs](https://github.com/NervanaSystems/maxas/), [AsFermi](https://github.com/hyqneuron/asfermi), [CuAssembler](https://github.com/cloudcores/CuAssembler),
[TuringAs](https://github.com/daadaada/turingas), [KeplerAs](https://github.com/PAA-NCIC/PPoPP2017_artifact), [Decuda](https://github.com/laanwj/decuda), and the papers [Dissecting the NVidia Turing T4 GPU](https://arxiv.org/abs/1903.07486), [Optimizing Batched Winograd Convolution on GPUs](https://www.cse.ust.hk/~weiwa/papers/yan-ppopp20.pdf).

Since the instructions and architecture change from generation to generation, it is an uphill battle.

**What if a description of the instructions can be found within the tools provided by NVIDIA?**<br>

The answer is: **of course they can.** It is just a question of finding where this data is hidden.

It turns out that an extensive description of SASS instructions is contained within `nvdisasm`.

## How to run
The easy way is by simply running [this notebook](https://colab.research.google.com/drive/1qjdpjCgozg-yKfW_u9lJfHuxOu0NrnGG) in Google Colab.

Requirements to run locally: Linux, Python 3, the CUDA Toolkit, and the `lz4` and `pyelftools` Python packages (`pip install lz4 pyelftools`). 

Run `make` to generate the `.txt` files describing instructions and latencies for all supported architectures. Be sure to change the paths at the beginning of the `Makefile` if they differ on your system. Tested on CUDA 12.8 by [OPS-NeoRetro](https://github.com/OPS-NeoRetro).

See [NOTES](NOTES.md) for more details on instruction scheduling. For some additional, unrelated observations, see [OTHER](OTHER.md).

## How it works
1. `nvcc` compiles `example.cu` into `.cubin` targets for every supported SM architecture.
2. `intercept.c` compiles into an [LD_PRELOAD](https://man7.org/linux/man-pages/man8/ld.so.8.html) library that hooks `nvdisasm`'s internal `decrypt_isa` function using a [trampoline](https://en.wikipedia.org/wiki/Trampoline_(computing)).
3. Running `nvdisasm` triggers the hook, which captures the cipher state alongside the primary encrypted payload (>100 KB) while letting the disassembler continue normally.
4. `extract_sass_docs.py` parses the [S-box](https://en.wikipedia.org/wiki/S-box) from the `nvdisasm` [ELF](https://en.wikipedia.org/wiki/Executable_and_Linkable_Format) binary, decrypts the payload via its [LCG](https://en.wikipedia.org/wiki/Linear_congruential_generator) stream, and unpacks the ~4 MB text buffer using [LZ4](https://github.com/lz4/lz4).
5. The decompressed schema is routed to `_instructions.txt`.

*(If an older, unencrypted version of `nvdisasm` is detected, the `Makefile` automatically falls back to native plaintext execution and bypasses the decryption logic).*

*Note on Latencies:* For older architectures (like Maxwell and Pascal), the extracted data includes explicit cycle-latency tables. These tables are no longer present in the `nvdisasm` payload.
