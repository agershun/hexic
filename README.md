# HEXIS - Hexagonal Tetris

A recreation of the classic DOS game HEXIS (circa 1987-1988).

## Play Online

**[Play HEXIS in your browser!](https://agershun.github.io/hexic/)**

The online version runs the original DOS executable via js-dos emulator.

## About

HEXIS is a Tetris-like puzzle game with hexagonal cells instead of squares. The original game was written in Borland Pascal with BGI graphics for DOS.

This project includes:
- **Original DOS game** running in browser via js-dos
- **Python recreation** using pygame
- **Reverse engineering documentation**

## Controls

| Key | Action |
|-----|--------|
| 7 / Left / Numpad 7 | Move Left |
| 9 / Right / Numpad 9 | Move Right |
| 8 / Up / Numpad 8 | Rotate |
| 4 / Space / Numpad 4 | Drop |
| 1 / Numpad 1 | Toggle Next Preview |
| 3 / Numpad 3 | Toggle Sound |
| 6 / Numpad 6 | Increase Level |
| Esc | Restart |
| F10 | Boss Key |

## Running Locally

### Browser Version (Original DOS)
```bash
python3 -m http.server 8080
# Open http://localhost:8080
```

### Python Version
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pygame
python src/hexis.py
```

## Project Structure

```
hexic/
├── index.html              # Web page with js-dos emulator
├── data/
│   ├── HEXIS.EXE          # Original DOS executable
│   └── hexis.jsdos        # js-dos bundle
├── src/
│   ├── hexis.py           # Python recreation
│   └── HEXIS.PAS          # Reconstructed Pascal source
└── docs/
    └── HEXIS_REVERSE_ENGINEERING.md
```

## Technical Details

- **Original**: Borland Pascal, BGI graphics, EGA 640x350
- **Python version**: pygame, 2x scaled display
- **Web version**: js-dos (DOSBox in browser)

## License

This is a fan recreation for educational purposes.
