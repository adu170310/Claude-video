#!/usr/bin/env python3
"""Athlo "One line, every sport." 1080x1920 @ 30 fps, drawn frame by frame with cairo.

    python3 reel/picture.py              # full render -> work/reel/picture.mp4 (+ motion.json, cues.json)
    python3 reel/picture.py --stills     # one still per beat -> work/reel/stills/ + contact sheet
    python3 reel/picture.py --at 2.3,5.1 # arbitrary single frames

One continuous orange-to-pink ribbon carries the whole film. Every background change is a
ribbon wipe: the line snaps to an edge, sweeps across and drags the new colour behind it,
then springs into the next sport.
"""
import json, math, os, subprocess, sys
from multiprocessing import Pool

import cairo
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from timeline import *  # noqa: F401,F403

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WK = os.path.join(ROOT, "work", "reel")


def hexrgb(h):
    return tuple(int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))


OFF, ORG, PNK = hexrgb("#F4F2EC"), hexrgb("#FFAD01"), hexrgb("#FC0464")
NAV = hexrgb("#05193A")          # the navy of the Athlo wordmark
WHT = (1, 1, 1)
LIME = hexrgb("#DDF54A")         # padel ball
TAN, TAN2 = hexrgb("#F6CB85"), hexrgb("#E2A85A")  # cricket bat willow
BLACK_FACE, XB_FACE = "Inter Display Black", "Inter Display ExtraBold"
N = 220                          # points per ribbon
RIB_W = 30

