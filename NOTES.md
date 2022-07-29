
# Interpretations
The resulting data is clearly meant for some program to parse, so it is not as immediately understandable as I would like.
Depending on how much time I have, I'll work on breaking down the data into a more understandable format.


Since SASS is undocumented, we can only really do interpretations of their function, unless we validate for every case (a daunting task).<br>
The grave accent and <code>@</code> symbols appear to be operators to do with table lookups.


## Instructions file
Whenever, for example `Predicate(PT):Pg` appears, it means initialization of type Predicate with default value PT (true), stored in variable Pg.
Then `/` means it is optional, maybe also that it must be displayed with a dot, e.g. `FFMA.SAT`. This is often coupled with quotation marks, meaning that it must be displayed as a string, even when the table value is numeric, e.g. `SAT "nosat"=0 , "SAT"=1;` for `/SAT("nosat"):sat`. The reason the table is numeric is probably because that gives a direct mapping from the bits to the string in the table.

Another example is `BITSET(6/0x0000):`, meaning a field of 6 bits (probably displayed as a bitset).
Similarly `UImm(3/0x7):src_rel_sb` probably means unsigned integer immediate value of 3 bits, with default value 7 (meaning no barrier).

Variable latency operations appear to use the `VarLatOperandEnc(src_rel_sb)` table value as well as a `VIRTUAL QUEUE`. This is very important information, as the queues tells us which operations can be done without affecting each other (different queues).
For fixed-latency operations there is no variable `src_rel_sb`, and the encoding for these bits is specified to have the value `*7`, probably literal 7. I noticed there is an exception of EXIT, where it just says `7`.


The binary code for the instruction is given in the OPCODES field. The leading bit is not part of the code; It is always 1, probably just to encode the length of the opcode. The encoding is given in the ENCODING field. These contain references to the bit field tables. An instruction is 128 bits, but in the bit field table, the first 64 bits are written last -- which makes sense since then the instruction field is contiguous, and the first bits give the control code.

The encoded opex field appear to give the stall cycles, as well as reuse flags, and something called `batch` (between 0 and 6, probably to do with variable latency instructions). A stall up to 15 is quite simple, but it appears that stalls all the way up to 27 cycles are actually supported, but doing so disables batch functionality (since there are limited bits available). Valid combinations are given in the opex tables.

## Latencies file
The latencies between operations is given in the different tables. The table is organized with respect to input and output resources, called connectors.
Latency for variable-latency operations does not necessarily reflect the actual latency, only a lower bound possibly.


I am not sure how to interpret latencies above 15, since 15 is the highest possible value in the latencies field of the instructions.
It seems like they are correct though, those that are given, but they should be interpreted carefully. <br>

For example for HMMA.16816.F16 (half-precision tensor-core accelerated matrix multiply): If they chained with the connection of with input register being the same as the output register, the stated latency is 28. By micro-benchmarking I find the latency to be 24 cycles. Looking at the SASS it appears there is inserted NOP operations between them. NOP is classified as a MIO_OP, essentially because it appears NOP is used specifically to resolve some data hazards for variable-latency instructions. The correct table value is then (HMMA_OP, MIO_FAST_OPS) = 22! And our observed value is 24 because one cycle is spent executing NOP, and one cycle is lost somewhere else. I wonder where?

Note that the measured time of HMMA.16816.F32 was 33-34 cycles, which is not in the latencies table. Maybe because it is above 2*15, or maybe cause is greater than 27, which is the largest value of the usched table in the instructions file -- 28 is the greatest value latency in the latency file. The latency for DMMA.884 was measured to be 38-39 cycles (and as high as 177 with multiple threads), which is quite far from (DMMA_OP, DMMA_OP) = 25 or (DMMA_OP, MIO_FAST_OPS) = 23.

Another example is with the variable-latency MUFU operation. It is also a MIO_FAST_OP, but unfortunately the latency for chaining these is not given. In terms of scheduling this is not an issue, as there is no hazards (as long as appropriate barriers are set). I measured MUFU.SQRT to be 17 cycles (sm86), which is also the time of MUFU.RSQ (reciprocal square root), MUFU.LG2 (2-logarithm) and MUFU.EX2 (2-exponential). The first case is most interesting, since one might expect MUFU.SQRT to have the latency of MUFU.RSQ + MUFU.RCP (reciprocal).


Findings:
1. Truly fixed latencies with times over 15 cycles appear to be implemented by inserting NOP instructions. These NOP probably either use barriers, or maybe just use the truly simple method fixed stall cycles (enough to cover the remaining cycles over 15).
2. Truly variable latencies are not specified in the latencies file. They must be resolved with barriers and the like. This is probably because they involve shared resources.
3. The time before a predicate can be used appear to be 13 cycles (sm86) in many cases, but it can be as low as 5 cycles in the common case of 32-bit float operations it seems (see table for specific connectors).

## Redundancies
The unique files are found by `md5sum * | grep ".txt" | sort | uniq -w33 | awk '{print $2}' | sort`
<pre>
sm_35_instructions.txt
sm_35_latencies.txt
sm_37_instructions.txt
sm_50_instructions.txt
sm_50_latencies.txt
sm_52_instructions.txt
sm_52_latencies.txt
sm_60_instructions.txt
sm_60_latencies.txt
sm_61_instructions.txt
sm_61_latencies.txt
sm_70_instructions.txt
sm_70_latencies.txt
sm_72_instructions.txt
sm_72_latencies.txt
sm_75_instructions.txt
sm_75_latencies.txt
sm_80_instructions.txt
sm_80_latencies.txt
sm_86_instructions.txt
sm_86_latencies.txt
</pre>
This shows that some parts were unchanged between different compute capabilities. These files are 32.6 MB.<br>
The size of the .data and .rodata segment in nvdisasm is 30.9 + 0.17 = 31.07 MB. So some decompression is most likely done, which explains why the text files are not easily discoverable.
