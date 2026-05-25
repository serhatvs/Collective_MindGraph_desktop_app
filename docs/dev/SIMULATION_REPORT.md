# FULL SCALE SIMULATION REPORT

## Overview
- **Session ID**: 13
- **Title**: Full Scale Simulated Technical Meeting — Collective MindGraph
- **Extraction Mode**: heuristic_fallback
- **Export Path**: /data/Workspace/Collective-MindGraph-2/realtime_backend_temp/export_simulation.json

> **Note**: Earlier runs may have used Local LLM when LM Studio was available. Current stable default mode is no-LLM fallback/evidence-only. Local LLM can be re-enabled later.


## Meeting Summary
The simulated meeting was a Turkish technical product planning session discussing Global Search, Ask Memory, VAD settings, Diarization, Export schemas, Semantic Search, and LLM Hallucination guard rules. Participants explicitly made decisions, assigned tasks, debated choices, and outlined open questions.

## Graph Metrics
- **Nodes**: 2
- **Edges**: 1
- **Approved Items**: 0
- **Edited Items**: 0
- **Rejected Items**: 0
- **Disabled Items**: 0
- **Pending Items**: 0

## Ask Memory Results
### Q: FastAPI tarafında kimin ne yapması gerekiyor?
- **Answer**: Üzgünüm, bu konuyla ilgili herhangi bir kanıt bulamadım.
- **Mode Used**: evidence_only
- **Validation**: accepted
- **Coverage**: 0%
- **Rejected Terms**: []
- **Warnings**: ["Could not determine graph reasoning intent. Use specific keywords like 'task' or 'decision'."]

### Q: Ask Memory neden hallucination guard kullanıyor?
- **Answer**: Üzgünüm, bu konuyla ilgili herhangi bir kanıt bulamadım.
- **Mode Used**: evidence_only
- **Validation**: accepted
- **Coverage**: 0%
- **Rejected Terms**: []
- **Warnings**: ["Could not determine graph reasoning intent. Use specific keywords like 'task' or 'decision'."]

### Q: Semantic search şu anda production'da aktif mi?
- **Answer**: Üzgünüm, bu konuyla ilgili herhangi bir kanıt bulamadım.
- **Mode Used**: evidence_only
- **Validation**: accepted
- **Coverage**: 0%
- **Rejected Terms**: []
- **Warnings**: ["Could not determine graph reasoning intent. Use specific keywords like 'task' or 'decision'."]

### Q: Diarization şu an var mı?
- **Answer**: Üzgünüm, bu konuyla ilgili herhangi bir kanıt bulamadım.
- **Mode Used**: evidence_only
- **Validation**: accepted
- **Coverage**: 0%
- **Rejected Terms**: []
- **Warnings**: ["Could not determine graph reasoning intent. Use specific keywords like 'task' or 'decision'."]

### Q: Export JSON neleri içermeli?
- **Answer**: Üzgünüm, bu konuyla ilgili herhangi bir kanıt bulamadım.
- **Mode Used**: evidence_only
- **Validation**: accepted
- **Coverage**: 0%
- **Rejected Terms**: []
- **Warnings**: ["Could not determine graph reasoning intent. Use specific keywords like 'task' or 'decision'."]

### Q: Riskler neler?
- **Answer**: Üzgünüm, bu konuyla ilgili herhangi bir kanıt bulamadım.
- **Mode Used**: evidence_only
- **Validation**: accepted
- **Coverage**: 0%
- **Rejected Terms**: []
- **Warnings**: ["No topic or item found matching 'Riskler'."]

### Q: Açık sorular neler?
- **Answer**: Üzgünüm, bu konuyla ilgili herhangi bir kanıt bulamadım.
- **Mode Used**: evidence_only
- **Validation**: accepted
- **Coverage**: 0%
- **Rejected Terms**: []
- **Warnings**: ["No topic or item found matching 'Açık'."]

### Q: Hangi entity/tool/library konuşuldu?
- **Answer**: Üzgünüm, bu konuyla ilgili herhangi bir kanıt bulamadım.
- **Mode Used**: evidence_only
- **Validation**: accepted
- **Coverage**: 0%
- **Rejected Terms**: []
- **Warnings**: ["No topic or item found matching 'Hangi'."]

### Q: Follow-up maddeleri neler?
- **Answer**: Üzgünüm, bu konuyla ilgili herhangi bir kanıt bulamadım.
- **Mode Used**: evidence_only
- **Validation**: accepted
- **Coverage**: 0%
- **Rejected Terms**: []
- **Warnings**: ["No topic or item found matching 'Follow-up'."]

