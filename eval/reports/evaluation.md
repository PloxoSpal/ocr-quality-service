# Оценка на выданном наборе данных

Изображений: 50, проверки: blur, contrast, exposure, noise, resolution, skew, text_presence, 30.6 мс на изображение (один поток).

## Совпадение с разметкой

Совпало **46 из 46** (пограничных случаев не считали: 4).

- пограничный: image_013.png -> непригоден
- пограничный: image_015.jpg -> пригоден
- пограничный: image_024.png -> пригоден
- пограничный: image_050.jpg -> непригоден

## Обнаружение дефектов

| дефект | проверка | случаев | поймано |
|---|---|---|---|
| blur | blur | 7 | 7 |
| skew | skew | 11 | 11 |
| noise | noise | 10 | 3 |
| low_contrast | contrast | 9 | 0 |
| small_text | resolution | 3 | 2 |
| no_text | text_presence | 3 | 3 |

## Корреляция с Tesseract

Спирмен между quality_score и уверенностью Tesseract: **0.69**.

## Изображения

| файл | разметка | вердикт | оценка | проблемы |
|---|---|---|---|---|
| image_001.png | yes | пригоден | 1.0 | - |
| image_002.jpg | no | **непригоден** | 0.7016 | skew: text is rotated by -13.4° (limit ±5°) |
| image_003.jpg | yes | пригоден | 0.9613 | - |
| image_004.png | yes | пригоден | 1.0 | - |
| image_005.png | no | **непригоден** | 0.7017 | skew: text is rotated by +9.7° (limit ±5°) |
| image_006.jpg | no | **непригоден** | 0.8227 | skew: text is rotated by +6.2° (limit ±5°) |
| image_007.jpg | no | **непригоден** | 0.7017 | skew: text is rotated by +8.2° (limit ±5°) |
| image_008.jpg | no | **непригоден** | 0.4125 | blur: text edges are blurred (edge spread 2.69px, limit 1.20px); skew: text is rotated by +7.4° (limit ±5°) |
| image_009.jpg | yes | пригоден | 0.9811 | - |
| image_010.png | no | **непригоден** | 0.7017 | skew: text is rotated by -7.5° (limit ±5°) |
| image_011.png | yes | пригоден | 1.0 | - |
| image_012.png | yes | пригоден | 1.0 | - |
| image_013.png | borderline | **непригоден** | 0.7642 | blur: 33% of the text area is blurred |
| image_014.png | yes | пригоден | 0.9977 | - |
| image_015.jpg | borderline | пригоден | 0.9719 | - |
| image_016.jpg | no | **непригоден** | 0.6802 | noise: 51119 specks per megapixel on the background; skew: text is rotated by -6.5° (limit ±5°) |
| image_017.png | yes | пригоден | 1.0 | - |
| image_018.jpg | no | **непригоден** | 0.7017 | skew: text is rotated by +7.8° (limit ±5°) |
| image_019.png | yes | пригоден | 1.0 | - |
| image_020.png | yes | пригоден | 0.9678 | - |
| image_021.png | yes | пригоден | 0.9458 | - |
| image_022.png | no | **непригоден** | 0.5878 | blur: 96% of the text area is blurred |
| image_023.png | yes | пригоден | 1.0 | - |
| image_024.png | borderline | пригоден | 0.9198 | - |
| image_025.png | yes | пригоден | 1.0 | - |
| image_026.png | yes | пригоден | 1.0 | - |
| image_027.png | yes | пригоден | 1.0 | - |
| image_028.jpg | no | **непригоден** | 0.7807 | resolution: characters are 5.0px high (need ~5.5px); rescan at a higher resolution |
| image_029.png | yes | пригоден | 1.0 | - |
| image_030.png | no | **непригоден** | 0.5454 | blur: text edges are blurred (edge spread 2.63px, limit 1.20px) |
| image_031.png | no | **непригоден** | 0.2154 | text_presence: only 0 text characters found (need ~35); the image may contain no text |
| image_032.png | yes | пригоден | 0.9978 | - |
| image_033.png | yes | пригоден | 0.9931 | - |
| image_034.png | yes | пригоден | 0.813 | noise: 45218 specks per megapixel on the background |
| image_035.jpg | no | **непригоден** | 0.7017 | skew: text is rotated by +11.8° (limit ±5°) |
| image_036.png | no | **непригоден** | 0.4873 | blur: text edges are blurred (edge spread 3.39px, limit 1.20px); text_presence: only 28 text characters found (need ~35); the image may contain no text |
| image_037.png | yes | пригоден | 0.9961 | - |
| image_038.jpg | no | **непригоден** | 0.3838 | blur: text edges are blurred (edge spread 1.65px, limit 1.20px); exposure: text is washed out (ink level 216/255); skew: text is rotated by -12.9° (limit ±5°) |
| image_039.png | yes | пригоден | 0.9946 | - |
| image_040.png | yes | пригоден | 0.8377 | noise: 56056 specks per megapixel on the background |
| image_041.jpg | no | **непригоден** | 0.8236 | skew: text is rotated by +6.3° (limit ±5°) |
| image_042.png | no | **непригоден** | 0.2154 | text_presence: only 3 text characters found (need ~35); the image may contain no text |
| image_043.png | yes | пригоден | 1.0 | - |
| image_044.png | no | **непригоден** | 0.7958 | resolution: characters are 5.0px high (need ~5.5px); rescan at a higher resolution |
| image_045.png | yes | пригоден | 0.9933 | - |
| image_046.png | yes | пригоден | 0.7858 | exposure: text is washed out (ink level 222/255) |
| image_047.png | no | **непригоден** | 0.5878 | blur: text edges are blurred (edge spread 2.71px, limit 1.20px) |
| image_048.jpg | yes | пригоден | 0.9715 | - |
| image_049.png | yes | пригоден | 0.9941 | - |
| image_050.jpg | borderline | **непригоден** | 0.6564 | blur: 44% of the text area is blurred |

