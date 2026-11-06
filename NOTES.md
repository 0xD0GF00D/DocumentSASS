# Interpretations
The resulting data is clearly meant for some program to parse, so it is not as immediately understandable as I would like. Depending on how much time I have, I'll work on breaking down the data into a more understandable format.

Since SASS is undocumented, we can only offer interpretations of its function, unless we validate every case (a daunting task).<br>
The grave accent and <code>@</code> symbols appear to be operators to do with table lookups.

## Instructions file
Whenever, for example, `Predicate(PT):Pg` appears, it means initialization of type Predicate with default value PT (true), stored in variable Pg. 
The `/` means it is optional, or that it must be displayed with a dot, e.g., `FFMA.SAT`. This is often coupled with quotation marks, meaning that it must be displayed as a string, even when the table value is numeric, e.g., `SAT "nosat"=0 , "SAT"=1;` for `/SAT("nosat"):sat`. The reason the table is numeric is probably that it gives a direct mapping from the bits to the string in the table.

Another example is `BITSET(6/0x0000):`, meaning a field of 6 bits (probably displayed as a bitset).
Similarly, `UImm(3/0x7):src_rel_sb` probably means an unsigned integer immediate value of 3 bits, with default value 7 (meaning no barrier).

Variable latency operations appear to use the `VarLatOperandEnc(src_rel_sb)` table value as well as a `VIRTUAL_QUEUE`. This is very important information, as the queues indicate which operations can be performed without affecting one another (different execution pipelines). 
For fixed-latency operations, there is no variable `src_rel_sb`, and the encoding of these bits is specified as `*7`, probably a literal 7. I noticed there is an exception for EXIT that just says `7`.

The binary code for the instruction is given in the OPCODES field. The leading bit is not part of the code; it is always 1, likely just to encode the opcode length. The encoding is given in the ENCODING field. These contain references to the bit field tables. An instruction is 128 bits, but in the bit field table, the first 64 bits are written last—which makes sense since the instruction field is contiguous, and the first bits give the control code.

The encoded `opex` field appears to include stall cycles, reuse flags, and something called `batch_t` (between 0 and 6, likely related to variable-latency instructions). A stall of up to 15 is quite simple, and it appears that stalls up to 27 cycles are supported, but doing so disables batch functionality (since there are limited bits available). Valid combinations are given in the `opex` tables.

## Latencies (Legacy vs. Modern)
**Note on Modern Architectures (Volta `sm_70` and newer):** The latency tables could no longer be found in the `nvdisasm` payload.

For older architectures (Maxwell up to Pascal `sm_62`), exact operation latencies are provided in separate tables, organized by input and output resources (connectors). 

For modern hardware, true cycle execution times may be measured via microbenchmarking:

*   **HMMA (Tensor Cores):** For `HMMA.16816.F16`, if chained with the connection of the input register being the same as the output register, legacy tables might suggest a latency of 28. By micro-benchmarking, I found the actual latency to be 24 cycles. Looking at the SASS, it appears that NOP operations are inserted between them. NOP is classified as a `MIO_OP` because it appears to be used specifically to resolve data hazards for variable-latency instructions. The correct table value is then `(HMMA_OP, MIO_FAST_OPS) = 22`! Our observed value is 24 because one cycle is spent executing NOPs, and one cycle is lost elsewhere.
*   **Larger Types:** The measured time of `HMMA.16816.F32` was 33-34 cycles (not present in tables, possibly because it exceeds the max `usched` value of 27). The latency for `DMMA.884` was measured at 38-39 cycles (up to 177 with multiple threads).
*   **MUFU:** A variable-latency `MIO_FAST_OP`. In terms of scheduling, this is not an issue, as there are no hazards provided appropriate variable-latency barriers are set. I measured `MUFU.SQRT` to be 17 cycles (on `sm_86`), which is also the time of `MUFU.RSQ` (reciprocal square root), `MUFU.LG2` (2-logarithm), and `MUFU.EX2` (2-exponential).

### Findings:
1. **Fixed Latencies Over 15 Cycles:** These appear to be implemented by inserting `NOP` instructions. These NOPs either use barriers or simply utilize fixed stall cycles to cover the remaining cycles over 15.
2. **Variable Latencies:** These are not specified in the static latencies file, even for legacy architectures. They involve shared hardware resources and must be resolved dynamically with explicit dependency barriers (`src_rel_sb`).
3. **Predicates:** The time before a predicate can be used appears to be 13 cycles (`sm_86`) in many cases, but it can be as low as 5 cycles in the common case of 32-bit float operations.

## Redundancies
Unique files found by `md5sum * | grep ".txt" | sort | uniq -w33 | awk '{print $2}' | sort`:
<pre>
sm_35_instructions.txt
sm_37_instructions.txt
sm_50_instructions.txt
sm_52_instructions.txt
sm_60_instructions.txt
sm_61_instructions.txt
sm_70_instructions.txt
sm_72_instructions.txt
sm_75_instructions.txt
sm_80_instructions.txt
sm_86_instructions.txt
</pre>
This shows that some parts were unchanged between different compute capabilities. 
The total size of these files is ~32.6 MB. The size of the `.data` and `.rodata` segments in `nvdisasm` is ~31.07 MB. This confirms that LZ4 decompression is taking place when running the tool, explaining why these text payloads are not discoverable via simple static analysis strings.
