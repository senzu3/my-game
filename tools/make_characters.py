# ひっさん モンスターバトル: モンスター40体と勇者5段階を Blender で組み立てて img/ に書き出す
#
# つかいかた（Blender の Python コンソールなどで）:
#   ns = {'__file__': '/path/to/my-game/tools/make_characters.py'}
#   exec(open(ns['__file__']).read(), ns)
#   ns['do_monsters']([f'{k}-{i}' for k in ns['KEYS'] for i in range(5)])
#   ns['do_heroes'](range(5))
# いまの シーンは さわらず、hissan_chars という べつの シーンで つくる。
# モンスターの パーツの きまりは hissan.html の monsterDef と おなじ。
import bpy, bmesh, math, os, colorsys
from mathutils import Vector, Quaternion

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'img')
SCENE = 'hissan_chars'

KEYS = ['mul1', 'mul2', 'mul3', 'mul4', 'div1', 'div2', 'div3', 'div4']
HUES = {'mul1': 120, 'mul2': 172, 'mul3': 212, 'mul4': 262, 'div1': 28, 'div2': 48, 'div3': 4, 'div4': 322}
SHAPES = ['blob', 'round', 'ghost', 'block', 'tall']
HORNS = ['none', 'two', 'ears', 'one', 'antenna']
MOUTHS = ['smile', 'fang', 'o', 'zig']
TOPS = {'blob': 30, 'round': 47, 'ghost': 30, 'block': 45, 'tall': 34}


def monster_def(key, k):  # hissan.html の monsterDef と同じ きまり
    li = KEYS.index(key)
    base = 0 if k == 4 else k
    return dict(id=f'{key}-{k}', boss=k == 4,
                shape=SHAPES[(base + li) % 5], horn=HORNS[(base * 2 + li) % 5],
                mouth=MOUTHS[(base + li * 3) % 4], eyes=[2, 1, 3, 2][(base + li) % 4],
                wings=k == 4 or (base + li) % 3 == 2, spots=(base + li) % 2 == 0,
                hue=HUES[key] + [0, 16, -16, 30][base])


# ---------- 色・マテリアル ----------
def lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hsl(h, s, l):
    r, g, b = colorsys.hls_to_rgb((h % 360) / 360, l, s)
    return (lin(r), lin(g), lin(b), 1)


def hexc(h):
    h = h.lstrip('#')
    return tuple(lin(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4)) + (1,)


