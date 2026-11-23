
import math, random, time, sys
import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *

W, H = 1200, 720
TABLES = [(-4, -1), (0, -1), (4, -1), (-4, 3), (0, 3), (4, 3)]
KITCHEN = (0.0, -4.5)
SPEED = 1.8  # robot speed (units / sec)
GST = 0.05

# name, price, 3D model, colour, description
MENU = {
    "Starters": [("Veg Spring Rolls", 120, "fries", (0.9, 0.75, 0.2), "Crispy rolls with sweet chilli dip"),
                 ("Paneer Tikka", 220, "tikka", (0.95, 0.5, 0.1), "Tandoori paneer, onion, capsicum"),
                 ("French Fries", 99, "fries", (0.95, 0.8, 0.2), "Golden salted fries")],
    "Mains": [("Cheese Burger", 180, "burger", (0.85, 0.55, 0.2), "Double cheese, lettuce, tomato"),
              ("Margherita Pizza", 299, "pizza", (0.95, 0.75, 0.35), "Mozzarella, basil, tomato sauce"),
              ("Butter Paneer", 260, "bowl", (0.9, 0.45, 0.1), "Creamy tomato gravy with paneer")],
    "Drinks": [("Cold Coffee", 110, "drink", (0.45, 0.28, 0.15), "Chilled & creamy"),
               ("Mango Shake", 130, "drink", (1.0, 0.75, 0.1), "Fresh alphonso mango"),
               ("Lemon Soda", 70, "drink", (0.75, 1.0, 0.4), "Sweet & salty fizz")],
    "Desserts": [("Ice Cream", 90, "icecream", (1.0, 0.6, 0.75), "Strawberry & vanilla scoops"),
                 ("Choco Brownie", 140, "brownie", (0.35, 0.18, 0.1), "Warm brownie with chocolate")],
}
ITEMS = {i[0]: i for c in MENU.values() for i in c}
CATS = list(MENU.keys())

S = dict(x=0.0, z=5.0, yaw=0.0, pitch=0.0, night=False, ui=None, table=0, screen="menu",
         cat=0, sel=None, carts={i: {} for i in range(6)}, orders=[], last={}, next_id=1001,
         click=False, scan_t=0, method="UPI", tip=0, paying=None, toast=("", 0))
Q = None
ROOM = None
_tex = {}
_fonts = {}

# ----------------------------------------------------------------- helpers
def font(sz):
    if sz not in _fonts:
        _fonts[sz] = pygame.font.Font(None, sz)
    return _fonts[sz]

def get_tex(s, size, color):
    key = (s, size, color)
    if key in _tex:
        return _tex[key]
    if len(_tex) > 400:
        glDeleteTextures([v[0] for v in _tex.values()])
        _tex.clear()
    surf = font(size).render(s, True, color)
    w, h = surf.get_size()
    data = pygame.image.tostring(surf, "RGBA", True)
    tid = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tid)
    glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, data)
    _tex[key] = (tid, w, h)
    return _tex[key]

def cube(w, h, d):
    x, y, z = w / 2, h / 2, d / 2
    faces = [((0, 0, 1), [(-x, -y, z), (x, -y, z), (x, y, z), (-x, y, z)]),
             ((0, 0, -1), [(x, -y, -z), (-x, -y, -z), (-x, y, -z), (x, y, -z)]),
             ((1, 0, 0), [(x, -y, z), (x, -y, -z), (x, y, -z), (x, y, z)]),
             ((-1, 0, 0), [(-x, -y, -z), (-x, -y, z), (-x, y, z), (-x, y, -z)]),
             ((0, 1, 0), [(-x, y, z), (x, y, z), (x, y, -z), (-x, y, -z)]),
             ((0, -1, 0), [(-x, -y, -z), (x, -y, -z), (x, -y, z), (-x, -y, z)])]
    glBegin(GL_QUADS)
    for n, vs in faces:
        glNormal3f(*n)
        for v in vs:
            glVertex3f(*v)
    glEnd()

def box(x, y, z, w, h, d, c):
    glPushMatrix(); glTranslatef(x, y, z); glColor3f(*c); cube(w, h, d); glPopMatrix()

def cyl(x, y, z, r, h, c, r2=None, cap=True):
    """Vertical cylinder / cone, base at y."""
    glPushMatrix(); glTranslatef(x, y, z); glRotatef(-90, 1, 0, 0); glColor3f(*c)
    gluCylinder(Q, r, r if r2 is None else r2, h, 28, 1)
    if cap:
        glTranslatef(0, 0, h); gluDisk(Q, 0, r if r2 is None else r2, 28, 1)
    glPopMatrix()

def sph(x, y, z, r, c, sy=1.0):
    glPushMatrix(); glTranslatef(x, y, z); glScalef(1, sy, 1); glColor3f(*c)
    gluSphere(Q, r, 24, 16); glPopMatrix()

