#!/usr/bin/env python3
"""Deep analysis of HEXIS.EXE game logic"""

import struct
from capstone import *

def analyze_hexis(filename):
    with open(filename, 'rb') as f:
        data = f.read()

    print("=" * 70)
    print("HEXIS.EXE Deep Analysis")
    print("=" * 70)

    # MZ Header
    header_size = struct.unpack('<H', data[8:10])[0] * 16
    print(f"\nCode starts at: 0x{header_size:04x}")

    # Look for shape definitions - small numbers in patterns
    print("\n=== Looking for piece shape tables ===")

    # Common pattern: arrays of small signed bytes for coordinates
    # Search for patterns that look like tetris piece definitions

    for i in range(header_size, len(data) - 40):
        # Look for sequences of small numbers (0-20 range)
        chunk = data[i:i+40]

        # Check if this could be piece data
        # Pieces typically have 4 cells with x,y coordinates
        try:
            vals = struct.unpack('<' + 'B' * 40, chunk)

            # Look for repeating patterns of small coords
            small_count = sum(1 for v in vals if v < 30)
            if small_count > 30:
                # Check for structure
                unique = len(set(vals))
                if 3 <= unique <= 15:
                    print(f"\n0x{i:05x}: potential piece data")
                    for j in range(0, 40, 8):
                        row = vals[j:j+8]
                        print(f"  {row}")
        except:
            pass

    # Look for the game board dimensions
    print("\n=== Looking for board constants ===")

    # Search for common board sizes
    for i in range(header_size, len(data) - 4):
        val = struct.unpack('<H', data[i:i+2])[0]
        # Look for typical game dimensions
        if val in [10, 20, 26, 13, 12, 6, 7]:
            # Check context
            prev = struct.unpack('<H', data[i-2:i])[0] if i >= 2 else 0
            next_val = struct.unpack('<H', data[i+2:i+4])[0]
            if prev in [10, 20, 26, 13, 12, 6, 7] or next_val in [10, 20, 26, 13, 12, 6, 7]:
                print(f"0x{i:05x}: dimension candidate = {val} (prev={prev}, next={next_val})")

    # Find score values
    print("\n=== Looking for score constants ===")
    for i in range(header_size, len(data) - 4):
        val = struct.unpack('<H', data[i:i+2])[0]
        if val in [10, 20, 30, 50, 100, 200, 300, 500, 1000]:
            # Check if near "Score" string
            context = data[max(0,i-100):i+100]
            if b'Score' in context or b'1000' in context:
                print(f"0x{i:05x}: score value = {val}")

    # Analyze key handling code
    print("\n=== Key code analysis ===")

    # Search for keyboard scan codes
    # 7=47h, 8=48h, 9=49h, 4=4Bh in keypad
    key_patterns = [
        (0x47, "Numpad 7 - Left"),
        (0x48, "Numpad 8 - Rotate"),
        (0x49, "Numpad 9 - Right"),
        (0x4B, "Numpad 4"),
        (0x39, "Space"),
        (0x01, "Escape"),
        (0x44, "F10"),
    ]

    for code, desc in key_patterns:
        for i in range(header_size, len(data) - 4):
            if data[i] == 0x3C and data[i+1] == code:  # CMP AL, code
                print(f"0x{i:05x}: CMP AL, 0x{code:02x} - {desc}")
                break

    # Look for graphics coordinates
    print("\n=== Graphics coordinate analysis ===")

    # BGI uses integer coordinates
    # Look for patterns that could be screen positions

    coord_candidates = []
    for i in range(header_size, len(data) - 4):
        x = struct.unpack('<H', data[i:i+2])[0]
        y = struct.unpack('<H', data[i+2:i+4])[0]

        # VGA 640x480
        if 0 < x < 640 and 0 < y < 480:
            if x % 10 == 0 and y % 10 == 0:  # Round numbers
                coord_candidates.append((i, x, y))

    print(f"Found {len(coord_candidates)} potential screen coordinates")
    # Show first few
    for i, x, y in coord_candidates[:20]:
        print(f"  0x{i:05x}: ({x}, {y})")

    # Disassemble drawing routines
    print("\n=== Looking for drawing routines ===")

    md = Cs(CS_ARCH_X86, CS_MODE_16)

    # Look for "putpixel" like patterns - setting video memory
    code = data[header_size:header_size + 0x5000]

    # Find INT 10h calls (BIOS video)
    for i in range(len(code) - 2):
        if code[i] == 0xCD and code[i+1] == 0x10:
            offset = header_size + i
            print(f"0x{offset:05x}: INT 10h (BIOS video interrupt)")

    # Look for BGI function calls (far calls to specific segments)
    print("\n=== BGI function analysis ===")

    bgi_functions = {
        0x0520: "RegisterBGIFont",
        0x036b: "InitGraph",
        0x09ec: "SetGraphMode",
        0x00a3: "GetGraphMode",
        0x15c6: "SetColor",
        0x17a5: "SetFillStyle",
        0x17ed: "Bar",
        0x1a38: "OutTextXY",
        0x18e1: "Line",
        0x11dc: "Circle or Arc",
        0x0ec1: "Rectangle",
        0x0e41: "MoveTo",
        0x1ac1: "SetTextStyle",
    }

    for i in range(len(code) - 5):
        if code[i] == 0x9A:  # far call
            offset_val = struct.unpack('<H', code[i+1:i+3])[0]
            segment = struct.unpack('<H', code[i+3:i+5])[0]

            if segment == 0x0b52:  # BGI segment
                func_name = bgi_functions.get(offset_val, f"BGI_{offset_val:04x}")
                file_offset = header_size + i
                print(f"0x{file_offset:05x}: call {func_name}")