def mat(name, color, rough=0.45, metal=0.0, coat=0.0, sss=0.0, bump=0.0, emit=0.0):
    m = bpy.data.materials.get(name)
    if m:
        bpy.data.materials.remove(m)
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    p = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if p is None:
        p = nt.nodes.new('ShaderNodeBsdfPrincipled')
        out = next((n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'), None) or nt.nodes.new('ShaderNodeOutputMaterial')
        nt.links.new(p.outputs['BSDF'], out.inputs['Surface'])
    p.inputs['Base Color'].default_value = color
    p.inputs['Roughness'].default_value = rough
    p.inputs['Metallic'].default_value = metal
    p.inputs['Coat Weight'].default_value = coat
    p.inputs['Subsurface Weight'].default_value = sss
    p.inputs['Subsurface Radius'].default_value = (0.3, 0.15, 0.1)
    p.inputs['Subsurface Scale'].default_value = 0.08
    if emit:
        p.inputs['Emission Color'].default_value = color
        p.inputs['Emission Strength'].default_value = emit
    if bump:
        tex = nt.nodes.new('ShaderNodeTexNoise')
        tex.inputs['Scale'].default_value = 28
        tex.inputs['Detail'].default_value = 6
        bn = nt.nodes.new('ShaderNodeBump')
        bn.inputs['Strength'].default_value = bump
        bn.inputs['Distance'].default_value = 0.02
        nt.links.new(tex.outputs['Fac'], bn.inputs['Height'])
        nt.links.new(bn.outputs['Normal'], p.inputs['Normal'])
    m['hissan'] = True
    return m


# ---------- シーン ----------
def setup_scene():
    sc = bpy.data.scenes.get(SCENE) or bpy.data.scenes.new(SCENE)
    for w in bpy.context.window_manager.windows:
        w.scene = sc
    r = sc.render
    r.engine = 'BLENDER_EEVEE'
    r.film_transparent = True
    r.image_settings.file_format = 'WEBP'
    r.image_settings.color_mode = 'RGBA'
    r.image_settings.quality = 88
    r.resolution_percentage = 100
    sc.eevee.taa_render_samples = 64
    try:
        sc.eevee.use_raytracing = True
        sc.eevee.use_shadows = True
    except Exception:
        pass
    sc.view_settings.view_transform = 'Standard'
    sc.view_settings.look = 'None'
    world = sc.world or bpy.data.worlds.new('hissan_world')
    sc.world = world
    world.use_nodes = True
    nt = world.node_tree
    bg = next((n for n in nt.nodes if n.type == 'BACKGROUND'), None)
    if bg is None:
        bg = nt.nodes.new('ShaderNodeBackground')
        out = next((n for n in nt.nodes if n.type == 'OUTPUT_WORLD'), None) or nt.nodes.new('ShaderNodeOutputWorld')
        nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
    bg.inputs['Color'].default_value = (0.75, 0.8, 0.9, 1)
    bg.inputs['Strength'].default_value = 0.7
    # ライト
    for name, loc, energy, size, color in [
        ('key', (-4.5, -7, 7.5), 900, 4.0, (1, 0.96, 0.9)),
        ('fill', (6, -5, 3), 350, 5.0, (0.85, 0.9, 1)),
        ('rim', (1.5, 6, 6.5), 700, 3.0, (1, 1, 1)),
    ]:
        ob = bpy.data.objects.get('hissan_' + name)
        if not ob:
            ld = bpy.data.lights.new('hissan_' + name, 'AREA')
            ob = bpy.data.objects.new('hissan_' + name, ld)
            sc.collection.objects.link(ob)
        ob.data.energy = energy
        ob.data.size = size
        ob.data.color = color
        ob.location = loc
        look_at(ob, Vector((0, 0, 1.8)))
    cam = bpy.data.objects.get('hissan_cam')
    if not cam:
        cd = bpy.data.cameras.new('hissan_cam')
        cam = bpy.data.objects.new('hissan_cam', cd)
        sc.collection.objects.link(cam)
    sc.camera = cam
    return sc


def look_at(ob, target):
    d = target - Vector(ob.location)
    ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


def frame_camera(sc, kind):
    cam = sc.camera
    cam.data.lens = 85
    if kind == 'monster':
        sc.render.resolution_x = sc.render.resolution_y = 400
        cam.data.sensor_fit = 'AUTO'
        cam.location = (0, -10.2, 2.9)
        look_at(cam, Vector((0, 0, 2.0)))
    else:
        sc.render.resolution_x, sc.render.resolution_y = 300, 400
        cam.data.sensor_fit = 'VERTICAL'
        cam.data.sensor_height = 32
        cam.location = (0, -9.0, 2.35)
        look_at(cam, Vector((0, 0, 1.6)))


def clear_parts(sc):
    for ob in list(sc.objects):
        if ob.get('hissan_part'):
            data = ob.data
            bpy.data.objects.remove(ob, do_unlink=True)
            if data is not None and data.users == 0:
                if isinstance(data, bpy.types.Mesh):
                    bpy.data.meshes.remove(data)
                elif isinstance(data, bpy.types.Curve):
                    bpy.data.curves.remove(data)
    for m in list(bpy.data.materials):
        if m.get('hissan') and m.users == 0:
            bpy.data.materials.remove(m)


# ---------- かたちを つくる 道具 ----------
def link(sc, name, data, material=None):
    ob = bpy.data.objects.new(name, data)
    ob['hissan_part'] = True
    sc.collection.objects.link(ob)
    if material is not None:
        ob.data.materials.append(material)
    return ob


def smooth(me):
    me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
    me.update()


def sphere_mesh(name, seg=64, ring=32, fn=None):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=ring, radius=1)
    if fn:
        for v in bm.verts:
            v.co = Vector(fn(v.co.copy()))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    smooth(me)
    return me


def ellipsoid(sc, name, center, scale, material, rot=None):
    ob = link(sc, name, sphere_mesh(name, 40, 20), material)
    ob.location = center
    ob.scale = scale
    if rot is not None:
        ob.rotation_mode = 'QUATERNION'
        ob.rotation_quaternion = rot
    return ob


def cone(sc, name, base, tip, r, material, flat=1.0):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=32, radius1=r, radius2=0.0, depth=1.0)
    for v in bm.verts:
        v.co.z += 0.5
        v.co.y *= flat
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    smooth(me)
    ob = link(sc, name, me, material)
    base, tip = Vector(base), Vector(tip)
    d = tip - base
    ob.location = base
    ob.scale = (1, 1, d.length)
    ob.rotation_mode = 'QUATERNION'
    ob.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d.normalized())
    sub = ob.modifiers.new('sub', 'SUBSURF')
    sub.levels = sub.render_levels = 1
    return ob