## Global Search Sample
### Q: FastAPI endpoint (Hits: 0)

### Q: hallucination guard (Hits: 19)
1. [SEGMENT] 
Serhat: Merhaba arkadaşlar. Collective MindGraph projesi için durum değerlendirme toplantısına hoş geldiniz.
Ayşe: Merhaba Serhat.
Mehmet: Merhaba.
Zeynep: Merhabalar.
Serhat: Öncelikle Global Search tarafında source trace çalışıyor ama Ask Memory sonuçlarında evidence coverage görünürlüğünü artırmamız lazım. Bu çok önemli bir eksik.
Mehmet: Haklısın. Bunu ben alayım. Ask Memory için coverage UI eklemesi yapacağım.
Zeynep: VAD ayarlarında silero VAD ile Faster-Whisper entegrasyonu iyi ama padding değerleri bazen kelime kesiyor. 
Serhat: Karar verelim: VAD padding değerini 100ms yerine 120ms olarak değiştireceğiz.
Ayşe: Diarization konusunda ne durumdayız?
Serhat: Diarization şu an üretimde aktif değil, roadmap üzerinde. Local-first bir model kullanmamız şart. Bunu not edelim.
Mehmet: Export JSON içinde review_status alanı eksik kalırsa import sonrası güven kaybı olur. Export formatını güncellememiz lazım.
Ayşe: O zaman ben Export JSON formatına review_status, disabled, ve original_text alanlarını ekleyeyim. Bu riskli bir açık.
Zeynep: Semantic search şu anda production'da aktif mi? SentenceTransformers entegre ettik ama emin olamadım.
Serhat: Evet, aktif. Modeli CPU üzerinde çalıştırıyoruz ki LLM ile GPU belleğinde çakışmasın.
Mehmet: Bu arada Local LLM extraction için Llama 3.1 8B kullanıyoruz ve oldukça başarılı. Ama hallucination guard'ın çok katı olması bazen doğru cevapları reddediyor.
Ayşe: Risk olarak not alalım: Hallucination guard bazen false positive verebilir.
Serhat: Tamam, guard kurallarını esnetelim.
Ayşe: Bence esnetmeyelim, güvenilirlik daha önemli.
Serhat: Haklısın, kararı değiştiriyorum: Hallucination guard kuralları esnetilmeyecek, şimdilik bu şekilde kalacak.
Mehmet: Local LLM fallback için heuristic scriptlerini sileyim mi?
Zeynep: Hayır, heuristic fallback kesinlikle silinmemeli. Zero-failure için gerekli.
Serhat: Tamam, task olarak yazıyorum: Zeynep heuristic fallback testlerini yazacak.
Ayşe: Açık soru: Pyannote diarization'ı tamamen offline çalıştırabilecek miyiz?
Serhat: Buna araştırma yapmamız lazım. Açık soru olarak kalacak.
Mehmet: Bir task daha: Hybrid Query search performansını ölçmemiz lazım.
Ayşe: Topic olarak 'Hybrid Memory Query' diyebiliriz.
Serhat: Başka eklenecek bir şey var mı?
Zeynep: Yok sanırım, toplantıyı bitirelim.
 (Score: 0.50, Matched By: ['keyword'])
2. [DECISION] Hallucination guard kuralları esnetilmeyecek (Score: 0.50, Matched By: ['keyword'])

