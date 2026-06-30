# mediaspeech_tr Turkish Transcription Benchmark

Date: 2026-06-22

Status: BENCHMARK_RUN

Dataset root path: `C:\Users\Serhat\Downloads\TR`
Files discovered: 2513
Files tested: 5
Audio type: `test_speech`
Human reference transcripts matched: 5/5

Tested files:

- `C:\Users\Serhat\Downloads\TR\TR\0044ad54-892f-4d23-a75b-0e22eb837914.wav` -> `C:\Users\Serhat\Downloads\TR\TR\0044ad54-892f-4d23-a75b-0e22eb837914.txt`
- `C:\Users\Serhat\Downloads\TR\TR\00482994-a9e2-4ec9-aa6d-a1960c82eeb9.wav` -> `C:\Users\Serhat\Downloads\TR\TR\00482994-a9e2-4ec9-aa6d-a1960c82eeb9.txt`
- `C:\Users\Serhat\Downloads\TR\TR\004ebcc0-8263-4983-8c1f-ae1f4bcf79cd.wav` -> `C:\Users\Serhat\Downloads\TR\TR\004ebcc0-8263-4983-8c1f-ae1f4bcf79cd.txt`
- `C:\Users\Serhat\Downloads\TR\TR\0067dc03-b29d-4a66-8260-a3178b176635.wav` -> `C:\Users\Serhat\Downloads\TR\TR\0067dc03-b29d-4a66-8260-a3178b176635.txt`
- `C:\Users\Serhat\Downloads\TR\TR\00963752-3348-4f84-9161-650d2743d007.wav` -> `C:\Users\Serhat\Downloads\TR\TR\00963752-3348-4f84-9161-650d2743d007.txt`

Claim boundary:

- This dataset can support Turkish ASR/media-speech benchmarking.
- This dataset must not be treated as proof of real meeting-room readiness.
- Project-specific real meeting-room audio remains a separate required benchmark.

Local-first controls:

- Faster-Whisper only; no cloud STT.
- `language=tr`.
- `transcript_cleanup_mode=conservative`.
- Faster-Whisper internal VAD disabled.
- External VAD requested as `silero`.
- `ASR_STATUS=MOCK_FALLBACK` invalidates the benchmark.

## Configuration Summary

| Model | Profile | Tested Files | Valid Results | Avg Time | Avg WER | Avg CER | Errors |
|---|---|---:|---:|---:|---:|---:|---:|
| large-v3 | max_quality | 5 | 5 | 28.570s | 0.1706 | 0.0917 | 0 |
| large-v3-turbo | max_quality | 5 | 5 | 10.614s | 0.1407 | 0.0826 | 0 |

## Per-File Summary Table

| Sample | Model | Profile | ASR Status | Mock Fallback | VAD | Beam | Compute | Preprocessing | Time | WER | CER | Error |
|---|---|---|---|---|---|---:|---|---|---:|---:|---:|---|
| TR/0044ad54-892f-4d23-a75b-0e22eb837914 | large-v3 | max_quality | ASR_STATUS=OK | False | silero | 8 | int8 | ffmpeg_normalized | 39.515s | 0.3103 | 0.1061 |  |
| TR/00482994-a9e2-4ec9-aa6d-a1960c82eeb9 | large-v3 | max_quality | ASR_STATUS=OK | False | silero | 8 | int8 | ffmpeg_normalized | 23.622s | 0.2000 | 0.0718 |  |
| TR/004ebcc0-8263-4983-8c1f-ae1f4bcf79cd | large-v3 | max_quality | ASR_STATUS=OK | False | silero | 8 | int8 | ffmpeg_normalized | 24.778s | 0.0000 | 0.0201 |  |
| TR/0067dc03-b29d-4a66-8260-a3178b176635 | large-v3 | max_quality | ASR_STATUS=OK | False | silero | 8 | int8 | ffmpeg_normalized | 35.409s | 0.2000 | 0.1447 |  |
| TR/00963752-3348-4f84-9161-650d2743d007 | large-v3 | max_quality | ASR_STATUS=OK | False | silero | 8 | int8 | ffmpeg_normalized | 19.526s | 0.1429 | 0.1161 |  |
| TR/0044ad54-892f-4d23-a75b-0e22eb837914 | large-v3-turbo | max_quality | ASR_STATUS=OK | False | silero | 8 | int8 | ffmpeg_normalized | 16.896s | 0.1034 | 0.0707 |  |
| TR/00482994-a9e2-4ec9-aa6d-a1960c82eeb9 | large-v3-turbo | max_quality | ASR_STATUS=OK | False | silero | 8 | int8 | ffmpeg_normalized | 9.200s | 0.2000 | 0.0667 |  |
| TR/004ebcc0-8263-4983-8c1f-ae1f4bcf79cd | large-v3-turbo | max_quality | ASR_STATUS=OK | False | silero | 8 | int8 | ffmpeg_normalized | 8.942s | 0.0000 | 0.0151 |  |
| TR/0067dc03-b29d-4a66-8260-a3178b176635 | large-v3-turbo | max_quality | ASR_STATUS=OK | False | silero | 8 | int8 | ffmpeg_normalized | 9.172s | 0.2571 | 0.1489 |  |
| TR/00963752-3348-4f84-9161-650d2743d007 | large-v3-turbo | max_quality | ASR_STATUS=OK | False | silero | 8 | int8 | ffmpeg_normalized | 8.859s | 0.1429 | 0.1116 |  |