def tube(sc, name, pts, radius, material):
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = radius
    cu.bevel_resolution = 6
    cu.use_fill_caps = True
    sp = cu.splines.new('POLY')
    sp.points.add(len(pts) - 1)
    for p, q in zip(sp.points, pts):
        p.co = (q[0], q[1], q[2], 1)
    return link(sc, name, cu, material)


def prism(sc, name, pts2d, thick, material, plane='XZ'):
    """2Dの かたちを あつみのある いたに する（はね・たてなど）"""
    bm = bmesh.new()
    vs = [bm.verts.new((x, 0, z)) for x, z in pts2d]
    f = bm.faces.new(vs)
    ex = bmesh.ops.extrude_face_region(bm, geom=[f])
    for v in [e for e in ex['geom'] if isinstance(e, bmesh.types.BMVert)]:
        v.co.y += thick
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = link(sc, name, me, material)
    bev = ob.modifiers.new('bev', 'BEVEL')
    bev.width = thick * 0.45
    bev.segments = 4
    return ob


def bezier_q(p0, p1, p2, n=12):
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
             (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]) for t in [i / n for i in range(n + 1)]]


def bezier_c(p0, p1, p2, p3, n=10):
    out = []
    for i in range(n + 1):
        t = i / n
        a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3
        out.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return out


# SVG（200×200、yは下むき）→ 3D（x よこ、z たて、じめん z=0）
def sx(x):
    return (x - 100) / 50


def sz(y):
    return (190 - y) / 50


class Surface:
    def __init__(self, ob):
        self.ob = ob
        bpy.context.view_layer.update()
        self.dg = bpy.context.evaluated_depsgraph_get()
        self.dz = 0.0  # かおの パーツを うえに ずらす りょう

    def cast(self, origin, direction):
        ev = self.ob.evaluated_get(self.dg)
        ok, loc, nor, _ = ev.ray_cast(Vector(origin), Vector(direction), distance=50)
        return (Vector(loc), Vector(nor).normalized()) if ok else (None, None)

    def front(self, x, z):
        return self.cast((x, -10, z + self.dz), (0, 1, 0))

    def top(self, x, y=0.0):
        return self.cast((x, y, 10), (0, 0, -1))

    def side(self, z, left=True):
        return self.cast((-10 if left else 10, 0, z), (1 if left else -1, 0, 0))


def on_surface(sc, surf, name, x, z, scale, material, push=0.0):
    p, n = surf.front(x, z)
    if p is None or n.y > -0.45:  # まえを むいていない ところには はらない
        return None
    rot = Vector((0, 0, 1)).rotation_difference(n)
    return ellipsoid(sc, name, p + n * push, scale, material, rot)


