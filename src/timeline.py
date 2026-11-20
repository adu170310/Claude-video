"""Shared timeline for picture and sound (seconds). 96 BPM: one beat = 0.625 s. 30 s = 48 beats."""
FPS = 30
W, H = 1080, 1920
DUR = 30.0
BEAT = 0.625

# Safe area for key text and buttons: out of the top tenth and the bottom fifth.
SAFE_TOP = 192
SAFE_BOTTOM = 1536

HOOK_IN = 0.12                  # "Sport in Dubai is scattered." over chaos already in motion
NUDGE = 1.9                     # three letters slip, then settle by NUDGE + 1.0
HOOK_OUT = 3.55                 # hook text leaves before the collapse
COLLAPSE = 3.75                 # chaos pulled to the centre
MERGE = 4.375                   # flash -> the real Athlo logo
LOGO_UP = 5.0                   # logo rises, phone with the real app slides up
APP_OUT = 7.12                  # app shot leaves
WORDS = [7.5, 10.0, 12.5, 15.0, 17.5]       # Discover / Book / Play / Train / Compete, 4 beats each
RECAP = [20.0 + i * BEAT / 2 for i in range(5)]   # the line builds word by word on eighth notes
RECAP_OUT = 21.95
LOGO = 22.5
LINE = 23.125                   # "Your sports life, in one place."
LINE_OUT = 24.62
CTA = 25.0                      # "Join the Dubai Fitness 30x30" (largest line)
WHOOP = 25.3125                 # "Win a Whoop for playing any sport."
BUTTON = 25.625                 # big "Link in bio" button
PULSE = 27.5                    # button press pulse