## Recommended Default Configuration

Reference-based recommendation from this subset: `large-v3-turbo + max_quality` (avg cleaned WER=0.1407, avg cleaned CER=0.0826). This applies only to the tested media-speech subset and must not be treated as real meeting-room readiness.

## Per-Configuration And Per-File Results

### TR/0044ad54-892f-4d23-a75b-0e22eb837914 / large-v3 + max_quality

- Audio path: `C:\Users\Serhat\Downloads\TR\TR\0044ad54-892f-4d23-a75b-0e22eb837914.wav`
- Reference path: `C:\Users\Serhat\Downloads\TR\TR\0044ad54-892f-4d23-a75b-0e22eb837914.txt`
- ASR status: `ASR_STATUS=OK`
- Mock fallback used: `False`
- Preprocessing status: `ffmpeg_normalized`
- VAD provider: `silero`
- Beam size: `8`
- Compute type: `int8`
- Processing time: `39.515s`

Reference metrics:

- Raw WER: 0.3103
- Raw CER: 0.1010
- Raw notable substitutions: [{'reference': 'adım', 'actual': 'i'}, {'reference': 'ilk', 'actual': 'lk'}, {'reference': 'kanuni', 'actual': 'kanduni'}, {'reference': "süleyman'ı", 'actual': "süleyman'ın"}, {'reference': "selimiye'si", 'actual': 'selimiyesi'}, {'reference': 'yapısı', 'actual': 'yekisi'}, {'reference': 'türbesi', 'actual': 'türbesiz'}]
- Raw notable deletions: ['yani']
- Raw notable insertions: ['abim']
- Cleaned WER: 0.3103
- Cleaned CER: 0.1061
- Cleaned notable substitutions: [{'reference': 'adım', 'actual': 'i'}, {'reference': 'ilk', 'actual': 'lk'}, {'reference': 'kanuni', 'actual': 'kanduni'}, {'reference': "süleyman'ı", 'actual': "süleyman'ın"}, {'reference': "selimiye'si", 'actual': 'selimiyesi'}, {'reference': 'yapısı', 'actual': 'yekisi'}, {'reference': 'türbesi', 'actual': 'türbesiz'}]
- Cleaned notable deletions: ['yani']
- Cleaned notable insertions: ['abim']

Turkish character preservation:

| Character | Raw Present | Cleaned Present |
|---|---|---|
| ç | True | True |
| ğ | True | True |
| ı | True | True |
| İ | True | True |
| ö | True | True |
| ş | False | False |
| ü | True | True |

Technical term preservation:

| Term | Raw Present | Cleaned Present |
|---|---|---|
| Collective MindGraph | False | False |
| FastAPI | False | False |
| SQLite | False | False |
| PySide6 | False | False |
| VAD | False | False |
| transcript | False | False |
| aksiyon | False | False |
| karar | False | False |

VAD clipping notes:

- No obvious clipping signal from simple VAD boundary heuristics; manual listening still required.

Reference transcript:

```text
böyle el çizimi olağanüstü bir adım ilk defa kanuni sultan süleyman'ı süleymaniye'si var oysa onun selimiye'si var edirne'de mimar sinan yapısı ve türbesiz külliye çünkü türbesi ayasofya oluyor yani
```

Raw transcript:

```text
böyle el çizimi olağanüstü bir abim. İlk defa Kanduni Sultan Süleyman'ın Süleymaniye'si var. Oysa
onun Selimiyesi var Edirne'de, Mimar Sinan Yekisi ve Türbesiz Külliye, çünkü Türbesiz Ayasofya oluyor.
```