## PDF

| документ | страниц | пригоден | оценка | проблемные страницы | пустые страницы |
|---|---|---|---|---|---|
| document_001.pdf | 4 | **нет** | 0.7833 | 1, 3 | - |
| document_002.pdf | 10 | **нет** | 0.9488 | 10 | - |
| document_003.pdf | 4 | да | 0.9394 | - | - |
| document_004.pdf | 10 | **нет** | 0.9259 | 6 | - |
| document_005.pdf | 5 | **нет** | 0.8534 | 3, 5 | - |
| document_006.pdf | 10 | **нет** | 0.944 | 1 | 5, 6 |
| document_007.pdf | 8 | **нет** | 0.8944 | 3, 5 | - |
| document_008.pdf | 7 | **нет** | 0.8114 | 3, 4, 7 | - |
| document_009.pdf | 7 | **нет** | 0.8553 | 2, 6 | 3 |
| document_010.pdf | 3 | да | 0.9286 | - | - |
| document_011.pdf | 5 | **нет** | 0.8254 | 1, 3 | - |
| document_012.pdf | 6 | да | 0.97 | - | - |
| document_013.pdf | 9 | **нет** | 0.904 | 4, 8 | 2 |
| document_014.pdf | 8 | **нет** | 0.8461 | 2, 3, 5 | 6 |
| document_015.pdf | 2 | **нет** | 0.7939 | 2 | - |
| document_016.pdf | 7 | **нет** | 0.9163 | 3 | - |
| document_017.pdf | 8 | **нет** | 0.8693 | 3, 5 | 7 |
| document_018.pdf | 2 | да | 0.8424 | - | 1 |
| document_019.pdf | 2 | да | 1.0 | - | - |
| document_020.pdf | 5 | да | 0.9995 | - | 4 |
