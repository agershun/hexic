#!/usr/bin/env python3
"""Deep disassembly of HEXIS game logic"""

import struct
from capstone import *

def disasm_range(data, start, end, base_offset=0):
    """Disassemble a range of bytes"""
    md = Cs(CS_ARCH_X86, CS_MODE_16)
    code = data[start:end]

    result = []
    for insn in md.disasm(code, start + base_offset):
        bytes_str = ' '.join(f'{b:02x}' for b in insn.bytes)
        result.append(f"0x{insn.address:05x}: {bytes_str:24s} {insn.mnemonic:8s} {insn.op_str}")

    return result

def analyze_main_game(filename):
    with open(filename, 'rb') as f:
        data = f.read()

    header_size = 0x6f0

    print("=" * 70)
    print("HEXIS Deep Disassembly")
    print("=" * 70)

    # Key handling at 0x007df
    print("\n=== Key Handler (0x07cf-0x0900) ===")
    for line in disasm_range(data, 0x07cf, 0x0900):
        print(line)

    # Piece type multiplication at 0x03d7d
    print("\n=== Piece Logic around IMUL (0x03d60-0x03df0) ===")
    for line in disasm_range(data, 0x03d60, 0x03e00):
        print(line)

    # Drawing loop with 7 at 0x06290
    print("\n=== Drawing Loop (0x06270-0x06350) ===")
    for line in disasm_range(data, 0x06270, 0x06370):
        print(line)

    # Most accessed variables 0x06d7, 0x06d8
    # Find code that manipulates these
    print("\n=== Variable 0x06d7/0x06d8 usage ===")

    code = data[header_size:]
    for i in range(len(code) - 5):
        # Look for access to 06d7 or 06d8
        if code[i:i+2] == b'\xd7\x06' or code[i:i+2] == b'\xd8\x06':
            # Disassemble context
            start = max(0, i - 10)
            end = min(len(code), i + 20)

            context = disasm_range(data, header_size + start, header_size + end)
            if len(context) > 0:
                print(f"\n--- Context at 0x{header_size + i:05x} ---")
                for line in context[:8]:
                    print(line)

    # Score display - find "Score" string usage
    print("\n=== Score String Usage ===")
    score_pos = data.find(b'Score : 0')
    if score_pos > 0:
        print(f"'Score : 0' at 0x{score_pos:x}")

        # Find code that references this
        # Look for LEA or MOV with this address
        addr_bytes = struct.pack('<H', score_pos & 0xFFFF)
        for i in range(header_size, len(data) - 10):
            if data[i:i+2] == addr_bytes:
                context = disasm_range(data, max(header_size, i-10), min(len(data), i+20))
                if context:
                    print(f"\n--- Reference at 0x{i:x} ---")
                    for line in context[:10]:
                        print(line)


def find_piece_data(filename):
    """Try to find piece shape data by looking at how it's accessed"""
    with open(filename, 'rb') as f:
        data = f.read()

    header_size = 0x6f0

    print("\n" + "=" * 70)
    print("Looking for Piece Data Arrays")
    print("=" * 70)

    # The IMUL 6 suggests 6 pieces
    # Each piece might have 4 cells
    # Cells could be stored as x,y pairs (bytes)

    # Look for arrays of small values accessed after IMUL
    imul_pos = 0x03d7d

    print(f"\nCode around IMUL at 0x{imul_pos:x}:")
    for line in disasm_range(data, imul_pos - 20, imul_pos + 60):
        print(line)

    # Look for repeated patterns of 6 or 8 bytes
    print("\n=== Searching for piece shape tables ===")

    for i in range(header_size, len(data) - 100):
        # Look for patterns like: small_val, small_val repeated 24+ times
        # (6 pieces * 4 cells = 24 coordinate pairs or 48 bytes)

        chunk = data[i:i+48]
        try:
            vals = struct.unpack('<' + 'b' * 48, chunk)

            # Check if these look like coordinate offsets
            # Values should be small (-5 to 5 range for a grid)
            if all(-5 <= v <= 5 for v in vals):
                # Should have variety
                unique = len(set(vals))
                if 5 <= unique <= 20:
                    # Should have some non-zero
                    non_zero = sum(1 for v in vals if v != 0)
                    if 15 <= non_zero <= 40:
                        print(f"\n0x{i:05x}: Potential piece table")
                        for j in range(6):
                            piece = vals[j*8:(j+1)*8]
                            # Format as 4 pairs
                            pairs = [(piece[k], piece[k+1]) for k in range(0, 8, 2)]
                            print(f"  Piece {j}: {pairs}")
        except:
            pass


