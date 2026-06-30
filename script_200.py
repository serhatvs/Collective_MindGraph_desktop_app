import re

file_200 = 'docs/reports/2026-06-30/transcription-benchmarks/MEDIASPEECH_TR_TRANSCRIPTION_BENCHMARK_200FILE.md'

with open(file_200, 'r', encoding='utf-8') as f:
    text = f.read()

lines = text.split('\n')
table_lines = [l for l in lines if l.startswith('| TR/')]

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

configs = [
    ('large-v3-turbo', 'balanced'), ('large-v3-turbo', 'max_quality')
]

summary = ""
for m, p in configs:
    rs = [r for r in results if r['model'] == m and r['profile'] == p]
    if rs:
        avg_time = sum(r['time'] for r in rs) / len(rs)
        avg_wer = sum(r['wer'] for r in rs) / len(rs)
        avg_cer = sum(r['cer'] for r in rs) / len(rs)
        invalid = sum(1 for r in rs if r['status'] != 'ASR_STATUS=OK')
        mock = any(r['mock'] == 'True' for r in rs)
        summary += f"| {m} | {p} | {len(rs)} | {avg_time:.3f}s | {avg_wer:.4f} | {avg_cer:.4f} | {invalid} | {mock} |\n"

# Worst 10 for max_quality
winner_results = [r for r in results if r['model'] == 'large-v3-turbo' and r['profile'] == 'max_quality']
winner_results.sort(key=lambda x: x['wer'])

worst_10 = winner_results[-10:]
worst_10.reverse()
for r in worst_10:
    summary += f"Worst: {r['sample']} WER: {r['wer']}\n"

print(summary)
