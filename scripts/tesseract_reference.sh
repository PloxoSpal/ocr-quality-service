#!/usr/bin/env bash
# Строит эталон OCR для калибровки: прогоняет Tesseract (в Docker, на хост ничего
# не ставится) по каждому изображению набора и записывает среднюю уверенность
# по словам и число распознанных слов.
#
# Использование: scripts/tesseract_reference.sh [IMAGES_DIR] [OUTPUT_CSV]
set -euo pipefail

IMAGES_DIR="$(cd "${1:-eval/dataset/images}" && pwd)"
OUTPUT="${2:-eval/tesseract_reference.csv}"
mkdir -p "$(dirname "$OUTPUT")"

docker run --rm -v "${IMAGES_DIR}:/data:ro" ubuntu:24.04 bash -c '
  set -e
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq >/dev/null
  apt-get install -y -qq tesseract-ocr tesseract-ocr-eng tesseract-ocr-fra tesseract-ocr-chi-sim >/dev/null
  echo "file,lang,words,mean_conf"
  for f in /data/*; do
    name=$(basename "$f")
    best=""
    for lang in eng+fra chi_sim; do
      line=$(tesseract "$f" stdout -l "$lang" --psm 3 tsv 2>/dev/null | awk -F"\t" -v n="$name" -v l="$lang" "
        NR > 1 && \$1 == 5 && \$11 >= 0 && \$12 ~ /[[:alnum:]]/ { s += \$11; c += 1 }
        END { printf \"%s,%s,%d,%.2f\", n, l, c, (c ? s / c : 0) }")
      # Выбираем язык с большей средней уверенностью (среди результатов хотя бы
      # с 5 словами): если считать только слова, chi_sim побеждает на латинице.
      if [ -z "$best" ]; then best="$line"; continue; fi
      better=$(echo "$line,$best" | awk -F, "{
        w1 = \$3; c1 = \$4; w2 = \$7; c2 = \$8
        ok1 = (w1 >= 5); ok2 = (w2 >= 5)
        print ((ok1 && !ok2) || (ok1 == ok2 && c1 > c2)) ? 1 : 0 }")
      if [ "$better" = "1" ]; then best="$line"; fi
    done
    echo "$best"
  done
' > "$OUTPUT"

echo "Wrote $(($(wc -l < "$OUTPUT") - 1)) rows to $OUTPUT"
