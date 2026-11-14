Avatar Reader
A screen reader helper for Avatar Legends: The Fighting Game on PC.

It watches the screen while the game runs and speaks what is highlighted,
through NVDA. If NVDA is not running, it uses the Windows voice instead.
It does not change the game or its files in any way. It only looks at the screen.


Starting it
1. Unzip the folder anywhere, for example into Documents.
2. Open the folder and open Avatar Reader (the program, Avatar Reader.exe).
3. You will hear "Avatar reader started". Then start the game.
Nothing needs installing. Windows may ask whether to run a program from an
unknown publisher the first time: choose More info, then Run anyway.


What it reads
- Menus: the highlighted option, and the menu title when a menu opens.
- Options and training settings: each setting with its value, for example
  "Main Volume, 50".
- Local VS controller setup: which side each controller is on (Player 1,
  the middle, or Player 2) and which side is the computer (CPU).
- Character select: both fighters, the support character and the variation.
- Stage select: the stage name.
- Command list: each move's name, tags, button input and description, for example
  "Blue Spirit Liberation, 4 Energy, Hard Knockdown. Input: quarter circle
  forward, A plus B plus C". Directions are for a fighter facing right.
- Online: the lobby list, custom lobbies (settings, capacity, invite code,
  players, host, match slots) and yes or no popups with their question.
- Online matches: searching status, the match-found popup (your opponent,
  their level and connection), the pick timer at 10, 5 and 3 seconds, and the
  results screen (who won, the score, and whether your opponent chose a rematch).
- Tutorials: the tutorial menu (including which fighter is highlighted on the
  grid) and the instruction text shown during a tutorial, with buttons named.
Before a fight: the stage name on the versus screen, and the fighters' lines, with who is speaking, for example
"Ozai: The universe has delivered me another act of providence!"
During fights:
- A chime when your Flow gauge is full again after using it.
- A note each time you gain energy, higher for each level (up to 7).
- Combos when they end, yours and your opponent's, for example "4 hits,
  87 damage" or "Opponent 3 hits, 123 damage".
- Tutorial instructions.
- An alert when your health or your opponent's drops to 30 percent: a
  two-tone alarm, higher for you, lower for your opponent.
Your sounds come from your side. Your opponent's come from their side (their
Flow and energy sounds can be turned on in the menu).

Accessibility menu
Press F3: up and down move, left and right change a setting, Enter switches
it, Escape or F3 closes the menu. On a controller, press the right stick in
(R3): push the right stick up or down to move and left or right to change,
and press it in again to close. The game ignores the right stick in its
menus, so it won't move along with you.
It has: fight sounds on or off, which player you are, combo announcements,
the health alert (you and your opponent, you only, or off), Flow and energy
sounds, your opponent's sounds, tutorial instructions,
and a separate volume for the health alert, the energy sounds, the Flow sound
and your opponent's sounds. Changing a volume plays that sound. Your choices
are remembered.

Custom sounds
You can use your own sounds instead of the built-in ones. Avatar Reader makes
a folder called "Custom sounds" next to it, with a file explaining the names to
use (for example health_low.wav, flow_full.wav and energy.wav). Sounds must be
WAV files. New files are picked up when you open the accessibility menu.


Hotkeys
Control Shift R: repeat the last thing said
Control Shift S: read all the text on the screen
Control Shift P: pause or resume automatic reading
Control Shift Q: quit Avatar Reader
Control Shift G: hear health, Flow gauge and energy, yours and your opponent's
Control Shift D: save a picture of the screen in the Saved screens folder,
  to share when something isn't read right
F3: accessibility menu (controller: press the right stick in, R3)


Game settings it needs
- Display mode: borderless or windowed. In exclusive fullscreen the screen can
  look black to the reader. It will tell you if that happens.
- Resolution: 1920 by 1080 works best. Other 16 by 9 sizes should also work.
- The game should be on your main monitor.
- Windows needs English text recognition, which English versions of Windows
  have built in.


If something goes wrong
The file avatar_reader.log, in the same folder, records what was said and any
errors. Please include it when reporting a problem.
