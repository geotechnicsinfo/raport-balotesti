#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prelucrează pozele din zborul cu drona (și pozele de recunoaștere geoetichetate) pentru aplicație:
  - orientare EXIF, redimensionare (2000 px dronă / 1600 px teren) + miniaturi 480 px;
  - corecție ușoară: autocontrast (0,4 %), saturație +6 %, unsharp mask fin;
  - poziția GPS, ora, altitudinea absolută și înălțimea aproximativă față de teren
    (altitudine EXIF − cota din terrain.json; indicativ, GPS-ul dronei are erori de câțiva metri).

Rulare (din folderul aplicației):
  python3 scripts/build_drona.py --src "../3. Poze/drona" --terrain terrain.json --out .
Rezultat: photos/drona/*.jpg, photos/teren/*.jpg, drona.json
"""
import argparse, json, os, re
from PIL import Image, ImageOps, ImageEnhance, ImageFilter

Q = 80


def dms(v, ref):
    if not v: return None
    d = float(v[0]) + float(v[1]) / 60 + float(v[2]) / 3600
    return round(-d if ref in ('S', 'W') else d, 7)


def z_at(T, lat, lon):
    n = T['n']
    fi = (lat - T['lat0']) / (T['lat1'] - T['lat0']) * (n - 1); fj = (lon - T['lon0']) / (T['lon1'] - T['lon0']) * (n - 1)
    # puncte puțin în afara grilei (≤ ~40 m, ex. deasupra lacului) → cota de la marginea grilei
    if min(fi, fj) < -8 or max(fi, fj) > n - 1 + 8: return None   # ~8 celule ≈ 45 m
    fi = max(0, min(fi, n - 1.001)); fj = max(0, min(fj, n - 1.001))
    i, j = int(fi), int(fj); a, b = fi - i, fj - j; g = lambda r, c: T['z'][r * n + c]
    return g(i, j) * (1 - a) * (1 - b) + g(i + 1, j) * a * (1 - b) + g(i, j + 1) * (1 - a) * b + g(i + 1, j + 1) * a * b


def enhance(im):
    im = ImageOps.autocontrast(im, cutoff=0.4, preserve_tone=True)
    im = ImageEnhance.Color(im).enhance(1.06)
    return im.filter(ImageFilter.UnsharpMask(radius=1.2, percent=45, threshold=3))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', required=True); ap.add_argument('--terrain', default='terrain.json'); ap.add_argument('--out', required=True)
    a = ap.parse_args()
    T = json.load(open(a.terrain, encoding='utf-8')) if os.path.exists(a.terrain) else None
    res = {'aerian': [], 'teren': []}
    files = sorted(f for f in os.listdir(a.src) if re.search(r'\.jpe?g$', f, re.I))
    for f in files:
        src = os.path.join(a.src, f)
        im0 = Image.open(src); ex = im0.getexif(); g = ex.get_ifd(0x8825); e2 = ex.get_ifd(0x8769)
        drone = f.lower().startswith('dji') or 'DJI' in str(ex.get(271, '')) or str(ex.get(272, '')).startswith('FC')
        kind = 'aerian' if drone else 'teren'
        lat, lon = dms(g.get(2), g.get(1, 'N')), dms(g.get(4), g.get(3, 'E'))
        alt = float(g.get(6)) if g.get(6) is not None else None
        dt = e2.get(36867) or ex.get(306)
        m = re.match(r'(\d{4}):(\d\d):(\d\d) (\d\d):(\d\d):(\d\d)', str(dt or ''))
        data, ora = (f'{m.group(1)}-{m.group(2)}-{m.group(3)}', f'{m.group(4)}:{m.group(5)}:{m.group(6)}') if m else (None, None)
        zt = z_at(T, lat, lon) if (T and lat) else None
        k = len(res[kind]) + 1; name = f'{k:02d}'
        od = os.path.join(a.out, 'photos', 'drona' if drone else 'teren'); os.makedirs(od, exist_ok=True)
        rel = 'photos/' + ('drona' if drone else 'teren')
        big, th = os.path.join(od, f'{name}.jpg'), os.path.join(od, f't_{name}.jpg')
        if not (os.path.exists(big) and os.path.getmtime(big) >= os.path.getmtime(src)):
            im = enhance(ImageOps.exif_transpose(im0).convert('RGB'))
            b = im.copy(); b.thumbnail((2000 if drone else 1600,) * 2, Image.LANCZOS); b.save(big, 'JPEG', quality=Q, optimize=True, progressive=True)
            t = im.copy(); t.thumbnail((480, 480), Image.LANCZOS); t.save(th, 'JPEG', quality=74, optimize=True, progressive=True)
        w, h = Image.open(big).size
        res[kind].append({'src': f'{rel}/{name}.jpg', 'thumb': f'{rel}/t_{name}.jpg', 'original': f, 'w': w, 'h': h,
                          'lat': lat, 'lon': lon, 'data': data, 'ora': ora,
                          'alt': round(alt, 1) if alt is not None else None,
                          'h_teren': round(alt - zt) if (alt is not None and zt is not None and drone) else None,
                          'aparat': ('DJI ' if drone else '') + str(ex.get(272, '')).strip()})
        print(kind, name, f, lat, lon, ora, alt, zt and round(zt, 1))
    for k in res: res[k].sort(key=lambda x: (x['data'] or '', x['ora'] or ''))
    json.dump(res, open(os.path.join(a.out, 'drona.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('drona.json:', len(res['aerian']), 'aeriene,', len(res['teren']), 'de teren')


if __name__ == '__main__':
    main()
