#!/usr/bin/env python3
"""Find HEXIS game logic - piece shapes, scoring, etc."""

import struct
from capstone import *

def analyze_hexis_detailed(filename):
    with open(filename, 'rb') as f:
        data = f.read()

    header_size = struct.unpack('<H', data[8:10])[0] * 16
    print(f"Header size: 0x{header_size:x}")

    # Find important data areas
    print("\n=== Looking for game constants ===")

    # Board dimensions - look for values like 10, 20, 26
    # Score values - 100, 1000
    # Color values - 1-15 for EGA

    # Search for the +1000 bonus near score code
    pos = data.find(b'+1000')
    print(f"\n'+1000' string at: 0x{pos:x}")

    # Look around this area for the actual value 1000 = 0x03E8
    for i in range(max(0, pos-100), min(len(data), pos+100)):
        val = struct.unpack('<H', data[i:i+2])[0]
        if val == 1000:
            print(f"  Value 1000 at: 0x{i:x}")
        if val == 100:
            print(f"  Value 100 at: 0x{i:x}")

    # Find drawing code by looking for specific BGI patterns
    print("\n=== Disassembling key areas ===")

    md = Cs(CS_ARCH_X86, CS_MODE_16)

    # Find the game data area - look for board array
    # Typical board: 10x20 = 200 bytes or 26x10 with offsets

    # Look for code that manipulates small values in loops
    # This is likely piece/board manipulation

    # Find the main game initialization
    # Look for code that sets up variables after "Choose Level"

    choose_pos = data.find(b'Choose Level')
    print(f"\n'Choose Level' at: 0x{choose_pos:x}")

    if choose_pos > 0:
        # Disassemble code before this string reference
        start = max(header_size, choose_pos - 500)
        code = data[start:choose_pos]

        print(f"\nCode before 'Choose Level':")
        for insn in list(md.disasm(code, start))[-30:]:
            bytes_str = ' '.join(f'{b:02x}' for b in insn.bytes)
            print(f"0x{insn.address:05x}: {bytes_str:20s} {insn.mnemonic:8s} {insn.op_str}")

    # Find key handling - look for keyboard scan code comparisons
    print("\n=== Key handling code ===")

    # Scan codes: 7=0x08, 8=0x09, 9=0x0A (top row numbers)
    # or numpad: 7=0x47, 8=0x48, 9=0x49
    # Space = 0x39, Esc = 0x01

    code = data[header_size:]

    key_locations = []
    for i in range(len(code) - 5):
        # CMP AL, imm8 = 3C xx
        if code[i] == 0x3C:
            key = code[i+1]
            # Check for game keys
            if key in [0x01, 0x02, 0x04, 0x05, 0x07, 0x08, 0x09,
                      0x39, 0x44, 0x47, 0x48, 0x49, 0x4B]:
                key_locations.append((header_size + i, key))

    print(f"Found {len(key_locations)} key comparisons")

    # Look for clusters of key handling
    prev = 0
    cluster = []
    for loc, key in key_locations:
        if loc - prev < 50 and prev > 0:
            cluster.append((loc, key))
        else:
            if len(cluster) > 3:
                print(f"\nKey cluster at 0x{cluster[0][0]:05x}:")
                for l, k in cluster:
                    print(f"  0x{l:05x}: key 0x{k:02x}")
            cluster = [(loc, key)]
        prev = loc

    if len(cluster) > 3:
        print(f"\nKey cluster at 0x{cluster[0][0]:05x}:")
        for l, k in cluster:
            print(f"  0x{l:05x}: key 0x{k:02x}")

    # Find piece rotation code - look for multiplication patterns
    print("\n=== Looking for rotation/piece logic ===")

    # Rotation often involves:
    # - Table lookups
    # - 90-degree rotation formulas
    # - Piece type * 4 states

    for i in range(len(code) - 10):
        # Look for: IMUL or MUL with small constants
        if code[i] == 0x69:  # IMUL r16, r/m16, imm16
            if 2 <= code[i+3] <= 10:
                print(f"0x{header_size+i:05x}: IMUL with constant {code[i+3]}")
        if code[i] == 0x6B:  # IMUL r16, r/m8, imm8
            if 2 <= code[i+2] <= 10:
                print(f"0x{header_size+i:05x}: IMUL with constant {code[i+2]}")

    # Find score calculation
    print("\n=== Looking for score calculation ===")

    # Search for ADD to memory locations
    # Score often uses: score += lines * level * base

    for i in range(len(code) - 6):
        # ADD word ptr [xxxx], imm
        if code[i] == 0x83 and code[i+1] == 0x06:
            addr = struct.unpack('<H', code[i+2:i+4])[0]
            val = code[i+4]
            if 1 <= val <= 100:
                print(f"0x{header_size+i:05x}: ADD [0x{addr:04x}], {val}")

        # ADD word ptr [xxxx], reg
        if code[i] == 0x01:
            if code[i+1] & 0xC0 == 0x00:  # Memory operand
                print(f"0x{header_size+i:05x}: ADD [mem], reg")

    # Find the piece shape data
    print("\n=== Looking for piece definitions ===")

    # Tetris pieces are often stored as 4x4 bitmaps or coordinate lists
    # For HEXIS with hexagonal pieces, might be different

    # Look for small arrays of coordinates
    for i in range(header_size, len(data) - 48):
        # Look for 6 pieces * 4 rotations * 4 cells * 2 coords = 192 bytes
        # Or simpler: 6-7 pieces with 4 cells each

        chunk = data[i:i+48]
        vals = struct.unpack('<' + 'b' * 48, chunk)

        # Check if all values are small (-10 to 10)
        if all(-10 <= v <= 10 for v in vals):
            # Check for pattern: pairs of coords
            non_zero = sum(1 for v in vals if v != 0)
            if 16 <= non_zero <= 40:  # Reasonable for piece coords
                # Check if it looks like coordinate pairs
                unique = len(set(vals))
                if 4 <= unique <= 15:
                    print(f"\n0x{i:05x}: Potential piece data")
                    for j in range(6):
                        piece = vals[j*8:(j+1)*8]
                        print(f"  Piece {j}: {piece}")
                    break  # Just show first match

    # Analyze drawing code
    print("\n=== Drawing routines ===")

    # Find calls to BGI functions with specific parameters
    # This tells us coordinates and colors used

    for i in range(len(code) - 20):
        # Look for: PUSH imm16, PUSH imm16, CALL (pushing coordinates)
        if code[i] == 0x68:  # PUSH imm16
            val1 = struct.unpack('<H', code[i+1:i+3])[0]
            if code[i+3] == 0x68:  # Another PUSH imm16
                val2 = struct.unpack('<H', code[i+4:i+6])[0]
                # Check if these look like coordinates
                if 0 < val1 < 640 and 0 < val2 < 480:
                    if code[i+6] == 0x9A:  # FAR CALL
                        target = struct.unpack('<H', code[i+7:i+9])[0]
                        if target in [0x17ed, 0x18e1, 0x11dc]:  # Bar, Line, etc
                            print(f"0x{header_size+i:05x}: Drawing at ({val1}, {val2})")


