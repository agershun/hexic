# HEXIS.EXE Reverse Engineering Documentation

## Overview
- **File**: HEXIS.EXE (DOS executable, MZ format)
- **Era**: ~1987-1988
- **Language**: Borland Pascal/Turbo Pascal with BGI graphics
- **Header size**: 0x6f0 (1776 bytes)
- **Code start**: 0x6f0

## Graphics System

### BGI (Borland Graphics Interface)
- **Segment**: 0x0b52
- **Mode**: EGA 640x350 or VGA 640x480 (auto-detect)
- **Font**: Built-in BGI font

### Key BGI Functions (at segment 0x0b52)
| Offset | Function |
|--------|----------|
| 0x036b | InitGraph |
| 0x09ec | SetGraphMode |
| 0x00a3 | GetGraphMode |
| 0x15c6 | SetColor |
| 0x17a5 | SetFillStyle |
| 0x17ed | Bar |
| 0x18e1 | Line |
| 0x0ea4 | MoveTo |
| 0x0ec1 | LineRel |
| 0x0e41 | Line (absolute) |
| 0x11dc | Circle/Arc |
| 0x1a38 | OutTextXY |
| 0x1ac1 | SetTextStyle |
| 0x0520 | RegisterBGIFont |

### Honeycomb Cell Drawing
- Uses LineRel pattern from 0x62b4-0x6370
- Row type 1 (0x62bd-0x62de): LineRel(10, 4), LineRel(19, -8), LineRel(9, 4)
  - Goes: right+down 4px, then right+up 8px, then right+down 4px
  - Creates peak at start, valley in middle, peak at end
- Row type 2 (0x6336-0x6357): LineRel(10, -4), LineRel(19, 8), LineRel(9, -4)
  - Goes: right+up 4px, then right+down 8px, then right+up 4px
  - Creates valley at start, peak in middle, valley at end
- Total wave width: 10 + 19 + 9 = 38px
- Flat segment: 19px (the center part)
- Zigzag amplitude: 8px peak-to-valley (4px up + 4px down from center)
- Row spacing: row * 8 (from shl ax, 3 at 0x6322)
- MoveTo position: (0xe1, row * 8 + 4) = (225, row * 8 + 4)

## Game Variables

### Memory Addresses (Data Segment)
| Address | Size | Description |
|---------|------|-------------|
| 0x6d5 | byte | Action code (keyboard input) |
| 0x6d7 | byte | Piece Y position (row) |
| 0x6d8 | byte | Piece X position (column) |
| 0x6d9 | byte | Piece color |
| 0x6da | byte | Next piece type |
| 0x6db | byte | Current piece type (0-5) |
| 0x6de | word | Score |
| 0x6e0 | byte | Level (1-9) |
| 0x6e3 | byte | Timer counter |
| 0x6ba | byte | Show next piece flag |
| 0x6bb | byte | Sound enabled flag |
| 0x6be | word | GraphDriver |
| 0x6c0 | word | GraphMode |
| 0x34a | array | Board data (26 * rows bytes) |

### Board Layout
- Internal width: 26 (0x1a)
- Board indexing: `(Y * 26 + X)`
- Board array at offset 0x34a from data segment

## Piece System

### Piece Types (6 total)
Piece types 0-5 where types are paired for similar collision behavior:
- Types 0 and 3: Diagonal pieces
- Types 1 and 4: Horizontal pieces
- Types 2 and 5: Horizontal variant pieces

### Rotation Logic (at 0x074bd-0x074ca)
```asm
MOV AL, [0x6db]    ; load current piece type
XOR AH, AH         ; clear high byte
INC AX             ; piece_type + 1
CDQ                ; sign extend for division
MOV CX, 6          ; divisor = 6
IDIV CX            ; AX / 6, remainder in DX
XCHG DX, AX        ; AL = remainder
MOV [0x6db], AL    ; save new piece type
```
**Result**: Rotation = `(piece_type + 1) % 6`, cycling 0→1→2→3→4→5→0