Cleaned transcript:

```text
Böyle el çizimi olağanüstü bir abim. İlk defa Kanduni Sultan Süleyman'ın Süleymaniye'si var. Oysa.
Onun Selimiyesi var Edirne'de, Mimar Sinan Yekisi ve Türbesiz Külliye, çünkü Türbesiz Ayasofya oluyor.
```

### TR/00482994-a9e2-4ec9-aa6d-a1960c82eeb9 / large-v3 + max_quality

- Audio path: `C:\Users\Serhat\Downloads\TR\TR\00482994-a9e2-4ec9-aa6d-a1960c82eeb9.wav`
- Reference path: `C:\Users\Serhat\Downloads\TR\TR\00482994-a9e2-4ec9-aa6d-a1960c82eeb9.txt`
- ASR status: `ASR_STATUS=OK`
- Mock fallback used: `False`
- Preprocessing status: `ffmpeg_normalized`
- VAD provider: `silero`
- Beam size: `8`
- Compute type: `int8`
- Processing time: `23.622s`

Reference metrics:

- Raw WER: 0.2000
- Raw CER: 0.0718
- Raw notable substitutions: [{'reference': 'on', 'actual': "avm'ler"}, {'reference': 'bir', 'actual': '11'}, {'reference': 'işçi', 'actual': 'şçi'}]
- Raw notable deletions: ['vemeler']
- Raw notable insertions: ['i']
- Cleaned WER: 0.2000
- Cleaned CER: 0.0718
- Cleaned notable substitutions: [{'reference': 'on', 'actual': "avm'ler"}, {'reference': 'bir', 'actual': '11'}, {'reference': 'işçi', 'actual': 'şçi'}]
- Cleaned notable deletions: ['vemeler']
- Cleaned notable insertions: ['i']

Turkish character preservation:

| Character | Raw Present | Cleaned Present |
|---|---|---|
| ç | True | True |
| ğ | True | True |
| ı | True | True |
| İ | True | True |
| ö | True | True |
| ş | True | True |
| ü | True | True |

Technical term preservation:

| Term | Raw Present | Cleaned Present |
|---|---|---|
| Collective MindGraph | False | False |
| FastAPI | False | False |
| SQLite | False | False |
| PySide6 | False | False |
| VAD | False | False |
| transcript | False | False |
| aksiyon | False | False |
| karar | False | False |

VAD clipping notes:

- First VAD region starts at 0.65s; verify no opening word was clipped.

Reference transcript:

```text
vemeler on bir mayıs'tan bu yana açıklar işçi sendikalarının iddiasına göre avm çalışanlarının virüse yakalandığına dair ihbarlar geliyordu şimdi ise dikkatler karantinaya alınan mağazalara döndü
```

Raw transcript:

```text
AVM'ler 11 Mayıs'tan bu yana açıklar. İşçi sendikalarının iddiasına göre AVM çalışanlarının virüse yakalandığına dair ihbarlar geliyordu.
Şimdi ise dikkatler, karantinaya alınan mağazalara döndü.
```

Cleaned transcript:

```text
AVM'ler 11 Mayıs'tan bu yana açıklar. İşçi sendikalarının iddiasına göre AVM çalışanlarının virüse yakalandığına dair ihbarlar geliyordu.
Şimdi ise dikkatler, karantinaya alınan mağazalara döndü.
```

### TR/004ebcc0-8263-4983-8c1f-ae1f4bcf79cd / large-v3 + max_quality

- Audio path: `C:\Users\Serhat\Downloads\TR\TR\004ebcc0-8263-4983-8c1f-ae1f4bcf79cd.wav`
- Reference path: `C:\Users\Serhat\Downloads\TR\TR\004ebcc0-8263-4983-8c1f-ae1f4bcf79cd.txt`
- ASR status: `ASR_STATUS=OK`
- Mock fallback used: `False`
- Preprocessing status: `ffmpeg_normalized`
- VAD provider: `silero`
- Beam size: `8`
- Compute type: `int8`
- Processing time: `24.778s`

Reference metrics:

- Raw WER: 0.0000
- Raw CER: 0.0201
- Raw notable substitutions: []
- Raw notable deletions: []
- Raw notable insertions: []
- Cleaned WER: 0.0000
- Cleaned CER: 0.0201
- Cleaned notable substitutions: []
- Cleaned notable deletions: []
- Cleaned notable insertions: []

