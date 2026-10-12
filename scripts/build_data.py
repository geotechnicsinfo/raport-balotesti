#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Construiește data.json și pozele optimizate pentru aplicația de raportare
a investigațiilor de teren – Balotești, str. Lacului (NC 66359), jud. Ilfov.

Surse:
  - fise_foraj_completate_F1-F8 Balotesti str.Lacului.xlsx (foaia "Fise": stratificație, apă, dată, GPS)
  - Balotesti_foraje_coordonate.csv   (forajele propuse: Stereo 70, cotă, adâncime, amplasare)
  - Balotesti_NC66359_cladiri_foraje.kmz (limita proprietății, marginea lacului, clădirile propuse, etapele)
  - coordonate.csv (5. Prelucrare date) – cota terenului din ridicarea topografică, în punctul GPS al forajului
  - probe.json + clasificare_probe.csv (5. Prelucrare date) – rezultatele de laborator (buletinele BBC)
  - foldere de poze f1 … f8 (poze WhatsApp + fișa manuscrisă f1.jpeg, f7B-1.jpeg …)
  - meteo.json (Open-Meteo archive)

Rulare (din folderul aplicației):
  python3 scripts/build_data.py --fise "../2. Fise de foraj/fise_foraj_completate_F1-F8 Balotesti str.Lacului.xlsx" \
     --csv "../1. Input/Balotesti_foraje_coordonate.csv" --kmz "../1. Input/Balotesti_NC66359_cladiri_foraje.kmz" \
     --cote "../5. Prelucrare date/coordonate (1).csv" --lab "../5. Prelucrare date/probe.json" \
     --clasif "../5. Prelucrare date/clasificare_probe.csv" --poze "../3. Poze" --meteo scripts/meteo.json --out .
