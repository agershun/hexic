{***************************************************************************}
{*                                                                         *}
{*                              H E X I S                                  *}
{*                                                                         *}
{*                    Hexagonal Tetris Game for DOS                        *}
{*                                                                         *}
{*         Reconstructed from HEXIS.EXE reverse engineering                *}
{*         Original: circa 1987-1988, Borland Turbo Pascal + BGI           *}
{*                                                                         *}
{***************************************************************************}

program Hexis;

uses
  Crt, Graph, Dos;

const
  { Board dimensions }
  BOARD_WIDTH = 26;      { Internal board width for indexing }
  BOARD_COLS = 11;       { Visible columns }
  BOARD_ROWS = 19;       { Visible rows }

  { Cell geometry (honeycomb pattern) }
  CELL_WIDTH = 19;       { Horizontal span }
  CELL_HALF_W = 10;      { Half width for offset }
  CELL_HEIGHT = 16;      { Full cell height }

  { Board position on screen }
  BOARD_X = 225;         { $E1 in hex }
  BOARD_Y = 15;

  { Number of piece types }
  NUM_PIECES = 6;

  { Action codes from keyboard }
  ACT_NONE = 0;
  ACT_TOGGLE_NEXT = 1;
  ACT_RESTART = 2;
  ACT_TOGGLE_SOUND = 3;
  ACT_DROP = 4;
  ACT_LEVEL_UP = 6;
  ACT_MOVE_LEFT = 7;
  ACT_ROTATE = 8;
  ACT_MOVE_RIGHT = 9;

  { Keyboard scan codes }
  KEY_ESC = 1;
  KEY_1 = 2;
  KEY_3 = 4;
  KEY_4 = 5;
  KEY_6 = 7;
  KEY_7 = 8;
  KEY_8 = 9;
  KEY_9 = 10;
  KEY_F10 = 68;
  KEY_HOME = $47;
  KEY_UP = $48;
  KEY_PGUP = $49;
  KEY_LEFT = $4B;
  KEY_END = $4F;
  KEY_PGDN = $51;
  KEY_SPACE = $39;

type
  TBoard = array[0..BOARD_ROWS-1, 0..BOARD_COLS-1] of Byte;

  { Piece cell offsets }
  TCellOffset = record
    dx, dy: ShortInt;
  end;

  TPieceShape = array[0..3] of TCellOffset;

  THighScore = record
    Name: string[12];
    Score: LongInt;
  end;

  THighScores = array[1..20] of THighScore;

var
  { Game board - 0 = empty, 1-15 = color }
  Board: TBoard;

  { Current piece state }
  PieceType: Byte;       { 0-5 }
  PieceX: Byte;          { Column position }
  PieceY: Byte;          { Row position }
  PieceColor: Byte;      { EGA color 1-15 }

  { Next piece }
  NextType: Byte;
  NextColor: Byte;

  { Game stats }
  Score: LongInt;
  Lines: Word;
  Level: Byte;

  { Settings }
  ShowNext: Boolean;
  SoundOn: Boolean;

  { Input action }
  Action: Byte;

  { Game state }
  GameOver: Boolean;
  BossMode: Boolean;

  { Timer }
  DropTimer: Word;
  DropInterval: Word;

  { High scores }
  HighScores: THighScores;
  Champion: THighScore;

  { Piece shapes - offsets from anchor point }
  PieceShapes: array[0..NUM_PIECES-1] of TPieceShape;

  { Original keyboard interrupt }
  OldInt9: Pointer;

