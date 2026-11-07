#!/usr/bin/env python3
"""
extract_sass_docs.py

Universal SASS documentation extractor for all NVIDIA GPU architectures.
Supports:
- Modern architectures (Volta/Turing/Ampere/Ada/Hopper/Blackwell) using SIDL CLASS blocks
- Legacy architectures (Maxwell/Pascal) using ARCHITECTURE blocks and OPERATION SETS
- Automatic rejection of internal binary trie/jump-table payloads
- Clean table boundary truncation preventing trailing stack/binary garbage
"""

import sys
import glob
import re
from pathlib import Path
import lz4.block

# Keywords marking the start of scheduling, resource, and latency matrices
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

def is_printable_ascii(data: bytes) -> bool:
    """Verifies that bytes represent genuine ASCII text, not binary structs."""
    if not data or len(data) < 20:
        return False
    # Reject binary data with null bytes
    if data.count(b"\x00") > 0:
        return False
    printable = sum(1 for b in data if (32 <= b <= 126) or b in (9, 10, 13))
    return (printable / len(data)) > 0.95

def try_decode_payload(raw_data: bytes) -> str | None:
    """
    Attempts to extract valid text from a payload:
    1. Tries LZ4 decompression (modern encrypted blocks).
    2. Tries direct uncompressed text (legacy streaming blocks).
    Returns None if the payload contains binary bytecode or lookup tables.
    """
    # Try LZ4 decompression first
    try:
        decompressed = lz4.block.decompress(raw_data, uncompressed_size=0x2000000)
        if is_printable_ascii(decompressed):
            return decompressed.decode("ascii", errors="replace")
    except Exception:
        pass

    # Try raw bytes directly
    if is_printable_ascii(raw_data):
        return raw_data.decode("ascii", errors="replace")

    return None

def clean_latency_block(text: str) -> str:
    """
    Extracts the latency table from the scheduling start marker and truncates
    cleanly before trailing binary garbage, memory addresses, or stack noise.
    """
    m = SCHED_START_RE.search(text)
    if not m:
        return ""

    lat_body = text[m.start():]
    clean_lines = []

    for line in lat_body.splitlines():
        # Stop if a legacy memory delimiter tag appears
        if "<0x" in line:
            break
        # Stop if non-printable control characters or unicode replacement symbols appear
        unprintable = sum(1 for c in line if ord(c) < 32 and c not in "\t\r\n")
        if unprintable > 0 or "\ufffd" in line:
            break
        clean_lines.append(line)

    result = "\n".join(clean_lines).strip()

    # Truncate at the final valid table or set closing token ('};' or '}')
    last_brace = result.rfind("}")
    last_semi = result.rfind(";")
    cut_point = max(last_brace, last_semi)
    if cut_point != -1 and cut_point < len(result) - 1:
        tail = result[cut_point + 1:].strip()
        if tail and not tail.startswith("//"):
            result = result[:cut_point + 1].strip()

    return result

def main():
    if len(sys.argv) < 2:
        sys.exit("Usage: python3 extract_sass_docs.py <arch>")

    arch = sys.argv[1]
    payload_files = sorted(glob.glob(f"{arch}_payload_*.bin"), key=get_payload_num)

    if not payload_files:
        sys.exit(f"[{arch}] Error: No payload files found matching '{arch}_payload_*.bin'.")

    # 1. Decode valid text payloads and group contiguous stream runs
    decoded_runs = []
    current_run = []
    last_num = None

    for p in payload_files:
        raw_bytes = Path(p).read_bytes()
        num = get_payload_num(p)
        text_chunk = try_decode_payload(raw_bytes)

        if text_chunk is not None:
            if last_num is not None and num == last_num + 1:
                current_run.append(text_chunk)
            else:
                if current_run:
                    decoded_runs.append("".join(current_run))
                current_run = [text_chunk]
            last_num = num
        else:
            # Binary payload encountered; terminates current stream run
            if current_run:
                decoded_runs.append("".join(current_run))
                current_run = []
            last_num = None

    if current_run:
        decoded_runs.append("".join(current_run))

    # 2. Extract Instruction Definitions
    instruction_candidates = []
    for stream in decoded_runs:
        # If the stream contains both instructions and latency tables, isolate the prefix
        m = SCHED_START_RE.search(stream)
        prefix = stream[:m.start()].strip() if m else stream.strip()

        # Check for genuine instruction markers (both modern SIDL and legacy formats)
        if 'CLASS "' in prefix or "ARCHITECTURE" in prefix or "FORMAT " in prefix:
            instruction_candidates.append(prefix)

    instructions_text = max(instruction_candidates, key=len) if instruction_candidates else ""

    # 3. Extract and Clean Latency / Scheduling Tables
    latencies_text = ""
    for stream in decoded_runs:
        cleaned_lat = clean_latency_block(stream)
        if cleaned_lat:
            latencies_text = cleaned_lat
            break

    # Legacy fallback: If latencies are embedded within the instruction payload itself
    if not latencies_text and instructions_text:
        cleaned_lat = clean_latency_block(instructions_text)
        if cleaned_lat:
            latencies_text = cleaned_lat
            # Remove latencies from the instructions file
            m = SCHED_START_RE.search(instructions_text)
            if m:
                instructions_text = instructions_text[:m.start()].strip()

    if not instructions_text:
        sys.exit(f"[{arch}] Error: Failed to locate valid instruction documentation.")

    # 4. Write final output files
    inst_path = Path(f"{arch}_instructions.txt")
    lat_path = Path(f"{arch}_latencies.txt")

    inst_path.write_text(instructions_text, encoding="utf-8")
    if latencies_text:
        lat_path.write_text(latencies_text, encoding="utf-8")
    else:
        lat_path.write_text("Notice: No latency or scheduling tables found for this architecture.", encoding="utf-8")

    # Clean up intermediate binaries
    for p in payload_files:
        Path(p).unlink(missing_ok=True)

    print(f"[{arch}] Successfully generated {inst_path.name} ({inst_path.stat().st_size:,} bytes)")
    print(f"[{arch}] Successfully generated {lat_path.name} ({lat_path.stat().st_size:,} bytes)")

if __name__ == "__main__":
    main()