def find_piece_shapes(filename):
    """Try to find tetris piece shape definitions"""
    with open(filename, 'rb') as f:
        data = f.read()

    header_size = struct.unpack('<H', data[8:10])[0] * 16

    print("\n" + "=" * 70)
    print("Searching for piece shape definitions")
    print("=" * 70)

    # In Tetris-like games, pieces are often defined as:
    # - Array of 4 (x,y) coordinates
    # - Or as 4x4 bitmaps
    # - Or as relative offsets

    # Look for repeated patterns of 4 small numbers
    for i in range(header_size, len(data) - 32):
        chunk = data[i:i+32]

        # Pattern 1: 4 pairs of coordinates (8 bytes per piece)
        # Each coord typically 0-3 or 0-4
        coords = struct.unpack('<' + 'b' * 8, chunk[:8])
        if all(-5 <= c <= 5 for c in coords):
            if len(set(coords)) >= 4:  # Not all same value
                # Check next few bytes for similar pattern
                coords2 = struct.unpack('<' + 'b' * 8, chunk[8:16])
                if all(-5 <= c <= 5 for c in coords2):
                    print(f"0x{i:05x}: Possible shape table:")
                    for j in range(4):
                        shape = struct.unpack('<' + 'b' * 8, chunk[j*8:(j+1)*8])
                        print(f"  Shape {j}: {shape}")

    # Look for bitmap patterns (4 bytes per row, 4 rows)
    print("\n=== Looking for bitmap shape definitions ===")
    for i in range(header_size, len(data) - 64):
        # Bitmap pieces often have specific bit patterns
        chunk = data[i:i+64]

        # Count how many bytes have only few bits set
        low_bits = sum(1 for b in chunk if bin(b).count('1') <= 4)
        if low_bits > 48:
            rows = [chunk[j:j+4] for j in range(0, 64, 4)]
            non_zero = sum(1 for row in rows if any(b != 0 for b in row))
            if 4 <= non_zero <= 12:
                print(f"\n0x{i:05x}: Possible bitmap shapes")
                for j in range(16):
                    row = rows[j]
                    bits = ''.join(f'{b:08b}' for b in row)
                    if any(b != 0 for b in row):
                        print(f"  Row {j:2d}: {row} = {bits}")


def analyze_game_loop(filename):
    """Analyze main game loop structure"""
    with open(filename, 'rb') as f:
        data = f.read()

    header_size = struct.unpack('<H', data[8:10])[0] * 16

    print("\n" + "=" * 70)
    print("Game Loop Analysis")
    print("=" * 70)

    md = Cs(CS_ARCH_X86, CS_MODE_16)
    code = data[header_size:]

    # Look for timer/delay loops
    print("\n=== Timer patterns ===")
    for i in range(len(code) - 10):
        # LOOP instruction
        if code[i] == 0xE2:
            file_offset = header_size + i
            print(f"0x{file_offset:05x}: LOOP instruction")

        # INT 1Ah (timer)
        if code[i] == 0xCD and code[i+1] == 0x1A:
            file_offset = header_size + i
            print(f"0x{file_offset:05x}: INT 1Ah (timer)")

        # INT 21h function 2Ch (get time)
        if i < len(code) - 3:
            if code[i] == 0xB4 and code[i+1] == 0x2C and code[i+2] == 0xCD and code[i+3] == 0x21:
                file_offset = header_size + i
                print(f"0x{file_offset:05x}: Get time (INT 21h, AH=2Ch)")


if __name__ == "__main__":
    filename = "data/HEXIS.EXE"

    analyze_hexis(filename)
    find_piece_shapes(filename)
    analyze_game_loop(filename)