Turkish character preservation:

| Character | Raw Present | Cleaned Present |
|---|---|---|
| ç | False | False |
| ğ | True | True |
| ı | True | True |
| İ | False | False |
| ö | True | True |
| ş | True | True |
| ü | False | False |

Technical term preservation:

| Term | Raw Present | Cleaned Present |
|---|---|---|
| Collective MindGraph | False | False |
| FastAPI | False | False |
| SQLite | False | False |
| PySide6 | False | False |
| VAD | False | False |
| transcript | False | False |
| aksiyon | False | False |
| karar | True | True |

VAD clipping notes:

- First VAD region starts at 1.64s; verify no opening word was clipped.

Reference transcript:

```text
yerel yönetimler yasasında bazı maddelerin değiştirilmesi kararlaştırılmıştı ak parti taslağı hazırladı o taslakta belediye başkanlarının akrabalarının belediyelerde işe girişlerine yasak getirilmesi
```

Raw transcript:

```text
Yerel yönetimler yasasında bazı maddelerin değiştirilmesi kararlaştırılmıştı. AK Parti taslağı hazırladı. O taslakta belediye başkanlarının, akrabalarının belediyelerde işe girişlerine yasak getirilmesi.
```

Cleaned transcript:

```text
Yerel yönetimler yasasında bazı maddelerin değiştirilmesi kararlaştırılmıştı. AK Parti taslağı hazırladı. O taslakta belediye başkanlarının, akrabalarının belediyelerde işe girişlerine yasak getirilmesi.
```

### TR/0067dc03-b29d-4a66-8260-a3178b176635 / large-v3 + max_quality

- Audio path: `C:\Users\Serhat\Downloads\TR\TR\0067dc03-b29d-4a66-8260-a3178b176635.wav`
- Reference path: `C:\Users\Serhat\Downloads\TR\TR\0067dc03-b29d-4a66-8260-a3178b176635.txt`
- ASR status: `ASR_STATUS=OK`
- Mock fallback used: `False`
- Preprocessing status: `ffmpeg_normalized`
- VAD provider: `silero`
- Beam size: `8`
- Compute type: `int8`
- Processing time: `35.409s`

Reference metrics:

- Raw WER: 0.2000
- Raw CER: 0.1404
- Raw notable substitutions: [{'reference': 'nerdeyse', 'actual': 'neredeyse'}, {'reference': 'ana', 'actual': 'an'}, {'reference': 'yüz', 'actual': 'tek'}, {'reference': 'ek', 'actual': 'gösteriyorum'}]
- Raw notable deletions: []
- Raw notable insertions: ['maaşları', 'da', 'yüzde']
- Cleaned WER: 0.2000
- Cleaned CER: 0.1447
- Cleaned notable substitutions: [{'reference': 'nerdeyse', 'actual': 'neredeyse'}, {'reference': 'ana', 'actual': 'an'}, {'reference': 'yüz', 'actual': 'tek'}, {'reference': 'ek', 'actual': 'gösteriyorum'}]
- Cleaned notable deletions: []
- Cleaned notable insertions: ['maaşları', 'da', 'yüzde']

Turkish character preservation:

| Character | Raw Present | Cleaned Present |
|---|---|---|
| ç | True | True |
| ğ | True | True |
| ı | True | True |
| İ | False | False |
| ö | True | True |
| ş | True | True |
| ü | True | True |

Technical term preservation:

| Term | Raw Present | Cleaned Present |
|---|---|---|
| Collective MindGraph | False | False |
| FastAPI | False | False |
| SQLite | False | False |
| PySide6 | False | False |
| VAD | False | False |
| transcript | False | False |
| aksiyon | False | False |
| karar | False | False |

VAD clipping notes:

- No obvious clipping signal from simple VAD boundary heuristics; manual listening still required.

Reference transcript:

```text
nerdeyse çalıştıkları döneme yaklaşacak çalışırken aldığı maaşla emekli olduktan sonra aldığı maaş arasında çok fazla bir fark olmayacak ama şu ana baktığımızda neredeyse yarı yarıya yakın bir düşüş meydana getiriyor üç bin altı yüz ek
```

Raw transcript:

```text
maaşları da neredeyse çalıştıkları döneme yaklaşacak. Çalışırken aldığı maaşla emekli olduktan sonra aldığı maaş arasında çok fazla bir fark olmayacak ama şu an baktığımızda neredeyse yarı yarıya yakın bir düşüş meydana getiriyor. Üç bin altı yüzde
Tek gösteriyorum.
```