# ---------- モンスター ----------
def body_mesh(shape):
    D = 0.82  # おくゆき
    if shape == 'blob':
        def f(co):
            zn = co.z
            k = 1 - 0.42 * max(0.0, zn)
            z = 1.95 + 1.5 * zn
            if zn < -0.7:
                z = 1.95 + 1.5 * (-0.7 + (zn + 0.7) * 0.8)
            return (co.x * 1.5 * k, co.y * 1.5 * k * D * 1.1, z)
        return sphere_mesh('body', fn=f)
    if shape == 'round':
        return sphere_mesh('body', fn=lambda co: (co.x * 1.36, co.y * 1.36 * D, 1.72 + co.z * 1.36))
    if shape == 'tall':
        return sphere_mesh('body', fn=lambda co: (co.x * 1.16, co.y * 1.16 * D, 1.82 + co.z * 1.52))
    if shape == 'ghost':
        def f(co):
            zn = co.z
            if zn >= 0:
                return (co.x * 1.2, co.y * 1.2 * D, 2.0 + zn * 1.4)
            r = math.hypot(co.x, co.y)
            ang = math.atan2(co.y, co.x)
            if zn > -0.97:
                rr = 1.2 * (1 + 0.04 * (-zn))
                z = 2.0 - 1.62 * (-zn / 0.97)
                if zn < -0.9:
                    z += 0.13 * math.cos(6 * ang)
            else:
                rr = 0.6
                z = 0.42
            s = rr / r if r > 1e-6 else 0
            return (co.x * s, co.y * s * D, z)
        return sphere_mesh('body', 64, 40, f)
    # block: かどの まるい はこ（たまを 四角に ちかづける）
    def f(co):
        def sq(c):
            return math.copysign(abs(c) ** 0.35, c)
        return (sq(co.x) * 1.24, sq(co.y) * 1.24 * D * 0.85, 1.72 + sq(co.z) * 1.37)
    return sphere_mesh('body', 64, 32, f)


