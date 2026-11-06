#!/usr/bin/env python3
import sys
from pathlib import Path
from elftools.elf.elffile import ELFFile
import lz4.block

SBOX_VADDR = 0x4E6480
SBOX_SIZE = 256

def extract_sbox_from_elf(nvdisasm_path: str) -> list[int]:
    with open(nvdisasm_path, "rb") as f:
        elf = ELFFile(f)
        for seg in elf.iter_segments():
            if seg.header.p_type == "PT_LOAD":
                vstart = seg.header.p_vaddr
                vend = vstart + seg.header.p_memsz
                if vstart <= SBOX_VADDR < vend:
                    file_offset = seg.header.p_offset + (SBOX_VADDR - vstart)
                    f.seek(file_offset)
                    return list(f.read(SBOX_SIZE))
    raise RuntimeError("SBOX not found.")

def decrypt_isa(state: list[int], buffer: bytearray, sbox: list[int]):
    rcx = state[1] & 0xFFFFFFFF
    r8 = state[2] & 0xFFFFFFFF
    result = state[3] & 0xFF

    for i in range(len(buffer)):
        if r8 == 1:
            r8 = 4
            state[0] = (state[0] * 0x41C64E6D + 0x3039) & 0xFFFFFFFF
            rcx = state[0]
        else:
            rcx = (rcx >> 8) & 0xFFFFFFFF
            r8 = (r8 - 1) & 0xFFFFFFFF

        enc = buffer[i]
        sbox_val = sbox[(result ^ enc) & 0xFF]
        result = enc
        buffer[i] = sbox_val ^ (rcx & 0xFF)

    state[1] = rcx
    state[2] = r8
    state[3] = (state[3] & 0xFFFFFF00) | (result & 0xFF)

def main():
    if len(sys.argv) < 3:
        sys.exit("Usage: python3 extract_sass_docs.py <arch> <nvdisasm_path>")

    arch = sys.argv[1]
    nvdisasm_path = sys.argv[2]
    
    payload_path = f"{arch}.bin"
    state_path = f"{arch}_state.txt"

    text = ""

    # 1. Attempt to decode modern encrypted payload
    if Path(payload_path).exists() and Path(state_path).exists():
        try:
            state = [int(x) for x in Path(state_path).read_text().split()]
            sbox = extract_sbox_from_elf(nvdisasm_path)
            data = bytearray(Path(payload_path).read_bytes())
            decrypt_isa(state, data, sbox)
            
            decompressed = lz4.block.decompress(data, uncompressed_size=0x2000000)
            text = decompressed.decode("ascii", errors="replace")
            print(f"[{arch}] Successfully decrypted modern ISA payload.")
        except Exception as e:
            print(f"[{arch}] Decryption failed: {e}")

    # 2. Fallback to raw plaintext if encryption wasn't used/hook failed
    raw_path = f"{arch}.raw"
    if not text.strip() and Path(raw_path).exists():
        text = Path(raw_path).read_text(errors="replace")
        if text.strip():
            print(f"[{arch}] Loaded unencrypted ISA from standard output.")

    if not text.strip():
        sys.exit(f"[{arch}] Error: No documentation text could be extracted.")

    # 3. Route content based on legacy vs modern structures
    if "OPERATION SETS" in text:
        # Legacy architecture (sm_50, sm_60) has static tables
        op_idx = text.find("OPERATION SETS")
        instructions = text[:op_idx].strip()
        latencies = text[op_idx:].strip()
        print(f"[{arch}] Extracted latency table.")
    else:
        # Modern architectures (sm_70+) get the disclaimer
        instructions = text.strip()
        latencies = (
            "Latency tables could not be found for this architecture.\n\n"
        )

    Path(f"{arch}_instructions.txt").write_text(instructions, encoding="utf-8")
    Path(f"{arch}_latencies.txt").write_text(latencies, encoding="utf-8")

    # Clean up all intermediates
    for p in [payload_path, state_path, raw_path]:
        Path(p).unlink(missing_ok=True)

if __name__ == "__main__":
    main()