Cleaned transcript:

```text
Maaşları da neredeyse çalıştıkları döneme yaklaşacak. Çalışırken aldığı maaşla emekli olduktan sonra aldığı maaş arasında çok fazla bir fark olmayacak ama şu an baktığımızda neredeyse yarı yarıya yakın bir düşüş meydana getiriyor. Üç bin altı yüzde.
Tek gösteriyorum.
```

### TR/00963752-3348-4f84-9161-650d2743d007 / large-v3 + max_quality

- Audio path: `C:\Users\Serhat\Downloads\TR\TR\00963752-3348-4f84-9161-650d2743d007.wav`
- Reference path: `C:\Users\Serhat\Downloads\TR\TR\00963752-3348-4f84-9161-650d2743d007.txt`
- ASR status: `ASR_STATUS=OK`
- Mock fallback used: `False`
- Preprocessing status: `ffmpeg_normalized`
- VAD provider: `silero`
- Beam size: `8`
- Compute type: `int8`
- Processing time: `19.526s`

Reference metrics:

- Raw WER: 0.1429
- Raw CER: 0.1161
- Raw notable substitutions: [{'reference': 'yargıtayın', 'actual': "yargıtay'ın"}]
- Raw notable deletions: ['anayasanın', 'seksen', 'üç']
- Raw notable insertions: []
- Cleaned WER: 0.1429
- Cleaned CER: 0.1161
- Cleaned notable substitutions: [{'reference': 'yargıtayın', 'actual': "yargıtay'ın"}]
- Cleaned notable deletions: ['anayasanın', 'seksen', 'üç']
- Cleaned notable insertions: []

Turkish character preservation:

| Character | Raw Present | Cleaned Present |
|---|---|---|
| ç | True | True |
| ğ | True | True |
| ı | True | True |
| İ | False | False |
| ö | False | False |
| ş | True | True |
| ü | False | False |

Technical term preservation:

| Term | Raw Present | Cleaned Present |
|---|---|---|
| Collective MindGraph | False | False |
| FastAPI | False | False |
| SQLite | False | False |
| PySide6 | False | False |
| VAD | False | False |
| transcript | False | False |
| aksiyon | False | False |
| karar | True | True |

VAD clipping notes:

- First VAD region starts at 0.62s; verify no opening word was clipped.

Reference transcript:

```text
o madde yargıtayın enis berberoğlu hakkındaki gerekçeli kararında da açıkça yazılı yargıtay berberoğlu hakkındaki yerel mahkeme kararını onarken cezanın uygulanması için vekilliği bittikten sonra demişti anayasanın seksen üç
```

Raw transcript:

```text
O madde, Yargıtay'ın Enis Berberoğlu hakkındaki gerekçeli kararında da açıkça yazılı.
Yargıtay, Berberoğlu hakkındaki yerel mahkeme kararını onarken, cezanın uygulanması için vekilliği bittikten sonra demişti.
```

Cleaned transcript:

```text
O madde, Yargıtay'ın Enis Berberoğlu hakkındaki gerekçeli kararında da açıkça yazılı.
Yargıtay, Berberoğlu hakkındaki yerel mahkeme kararını onarken, cezanın uygulanması için vekilliği bittikten sonra demişti.
```

### TR/0044ad54-892f-4d23-a75b-0e22eb837914 / large-v3-turbo + max_quality

- Audio path: `C:\Users\Serhat\Downloads\TR\TR\0044ad54-892f-4d23-a75b-0e22eb837914.wav`
- Reference path: `C:\Users\Serhat\Downloads\TR\TR\0044ad54-892f-4d23-a75b-0e22eb837914.txt`
- ASR status: `ASR_STATUS=OK`
- Mock fallback used: `False`
- Preprocessing status: `ffmpeg_normalized`
- VAD provider: `silero`
- Beam size: `8`
- Compute type: `int8`
- Processing time: `16.896s`

Reference metrics:

- Raw WER: 0.1034
- Raw CER: 0.0808
- Raw notable substitutions: [{'reference': 'ilk', 'actual': 'lk'}]
- Raw notable deletions: ['yani']
- Raw notable insertions: ['i']
- Cleaned WER: 0.1034
- Cleaned CER: 0.0707
- Cleaned notable substitutions: [{'reference': 'ilk', 'actual': 'lk'}]
- Cleaned notable deletions: ['yani']
- Cleaned notable insertions: ['i']

Turkish character preservation:

