#!/usr/bin/env python3
import sys
from pathlib import Path
import lz4.block

def main():
    if len(sys.argv) < 2:
        sys.exit("Usage: python3 extract_sass_docs.py <arch>")

    arch = sys.argv[1]
    payload_path = Path(f"{arch}.bin")

    if not payload_path.exists():
        sys.exit(f"[{arch}] Payload file {payload_path} not found.")

    compressed_data = payload_path.read_bytes()

    try:
        decompressed = lz4.block.decompress(compressed_data, uncompressed_size=0x2000000)
    except Exception as e:
        sys.exit(f"[{arch}] LZ4 decompression failed: {e}")

    text = decompressed.decode("ascii", errors="replace")

    # Split legacy latencies table if present (Maxwell/Pascal), otherwise write disclaimer
    if "OPERATION SETS" in text:
        op_idx = text.find("OPERATION SETS")
        instructions = text[:op_idx].rstrip()
        latencies = text[op_idx:].lstrip()
    else:
        instructions = text.strip()
        latencies = None

    Path(f"{arch}_instructions.txt").write_text(instructions, encoding="utf-8")
    if latencies is not None:
        Path(f"{arch}_latencies.txt").write_text(latencies, encoding="utf-8")

    payload_path.unlink(missing_ok=True)

if __name__ == "__main__":
    main()
