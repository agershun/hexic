#!/usr/bin/env python3
"""Analyze HEXIS drawing and piece logic in detail"""

import struct
from capstone import *

def disasm_range(data, start, end):
    """Disassemble a range"""
    md = Cs(CS_ARCH_X86, CS_MODE_16)
    code = data[start:end]
    result = []
    for insn in md.disasm(code, start):
        bytes_str = ' '.join(f'{b:02x}' for b in insn.bytes)
        result.append((insn.address, bytes_str, insn.mnemonic, insn.op_str))
    return result

def analyze_hexagon_drawing(filename):
    """Find exact hexagon drawing code"""
    with open(filename, 'rb') as f:
        data = f.read()

    print("=" * 70)
    print("HEXAGON DRAWING ANALYSIS")
    print("=" * 70)

    # From previous analysis, drawing loop is around 0x6270-0x6370
    # Let's look at the exact BGI calls

    # BGI functions in segment 0x0b52:
    # 0x0ea4 = MoveTo
    # 0x0ec1 = LineTo (relative)
    # 0x0e41 = Line (absolute)

    print("\n=== Drawing code at 0x62a0-0x6370 ===")
    for addr, bytes_str, mnem, ops in disasm_range(data, 0x62a0, 0x6370):
        print(f"0x{addr:05x}: {bytes_str:24s} {mnem:8s} {ops}")

    # Look for the actual hex shape coordinates
    # The code pushes pairs of values before calling LineTo

    print("\n=== Looking for coordinate patterns ===")

    code = data[0x6200:0x6400]
    coords = []

    i = 0
    while i < len(code) - 10:
        # Pattern: PUSH imm16/imm8, PUSH imm16/imm8, CALL
        if code[i] == 0xB8:  # MOV AX, imm16
            val1 = struct.unpack('<h', code[i+1:i+3])[0]  # signed
            if code[i+3] == 0x50:  # PUSH AX
                if code[i+4] == 0xB8:  # MOV AX, imm16
                    val2 = struct.unpack('<h', code[i+5:i+7])[0]
                    if code[i+7] == 0x50:  # PUSH AX
                        if code[i+8] == 0x9A:  # FAR CALL
                            target = struct.unpack('<H', code[i+9:i+11])[0]
                            if target == 0x0ec1:  # LineTo relative
                                coords.append((0x6200 + i, val1, val2, "LineRel"))
                            elif target == 0x0ea4:  # MoveTo
                                coords.append((0x6200 + i, val1, val2, "MoveTo"))
        i += 1

    print("\nCoordinates found:")
    for addr, x, y, func in coords:
        print(f"  0x{addr:05x}: {func}({x}, {y})")

    # The hexagon seems to be drawn with relative moves
    # Let's trace through the drawing loop more carefully

    print("\n=== Full drawing routine analysis ===")

    # Find the cell drawing function - look for a complete pattern
    # The loop counter [bp-0x2c] goes from 1 to 5
    # The outer counter [bp-0x2d] goes from 1 to 6

    for addr, bytes_str, mnem, ops in disasm_range(data, 0x62b0, 0x62f0):
        print(f"0x{addr:05x}: {bytes_str:24s} {mnem:8s} {ops}")


def analyze_piece_structure(filename):
    """Analyze how pieces are stored and drawn"""
    with open(filename, 'rb') as f:
        data = f.read()

    print("\n" + "=" * 70)
    print("PIECE STRUCTURE ANALYSIS")
    print("=" * 70)

    # The key is to find where piece shapes are defined
    # From analysis: piece type is compared (0-5 or 0-9)
    # and then cells are drawn

    # Look at the code that checks piece type and draws cells
    # This is around the collision detection code

    print("\n=== Piece collision/drawing code around 0x1a80-0x1c00 ===")

    for addr, bytes_str, mnem, ops in disasm_range(data, 0x1a80, 0x1c00):
        # Focus on the important parts
        if 'cmp' in mnem or 'je' in mnem or 'jne' in mnem or '06d' in ops:
            print(f"0x{addr:05x}: {bytes_str:24s} {mnem:8s} {ops}")

    # Look for the piece type switch
    print("\n=== Looking for piece type handling ===")

    # Search for pattern: CMP AL, 0/1/2/3/4/5 followed by jumps
    code = data[0x0c00:0x6000]

    piece_handlers = []
    i = 0
    while i < len(code) - 20:
        # CMP AL, imm8 pattern for piece types
        if code[i] == 0x3C and code[i+1] <= 10:
            piece_type = code[i+1]
            # Check if followed by conditional jump
            if code[i+2] in [0x74, 0x75]:  # JE or JNE
                addr = 0x0c00 + i
                piece_handlers.append((addr, piece_type))
        i += 1

    # Group by proximity to find piece type switch statements
    print("\nPotential piece type comparisons:")
    prev_addr = 0
    for addr, ptype in piece_handlers:
        if addr - prev_addr > 100 and prev_addr > 0:
            print("---")
        print(f"  0x{addr:05x}: CMP AL, {ptype}")
        prev_addr = addr