### Piece Cells (from collision code at 0x1a80-0x1c00)
Each piece type has 4 cells calculated relative to anchor (X, Y):

**Type 0/3** (diagonal):
- (X-2, Y-3), (X-1, Y-2), (X, Y-1), (X+1, Y)

**Type 1/4** (horizontal):
- (X-2, Y), (X-1, Y), (X, Y), (X+1, Y)

**Type 2/5** (horizontal variant):
- (X-1, Y), (X, Y), (X+1, Y), (X+2, Y)

## Keyboard Handling

### Key Handler (at 0x07c0-0x08a4)
Reads from port 0x60 (keyboard controller) and sets action code at [0x6d5].

### Scan Codes → Action Mapping
| Scan Code | Key | Action |
|-----------|-----|--------|
| 0x01 | Esc | 2 (restart) |
| 0x02, 0x4f | 1/End | 1 |
| 0x04, 0x51 | 3/PgDn | 3 |
| 0x05, 0x39, 0x4b | 4/Space/Left | 4 (drop) |
| 0x07, 0x4d | 6/Right | 6 (level up) |
| 0x08, 0x47 | 7/Home | 7 (move left) |
| 0x09, 0x48 | 8/Up | 8 (rotate) |
| 0x0a, 0x49 | 9/PgUp | 9 (move right) |
| 0x44 | F10 | Boss key |

### Action Codes
| Code | Action |
|------|--------|
| 1 | Toggle next piece preview |
| 2 | Restart game |
| 3 | Toggle sound |
| 4 | Hard drop |
| 6 | Increase level |
| 7 | Move left |
| 8 | Rotate (cycle piece type) |
| 9 | Move right |

## Collision Detection (0x1a80-0x1c00)

Checks if piece can move to new position by:
1. Loading piece type from [0x6db]
2. Checking piece type (0/3, 1/4, or 2/5)
3. For each cell offset, checking board[Y*26+X+offset] == 0

## Scoring System

### Strings
- "Score : 0" at 0x6fc7
- "+1000" bonus string nearby
- "Full Lines" at 0x6fb8
- "Top Twenty" at 0x700e

### Score Increment Patterns
Found at various locations:
- Base score per line: 100
- Bonus for multiple lines: +1000 (4 lines), +300 (3 lines), +100 (2 lines)
- Score multiplied by level

## Line Clearing

- Check horizontal rows for completion
- Full row = all cells non-zero
- Pattern at [0x34a + Y*26 + X] checked for each X in row
- CMP byte ptr [di + 0x34a], 0 in loops

## Game Loop

### Timer
- INT 1Ah used for timing
- Timer counter at [0x6e3]
- Pieces fall faster at higher levels

### Main Loop
1. Handle keyboard input → set action code
2. Process action (move/rotate/drop)
3. Check collisions
4. Lock piece if can't move
5. Clear completed lines
6. Spawn next piece
7. Update score/display
8. Repeat

## EGA Colors (0-15)
| Index | Color |
|-------|-------|
| 0 | Black |
| 1 | Blue |
| 2 | Green |
| 3 | Cyan |
| 4 | Red |
| 5 | Magenta |
| 6 | Brown |
| 7 | Light Gray |
| 8 | Dark Gray |
| 9 | Light Blue |
| 10 | Light Green |
| 11 | Light Cyan |
| 12 | Light Red |
| 13 | Light Magenta |
| 14 | Yellow |
| 15 | White |

## Screen Layout

### Coordinates (from analysis)
- Board starts at X = 0xe1 (225)
- Board area uses ~11 columns, ~21 rows
- Next piece preview on right side
- Score/level info on left side (X < 225)

### Key Positions
- "Play HEXIS !" title: top center
- Level selection: center screen
- Score display: left side
- Hot keys help: right side