| Character | Raw Present | Cleaned Present |
|---|---|---|
| ç | True | True |
| ğ | True | True |
| ı | True | True |
| İ | True | True |
| ö | True | True |
| ş | False | False |
| ü | True | True |

Technical term preservation:

| Term | Raw Present | Cleaned Present |
|---|---|---|
| Collective MindGraph | False | False |
| FastAPI | False | False |
| SQLite | False | False |
| PySide6 | False | False |
| VAD | False | False |
| transcript | False | False |
| aksiyon | False | False |
| karar | False | False |

VAD clipping notes:

- No obvious clipping signal from simple VAD boundary heuristics; manual listening still required.

Reference transcript:

```text
böyle el çizimi olağanüstü bir adım ilk defa kanuni sultan süleyman'ı süleymaniye'si var oysa onun selimiye'si var edirne'de mimar sinan yapısı ve türbesiz külliye çünkü türbesi ayasofya oluyor yani
```

Raw transcript:

```text
Böyle, el çizimi, olağanüstü bir adım. İlk defa, Kanuni Sultan Süleyman'ı Süleymaniye'si var, oysa...
onun Selimiye'si var Edirne'de, Mimar Sinan yapısı ve türbesiz külliye, çünkü türbesi Ayasofya oluyor.
```

Cleaned transcript:

```text
Böyle, el çizimi, olağanüstü bir adım. İlk defa, Kanuni Sultan Süleyman'ı Süleymaniye'si var, oysa.
Onun Selimiye'si var Edirne'de, Mimar Sinan yapısı ve türbesiz külliye, çünkü türbesi Ayasofya oluyor.
```

### TR/00482994-a9e2-4ec9-aa6d-a1960c82eeb9 / large-v3-turbo + max_quality

- Audio path: `C:\Users\Serhat\Downloads\TR\TR\00482994-a9e2-4ec9-aa6d-a1960c82eeb9.wav`
- Reference path: `C:\Users\Serhat\Downloads\TR\TR\00482994-a9e2-4ec9-aa6d-a1960c82eeb9.txt`
- ASR status: `ASR_STATUS=OK`
- Mock fallback used: `False`
- Preprocessing status: `ffmpeg_normalized`
- VAD provider: `silero`
- Beam size: `8`
- Compute type: `int8`
- Processing time: `9.200s`

Reference metrics:

- Raw WER: 0.2000
- Raw CER: 0.0667
- Raw notable substitutions: [{'reference': 'on', 'actual': "avm'ler"}, {'reference': 'bir', 'actual': '11'}, {'reference': 'işçi', 'actual': 'şçi'}]
- Raw notable deletions: ['vemeler']
- Raw notable insertions: ['i']
- Cleaned WER: 0.2000
- Cleaned CER: 0.0667
- Cleaned notable substitutions: [{'reference': 'on', 'actual': "avm'ler"}, {'reference': 'bir', 'actual': '11'}, {'reference': 'işçi', 'actual': 'şçi'}]
- Cleaned notable deletions: ['vemeler']
- Cleaned notable insertions: ['i']

Turkish character preservation:

| Character | Raw Present | Cleaned Present |
|---|---|---|
| ç | True | True |
| ğ | True | True |
| ı | True | True |
| İ | True | True |
| ö | True | True |
| ş | True | True |
| ü | True | True |

Technical term preservation:

| Term | Raw Present | Cleaned Present |
|---|---|---|
| Collective MindGraph | False | False |
| FastAPI | False | False |
| SQLite | False | False |
| PySide6 | False | False |
| VAD | False | False |
| transcript | False | False |
| aksiyon | False | False |
| karar | False | False |

VAD clipping notes:

- First VAD region starts at 0.65s; verify no opening word was clipped.

Reference transcript:

```text
vemeler on bir mayıs'tan bu yana açıklar işçi sendikalarının iddiasına göre avm çalışanlarının virüse yakalandığına dair ihbarlar geliyordu şimdi ise dikkatler karantinaya alınan mağazalara döndü
```

Raw transcript:

```text
AVM'ler 11 Mayıs'tan bu yana açıklar. İşçi sendikalarının iddiasına göre AVM çalışanlarının virüse yakalandığına dair ihbarlar geliyordu.
Şimdi ise dikkatler karantinaya alınan mağazalara döndü.
```

Cleaned transcript:

```text
AVM'ler 11 Mayıs'tan bu yana açıklar. İşçi sendikalarının iddiasına göre AVM çalışanlarının virüse yakalandığına dair ihbarlar geliyordu.
Şimdi ise dikkatler karantinaya alınan mağazalara döndü.
```

