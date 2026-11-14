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
- **Local VS controller setup:** which side each controller is on, and which side is the computer.
- **Arcade mode:** the fighter you are choosing.
- **Before a fight:** the stage on the versus screen and the fighters' lines, with who is speaking.
- **Popups:** the question ("Leave the lobby?") as soon as it appears, then Yes or No.
- **Tutorials:** the tutorial menu and the instruction text shown during a tutorial.

## During fights

- **Combos:** hits and damage when a combo ends, yours and your opponent's, for example
  "4 hits, 150 damage" or "Opponent 2 hits, 128 damage".
- **Flow gauge full:** a rising two-note chime when your Flow gauge refills after you used it.
- **Energy:** a plucked note when you gain energy, higher for each level (1 to 7).
- **Low health:** a two-tone alarm when your health or your opponent's drops to 30 percent,
  higher for you and lower for your opponent. Once per fighter per round.

Your sounds come from your side of the screen and your opponent's from theirs.

## Accessibility menu

Press **F3**, or click the right stick (**R3**) on a controller. With the keyboard, up and
down move and left and right change a setting; with a controller, push the right stick.
Escape, F3 or R3 closes it. It has: all fight sounds on or off, which player you are,
combos, the health alert (you and your opponent, you only, or off), Flow and energy
sounds, your opponent's Flow and energy sounds, tutorial instructions, and a separate
volume for each kind of sound. Your choices are saved.

### Custom sounds

The reader makes a **Custom sounds** folder beside it. Put WAV files there named after the
sound they replace: `health_low.wav`, `flow_full.wav`, `energy.wav` (or `energy_1.wav` to
`energy_7.wav`). Add `_opponent` for your opponent's version, for example
`health_low_opponent.wav`. New files are picked up when you open the accessibility menu.
The folder has a text file with the full details.

## Install

1. Download **[AvatarReader.zip](https://github.com/ItsTBlaze/avatar-legends-fighting-game-accessibility/raw/main/download/AvatarReader.zip)**.
   This link always gets the newest version (currently 0.2.0).
2. Unzip it anywhere, for example into Documents.
3. Open the unzipped **Avatar Reader** folder and run **Avatar Reader**. Nothing needs
   installing. Windows may ask whether to run a program from an unknown publisher:
   choose **More info**, then **Run anyway**.
4. You will hear "Avatar reader" followed by the version number and "started". Then
   start the game. You can also start the reader after the game.

To update, download the new zip and unzip it over the old folder (quit the reader
first with Ctrl+Shift+Q).

### Hotkeys

| Keys | Action |
| --- | --- |
| Ctrl+Shift+R | Repeat the last thing said |
| Ctrl+Shift+S | Read all the text on the screen |
| Ctrl+Shift+P | Pause or resume automatic reading |
| Ctrl+Shift+Q | Quit |
| Ctrl+Shift+G | Hear health, Flow gauge and energy, yours and your opponent's |
| Ctrl+Shift+D | Save a picture of the screen in the Saved screens folder, to share when something isn't read |
| F3 | Accessibility menu (controller: R3) |

The reader only reads while the game is the window in front, so it stays quiet in
other programs.

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
4. **Make shareable copy.bat** builds the standalone `AvatarReader.zip`, next to the
   batch file. To save it somewhere else, put that folder's path on the first line of a
   file named `output_folder.txt` beside the batch file.

### How it works

| File | Purpose |
| --- | --- |
| `avatar_reader.py` | Main program: screen capture, hotkeys, self test |
| `reader.py` | Decides what to say for each screen |
| `fight.py` | Fight sounds and combo announcements |
| `sounds.py` | Makes the sound cues and loads custom sounds |
| `menu.py` | The accessibility menu and the controller shortcut |
| `settings.py` | Saves the menu choices |
| `hotkeys.py` | Shortcut keys through Windows (no keyboard hook) |
| `detector.py` | Finds highlights, screens and fixed regions |
| `ocr.py` | Text recognition with the OCR built into Windows |
| `inputs.py` | Reads arrow and button icons in move inputs |
| `textclean.py` | Tidies recognised text for speech |
| `speech.py` | Speech through NVDA, with the Windows voice as a fallback |

## Reporting problems

Open an issue describing the screen and what was said. If you can, attach
`avatar_reader.log` (in the program's folder) and a picture of the screen: press
Ctrl+Shift+D on it, and the picture is saved in the Saved screens folder.

## Credits

NVDA's controller library (in `lib`) is from NV Access, under the GNU LGPL 2.1, via the
[accessible_output2](https://github.com/accessibleapps/accessible_output2) project.
See `share/LICENSES.txt`.

Avatar Reader is released under the MIT License (see `LICENSE`).
