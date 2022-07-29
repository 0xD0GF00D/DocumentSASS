# DocumentSASS
The instruction sets for NVIDIA GPUs have a very sparse [official documentation](https://docs.nvidia.com/cuda/cuda-binary-utilities/index.html).

Other projects have worked on examining the instructions mainly through reverse-engineering, such as 
[MaxAs](https://github.com/NervanaSystems/maxas/), [AsFermi](https://github.com/hyqneuron/asfermi), [CuAssembler](https://github.com/cloudcores/CuAssembler),
[TuringAs](https://github.com/daadaada/turingas), [KeplerAs](https://github.com/PAA-NCIC/PPoPP2017_artifact), [Decuda](https://github.com/laanwj/decuda), and the paper [Dissecting the NVidia Turing T4 GPU](https://arxiv.org/abs/1903.07486).


Since the instructions and architecture changes from generation to generation, it is an uphill battle.<br>
**What if a description of the instruction encoding could be found within the tools provided by NVIDIA?**<br>
**What if the instruction latencies could be found inside these as well?**<br>


**The answer is of course they can.** Otherwise the compiler would do a poor job scheduling instructions. Furthermore, for SASS it turns out that fixed-latency instructions have the number of stall cycles hard-coded into them [[src](https://arxiv.org/pdf/1903.07486.pdf)]. It is just a question of finding where this data is hidden.

It turns out that an extensive description of SASS instructions as well as latencies was contained in two specific strings in `nvdisasm`. Instead of having to write micro-benchmarks to find latencies, or use reverse engineering to make an assembler, one could in theory just consult these files. [Instruction scheduling](https://en.wikipedia.org/wiki/Instruction_scheduling) info is given in the latencies file, with the minimum time for fixed-latency ops. essentially being the latency. See [NOTES](NOTES.md).

For some additional, unrelated observations, see [OTHER](OTHER.md).


## How to run
The easy way is by simply running [this notebook](https://colab.research.google.com/drive/1qjdpjCgozg-yKfW_u9lJfHuxOu0NrnGG?authuser=1) in Google Colab. No requirements.

Requirements to run locally: Linux, Python 3, CUDA Toolkit. Run `make` to generate the raw files describing instructions and latencies. Be sure to change the paths in the beginning of the Makefile if they are different on your system. Tested with CUDA 11.6.

## How it works
1. `nvcc` is used to compile example.cu to .cubin binaries for a list of architectures.
2. `cc` is used to compile intercept.c to a .so library that serves as a [man-in-the-middle](https://www.thegeekstuff.com/2012/03/reverse-engineering-tools/) for data from memcpy calls.
3. We intercept `nvdisasm` applied on each binary file using `intercept.so`.
4. The result is filtered with `strings` to only get text, and then the script `funnel.py` gathers the relevant portions and writes them to files.

An initial approach was to simply run `strings nvdisasm` to get text embedded in the executable, but it turned out the relevant strings were dynamically generated (and only for the input architecture), which is why this solution is needed.

## TODO
- It appears the instruction string may be slightly corrupted for compute capability 3.5 currently.