# ----------------------------------------------------------------- QR code (generated pattern)
_qr = {}
def make_qr(seed):
    if seed in _qr:
        return _qr[seed]
    rnd = random.Random(seed * 7919); N = 21
    g = [[rnd.random() < 0.5 for _ in range(N)] for _ in range(N)]
    for ox, oy in ((0, 0), (N - 7, 0), (0, N - 7)):
        for i in range(-1, 8):
            for j in range(-1, 8):
                x, y = ox + i, oy + j
                if 0 <= x < N and 0 <= y < N:
                    d = max(abs(i - 3), abs(j - 3))
                    g[y][x] = (d == 3 or d <= 1)
    _qr[seed] = g
    return g

def qr_3d(seed, size, c):
    g = make_qr(seed); N = len(g); cs = size / N
    glDisable(GL_LIGHTING)
    glColor3f(1, 1, 1)
    glBegin(GL_QUADS)
    for (a, b) in ((-size / 2 - cs, -size / 2 - cs), (size / 2 + cs, size / 2 + cs)):
        pass
    glVertex3f(-size / 2 - cs, -size / 2 - cs, 0.002); glVertex3f(size / 2 + cs, -size / 2 - cs, 0.002)
    glVertex3f(size / 2 + cs, size / 2 + cs, 0.002); glVertex3f(-size / 2 - cs, size / 2 + cs, 0.002)
    glEnd()
    glColor3f(*c)
    glBegin(GL_QUADS)
    for r in range(N):
        for k in range(N):
            if g[r][k]:
                x0 = -size / 2 + k * cs; y0 = size / 2 - (r + 1) * cs
                glVertex3f(x0, y0, 0.004); glVertex3f(x0 + cs, y0, 0.004)
                glVertex3f(x0 + cs, y0 + cs, 0.004); glVertex3f(x0, y0 + cs, 0.004)
    glEnd()
    glEnable(GL_LIGHTING)

# ----------------------------------------------------------------- 2D drawing
def begin2d():
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity(); glOrtho(0, W, H, 0, -1, 1)
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()
    glDisable(GL_DEPTH_TEST); glDisable(GL_LIGHTING)

def end2d():
    glMatrixMode(GL_PROJECTION); glPopMatrix(); glMatrixMode(GL_MODELVIEW); glPopMatrix()
    glEnable(GL_DEPTH_TEST); glEnable(GL_LIGHTING); glDisable(GL_TEXTURE_2D)

def rect(x, y, w, h, c):
    glDisable(GL_TEXTURE_2D)
    glColor4f(c[0] / 255, c[1] / 255, c[2] / 255, c[3] if len(c) > 3 else 1)
    glBegin(GL_QUADS)
    glVertex2f(x, y); glVertex2f(x + w, y); glVertex2f(x + w, y + h); glVertex2f(x, y + h)
    glEnd()

def text(s, x, y, size=26, color=(255, 255, 255), align="l"):
    tid, w, h = get_tex(s, size, color)
    if align == "c": x -= w / 2
    elif align == "r": x -= w
    glEnable(GL_TEXTURE_2D); glBindTexture(GL_TEXTURE_2D, tid); glColor4f(1, 1, 1, 1)
    glBegin(GL_QUADS)
    glTexCoord2f(0, 1); glVertex2f(x, y)
    glTexCoord2f(1, 1); glVertex2f(x + w, y)
    glTexCoord2f(1, 0); glVertex2f(x + w, y + h)
    glTexCoord2f(0, 0); glVertex2f(x, y + h)
    glEnd()
    glDisable(GL_TEXTURE_2D)

def button(x, y, w, h, label, color=(60, 120, 220), size=26, active=False):
    mx, my = pygame.mouse.get_pos()
    hov = x <= mx <= x + w and y <= my <= y + h
    c = tuple(min(255, v + 40) for v in color) if hov else color
    if active: c = (40, 170, 90)
    rect(x, y, w, h, c)
    text(label, x + w / 2, y + h / 2 - size * 0.3, size, align="c")
    if hov and S["click"]:
        S["click"] = False
        return True
    return False

def text3d(s, x, y, z, h, size=48, color=(255, 255, 255)):
    tid, w, hh = get_tex(s, size, color)
    ww = h * w / hh
    glPushMatrix(); glTranslatef(x, y, z); glRotatef(-S["yaw"], 0, 1, 0)
    glDisable(GL_LIGHTING); glEnable(GL_TEXTURE_2D); glBindTexture(GL_TEXTURE_2D, tid); glColor4f(1, 1, 1, 1)
    glBegin(GL_QUADS)
    glTexCoord2f(0, 0); glVertex3f(-ww / 2, -h / 2, 0)
    glTexCoord2f(1, 0); glVertex3f(ww / 2, -h / 2, 0)
    glTexCoord2f(1, 1); glVertex3f(ww / 2, h / 2, 0)
    glTexCoord2f(0, 1); glVertex3f(-ww / 2, h / 2, 0)
    glEnd()
    glDisable(GL_TEXTURE_2D); glEnable(GL_LIGHTING); glPopMatrix()

