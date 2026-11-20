"""Every cue of the speedrun reel, in beats at 128 BPM. Shared by picture and sound."""
BPM = 128
B = 60.0 / BPM            # 0.46875 s per beat; 30 s = 64 beats
FPS, W, H = 30, 1080, 1920
DUR = 30.0
N = int(DUR * FPS)

def tb(b):
    return b * B

# safe area for text: below the top tenth, above the bottom fifth
SAFE_TOP, SAFE_BOT = int(H * 0.10), int(H * 0.80)   # 192 .. 1536

GO = 5                       # "GO!" stab
SESS0, SESS_LEN = 6, 3       # five sessions, 3 beats each: b6, 9, 12, 15, 18
SPORTS = [("PADEL", "PADEL PRO"), ("RUNNING", "PACE SETTER"), ("FOOTBALL", "PITCH MASTER"),
          ("GYM", "IRON WILL"), ("SWIMMING", "LANE LEGEND")]
SESS = [SESS0 + i * SESS_LEN for i in range(5)]
ACH = [s + 1 for s in SESS]  # achievement pop-up one beat after each log
RANK0 = 21
RANKS = [(21, 99, 47), (23, 47, 30), (25, 30, 12)]   # (beat, from, to) -- illustrative only
COMBO0 = 28
COMBOS = [(28, 3), (32, 5), (35, 7)]
BOSS0 = 38
STOMPS = [38, 40, 42]
POWER0 = 44
COLLECT = 45
WIN = 48
RANK_WIN = (48, 12, 1)
END0 = 50                    # "PRESS START"
CARD = 53                    # logo end card, held to the end (5.6 s)
SCENE_CUTS = [6, 21, 28, 38, 44, 50, 53]
