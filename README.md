# Investigații de teren – Balotești, str. Lacului (NC 66359)

Aplicație web statică (fără backend) pentru raportarea investigațiilor geotehnice de teren executate
la Balotești, str. Lacului, jud. Ilfov – ansamblu de locuințe cuplate P+1E+pod și clădire cu funcțiuni conexe P+2E:

- **foraje geotehnice** F1–F8 (+ F7b, înlocuirea F7 oprit la 4,00 m), 11–14.09.2026;
- **încercări de laborator** pe 45 de probe (buletine BBCGEOTECHNIC, comanda 505).

Pentru fiecare foraj: fotografii de teren + fișa manuscrisă, stratificația transcrisă cu coloană litologică,
apa (infiltrații), cota terenului din ridicarea topografică, GPS + Stereo 70, profilul de plasticitate
(w, w<sub>P</sub>–w<sub>L</sub>, I<sub>C</sub>), tabelul rezultatelor de laborator, poziția în diagrama Casagrande,
meteo în ziua execuției, mini-hartă.

Fotografii aeriene: 24 de cadre din zborul cu drona din 12.09.2026 (DJI FC8582) + 9 fotografii de recunoaștere geoetichetate
și 8 panorame lipite din cadrele făcute din același punct; galerie cu lightbox, traseul zborului și pozițiile pe hartă,
înălțimea aproximativă față de teren. Prelucrare cu LightCraft (ArtCraft, open source, Rust): `scripts/lightcraft_drona.sh`.

Plus: intro 3D (bloc de teren din ridicarea topografică, clădirile propuse, forajele „extrase” în ordinea execuției),
hartă cu limita proprietății, marginea lacului și clădirile propuse, stadiu, calendar, centralizatoare + CSV.

## Structura

```
index.html            aplicația (HTML + CSS + JS, un singur fișier)
intro3d.js            intro 3D (Three.js r128)
data.json             foraje + laborator + clădiri + meteo (generat)
terrain.json          grilă de cote 40×40 din DEM-ul 1 m al ridicării topografice
photos/<ID>/          poze optimizate (1200 px) + miniaturi t_*.jpg + fisa1.jpg … (generat)
scripts/build_data.py generatorul data.json + poze
scripts/build_drona.py  prelucrarea pozelor din dronă / recunoaștere -> photos/drona, photos/teren, drona.json
drona.json            pozițiile, ora și înălțimea fotografiilor aeriene și de recunoaștere (generat)
scripts/meteo.json    răspunsul Open-Meteo (archive) pentru 10–15.09.2026
```

## Surse de date (Google Drive office.geotehnica, `Work\2026\Balotesti`)

- `2. Fise de foraj\fise_foraj_completate_F1-F8 Balotesti str.Lacului.xlsx`, foaia „Fise”
  (foraj | de la | până la | – | descriere | apă | dată | GPS). Foile „PDG” și „Probe” nu sunt folosite.
- `3. Poze\f1 … f8` – poze WhatsApp + fișa manuscrisă (`f1.jpeg`; F7b: `f7B-1.jpeg`, `F7b-2.jpeg` în folderul `f7`).
- `1. Input\Balotesti_foraje_coordonate.csv` (forajele propuse) și `Balotesti_NC66359_cladiri_foraje.kmz`.
- `5. Prelucrare date\coordonate (1).csv` (cota TIN în punctul GPS), `probe.json`, `clasificare_probe.csv`.

## Regenerarea datelor

```bash
cd raport-investigatii-balotesti
python3 scripts/build_data.py \
  --fise "../2. Fise de foraj/fise_foraj_completate_F1-F8 Balotesti str.Lacului.xlsx" \
  --csv "../1. Input/Balotesti_foraje_coordonate.csv" --kmz "../1. Input/Balotesti_NC66359_cladiri_foraje.kmz" \
  --cote "../5. Prelucrare date/coordonate (1).csv" --lab "../5. Prelucrare date/probe.json" \
  --clasif "../5. Prelucrare date/clasificare_probe.csv" --poze "../3. Poze" --meteo scripts/meteo.json --out .
```

Pozele din dronă (album Google Foto „Balotesti str. Lacului 2026”, descărcat în `3. Poze\drona`):

```bash
python3 scripts/build_drona.py --src "../3. Poze/drona" --terrain terrain.json --out .
```

Necesită `openpyxl` și `Pillow`. Pozele deja procesate sunt sărite (deci versiunile LightCraft din `photos/drona`,
`photos/teren`, `photos/panorame` nu sunt suprascrise de `build_drona.py`, care doar recitește pozițiile).

## Observații asupra datelor (JURNAL.md, 12.10.2026)

- Pe fișe luna este trecută greșit (10 în loc de 09); s-au reținut datele 11–14.09.2026. F8 nu are dată pe fișă.
- F5: adâncimea reală 8,00 m (fișa: 7,00 m), proba P8 de la 8,00 m.
- F7: oprit la 4,00 m pe o piatră mare, reluat ca F7b. GPS-ul din fișa F7 este eronat; poziția afișată (corectată 12.10.2026) e pe limita vestică a clădirii L17, la ~10,6 m E de F7b. Pozele din folderul `f7` nu se pot separa sigur
  și sunt afișate la F7b; F7 păstrează fișa manuscrisă. Buletinele 8005–8007 („F7” în antet) sunt ale F7b.
- „IN” în fișă = infiltrație de apă (F7b la 6,00 m; F8 infiltrație slabă la 6,50 m).
- Denumirea pământurilor: diagrama ternară NP 074/2022 din granulometrie; F8-P4 (8013) are doar forfecare directă.

## Rulare locală / publicare

```bash
python -m http.server 8000     # apoi http://localhost:8000
```

Publicare: repo GitHub `geotechnicsinfo/raport-balotesti`, Settings → Pages → Source: *GitHub Actions*;
workflow-ul `.github/workflows/pages.yml` publică la fiecare push pe `main`.
