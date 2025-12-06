#!/usr/bin/env python3
"""
HEXIS - Hexagonal Tetris Clone
Recreated from the original DOS game (circa 1987-1988)
Original: Borland Pascal with BGI graphics (EGA 640x350)

Based on deep reverse engineering of HEXIS.EXE:
- Graphics: Honeycomb pattern drawn with LineRel zigzag lines
- 6 piece types (0-5), rotation cycles through all: 0→1→2→3→4→5→0
- Board uses Y * 26 + X indexing (internal width = 26)
- Pieces fall DOWN (Y increases)

Original LineRel patterns for cell edges:
  Row type 1: LineRel(10, 4), LineRel(19, -8), LineRel(9, 4)
  Row type 2: LineRel(10, -4), LineRel(19, 8), LineRel(9, -4)

Controls:
  7 / Left Arrow   : Move Left
  8 / Up Arrow     : Rotate (cycle piece type 0→1→2→3→4→5→0)
  9 / Right Arrow  : Move Right
  4 / Space / Down : Drop
  1                : Toggle Next Preview
  3                : Toggle Sound
  6                : Increase Level
  Esc              : Restart
  F10              : Boss Key
"""

import pygame
import random
import math
import json
import os

# Initialize pygame
pygame.init()
pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)

# ============================================================================
# EGA/VGA Color Palette (as used by BGI in original)
# ============================================================================
BLACK = (0, 0, 0)
BLUE = (0, 0, 170)
GREEN = (0, 170, 0)
CYAN = (0, 170, 170)
RED = (170, 0, 0)
MAGENTA = (170, 0, 170)
BROWN = (170, 85, 0)
LIGHT_GRAY = (170, 170, 170)
DARK_GRAY = (85, 85, 85)
LIGHT_BLUE = (85, 85, 255)
LIGHT_GREEN = (85, 255, 85)
LIGHT_CYAN = (85, 255, 255)
LIGHT_RED = (255, 85, 85)
LIGHT_MAGENTA = (255, 85, 255)
YELLOW = (255, 255, 85)
WHITE = (255, 255, 255)

# Piece colors (from original)
PIECE_COLORS = [
    LIGHT_RED,
    LIGHT_GREEN,
    LIGHT_CYAN,
    YELLOW,
    LIGHT_MAGENTA,
    LIGHT_BLUE,
]

# ============================================================================
# Display scaling (2x for modern screens)
# ============================================================================
SCALE = 2

# ============================================================================
# Screen dimensions (EGA 640x350 - the original DOS mode)
# ============================================================================
INTERNAL_WIDTH = 640
INTERNAL_HEIGHT = 350
SCREEN_WIDTH = INTERNAL_WIDTH * SCALE
SCREEN_HEIGHT = INTERNAL_HEIGHT * SCALE

# ============================================================================
# Honeycomb cell geometry
#
# Original DOS game used very flat hexagons (19px wide, 8px between rows).
# For better visuals, we use proper regular hexagons.
#
# Regular hexagon geometry (flat-top orientation):
#   - Width = 2 * size (point to point horizontally)
#   - Height = sqrt(3) * size ≈ 1.732 * size
#   - For width=20: height ≈ 17
#
# We use a slightly wider hexagon for better fit:
# ============================================================================
CELL_SIZE = 10       # Base size unit
CELL_WIDTH = 18      # Flat top/bottom width
CELL_HEIGHT = 16     # Full height of hexagon
ROW_SPACING = 12     # Vertical spacing (3/4 of height for honeycomb overlap)
HEX_SIDE_W = 5       # Width of left angled side
HEX_SIDE_W2 = 5      # Width of right angled side
HEX_SIDE_H = 8       # Half height (for middle point)

# ============================================================================
# Board dimensions
# From disassembly: internal width = 26 (0x1a), used in Y * 26 + X
# ============================================================================
BOARD_COLS = 11      # Visible columns
BOARD_ROWS = 21      # Visible rows (for EGA 350 height with 8px per row)
BOARD_INTERNAL_WIDTH = 26

# Board position on screen (from 0x6317: MoveTo(0xe1, ...) = MoveTo(225, ...))
BOARD_X = 225
BOARD_Y = 8

# ============================================================================
# Game states
# ============================================================================
STATE_MENU = 0
STATE_PLAYING = 1
STATE_GAME_OVER = 2
STATE_HIGH_SCORES = 3
STATE_BOSS_KEY = 4
STATE_ENTER_NAME = 5