# ------------------------------------------------------------------ easing + maths
def cl(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def eo(t, p=3):                  # ease-out
    return 1 - (1 - cl(t)) ** p


def eob(t, s=1.7):               # ease-out with overshoot
    t = cl(t) - 1
    return 1 + t * t * ((s + 1) * t + s)


def eio(t):
    t = cl(t)
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def lerp(a, b, t):
    return a + (b - a) * t


def mix(c0, c1, t):
    return tuple(a + (b - a) * t for a, b in zip(c0, c1))


def arcd(P):
    return np.r_[0, np.cumsum(np.hypot(*np.diff(P, axis=0).T))]


def sub(P, a, b, n=N):
    P = np.asarray(P, float)
    d = arcd(P)
    s = np.linspace(a * d[-1], b * d[-1], n)
    return np.c_[np.interp(s, d, P[:, 0]), np.interp(s, d, P[:, 1])]


def frac_at(P, pt):
    """Arc-length fraction of the vertex of P nearest to pt."""
    P = np.asarray(P, float)
    i = int(np.argmin(np.hypot(*(P - np.asarray(pt, float)).T)))
    d = arcd(P)
    return d[i] / d[-1]


def point_at(P, f):
    return sub(P, f, f, 1)[0]


def bez(p0, p1, p2, p3, n=60):
    t = np.linspace(0, 1, n)[:, None]
    p0, p1, p2, p3 = map(np.asarray, (p0, p1, p2, p3))
    return (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3


def catmull(pts, k=24):
    p = np.asarray(pts, float)
    p = np.vstack([2 * p[0] - p[1], p, 2 * p[-1] - p[-2]])
    out = []
    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
        for t in np.linspace(0, 1, k, endpoint=False):
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(p[-2])
    return np.array(out)


def arc(cx, cy, r, a0, a1, n=120):
    a = np.linspace(a0, a1, n)
    return np.c_[cx + r * np.cos(a), cy + r * np.sin(a)]


def cat(*segs):
    return np.vstack([np.asarray(s, float) for s in segs])


def xform(P, cx, cy, s=1.0, rot=0.0):
    P = np.asarray(P, float)
    c, si = math.cos(rot), math.sin(rot)
    return np.c_[cx + s * (P[:, 0] * c - P[:, 1] * si), cy + s * (P[:, 0] * si + P[:, 1] * c)]


def closed(P):
    P = np.asarray(P, float)
    return np.vstack([P, P[:1]])


# ------------------------------------------------------------------ drawing helpers
def poly(c, P, close=False):
    c.move_to(*P[0])
    for p in P[1:]:
        c.line_to(*p)
    if close:
        c.close_path()


def fill_poly(c, P, col, a=1.0):
    poly(c, P, True)
    c.set_source_rgba(*col, a)
    c.fill()


def stroke_poly(c, P, col, w, a=1.0, close=False):
    poly(c, P, close)
    c.set_source_rgba(*col, a)
    c.set_line_width(w)
    c.set_line_cap(cairo.LINE_CAP_ROUND)
    c.set_line_join(cairo.LINE_JOIN_ROUND)
    c.stroke()


def circle(c, x, y, r, col, a=1.0):
    c.arc(x, y, max(r, 0.01), 0, 2 * math.pi)
    c.set_source_rgba(*col, a)
    c.fill()


def rrect(c, x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    c.new_sub_path()
    c.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    c.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    c.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    c.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    c.close_path()


def rib_colors(n, phase=None, k=0.0):
    """Orange -> pink along the ribbon. In the end card the gradient flows round the loop."""
    u = np.linspace(0, 1, n)
    if phase is not None and k > 0:
        tri = 1 - np.abs(2 * ((u + phase) % 1.0) - 1)
        u = u * (1 - k) + tri * k
    return [mix(ORG, PNK, x) for x in u]


def draw_ribbon(c, P, w=RIB_W, cols=None, halo=7, alpha=1.0):
    cols = cols or rib_colors(len(P))
    c.set_line_cap(cairo.LINE_CAP_ROUND)
    c.set_line_join(cairo.LINE_JOIN_ROUND)
    if halo:
        poly(c, P)
        c.set_source_rgba(*OFF, alpha)
        c.set_line_width(w + 2 * halo)
        c.stroke()
    c.set_line_width(w)
    for i in range(len(P) - 1):
        c.set_source_rgba(*cols[i], alpha)
        c.move_to(*P[i])
        c.line_to(*P[i + 1])
        c.stroke()


def text_line(c, segs, cx, cy, size, t, face=BLACK_FACE, stagger=0.03, dur=0.24, maxw=940,
              track=0.0, typed=False):
    """Kinetic line: each letter springs up from its baseline with overshoot.
    segs = [(text, colour), ...]; cy is the optical centre of the capitals."""
    if t <= 0:
        return
    c.select_font_face(face)
    c.set_font_size(size)
    chars = [(ch, col) for s, col in segs for ch in s]
    adv = [c.text_extents(ch).x_advance + track for ch, _ in chars]
    tot = sum(adv) - track
    if tot > maxw:
        size *= maxw / tot
        c.set_font_size(size)
        adv = [c.text_extents(ch).x_advance + track * maxw / tot for ch, _ in chars]
        tot = sum(adv) - track * maxw / tot
    cap = 0.727 * size
    x, base = cx - tot / 2, cy + cap / 2
    for i, (ch, col) in enumerate(chars):
        u = (t - i * stagger) / dur
        if u > 0 and ch != " ":
            if typed:
                s, dy = 0.85 + 0.15 * eob(u * 3), 0.0
            else:
                s, dy = eob(u, 2.2), (1 - eo(u)) * 0.35 * size
            c.save()
            c.translate(x + adv[i] / 2, base + dy)
            c.scale(s, s)
            c.move_to(-(adv[i] - track) / 2, 0)
            c.set_source_rgb(*col)
            c.show_text(ch)
            c.restore()
        x += adv[i]
    return x  # right edge, for carets


def burst(c, x, y, tau, col, n=8, r0=40, r1=150, a0=-math.pi, a1=0.0, w=10, dur=0.32):
    if not 0 <= tau <= dur:
        return
    e = eo(tau / dur)
    for i in range(n):
        a = lerp(a0, a1, (i + 0.5) / n)
        ri, ro = lerp(r0, r1 * 0.75, e), lerp(r0 + 25, r1, eo(tau / dur * 1.6))
        if ro - ri < 1:
            continue
        stroke_poly(c, [(x + ri * math.cos(a), y + ri * math.sin(a)), (x + ro * math.cos(a), y + ro * math.sin(a))],
                    col, w * (1 - 0.6 * e))


def pop(t, s=1.9):
    return eob(t, s) if t > 0 else 0.0


TEXT_Y = 1365  # one consistent line for every sport word (inside the safe area)

# ------------------------------------------------------------------ scene 0: "One line."
P0 = catmull([(-90, 1140), (170, 1080), (400, 960), (590, 820), (640, 660), (520, 590), (420, 690),
              (500, 840), (720, 900), (930, 830), (1170, 760)], 30)


def rib0(tl):
    return sub(P0, 0, 0.10 + 0.90 * eo(tl / 0.62))


def under0(c, tl):
    pass


def over0(c, tl):
    t = tl - 0.42
    if t <= 0:
        return
    full = "One line."
    k = min(len(full), int(t / 0.055) + 1)
    c.select_font_face(BLACK_FACE)
    c.set_font_size(176)
    width = sum(c.text_extents(ch).x_advance for ch in full)
    # letters type on in place (the line is laid out at its final centred position)
    text_line(c, [(full, NAV)], 540, TEXT_Y, 176, t, stagger=0.055, dur=0.1, typed=True)
    right = 540 - width / 2 + sum(c.text_extents(ch).x_advance for ch in full[:k])
    # pink caret, blinking once typing is done
    done = t > 0.055 * len(full)
    if not done or int((t - 0.055 * len(full)) / 0.22) % 2 == 0:
        c.rectangle(right + 10, TEXT_Y - 66, 14, 132)
        c.set_source_rgb(*PNK)
        c.fill()


# ------------------------------------------------------------------ scene 1: PADEL
FLOOR1 = 1190
_lead1 = bez((-60, 760), (60, 820), (100, 1000), (150, 1150), 50)
_u = np.linspace(0, 1, 110)
_para1 = np.c_[150 + 710 * _u, lerp(1150, 1156, _u) - 4 * 520 * _u * (1 - _u)]
_u = np.linspace(0, 1, 40)
_bnc1 = np.c_[860 + 150 * _u, 1156 - 4 * 110 * _u * (1 - _u)]
P1 = cat(_lead1, _para1[1:], _bnc1[1:])
F1_HIT, F1_LAND = frac_at(P1, (150, 1150)), frac_at(P1, (860, 1156))
T1_HIT, T1_LAND, T1_END = 0.32, 0.86, 1.10


def head1(tl):
    if tl < T1_HIT:
        return F1_HIT
    if tl < T1_LAND:
        return lerp(F1_HIT, F1_LAND, (tl - T1_HIT) / (T1_LAND - T1_HIT))
    return lerp(F1_LAND, 1.0, cl((tl - T1_LAND) / (T1_END - T1_LAND)))


def rib1(tl):
    return sub(P1, 0, head1(tl))


def racket(c, px, py, ang):
    c.save()
    c.translate(px, py)
    c.rotate(ang)
    rrect(c, -14, -70, 28, 120, 12)              # handle
    c.set_source_rgb(*NAV)
    c.fill()
    for yy in (-40, -10, 20):
        c.rectangle(-14, yy, 28, 9)
        c.set_source_rgb(*OFF)
        c.fill()
    c.save()
    c.translate(0, -150)
    c.scale(64, 84)
    c.arc(0, 0, 1, 0, 2 * math.pi)
    c.restore()
    c.set_source_rgb(*NAV)
    c.fill_preserve()
    c.set_source_rgb(*OFF)
    c.set_line_width(7)
    c.stroke()
    for gx in (-30, -10, 10, 30):
        for gy in (-195, -172, -149, -126, -103):
            if (gx / 58) ** 2 + ((gy + 150) / 76) ** 2 < 0.8:
                circle(c, gx, gy, 5, OFF)
    c.restore()


def under1(c, tl):
    # court floor line draws out from the centre
    e = eo((tl - 0.18) / 0.3)
    if e > 0:
        stroke_poly(c, [(540 - 500 * e, FLOOR1), (540 + 500 * e, FLOOR1)], OFF, 10)
    # net: side-on panel with mesh, pops up from the floor
    s = pop((tl - 0.22) / 0.32)
    if s > 0:
        c.save()
        c.translate(540, FLOOR1)
        c.scale(1, s)
        c.translate(-540, -FLOOR1)
        top_l, top_r = (505, 1015), (575, 995)
        for i in range(1, 7):
            y = lerp(0, 175, i / 7)
            stroke_poly(c, [(505, 1015 + y), (575, 995 + y)], NAV, 3, 0.6)
        for i in range(1, 5):
            x = lerp(505, 575, i / 5)
            yt = lerp(1015, 995, i / 5)
            stroke_poly(c, [(x, yt), (x, yt + 175)], NAV, 3, 0.6)
        stroke_poly(c, [(505, 1015), (505, FLOOR1)], NAV, 14)
        stroke_poly(c, [(575, 995), (575, FLOOR1 - 20)], NAV, 14)
        stroke_poly(c, [top_l, top_r], OFF, 12)
        c.restore()
    # racket swings through the ball at T1_HIT
    if tl > 0.12:
        sw = eob((tl - 0.20) / 0.20, 1.2)
        ang = math.radians(lerp(-38, 42, sw))
        sc = pop((tl - 0.12) / 0.2)
        c.save()
        c.translate(48, 1225)
        c.scale(sc, sc)
        racket(c, 0, 0, ang)
        c.restore()


def ball_padel(c, x, y, r, spin, sx=1.0, sy=1.0):
    c.save()
    c.translate(x, y)
    c.scale(sx, sy)
    circle(c, 0, 0, r, LIME)
    c.rotate(spin)
    c.set_source_rgb(*OFF)
    c.set_line_width(5)
    c.arc(-r * 1.25, 0, r * 0.95, -0.75, 0.75)
    c.stroke()
    c.arc(r * 1.25, 0, r * 0.95, math.pi - 0.75, math.pi + 0.75)
    c.stroke()
    c.restore()


def over1(c, tl):
    if tl > 0.18:
        h = head1(tl)
        x, y = point_at(P1, h)
        # floor shadow
        k = cl(1 - (FLOOR1 - 34 - y) / 600)
        c.save()
        c.translate(x, FLOOR1 + 4)
        c.scale(46 * (0.45 + 0.55 * k), 9)
        c.arc(0, 0, 1, 0, 2 * math.pi)
        c.restore()
        c.set_source_rgba(*NAV, 0.22 * k)
        c.fill()
        sx = sy = 1.0
        for tland in (T1_LAND, T1_END):
            d = tl - tland
            if 0 <= d < 0.09:
                q = math.sin(math.pi * d / 0.09)
                sx, sy = 1 + 0.32 * q, 1 - 0.3 * q
                y += 34 * 0.3 * q
        r = 34 * pop((tl - 0.18) / 0.15)
        ball_padel(c, x, y, r, tl * 9, sx, sy)
    burst(c, 860, FLOOR1 - 4, tl - T1_LAND, OFF, n=9, r0=48, r1=170)
    text_line(c, [("PADEL", NAV)], 540, TEXT_Y, 230, tl - 0.40)


# ------------------------------------------------------------------ scene 2: RUN
LANE2 = 1040


def heel2(tl):
    return 380 + 260 * eo((tl - 0.30) / 1.0, 2)


def step_bounce(tl):
    if tl < 0.45:
        return 0.0, 0.0
    ph = (tl - 0.45) / 0.23
    return 30 * abs(math.sin(math.pi * ph)), -0.10 * math.sin(2 * math.pi * ph)


def rib2(tl):
    return sub([(-80, LANE2), (heel2(tl) + 14, LANE2)], 0, 1)


_rng = np.random.default_rng(7)
STREAKS = [(float(_rng.uniform(0, 1500)), float(y), float(_rng.uniform(90, 300)), float(_rng.uniform(2200, 3400)))
           for y in list(np.linspace(830, 990, 5)) + list(np.linspace(1090, 1180, 3)) + list(np.linspace(640, 760, 3))]


def under2(c, tl):
    # lane lines with scrolling dashes
    for y in (780, 1210):
        e = eo((tl - 0.15) / 0.3)
        if e <= 0:
            continue
        stroke_poly(c, [(540 - 560 * e, y), (540 + 560 * e, y)], OFF, 10)
    off = (tl * 1900) % 160
    for y in (880, 1150):
        a = cl((tl - 0.3) / 0.2)
        if a <= 0:
            continue
        for x in np.arange(-160, 1240, 160) - off:
            stroke_poly(c, [(x, y), (x + 60, y)], OFF, 8, 0.55 * a)
    # motion streaks rushing past
    if tl > 0.30:
        g = eo((tl - 0.30) / 0.25)
        for x0, y, ln, v in STREAKS:
            x = (x0 - v * tl) % 1500 - 200
            stroke_poly(c, [(x, y), (x + ln * g, y)], OFF, 8, 0.8)


def sneaker(c, x, y, s, rot):
    """Flat side-view running shoe, heel at the origin, facing right."""
    c.save()
    c.translate(x, y)
    c.rotate(rot)
    c.scale(s, s)
    # sole
    rrect(c, -6, -34, 300, 34, 17)
    c.set_source_rgb(*OFF)
    c.fill()
    c.rectangle(-4, -14, 296, 6)
    c.set_source_rgb(*ORG)
    c.fill()
    # upper
    c.move_to(0, -30)
    c.line_to(2, -118)
    c.curve_to(4, -140, 30, -146, 52, -138)
    c.line_to(104, -118)
    c.curve_to(128, -110, 150, -96, 176, -78)
    c.curve_to(218, -60, 282, -58, 292, -30)
    c.close_path()
    c.set_source_rgb(*NAV)
    c.fill()
    # speed band
    c.move_to(40, -62)
    c.curve_to(110, -78, 170, -70, 238, -48)
    c.line_to(226, -36)
    c.curve_to(160, -52, 110, -56, 46, -44)
    c.close_path()
    c.set_source_rgb(*ORG)
    c.fill()
    # heel tab + laces
    rrect(c, -4, -132, 22, 46, 8)
    c.set_source_rgb(*PNK)
    c.fill()
    for i in range(3):
        lx = 120 + i * 22
        ly = -112 + i * 14
        stroke_poly(c, [(lx - 8, ly - 6), (lx + 10, ly + 6)], OFF, 6)
    c.restore()


def over2(c, tl):
    if tl > 0.26:
        b, r = step_bounce(tl)
        x = heel2(tl)
        s = 1.1 * pop((tl - 0.26) / 0.18)
        # little speed ticks behind the heel
        for i, yy in enumerate((-60, -100, -140)):
            a = cl((tl - 0.35) / 0.1)
            ln = 50 + 30 * math.sin(tl * 30 + i)
            stroke_poly(c, [(x - 40 - ln, LANE2 - 14 + yy * 1.2 - b), (x - 40, LANE2 - 14 + yy * 1.2 - b)], OFF, 8, a)
        sneaker(c, x, LANE2 - 14 - b, s, r)
    text_line(c, [("RUN", NAV)], 540, TEXT_Y, 260, tl - 0.40)


# ------------------------------------------------------------------ scene 3: FOOTBALL
_lead3 = bez((-60, 190), (180, 520), (-60, 1080), (200, 1185), 70)
_pass3 = bez((200, 1185), (560, 1250), (800, 990), (640, 765), 90)
P3 = cat(_lead3, _pass3[1:])
F3_KICK = frac_at(P3, (200, 1185))
T3_KICK, T3_GOAL = 0.30, 0.78
HIT3 = np.array([640.0, 765.0])
GX0, GX1, GY0, GY1 = 232, 848, 560, 1010


def head3(tl):
    if tl < T3_KICK:
        return F3_KICK
    return lerp(F3_KICK, 1.0, eo((tl - T3_KICK) / (T3_GOAL - T3_KICK), 2))


def rib3(tl):
    return sub(P3, 0, head3(tl))


def net_disp(x, y, tl):
    tau = tl - T3_GOAL
    if tau <= 0:
        return x, y
    dx, dy = x - HIT3[0], y - HIT3[1]
    r = np.hypot(dx, dy) + 1e-6
    a = 34 * np.exp(-3.2 * tau) * np.exp(-r / 240) * np.sin(r / 36 - 26 * tau)
    a = a - 30 * np.exp(-r / 90) * np.exp(-5 * tau)  # the pocket the ball punches in
    return x + a * dx / r, y + a * dy / r


def under3(c, tl):
    s = pop((tl - 0.18) / 0.3)
    if s <= 0:
        return
    c.save()
    c.translate(540, GY1)
    c.scale(s, s)
    c.translate(-540, -GY1)
    stroke_poly(c, [(120, GY1), (960, GY1)], NAV, 6, 0.25)
    xs = np.linspace(GX0, GX1, 60)
    for y in np.arange(GY0 + 40, GY1, 44):
        X, Y = net_disp(xs, np.full_like(xs, y), tl)
        stroke_poly(c, np.c_[X, Y], NAV, 3.5, 0.35)
    ys = np.linspace(GY0, GY1, 50)
    for x in np.arange(GX0 + 44, GX1, 44):
        X, Y = net_disp(np.full_like(ys, x), ys, tl)
        stroke_poly(c, np.c_[X, Y], NAV, 3.5, 0.35)
    stroke_poly(c, [(GX0, GY1), (GX0, GY0), (GX1, GY0), (GX1, GY1)], NAV, 24)
    c.restore()


def football(c, x, y, r, spin):
    c.save()
    c.translate(x, y)
    circle(c, 0, 0, r, WHT)
    c.arc(0, 0, r, 0, 2 * math.pi)
    c.clip()
    c.rotate(spin)

    def pent(px, py, pr, rot):
        pts = [(px + pr * math.cos(rot + i * 2 * math.pi / 5), py + pr * math.sin(rot + i * 2 * math.pi / 5)) for i in range(5)]
        fill_poly(c, pts, NAV)

    pent(0, 0, r * 0.34, -math.pi / 2)
    for i in range(5):
        a = -math.pi / 2 + math.pi / 5 + i * 2 * math.pi / 5
        pent(r * 0.98 * math.cos(a), r * 0.98 * math.sin(a), r * 0.30, a)
        stroke_poly(c, [(r * 0.34 * math.cos(a), r * 0.34 * math.sin(a)), (r * 0.78 * math.cos(a), r * 0.78 * math.sin(a))], NAV, r * 0.06)
    c.reset_clip()
    c.arc(0, 0, r, 0, 2 * math.pi)
    c.set_source_rgb(*NAV)
    c.set_line_width(max(3, r * 0.1))
    c.stroke()
    c.restore()


def over3(c, tl):
    if tl > 0.20:
        h = head3(tl)
        x, y = point_at(P3, h)
        u = cl((tl - T3_KICK) / (T3_GOAL - T3_KICK))
        r = lerp(62, 40, eo(u, 2)) * pop((tl - 0.20) / 0.14)
        if tl > T3_GOAL:
            y += 22 * eo((tl - T3_GOAL) / 0.35)
        football(c, x, y, r, (tl - T3_KICK) * 14 if tl > T3_KICK else 0)
    burst(c, 200, 1185, tl - T3_KICK, NAV, n=5, r0=74, r1=140, a0=math.pi * 0.55, a1=math.pi * 1.15, w=8, dur=0.25)
    text_line(c, [("FOOTBALL", NAV)], 540, TEXT_Y, 230, tl - 0.40)


# ------------------------------------------------------------------ scene 4: ARCHERY
TIP_T, TIP_B, NOCK_Y = (300, 560), (300, 1160), 860
TGT = (860, 860)
T4_PULL0, T4_PULL1, T4_REL, T4_HIT = 0.30, 0.66, 0.80, 0.96
ARROW_L = 330
BOW = catmull([(270, 538), (300, 560), (392, 640), (446, 760), (456, 860), (446, 960), (392, 1080), (300, 1160), (270, 1182)], 16)


def nock4(tl):
    if tl < T4_REL:
        x = lerp(300, 140, eo((tl - T4_PULL0) / (T4_PULL1 - T4_PULL0)))
        if tl > T4_PULL1:
            x += 2.5 * math.sin(tl * 90)
        return x
    return lerp(140, TGT[0] - ARROW_L + 6, cl((tl - T4_REL) / (T4_HIT - T4_REL)))


def string4(xn):
    return sub([TIP_T, (xn, NOCK_Y), TIP_B], 0, 1)


TRAIL_X0 = 180


def rib4(tl):
    if tl < T4_REL:
        return string4(nock4(tl))
    xn = nock4(tl)
    trail = sub([(TRAIL_X0, NOCK_Y), (max(xn, TRAIL_X0 + 40), NOCK_Y)], 0, 1)
    return lerp(string4(nock4(T4_REL - 1e-3)), trail, eob((tl - T4_REL) / 0.14, 1.2))


def target(c, x, y, s):
    for r, col in ((175, OFF), (136, PNK), (98, OFF), (60, PNK), (26, NAV)):
        circle(c, x, y, r * s, col)


def under4(c, tl):
    s = pop((tl - 0.16) / 0.3)
    if s > 0:
        c.save()
        c.translate(TIP_T[0], NOCK_Y)
        c.scale(s, s)
        c.translate(-TIP_T[0], -NOCK_Y)
        stroke_poly(c, BOW, NAV, 22)
        rrect(c, 436, 812, 38, 96, 14)
        c.set_source_rgb(*OFF)
        c.fill()
        c.restore()
    if tl >= T4_REL:  # thin bow string left behind, still humming
        tau = tl - T4_REL
        vib = 16 * math.sin(tau * 75) * math.exp(-tau * 8)
        stroke_poly(c, [TIP_T, (300 + vib, NOCK_Y), TIP_B], NAV, 4)
    ts = pop((tl - 0.22) / 0.3)
    if ts > 0:
        dx = 0
        if tl > T4_HIT:
            tau = tl - T4_HIT
            dx = 12 * math.sin(tau * 60) * math.exp(-tau * 9)
        stroke_poly(c, [(805 + dx, 1000), (770 + dx, 1190)], NAV, 16)
        stroke_poly(c, [(915 + dx, 1000), (950 + dx, 1190)], NAV, 16)
        target(c, TGT[0] + dx, TGT[1], ts)
        tau = tl - T4_HIT
        if 0 <= tau < 0.4:
            e = eo(tau / 0.4)
            c.arc(TGT[0], TGT[1], lerp(40, 280, e), 0, 2 * math.pi)
            c.set_source_rgba(*OFF, 1 - e)
            c.set_line_width(12 * (1 - e) + 2)
            c.stroke()


def arrow(c, xn, y, rot=0.0, tip_x=None):
    c.save()
    tip = xn + ARROW_L
    c.translate(tip, y)
    c.rotate(rot)
    c.translate(-tip, -y)
    stroke_poly(c, [(xn + 10, y), (tip - 24, y)], NAV, 9)
    fill_poly(c, [(tip, y), (tip - 40, y - 17), (tip - 30, y), (tip - 40, y + 17)], NAV)
    for sgn in (-1, 1):
        fill_poly(c, [(xn + 8, y), (xn + 62, y), (xn + 38, y + sgn * 28), (xn - 10, y + sgn * 28)], OFF)
    rrect(c, xn - 4, y - 7, 18, 14, 5)
    c.set_source_rgb(*PNK)
    c.fill()
    c.restore()


def over4(c, tl):
    a = pop((tl - 0.24) / 0.2)
    if a > 0:
        xn = nock4(tl)
        rot = 0.0
        if tl > T4_HIT:
            tau = tl - T4_HIT
            rot = math.radians(5) * math.sin(tau * 55) * math.exp(-tau * 7)
        c.save()
        c.translate(xn, NOCK_Y)
        c.scale(a, a)
        c.translate(-xn, -NOCK_Y)
        arrow(c, xn, NOCK_Y, rot)
        c.restore()
    burst(c, TGT[0], TGT[1], tl - T4_HIT, NAV, n=10, r0=190, r1=260, a0=0, a1=2 * math.pi, w=9, dur=0.3)
    text_line(c, [("ARCHERY", NAV)], 540, TEXT_Y, 230, tl - 0.40)


# ------------------------------------------------------------------ scene 5: SWIM
ROPE5 = 900
T5_SPLASH = 0.40
_rng = np.random.default_rng(11)
DROPS = [(float(_rng.uniform(-1, 1)), float(_rng.uniform(900, 1600)), float(_rng.uniform(9, 18))) for _ in range(18)]


def rope_y(x, tl):
    A = 38 * eob((tl - 0.32) / 0.4, 2.0)
    return ROPE5 + A * np.sin(2 * np.pi * x / 380 - 2 * np.pi * 1.5 * tl)


def rib5(tl):
    x = np.linspace(-80, 1160, N)
    return np.c_[x, rope_y(x, tl)]


def under5(c, tl):
    rows = ((690, 1), (770, -1), (1030, 1), (1110, -1), (1190, 1))
    for i, (y0, d) in enumerate(rows):
        e = eo((tl - 0.34 - 0.04 * i) / 0.35)
        if e <= 0:
            continue
        x = np.linspace(540 - 640 * e, 540 + 640 * e, 120)
        y = y0 + 13 * np.sin(2 * np.pi * x / 210 + d * 2 * np.pi * 1.1 * tl + i)
        stroke_poly(c, np.c_[x, y], OFF, 9, 0.9)


def over5(c, tl):
    # lane-rope floats ride the ribbon
    a = pop((tl - 0.5) / 0.25)
    if a > 0:
        for i, x in enumerate(np.arange(60, 1080, 160)):
            y = float(rope_y(np.array([x]), tl)[0])
            sl = float(rope_y(np.array([x + 2]), tl)[0]) - y
            c.save()
            c.translate(x, y)
            c.rotate(math.atan2(sl, 2))
            c.scale(26 * a, 19 * a)
            c.arc(0, 0, 1, 0, 2 * math.pi)
            c.restore()
            c.set_source_rgb(*(OFF if i % 2 == 0 else NAV))
            c.fill()
    tau = tl - T5_SPLASH
    if 0 <= tau < 0.6:
        for vx, vy, r in DROPS:
            x = 540 + vx * 620 * tau
            y = ROPE5 - vy * tau + 0.5 * 4200 * tau * tau
            rr = r * (1 - eo(tau / 0.6, 2))
            if y < ROPE5 + 10:
                circle(c, x, y, rr, OFF)
        e = eo(tau / 0.35)
        c.save()
        c.translate(540, ROPE5)
        c.scale(lerp(40, 300, e), lerp(12, 70, e))
        c.arc(0, 0, 1, math.pi, 2 * math.pi)
        c.restore()
        c.set_source_rgba(*OFF, 1 - e)
        c.set_line_width(10)
        c.stroke()
    text_line(c, [("SWIM", NAV)], 540, TEXT_Y, 250, tl - 0.40)


# ------------------------------------------------------------------ scene 6: montage
T6 = [0.30, 0.77, 1.24]
CEN6 = (540, 860)

DUMBBELL = [(-235, -30), (-215, -30), (-215, -95), (-175, -95), (-175, -125), (-120, -125), (-120, -20),
            (120, -20), (120, -125), (175, -125), (175, -95), (215, -95), (215, -30), (235, -30),
            (235, 30), (215, 30), (215, 95), (175, 95), (175, 125), (120, 125), (120, 20), (-120, 20),
            (-120, 125), (-175, 125), (-175, 95), (-215, 95), (-215, 30), (-235, 30)]


def _shuttle_outline():
    pts = [(-60, 100), (-150, -175)]
    for i in range(5):  # scalloped feather tips
        xa, xb = lerp(-150, 150, i / 5), lerp(-150, 150, (i + 1) / 5)
        for t in np.linspace(0, 1, 10)[1:]:
            x = lerp(xa, xb, t)
            pts.append((x, -175 - 22 * math.sin(math.pi * t)))
    pts += [(60, 100), (60, 118)]
    pts += [tuple(p) for p in arc(0, 118, 60, 0, math.pi, 30)]
    pts += [(-60, 100)]
    return pts


SHUTTLE = _shuttle_outline()
BAT = [(-17, -290), (17, -290), (17, -112), (62, -92), (62, 232), (48, 252), (-48, 252), (-62, 232), (-62, -92), (-17, -112)]
OBJ6 = [(DUMBBELL, 1.55, -0.26), (SHUTTLE, 1.45, 0.62), (BAT, 1.45, -0.52)]


def obj6_tf(k, tl):
    pts, s, rot = OBJ6[k]
    return s, rot + 0.10 * (tl - T6[k])


def outline6(k, tl):
    s, rot = obj6_tf(k, tl)
    return sub(closed(xform(OBJ6[k][0], *CEN6, s, rot)), 0, 1)


def rib6(tl):
    if tl < T6[1]:
        return outline6(0, tl)
    if tl < T6[2]:
        return lerp(outline6(0, tl), outline6(1, tl), eob((tl - T6[1]) / 0.14, 1.3))
    return lerp(outline6(1, tl), outline6(2, tl), eob((tl - T6[2]) / 0.14, 1.3))


def obj6_fill(c, k, tl):
    s, rot = obj6_tf(k, tl)
    p = pop((tl - T6[k] - 0.06) / 0.16, 2.2)
    if p <= 0:
        return
    c.save()
    c.translate(*CEN6)
    c.rotate(rot)
    c.scale(s * p, s * p)
    if k == 0:
        fill_poly(c, DUMBBELL, NAV)
        for x in (-150, 145):
            rrect(c, x, -100, 10, 200, 5)
            c.set_source_rgb(*OFF)
            c.fill()
        c.rectangle(-60, -20, 120, 40)
        c.set_source_rgb(*PNK)
        c.fill()
        for x in range(-50, 60, 20):
            c.rectangle(x, -20, 6, 40)
            c.set_source_rgb(*NAV)
            c.fill()
    elif k == 1:
        sk = [(-60, 100), (-150, -175)] + [p for p in SHUTTLE[2:47]] + [(60, 100)]
        fill_poly(c, sk, WHT)
        for i in range(6):
            xt = lerp(-150, 150, i / 5)
            stroke_poly(c, [(lerp(-50, 50, i / 5), 100), (xt, -178)], NAV, 4)
        for yy in (-30, 40):
            hw = lerp(60, 150, (100 - yy) / 275)
            stroke_poly(c, [(-hw, yy), (hw, yy)], PNK, 6)
        c.rectangle(-60, 100, 120, 18)
        c.set_source_rgb(*PNK)
        c.fill()
        c.arc(0, 118, 60, 0, math.pi)
        c.set_source_rgb(*ORG)
        c.fill()
    else:
        fill_poly(c, BAT[2:] + [BAT[2]], TAN)
        fill_poly(c, [(30, -92), (62, -92), (62, 232), (48, 252), (30, 252)], TAN2)
        fill_poly(c, [(-17, -290), (17, -290), (17, -112), (-17, -112)], NAV)
        for y in range(-275, -120, 26):
            c.rectangle(-17, y, 34, 8)
            c.set_source_rgb(*OFF)
            c.fill()
        c.rectangle(-62, -40, 124, 26)
        c.set_source_rgb(*PNK)
        c.fill()
    c.restore()


def under6(c, tl):
    k = 0 if tl < T6[1] else 1 if tl < T6[2] else 2
    obj6_fill(c, k, tl)


def over6(c, tl):
    text_line(c, [("…any sport.", NAV)], 540, TEXT_Y, 150, tl - 0.30, stagger=0.018)


# ------------------------------------------------------------------ scene 7: staircase to a trophy
_lead7 = bez((-60, 150), (320, 430), (-90, 1110), (120, 1200), 70)
_steps7 = [(120, 1200)]
for i in range(5):
    x, y = 120 + 140 * (i + 1), 1200 - 100 * i
    _steps7 += [(x, y), (x, y - 100)]
_steps7 += [(1000, 700)]
P7 = cat(_lead7, sub(_steps7, 0, 1, 260)[1:])
F7_0 = frac_at(P7, (120, 1200))
CORNERS7 = [(120 + 140 * (i + 1), 1100 - 100 * i) for i in range(5)]
F7_C = [frac_at(P7, p) for p in CORNERS7]
T7_A, T7_B, T7_TROPHY = 0.30, 0.98, 1.00
TROPHY7 = (905, 700)


def head7(tl):
    return lerp(F7_0, 1.0, cl((tl - T7_A) / (T7_B - T7_A)))


def corner_times7():
    return [T7_A + (f - F7_0) / (1 - F7_0) * (T7_B - T7_A) for f in F7_C]


def rib7(tl):
    return sub(P7, 0, head7(tl))


def trophy(c, x, y, s):
    c.save()
    c.translate(x, y)
    c.scale(s, s)
    rrect(c, -78, -30, 156, 30, 8)
    c.set_source_rgb(*NAV)
    c.fill()
    fill_poly(c, [(-22, -30), (22, -30), (14, -86), (-14, -86)], NAV)
    rrect(c, -44, -102, 88, 18, 6)
    c.set_source_rgb(*NAV)
    c.fill()
    c.set_line_width(16)
    c.set_source_rgb(*OFF)
    c.arc_negative(-92, -205, 42, -math.pi * 0.5, -math.pi * 1.5)
    c.stroke()
    c.arc(92, -205, 42, -math.pi * 0.5, math.pi * 0.5)
    c.stroke()
    c.move_to(-100, -262)
    c.line_to(100, -262)
    c.curve_to(100, -150, 54, -104, 0, -102)
    c.curve_to(-54, -104, -100, -150, -100, -262)
    c.close_path()
    c.set_source_rgb(*OFF)
    c.fill()
    pts = []
    for i in range(10):
        r = 34 if i % 2 == 0 else 15
        a = -math.pi / 2 + i * math.pi / 5
        pts.append((r * math.cos(a), -192 + r * math.sin(a)))
    fill_poly(c, pts, PNK)
    c.restore()


def sparkle(c, x, y, r, col):
    pts = []
    for i in range(8):
        rr = r if i % 2 == 0 else r * 0.28
        a = i * math.pi / 4
        pts.append((x + rr * math.cos(a), y + rr * math.sin(a)))
    fill_poly(c, pts, col)


def under7(c, tl):
    tau = tl - T7_TROPHY
    if tau > 0:
        a = eo(tau / 0.3)
        x, y = TROPHY7[0], TROPHY7[1] - 170
        for i in range(12):
            ang = i * math.pi / 6 + tau * 0.8
            r0, r1 = 150, 150 + 230 * a
            c.move_to(x + r0 * math.cos(ang - 0.08), y + r0 * math.sin(ang - 0.08))
            c.line_to(x + r1 * math.cos(ang - 0.13), y + r1 * math.sin(ang - 0.13))
            c.line_to(x + r1 * math.cos(ang + 0.13), y + r1 * math.sin(ang + 0.13))
            c.line_to(x + r0 * math.cos(ang + 0.08), y + r0 * math.sin(ang + 0.08))
            c.close_path()
            c.set_source_rgba(*OFF, 0.38)
            c.fill()


def over7(c, tl):
    for (x, y), tc in zip(CORNERS7, corner_times7()):
        p = pop((tl - tc) / 0.2, 2.6)
        if p > 0:
            circle(c, x, y, 17 * p, OFF)
            circle(c, x, y, 7 * p, NAV)
    s = pop((tl - T7_TROPHY) / 0.28, 2.2)
    if s > 0:
        trophy(c, TROPHY7[0], TROPHY7[1], s)
        tau = tl - T7_TROPHY
        for i, (dx, dy, r) in enumerate(((-150, -300, 26), (140, -330, 20), (165, -150, 16), (-170, -140, 18))):
            q = math.sin(math.pi * cl((tau - 0.08 * i) / 0.45))
            if q > 0:
                sparkle(c, TROPHY7[0] + dx, TROPHY7[1] + dy, r * q * 1.4, OFF)
    text_line(c, [("Every session", NAV)], 540, 1305, 124, tl - 0.40)
    text_line(c, [("counts.", NAV)], 540, 1445, 124, tl - 0.56)


# ------------------------------------------------------------------ scene 8: logo
LOGO_META = json.load(open(os.path.join(WK, "logo.json"))) if os.path.exists(os.path.join(WK, "logo.json")) else None
_LOGO = None


def logo_surface():
    global _LOGO
    if _LOGO is None:
        _LOGO = cairo.ImageSurface.create_from_png(os.path.join(WK, "logo.png"))
    return _LOGO


LW0, LCY0 = 900.0, 860.0


def logo_geom(width, cy):
    lw, lh = LOGO_META["size"]
    s = width / lw
    x0, y0 = 540 - width / 2, cy - lh * s / 2
    rings = [(x0 + r["cx"] * s, y0 + r["cy"] * s, r["r"] * s) for r in LOGO_META["rings"]]
    return s, x0, y0, rings


def _logo_path():
    s, x0, y0, ((c1x, c1y, r1), (c2x, c2y, r2)) = logo_geom(LW0, LCY0)
    a1 = math.pi / 4
    p1 = (c1x + r1 * math.cos(a1), c1y + r1 * math.sin(a1))
    lead = bez((-50, 1330), (90, 1300), (p1[0] - 70, p1[1] + 120), p1, 60)
    ring1 = arc(c1x, c1y, r1, a1, a1 - 2 * math.pi, 160)
    a2 = 3 * math.pi / 4
    ring2 = arc(c2x, c2y, r2, a2, a2 - 2 * math.pi, 160)
    q = ring2[-1]
    ul_y = y0 + LOGO_META["size"][1] * s + 55
    conn = bez(q, (q[0] + 20, q[1] + 60), (q[0] + 90, ul_y), (q[0] + 170, ul_y), 40)
    under = np.c_[np.linspace(q[0] + 170, 990, 80), ul_y + 10 * np.sin(np.linspace(0, math.pi, 80))]
    P = cat(lead, ring1[1:], ring2, conn[1:], under[1:])
    return P, frac_at(P, p1), frac_at(P, q), frac_at(P, (q[0] + 170, ul_y))


P8, F8_0, F8_RINGS, F8_UL = _logo_path() if LOGO_META else (None, 0, 0, 0)
T8_A, T8_B, T8_POP, T8_SLIDE = 0.30, 0.78, 0.78, (0.86, 1.22)


def window8(tl):
    if tl < T8_A:
        return 0.0, F8_0
    if tl < T8_SLIDE[0]:
        return 0.0, lerp(F8_0, F8_RINGS, eio((tl - T8_A) / (T8_B - T8_A)))
    u = eio((tl - T8_SLIDE[0]) / (T8_SLIDE[1] - T8_SLIDE[0]))
    return lerp(0.0, F8_UL - 0.06, u), lerp(F8_RINGS, 1.0, u)


def rib8(tl):
    a, b = window8(tl)
    return sub(P8, a, b)


def draw_logo(c, width, cy, ring_scale=1.0, word_reveal=1.0, alpha=1.0):
    s, x0, y0, rings = logo_geom(width, cy)
    lw, lh = LOGO_META["size"]
    split = LOGO_META["rings_right_edge"]
    surf = logo_surface()
    # rings
    c.save()
    rx, ry = rings[0][0] / 2 + rings[1][0] / 2, rings[0][1]
    c.translate(rx, ry)
    c.scale(ring_scale, ring_scale)
    c.translate(-rx, -ry)
    c.rectangle(x0, y0 - 5, (split + 4) * s, lh * s + 10)
    c.clip()
    c.translate(x0, y0)
    c.scale(s, s)
    c.set_source_surface(surf, 0, 0)
    c.get_source().set_filter(cairo.FILTER_BEST)
    c.paint_with_alpha(alpha)
    c.restore()
    # wordmark, revealed left to right
    if word_reveal > 0:
        c.save()
        wx = x0 + (split + 4) * s
        c.rectangle(wx, y0 - 5, (lw - split) * s * word_reveal, lh * s + 10)
        c.clip()
        c.translate(x0 - (1 - word_reveal) * 60, y0)
        c.scale(s, s)
        c.set_source_surface(surf, 0, 0)
        c.get_source().set_filter(cairo.FILTER_BEST)
        c.paint_with_alpha(alpha)
        c.restore()


def under8(c, tl):
    pass


def over8(c, tl):
    if tl >= T8_POP:
        u = (tl - T8_POP) / 0.28
        rs = 1 + 0.12 * (1 - eob(u, 2.0))
        wr = eo((tl - T8_SLIDE[0]) / 0.30)
        draw_logo(c, LW0, LCY0, rs, wr)


# ------------------------------------------------------------------ scene 9: end card
LOGO_END_W, LOGO_END_CY = 470.0, 330.0
BTN_CY, BTN_W, BTN_H = 1270, 760, 170
PILL_PAD = 22
T9_WRAP, T9_BTN = (0.50, 0.92), 0.92


def _pill(w, h, cx, cy):
    r = h / 2
    top = [(cx, cy - r), (cx + w / 2 - r, cy - r)]
    right = arc(cx + w / 2 - r, cy, r, -math.pi / 2, math.pi / 2, 70)
    bottom = [(cx - w / 2 + r, cy + r)]
    left = arc(cx - w / 2 + r, cy, r, math.pi / 2, 1.5 * math.pi, 70)
    return sub(cat(top, right, bottom, left, [(cx, cy - r)]), 0, 1)


PILL9 = _pill(BTN_W + 2 * PILL_PAD + 24, BTN_H + 2 * PILL_PAD + 24, 540, BTN_CY)


def rib9(tl):
    base = rib8(S[9] - S[8])
    return lerp(base, PILL9, eob((tl - T9_WRAP[0]) / (T9_WRAP[1] - T9_WRAP[0]), 1.3))


def logo9(tl):
    u = eob((tl - 0.05) / 0.42, 1.2)
    return lerp(LW0, LOGO_END_W, u), lerp(LCY0, LOGO_END_CY, u)


def under9(c, tl):
    pass


def over9(c, tl):
    w, cy = logo9(tl)
    draw_logo(c, w, cy)
    text_line(c, [("Join the", NAV)], 540, 565, 136, tl - 0.30)
    text_line(c, [("Athlo ", NAV), ("30x30", PNK)], 540, 705, 136, tl - 0.40)
    text_line(c, [("challenge", NAV)], 540, 845, 136, tl - 0.50)
    text_line(c, [("PRIZES", PNK)], 540, 985, 34, tl - 0.78, face=XB_FACE, track=7, stagger=0.015)
    text_line(c, [("Whoop · Sneakers · Gymshark", NAV)], 540, 1050, 52, tl - 0.84, face=XB_FACE, stagger=0.012)
    s = pop((tl - T9_BTN) / 0.32, 2.0)
    if s > 0:
        for tp in (2.05, 2.95):  # two gentle pulses on the button
            u = (tl - tp) / 0.32
            if 0 < u < 1:
                s *= 1 + 0.05 * math.sin(math.pi * u)
        c.save()
        c.translate(540, BTN_CY)
        c.scale(s, s)
        rrect(c, -BTN_W / 2, -BTN_H / 2, BTN_W, BTN_H, BTN_H / 2)
        c.set_source_rgb(*PNK)
        c.fill()
        c.restore()
        c.save()
        c.translate(0, 0)
        text_line(c, [("Link in bio", OFF)], 540, BTN_CY, 84 * s, 10.0)
        c.restore()


def ribw9(tl):
    return lerp(RIB_W, 22, eo((tl - T9_WRAP[0]) / 0.4))


def cols9(tl, n):
    k = eo((tl - T9_WRAP[1]) / 0.5)
    return rib_colors(n, phase=(tl - T9_WRAP[1]) * 0.55, k=k)


# ------------------------------------------------------------------ scene table
class Scene:
    def __init__(self, bg, wipe, rib, under, over, ribw=None, cols=None):
        self.bg, self.wipe, self.rib, self.under, self.over = bg, wipe, rib, under, over
        self.ribw = ribw or (lambda tl: RIB_W)
        self.cols = cols or (lambda tl, n: rib_colors(n))


SCENES = [
    Scene(OFF, None, rib0, under0, over0),
    Scene(ORG, "down", rib1, under1, over1),
    Scene(PNK, "right", rib2, under2, over2),
    Scene(OFF, "up", rib3, under3, over3),
    Scene(ORG, "left", rib4, under4, over4),
    Scene(PNK, "down", rib5, under5, over5),
    Scene(OFF, "right", rib6, under6, over6, ribw=lambda tl: 26),
    Scene(ORG, "up", rib7, under7, over7),
    Scene(OFF, "left", rib8, under8, over8),
    Scene(OFF, None, rib9, under9, over9, ribw=ribw9, cols=cols9),
]


def scene_at(t):
    for k in range(len(SCENES) - 1, -1, -1):
        if t >= S[k] - 1e-9:
            return k, t - S[k]
    return 0, t


def sweep_p(direction, tl):
    span = H if direction in ("down", "up") else W
    return span * eio((tl - SNAP) / (SWEEP_END - SNAP))


def sweep_line(direction, p):
    if direction == "down":
        P = [(-60, p), (W + 60, p)]
    elif direction == "up":
        P = [(W + 60, H - p), (-60, H - p)]
    elif direction == "right":
        P = [(p, -60), (p, H + 60)]
    else:
        P = [(W - p, H + 60), (W - p, -60)]
    return sub(P, 0, 1)


def reveal_rect(direction, p):
    return {"down": (0, 0, W, p), "up": (0, H - p, W, p), "right": (0, 0, p, H), "left": (W - p, 0, p, H)}[direction]


def ribbon_at(t):
    k, tl = scene_at(t)
    sc = SCENES[k]
    if sc.wipe and tl < ARRIVE:
        old = SCENES[k - 1]
        oend = old.rib(S[k] - S[k - 1])
        if tl < SWEEP_END:
            return lerp(oend, sweep_line(sc.wipe, sweep_p(sc.wipe, tl)), eo(tl / SNAP))
        L = sweep_line(sc.wipe, sweep_p(sc.wipe, SWEEP_END))
        return lerp(L, sc.rib(tl), eob((tl - SWEEP_END) / (ARRIVE - SWEEP_END), 1.3))
    return sc.rib(tl)


def ribbon_width(t):
    k, tl = scene_at(t)
    sc = SCENES[k]
    if sc.wipe and tl < ARRIVE:
        w0 = SCENES[k - 1].ribw(S[k] - S[k - 1])
        return lerp(w0, sc.ribw(tl), cl(tl / ARRIVE))
    return sc.ribw(tl)


def render(t):
    surf = cairo.ImageSurface(cairo.FORMAT_RGB24, W, H)
    c = cairo.Context(surf)
    k, tl = scene_at(t)
    sc = SCENES[k]
    wiping = sc.wipe is not None and tl < SWEEP_END
    if wiping:
        old = SCENES[k - 1]
        otl = S[k] - S[k - 1] + tl
        c.set_source_rgb(*old.bg)
        c.paint()
        old.under(c, otl)
        old.over(c, otl)
        p = sweep_p(sc.wipe, tl)
        c.save()
        c.rectangle(*reveal_rect(sc.wipe, p))
        c.clip()
        c.set_source_rgb(*sc.bg)
        c.paint()
        c.restore()
        # two faint ghosts of the line trailing the sweep, for speed
        if tl > SNAP:
            for lag, a in ((0.022, 0.45), (0.044, 0.2)):
                pg = sweep_p(sc.wipe, tl - lag)
                if abs(p - pg) > 30:
                    draw_ribbon(c, sweep_line(sc.wipe, pg), ribbon_width(t), halo=0, alpha=a)
    else:
        c.set_source_rgb(*sc.bg)
        c.paint()
        sc.under(c, tl)
    P = ribbon_at(t)
    cols = sc.cols(tl, len(P)) if not (sc.wipe and tl < ARRIVE) else rib_colors(len(P))
    draw_ribbon(c, P, ribbon_width(t), cols)
    if not wiping:
        sc.over(c, tl)
    surf.flush()
    return surf


def frame_bytes(i):
    surf = render(i / FPS)
    return bytes(surf.get_data())


# ------------------------------------------------------------------ cues + motion for the sound
def cues():
    out = []
    for i, ch in enumerate("One line."):
        if ch != " ":
            out.append((S[0] + 0.42 + 0.055 * i, "type", {}))
    out += [(S[1] + T1_HIT, "racket", {}), (S[1] + T1_LAND, "ball_pop", {}), (S[1] + T1_END, "ball_pop_small", {})]
    out += [(S[2] + 0.45 + 0.23 * i, "step", {"i": i}) for i in range(4)]
    out += [(S[3] + T3_KICK, "kick_ball", {}), (S[3] + T3_GOAL, "net_swish", {})]
    out += [(S[4] + T4_PULL0, "bow_creak", {"dur": T4_REL - T4_PULL0}), (S[4] + T4_REL, "twang", {}),
            (S[4] + T4_HIT, "arrow_thunk", {})]
    out += [(S[5] + T5_SPLASH, "splash", {})]
    out += [(S[6] + T6[0] + 0.06, "clank", {}), (S[6] + T6[1] + 0.06, "shuttle", {}), (S[6] + T6[2] + 0.06, "bat_crack", {})]
    out += [(S[7] + tc, "step_blip", {"i": i}) for i, tc in enumerate(corner_times7())]
    out += [(S[7] + T7_TROPHY, "trophy", {})]
    out += [(S[8] + T8_POP, "logo_pop", {})]
    out += [(S[8] + 0.15, "riser", {"end": S[9]}), (S[9], "impact", {}), (S[9] + T9_BTN, "button", {})]
    return out


def motion():
    prev = ribbon_at(0)
    rows = []
    for i in range(int(round(DUR * FPS))):
        P = ribbon_at(i / FPS)
        d = np.hypot(*(P - prev).T)
        sp = float(d.mean()) * FPS                       # px/s, average over the ribbon
        wx = float((P[:, 0] * (d + 1e-6)).sum() / (d + 1e-6).sum())
        rows.append({"t": i / FPS, "speed": sp, "x": wx})
        prev = P
    return rows


# ------------------------------------------------------------------ main
STILLS = [(0, 1.20, "1_one_line"), (1, 0.93, "2_padel"), (2, 1.05, "3_run"), (3, 0.98, "4_football"),
          (4, 0.79, "5a_archery_taut"), (4, 1.20, "5b_archery_hit"), (5, 0.82, "6_swim"),
          (6, 0.74, "7a_dumbbell"), (6, 1.09, "7b_shuttlecock"), (6, 1.70, "7c_cricket_bat"),
          (7, 1.30, "8_stairs_trophy"), (8, 1.33, "9_logo"), (9, 3.20, "10_end_card")]


def contact_sheet(paths, out):
    from PIL import Image, ImageDraw, ImageFont
    tw, th, pad, lab = 270, 480, 14, 40
    cols = 7
    rows = (len(paths) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (tw + pad) + pad, rows * (th + pad + lab) + pad), (40, 40, 44))
    d = ImageDraw.Draw(sheet)
    f = ImageFont.truetype("/usr/share/fonts/opentype/inter/Inter-Bold.otf", 20)
    for i, (p, name) in enumerate(paths):
        im = Image.open(p).convert("RGB").resize((tw, th), Image.LANCZOS)
        x, y = pad + (i % cols) * (tw + pad), pad + (i // cols) * (th + pad + lab)
        sheet.paste(im, (x, y + lab))
        d.text((x, y + 8), name, fill=(240, 240, 240), font=f)
    sheet.save(out)


def main():
    args = sys.argv[1:]
    sd = os.path.join(WK, "stills")
    os.makedirs(sd, exist_ok=True)
    if args and args[0] == "--stills":
        paths = []
        for k, tl, name in STILLS:
            t = S[k] + tl
            p = os.path.join(sd, f"{name}_{t:05.2f}s.png")
            render(t).write_to_png(p)
            paths.append((p, f"{name.split('_', 1)[0]}  {t:.2f}s"))
            print(p)
        contact_sheet(paths, os.path.join(sd, "contact_sheet.png"))
        return
    if args and args[0] == "--at":
        for t in map(float, args[1].split(",")):
            p = os.path.join(sd, f"at_{t:05.2f}.png")
            render(t).write_to_png(p)
            print(p)
        return
    json.dump([{"t": t, "name": n, **kw} for t, n, kw in cues()], open(os.path.join(WK, "cues.json"), "w"), indent=1)
    json.dump(motion(), open(os.path.join(WK, "motion.json"), "w"))
    nf = int(round(DUR * FPS))
    out = os.path.join(WK, "picture.mp4")
    ff = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr0",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                           "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
                           "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-profile:v", "high", "-level", "4.2",
                           "-g", "30", "-bf", "2", "-color_primaries", "bt709", "-color_trc", "bt709",
                           "-colorspace", "bt709", "-color_range", "tv", "-movflags", "+faststart", out],
                          stdin=subprocess.PIPE)
    with Pool(os.cpu_count()) as pool:
        for i, buf in enumerate(pool.imap(frame_bytes, range(nf), chunksize=4)):
            ff.stdin.write(buf)
            if i % 60 == 0:
                print(f"frame {i}/{nf}", flush=True)
    ff.stdin.close()
    ff.wait()
    print("wrote", out)


if __name__ == "__main__":
    main()