def analyze_piece_drawing_detail(filename):
    """Find exact piece cell positions"""
    with open(filename, 'rb') as f:
        data = f.read()

    print("\n" + "=" * 70)
    print("PIECE CELL POSITION ANALYSIS")
    print("=" * 70)

    # The collision detection code at 0x1a94 uses:
    # AL = [0x6d8] (X position)
    # CX from [0x6d7] (Y position)
    # Then: Y * 26 + X to get board index
    # Offset +/- 1,2,3 for different cells of the piece

    # Let's trace through piece type 0 (first piece)
    print("\n=== Tracing piece type checks in collision code ===")

    # The code at 0x1a94 onwards
    for addr, bytes_str, mnem, ops in disasm_range(data, 0x1a80, 0x1c50):
        print(f"0x{addr:05x}: {bytes_str:24s} {mnem:8s} {ops}")

    print("\n" + "=" * 70)

    # Also look at the piece spawning code
    print("\n=== Piece spawn/init code ===")

    # Search for where piece type is set (stored in a variable)
    # Look for random number generation followed by piece type storage

    code = data[0x6f0:]  # Skip header

    # Find INT 21h with AH=2C (get time - often used for random seed)
    for i in range(len(code) - 4):
        if code[i] == 0xB4 and code[i+1] == 0x2C:  # MOV AH, 2Ch
            print(f"0x{0x6f0 + i:05x}: MOV AH, 2Ch (get time for random)")


def find_piece_data_tables(filename):
    """Search for piece data tables more thoroughly"""
    with open(filename, 'rb') as f:
        data = f.read()

    print("\n" + "=" * 70)
    print("SEARCHING FOR PIECE DATA TABLES")
    print("=" * 70)

    # Look for small arrays that could be piece offsets
    # Each piece has 4 cells, each cell has (dx, dy) offset
    # So 8 bytes per piece, 6 pieces = 48 bytes
    # Or if stored per rotation: 6 pieces * 6 rotations * 8 = 288 bytes

    header_size = 0x6f0

    # Strategy: look for sequences of small signed bytes
    # that could represent cell offsets (-3 to +3 range)

    print("\nLooking for offset patterns...")

    for start in range(header_size, len(data) - 48):
        # Read 48 bytes
        chunk = data[start:start+48]

        # Check if all bytes are in valid range for offsets
        vals = struct.unpack('<' + 'b' * 48, chunk)

        # Valid offset range
        if all(-4 <= v <= 4 for v in vals):
            # Should have some variety
            unique = set(vals)
            if len(unique) >= 5:
                # Not too many zeros
                zeros = sum(1 for v in vals if v == 0)
                if zeros < 30:
                    print(f"\n0x{start:05x}: Possible piece offsets")
                    # Print as 6 groups of 8 (4 cells * 2 coords)
                    for j in range(6):
                        piece = vals[j*8:(j+1)*8]
                        cells = [(piece[k], piece[k+1]) for k in range(0, 8, 2)]
                        print(f"  Piece {j}: {cells}")


def analyze_main_draw_piece(filename):
    """Find the main piece drawing routine"""
    with open(filename, 'rb') as f:
        data = f.read()

    print("\n" + "=" * 70)
    print("MAIN PIECE DRAWING ROUTINE")
    print("=" * 70)

    # Look for code that:
    # 1. Reads piece type
    # 2. Reads piece position
    # 3. Calculates screen coordinates
    # 4. Draws hexagon for each cell

    # The multiplication by 8 (SHL 3) is used for pixel positioning
    # Found earlier at 0x62a9: SHL AX, 3

    # Let's look for the complete draw piece function
    print("\n=== Code with SHL by 3 (pixel positioning) ===")

    code = data[0x6f0:]
    for i in range(len(code) - 5):
        # SHL AX, CL where CL=3
        if code[i] == 0xB1 and code[i+1] == 0x03:  # MOV CL, 3
            if code[i+2] == 0xD3 and code[i+3] == 0xE0:  # SHL AX, CL
                addr = 0x6f0 + i
                print(f"0x{addr:05x}: MOV CL, 3 / SHL AX, CL")

                # Disassemble context
                start = max(0x6f0, addr - 20)
                for a, b, m, o in disasm_range(data, start, addr + 20):
                    marker = ">>>" if a == addr else "   "
                    print(f"  {marker} 0x{a:05x}: {m:8s} {o}")
                print()


def analyze_draw_cell_function(filename):
    """Analyze the individual cell drawing function"""
    with open(filename, 'rb') as f:
        data = f.read()

    print("\n" + "=" * 70)
    print("CELL DRAWING FUNCTION")
    print("=" * 70)

    # The hexagon drawing with LineRel calls
    # From 0x62bd we see: loop from 1 to 5, drawing lines

    # Let's see the exact sequence of line draws
    print("\n=== Hexagon line sequence (0x62bd-0x62f0) ===")

    # This draws one "row" of the hexagon pattern
    # The inner loop draws 5 line segments

    # LineRel(0x0a, 0x04) = (10, 4)
    # LineRel(0x13, -8) = (19, -8)
    # LineRel(0x09, 0x04) = (9, 4)

    # That's only 3 lines - so the hexagon is made of repeated patterns

    for addr, bytes_str, mnem, ops in disasm_range(data, 0x62b4, 0x6370):
        print(f"0x{addr:05x}: {bytes_str:24s} {mnem:8s} {ops}")


if __name__ == "__main__":
    filename = "data/HEXIS.EXE"

    analyze_hexagon_drawing(filename)
    analyze_piece_structure(filename)
    analyze_piece_drawing_detail(filename)
    find_piece_data_tables(filename)
    analyze_main_draw_piece(filename)
    analyze_draw_cell_function(filename)