# ----------------------------------------------------------------- 3D food models (base at y=0)
def draw_food(model, c):
    if model == "burger":
        cyl(0, 0, 0, .6, .15, (.85, .55, .2)); cyl(0, .15, 0, .62, .15, (.35, .17, .08))
        box(0, .32, 0, 1.3, .04, 1.3, (1, .85, .1)); cyl(0, .34, 0, .66, .06, (.3, .75, .2))
        cyl(0, .4, 0, .63, .06, (.85, .15, .1)); sph(0, .46, 0, .62, (.85, .55, .2), .6)
    elif model == "pizza":
        cyl(0, 0, 0, .9, .08, c); cyl(0, .08, 0, .8, .02, (.8, .2, .1))
        for a in range(7):
            ang = a * 0.9
            cyl(.5 * math.cos(ang), .1, .5 * math.sin(ang), .12, .03, (.6, .1, .08))
        cyl(0, .1, 0, .12, .03, (.6, .1, .08))
    elif model == "fries":
        cyl(0, 0, 0, .35, .5, (.85, .1, .1), r2=.5)
        rnd = random.Random(3)
        for _ in range(14):
            box(rnd.uniform(-.25, .25), .55 + rnd.uniform(0, .25), rnd.uniform(-.25, .25), .1, .55, .1, c)
    elif model == "tikka":
        cyl(0, 0, 0, .03, 1.3, (.7, .7, .7))
        for i, col in enumerate([c, (.3, .7, .2), c, (.9, .9, .8), c]):
            box(0, .2 + i * .22, 0, .3, .2, .3, col)
    elif model == "bowl":
        cyl(0, 0, 0, .4, .5, (.95, .95, .95), r2=.7, cap=False); cyl(0, .45, 0, .64, .03, c)
        for a in range(5):
            box(.3 * math.cos(a * 1.3), .5, .3 * math.sin(a * 1.3), .22, .12, .22, (.95, .85, .6))
    elif model == "drink":
        cyl(0, 0, 0, .3, 1.0, (.85, .95, 1), r2=.42, cap=False); cyl(0, 0, 0, .27, .8, c, r2=.38)
        glPushMatrix(); glTranslatef(.1, .6, 0); glRotatef(-12, 0, 0, 1)
        cyl(0, 0, 0, .03, .7, (.9, .1, .1)); glPopMatrix()
    elif model == "icecream":
        cyl(0, 0, 0, 0, .9, (.9, .65, .3), r2=.4, cap=False)
        sph(0, 1.05, 0, .45, c); sph(0, 1.5, 0, .35, (1, .95, .85)); sph(0, 1.85, 0, .08, (.8, .1, .1))
    elif model == "brownie":
        box(0, .18, 0, 1.0, .36, 1.0, c); sph(0, .4, 0, .3, (1, .95, .9), .5); sph(0, .62, 0, .08, (.8, .1, .1))
    cyl(0, -.05 if model != "pizza" else -.05, 0, 1.1 if model != "drink" else .8, .05, (.95, .95, .95)) if False else None

def plate(r):
    cyl(0, -.05, 0, r, .05, (.95, .95, .95))

# ----------------------------------------------------------------- scene geometry
def build_room():
    global ROOM
    ROOM = glGenLists(1)
    glNewList(ROOM, GL_COMPILE)
    glBegin(GL_QUADS); glNormal3f(0, 1, 0)
    for i in range(-8, 8):
        for j in range(-6, 6):
            glColor3f(*((.82, .78, .7) if (i + j) % 2 == 0 else (.35, .28, .24)))
            glVertex3f(i, 0, j); glVertex3f(i, 0, j + 1); glVertex3f(i + 1, 0, j + 1); glVertex3f(i + 1, 0, j)
    glEnd()
    wall = (.93, .88, .8)
    box(0, 1.75, -6.1, 16.4, 3.5, .2, wall); box(0, 1.75, 6.1, 16.4, 3.5, .2, wall)
    box(-8.1, 1.75, 0, .2, 3.5, 12, wall); box(8.1, 1.75, 0, .2, 3.5, 12, wall)
    box(0, 3.55, 0, 16.4, .1, 12.4, (.95, .95, .95))
    # kitchen counter + pass-through
    box(0, .5, -5.5, 9, 1.0, .8, (.35, .22, .12)); box(0, 1.02, -5.5, 9.2, .06, .9, (.75, .75, .78))
    box(-3.5, 1.5, -5.7, 1.2, 1.0, .4, (.6, .6, .65)); box(3.5, 1.5, -5.7, 1.2, 1.0, .4, (.6, .6, .65))
    for (tx, tz) in TABLES:
        cyl(tx, 0, tz, .35, .03, (.2, .2, .2)); cyl(tx, 0, tz, .07, .72, (.7, .7, .72))
        cyl(tx, .72, tz, .9, .06, (.55, .33, .18))
        for dz in (-1.3, 1.3):
            cx, cz = tx, tz + dz
            box(cx, .45, cz, .55, .06, .55, (.7, .2, .2))
            for lx in (-.22, .22):
                for lz in (-.22, .22):
                    box(cx + lx, .22, cz + lz, .05, .44, .05, (.2, .15, .1))
            box(cx, .75, cz + (.26 if dz > 0 else -.26), .55, .55, .05, (.7, .2, .2))
    glEndList()