"""
import argparse, csv, html, json, os, re, datetime, zipfile
import openpyxl
from PIL import Image, ImageOps

MAX_W = 1200
THUMB_W = 420
QUALITY = 68

# ---- corecturi confirmate (JURNAL.md, 12.10.2026) ----
# Pe fișe luna este trecută greșit (10 în loc de 09): forajele s-au executat în 11–14.09.2026.
LUNA_GRESITA = ('2026-10', '2026-09')
CORECTII = {
    'F5': {'adancime': 8.0, 'nota': 'Adâncimea reală a forajului este 8,00 m (pe fișă: 7,00 m); proba P8 a fost prelevată la 8,00 m.'},
    'F7': {'nota': 'Forajul a fost oprit la 4,00 m pe o piatră mare și a fost reluat în apropiere ca F7b. Fotografiile de teren sunt prezentate la F7b.'},
    'F7b': {'proiectat': 'F7', 'nota': 'Foraj de înlocuire pentru F7 (oprit la 4,00 m).'},
    'F8': {'nota': 'Data execuției nu este consemnată pe fișă.'},
}
# Folderul de poze al fiecărui foraj (implicit: id-ul cu litere mici). F7 și F7b au pozele în același folder „f7”.
FOLDER = {'F7b': 'f7'}
# Pozele din „f7” nu se pot separa sigur între F7 și F7b (aceeași zi, același echipament; lăzile etichetate F7B):
# toate pozele de teren se afișează la F7b, iar F7 păstrează doar fișa manuscrisă. Fișa F7b = f7B-1.jpeg, F7b-2.jpeg.


def dms_to_dec(s):
    m = re.search(r'([NSEW])\s*(\d+)[°\s]+(\d+)[\'\s]+([\d.]+)', str(s or ''))
    if not m: return None
    h, d, mi, se = m.group(1), float(m.group(2)), float(m.group(3)), float(m.group(4))
    v = d + mi / 60 + se / 3600
    return round(-v if h in 'SW' else v, 6)


def norm_date(s):
    if not s: return None
    if isinstance(s, (datetime.date, datetime.datetime)): return s.strftime('%Y-%m-%d')
    m = re.match(r'(\d{1,2})[.\-](\d{1,2})[.\-](\d{4})', str(s).strip())
    return f'{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}' if m else None


def fnum(v):
    if v is None: return None
    if isinstance(v, (int, float)): return float(v)
    s = str(v).strip().replace(',', '.')
    if s in ('', '--', '-', 'None'): return None
    try: return float(s)
    except ValueError: return None


def parse_fise(path):
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb['Fise']
    inv = {}
    for r in ws.iter_rows(min_row=1, values_only=True):
        name = r[0]
        if not name or str(name).strip() in ('foraj', 'Amplasament:'): continue
        name = str(name).strip()
        d = inv.setdefault(name, {'id': name, 'straturi': [], 'apa': None, 'data': None, 'data_fisa': None, 'gps_dms': [], 'note_apa': [], 'obs': []})
        de, la, desc = r[1], r[2], r[4]
        if desc and isinstance(de, (int, float)):
            d['straturi'].append({'de': float(de), 'la': float(la) if isinstance(la, (int, float)) else None, 'descriere': str(desc).strip()})
        elif desc:
            d['obs'].append(re.sub(r'^Obs\.?:\s*', '', str(desc).strip()))
        if r[5]:
            if d['apa'] is None: d['apa'] = str(r[5]).strip()
            else: d['note_apa'].append(str(r[5]).strip())
        if r[6]: d['data_fisa'] = norm_date(r[6])
        if r[7]: d['gps_dms'].append(str(r[7]).strip())
    for d in inv.values():
        lat = lon = None
        for g in d['gps_dms']:
            v = dms_to_dec(g)
            if g.strip().startswith('N'): lat = v
            elif g.strip().startswith('E'): lon = v
        d['lat'], d['lon'] = lat, lon
        vals = [s['la'] for s in d['straturi'] if s['la'] is not None] + [s['de'] for s in d['straturi']]
        d['adancime'] = max(vals) if vals else None
        allw = ' '.join([d['apa'] or ''] + d['note_apa'])
        m = re.search(r'NH\s*=\s*([\d.,]+)', allw); d['NH'] = float(m.group(1).replace(',', '.')) if m else None
        m = re.search(r'IN\s*=\s*([\d.,]+)', allw) or re.search(r'infiltra\w*.*?la\s*([\d.,]+)\s*m', allw, re.I)
        d['IN'] = float(m.group(1).replace(',', '.').rstrip('.')) if m else None
        m = re.search(r'24\s*h\s*=\s*([\d.,]+)', allw); d['NH_24h'] = float(m.group(1).replace(',', '.')) if m else None
        df = d['data_fisa']
        d['data'] = df.replace(*LUNA_GRESITA) if df and df.startswith(LUNA_GRESITA[0]) else df
    return inv


def parse_csv(path):
    pts = []
    with open(path, encoding='utf-8-sig') as fh:
        for r in csv.DictReader(fh, delimiter=';'):
            pts.append({'id': r['Foraj'].strip(), 'stereo70': {'N': float(r['X(N) Stereo70 [m]']), 'E': float(r['Y(E) Stereo70 [m]'])},
                        'cota': float(r['Cota teren [m]']), 'adancime': float(r['Adancime propusa [m]']),
                        'lat': float(r['Lat WGS84']), 'lon': float(r['Lon WGS84']), 'amplasare': r['Amplasare'].strip()})
    return pts


def parse_cote(path):
    out = {}
    if not path or not os.path.exists(path): return out
    with open(path, encoding='utf-8-sig') as fh:
        for r in csv.DictReader(fh):
            out[r['foraj'].strip()] = {'cota': fnum(r.get('cota_topo_TIN')), 'N': fnum(r.get('N_Stereo70')), 'E': fnum(r.get('E_Stereo70'))}
    return out


def parse_kmz(path):
    z = zipfile.ZipFile(path)
    s = z.read([n for n in z.namelist() if n.endswith('.kml')][0]).decode('utf-8')
    res = {'limita': None, 'lac': None, 'cladiri': [], 'etape': []}
    for folder in re.findall(r'<Folder>(.*?)</Folder>', s, re.S):
        fname = html.unescape(re.search(r'<name>(.*?)</name>', folder).group(1))
        for p in re.findall(r'<Placemark>(.*?)</Placemark>', folder, re.S):
            n = html.unescape(re.search(r'<name>(.*?)</name>', p).group(1))
            c = re.search(r'<coordinates>(.*?)</coordinates>', p, re.S)
            if not c: continue
            pts = [[round(float(x.split(',')[1]), 7), round(float(x.split(',')[0]), 7)] for x in c.group(1).split()]
            if n == 'Limită proprietate': res['limita'] = pts
            elif n == 'Margine lac': res['lac'] = pts
            elif fname.startswith('Clădiri'):
                res['cladiri'].append({'nume': n, 'tip': 'conexe' if 'conexe' in n else 'locuinta', 'contur': pts})
            elif fname.startswith('Etape'):
                res['etape'].append({'nume': n, 'contur': pts})
    return res


def diacritice(s):
    if not s: return s
    for a, d in (('Argila', 'Argilă'), ('argila', 'argilă'), ('prafoasa', 'prăfoasă'), ('nisipoasa', 'nisipoasă'), ('grasa', 'grasă'), ('pietris', 'pietriș')):
        s = re.sub(rf'\b{a}\b', d, s)
    return s


def parse_lab(probe_path, clasif_path):
    by = {}
    if not probe_path or not os.path.exists(probe_path): return by
    cl = {}
    if clasif_path and os.path.exists(clasif_path):
        with open(clasif_path, encoding='utf-8-sig') as fh:
            for r in csv.DictReader(fh): cl[r['buletin']] = r
    pc = lambda v: None if v is None else round(v * 100, 1)
    for p in json.load(open(probe_path, encoding='utf-8')):
        # foraj din numele fișierului (buletinele 8005–8007 au „F7” în antet, dar sunt ale F7b)
        mf = re.search(r' - (F\d+b?) - ', p.get('fisier') or '')
        f = mf.group(1) if mf else p['foraj'].strip(); c = cl.get(p['buletin'], {})
        nr = re.search(r'-(\d+)$', p['buletin']); pr = re.match(r'(P\d+)', p['proba'])
        g = lambda k: fnum(p.get(k))
        item = {
            'proba': pr.group(1) if pr else p['proba'], 'adancime': fnum(re.sub(r'[^\d.,]', '', p['adancime'])),
            'buletin': nr.group(1) if nr else p['buletin'], 'data_primire': p.get('data_primire'),
            'denumire': diacritice(c.get('denumire_N1')) or None, 'den_buletin': (p.get('tip_pamant') or '').split(' - ')[0] or None,
            'culoare': p.get('culoare'),
            'A': pc(g('A_pct')), 'P': pc(g('P_pct')), 'N': pc(g('N_pct')), 'Pi': pc(g('Pi_pct')),
            'w': pc(g('w')), 'wL': pc(g('wL')), 'wP': pc(g('wP')), 'IP': pc(g('IP')), 'IC': g('IC'), 'IA': g('IA'),
            'gama': g('gama'), 'gama_d': g('gama_d'), 'e': g('e'), 'n': pc(g('n')), 'Sr': g('Sr'),
            'M23': g('M23_nat'), 'M23_sat': g('M23_sat'), 'im3': g('im3'), 'phi': g('phi'), 'c': g('c'),
        }
        # probă netulburată = s-au determinat greutatea volumică / încercări pe ștuț
        item['netulburata'] = any(item[k] is not None for k in ('gama', 'M23', 'M23_sat', 'im3', 'phi'))
        by.setdefault(f, []).append(item)
    for f in by: by[f].sort(key=lambda x: (x['adancime'] or 0, x['proba']))
    return by


def process_photos(folder, out_dir, rel, iid, keep=None):
    os.makedirs(out_dir, exist_ok=True)
    files = sorted((f for f in os.listdir(folder) if re.search(r'\.jpe?g$|\.png$', f, re.I)), key=str.lower)
    fise, pics, n, nf = [], [], 0, 0
    for f in files:
        is_fisa = 'fisa' in f.lower() or bool(re.match(rf'^{re.escape(iid)}[\s_-]*\d*\.(jpe?g|png)$', f, re.I))
        is_other_fisa = bool(re.match(r'^f\d+b?[\s_-]*\d*\.(jpe?g|png)$', f, re.I)) and not is_fisa
        if is_other_fisa: continue
        if not is_fisa and keep is not None and not keep(f): continue
        src = os.path.join(folder, f)
        try:
            im = ImageOps.exif_transpose(Image.open(src)).convert('RGB')
        except Exception as e:
            print('  ! poza ignorată', src, e); continue
        if is_fisa: nf += 1; name = f'fisa{nf}'
        else: n += 1; name = f'{n:02d}'
        for w, suffix in ((MAX_W, ''), (THUMB_W, 't_')):
            dst = os.path.join(out_dir, f'{suffix}{name}.jpg')
            if os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src): continue
            img = im.copy(); img.thumbnail((w, w))
            img.save(dst, 'JPEG', quality=QUALITY, optimize=True, progressive=True)
        entry = {'src': f'{rel}/{name}.jpg', 'thumb': f'{rel}/t_{name}.jpg', 'original': f, 'w': im.width, 'h': im.height}
        m = re.search(r'(\d{4}-\d{2}-\d{2}) at (\d{2})\.(\d{2})', f)
        if m: entry['timestamp'] = f'{m.group(1)} {m.group(2)}:{m.group(3)}'
        (fise if is_fisa else pics).append(entry)
    return fise, pics


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fise', required=True); ap.add_argument('--csv', required=True); ap.add_argument('--kmz', required=True)
    ap.add_argument('--cote', default=None); ap.add_argument('--lab', default=None); ap.add_argument('--clasif', default=None)
    ap.add_argument('--poze', required=True); ap.add_argument('--meteo', default=None); ap.add_argument('--out', required=True)
    a = ap.parse_args()

    fise = parse_fise(a.fise)
    pts = parse_csv(a.csv); by_id = {p['id']: p for p in pts}
    kmz = parse_kmz(a.kmz)
    cote = parse_cote(a.cote)
    lab = parse_lab(a.lab, a.clasif)
    print(f'fise: {len(fise)}  foraje propuse: {len(pts)}  clădiri: {len(kmz["cladiri"])}  probe lab: {sum(len(v) for v in lab.values())}')

    investigatii = []
    for iid in sorted(fise, key=lambda x: (int(re.sub(r'\D', '', x) or 0), x)):
        f = fise[iid]; corr = CORECTII.get(iid, {})
        planned = by_id.get(corr.get('proiectat', iid))
        folder = os.path.join(a.poze, FOLDER.get(iid, iid.lower()))
        keep = (lambda fn: False) if iid == 'F7' else None
        fise_img, pics = ([], [])
        if os.path.isdir(folder):
            print('poze', iid); fise_img, pics = process_photos(folder, os.path.join(a.out, 'photos', iid), f'photos/{iid}', iid, keep)
        straturi = f['straturi']; adancime = f['adancime']
        if 'adancime' in corr:
            adancime = corr['adancime']
            if straturi and straturi[-1]['la'] is not None and straturi[-1]['la'] < adancime: straturi[-1]['la'] = adancime
        note = []
        if f['data_fisa'] and f['data'] != f['data_fisa']:
            note.append(f"Pe fișă luna este trecută greșit ({f['data_fisa'][8:]}.{f['data_fisa'][5:7]}.{f['data_fisa'][:4]}); data execuției: {f['data'][8:]}.{f['data'][5:7]}.{f['data'][:4]}.")
        if corr.get('nota'): note.append(corr['nota'])
        note += f['obs']
        lat, lon, src = f['lat'], f['lon'], 'GPS teren'
        if (lat is None or lon is None) and planned: lat, lon, src = planned['lat'], planned['lon'], 'punct proiectat (fără GPS în fișă)'
        ct = cote.get(iid, {})
        probe_lab = lab.get(iid, [])
        investigatii.append({
            'id': iid, 'id_fisa': iid, 'tip': 'foraj', 'nr': int(re.sub(r'\D', '', iid)),
            'amplasare': planned['amplasare'] if planned else '',
            'categorie_kml': 'Foraj geotehnic' + (' (înlocuire F7)' if iid == 'F7b' else ''),
            'eticheta': f'Foraj geotehnic {iid}', 'data': f['data'], 'nota_data': ' '.join(note) or None,
            'adancime': adancime, 'adancime_proiectata': planned['adancime'] if planned else None,
            'apa': f['apa'], 'NH': f['NH'], 'NH_24h': f['NH_24h'], 'IN': f['IN'], 'note_apa': f['note_apa'],
            'gps_dms': f['gps_dms'], 'lat': lat, 'lon': lon, 'coord_sursa': src,
            'cota': ct.get('cota'), 'stereo70': {'N': ct['N'], 'E': ct['E']} if ct.get('N') else None,
            'proiectat': planned and {'id': planned['id'], 'lat': planned['lat'], 'lon': planned['lon'], 'stereo70': planned['stereo70'],
                                      'cota': planned['cota'], 'obs': planned['amplasare'], 'adancime': f"{planned['adancime']:.0f} m"},
            'straturi': straturi,
            'probe': [{'nr': int(p['proba'][1:]) if p['proba'][1:].isdigit() else 0, 'adancime': p['adancime'],
                       'tip': 'probă netulburată (ștuț)' if p['netulburata'] else 'probă tulburată', 'observatii': p['denumire'] or ''} for p in probe_lab],
            'lab': probe_lab,
            'fisa_foto': fise_img[0] if fise_img else None, 'fise_foto': fise_img, 'poze': pics,
        })

    meteo = {}
    if a.meteo and os.path.exists(a.meteo):
        mj = json.load(open(a.meteo, encoding='utf-8')); d = mj['daily']
        for i, t in enumerate(d['time']): meteo[t] = {k: d[k][i] for k in d if k != 'time'}
        meteo['_meta'] = {'sursa': 'Open-Meteo (ERA5 / archive API)', 'lat': mj.get('latitude'), 'lon': mj.get('longitude'), 'elevatie_m': mj.get('elevation')}

    exec_ids = {i['id'] for i in investigatii}
    nlab = sum(len(i['lab']) for i in investigatii)
    stadiu = [
        {'categorie': 'Foraje geotehnice (plan: 8 foraje)', 'proiectate': len(pts), 'executate': len([p for p in pts if p['id'] in exec_ids]),
         'neexecutate': [p['id'] for p in pts if p['id'] not in exec_ids], 'obs': 'F7 oprit la 4,00 m – reluat ca F7b'},
        {'categorie': 'Probe încercate în laborator', 'proiectate': nlab, 'executate': nlab, 'neexecutate': [],
         'obs': f"{sum(1 for i in investigatii for p in i['lab'] if p['netulburata'])} netulburate · buletine BBC"},
    ]
    dates = [i['data'] for i in investigatii if i['data']]
    out = {
        'stadiu': stadiu,
        'proiect': {
            'titlu': 'Investigații geotehnice – Balotești, str. Lacului',
            'beneficiar_lucrare': 'Ansamblu de locuințe cuplate P+1E+pod și clădire cu funcțiuni conexe P+2E',
            'amplasament': 'str. Lacului, NC 66359, com. Balotești, jud. Ilfov',
            'executant': 'SC BBCGEOTECHNIC SRL',
            'tip_lucrari': 'Foraje geotehnice cu prelevare de probe (F1–F8, 4–8 m) și încercări de laborator',
            'perioada': {'de_la': min(dates) if dates else None, 'pana_la': max(dates) if dates else None},
            'generat': datetime.date.today().isoformat(),
        },
        'investigatii': investigatii,
        'puncte_proiectate': [{'id': p['id'], 'lat': p['lat'], 'lon': p['lon'], 'tip': 'Foraj geotehnic propus', 'obs': p['amplasare'],
                               'adancime': f"{p['adancime']:.0f} m", 'stereo70': p['stereo70'], 'cota': p['cota']} for p in pts],
        'limita': kmz['limita'], 'lac': kmz['lac'], 'cladiri': kmz['cladiri'], 'etape': kmz['etape'],
        'meteo': meteo,
    }
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, 'data.json'), 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print('scris data.json', len(investigatii), 'foraje,', nlab, 'probe lab')


if __name__ == '__main__':
    main()