### Q: export JSON (Hits: 13)
1. [SEGMENT] 
Serhat: Merhaba arkadaşlar. Collective MindGraph projesi için durum değerlendirme toplantısına hoş geldiniz.
Ayşe: Merhaba Serhat.
Mehmet: Merhaba.
Zeynep: Merhabalar.
Serhat: Öncelikle Global Search tarafında source trace çalışıyor ama Ask Memory sonuçlarında evidence coverage görünürlüğünü artırmamız lazım. Bu çok önemli bir eksik.
Mehmet: Haklısın. Bunu ben alayım. Ask Memory için coverage UI eklemesi yapacağım.
Zeynep: VAD ayarlarında silero VAD ile Faster-Whisper entegrasyonu iyi ama padding değerleri bazen kelime kesiyor. 
Serhat: Karar verelim: VAD padding değerini 100ms yerine 120ms olarak değiştireceğiz.
Ayşe: Diarization konusunda ne durumdayız?
Serhat: Diarization şu an üretimde aktif değil, roadmap üzerinde. Local-first bir model kullanmamız şart. Bunu not edelim.
Mehmet: Export JSON içinde review_status alanı eksik kalırsa import sonrası güven kaybı olur. Export formatını güncellememiz lazım.
Ayşe: O zaman ben Export JSON formatına review_status, disabled, ve original_text alanlarını ekleyeyim. Bu riskli bir açık.
Zeynep: Semantic search şu anda production'da aktif mi? SentenceTransformers entegre ettik ama emin olamadım.
Serhat: Evet, aktif. Modeli CPU üzerinde çalıştırıyoruz ki LLM ile GPU belleğinde çakışmasın.
Mehmet: Bu arada Local LLM extraction için Llama 3.1 8B kullanıyoruz ve oldukça başarılı. Ama hallucination guard'ın çok katı olması bazen doğru cevapları reddediyor.
Ayşe: Risk olarak not alalım: Hallucination guard bazen false positive verebilir.
Serhat: Tamam, guard kurallarını esnetelim.
Ayşe: Bence esnetmeyelim, güvenilirlik daha önemli.
Serhat: Haklısın, kararı değiştiriyorum: Hallucination guard kuralları esnetilmeyecek, şimdilik bu şekilde kalacak.
Mehmet: Local LLM fallback için heuristic scriptlerini sileyim mi?
Zeynep: Hayır, heuristic fallback kesinlikle silinmemeli. Zero-failure için gerekli.
Serhat: Tamam, task olarak yazıyorum: Zeynep heuristic fallback testlerini yazacak.
Ayşe: Açık soru: Pyannote diarization'ı tamamen offline çalıştırabilecek miyiz?
Serhat: Buna araştırma yapmamız lazım. Açık soru olarak kalacak.
Mehmet: Bir task daha: Hybrid Query search performansını ölçmemiz lazım.
Ayşe: Topic olarak 'Hybrid Memory Query' diyebiliriz.
Serhat: Başka eklenecek bir şey var mı?
Zeynep: Yok sanırım, toplantıyı bitirelim.
 (Score: 0.50, Matched By: ['keyword'])
2. [TASK] Export JSON formatına review_status, disabled, ve original_text alanlarını eklemek (Score: 0.50, Matched By: ['keyword'])

### Q: diarization (Hits: 21)
1. [SEGMENT] 
Serhat: Merhaba arkadaşlar. Collective MindGraph projesi için durum değerlendirme toplantısına hoş geldiniz.
Ayşe: Merhaba Serhat.
Mehmet: Merhaba.
Zeynep: Merhabalar.
Serhat: Öncelikle Global Search tarafında source trace çalışıyor ama Ask Memory sonuçlarında evidence coverage görünürlüğünü artırmamız lazım. Bu çok önemli bir eksik.
Mehmet: Haklısın. Bunu ben alayım. Ask Memory için coverage UI eklemesi yapacağım.
Zeynep: VAD ayarlarında silero VAD ile Faster-Whisper entegrasyonu iyi ama padding değerleri bazen kelime kesiyor. 
Serhat: Karar verelim: VAD padding değerini 100ms yerine 120ms olarak değiştireceğiz.
Ayşe: Diarization konusunda ne durumdayız?
Serhat: Diarization şu an üretimde aktif değil, roadmap üzerinde. Local-first bir model kullanmamız şart. Bunu not edelim.
Mehmet: Export JSON içinde review_status alanı eksik kalırsa import sonrası güven kaybı olur. Export formatını güncellememiz lazım.
Ayşe: O zaman ben Export JSON formatına review_status, disabled, ve original_text alanlarını ekleyeyim. Bu riskli bir açık.
Zeynep: Semantic search şu anda production'da aktif mi? SentenceTransformers entegre ettik ama emin olamadım.
Serhat: Evet, aktif. Modeli CPU üzerinde çalıştırıyoruz ki LLM ile GPU belleğinde çakışmasın.
Mehmet: Bu arada Local LLM extraction için Llama 3.1 8B kullanıyoruz ve oldukça başarılı. Ama hallucination guard'ın çok katı olması bazen doğru cevapları reddediyor.
Ayşe: Risk olarak not alalım: Hallucination guard bazen false positive verebilir.
Serhat: Tamam, guard kurallarını esnetelim.
Ayşe: Bence esnetmeyelim, güvenilirlik daha önemli.
Serhat: Haklısın, kararı değiştiriyorum: Hallucination guard kuralları esnetilmeyecek, şimdilik bu şekilde kalacak.
Mehmet: Local LLM fallback için heuristic scriptlerini sileyim mi?
Zeynep: Hayır, heuristic fallback kesinlikle silinmemeli. Zero-failure için gerekli.
Serhat: Tamam, task olarak yazıyorum: Zeynep heuristic fallback testlerini yazacak.
Ayşe: Açık soru: Pyannote diarization'ı tamamen offline çalıştırabilecek miyiz?
Serhat: Buna araştırma yapmamız lazım. Açık soru olarak kalacak.
Mehmet: Bir task daha: Hybrid Query search performansını ölçmemiz lazım.
Ayşe: Topic olarak 'Hybrid Memory Query' diyebiliriz.
Serhat: Başka eklenecek bir şey var mı?
Zeynep: Yok sanırım, toplantıyı bitirelim.
 (Score: 0.50, Matched By: ['keyword'])