def set_lights():
    n = S["night"]
    glLightModelfv(GL_LIGHT_MODEL_AMBIENT, (.16, .14, .2, 1) if n else (.5, .5, .5, 1))
    dif = (1.0, .72, .4, 1) if n else (.9, .9, .85, 1)
    for L, p in ((GL_LIGHT0, (-3, 3.2, 1, 1)), (GL_LIGHT1, (3, 3.2, 1, 1))):
        glLightfv(L, GL_POSITION, p); glLightfv(L, GL_DIFFUSE, dif); glLightfv(L, GL_SPECULAR, (.3, .3, .3, 1))
        glLightf(L, GL_LINEAR_ATTENUATION, .035)

def path_for(t):
    tx, tz = TABLES[t]
    ax = -2 if tx < 0 else 2
    sg = 1 if ax > tx else -1
    return [KITCHEN, (ax, KITCHEN[1]), (ax, tz), (tx + sg * 1.3, tz)]

def path_len(p):
    return sum(math.dist(a, b) for a, b in zip(p, p[1:]))

def path_pos(p, d):
    hd = 0
    for a, b in zip(p, p[1:]):
        L = math.dist(a, b)
        hd = math.degrees(math.atan2(b[0] - a[0], b[1] - a[1]))
        if d <= L:
            t = d / L if L else 0
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t), hd
        d -= L
    return p[-1], hd

def draw_robot(x, z, hd, tray):
    glPushMatrix(); glTranslatef(x, 0, z); glRotatef(hd, 0, 1, 0)
    cyl(0, 0, 0, .32, .12, (.15, .15, .18)); cyl(0, .12, 0, .26, .75, (.85, .87, .92), r2=.2)
    sph(0, 1.1, 0, .22, (.95, .95, .98))
    sph(-.08, 1.14, .18, .05, (.1, .4, 1)); sph(.08, 1.14, .18, .05, (.1, .4, 1))
    box(0, .85, .4, .55, .03, .38, (.7, .7, .75))
    if tray:
        glPushMatrix(); glTranslatef(0, .87, .4); glScalef(.2, .2, .2)
        draw_food(tray[0], tray[1]); glPopMatrix()
    glPopMatrix()

def draw_scene(now):
    n = S["night"]
    glClearColor(.02, .02, .05, 1) if n else glClearColor(.5, .7, .9, 1)
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glMatrixMode(GL_PROJECTION); glLoadIdentity(); gluPerspective(70, W / H, .05, 100)
    glMatrixMode(GL_MODELVIEW); glLoadIdentity()
    glRotatef(S["pitch"], 1, 0, 0); glRotatef(S["yaw"], 0, 1, 0); glTranslatef(-S["x"], -1.6, -S["z"])
    set_lights()
    glCallList(ROOM)
    # windows
    glDisable(GL_LIGHTING); glColor3f(*((.05, .07, .15) if n else (.55, .8, 1)))
    glBegin(GL_QUADS)
    for sx in (-7.98, 7.98):
        for zc in (-3, 0, 3):
            glVertex3f(sx, 1.2, zc - .9); glVertex3f(sx, 1.2, zc + .9)
            glVertex3f(sx, 2.7, zc + .9); glVertex3f(sx, 2.7, zc - .9)
    glEnd(); glEnable(GL_LIGHTING)
    text3d("SMART KITCHEN", 0, 2.7, -5.85, .5, 56, (255, 210, 90))
    near = nearest_table()
    for i, (tx, tz) in enumerate(TABLES):
        # hanging lamp
        cyl(tx, 3.0, tz, .02, .55, (.3, .3, .3)); cyl(tx, 2.75, tz, .12, .3, (.9, .6, .2), r2=.5, cap=False)
        glDisable(GL_LIGHTING); sph(tx, 2.78, tz, .13, (1, .95, .7)); glEnable(GL_LIGHTING)
        text3d("TABLE %d" % (i + 1), tx, 2.2, tz, .28, 48, (255, 255, 255))
        # QR card on table
        glPushMatrix(); glTranslatef(tx, .78, tz); glRotatef(-60, 1, 0, 0)
        glColor3f(*((.1, .8, .3) if i == near else (.15, .15, .2))); cube(.5, .5, .02)
        glTranslatef(0, 0, .011); qr_3d(i + 1, .38, (0, 0, 0)); glPopMatrix()
        # served dishes
        o = S["last"].get(i)
        if o and o["stage"] == 3:
            names = list(o["items"].keys())[:4]
            for k, nm in enumerate(names):
                a = k * 6.283 / max(1, len(names)) + .6
                glPushMatrix(); glTranslatef(tx + .5 * math.cos(a), .78, tz + .5 * math.sin(a)); glScalef(.16, .16, .16)
                plate(1.1); draw_food(ITEMS[nm][2], ITEMS[nm][3]); glPopMatrix()
    # robots
    for o in S["orders"]:
        d = (o["e"] - 13) * SPEED
        L = o["L"]; p = path_for(o["table"])
        if 0 <= d <= L:
            (x, z), hd = path_pos(p, d)
            nm = list(o["items"].keys())[0]
            draw_robot(x, z, hd, (ITEMS[nm][2], ITEMS[nm][3]))
        elif L < d <= 2 * L:
            (x, z), hd = path_pos(p[::-1], d - L)
            draw_robot(x, z, hd, None)
    if not any(0 <= (o["e"] - 13) * SPEED <= 2 * o["L"] for o in S["orders"]):
        draw_robot(KITCHEN[0], KITCHEN[1], 180 + 20 * math.sin(now), None)