# ============================================================================
# Piece definitions from disassembly
#
# From collision code at 0x1a80-0x1c00:
# Piece types check: (piece_type == 0 || piece_type == 3), etc.
#
# Type 0/3 (diagonal): cells at (X-2, Y-3), (X-1, Y-2), (X, Y-1), (X+1, Y)
# Type 1/4 (horizontal): checks cell at (X, Y-3)
# Type 2/5 (another): checks cells at (X+2, Y-1), (X-1, Y-1), (X, Y-1), (X+1, Y-1)
#
# Rotation cycles through ALL 6 types: 0→1→2→3→4→5→0
# ============================================================================

# Piece shapes based on collision detection analysis
# Each piece is 4 cells relative to anchor (X, Y)
PIECE_SHAPES = {
    # Type 0: Diagonal going up-left to down-right
    0: [(0, 0), (-1, -1), (-2, -2), (1, 1)],

    # Type 1: Vertical line
    1: [(0, 0), (0, -1), (0, -2), (0, -3)],

    # Type 2: Horizontal line shifted
    2: [(0, 0), (-1, 0), (1, 0), (2, 0)],

    # Type 3: Diagonal going up-right to down-left
    3: [(0, 0), (1, -1), (2, -2), (-1, 1)],

    # Type 4: Vertical line (variant)
    4: [(0, 0), (0, -1), (0, -2), (0, 1)],

    # Type 5: Horizontal line
    5: [(0, 0), (-1, 0), (1, 0), (-2, 0)],
}

NUM_PIECE_TYPES = 6


def get_piece_cells(piece_type, anchor_x, anchor_y):
    """Get absolute board positions for piece cells"""
    offsets = PIECE_SHAPES.get(piece_type % NUM_PIECE_TYPES, PIECE_SHAPES[0])
    return [(anchor_x + dx, anchor_y + dy) for dx, dy in offsets]