def find_data_structures(filename):
    """Find game data structures"""
    with open(filename, 'rb') as f:
        data = f.read()

    header_size = struct.unpack('<H', data[8:10])[0] * 16

    print("\n" + "=" * 70)
    print("Data Structure Analysis")
    print("=" * 70)

    # Look for the board array
    # Typically starts with zeros and is accessed frequently

    # Find variables that are accessed often
    md = Cs(CS_ARCH_X86, CS_MODE_16)
    code = data[header_size:]

    mem_accesses = {}

    for i in range(len(code) - 4):
        # MOV to/from memory [xxxx]
        if code[i] in [0xA0, 0xA1, 0xA2, 0xA3]:  # MOV AL/AX, [xxxx] and reverse
            addr = struct.unpack('<H', code[i+1:i+3])[0]
            if 0x100 < addr < 0x8000:
                mem_accesses[addr] = mem_accesses.get(addr, 0) + 1

    print("\nMost accessed memory locations:")
    for addr, count in sorted(mem_accesses.items(), key=lambda x: -x[1])[:30]:
        print(f"  [0x{addr:04x}]: {count} accesses")

    # These are likely game variables:
    # - score
    # - level
    # - lines
    # - current piece
    # - next piece
    # - piece position x, y
    # - board array base


def extract_piece_drawing(filename):
    """Extract how pieces are drawn"""
    with open(filename, 'rb') as f:
        data = f.read()

    header_size = struct.unpack('<H', data[8:10])[0] * 16

    print("\n" + "=" * 70)
    print("Piece Drawing Analysis")
    print("=" * 70)

    # Find the draw piece function by looking for patterns

    md = Cs(CS_ARCH_X86, CS_MODE_16)

    # Look for code that draws hexagons or blocks
    # This usually involves:
    # 1. Calculate screen position from grid position
    # 2. Draw filled polygon or rectangle
    # 3. Maybe draw outline

    code = data[header_size:]

    # Find loops that might draw 4 cells of a piece
    loop_starts = []
    for i in range(len(code) - 10):
        # MOV CX, 4 (or similar small loop count)
        if code[i] == 0xB9:  # MOV CX, imm16
            count = struct.unpack('<H', code[i+1:i+3])[0]
            if 3 <= count <= 10:
                loop_starts.append((header_size + i, count))

    print("\nPotential piece drawing loops:")
    for loc, count in loop_starts[:20]:
        print(f"  0x{loc:05x}: loop count = {count}")

    # Find color setting before drawing
    print("\nColor settings:")
    for i in range(len(code) - 10):
        # SetColor is BGI function at 0x15c6
        if code[i] == 0x9A:  # FAR CALL
            target = struct.unpack('<H', code[i+1:i+3])[0]
            if target == 0x15c6:
                # Look at what was pushed before
                if code[i-3] == 0xB8:  # MOV AX, imm16
                    color = struct.unpack('<H', code[i-2:i])[0]
                    print(f"  0x{header_size+i:05x}: SetColor({color})")


if __name__ == "__main__":
    filename = "data/HEXIS.EXE"

    analyze_hexis_detailed(filename)
    find_data_structures(filename)
    extract_piece_drawing(filename)