### TR/004ebcc0-8263-4983-8c1f-ae1f4bcf79cd / large-v3-turbo + max_quality

- Audio path: `C:\Users\Serhat\Downloads\TR\TR\004ebcc0-8263-4983-8c1f-ae1f4bcf79cd.wav`
- Reference path: `C:\Users\Serhat\Downloads\TR\TR\004ebcc0-8263-4983-8c1f-ae1f4bcf79cd.txt`
- ASR status: `ASR_STATUS=OK`
- Mock fallback used: `False`
- Preprocessing status: `ffmpeg_normalized`
- VAD provider: `silero`
- Beam size: `8`
- Compute type: `int8`
- Processing time: `8.942s`

Reference metrics:

- Raw WER: 0.0000
- Raw CER: 0.0151
- Raw notable substitutions: []
- Raw notable deletions: []
- Raw notable insertions: []
- Cleaned WER: 0.0000
- Cleaned CER: 0.0151
- Cleaned notable substitutions: []
- Cleaned notable deletions: []
- Cleaned notable insertions: []

Turkish character preservation:

| Character | Raw Present | Cleaned Present |
|---|---|---|
| ç | False | False |
| ğ | True | True |
| ı | True | True |
| İ | False | False |
| ö | True | True |
| ş | True | True |
| ü | False | False |

Technical term preservation:

| Term | Raw Present | Cleaned Present |
|---|---|---|
| Collective MindGraph | False | False |
| FastAPI | False | False |
| SQLite | False | False |
| PySide6 | False | False |
| VAD | False | False |
| transcript | False | False |
| aksiyon | False | False |
| karar | True | True |

VAD clipping notes:

- First VAD region starts at 1.64s; verify no opening word was clipped.

Reference transcript:

```text
yerel yönetimler yasasında bazı maddelerin değiştirilmesi kararlaştırılmıştı ak parti taslağı hazırladı o taslakta belediye başkanlarının akrabalarının belediyelerde işe girişlerine yasak getirilmesi
```

Raw transcript:

```text
Yerel yönetimler yasasında bazı maddelerin değiştirilmesi kararlaştırılmıştı. AK Parti taslağı hazırladı. O taslakta belediye başkanlarının akrabalarının belediyelerde işe girişlerine yasak getirilmesi.
```

Cleaned transcript:

```text
Yerel yönetimler yasasında bazı maddelerin değiştirilmesi kararlaştırılmıştı. AK Parti taslağı hazırladı. O taslakta belediye başkanlarının akrabalarının belediyelerde işe girişlerine yasak getirilmesi.
```

### TR/0067dc03-b29d-4a66-8260-a3178b176635 / large-v3-turbo + max_quality

- Audio path: `C:\Users\Serhat\Downloads\TR\TR\0067dc03-b29d-4a66-8260-a3178b176635.wav`
- Reference path: `C:\Users\Serhat\Downloads\TR\TR\0067dc03-b29d-4a66-8260-a3178b176635.txt`
- ASR status: `ASR_STATUS=OK`
- Mock fallback used: `False`
- Preprocessing status: `ffmpeg_normalized`
- VAD provider: `silero`
- Beam size: `8`
- Compute type: `int8`
- Processing time: `9.172s`

Reference metrics:

- Raw WER: 0.2571
- Raw CER: 0.1489
- Raw notable substitutions: [{'reference': 'nerdeyse', 'actual': 'neredeyse'}, {'reference': 'ana', 'actual': 'an'}]
- Raw notable deletions: ['üç', 'bin', 'altı', 'yüz', 'ek']
- Raw notable insertions: ['maaşları', 'da']
- Cleaned WER: 0.2571
- Cleaned CER: 0.1489
- Cleaned notable substitutions: [{'reference': 'nerdeyse', 'actual': 'neredeyse'}, {'reference': 'ana', 'actual': 'an'}]
- Cleaned notable deletions: ['üç', 'bin', 'altı', 'yüz', 'ek']
- Cleaned notable insertions: ['maaşları', 'da']

Turkish character preservation:

| Character | Raw Present | Cleaned Present |
|---|---|---|
| ç | True | True |
| ğ | True | True |
| ı | True | True |
| İ | False | False |
| ö | True | True |
| ş | True | True |
| ü | True | True |

Technical term preservation:

