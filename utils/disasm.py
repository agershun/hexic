#!/usr/bin/env python3
"""Disassemble DOS MZ executable"""

import struct
from capstone import *

def read_mz_header(data):
    """Parse MZ executable header"""
    if data[:2] != b'MZ':
        raise ValueError("Not a valid MZ executable")

    header = struct.unpack('<HHHHHHHHHHHHHH', data[:28])

    return {
        'signature': 'MZ',
        'last_page_size': header[1],
        'pages': header[2],
        'relocations': header[3],
        'header_paragraphs': header[4],
        'min_alloc': header[5],
        'max_alloc': header[6],
        'initial_ss': header[7],
        'initial_sp': header[8],
        'checksum': header[9],
        'initial_ip': header[10],
        'initial_cs': header[11],
        'reloc_table_offset': header[12],
        'overlay': header[13],
    }

def disassemble_dos(filename, start_offset=None, length=0x2000):
    """Disassemble DOS executable"""
    with open(filename, 'rb') as f:
        data = f.read()

    header = read_mz_header(data)
    print("=== MZ Header ===")
    for k, v in header.items():
        if isinstance(v, int):
            print(f"  {k}: {v} (0x{v:04x})")
        else:
            print(f"  {k}: {v}")

    # Calculate code start
    header_size = header['header_paragraphs'] * 16
    code_start = header_size

    print(f"\n=== Code starts at offset 0x{code_start:04x} ===")
    print(f"Initial CS:IP = {header['initial_cs']:04x}:{header['initial_ip']:04x}")

    # Entry point offset
    entry_offset = code_start + header['initial_cs'] * 16 + header['initial_ip']
    print(f"Entry point file offset: 0x{entry_offset:04x}")

    if start_offset is None:
        start_offset = entry_offset

    # Disassemble
    md = Cs(CS_ARCH_X86, CS_MODE_16)
    md.detail = True

    code = data[start_offset:start_offset + length]

    print(f"\n=== Disassembly from 0x{start_offset:04x} ===\n")

    for insn in md.disasm(code, start_offset):
        bytes_str = ' '.join(f'{b:02x}' for b in insn.bytes)
        print(f"0x{insn.address:05x}: {bytes_str:24s} {insn.mnemonic:8s} {insn.op_str}")

def find_strings_with_refs(filename):
    """Find string references in code"""
    with open(filename, 'rb') as f:
        data = f.read()

    # Find all printable strings
    strings = []
    current = b''
    start = 0

    for i, b in enumerate(data):
        if 32 <= b < 127:
            if not current:
                start = i
            current += bytes([b])
        else:
            if len(current) >= 4:
                strings.append((start, current.decode('ascii', errors='ignore')))
            current = b''

    print("=== Strings found ===")
    for offset, s in strings:
        if len(s) >= 5 and not s.startswith('PSQR'):  # filter asm noise
            print(f"0x{offset:05x}: {s}")

def analyze_graphics_calls(filename):
    """Look for BGI graphics function calls"""
    with open(filename, 'rb') as f:
        data = f.read()

    header = read_mz_header(data)
    header_size = header['header_paragraphs'] * 16

    md = Cs(CS_ARCH_X86, CS_MODE_16)
    code = data[header_size:]

    # Look for far calls (9A xx xx xx xx) and near calls (E8 xx xx)
    calls = []

    print("=== Analyzing calls ===")

    i = 0
    while i < len(code) - 5:
        if code[i] == 0x9A:  # far call
            offset = struct.unpack('<H', code[i+1:i+3])[0]
            segment = struct.unpack('<H', code[i+3:i+5])[0]
            calls.append((header_size + i, 'far', segment, offset))
            i += 5
        elif code[i] == 0xE8:  # near call
            rel = struct.unpack('<h', code[i+1:i+3])[0]
            target = i + 3 + rel
            calls.append((header_size + i, 'near', 0, target))
            i += 3
        else:
            i += 1

    # Count call targets
    from collections import Counter
    targets = Counter((c[2], c[3]) for c in calls)

    print("\nMost called functions:")
    for (seg, off), count in targets.most_common(30):
        print(f"  {seg:04x}:{off:04x} called {count} times")

def dump_data_segment(filename):
    """Dump likely data segments"""
    with open(filename, 'rb') as f:
        data = f.read()

    # Look for data patterns - arrays of similar values
    print("=== Looking for data tables ===\n")

    # Find sequences that look like coordinate/shape tables
    for i in range(0, len(data) - 20, 2):
        # Look for small numbers that could be coordinates
        vals = struct.unpack('<' + 'b' * 10, data[i:i+10])
        if all(-20 <= v <= 20 for v in vals):
            # Check if non-trivial
            if len(set(vals)) > 2 and any(v != 0 for v in vals):
                print(f"0x{i:05x}: {vals}")

if __name__ == "__main__":
    import sys

    filename = sys.argv[1] if len(sys.argv) > 1 else "data/HEXIS.EXE"

    print("=" * 60)
    print("HEXIS.EXE Analysis")
    print("=" * 60)

    find_strings_with_refs(filename)
    print("\n")
    analyze_graphics_calls(filename)
    print("\n")
    disassemble_dos(filename, length=0x500)
