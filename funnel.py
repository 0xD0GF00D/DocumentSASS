#!/usr/bin/env python3
"""
extract_sass_docs.py

Automated SASS extraction and documentation pipeline for NVIDIA GPU architectures.
- Decompresses grammar payloads (payload_1.bin).
- Reassembles streaming Machine Description (.md) payloads (payloads 2..N).
- Partitions instruction classes from latency, resource, and conflict matrices.
- Cleans up intermediate artifacts automatically.
"""

import sys
import glob
import re
from pathlib import Path
import lz4.block

# Keywords that mark the beginning of the scheduling, resource, and latency model
SCHED_START_RE = re.compile(
    r"^[ \t]*(?:"
    r"HARD\s+RESOURCE\b|"
    r"CONNECTOR\s+NAMES\b|"
    r"CONNECTOR\s+SETS\b|"
    r"OPERATION\s+SETS\b|"
    r"TABLE_OUTPUT\b|"
    r"TABLE_TRUE\b|"
    r"TABLE_ANTI\b|"
    r"TABLE_NONREG\b"
    r")",
    re.MULTILINE,
)

def get_payload_num(filename: str) -> int:
    m = re.search(r"_payload_(\d+)\.bin$", filename)
    return int(m.group(1)) if m else -1

def is_ascii_chunk(data: bytes) -> bool:
    if not data:
        return False
    printable = sum(1 for b in data if (32 <= b <= 126) or b in (9, 10, 13))
    return (printable / len(data)) > 0.85

def main():
    if len(sys.argv) < 2:
        sys.exit("Usage: python3 extract_sass_docs.py <arch>")

    arch = sys.argv[1]
    payload_files = sorted(glob.glob(f"{arch}_payload_*.bin"), key=get_payload_num)

    if not payload_files:
        sys.exit(f"[{arch}] Error: No payload files found matching '{arch}_payload_*.bin'.")

    instructions_text = ""
    candidate_runs = []
    current_run = []
    last_num = None

    for p in payload_files:
        path = Path(p)
        data = path.read_bytes()
        num = get_payload_num(p)

        # 1. Main compressed grammar payload (payload_1.bin, >100 KB)
        if len(data) > 100000:
            try:
                dec = lz4.block.decompress(data, uncompressed_size=0x2000000)
                instructions_text = dec.decode("ascii", errors="replace")
                print(f"[{arch}] Decompressed grammar payload {p} ({len(instructions_text):,} chars).")
            except Exception as e:
                print(f"[{arch}] LZ4 decompression failed on {p}: {e}")

        # 2. Sequential ASCII stream blocks (Machine Description chunks)
        elif is_ascii_chunk(data):
            if last_num is not None and num == last_num + 1:
                current_run.append(data)
            else:
                if current_run:
                    candidate_runs.append(b"".join(current_run))
                current_run = [data]
            last_num = num
        else:
            if current_run:
                candidate_runs.append(b"".join(current_run))
                current_run = []
            last_num = None

    if current_run:
        candidate_runs.append(b"".join(current_run))

    latencies_text = ""
    stream_instructions = ""

    # 3. Locate and partition the Machine Description stream
    for run_bytes in candidate_runs:
        text = run_bytes.decode("ascii", errors="replace")
        m = SCHED_START_RE.search(text)
        if m:
            split_idx = m.start()
            stream_instructions = text[:split_idx].strip()
            latencies_text = text[split_idx:].strip()
            matched_kw = m.group(0).strip()
            print(f"[{arch}] Partitioned stream at '{matched_kw}' (offset {split_idx:,}):")
            print(f"       -> Stream instructions: {len(stream_instructions):,} chars")
            print(f"       -> Stream latencies:    {len(latencies_text):,} chars")
            break
        elif "TABLE_OUTPUT" in text or "OPERATION SETS" in text or "HARD RESOURCE" in text:
            latencies_text = text.strip()
            break

    # If the streamed instruction definitions are more comprehensive than payload_1, use them
    if stream_instructions and len(stream_instructions) > len(instructions_text):
        instructions_text = stream_instructions

    # Legacy fallback: OPERATION SETS appended directly in the primary instructions payload
    if not latencies_text and "OPERATION SETS" in instructions_text:
        op_idx = instructions_text.find("OPERATION SETS")
        latencies_text = instructions_text[op_idx:].strip()
        instructions_text = instructions_text[:op_idx].strip()
        print(f"[{arch}] Split legacy OPERATION SETS from main instruction stream.")

    if not instructions_text:
        sys.exit(f"[{arch}] Error: Failed to extract instruction definitions.")

    # Write clean target documentation files
    inst_path = Path(f"{arch}_instructions.txt")
    lat_path = Path(f"{arch}_latencies.txt")

    inst_path.write_text(instructions_text, encoding="utf-8")
    if latencies_text:
        lat_path.write_text(latencies_text, encoding="utf-8")
    else:
        lat_path.write_text("Notice: No latency or resource scheduling table found for this architecture.", encoding="utf-8")

    # Clean up all raw binary payload files
    for p in payload_files:
        Path(p).unlink(missing_ok=True)

    print(f"[{arch}] Successfully generated {inst_path.name} ({inst_path.stat().st_size:,} bytes)")
    print(f"[{arch}] Successfully generated {lat_path.name} ({lat_path.stat().st_size:,} bytes)")

if __name__ == "__main__":
    main()
