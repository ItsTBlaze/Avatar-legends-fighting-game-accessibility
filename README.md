# Avatar Legends: The Fighting Game – Accessibility

A screen reader helper for **Avatar Legends: The Fighting Game** on PC, made by a
blind player so that blind and low-vision players can find their way around the game.

It watches the screen while the game runs and speaks what is highlighted through
**NVDA** (or the Windows voice if NVDA is not running). It does not change the
game or its files in any way. It only looks at the screen.

This is a fan-made tool. It is not affiliated with or endorsed by the makers of
the game.

## What it reads

- **Menus:** the highlighted option, and the menu title when a menu opens.
- **Options and training settings:** each setting with its value, for example "Main Volume, 50".
- **Character select:** both fighters, the support character and the variation, for both
  players, including online. Fighters are named from the cursor's place on the grid.
- **Stage select:** the stage name.
- **Command list:** each move's name, tags, button input and description, for example
  "Blue Spirit Liberation, 4 Energy, Hard Knockdown. Input: quarter circle forward, A plus B plus C".
- **Online:** the lobby list, custom lobbies (settings, capacity, invite code, players, host,
  match slots), yes or no popups, the match-found popup, the pick timer and the results screen.
- **Tutorials:** the tutorial menu and the instruction text shown during a tutorial.

During fights it only reads tutorial instructions. Fight audio cues (distance to the
opponent, health and so on) are planned.

## Using it

Download the latest zip from the [Releases](../../releases) page when one is available,
unzip it, and open **Avatar Reader.exe**. Nothing needs installing.

### Hotkeys

| Keys | Action |
| --- | --- |
| Ctrl+Shift+R | Repeat the last thing said |
| Ctrl+Shift+S | Read all the text on the screen |
| Ctrl+Shift+P | Pause or resume automatic reading |
| Ctrl+Shift+Q | Quit |

### Game settings it needs

- Display mode: borderless or windowed (exclusive fullscreen can look black to the reader).
- Resolution: 1920 by 1080 works best; other 16:9 sizes should work.
- The game on your main monitor.
- Windows with English text recognition (built into English versions of Windows).

## Running from the source code

1. Install [Python](https://www.python.org/) 3.10 to 3.13, or let the setup install it.
2. Open **Start Avatar Reader.bat**. The first run sets up its parts, which takes a few minutes.
3. **Run self test.bat** checks the reader against your Steam screenshots of the game
   (take some with F12) and writes the results to `selftest.txt`.
4. **Make shareable copy.bat** builds the standalone `Avatar Reader.zip`.

### How it works

| File | Purpose |
| --- | --- |
| `avatar_reader.py` | Main program: screen capture, hotkeys, self test |
| `reader.py` | Decides what to say for each screen |
| `detector.py` | Finds highlights, screens and fixed regions |
| `ocr.py` | Text recognition with the OCR built into Windows |
| `inputs.py` | Reads arrow and button icons in move inputs |
| `textclean.py` | Tidies recognised text for speech |
| `speech.py` | Speech through NVDA, with the Windows voice as a fallback |

## Reporting problems

Open an issue describing the screen and what was said. If you can, attach
`avatar_reader.log` (in the program's folder) and a screenshot of the screen (F12 in Steam).

## Credits

NVDA's controller library (in `lib`) is from NV Access, under the GNU LGPL 2.1, via the
[accessible_output2](https://github.com/accessibleapps/accessible_output2) project.
See `share/LICENSES.txt`.