def build_monster(sc, m):
    h = m['hue']
    M_body = mat('m_body', hsl(h, 0.62, 0.58), rough=0.42, coat=0.35, sss=0.15, bump=0.12)
    M_dark = mat('m_dark', hsl(h, 0.5, 0.26), rough=0.5, coat=0.2)
    M_light = mat('m_light', hsl(h, 0.8, 0.82), rough=0.45, coat=0.3, sss=0.1)
    M_white = mat('m_white', (0.95, 0.95, 0.95, 1), rough=0.12, coat=0.6)
    M_pupil = mat('m_pupil', (0.01, 0.01, 0.012, 1), rough=0.05, coat=1.0)
    M_glint = mat('m_glint', (1, 1, 1, 1), emit=4.0)
    M_mouth = mat('m_mouth', hsl(h, 0.45, 0.16), rough=0.6)
    M_cheek = mat('m_cheek', hexc('#ff8fa3'), rough=0.6)
    M_gold = mat('m_gold', hexc('#ffc93c'), rough=0.22, metal=1.0)
    M_gem_r = mat('m_gem_r', hexc('#e23d3d'), rough=0.05, coat=1.0)
    M_gem_b = mat('m_gem_b', hexc('#3f8fe0'), rough=0.05, coat=1.0)

    body = link(sc, 'body', body_mesh(m['shape']), M_body)
    surf = Surface(body)
    if m['shape'] == 'blob':
        surf.dz = 0.3
    shift = (TOPS[m['shape']] - 40) / 50  # SVG の つのを ずらした ぶん

    # うで
    for left in (True, False):
        p, n = surf.side(sz(128), left)
        if p is not None:
            s = -1 if left else 1
            ellipsoid(sc, 'arm', p + Vector((s * 0.12, -0.15, 0)), (0.27, 0.24, 0.44), M_body,
                      Quaternion((0, 1, 0), -s * 0.55))
    # あし（まるいからだ）
    if m['shape'] == 'round':
        for s in (-1, 1):
            ellipsoid(sc, 'foot', (s * 0.62, -0.35, 0.22), (0.44, 0.5, 0.24), M_dark)
    # おなか・もよう
    if m['shape'] != 'blob':
        on_surface(sc, surf, 'belly', 0, sz(150), (0.6, 0.38, 0.035), M_light, push=-0.01)
    if m['spots']:
        for x, y, r in [(62, 76, 7), (142, 84, 5), (140, 140, 6)]:
            on_surface(sc, surf, 'spot', sx(x), sz(y), (r / 50, r / 50, 0.04), M_light)
    # め
    eyes = {1: [(100, 94, 24)], 2: [(74, 98, 16), (126, 98, 16)], 3: [(68, 102, 12), (100, 86, 13), (132, 102, 12)]}[m['eyes']]
    for x, y, r in eyes:
        p, n = surf.front(sx(x), sz(y))
        if p is None:
            continue
        R = r / 50 * 1.05
        c = p + n * (R * 0.35)
        ellipsoid(sc, 'eye', c, (R, R, R), M_white)
        fwd = (n + Vector((0, -1, 0))).normalized()
        pc = c + fwd * (R * 0.72) + Vector((R * 0.12, 0, -R * 0.08))
        ellipsoid(sc, 'pupil', pc, (R * 0.55, R * 0.55, R * 0.3), M_pupil, Vector((0, 0, 1)).rotation_difference(fwd))
        ellipsoid(sc, 'glint', pc + fwd * (R * 0.22) + Vector((-R * 0.15, 0, R * 0.2)), (R * 0.16,) * 3, M_glint)
    # まゆ（ボス）
    if m['boss']:
        for s in (-1, 1):
            a, b = (sx(100 + s * 48), sz(70)), (sx(100 + s * 12), sz(80))
            pts = []
            for t in [i / 6 for i in range(7)]:
                x, z = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
                p, n = surf.front(x, z)
                if p is not None:
                    pts.append(p + n * 0.1)
            if len(pts) > 1:
                tube(sc, 'brow', pts, 0.085, M_mouth)
    # くち
    def proj(path, push=0.06):
        pts = []
        for x, y in path:
            p, n = surf.front(sx(x), sz(y))
            if p is not None:
                pts.append(p + n * push)
        return pts
    if m['mouth'] in ('smile', 'fang'):
        tube(sc, 'mouth', proj(bezier_q((78, 130), (100, 154), (122, 130), 16)), 0.055, M_mouth)
        if m['mouth'] == 'fang':
            for x in (90, 110):
                p, n = surf.front(sx(x), sz(142))
                if p is not None:
                    cone(sc, 'fang', p + n * 0.06 + Vector((0, 0, 0.16)), p + n * 0.12 + Vector((0, 0, -0.14)), 0.1, M_white)
    if m['mouth'] == 'o':
        on_surface(sc, surf, 'mouth', 0, sz(138), (0.24, 0.29, 0.06), M_mouth)
        on_surface(sc, surf, 'tongue', 0, sz(147), (0.14, 0.09, 0.07), M_cheek, push=0.01)
    if m['mouth'] == 'zig':
        tube(sc, 'mouth', proj([(76, 134), (86, 143), (96, 134), (106, 143), (116, 134), (124, 141)]), 0.055, M_mouth)
    # ほっぺ
    for s in (-1, 1):
        on_surface(sc, surf, 'cheek', s * sx(56) * -1 if s < 0 else -sx(56), sz(124), (0.21, 0.13, 0.03), M_cheek)
    # つの
    def horn_at(bx, tip, r, material, flat=1.0):
        p, n = surf.top(bx)
        if p is None:
            return
        base = p - n * 0.12
        t = Vector((sx(tip[0]), 0, sz(tip[1]) - shift))
        cone(sc, 'horn', base, Vector((t.x, base.y, t.z)), r, material, flat)
    if m['horn'] == 'two':
        for s in (-1, 1):
            horn_at(s * 0.56, (100 + s * 54, 4), 0.32, M_light)
    if m['horn'] == 'one':
        horn_at(0, (100, -10), 0.32, M_light)
    if m['horn'] == 'ears':
        for s in (-1, 1):
            horn_at(s * 0.62, (100 + s * 46, 20), 0.34, M_body, flat=0.4)
    if m['horn'] == 'antenna':
        for s in (-1, 1):
            p, n = surf.top(s * 0.28)
            if p is None:
                continue
            tip = Vector((s * 0.64, p.y, sz(12) - shift))
            tube(sc, 'antenna', [p - n * 0.1, (p + tip) / 2 + Vector((0, 0, 0.05)), tip], 0.05, M_dark)
            ellipsoid(sc, 'ball', tip, (0.19, 0.19, 0.19), M_light)
    # はね
    if m['wings']:
        pts = bezier_c((50, 105), (12, 70), (0, 112), (12, 138)) + bezier_c((12, 138), (24, 124), (32, 132), (46, 124))[1:]
        for s in (-1, 1):
            p2 = [(sx(100 + s * (100 - x)) if s > 0 else sx(x), sz(y)) for x, y in pts]
            if s > 0:
                p2 = list(reversed(p2))
            w = prism(sc, 'wing', p2, 0.07, M_dark)
            w.location = (0, 0.35, 0.1)
            w.rotation_euler = (0, 0, -s * 0.35)
    # おうかん
    if m['boss']:
        p, n = surf.top(0)
        if p is not None:
            build_crown(sc, Vector((0, p.y, p.z - 0.22)), 0.62, 0.42, M_gold, [M_gem_r, M_gem_b])
    return body