{---------------------------------------------------------------------------}
{ Initialize piece shape data                                               }
{---------------------------------------------------------------------------}
procedure InitPieceShapes;
begin
  { Type 0: Diagonal up-right }
  PieceShapes[0][0].dx := -2; PieceShapes[0][0].dy := -2;
  PieceShapes[0][1].dx := -1; PieceShapes[0][1].dy := -1;
  PieceShapes[0][2].dx :=  0; PieceShapes[0][2].dy :=  0;
  PieceShapes[0][3].dx :=  1; PieceShapes[0][3].dy :=  1;

  { Type 1: Horizontal line }
  PieceShapes[1][0].dx := -2; PieceShapes[1][0].dy := 0;
  PieceShapes[1][1].dx := -1; PieceShapes[1][1].dy := 0;
  PieceShapes[1][2].dx :=  0; PieceShapes[1][2].dy := 0;
  PieceShapes[1][3].dx :=  1; PieceShapes[1][3].dy := 0;

  { Type 2: Horizontal shifted }
  PieceShapes[2][0].dx := -1; PieceShapes[2][0].dy := 0;
  PieceShapes[2][1].dx :=  0; PieceShapes[2][1].dy := 0;
  PieceShapes[2][2].dx :=  1; PieceShapes[2][2].dy := 0;
  PieceShapes[2][3].dx :=  2; PieceShapes[2][3].dy := 0;

  { Type 3: Diagonal down-right }
  PieceShapes[3][0].dx := -2; PieceShapes[3][0].dy :=  2;
  PieceShapes[3][1].dx := -1; PieceShapes[3][1].dy :=  1;
  PieceShapes[3][2].dx :=  0; PieceShapes[3][2].dy :=  0;
  PieceShapes[3][3].dx :=  1; PieceShapes[3][3].dy := -1;

  { Type 4: Vertical line }
  PieceShapes[4][0].dx := 0; PieceShapes[4][0].dy := -2;
  PieceShapes[4][1].dx := 0; PieceShapes[4][1].dy := -1;
  PieceShapes[4][2].dx := 0; PieceShapes[4][2].dy :=  0;
  PieceShapes[4][3].dx := 0; PieceShapes[4][3].dy :=  1;

  { Type 5: Vertical shifted }
  PieceShapes[5][0].dx := 0; PieceShapes[5][0].dy := -1;
  PieceShapes[5][1].dx := 0; PieceShapes[5][1].dy :=  0;
  PieceShapes[5][2].dx := 0; PieceShapes[5][2].dy :=  1;
  PieceShapes[5][3].dx := 0; PieceShapes[5][3].dy :=  2;
end;

{---------------------------------------------------------------------------}
{ Convert board cell to screen pixel coordinates                            }
{---------------------------------------------------------------------------}
procedure CellToPixel(Col, Row: Integer; var PixelX, PixelY: Integer);
begin
  PixelX := BOARD_X + Col * CELL_WIDTH;
  PixelY := BOARD_Y + Row * CELL_HEIGHT;

  { Offset odd rows by half cell width for honeycomb pattern }
  if Odd(Row) then
    Inc(PixelX, CELL_HALF_W);
end;

{---------------------------------------------------------------------------}
{ Draw a honeycomb cell using LineRel pattern                               }
{ Original BGI drawing sequence from disassembly                            }
{---------------------------------------------------------------------------}
procedure DrawHoneycombCell(X, Y: Integer; Color: Byte; Filled: Boolean);
var
  Points: array[1..6] of PointType;
begin
  { Calculate hexagon vertices }
  { Width: 19px, Height: 16px }
  Points[1].X := X;      Points[1].Y := Y + 8;   { left middle }
  Points[2].X := X + 5;  Points[2].Y := Y;       { top-left }
  Points[3].X := X + 14; Points[3].Y := Y;       { top-right }
  Points[4].X := X + 19; Points[4].Y := Y + 8;   { right middle }
  Points[5].X := X + 14; Points[5].Y := Y + 16;  { bottom-right }
  Points[6].X := X + 5;  Points[6].Y := Y + 16;  { bottom-left }

  if Filled then
  begin
    SetFillStyle(SolidFill, Color);
    FillPoly(6, Points);
    SetColor(Color - 1);  { Darker outline }
    DrawPoly(7, Points);  { 7 to close the polygon }
  end
  else
  begin
    SetColor(Color);
    DrawPoly(7, Points);
  end;
end;

{---------------------------------------------------------------------------}
{ Play a beep sound through PC speaker                                      }
{---------------------------------------------------------------------------}
procedure Beep(Freq, Duration: Word);
begin
  if SoundOn then
  begin
    Sound(Freq);
    Delay(Duration);
    NoSound;
  end;
end;

{---------------------------------------------------------------------------}
{ Check if piece position is valid                                          }
{---------------------------------------------------------------------------}
function IsValidPosition(PType: Byte; PX, PY: Integer): Boolean;
var
  i: Integer;
  CellX, CellY: Integer;
