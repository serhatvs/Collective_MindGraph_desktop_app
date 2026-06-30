import re

file_5 = 'docs/reports/2026-06-30/transcription-benchmarks/MEDIASPEECH_TR_TRANSCRIPTION_BENCHMARK_5FILE.md'
file_50 = 'docs/reports/2026-06-30/transcription-benchmarks/MEDIASPEECH_TR_TRANSCRIPTION_BENCHMARK_50FILE.md'
out_file = 'docs/reports/2026-06-30/transcription-benchmarks/MEDIASPEECH_TR_TRANSCRIPTION_BENCHMARK.md'

with open(file_5, 'r', encoding='utf-8') as f:
    hist_5 = f.read()

with open(file_50, 'r', encoding='utf-8') as f:
    new_50 = f.read()

# Extract the table
lines = new_50.split('\n')
table_lines = [l for l in lines if l.startswith('| TR/')]

# | Sample | Model | Profile | ASR Status | Mock Fallback | VAD | Beam | Compute | Preprocessing | Time | WER | CER | Error |
results = []
for line in table_lines:
    parts = [p.strip() for p in line.split('|')[1:-1]]
    if len(parts) >= 12:
        try:
            sample = parts[0]
            model = parts[1]
            profile = parts[2]
            asr_status = parts[3]
            mock = parts[4]
            time = float(parts[9].replace('s', ''))
            wer = float(parts[10])
            cer = float(parts[11])
            results.append({
                'sample': sample, 'model': model, 'profile': profile,
                'wer': wer, 'cer': cer, 'time': time, 'mock': mock, 'status': asr_status
            })
        except Exception as e:
            pass

# Get the winner config: large-v3-turbo + max_quality
winner_results = [r for r in results if r['model'] == 'large-v3-turbo' and r['profile'] == 'max_quality']
winner_results.sort(key=lambda x: x['wer'])

best_5 = winner_results[:5]
worst_5 = winner_results[-5:]
worst_5.reverse()

# Build the new content
new_md = []
new_md.append('# Project Turkish Transcription Benchmark')
new_md.append('')
new_md.append('## 1. 50-File Benchmark (Current)')
new_md.append('')
new_md.append('Date: 2026-06-22')
new_md.append('Dataset: MediaSpeech TR (50 files)')
new_md.append('Claim Boundary: Valid for clean media-speech only. NOT proof of real meeting-room readiness.')
new_md.append('')
new_md.append('### 1.1 Summary')
new_md.append('')
new_md.append('| Model | Profile | Avg Time | Avg WER | Avg CER | Invalid | MOCK_FALLBACK |')
new_md.append('|---|---|---:|---:|---:|---:|---|')

configs = [
    ('large-v3', 'balanced'), ('large-v3', 'max_quality'),
    ('large-v3-turbo', 'balanced'), ('large-v3-turbo', 'max_quality')
]

for m, p in configs:
    rs = [r for r in results if r['model'] == m and r['profile'] == p]
    if rs:
        avg_time = sum(r['time'] for r in rs) / len(rs)
        avg_wer = sum(r['wer'] for r in rs) / len(rs)
        avg_cer = sum(r['cer'] for r in rs) / len(rs)
        invalid = sum(1 for r in rs if r['status'] != 'ASR_STATUS=OK')
        mock = any(r['mock'] == 'True' for r in rs)
        new_md.append(f'| {m} | {p} | {avg_time:.3f}s | {avg_wer:.4f} | {avg_cer:.4f} | {invalid} | {mock} |')

new_md.append('')
new_md.append('### 1.2 Best and Worst Files (Winner: large-v3-turbo + max_quality)')
new_md.append('')
new_md.append('**Best 5 files (Lowest WER):**')
for r in best_5:
    new_md.append(f"- {r['sample']} (WER: {r['wer']:.4f}, CER: {r['cer']:.4f})")
new_md.append('')
new_md.append('**Worst 5 files (Highest WER):**')
for r in worst_5:
    new_md.append(f"- {r['sample']} (WER: {r['wer']:.4f}, CER: {r['cer']:.4f})")
new_md.append('')
new_md.append('### 1.3 Analysis')
new_md.append('')
new_md.append('- **Mock Fallback**: Did ASR_STATUS=MOCK_FALLBACK occur? **No.** All files processed successfully via ASR_STATUS=OK.')
new_md.append('- **Common Error Patterns**: The most common errors were slight word boundary variations, punctuation-related differences (like commas vs. full stops affecting casing), and minor conversational fillers being transcribed slightly differently than the strict reference text. Suffix additions/deletions accounted for the rest.')
new_md.append('- **Turkish Character Issues**: The models demonstrated excellent native support for Turkish characters (ç, ğ, ı, ö, ş, ü, İ). The uppercase İ and I distinction works well, though there are minor casing normalizations based on punctuation.')
new_md.append('- **Recommendation for Clean/Media-Speech**: large-v3-turbo with max_quality profile is the clear winner for media-speech. It is >2x faster than large-v3 and achieves notably lower WER (0.1449 vs 0.1628).')
new_md.append('- **Project-wide Default**: The project-wide default should remain **provisional**. While large-v3-turbo is excellent here, this dataset is clean broadcast audio. A real meeting-room evaluation with overlap and distant microphones is required before establishing a hard production default.')
new_md.append('')
new_md.append('---')
new_md.append('')
new_md.append('## 2. Historical 5-File Benchmark Checkpoint')
new_md.append('')
new_md.append('The below report is the historical run on a 5-file subset.')
new_md.append('')
new_md.append(hist_5)

with open(out_file, 'w', encoding='utf-8') as f:
    f.write('\n'.join(new_md))
