# MediaSpeech TR Local Manifest

Date: 2026-06-22

Dataset root inspected:

```text
C:\Users\Serhat\Downloads\TR
```

Detected nested data folder:

```text
C:\Users\Serhat\Downloads\TR\TR
```

## Summary

| Item | Finding |
|---|---:|
| Audio files detected | 2,513 |
| Transcript/reference files detected | 2,513 |
| Audio extension | `.wav` |
| Reference extension | `.txt` |
| Pairing pattern | same filename stem |
| Automatically matchable references | yes, 2,513/2,513 |
| Metadata files detected | none beyond per-audio `.txt` references |
| Full dataset copied into repo | no |

## Structure

The folder contains one nested `TR` directory. Inside that directory, each item appears as a pair:

```text
<uuid>.wav
<uuid>.txt
```

Example:

```text
C:\Users\Serhat\Downloads\TR\TR\0044ad54-892f-4d23-a75b-0e22eb837914.wav
C:\Users\Serhat\Downloads\TR\TR\0044ad54-892f-4d23-a75b-0e22eb837914.txt
```

The pairing is obvious and can be matched automatically by replacing `.wav` with `.txt`.

## Sample Files

### Sample 1

Audio:

```text
C:\Users\Serhat\Downloads\TR\TR\0044ad54-892f-4d23-a75b-0e22eb837914.wav
```

Reference:

```text
C:\Users\Serhat\Downloads\TR\TR\0044ad54-892f-4d23-a75b-0e22eb837914.txt
```

Observed WAV facts:

- Duration: about 14.500 seconds
- Sample rate: 16,000 Hz
- Channels: 1
- Sample width: 16-bit PCM

Reference excerpt:

```text
böyle el çizimi olağanüstü bir adım ilk defa kanuni sultan süleyman'ı süleymaniye'si var oysa onun selimiye'si var edirne'de mimar sinan yapısı ve türbesiz külliye çünkü türbesi ayasofya oluyor yani
```

### Sample 2

Audio:

```text
C:\Users\Serhat\Downloads\TR\TR\00482994-a9e2-4ec9-aa6d-a1960c82eeb9.wav
```

Reference:

```text
C:\Users\Serhat\Downloads\TR\TR\00482994-a9e2-4ec9-aa6d-a1960c82eeb9.txt
```

Observed WAV facts:

- Duration: about 14.600 seconds
- Sample rate: 16,000 Hz
- Channels: 1
- Sample width: 16-bit PCM

Reference excerpt:

```text
vemeler on bir mayıs'tan bu yana açıklar işçi sendikalarının iddiasına göre avm çalışanlarının virüse yakalandığına dair ihbarlar geliyordu şimdi ise dikkatler karantinaya alınan mağazalara döndü
```

### Sample 3

Audio:

```text
C:\Users\Serhat\Downloads\TR\TR\004ebcc0-8263-4983-8c1f-ae1f4bcf79cd.wav
```

Reference:

```text
C:\Users\Serhat\Downloads\TR\TR\004ebcc0-8263-4983-8c1f-ae1f4bcf79cd.txt
```

Observed WAV facts:

- Duration: about 14.800 seconds
- Sample rate: 16,000 Hz
- Channels: 1
- Sample width: 16-bit PCM

Reference excerpt:

```text
yerel yönetimler yasasında bazı maddelerin değiştirilmesi kararlaştırılmıştı ak parti taslağı hazırladı o taslakta belediye başkanlarının akrabalarının belediyelerde işe girişlerine yasak getirilmesi
```

## License / Source Note

The inspected folder did not contain an obvious license, README, metadata JSON, CSV, or TSV file. The user identified this folder as the downloaded Turkish MediaSpeech dataset. The benchmark report should therefore cite it as a local MediaSpeech TR dataset folder, but the license/source details should be verified from the original download page before redistribution or publication.

## Benchmark Suitability

This dataset is suitable for Turkish ASR/media-speech benchmarking because:

- audio and references are paired automatically,
- references are available as local `.txt` files,
- audio is already 16 kHz mono WAV,
- files are short enough for safe subset tests.

Claim boundary:

- This appears to be clean/media speech, not real meeting-room audio.
- It must not be used as proof of real Turkish meeting-room readiness.
- Project-specific meeting-room audio remains a separate required benchmark.

## Recommended Subset Command

```powershell
python scripts/run_project_turkish_transcription_benchmark.py `
  --dataset-root "C:\Users\Serhat\Downloads\TR" `
  --max-files 5 `
  --dataset-name mediaspeech_tr `
  --models large-v3 large-v3-turbo `
  --profiles max_quality `
  --audio-kind test_speech `
  --output docs/reports/2026-06-30/transcription-benchmarks/MEDIASPEECH_TR_TRANSCRIPTION_BENCHMARK.md
```