def nearest_table():
    best, bd = None, 2.8
    for i, (tx, tz) in enumerate(TABLES):
        d = math.dist((S["x"], S["z"]), (tx, tz))
        if d < bd: best, bd = i, d
    return best

# ----------------------------------------------------------------- business logic
def totals(cart, tip=0):
    sub = sum(ITEMS[n][1] * q for n, q in cart.items())
    gst = round(sub * GST, 2); tp = round(sub * tip / 100, 2)
    return sub, gst, tp, round(sub + gst + tp, 2)

def cart_count(t):
    return sum(S["carts"][t].values())

def place_order(t):
    sub, gst, tp, total = totals(S["carts"][t], S["tip"])
    o = dict(id="ORD-%d" % S["next_id"], table=t, items=dict(S["carts"][t]), sub=sub, gst=gst, tip=tp,
             total=total, method=S["method"], t0=time.time(), stage=0, e=0, L=path_len(path_for(t)))
    S["next_id"] += 1; S["orders"].append(o); S["last"][t] = o; S["carts"][t] = {}

STAGES = ["Order Received", "Cooking in Kitchen", "On the Way", "Served"]
def update_orders(now):
    for o in S["orders"]:
        e = now - o["t0"]; o["e"] = e
        st = 0 if e < 3 else 1 if e < 13 else 2 if e < 13 + o["L"] / SPEED else 3
        if st != o["stage"]:
            o["stage"] = st
            if st == 3:
                S["toast"] = ("%s served at Table %d. Enjoy your meal!" % (o["id"], o["table"] + 1), now + 5)
            elif st == 1:
                S["toast"] = ("%s is being cooked..." % o["id"], now + 3)

# ----------------------------------------------------------------- UI
PX, PY, PW, PH = 60, 40, W - 120, H - 80

def preview3d(item, x, y, w, h, now):
    vy = H - y - h
    glViewport(x, vy, w, h)
    glEnable(GL_SCISSOR_TEST); glScissor(x, vy, w, h); glClear(GL_DEPTH_BUFFER_BIT); glDisable(GL_SCISSOR_TEST)
    glMatrixMode(GL_PROJECTION); glLoadIdentity(); gluPerspective(40, w / h, .1, 50)
    glMatrixMode(GL_MODELVIEW); glLoadIdentity(); gluLookAt(0, 1.6, 4.2, 0, .6, 0, 0, 1, 0)
    glLightModelfv(GL_LIGHT_MODEL_AMBIENT, (.45, .45, .45, 1))
    glDisable(GL_LIGHT1); glLightfv(GL_LIGHT0, GL_POSITION, (2, 4, 4, 1)); glLightfv(GL_LIGHT0, GL_DIFFUSE, (1, 1, 1, 1))
    glRotatef(now * 40 % 360, 0, 1, 0)
    plate(1.15); draw_food(item[2], item[3])
    glEnable(GL_LIGHT1); glViewport(0, 0, W, H)

def ui_panel_bg():
    begin2d()
    rect(0, 0, W, H, (0, 0, 0, .7)); rect(PX, PY, PW, PH, (24, 26, 40, .97))
    rect(PX, PY, PW, 60, (38, 42, 66))
    end2d()

def ui_header(t):
    text("Table %d  |  Scan & Order" % (t + 1), PX + 20, PY + 18, 34, (255, 215, 100))
    bx = PX + PW - 20
    if button(bx - 40, PY + 12, 40, 36, "X", (190, 60, 60)): close_ui()
    if button(bx - 160, PY + 12, 110, 36, "Track", (70, 90, 160), 24, S["screen"] == "track"): S["screen"] = "track"
    if button(bx - 300, PY + 12, 130, 36, "Cart (%d)" % cart_count(t), (70, 90, 160), 24, S["screen"] in ("cart", "pay")): S["screen"] = "cart"
    if button(bx - 420, PY + 12, 110, 36, "Menu", (70, 90, 160), 24, S["screen"] == "menu"): S["screen"] = "menu"