2. [TOPIC] Diarization (Score: 0.50, Matched By: ['keyword'])

### Q: semantic retrieval (Hits: 0)

### Q: review_status (Hits: 10)
1. [SEGMENT] 
Serhat: Merhaba arkadaşlar. Collective MindGraph projesi için durum değerlendirme toplantısına hoş geldiniz.
Ayşe: Merhaba Serhat.
Mehmet: Merhaba.
Zeynep: Merhabalar.
Serhat: Öncelikle Global Search tarafında source trace çalışıyor ama Ask Memory sonuçlarında evidence coverage görünürlüğünü artırmamız lazım. Bu çok önemli bir eksik.
Mehmet: Haklısın. Bunu ben alayım. Ask Memory için coverage UI eklemesi yapacağım.
Zeynep: VAD ayarlarında silero VAD ile Faster-Whisper entegrasyonu iyi ama padding değerleri bazen kelime kesiyor. 
Serhat: Karar verelim: VAD padding değerini 100ms yerine 120ms olarak değiştireceğiz.
Ayşe: Diarization konusunda ne durumdayız?
Serhat: Diarization şu an üretimde aktif değil, roadmap üzerinde. Local-first bir model kullanmamız şart. Bunu not edelim.
Mehmet: Export JSON içinde review_status alanı eksik kalırsa import sonrası güven kaybı olur. Export formatını güncellememiz lazım.
Ayşe: O zaman ben Export JSON formatına review_status, disabled, ve original_text alanlarını ekleyeyim. Bu riskli bir açık.
Zeynep: Semantic search şu anda production'da aktif mi? SentenceTransformers entegre ettik ama emin olamadım.
Serhat: Evet, aktif. Modeli CPU üzerinde çalıştırıyoruz ki LLM ile GPU belleğinde çakışmasın.
Mehmet: Bu arada Local LLM extraction için Llama 3.1 8B kullanıyoruz ve oldukça başarılı. Ama hallucination guard'ın çok katı olması bazen doğru cevapları reddediyor.
Ayşe: Risk olarak not alalım: Hallucination guard bazen false positive verebilir.
Serhat: Tamam, guard kurallarını esnetelim.
Ayşe: Bence esnetmeyelim, güvenilirlik daha önemli.
Serhat: Haklısın, kararı değiştiriyorum: Hallucination guard kuralları esnetilmeyecek, şimdilik bu şekilde kalacak.
Mehmet: Local LLM fallback için heuristic scriptlerini sileyim mi?
Zeynep: Hayır, heuristic fallback kesinlikle silinmemeli. Zero-failure için gerekli.
Serhat: Tamam, task olarak yazıyorum: Zeynep heuristic fallback testlerini yazacak.
Ayşe: Açık soru: Pyannote diarization'ı tamamen offline çalıştırabilecek miyiz?
Serhat: Buna araştırma yapmamız lazım. Açık soru olarak kalacak.
Mehmet: Bir task daha: Hybrid Query search performansını ölçmemiz lazım.
Ayşe: Topic olarak 'Hybrid Memory Query' diyebiliriz.
Serhat: Başka eklenecek bir şey var mı?
Zeynep: Yok sanırım, toplantıyı bitirelim.
 (Score: 0.50, Matched By: ['keyword'])
2. [TASK] Export JSON formatına review_status, disabled, ve original_text alanlarını eklemek (Score: 0.50, Matched By: ['keyword'])

### Q: source reference (Hits: 0)

## Findings & TODOs
- **Diarization**: Remains unimplemented natively; simulated via text markers but graph does not natively separate speakers cleanly yet without pyannote.
- **Graph Expansion**: Hybrid query 1-hop expansion is currently a pass/placeholder.
- **Native Schema Expansion**: FIXED. ENTITY, RISK, OPEN_QUESTION, and FOLLOW_UP nodes are now natively supported with corresponding edges.