def analyze_board_array(filename):
    """Find and analyze the game board array"""
    with open(filename, 'rb') as f:
        data = f.read()

    header_size = 0x6f0

    print("\n" + "=" * 70)
    print("Board Array Analysis")
    print("=" * 70)

    # Variables at 0x06d7-0x06e2 are heavily accessed
    # Let's see how they're used

    # Look for code that does: [board + y * width + x]
    # This would be: IMUL or MUL followed by ADD

    code = data[header_size:]

    print("\nLooking for board access patterns (y * width + x)...")

    for i in range(len(code) - 20):
        # Pattern: MUL by constant (board width)
        # Common widths: 10, 12, 20, 26

        if code[i] == 0xB8:  # MOV AX, imm16
            width = struct.unpack('<H', code[i+1:i+3])[0]
            if width in [10, 12, 20, 26]:
                # Check if followed by MUL
                if code[i+3] in [0xF6, 0xF7]:  # MUL
                    print(f"0x{header_size + i:05x}: MOV AX, {width} followed by MUL")

                    # Disassemble context
                    context = disasm_range(data, header_size + i - 5, header_size + i + 30)
                    for line in context:
                        print(f"  {line}")

    # Look for board base address
    print("\nLooking for board base address references...")

    # Common pattern: LEA reg, [base + offset]
    for i in range(len(code) - 10):
        if code[i] == 0x8D:  # LEA
            # Check for base + indexed access
            if code[i+1] & 0xC0 == 0x80:  # 16-bit displacement
                disp = struct.unpack('<h', code[i+2:i+4])[0]
                if 0x100 < abs(disp) < 0x1000:
                    print(f"0x{header_size + i:05x}: LEA with displacement 0x{disp & 0xFFFF:04x}")


def analyze_score_system(filename):
    """Analyze scoring logic"""
    with open(filename, 'rb') as f:
        data = f.read()

    header_size = 0x6f0

    print("\n" + "=" * 70)
    print("Score System Analysis")
    print("=" * 70)

    # Find +1000 related code
    plus_pos = data.find(b'+1000')
    print(f"\n'+1000' bonus string at: 0x{plus_pos:x}")

    # Find code that displays this
    # Look for references to this address
    for i in range(header_size, len(data) - 10):
        # Check if this address is referenced
        if data[i:i+2] == struct.pack('<H', plus_pos & 0xFFFF):
            print(f"\nReference at 0x{i:x}:")
            context = disasm_range(data, max(header_size, i-30), min(len(data), i+30))
            for line in context[:15]:
                print(f"  {line}")

    # Look for score variable manipulation
    # Score is likely a 16 or 32 bit value

    print("\nLooking for score increment patterns...")

    code = data[header_size:]
    for i in range(len(code) - 10):
        # ADD to memory with immediate value
        if code[i] == 0x81 and code[i+1] == 0x06:  # ADD word [xxxx], imm16
            addr = struct.unpack('<H', code[i+2:i+4])[0]
            val = struct.unpack('<H', code[i+4:i+6])[0]
            if val in [1, 10, 50, 100, 1000]:
                print(f"0x{header_size + i:05x}: ADD [0x{addr:04x}], {val}")


def analyze_line_clear(filename):
    """Find line clearing logic"""
    with open(filename, 'rb') as f:
        data = f.read()

    header_size = 0x6f0

    print("\n" + "=" * 70)
    print("Line Clear Logic")
    print("=" * 70)

    # Find "Full Lines" reference
    lines_pos = data.find(b'Full Lines')
    print(f"'Full Lines' at: 0x{lines_pos:x}")

    # Look for loops that check full rows
    # Pattern: loop through row, check if all cells filled

    code = data[header_size:]

    print("\nLooking for line check loops...")

    # Find compare with 0 in loops
    for i in range(len(code) - 20):
        # CMP byte ptr [mem], 0 = 80 3e xx xx 00
        if code[i] == 0x80 and code[i+1] == 0x3E:
            addr = struct.unpack('<H', code[i+2:i+4])[0]
            if code[i+4] == 0x00:
                # Check if this is in a loop (LOOP instruction nearby)
                for j in range(i, min(i+50, len(code))):
                    if code[j] == 0xE2:  # LOOP
                        print(f"0x{header_size + i:05x}: CMP [0x{addr:04x}], 0 - in loop")
                        break


if __name__ == "__main__":
    filename = "data/HEXIS.EXE"

    analyze_main_game(filename)
    find_piece_data(filename)
    analyze_board_array(filename)
    analyze_score_system(filename)
    analyze_line_clear(filename)