def screen_scan(t, now):
    begin2d()
    cx, cy, s = W / 2, H / 2, 300
    rect(cx - s / 2, cy - s / 2, s, s, (255, 255, 255))
    g = make_qr(t + 1); N = len(g); cs = (s - 20) / N
    for r in range(N):
        for k in range(N):
            if g[r][k]: rect(cx - s / 2 + 10 + k * cs, cy - s / 2 + 10 + r * cs, cs, cs, (0, 0, 0))
    ly = cy - s / 2 + (s - 4) * (0.5 + 0.5 * math.sin((now - S["scan_t"]) * 5))
    rect(cx - s / 2 - 20, ly, s + 40, 4, (40, 255, 120, .9))
    for (a, b) in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        rect(cx + a * (s / 2 + 18) - (0 if a < 0 else 40), cy + b * (s / 2 + 18) - (0 if b < 0 else 6), 40, 6, (40, 255, 120))
        rect(cx + a * (s / 2 + 18) - (0 if a < 0 else 6), cy + b * (s / 2 + 18) - (0 if b < 0 else 40), 6, 40, (40, 255, 120))
    text("Scanning QR code on Table %d ..." % (t + 1), cx, cy + s / 2 + 40, 38, (255, 255, 255), "c")
    end2d()
    if now - S["scan_t"] > 1.8:
        S["screen"] = "menu"

def screen_menu(t, now):
    items = MENU[CATS[S["cat"]]]
    for i, cname in enumerate(CATS):
        if button(PX + 20 + i * 135, PY + 80, 125, 38, cname, (60, 80, 140), 24, i == S["cat"]):
            S["cat"] = i; S["sel"] = None
    if S["sel"] is None or S["sel"] not in [i[0] for i in items]:
        S["sel"] = items[0][0]
    mx, my = pygame.mouse.get_pos()
    for k, it in enumerate(items):
        y = PY + 135 + k * 80
        if PX + 20 <= mx <= PX + 600 and y <= my <= y + 72: S["sel"] = it[0]
        rect(PX + 20, y, 580, 72, (60, 70, 110) if S["sel"] == it[0] else (40, 44, 70))
        text(it[0], PX + 36, y + 10, 32); text(it[4], PX + 36, y + 42, 22, (170, 180, 210))
        text("Rs. %d" % it[1], PX + 440, y + 22, 30, (255, 215, 100), "r")
        q = S["carts"][t].get(it[0], 0)
        if q: text("x%d" % q, PX + 465, y + 24, 28, (120, 255, 150))
        if button(PX + 510, y + 18, 80, 36, "Add", (40, 150, 80), 26):
            S["carts"][t][it[0]] = q + 1
    sub, gst, tp, total = totals(S["carts"][t])
    if button(PX + 20, PY + PH - 70, 580, 50, "View Cart  (%d items)   Rs. %.2f" % (cart_count(t), total), (200, 120, 30), 30):
        S["screen"] = "cart"
    rect(PX + 640, PY + 135, 440, 420, (14, 16, 28))
    sel = ITEMS[S["sel"]]
    text(sel[0], PX + 860, PY + 570 - 14, 34, (255, 255, 255), "c")
    return (sel, PX + 640, PY + 135, 440, 360)

def screen_cart(t, now):
    cart = S["carts"][t]
    text("Your Cart", PX + 30, PY + 85, 38, (255, 215, 100))
    y = PY + 135
    if not cart: text("Cart is empty. Open the Menu tab and add some food!", PX + 30, y + 20, 30, (200, 200, 220))
    for nm, q in list(cart.items()):
        rect(PX + 30, y, 700, 56, (40, 44, 70))
        text(nm, PX + 46, y + 14, 30); text("Rs. %d" % (ITEMS[nm][1] * q), PX + 715, y + 16, 30, (255, 215, 100), "r")
        if button(PX + 480, y + 10, 36, 36, "-", (170, 60, 60), 32):
            cart[nm] -= 1
            if cart[nm] <= 0: del cart[nm]
            break
        text(str(q), PX + 540, y + 14, 32, align="c")
        if button(PX + 560, y + 10, 36, 36, "+", (40, 150, 80), 32): cart[nm] += 1
        y += 64
    sub, gst, tp, total = totals(cart)
    rect(PX + 780, PY + 135, 300, 260, (40, 44, 70))
    text("Subtotal", PX + 800, PY + 155, 28); text("Rs. %.2f" % sub, PX + 1060, PY + 155, 28, align="r")
    text("GST 5%", PX + 800, PY + 195, 28); text("Rs. %.2f" % gst, PX + 1060, PY + 195, 28, align="r")
    text("Total", PX + 800, PY + 260, 38, (255, 215, 100)); text("Rs. %.2f" % total, PX + 1060, PY + 260, 38, (255, 215, 100), "r")
    if cart and button(PX + 780, PY + 420, 300, 56, "Checkout", (40, 150, 80), 34): S["screen"] = "pay"; S["paying"] = None
    if button(PX + 780, PY + 490, 300, 46, "Back to Menu", (70, 90, 160), 28): S["screen"] = "menu"

