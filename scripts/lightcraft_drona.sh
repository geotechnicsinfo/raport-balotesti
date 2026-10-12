#!/usr/bin/env bash
# Prelucrarea pozelor din dronă cu LightCraft (ArtCraft, https://github.com/storytold/lightcraft), CLI headless.
# Build: cargo build --release -p lightcraft-cli   (sau lightcraft-cli din pachetul de instalare)
# Rulare: scripts/lightcraft_drona.sh "<folder originale>" <folder ieșire>
# După rulare: copiază ieșire/drona/NN.jpg → photos/drona/, ieșire/teren/NN.jpg → photos/teren/ și
# panoramele decupate → photos/panorame/pN.jpg (lista și titlurile în drona.json, cheia "panorame").
set -euo pipefail
SRC="$1"; OUT="$2"; LC="${LC:-lightcraft-cli}"
LOOK="--set effects.dehaze=18 --set light.highlights=-35 --set light.shadows=30 --set light.whites=8 --set light.blacks=-6 --set effects.clarity=12 --set effects.texture=10 --set color.vibrance=14"
LOOKT="--set effects.dehaze=8 --set light.highlights=-30 --set light.shadows=25 --set effects.clarity=8 --set effects.texture=6 --set color.vibrance=10"
mkdir -p "$OUT/drona" "$OUT/teren" "$OUT/pano" "$OUT/tmp"
k=0; for f in $(ls "$SRC"/dji_*.jpg | sort); do k=$((k+1)); $LC render "$f" -o "$OUT/drona/$(printf %02d $k).jpg" --size 2000 --quality 84 $LOOK; done
k=0; for f in $(ls "$SRC"/TimePhoto_*.jpg | sort); do k=$((k+1)); $LC render "$f" -o "$OUT/teren/$(printf %02d $k).jpg" --size 1600 --quality 84 $LOOKT; done
# panorame: grupuri de cadre făcute din același punct (numerele = ordinea cronologică a cadrelor dji)
files=($(ls "$SRC"/dji_*.jpg | sort))
for grp in "2 3 4" "5 6 7" "9 10" "11 12 13" "14 15 16 17" "18 19" "20 21 22" "23 24"; do
  g=$(echo $grp | tr ' ' '-'); d="$OUT/tmp/$g"; mkdir -p "$d"; fs=()
  for i in $grp; do cp "${files[$((i-1))]}" "$d/"; fs+=("$d/$(basename "${files[$((i-1))]}")"); done
  $LC merge panorama "${fs[@]}" >/dev/null
  $LC render "$(ls "$d"/*-Pano.dng | head -1)" -o "$OUT/pano/pano_$g.jpg" --size 2800 --quality 86 $LOOK
done
# marginile negre ale panoramelor se decupează la cel mai mare dreptunghi util (vezi README)