begin
  IsValidPosition := True;

  for i := 0 to 3 do
  begin
    CellX := PX + PieceShapes[PType][i].dx;
    CellY := PY + PieceShapes[PType][i].dy;

    { Check bounds }
    if (CellX < 0) or (CellX >= BOARD_COLS) then
    begin
      IsValidPosition := False;
      Exit;
    end;

    if (CellY < 0) or (CellY >= BOARD_ROWS) then
    begin
      IsValidPosition := False;
      Exit;
    end;

    { Check collision with locked cells }
    if Board[CellY, CellX] <> 0 then
    begin
      IsValidPosition := False;
      Exit;
    end;
  end;
end;

{---------------------------------------------------------------------------}
{ Draw the current piece                                                     }
{---------------------------------------------------------------------------}
procedure DrawPiece(Erase: Boolean);
var
  i: Integer;
  CellX, CellY: Integer;
  PixelX, PixelY: Integer;
  DrawColor: Byte;
begin
  if Erase then
    DrawColor := Black
  else
    DrawColor := PieceColor;

  for i := 0 to 3 do
  begin
    CellX := PieceX + PieceShapes[PieceType][i].dx;
    CellY := PieceY + PieceShapes[PieceType][i].dy;

    if (CellX >= 0) and (CellX < BOARD_COLS) and
       (CellY >= 0) and (CellY < BOARD_ROWS) then
    begin
      CellToPixel(CellX, CellY, PixelX, PixelY);
      if Erase then
        DrawHoneycombCell(PixelX, PixelY, DarkGray, False)
      else
        DrawHoneycombCell(PixelX, PixelY, DrawColor, True);
    end;
  end;
end;

{---------------------------------------------------------------------------}
{ Lock piece into board                                                      }
{---------------------------------------------------------------------------}
procedure LockPiece;
var
  i: Integer;
  CellX, CellY: Integer;
begin
  for i := 0 to 3 do
  begin
    CellX := PieceX + PieceShapes[PieceType][i].dx;
    CellY := PieceY + PieceShapes[PieceType][i].dy;

    if (CellX >= 0) and (CellX < BOARD_COLS) and
       (CellY >= 0) and (CellY < BOARD_ROWS) then
    begin
      Board[CellY, CellX] := PieceColor;
    end;
  end;

  Beep(440, 50);
end;

{---------------------------------------------------------------------------}
{ Clear completed lines                                                      }
{---------------------------------------------------------------------------}
procedure ClearLines;
var
  Row, Col, Y: Integer;
  FullRow: Boolean;
  Cleared: Integer;
  PixelX, PixelY: Integer;