def screen_pay(t, now):
    cart = S["carts"][t]
    text("Payment", PX + 30, PY + 85, 38, (255, 215, 100))
    for i, m in enumerate(("UPI", "Card", "Cash")):
        if button(PX + 30 + i * 150, PY + 140, 140, 48, m, (70, 90, 160), 30, S["method"] == m): S["method"] = m
    text("Add a tip for the staff:", PX + 30, PY + 215, 28)
    for i, tp in enumerate((0, 5, 10, 15)):
        if button(PX + 30 + i * 110, PY + 250, 100, 42, "%d%%" % tp, (70, 90, 160), 28, S["tip"] == tp): S["tip"] = tp
    sub, gst, tp, total = totals(cart, S["tip"])
    rect(PX + 30, PY + 320, 600, 210, (40, 44, 70))
    for k, (lab, v) in enumerate((("Subtotal", sub), ("GST 5%", gst), ("Tip", tp))):
        text(lab, PX + 50, PY + 335 + k * 36, 28); text("Rs. %.2f" % v, PX + 610, PY + 335 + k * 36, 28, align="r")
    text("TOTAL", PX + 50, PY + 455, 40, (255, 215, 100)); text("Rs. %.2f" % total, PX + 610, PY + 455, 40, (255, 215, 100), "r")
    # method panel
    rect(PX + 680, PY + 140, 400, 390, (14, 16, 28))
    if S["method"] == "UPI":
        text("Scan to pay with any UPI app", PX + 880, PY + 155, 26, align="c")
        g = make_qr(50 + t); N = len(g); cs = 12
        ox, oy = PX + 880 - N * cs / 2, PY + 200
        rect(ox - 8, oy - 8, N * cs + 16, N * cs + 16, (255, 255, 255))
        for r in range(N):
            for k in range(N):
                if g[r][k]: rect(ox + k * cs, oy + r * cs, cs, cs, (0, 0, 0))
    elif S["method"] == "Card":
        rect(PX + 710, PY + 190, 340, 190, (60, 90, 200))
        text("4242  4242  4242  4242", PX + 730, PY + 280, 34); text("DEMO CARD   12/30", PX + 730, PY + 340, 26)
    else:
        text("Pay cash to the waiter", PX + 880, PY + 260, 32, align="c")
        text("when your food is served.", PX + 880, PY + 300, 28, (180, 190, 210), "c")
    if S["paying"]:
        text("Processing payment...", PX + 880, PY + 450, 30, (255, 215, 100), "c")
        if now - S["paying"] > 1.8:
            place_order(t); S["paying"] = None; S["screen"] = "track"
    elif cart:
        if button(PX + 700, PY + 460, 360, 54, "Pay Rs. %.2f" % total, (40, 150, 80), 32): S["paying"] = now
    if button(PX + 30, PY + PH - 60, 160, 40, "< Back", (70, 90, 160), 26): S["screen"] = "cart"

def screen_track(t, now):
    o = S["last"].get(t)
    if not o:
        text("No active order for this table yet.", PX + 30, PY + 100, 34)
        if button(PX + 30, PY + 160, 240, 50, "Order Now", (40, 150, 80), 30): S["screen"] = "menu"
        return
    text("Order %s  |  Table %d" % (o["id"], t + 1), PX + 30, PY + 80, 36, (255, 215, 100))
    # status stepper
    for i, st in enumerate(STAGES):
        cx = PX + 110 + i * 230
        col = (40, 190, 100) if i <= o["stage"] else (80, 80, 100)
        if i: rect(cx - 230 + 18, PY + 146, 230 - 36, 6, (40, 190, 100) if i <= o["stage"] else (80, 80, 100))
        rect(cx - 18, PY + 132, 36, 36, col)
        text(str(i + 1), cx, PY + 140, 28, align="c"); text(st, cx, PY + 180, 24, align="c")
    eta = max(0, 13 + o["L"] / SPEED - o["e"])
    text("Served! Enjoy your meal." if o["stage"] == 3 else "Estimated time: %d sec" % eta, PX + 30, PY + 225, 28, (120, 255, 150))
    rect(PX + 30, PY + 270, 560, 270, (40, 44, 70))
    text("ORDER DETAILS", PX + 50, PY + 282, 26, (160, 170, 210))
    y = PY + 315
    for nm, q in o["items"].items():
        text("%s  x%d" % (nm, q), PX + 50, y, 26); text("Rs. %d" % (ITEMS[nm][1] * q), PX + 570, y, 26, align="r"); y += 30
    rect(PX + 620, PY + 270, 460, 270, (40, 44, 70))
    for k, (lab, v) in enumerate((("Subtotal", o["sub"]), ("GST 5%", o["gst"]), ("Tip", o["tip"]))):
        text(lab, PX + 640, PY + 290 + k * 34, 26); text("Rs. %.2f" % v, PX + 1060, PY + 290 + k * 34, 26, align="r")
    text("TOTAL", PX + 640, PY + 400, 38, (255, 215, 100)); text("Rs. %.2f" % o["total"], PX + 1060, PY + 400, 38, (255, 215, 100), "r")
    text("Paid via: %s" % o["method"] + ("  (pay at table)" if o["method"] == "Cash" else "  (PAID)"), PX + 640, PY + 460, 26, (120, 255, 150))
    if o["stage"] == 3 and button(PX + 640, PY + 495, 220, 36, "Order more", (200, 120, 30), 26): S["screen"] = "menu"
    if button(PX + 880, PY + 495, 200, 36, "Look at robot", (70, 90, 160), 24): close_ui()