def build_crown(sc, base, radius, spike, M_gold, gems):
    bm = bmesh.new()
    n = 96
    h = 0.28
    bot = [bm.verts.new((radius * math.cos(2 * math.pi * i / n), radius * math.sin(2 * math.pi * i / n), 0)) for i in range(n)]
    top = []
    for i in range(n):
        a = 2 * math.pi * i / n
        t = (6 * a / (2 * math.pi)) % 1
        tri = 1 - abs(t * 2 - 1)
        top.append(bm.verts.new((radius * 1.06 * math.cos(a), radius * 1.06 * math.sin(a), h + spike * tri ** 1.5)))
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((bot[i], bot[j], top[j], top[i]))
    me = bpy.data.meshes.new('crown')
    bm.to_mesh(me)
    bm.free()
    smooth(me)
    ob = link(sc, 'crown', me, M_gold)
    ob.location = base
    ob.rotation_euler = (0, 0, math.pi / 2)  # とがりを まえに
    so = ob.modifiers.new('sol', 'SOLIDIFY')
    so.thickness = 0.06
    for k, ang in enumerate((-0.6, 0, 0.6)):
        g = gems[0] if k == 1 else gems[1]
        p = base + Vector((radius * 1.08 * math.sin(ang), -radius * 1.08 * math.cos(ang), h * 0.5))
        ellipsoid(sc, 'gem', p, (0.09, 0.05, 0.09), g)
    return ob


# ---------- ゆうしゃ ----------
TIERS = [
    dict(cape='#e05a47', armor='#8bc34a'),
    dict(cape='#3d7fe0', armor='#7cb342'),
    dict(cape='#5e6b85', armor='#b0bec5'),
    dict(cape='#c62828', armor='#ffca28'),
    dict(cape='#8e24aa', armor='#ffd54f'),
]


