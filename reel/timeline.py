"""Shared timeline for the Athlo "One line, every sport." reel (picture and sound).

128 BPM, one beat = 0.469 s. Each sport beat is 3 beats long (1.41 s); the montage is
4 beats (three objects, one beat each); the end card holds for 3.9 s.
"""
FPS = 30
W, H = 1080, 1920
BPM = 128
BEAT = 60.0 / BPM
DUR = 17.0

#            0 one line, 1 padel, 2 run, 3 football, 4 archery, 5 swim, 6 montage, 7 stairs, 8 logo, 9 end card
_BEATS = [0, 3, 6, 9, 12, 15, 18, 22, 25, 28]
S = [b * BEAT for b in _BEATS] + [DUR]
NAMES = ["one_line", "padel", "run", "football", "archery", "swim", "montage", "stairs", "logo", "end_card"]

# Ribbon wipe, relative to the start of each scene: the old shape snaps to the edge (0-0.10),
# the line sweeps across and drags the new colour behind it (0.10-0.30), then it springs
# into the new scene's first shape (0.30-0.55).
SNAP, SWEEP_END, ARRIVE = 0.10, 0.30, 0.55

# Safe area for text and buttons: nothing in the top 10 % or bottom 20 %.
SAFE_TOP, SAFE_BOTTOM = int(H * 0.10), int(H * 0.80)
