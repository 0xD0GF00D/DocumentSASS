## Essential resources
1. [MaxAs](https://github.com/NervanaSystems/maxas) is a reverse-engineered assembler for the Maxwell architecture (Compute Capability 5.2), by [Scott Gray](https://forums.developer.nvidia.com/u/scottgray/summary). The story is he needed a fast GEMM implementation, but the public CUDA tools do not allow for precise editing of SASS assembly. 80% of the theoretical throughput could be attained in PTX, and only with hand-written assembly could ~98% be reached.
2. [Dissecting the NVidia Turing T4 GPU via Microbenchmarking](https://arxiv.org/abs/1903.07486). This paper uses micro-benchmarks to estimate the undocumented latencies of instructions for Compute Capabilities 3.0-7.5. It also provides a reverse-engineered description of the instruction encoding for these generations.
3. [RTX ON: The NVIDIA Turing GPU Architecture](https://old.hotchips.org/hc31/HC31_2.12_NVIDIA_final.pdf) [[video](https://www.youtube.com/watch?v=IjxpMZUqu6c), [paper](https://ieeexplore.ieee.org/document/8981896)] slides for a talk describing the improved throughput on Turing. Shows how dispatch happens. Appears to confirm the uniform datapath consists of a separate unit and register file. But it is still unclear to me what the interaction between MUFU and MIO is (why MUFU use can cause [MIO stall](https://docs.nvidia.com/nsight-compute/ProfilingGuide/#statistical-sampler)).
4. [L1TEX usage and L2 below](https://docs.nvidia.com/nsight-compute/ProfilingGuide/index.html#memory-tables-l1) from the profiling guide. Shows more in-depth how the L1Tex unit works on GA100 (Compute Capability 8.0).

See the diagram in (2) for memory hierarchy and the diagram in (3) for throughput, of Compute Capability 7.5.


## Profiling
Metrics with "sass_" in the name work by [patching the kernel](https://forums.developer.nvidia.com/t/difference-between-thread-inst-executed-metrics/217587), and therefore come with a greater overhead compared to hardware counters.

## Compiler arguments
Some apparently undocumented arguments for the compiler ptxas.
<pre>
--compiler-stats (-compilerStats) <t/m/p>
    Prints out compiler statistics.
    time/t       : Prints compilation time.
    memory/m     : Prints peak memory usage.
    phase-wise/p : Prints the above data for various compiler phases.

--no-fastreg
    Disable fast register allocation.
No idea if this is good or bad in terms of performance. Very curious to try it out.

--opt-pointers (-Op)
    Optimize 64-bit pointers by truncating them to 32-bit
Another option that could impact performance.

--tool-name <string>
    Change tool name to specified string.
Appears to just change the string "ptxas" to something else in the help page.

--fastimul
    Enable 24 bit integer multiplication
I think this is only relevant for older GPU generations. For some reason 24-bit integer mult. was faster then.

--fast-compile (-fc)
    EXPERIMENTAL FEATURE: Enable optimization strategies that improve compilation time while reducing runtime performance

--cuda-api-version <major>.<minor>
    CUDA API version to use to for compilation

--sw2614554
--sw1729687
--sw200428197
--sw200387803
These just say "Enable sw_______". No idea what it does.

--key (-k)
    Hash value representing the device code from which the binaries were compiled
--okey (-ok)
    Deobfuscation key for specified ptx input
--ptx-length (-ptxlen)
    Length in bytes of obfuscated ptx string

Some arguments that appear in the data, but does not seem to work are "-dump-perf-stats", "-forcetext"
</pre>

## Half-precision MOV
Some interesting things happen when you compile PTX for SM 86, and then use in on an SM 86 device. Since the PTX is a newer version, newer features are used, which not supported on the default, SM 52.
<pre>
The line of code (variable names simplified):
float sign_value = x > y ? 1 : -1;


Becomes partly the SASS:
97	      HFMA2.MMA R16, -RZ, RZ, 1.875, 0
125	      FSEL R6, R16, -1, P1 
</pre>
The utility of the RZ register is to encode literal float zero using only 8 bits instead of e.g. 32 for a float, or 24 for an immediate float value.

Not sure what the .MMA part is, but HFMA2 is half2 vector fused multiply-add.<br>
We have in half precision 1.875 = 0011111110000000, and 0 is just 16 zeros. The result is that half2 adding {1.875, 0} to 0 (RZ * RZ) gives [the float representation of 1](https://evanw.github.io/float-toy/)!
The result is that the float literal "1" gets stored in in R16.

Now there is the MOV instruction, which could do the same. I have no idea which unit does MOV, it is clearly not the half-precision unit; therefore using this otherwise un-used unit gives a higher throughput.
This explains why one might see half-precision operations even if half precision is not used anywhere in the code.