def build_hero(sc, ti):
    t = TIERS[ti]
    metal_armor = ti >= 2
    M_skin = mat('h_skin', hexc('#ffd2a6'), rough=0.5, sss=0.25)
    M_hair = mat('h_hair', hexc('#5d4037'), rough=0.5, coat=0.2, bump=0.06)
    M_armor = mat('h_armor', hexc(t['armor']), rough=0.25 if metal_armor else 0.6, metal=0.9 if metal_armor else 0.0, bump=0 if metal_armor else 0.1)
    M_cape = mat('h_cape', hexc(t['cape']), rough=0.75, sss=0.05, bump=0.15)
    M_leather = mat('h_leather', hexc('#5d4037'), rough=0.6, bump=0.1)
    M_belt = mat('h_belt', hexc('#6d4c41'), rough=0.55)
    M_steel = mat('h_steel', hexc('#fff3b0') if ti >= 3 else hexc('#e3e9f0'), rough=0.12, metal=1.0, emit=0.6 if ti >= 2 else 0.0)
    M_eye = mat('h_eye', (0.02, 0.02, 0.025, 1), rough=0.05, coat=1.0)
    M_glint = mat('h_glint', (1, 1, 1, 1), emit=4.0)
    M_cheek = mat('h_cheek', hexc('#ff8fa3'), rough=0.6)
    M_helm = mat('h_helm', hexc('#b0bec5'), rough=0.2, metal=1.0)
    M_shield = mat('h_shield', hexc('#ffca28') if ti >= 3 else hexc('#90a4ae'), rough=0.25, metal=1.0)
    M_emblem = mat('h_emblem', hexc(t['cape']), rough=0.3, coat=0.8)
    M_gold = mat('h_gold', hexc('#ffc93c'), rough=0.22, metal=1.0)
    M_gem_r = mat('h_gem_r', hexc('#e23d3d'), rough=0.05, coat=1.0)
    M_gem_b = mat('h_gem_b', hexc('#3f8fe0'), rough=0.05, coat=1.0)

    # あし・くつ
    for s in (-1, 1):
        ellipsoid(sc, 'leg', (s * 0.2, 0, 0.42), (0.15, 0.15, 0.32), M_leather)
        ellipsoid(sc, 'boot', (s * 0.21, -0.08, 0.12), (0.19, 0.26, 0.13), M_leather)
    # マント（うしろの はんぶんの つつ）
    bm = bmesh.new()
    seg, rows = 40, 16
    grid = []
    for r_ in range(rows + 1):
        v = r_ / rows
        z = 1.62 - v * 1.4
        rad = 0.42 + v * 0.45
        row = []
        for i in range(seg + 1):
            a = math.pi * (0.05 + 0.9 * i / seg)
            wave = 0.04 * math.sin(i * 0.9) * v
            row.append(bm.verts.new(((rad + wave) * math.cos(a), (rad + wave) * math.sin(a) * 0.75 + 0.05, z)))
        grid.append(row)
    for r_ in range(rows):
        for i in range(seg):
            bm.faces.new((grid[r_][i], grid[r_][i + 1], grid[r_ + 1][i + 1], grid[r_ + 1][i]))
    me = bpy.data.meshes.new('cape')
    bm.to_mesh(me)
    bm.free()
    smooth(me)
    cape = link(sc, 'cape', me, M_cape)
    cape.modifiers.new('sol', 'SOLIDIFY').thickness = 0.04
    # からだ
    ellipsoid(sc, 'torso', (0, 0, 1.12), (0.5, 0.4, 0.56), M_armor)
    bt = bpy.data.meshes.new('belt')
    bmb = bmesh.new()
    bmesh.ops.create_cone(bmb, cap_ends=False, segments=48, radius1=0.47, radius2=0.47, depth=0.13)
    bmb.to_mesh(bt)
    bmb.free()
    smooth(bt)
    belt = link(sc, 'belt', bt, M_belt)
    belt.location = (0, 0, 0.86)
    belt.scale = (1.0, 0.82, 1)
    ellipsoid(sc, 'buckle', (0, -0.39, 0.86), (0.08, 0.03, 0.07), M_gold)
    # うで・て
    ellipsoid(sc, 'arm_r', (0.5, -0.05, 1.12), (0.13, 0.13, 0.3), M_armor, Quaternion((0, 1, 0), 0.6))
    ellipsoid(sc, 'arm_l', (-0.5, -0.05, 1.12), (0.13, 0.13, 0.3), M_armor, Quaternion((0, 1, 0), -0.6))
    hand = Vector((0.66, -0.28, 0.95))
    ellipsoid(sc, 'hand_r', hand, (0.13, 0.13, 0.13), M_skin)
    ellipsoid(sc, 'hand_l', (-0.66, -0.28, 0.95), (0.13, 0.13, 0.13), M_skin)
    # つるぎ（にぎりを てに、はを みぎうえへ）
    up = Vector((math.sin(0.28), -0.05, math.cos(0.28))).normalized()
    side = Vector((math.cos(0.28), 0, -math.sin(0.28)))
    q = Vector((0, 0, 1)).rotation_difference(up)
    ellipsoid(sc, 'grip', hand + up * 0.02, (0.05, 0.05, 0.18), M_leather, q)
    ellipsoid(sc, 'pommel', hand - up * 0.2, (0.07, 0.07, 0.07), M_gold)
    guard_c = hand + up * 0.2
    tube(sc, 'guard', [guard_c - side * 0.24, guard_c + side * 0.24], 0.045, M_gold)
    bl = prism(sc, 'blade', [(-0.07, 0), (0.07, 0), (0.07, 1.2), (0, 1.36), (-0.07, 1.2)], 0.035, M_steel)
    bl.location = guard_c + Vector((0, 0.0175, 0))
    bl.rotation_mode = 'QUATERNION'
    bl.rotation_quaternion = Quaternion((0, 1, 0), 0.28)
    # たて
    if ti >= 1:
        pts = [(-0.34, 0.3), (0.34, 0.3), (0.34, -0.1)] + [(0.34 * math.cos(a), -0.1 - 0.36 * math.sin(a)) for a in [i / 10 * math.pi for i in range(1, 10)]] + [(-0.34, -0.1)]
        sh = prism(sc, 'shield', pts, 0.07, M_shield)
        sh.location = (-0.74, -0.42, 1.0)
        sh.rotation_euler = (0, 0, 0.35)
        ellipsoid(sc, 'emblem', (-0.72, -0.5, 1.02), (0.12, 0.04, 0.12), M_emblem)
    # あたま
    head_c = Vector((0, 0, 2.02))
    ellipsoid(sc, 'head', head_c, (0.6, 0.56, 0.58), M_skin)
    # かみ：あたまを おおう キャップ（かおの ところは あたまの なかへ しずめる）＋ まえがみの たば
    def ss(e0, e1, x):
        t = min(1.0, max(0.0, (x - e0) / (e1 - e0)))
        return t * t * (3 - 2 * t)
    def hair_fn(co):
        x, y, z = co.x, co.y, co.z
        front = ss(0.0, -0.75, y)          # まえほど 1
        th = -0.6 + 0.85 * front           # これより したは かおを だす
        w = ss(th + 0.08, th - 0.08, z)    # 1 なら しずめる
        k = 1.0 - 0.2 * w
        return (x * 0.66 * k, y * 0.62 * k, z * 0.64 * k + (0.04 if z > 0 else 0))
    hm = sphere_mesh('hair', 72, 36, hair_fn)
    hair = link(sc, 'hair', hm, M_hair)
    hair.location = head_c + Vector((0, 0.02, 0.02))
    for sgn in (-1, 1):  # よこの かみ
        cone(sc, 'side', head_c + Vector((sgn * 0.56, -0.1, 0.2)), head_c + Vector((sgn * 0.6, -0.22, -0.22)), 0.15, M_hair, flat=0.6)
    # かお
    for s in (-1, 1):
        e = head_c + Vector((s * 0.2, -0.52, -0.02))
        ellipsoid(sc, 'eye', e, (0.065, 0.04, 0.085), M_eye)
        ellipsoid(sc, 'glint', e + Vector((-0.02, -0.035, 0.03)), (0.022,) * 3, M_glint)
        ellipsoid(sc, 'cheek', head_c + Vector((s * 0.33, -0.44, -0.16)), (0.09, 0.03, 0.055), M_cheek, Quaternion((0, 0, 1), s * 0.5))
    mouth = [head_c + Vector((0.16 * math.cos(a), -0.54 + 0.06 * abs(math.cos(a)), -0.2 - 0.08 * math.sin(a))) for a in [math.pi * i / 10 for i in range(11)]]
    tube(sc, 'mouth', mouth, 0.022, M_belt)
    # かぶと
    if ti >= 2:
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=72, v_segments=36, radius=1)
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < 0.05 or (v.co.y < -0.35 and v.co.z < 0.42)], context='VERTS')
        for v in bm.verts:
            v.co = Vector((v.co.x * 0.71, v.co.y * 0.67, v.co.z * 0.68)) + head_c + Vector((0, 0.02, 0.06))
        me = bpy.data.meshes.new('helm')
        bm.to_mesh(me)
        bm.free()
        smooth(me)
        hm = link(sc, 'helm', me, M_helm)
        hso = hm.modifiers.new('sol', 'SOLIDIFY')
        hso.thickness = 0.05
        hso.offset = 1
    if ti >= 3:
        build_crown(sc, head_c + Vector((0, 0, 0.5)), 0.32, 0.26, M_gold, [M_gem_r, M_gem_b])


# ---------- かきだし ----------
def render(sc, path):
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True, scene=sc.name)


def do_monsters(ids):
    sc = setup_scene()
    frame_camera(sc, 'monster')
    os.makedirs(OUT, exist_ok=True)
    done = []
    for mid in ids:
        key, k = mid.split('-')
        clear_parts(sc)
        build_monster(sc, monster_def(key, int(k)))
        render(sc, f'{OUT}/mon-{mid}.webp')
        done.append(mid)
    return done


def do_heroes(tiers):
    sc = setup_scene()
    frame_camera(sc, 'hero')
    os.makedirs(OUT, exist_ok=True)
    for ti in tiers:
        clear_parts(sc)
        build_hero(sc, ti)
        render(sc, f'{OUT}/hero-{ti}.webp')
    return list(tiers)