class HexisGame:
    def __init__(self):
        # Create internal surface at original resolution
        self.internal_surface = pygame.Surface((INTERNAL_WIDTH, INTERNAL_HEIGHT))
        # Create scaled display
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Play HEXIS !")
        self.clock = pygame.time.Clock()

        # Font - simulating DOS look (scaled for internal resolution)
        self.font = pygame.font.Font(None, 16)
        self.font_large = pygame.font.Font(None, 24)
        self.font_small = pygame.font.Font(None, 12)

        # Game state
        self.state = STATE_MENU
        self.reset_game()

        # High scores
        self.high_scores = self.load_high_scores()
        self.champion = self.high_scores[0] if self.high_scores else ("Pretender", 1000)

        # Settings
        self.show_next = True    # [0x6ba] - show next piece preview
        self.sound_on = True     # [0x6bb] - sound enabled

        # Input for high score
        self.input_name = ""

        # Sounds
        self.init_sounds()

    def init_sounds(self):
        """Create PC speaker-like beep sounds"""
        try:
            sample_rate = 22050

            # Drop sound
            duration = 0.05
            samples = int(sample_rate * duration)
            freq = 440
            buffer = bytes([int(127 + 100 * math.sin(2 * math.pi * freq * t / sample_rate))
                          for t in range(samples)])
            self.sound_drop = pygame.mixer.Sound(buffer=buffer)

            # Move sound
            duration = 0.02
            samples = int(sample_rate * duration)
            freq = 880
            buffer = bytes([int(127 + 80 * math.sin(2 * math.pi * freq * t / sample_rate))
                          for t in range(samples)])
            self.sound_move = pygame.mixer.Sound(buffer=buffer)

            # Line clear
            duration = 0.15
            samples = int(sample_rate * duration)
            buffer = bytes([int(127 + 100 * math.sin(2 * math.pi * (600 + 400 * t / samples) * t / sample_rate))
                          for t in range(samples)])
            self.sound_line = pygame.mixer.Sound(buffer=buffer)

            # Level up
            duration = 0.2
            samples = int(sample_rate * duration)
            buffer = bytes([int(127 + 100 * math.sin(2 * math.pi * (400 + 600 * t / samples) * t / sample_rate))
                          for t in range(samples)])
            self.sound_levelup = pygame.mixer.Sound(buffer=buffer)

            # Game over
            duration = 0.4
            samples = int(sample_rate * duration)
            buffer = bytes([int(127 + 100 * math.sin(2 * math.pi * (500 - 300 * t / samples) * t / sample_rate))
                          for t in range(samples)])
            self.sound_gameover = pygame.mixer.Sound(buffer=buffer)

        except Exception:
            self.sound_drop = None
            self.sound_move = None
            self.sound_line = None
            self.sound_levelup = None
            self.sound_gameover = None

    def play_sound(self, sound):
        if self.sound_on and sound:
            try:
                sound.play()
            except Exception:
                pass

    def load_high_scores(self):
        scores_file = os.path.join(os.path.dirname(__file__), "..", "data", "hexis.scores")
        try:
            with open(scores_file, 'r') as f:
                data = json.load(f)
                return [(s['name'], s['score']) for s in data[:20]]
        except Exception:
            return [("Pretender", 1000)]

    def save_high_scores(self):
        scores_file = os.path.join(os.path.dirname(__file__), "..", "data", "hexis.scores")
        try:
            os.makedirs(os.path.dirname(scores_file), exist_ok=True)
            data = [{'name': name, 'score': score} for name, score in self.high_scores[:20]]
            with open(scores_file, 'w') as f:
                json.dump(data, f)
        except Exception:
            pass

    def reset_game(self):
        """Reset game state"""
        # Board: stores color or None for each cell
        self.board = [[None for _ in range(BOARD_COLS)] for _ in range(BOARD_ROWS)]

        # Current piece state (matching original variables)
        self.piece_type = None      # [0x6db] - piece type 0-5
        self.piece_x = 0            # [0x6d8] - X position (column)
        self.piece_y = 0            # [0x6d7] - Y position (row)
        self.piece_color = None     # [0x6d9] - piece color

        # Next piece
        self.next_type = None       # [0x6da] - next piece type
        self.next_color = None

        # Stats
        self.score = 0              # [0x6de] - score
        self.lines = 0
        self.level = 1              # [0x6e0] - current level (1-9)

        # Timing
        self.drop_timer = 0
        self.base_interval = 800
        self.drop_interval = self.base_interval

    def get_piece_cells_at(self, ptype, px, py):
        """Get absolute board positions for piece cells"""
        return get_piece_cells(ptype, px, py)

    def is_valid_position(self, ptype, px, py):
        """Check if piece can be placed at position"""
        cells = self.get_piece_cells_at(ptype, px, py)
        for x, y in cells:
            # Check horizontal bounds
            if x < 0 or x >= BOARD_COLS:
                return False
            # Check bottom bound (top can be negative for spawning pieces)
            if y >= BOARD_ROWS:
                return False
            # Check collision with locked cells (only for cells on visible board)
            if y >= 0 and self.board[y][x] is not None:
                return False
        return True

    def spawn_piece(self):
        """Spawn a new piece at the top"""
        if self.next_type is None:
            self.next_type = random.randint(0, NUM_PIECE_TYPES - 1)
            self.next_color = PIECE_COLORS[random.randint(0, len(PIECE_COLORS) - 1)]

        self.piece_type = self.next_type
        self.piece_color = self.next_color
        # Spawn at top center
        self.piece_x = BOARD_COLS // 2
        self.piece_y = 3  # Start a bit down to allow for cells above

        self.next_type = random.randint(0, NUM_PIECE_TYPES - 1)
        self.next_color = PIECE_COLORS[random.randint(0, len(PIECE_COLORS) - 1)]

        # Check if spawn position is valid
        if not self.is_valid_position(self.piece_type, self.piece_x, self.piece_y):
            self.game_over()

    def move_left(self):
        """Move piece left"""
        if self.piece_type is None:
            return
        if self.is_valid_position(self.piece_type, self.piece_x - 1, self.piece_y):
            self.piece_x -= 1
            self.play_sound(self.sound_move)

    def move_right(self):
        """Move piece right"""
        if self.piece_type is None:
            return
        if self.is_valid_position(self.piece_type, self.piece_x + 1, self.piece_y):
            self.piece_x += 1
            self.play_sound(self.sound_move)

    def rotate(self):
        """Rotate piece by cycling through piece types"""
        if self.piece_type is None:
            return
        # Rotation = cycling piece type: 0->1->2->3->4->5->0
        new_type = (self.piece_type + 1) % NUM_PIECE_TYPES
        if self.is_valid_position(new_type, self.piece_x, self.piece_y):
            self.piece_type = new_type
            self.play_sound(self.sound_move)

    def drop_one(self):
        """Move piece down by one row (pieces fall down, Y increases)"""
        if self.piece_type is None:
            return False
        if self.is_valid_position(self.piece_type, self.piece_x, self.piece_y + 1):
            self.piece_y += 1
            return True
        else:
            self.lock_piece()
            return False

    def hard_drop(self):
        """Drop piece all the way down"""
        if self.piece_type is None:
            return
        count = 0
        while self.is_valid_position(self.piece_type, self.piece_x, self.piece_y + 1):
            self.piece_y += 1
            count += 1
        self.score += count
        self.lock_piece()
        self.play_sound(self.sound_drop)

    def lock_piece(self):
        """Lock current piece into board"""
        if self.piece_type is None:
            return

        cells = self.get_piece_cells_at(self.piece_type, self.piece_x, self.piece_y)
        for x, y in cells:
            if 0 <= y < BOARD_ROWS and 0 <= x < BOARD_COLS:
                self.board[y][x] = self.piece_color

        self.play_sound(self.sound_drop)
        self.clear_lines()
        self.spawn_piece()

    def clear_lines(self):
        """Check and clear complete horizontal rows"""
        cleared = 0

        # Check rows from bottom to top
        y = BOARD_ROWS - 1
        while y >= 0:
            # Check if entire row is filled
            if all(self.board[y][x] is not None for x in range(BOARD_COLS)):
                # Remove this row and shift everything down
                del self.board[y]
                self.board.insert(0, [None for _ in range(BOARD_COLS)])
                cleared += 1
            else:
                y -= 1

        if cleared > 0:
            self.play_sound(self.sound_line)
            self.lines += cleared

            # Scoring (from analysis: +1000 bonus for multiple lines)
            points = 100 * self.level * cleared
            if cleared >= 4:
                points += 1000
            elif cleared >= 3:
                points += 300
            elif cleared >= 2:
                points += 100
            self.score += points

            # Level up
            new_level = min(9, 1 + self.lines // 10)
            if new_level > self.level:
                self.level = new_level
                self.drop_interval = max(100, self.base_interval - (self.level - 1) * 80)
                self.play_sound(self.sound_levelup)

    def game_over(self):
        self.state = STATE_GAME_OVER
        self.play_sound(self.sound_gameover)
        self.piece_type = None

        if self.score > 0 and (len(self.high_scores) < 20 or self.score > self.high_scores[-1][1]):
            self.state = STATE_ENTER_NAME
            self.input_name = ""

    def add_high_score(self, name):
        self.high_scores.append((name, self.score))
        self.high_scores.sort(key=lambda x: x[1], reverse=True)
        self.high_scores = self.high_scores[:20]
        self.champion = self.high_scores[0]
        self.save_high_scores()
        self.state = STATE_GAME_OVER

    def start_game(self):
        self.reset_game()
        self.drop_interval = max(100, self.base_interval - (self.level - 1) * 80)
        self.state = STATE_PLAYING
        self.spawn_piece()

    # ========================================================================
    # Drawing - Honeycomb pattern matching original BGI graphics
    # ========================================================================

    def cell_to_pixel(self, col, row):
        """Convert grid cell (col, row) to screen pixel position.

        From disassembly at 0x6317-0x6327:
          MoveTo(0xe1, row * 8 + 4) = MoveTo(225, row * 8 + 4)

        The grid uses 8 pixels between row centers (ROW_SPACING).
        Horizontally, each cell is CELL_WIDTH (19px) wide.
        """
        # Horizontal: each column is CELL_WIDTH apart
        # Odd rows shift right by half a cell for honeycomb pattern
        x = BOARD_X + col * CELL_WIDTH
        if row % 2 == 1:
            x += CELL_WIDTH // 2

        # Vertical: rows are ROW_SPACING apart (8px from original)
        y = BOARD_Y + row * ROW_SPACING

        return x, y

    def draw_honeycomb_cell(self, x, y, color, row=0, filled=True):
        """
        Draw a honeycomb cell.

        Based on original BGI LineRel commands:
          Row type 1: LineRel(10, 4), LineRel(19, -8), LineRel(9, 4)  -> zigzag up
          Row type 2: LineRel(10, -4), LineRel(19, 8), LineRel(9, -4) -> zigzag down

        This creates a hexagonal cell with:
        - Flat top and bottom (CELL_WIDTH = 19px wide)
        - Angled sides (HEX_SIDE_W = 10px, HEX_SIDE_W2 = 9px diagonal)
        - Full height (CELL_HEIGHT = 16px)
        - Half height for sides (HEX_SIDE_H = 8px)
        """
        # Hexagon with flat top and bottom
        # The cell is centered at (x, y) with the middle at y + HEX_SIDE_H
        half_h = HEX_SIDE_H  # 8px - half the cell height

        # 6-point hexagon: flat top and bottom
        points = [
            (x, y + half_h),                                    # left middle
            (x + HEX_SIDE_W, y),                                # top-left
            (x + HEX_SIDE_W + CELL_WIDTH, y),                   # top-right
            (x + HEX_SIDE_W + CELL_WIDTH + HEX_SIDE_W2, y + half_h),  # right middle
            (x + HEX_SIDE_W + CELL_WIDTH, y + CELL_HEIGHT),     # bottom-right
            (x + HEX_SIDE_W, y + CELL_HEIGHT),                  # bottom-left
        ]

        if filled:
            pygame.draw.polygon(self.internal_surface, color, points)
            # Darker outline for 3D effect
            darker = tuple(max(0, c - 60) for c in color)
            pygame.draw.polygon(self.internal_surface, darker, points, 1)
        else:
            # Just outline for empty cells
            pygame.draw.polygon(self.internal_surface, color, points, 1)

    def draw_board(self):
        """Draw the game board with honeycomb cells"""
        # Calculate board dimensions
        board_w = BOARD_COLS * CELL_WIDTH + CELL_WIDTH // 2 + HEX_SIDE_W * 2 + 10
        board_h = BOARD_ROWS * ROW_SPACING + CELL_HEIGHT + 5

        # Board border
        pygame.draw.rect(self.internal_surface, DARK_GRAY,
                        (BOARD_X - 5, BOARD_Y - 2, board_w, board_h), 1)

        # Draw all cells - empty ones as outlines
        for row in range(BOARD_ROWS):
            for col in range(BOARD_COLS):
                px, py = self.cell_to_pixel(col, row)
                cell = self.board[row][col]

                if cell is not None:
                    self.draw_honeycomb_cell(px, py, cell, row=row, filled=True)
                else:
                    self.draw_honeycomb_cell(px, py, DARK_GRAY, row=row, filled=False)

        # Draw current falling piece
        if self.piece_type is not None and self.state == STATE_PLAYING:
            cells = self.get_piece_cells_at(self.piece_type, self.piece_x, self.piece_y)
            for cx, cy in cells:
                if 0 <= cy < BOARD_ROWS and 0 <= cx < BOARD_COLS:
                    px, py = self.cell_to_pixel(cx, cy)
                    self.draw_honeycomb_cell(px, py, self.piece_color, row=cy, filled=True)

    def draw_ui(self):
        """Draw UI elements"""
        # Title
        title = self.font_large.render("Play HEXIS !", True, LIGHT_CYAN)
        self.internal_surface.blit(title, (20, 15))

        # Level
        self.internal_surface.blit(self.font.render(f"Level : {self.level}", True, WHITE), (20, 55))

        # Lines
        self.internal_surface.blit(self.font.render(f"Full Lines : {self.lines}", True, WHITE), (20, 75))

        # Score
        self.internal_surface.blit(self.font.render(f"Score : {self.score}", True, YELLOW), (20, 95))

        # Champion
        self.internal_surface.blit(self.font.render("Champion :", True, LIGHT_GREEN), (20, 130))
        self.internal_surface.blit(self.font.render(f"{self.champion[0]}", True, WHITE), (20, 148))
        self.internal_surface.blit(self.font.render(f"{self.champion[1]}", True, YELLOW), (20, 166))

        # Next piece preview
        if self.show_next and self.next_type is not None and self.next_color is not None:
            next_x = 20
            next_y = 200
            self.internal_surface.blit(self.font.render("NEXT", True, WHITE), (next_x, next_y))

            # Draw next piece preview
            offsets = PIECE_SHAPES.get(self.next_type % NUM_PIECE_TYPES, PIECE_SHAPES[0])
            for dx, dy in offsets:
                px = next_x + 40 + dx * 12
                py = next_y + 30 + dy * 8
                # Draw small hexagon
                points = [
                    (px, py + 2),
                    (px + 3, py),
                    (px + 9, py),
                    (px + 12, py + 2),
                    (px + 9, py + 6),
                    (px + 3, py + 6),
                ]
                pygame.draw.polygon(self.internal_surface, self.next_color, points)

        # Hot Keys - positioned on the right
        hotkeys_x = 530
        hotkeys_y = 20

        self.internal_surface.blit(self.font.render("Hot Keys", True, LIGHT_CYAN), (hotkeys_x, hotkeys_y))

        keys = [
            "7/Left  : Move Left",
            "8/Up    : Rotate",
            "9/Right : Move Right",
            "4/Space : Drop",
            "1       : Next On/Off",
            "6       : Increase Level",
            "3       : Sound On/Off",
            "Esc     : Restart",
            "F10     : Boss Key",
        ]
        for i, text in enumerate(keys):
            self.internal_surface.blit(self.font_small.render(text, True, LIGHT_GRAY),
                           (hotkeys_x, hotkeys_y + 20 + i * 12))

    def draw_menu(self):
        overlay = pygame.Surface((200, 130), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        self.internal_surface.blit(overlay, (INTERNAL_WIDTH // 2 - 100, 100))

        self.internal_surface.blit(self.font_large.render("Choose Level :", True, LIGHT_CYAN),
                        (INTERNAL_WIDTH // 2 - 60, 110))

        for i in range(1, 10):
            color = YELLOW if i == self.level else WHITE
            x = INTERNAL_WIDTH // 2 - 50 + ((i - 1) % 5) * 22
            y = 140 + ((i - 1) // 5) * 22
            self.internal_surface.blit(self.font.render(str(i), True, color), (x, y))

        self.internal_surface.blit(self.font.render("Press ENTER to Start", True, LIGHT_GREEN),
                        (INTERNAL_WIDTH // 2 - 65, 195))

    def draw_game_over(self):
        overlay = pygame.Surface((200, 120), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 220))
        self.internal_surface.blit(overlay, (INTERNAL_WIDTH // 2 - 100, 100))

        self.internal_surface.blit(self.font_large.render("GAME OVER", True, LIGHT_RED),
                        (INTERNAL_WIDTH // 2 - 50, 110))
        self.internal_surface.blit(self.font.render(f"Score: {self.score}", True, YELLOW),
                        (INTERNAL_WIDTH // 2 - 35, 140))

        if len(self.high_scores) < 20 or self.score > self.high_scores[-1][1]:
            self.internal_surface.blit(self.font.render("Top Twenty!", True, LIGHT_GREEN),
                           (INTERNAL_WIDTH // 2 - 35, 165))

        self.internal_surface.blit(self.font.render("Once More ? (Y/N)", True, WHITE),
                        (INTERNAL_WIDTH // 2 - 55, 190))

    def draw_enter_name(self):
        overlay = pygame.Surface((220, 120), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 230))
        self.internal_surface.blit(overlay, (INTERNAL_WIDTH // 2 - 110, 100))

        self.internal_surface.blit(self.font_large.render("New Champion!", True, LIGHT_GREEN),
                        (INTERNAL_WIDTH // 2 - 60, 110))
        self.internal_surface.blit(self.font.render("Enter Your Name:", True, WHITE),
                        (INTERNAL_WIDTH // 2 - 55, 145))
        self.internal_surface.blit(self.font.render(self.input_name + "_", True, YELLOW),
                        (INTERNAL_WIDTH // 2 - 40, 170))

    def draw_high_scores(self):
        self.internal_surface.fill(BLACK)
        self.internal_surface.blit(self.font_large.render("Top Twenty", True, LIGHT_CYAN),
                        (INTERNAL_WIDTH // 2 - 50, 15))

        for i, (name, score) in enumerate(self.high_scores[:20]):
            y = 45 + i * 14
            color = YELLOW if i == 0 else WHITE
            self.internal_surface.blit(self.font.render(f"{i+1:2}.", True, LIGHT_GRAY),
                           (INTERNAL_WIDTH // 2 - 80, y))
            self.internal_surface.blit(self.font.render(f"{name[:12]:12s}", True, color),
                           (INTERNAL_WIDTH // 2 - 55, y))
            self.internal_surface.blit(self.font.render(f"{score:8}", True, YELLOW),
                           (INTERNAL_WIDTH // 2 + 40, y))

        self.internal_surface.blit(self.font.render("Press any key...", True, LIGHT_GREEN),
                        (INTERNAL_WIDTH // 2 - 50, INTERNAL_HEIGHT - 25))

    def draw_boss_key(self):
        self.internal_surface.fill(BLACK)
        self.internal_surface.blit(self.font.render("C:\\>", True, LIGHT_GRAY), (10, 10))
        if pygame.time.get_ticks() % 1000 < 500:
            self.internal_surface.blit(self.font.render("_", True, LIGHT_GRAY), (40, 10))

    # ========================================================================
    # Event handling
    # ========================================================================

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                return self.handle_key(event)
        return True

    def handle_key(self, event):
        key = event.key

        if self.state == STATE_BOSS_KEY:
            self.state = STATE_PLAYING
            return True

        if key == pygame.K_F10 and self.state == STATE_PLAYING:
            self.state = STATE_BOSS_KEY
            return True

        if self.state == STATE_MENU:
            if key == pygame.K_RETURN:
                self.start_game()
            elif key == pygame.K_t:
                self.state = STATE_HIGH_SCORES
            elif pygame.K_1 <= key <= pygame.K_9:
                self.level = key - pygame.K_0
            elif pygame.K_KP1 <= key <= pygame.K_KP9:
                self.level = key - pygame.K_KP0

        elif self.state == STATE_PLAYING:
            if key in [pygame.K_7, pygame.K_KP7, pygame.K_LEFT]:
                self.move_left()
            elif key in [pygame.K_9, pygame.K_KP9, pygame.K_RIGHT]:
                self.move_right()
            elif key in [pygame.K_8, pygame.K_KP8, pygame.K_UP]:
                self.rotate()
            elif key in [pygame.K_4, pygame.K_KP4, pygame.K_SPACE, pygame.K_DOWN]:
                self.hard_drop()
            elif key in [pygame.K_1, pygame.K_KP1]:
                self.show_next = not self.show_next
            elif key in [pygame.K_3, pygame.K_KP3]:
                self.sound_on = not self.sound_on
            elif key in [pygame.K_6, pygame.K_KP6]:
                if self.level < 9:
                    self.level += 1
                    self.drop_interval = max(100, self.base_interval - (self.level - 1) * 80)
                    self.play_sound(self.sound_levelup)
            elif key == pygame.K_ESCAPE:
                self.state = STATE_MENU
                self.reset_game()

        elif self.state == STATE_GAME_OVER:
            if key in [pygame.K_y, pygame.K_RETURN]:
                self.state = STATE_MENU
            elif key == pygame.K_n:
                return False
            elif key == pygame.K_t:
                self.state = STATE_HIGH_SCORES

        elif self.state == STATE_ENTER_NAME:
            if key == pygame.K_RETURN and self.input_name:
                self.add_high_score(self.input_name)
            elif key == pygame.K_BACKSPACE:
                self.input_name = self.input_name[:-1]
            elif hasattr(event, 'unicode') and event.unicode:
                if event.unicode.isalnum() or event.unicode in ' ._-':
                    if len(self.input_name) < 12:
                        self.input_name += event.unicode

        elif self.state == STATE_HIGH_SCORES:
            self.state = STATE_MENU

        return True

    def update(self, dt):
        if self.state != STATE_PLAYING:
            return

        self.drop_timer += dt
        if self.drop_timer >= self.drop_interval:
            self.drop_timer = 0
            self.drop_one()

    def draw(self):
        # Draw to internal surface at original resolution
        self.internal_surface.fill(BLACK)

        if self.state == STATE_BOSS_KEY:
            self.draw_boss_key()
        elif self.state == STATE_HIGH_SCORES:
            self.draw_high_scores()
        else:
            self.draw_board()
            self.draw_ui()

            if self.state == STATE_MENU:
                self.draw_menu()
            elif self.state == STATE_GAME_OVER:
                self.draw_game_over()
            elif self.state == STATE_ENTER_NAME:
                self.draw_enter_name()

        # Scale up to display
        pygame.transform.scale(self.internal_surface, (SCREEN_WIDTH, SCREEN_HEIGHT), self.screen)
        pygame.display.flip()

    def run(self):
        running = True
        while running:
            dt = self.clock.tick(60)
            running = self.handle_events()
            self.update(dt)
            self.draw()
        pygame.quit()


def main():
    game = HexisGame()
    game.run()


if __name__ == "__main__":
    main()