def ui_draw(now):
    t = S["table"]
    ui_panel_bg()
    prev = None
    begin2d()
    scr = S["screen"]
    if scr == "scan": screen_scan(t, now)
    else:
        ui_header(t)
        if scr == "menu": prev = screen_menu(t, now)
        elif scr == "cart": screen_cart(t, now)
        elif scr == "pay": screen_pay(t, now)
        elif scr == "track": screen_track(t, now)
    end2d()
    if prev:  # 3D preview drawn above panel backgrounds
        preview3d(prev[0], prev[1], prev[2], prev[3], prev[4], now)
        begin2d()
        text(prev[0][4], prev[1] + 220, prev[2] + 395, 22, (170, 180, 210), "c")
        end2d()

def open_ui(t, now):
    S["ui"] = True; S["table"] = t; S["screen"] = "scan"; S["scan_t"] = now
    pygame.mouse.set_visible(True); pygame.event.set_grab(False)

def close_ui():
    S["ui"] = None
    pygame.mouse.set_visible(False); pygame.event.set_grab(True); pygame.mouse.get_rel()

def hud(now):
    begin2d()
    text("WASD move | Mouse look | E scan QR | N day/night | ESC quit", 14, 12, 24, (255, 255, 255))
    y = 40
    for o in S["orders"]:
        text("Table %d  %s: %s" % (o["table"] + 1, o["id"], STAGES[o["stage"]]), 14, y, 24, (255, 215, 100)); y += 24
    n = nearest_table()
    if n is not None:
        rect(W / 2 - 230, H - 90, 460, 46, (0, 0, 0, .65))
        text("Press  E  to scan QR on Table %d" % (n + 1), W / 2, H - 80, 32, (120, 255, 150), "c")
    rect(W / 2 - 3, H / 2 - 3, 6, 6, (255, 255, 255, .8))
    if now < S["toast"][1]:
        rect(W / 2 - 330, 60, 660, 44, (30, 150, 80, .9)); text(S["toast"][0], W / 2, 70, 30, align="c")
    end2d()

# ----------------------------------------------------------------- main
def main():
    global Q
    pygame.init()
    pygame.display.set_mode((W, H), DOUBLEBUF | OPENGL)
    pygame.display.set_caption("Smart Restaurant - QR Ordering (OpenGL)")
    Q = gluNewQuadric(); gluQuadricNormals(Q, GLU_SMOOTH)
    glViewport(0, 0, W, H)
    glEnable(GL_DEPTH_TEST); glEnable(GL_LIGHTING); glEnable(GL_LIGHT0); glEnable(GL_LIGHT1)
    glEnable(GL_COLOR_MATERIAL); glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
    glEnable(GL_NORMALIZE); glEnable(GL_BLEND); glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glMaterialfv(GL_FRONT_AND_BACK, GL_SPECULAR, (.2, .2, .2, 1)); glMaterialf(GL_FRONT_AND_BACK, GL_SHININESS, 24)
    build_room()
    close_ui()
    clock = pygame.time.Clock()
    while True:
        dt = clock.tick(60) / 1000.0
        now = time.time()
        S["click"] = False
        for e in pygame.event.get():
            if e.type == QUIT: pygame.quit(); sys.exit()
            if e.type == KEYDOWN:
                if e.key == K_ESCAPE:
                    if S["ui"]: close_ui()
                    else: pygame.quit(); sys.exit()
                elif e.key == K_n: S["night"] = not S["night"]
                elif e.key == K_e and not S["ui"]:
                    n = nearest_table()
                    if n is not None: open_ui(n, now)
            if e.type == MOUSEBUTTONDOWN and e.button == 1 and S["ui"]: S["click"] = True
        update_orders(now)
        if not S["ui"]:
            dx, dy = pygame.mouse.get_rel()
            S["yaw"] += dx * .12; S["pitch"] = max(-80, min(80, S["pitch"] + dy * .12))
            k = pygame.key.get_pressed(); yaw = math.radians(S["yaw"])
            fx, fz, rx, rz = math.sin(yaw), -math.cos(yaw), math.cos(yaw), math.sin(yaw)
            mx = mz = 0
            if k[K_w]: mx += fx; mz += fz
            if k[K_s]: mx -= fx; mz -= fz
            if k[K_d]: mx += rx; mz += rz
            if k[K_a]: mx -= rx; mz -= rz
            l = math.hypot(mx, mz)
            if l:
                S["x"] += mx / l * 3.5 * dt; S["z"] += mz / l * 3.5 * dt
            for (tx, tz) in TABLES:  # table collision
                d = math.dist((S["x"], S["z"]), (tx, tz))
                if d < 1.1:
                    S["x"] = tx + (S["x"] - tx) / (d or 1) * 1.1; S["z"] = tz + (S["z"] - tz) / (d or 1) * 1.1
            S["x"] = max(-7.5, min(7.5, S["x"])); S["z"] = max(-4.8, min(5.5, S["z"]))
        draw_scene(now)
        if S["ui"]: ui_draw(now)
        else: hud(now)
        pygame.display.flip()

if __name__ == "__main__":
    main()