| Term | Raw Present | Cleaned Present |
|---|---|---|
| Collective MindGraph | False | False |
| FastAPI | False | False |
| SQLite | False | False |
| PySide6 | False | False |
| VAD | False | False |
| transcript | False | False |
| aksiyon | False | False |
| karar | False | False |

VAD clipping notes:

- No obvious clipping signal from simple VAD boundary heuristics; manual listening still required.

Reference transcript:

```text
nerdeyse çalıştıkları döneme yaklaşacak çalışırken aldığı maaşla emekli olduktan sonra aldığı maaş arasında çok fazla bir fark olmayacak ama şu ana baktığımızda neredeyse yarı yarıya yakın bir düşüş meydana getiriyor üç bin altı yüz ek
```

Raw transcript:

```text
Maaşları da neredeyse çalıştıkları döneme yaklaşacak.
Çalışırken aldığı maaşla, emekli olduktan sonra aldığı maaş arasında çok fazla bir fark olmayacak ama şu an baktığımızda neredeyse yarı yarıya yakın bir düşüş meydana getiriyor.
```

Cleaned transcript:

```text
Maaşları da neredeyse çalıştıkları döneme yaklaşacak.
Çalışırken aldığı maaşla, emekli olduktan sonra aldığı maaş arasında çok fazla bir fark olmayacak ama şu an baktığımızda neredeyse yarı yarıya yakın bir düşüş meydana getiriyor.
```

### TR/00963752-3348-4f84-9161-650d2743d007 / large-v3-turbo + max_quality

- Audio path: `C:\Users\Serhat\Downloads\TR\TR\00963752-3348-4f84-9161-650d2743d007.wav`
- Reference path: `C:\Users\Serhat\Downloads\TR\TR\00963752-3348-4f84-9161-650d2743d007.txt`
- ASR status: `ASR_STATUS=OK`
- Mock fallback used: `False`
- Preprocessing status: `ffmpeg_normalized`
- VAD provider: `silero`
- Beam size: `8`
- Compute type: `int8`
- Processing time: `8.859s`

Reference metrics:

- Raw WER: 0.1429
- Raw CER: 0.1116
- Raw notable substitutions: [{'reference': 'yargıtayın', 'actual': "yargıtay'ın"}]
- Raw notable deletions: ['anayasanın', 'seksen', 'üç']
- Raw notable insertions: []
- Cleaned WER: 0.1429
- Cleaned CER: 0.1116
- Cleaned notable substitutions: [{'reference': 'yargıtayın', 'actual': "yargıtay'ın"}]
- Cleaned notable deletions: ['anayasanın', 'seksen', 'üç']
- Cleaned notable insertions: []

Turkish character preservation:

| Character | Raw Present | Cleaned Present |
|---|---|---|
| ç | True | True |
| ğ | True | True |
| ı | True | True |
| İ | False | False |
| ö | False | False |
| ş | True | True |
| ü | False | False |

Technical term preservation:

| Term | Raw Present | Cleaned Present |
|---|---|---|
| Collective MindGraph | False | False |
| FastAPI | False | False |
| SQLite | False | False |
| PySide6 | False | False |
| VAD | False | False |
| transcript | False | False |
| aksiyon | False | False |
| karar | True | True |

VAD clipping notes:

- First VAD region starts at 0.62s; verify no opening word was clipped.

Reference transcript:

```text
o madde yargıtayın enis berberoğlu hakkındaki gerekçeli kararında da açıkça yazılı yargıtay berberoğlu hakkındaki yerel mahkeme kararını onarken cezanın uygulanması için vekilliği bittikten sonra demişti anayasanın seksen üç
```

Raw transcript:

```text
O madde, Yargıtay'ın Enis Berberoğlu hakkındaki gerekçeli kararında da açıkça yazılı. Yargıtay, Berberoğlu hakkındaki yerel mahkeme kararını onarken cezanın uygulanması için vekilliği bittikten sonra demişti.
```

Cleaned transcript:

```text
O madde, Yargıtay'ın Enis Berberoğlu hakkındaki gerekçeli kararında da açıkça yazılı. Yargıtay, Berberoğlu hakkındaki yerel mahkeme kararını onarken cezanın uygulanması için vekilliği bittikten sonra demişti.
```

## Unresolved Issues

- Media-speech results do not prove real meeting-room readiness.
- If references were missing or failed to match, WER/CER for those files are unavailable.
- VAD clipping notes are heuristic and require manual listening review.
- Proper-noun/technical-term errors need manual review beyond the fixed term checklist.