begin
  Cleared := 0;

  Row := BOARD_ROWS - 1;
  while Row >= 0 do
  begin
    { Check if row is full }
    FullRow := True;
    for Col := 0 to BOARD_COLS - 1 do
    begin
      if Board[Row, Col] = 0 then
      begin
        FullRow := False;
        Break;
      end;
    end;

    if FullRow then
    begin
      Inc(Cleared);

      { Shift all rows down }
      for Y := Row downto 1 do
        Board[Y] := Board[Y - 1];

      { Clear top row }
      for Col := 0 to BOARD_COLS - 1 do
        Board[0, Col] := 0;

      { Don't decrement Row - check same position again }
    end
    else
      Dec(Row);
  end;

  if Cleared > 0 then
  begin
    Beep(880, 100);
    Inc(Lines, Cleared);

    { Scoring }
    Inc(Score, 100 * Level * Cleared);
    if Cleared >= 4 then
      Inc(Score, 1000)
    else if Cleared >= 3 then
      Inc(Score, 300)
    else if Cleared >= 2 then
      Inc(Score, 100);

    { Level up }
    if Lines div 10 + 1 > Level then
    begin
      if Level < 9 then
      begin
        Inc(Level);
        DropInterval := 1000 - (Level - 1) * 100;
        if DropInterval < 100 then
          DropInterval := 100;
        Beep(1200, 150);
      end;
    end;
  end;
end;

{---------------------------------------------------------------------------}
{ Spawn new piece                                                            }
{---------------------------------------------------------------------------}
procedure SpawnPiece;
begin
  PieceType := NextType;
  PieceColor := NextColor;
  PieceX := BOARD_COLS div 2 + 1;
  PieceY := 3;

  { Generate next piece }
  NextType := Random(NUM_PIECES);
  NextColor := Random(14) + 1;  { Colors 1-14 }

  { Check if spawn position is valid }
  if not IsValidPosition(PieceType, PieceX, PieceY) then
    GameOver := True;
end;

{---------------------------------------------------------------------------}
{ Move piece left                                                            }
{---------------------------------------------------------------------------}
procedure MoveLeft;
begin
  if IsValidPosition(PieceType, PieceX - 1, PieceY) then
  begin
    DrawPiece(True);
    Dec(PieceX);
    DrawPiece(False);
    Beep(660, 20);
  end;
end;

{---------------------------------------------------------------------------}
{ Move piece right                                                           }
{---------------------------------------------------------------------------}
procedure MoveRight;
begin
  if IsValidPosition(PieceType, PieceX + 1, PieceY) then
  begin
    DrawPiece(True);
    Inc(PieceX);
    DrawPiece(False);
    Beep(660, 20);
  end;
end;

{---------------------------------------------------------------------------}
{ Rotate piece - cycle through piece types 0->1->2->3->4->5->0              }
{---------------------------------------------------------------------------}
procedure RotatePiece;
var
  NewType: Byte;
begin
  NewType := (PieceType + 1) mod NUM_PIECES;

  if IsValidPosition(NewType, PieceX, PieceY) then
  begin
    DrawPiece(True);
    PieceType := NewType;
    DrawPiece(False);
    Beep(880, 20);
  end;
end;

{---------------------------------------------------------------------------}
{ Drop piece one row                                                         }
{---------------------------------------------------------------------------}
function DropOne: Boolean;
begin
  if IsValidPosition(PieceType, PieceX, PieceY + 1) then
  begin
    DrawPiece(True);
    Inc(PieceY);
    DrawPiece(False);
    DropOne := True;
  end
  else
  begin
    LockPiece;
    ClearLines;
    SpawnPiece;
    if not GameOver then
      DrawPiece(False);
    DropOne := False;
  end;
end;

{---------------------------------------------------------------------------}
{ Hard drop piece                                                            }
{---------------------------------------------------------------------------}
procedure HardDrop;
var
  Count: Integer;
begin
  DrawPiece(True);
  Count := 0;

  while IsValidPosition(PieceType, PieceX, PieceY + 1) do
  begin
    Inc(PieceY);
    Inc(Count);
  end;

  Inc(Score, Count);
  DrawPiece(False);

  LockPiece;
  ClearLines;
  SpawnPiece;
  if not GameOver then
    DrawPiece(False);

  Beep(220, 50);
end;

{---------------------------------------------------------------------------}
{ Draw the game board                                                        }
{---------------------------------------------------------------------------}
procedure DrawBoard;
var
  Row, Col: Integer;
  PixelX, PixelY: Integer;
  BoardW, BoardH: Integer;
begin
  { Board border }
  BoardW := BOARD_COLS * CELL_WIDTH + CELL_HALF_W + 10;
  BoardH := BOARD_ROWS * CELL_HEIGHT + 10;

  SetColor(DarkGray);
  Rectangle(BOARD_X - 5, BOARD_Y - 5,
            BOARD_X + BoardW, BOARD_Y + BoardH);

  { Draw all cells }
  for Row := 0 to BOARD_ROWS - 1 do
  begin
    for Col := 0 to BOARD_COLS - 1 do
    begin
      CellToPixel(Col, Row, PixelX, PixelY);

      if Board[Row, Col] <> 0 then
        DrawHoneycombCell(PixelX, PixelY, Board[Row, Col], True)
      else
        DrawHoneycombCell(PixelX, PixelY, DarkGray, False);
    end;
  end;
end;

{---------------------------------------------------------------------------}
{ Draw UI elements                                                           }
{---------------------------------------------------------------------------}
procedure DrawUI;
var
  S: string;
  NextX, NextY: Integer;
  i: Integer;
  PixelX, PixelY: Integer;
begin
  { Title }
  SetColor(LightCyan);
  SetTextStyle(DefaultFont, HorizDir, 2);
  OutTextXY(20, 15, 'Play HEXIS !');

  SetTextStyle(DefaultFont, HorizDir, 1);

  { Level }
  SetColor(White);
  Str(Level, S);
  OutTextXY(20, 60, 'Level : ' + S);

  { Lines }
  Str(Lines, S);
  OutTextXY(20, 80, 'Full Lines : ' + S);

  { Score }
  SetColor(Yellow);
  Str(Score, S);
  OutTextXY(20, 100, 'Score : ' + S);

  { Champion }
  SetColor(LightGreen);
  OutTextXY(20, 140, 'Champion :');
  SetColor(White);
  OutTextXY(20, 155, Champion.Name);
  SetColor(Yellow);
  Str(Champion.Score, S);
  OutTextXY(20, 170, S);

  { Next piece preview }
  if ShowNext then
  begin
    NextX := BOARD_X + BOARD_COLS * CELL_WIDTH + 60;
    NextY := 50;

    SetColor(White);
    OutTextXY(NextX, NextY, 'NEXT');

    { Draw next piece }
    for i := 0 to 3 do
    begin
      PixelX := NextX + 20 + (PieceShapes[NextType][i].dx + 2) * 12;
      PixelY := NextY + 30 + (PieceShapes[NextType][i].dy + 2) * 10;
      DrawHoneycombCell(PixelX, PixelY, NextColor, True);
    end;
  end;

  { Hot keys }
  NextX := BOARD_X + BOARD_COLS * CELL_WIDTH + 40;
  NextY := 160;

  SetColor(LightCyan);
  OutTextXY(NextX, NextY, 'Hot Keys');

  SetColor(LightGray);
  OutTextXY(NextX, NextY + 20, '7/Left  : Move Left');
  OutTextXY(NextX, NextY + 35, '8/Up    : Rotate');
  OutTextXY(NextX, NextY + 50, '9/Right : Move Right');
  OutTextXY(NextX, NextY + 65, '4/Space : Drop');
  OutTextXY(NextX, NextY + 80, '1       : Next On/Off');
  OutTextXY(NextX, NextY + 95, '6       : Increase Level');
  OutTextXY(NextX, NextY + 110, '3       : Sound On/Off');
  OutTextXY(NextX, NextY + 125, 'Esc     : Restart');
  OutTextXY(NextX, NextY + 140, 'F10     : Boss Key');
end;

{---------------------------------------------------------------------------}
{ Update score display                                                       }
{---------------------------------------------------------------------------}
procedure UpdateScore;
var
  S: string;
begin
  SetFillStyle(SolidFill, Black);
  Bar(20, 95, 150, 115);

  SetColor(Yellow);
  Str(Score, S);
  OutTextXY(20, 100, 'Score : ' + S);
end;

{---------------------------------------------------------------------------}
{ Keyboard interrupt handler                                                 }
{---------------------------------------------------------------------------}
procedure KeyboardHandler; interrupt;
var
  ScanCode: Byte;
begin
  ScanCode := Port[$60];

  { Acknowledge keyboard }
  asm
    push ax
    in al, $61
    or al, $80
    out $61, al
    and al, $7F
    out $61, al
    mov al, $20
    out $20, al
    pop ax
  end;

  { Only process key press, not release }
  if ScanCode < $80 then
  begin
    case ScanCode of
      KEY_F10: BossMode := True;
      KEY_ESC: Action := ACT_RESTART;
      KEY_1, KEY_END: Action := ACT_TOGGLE_NEXT;
      KEY_3, KEY_PGDN: Action := ACT_TOGGLE_SOUND;
      KEY_4, KEY_LEFT, KEY_SPACE: Action := ACT_DROP;
      KEY_6: Action := ACT_LEVEL_UP;
      KEY_7, KEY_HOME: Action := ACT_MOVE_LEFT;
      KEY_8, KEY_UP: Action := ACT_ROTATE;
      KEY_9, KEY_PGUP: Action := ACT_MOVE_RIGHT;
    end;
  end;
end;

{---------------------------------------------------------------------------}
{ Process action from keyboard                                               }
{---------------------------------------------------------------------------}
procedure ProcessAction;
begin
  case Action of
    ACT_TOGGLE_NEXT:
      ShowNext := not ShowNext;

    ACT_TOGGLE_SOUND:
      SoundOn := not SoundOn;

    ACT_DROP:
      HardDrop;

    ACT_LEVEL_UP:
      if Level < 9 then
      begin
        Inc(Level);
        DropInterval := 1000 - (Level - 1) * 100;
        if DropInterval < 100 then
          DropInterval := 100;
        Beep(1200, 100);
      end;

    ACT_MOVE_LEFT:
      MoveLeft;

    ACT_ROTATE:
      RotatePiece;

    ACT_MOVE_RIGHT:
      MoveRight;

    ACT_RESTART:
      GameOver := True;
  end;

  Action := ACT_NONE;
end;

{---------------------------------------------------------------------------}
{ Show boss key screen (fake DOS prompt)                                     }
{---------------------------------------------------------------------------}
procedure ShowBossScreen;
begin
  ClearDevice;
  SetColor(LightGray);
  OutTextXY(10, 10, 'C:\>');

  repeat
    { Wait for any key }
  until KeyPressed;

  ReadKey;
  BossMode := False;

  { Redraw game }
  ClearDevice;
  DrawBoard;
  DrawUI;
  DrawPiece(False);
end;

{---------------------------------------------------------------------------}
{ Show level selection menu                                                  }
{---------------------------------------------------------------------------}
function ShowMenu: Byte;
var
  Ch: Char;
  SelectedLevel: Byte;
  i: Integer;
  X, Y: Integer;
begin
  SelectedLevel := 1;

  repeat
    { Draw menu overlay }
    SetFillStyle(SolidFill, Black);
    Bar(170, 120, 470, 230);

    SetColor(LightCyan);
    SetTextStyle(DefaultFont, HorizDir, 1);
    OutTextXY(240, 130, 'Choose Level :');

    { Draw level numbers }
    for i := 1 to 9 do
    begin
      X := 220 + ((i - 1) mod 5) * 30;
      Y := 160 + ((i - 1) div 5) * 25;

      if i = SelectedLevel then
        SetColor(Yellow)
      else
        SetColor(White);

      OutTextXY(X, Y, Chr(Ord('0') + i));
    end;

    SetColor(LightGreen);
    OutTextXY(220, 200, 'Press ENTER to Start');
    SetColor(LightGray);
    OutTextXY(240, 218, 'T - Top Twenty');

    { Wait for key }
    Ch := ReadKey;

    case Ch of
      '1'..'9': SelectedLevel := Ord(Ch) - Ord('0');
      #13: Break;  { Enter }
      #27: Halt;   { Escape - exit }
    end;
  until False;

  ShowMenu := SelectedLevel;
end;

{---------------------------------------------------------------------------}
{ Show game over screen                                                      }
{---------------------------------------------------------------------------}
function ShowGameOver: Boolean;
var
  Ch: Char;
  S: string;
begin
  SetFillStyle(SolidFill, Black);
  Bar(170, 130, 470, 250);

  SetColor(LightRed);
  SetTextStyle(DefaultFont, HorizDir, 2);
  OutTextXY(250, 145, 'GAME OVER');

  SetTextStyle(DefaultFont, HorizDir, 1);
  SetColor(Yellow);
  Str(Score, S);
  OutTextXY(270, 180, 'Score: ' + S);

  if Score > Champion.Score then
  begin
    SetColor(LightGreen);
    OutTextXY(220, 210, 'You Are New Champion !');
  end;

  SetColor(White);
  OutTextXY(230, 235, 'Once More ? (Y/N)');

  repeat
    Ch := UpCase(ReadKey);
  until Ch in ['Y', 'N'];

  ShowGameOver := (Ch = 'Y');
end;

{---------------------------------------------------------------------------}
{ Initialize game                                                            }
{---------------------------------------------------------------------------}
procedure InitGame;
var
  Row, Col: Integer;
begin
  { Clear board }
  for Row := 0 to BOARD_ROWS - 1 do
    for Col := 0 to BOARD_COLS - 1 do
      Board[Row, Col] := 0;

  { Reset stats }
  Score := 0;
  Lines := 0;

  { Reset state }
  GameOver := False;
  BossMode := False;
  Action := ACT_NONE;

  { Timer }
  DropTimer := 0;
  DropInterval := 1000 - (Level - 1) * 100;
  if DropInterval < 100 then
    DropInterval := 100;

  { Generate first pieces }
  NextType := Random(NUM_PIECES);
  NextColor := Random(14) + 1;
  SpawnPiece;
end;

{---------------------------------------------------------------------------}
{ Initialize graphics                                                        }
{---------------------------------------------------------------------------}
procedure InitGraphics;
var
  Gd, Gm: Integer;
  ErrCode: Integer;
begin
  Gd := Detect;
  InitGraph(Gd, Gm, '');

  ErrCode := GraphResult;
  if ErrCode <> grOk then
  begin
    WriteLn('Graphics error: ', GraphErrorMsg(ErrCode));
    Halt(1);
  end;
end;

{---------------------------------------------------------------------------}
{ Load high scores                                                           }
{---------------------------------------------------------------------------}
procedure LoadHighScores;
var
  F: file of THighScore;
  i: Integer;
begin
  { Initialize with defaults }
  for i := 1 to 20 do
  begin
    HighScores[i].Name := 'Pretender';
    HighScores[i].Score := 1000 - (i - 1) * 50;
  end;

  Champion := HighScores[1];

  { Try to load from file }
  {$I-}
  Assign(F, 'HEXIS.SCO');
  Reset(F);
  if IOResult = 0 then
  begin
    i := 1;
    while (not Eof(F)) and (i <= 20) do
    begin
      Read(F, HighScores[i]);
      Inc(i);
    end;
    Close(F);
    Champion := HighScores[1];
  end;
  {$I+}
end;

{---------------------------------------------------------------------------}
{ Save high scores                                                           }
{---------------------------------------------------------------------------}
procedure SaveHighScores;
var
  F: file of THighScore;
  i: Integer;
begin
  {$I-}
  Assign(F, 'HEXIS.SCO');
  Rewrite(F);
  if IOResult = 0 then
  begin
    for i := 1 to 20 do
      Write(F, HighScores[i]);
    Close(F);
  end;
  {$I+}
end;

{---------------------------------------------------------------------------}
{ Main game loop                                                             }
{---------------------------------------------------------------------------}
procedure GameLoop;
var
  LastTick: LongInt;
  CurrentTick: LongInt;
  Hour, Min, Sec, Sec100: Word;
begin
  { Get initial time }
  GetTime(Hour, Min, Sec, Sec100);
  LastTick := LongInt(Sec) * 100 + Sec100;

  while not GameOver do
  begin
    { Handle boss key }
    if BossMode then
      ShowBossScreen;

    { Process action }
    if Action <> ACT_NONE then
      ProcessAction;

    { Timer-based drop }
    GetTime(Hour, Min, Sec, Sec100);
    CurrentTick := LongInt(Sec) * 100 + Sec100;

    { Handle wrap-around at minute boundary }
    if CurrentTick < LastTick then
      Inc(CurrentTick, 6000);  { 60 seconds * 100 }

    Inc(DropTimer, CurrentTick - LastTick);
    LastTick := CurrentTick mod 6000;

    if DropTimer >= DropInterval div 10 then
    begin
      DropTimer := 0;
      DropOne;
      UpdateScore;
    end;

    { Small delay to reduce CPU usage }
    Delay(10);
  end;
end;

{---------------------------------------------------------------------------}
{ Main program                                                               }
{---------------------------------------------------------------------------}
begin
  { Initialize }
  Randomize;
  InitPieceShapes;
  LoadHighScores;
  InitGraphics;

  { Install keyboard handler }
  GetIntVec($09, OldInt9);
  SetIntVec($09, @KeyboardHandler);

  { Default settings }
  ShowNext := True;
  SoundOn := True;
  Level := 1;

  try
    repeat
      { Show menu and get level }
      ClearDevice;
      DrawBoard;
      DrawUI;
      Level := ShowMenu;

      { Start game }
      InitGame;
      ClearDevice;
      DrawBoard;
      DrawUI;
      DrawPiece(False);

      { Run game }
      GameLoop;

      { Update high scores if needed }
      if Score > HighScores[20].Score then
      begin
        { Insert new score }
        HighScores[20].Name := 'Player';
        HighScores[20].Score := Score;
        { Sort would go here }
        SaveHighScores;
      end;

    until not ShowGameOver;

  finally
    { Restore keyboard handler }
    SetIntVec($09, OldInt9);

    { Close graphics }
    CloseGraph;
  end;

  WriteLn('Thanks for playing HEXIS!');
end.
