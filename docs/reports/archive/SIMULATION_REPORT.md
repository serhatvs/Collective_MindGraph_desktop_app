# FULL SCALE SIMULATION REPORT

## Overview
- **Session ID**: 13
- **Title**: Full Scale Simulated Technical Meeting â€” Collective MindGraph
- **Extraction Mode**: heuristic_fallback
- **Export Path**: /data/Workspace/Collective-MindGraph-2/docs/reports/2026-06-30/simulation/export_simulation.json

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
### Q: FastAPI tarafÄ±nda kimin ne yapmasÄ± gerekiyor?
- **Answer**: ÃœzgÃ¼nÃ¼m, bu konuyla ilgili herhangi bir kanÄ±t bulamadÄ±m.
- **Mode Used**: evidence_only
- **Validation**: accepted
- **Coverage**: 0%
- **Rejected Terms**: []
- **Warnings**: ["Could not determine graph reasoning intent. Use specific keywords like 'task' or 'decision'."]

### Q: Ask Memory neden hallucination guard kullanÄ±yor?
- **Answer**: ÃœzgÃ¼nÃ¼m, bu konuyla ilgili herhangi bir kanÄ±t bulamadÄ±m.
- **Mode Used**: evidence_only
- **Validation**: accepted
- **Coverage**: 0%
- **Rejected Terms**: []
- **Warnings**: ["Could not determine graph reasoning intent. Use specific keywords like 'task' or 'decision'."]

### Q: Semantic search ÅŸu anda production'da aktif mi?
- **Answer**: ÃœzgÃ¼nÃ¼m, bu konuyla ilgili herhangi bir kanÄ±t bulamadÄ±m.
- **Mode Used**: evidence_only
- **Validation**: accepted
- **Coverage**: 0%
- **Rejected Terms**: []
- **Warnings**: ["Could not determine graph reasoning intent. Use specific keywords like 'task' or 'decision'."]

### Q: Diarization ÅŸu an var mÄ±?
- **Answer**: ÃœzgÃ¼nÃ¼m, bu konuyla ilgili herhangi bir kanÄ±t bulamadÄ±m.
- **Mode Used**: evidence_only
- **Validation**: accepted
- **Coverage**: 0%
- **Rejected Terms**: []
- **Warnings**: ["Could not determine graph reasoning intent. Use specific keywords like 'task' or 'decision'."]

### Q: Export JSON neleri iÃ§ermeli?
- **Answer**: ÃœzgÃ¼nÃ¼m, bu konuyla ilgili herhangi bir kanÄ±t bulamadÄ±m.
- **Mode Used**: evidence_only
- **Validation**: accepted
- **Coverage**: 0%
- **Rejected Terms**: []
- **Warnings**: ["Could not determine graph reasoning intent. Use specific keywords like 'task' or 'decision'."]

### Q: Riskler neler?
- **Answer**: ÃœzgÃ¼nÃ¼m, bu konuyla ilgili herhangi bir kanÄ±t bulamadÄ±m.
- **Mode Used**: evidence_only
- **Validation**: accepted
- **Coverage**: 0%
- **Rejected Terms**: []
- **Warnings**: ["No topic or item found matching 'Riskler'."]

### Q: AÃ§Ä±k sorular neler?
- **Answer**: ÃœzgÃ¼nÃ¼m, bu konuyla ilgili herhangi bir kanÄ±t bulamadÄ±m.
- **Mode Used**: evidence_only
- **Validation**: accepted
- **Coverage**: 0%
- **Rejected Terms**: []
- **Warnings**: ["No topic or item found matching 'AÃ§Ä±k'."]

### Q: Hangi entity/tool/library konuÅŸuldu?
- **Answer**: ÃœzgÃ¼nÃ¼m, bu konuyla ilgili herhangi bir kanÄ±t bulamadÄ±m.
- **Mode Used**: evidence_only
- **Validation**: accepted
- **Coverage**: 0%
- **Rejected Terms**: []
- **Warnings**: ["No topic or item found matching 'Hangi'."]

### Q: Follow-up maddeleri neler?
- **Answer**: ÃœzgÃ¼nÃ¼m, bu konuyla ilgili herhangi bir kanÄ±t bulamadÄ±m.
- **Mode Used**: evidence_only
- **Validation**: accepted
- **Coverage**: 0%
- **Rejected Terms**: []
- **Warnings**: ["No topic or item found matching 'Follow-up'."]

## Global Search Sample
### Q: FastAPI endpoint (Hits: 0)

### Q: hallucination guard (Hits: 19)
1. [SEGMENT] 
Serhat: Merhaba arkadaÅŸlar. Collective MindGraph projesi iÃ§in durum deÄŸerlendirme toplantÄ±sÄ±na hoÅŸ geldiniz.
AyÅŸe: Merhaba Serhat.
Mehmet: Merhaba.
Zeynep: Merhabalar.
Serhat: Ã–ncelikle Global Search tarafÄ±nda source trace Ã§alÄ±ÅŸÄ±yor ama Ask Memory sonuÃ§larÄ±nda evidence coverage gÃ¶rÃ¼nÃ¼rlÃ¼ÄŸÃ¼nÃ¼ artÄ±rmamÄ±z lazÄ±m. Bu Ã§ok Ã¶nemli bir eksik.
Mehmet: HaklÄ±sÄ±n. Bunu ben alayÄ±m. Ask Memory iÃ§in coverage UI eklemesi yapacaÄŸÄ±m.
Zeynep: VAD ayarlarÄ±nda silero VAD ile Faster-Whisper entegrasyonu iyi ama padding deÄŸerleri bazen kelime kesiyor. 
Serhat: Karar verelim: VAD padding deÄŸerini 100ms yerine 120ms olarak deÄŸiÅŸtireceÄŸiz.
AyÅŸe: Diarization konusunda ne durumdayÄ±z?
Serhat: Diarization ÅŸu an Ã¼retimde aktif deÄŸil, roadmap Ã¼zerinde. Local-first bir model kullanmamÄ±z ÅŸart. Bunu not edelim.
Mehmet: Export JSON iÃ§inde review_status alanÄ± eksik kalÄ±rsa import sonrasÄ± gÃ¼ven kaybÄ± olur. Export formatÄ±nÄ± gÃ¼ncellememiz lazÄ±m.
AyÅŸe: O zaman ben Export JSON formatÄ±na review_status, disabled, ve original_text alanlarÄ±nÄ± ekleyeyim. Bu riskli bir aÃ§Ä±k.
Zeynep: Semantic search ÅŸu anda production'da aktif mi? SentenceTransformers entegre ettik ama emin olamadÄ±m.
Serhat: Evet, aktif. Modeli CPU Ã¼zerinde Ã§alÄ±ÅŸtÄ±rÄ±yoruz ki LLM ile GPU belleÄŸinde Ã§akÄ±ÅŸmasÄ±n.
Mehmet: Bu arada Local LLM extraction iÃ§in Llama 3.1 8B kullanÄ±yoruz ve oldukÃ§a baÅŸarÄ±lÄ±. Ama hallucination guard'Ä±n Ã§ok katÄ± olmasÄ± bazen doÄŸru cevaplarÄ± reddediyor.
AyÅŸe: Risk olarak not alalÄ±m: Hallucination guard bazen false positive verebilir.
Serhat: Tamam, guard kurallarÄ±nÄ± esnetelim.
AyÅŸe: Bence esnetmeyelim, gÃ¼venilirlik daha Ã¶nemli.
Serhat: HaklÄ±sÄ±n, kararÄ± deÄŸiÅŸtiriyorum: Hallucination guard kurallarÄ± esnetilmeyecek, ÅŸimdilik bu ÅŸekilde kalacak.
Mehmet: Local LLM fallback iÃ§in heuristic scriptlerini sileyim mi?
Zeynep: HayÄ±r, heuristic fallback kesinlikle silinmemeli. Zero-failure iÃ§in gerekli.
Serhat: Tamam, task olarak yazÄ±yorum: Zeynep heuristic fallback testlerini yazacak.
AyÅŸe: AÃ§Ä±k soru: Pyannote diarization'Ä± tamamen offline Ã§alÄ±ÅŸtÄ±rabilecek miyiz?
Serhat: Buna araÅŸtÄ±rma yapmamÄ±z lazÄ±m. AÃ§Ä±k soru olarak kalacak.
Mehmet: Bir task daha: Hybrid Query search performansÄ±nÄ± Ã¶lÃ§memiz lazÄ±m.
AyÅŸe: Topic olarak 'Hybrid Memory Query' diyebiliriz.
Serhat: BaÅŸka eklenecek bir ÅŸey var mÄ±?
Zeynep: Yok sanÄ±rÄ±m, toplantÄ±yÄ± bitirelim.
 (Score: 0.50, Matched By: ['keyword'])
2. [DECISION] Hallucination guard kurallarÄ± esnetilmeyecek (Score: 0.50, Matched By: ['keyword'])

### Q: export JSON (Hits: 13)
1. [SEGMENT] 
Serhat: Merhaba arkadaÅŸlar. Collective MindGraph projesi iÃ§in durum deÄŸerlendirme toplantÄ±sÄ±na hoÅŸ geldiniz.
AyÅŸe: Merhaba Serhat.
Mehmet: Merhaba.
Zeynep: Merhabalar.
Serhat: Ã–ncelikle Global Search tarafÄ±nda source trace Ã§alÄ±ÅŸÄ±yor ama Ask Memory sonuÃ§larÄ±nda evidence coverage gÃ¶rÃ¼nÃ¼rlÃ¼ÄŸÃ¼nÃ¼ artÄ±rmamÄ±z lazÄ±m. Bu Ã§ok Ã¶nemli bir eksik.
Mehmet: HaklÄ±sÄ±n. Bunu ben alayÄ±m. Ask Memory iÃ§in coverage UI eklemesi yapacaÄŸÄ±m.
Zeynep: VAD ayarlarÄ±nda silero VAD ile Faster-Whisper entegrasyonu iyi ama padding deÄŸerleri bazen kelime kesiyor. 
Serhat: Karar verelim: VAD padding deÄŸerini 100ms yerine 120ms olarak deÄŸiÅŸtireceÄŸiz.
AyÅŸe: Diarization konusunda ne durumdayÄ±z?
Serhat: Diarization ÅŸu an Ã¼retimde aktif deÄŸil, roadmap Ã¼zerinde. Local-first bir model kullanmamÄ±z ÅŸart. Bunu not edelim.
Mehmet: Export JSON iÃ§inde review_status alanÄ± eksik kalÄ±rsa import sonrasÄ± gÃ¼ven kaybÄ± olur. Export formatÄ±nÄ± gÃ¼ncellememiz lazÄ±m.
AyÅŸe: O zaman ben Export JSON formatÄ±na review_status, disabled, ve original_text alanlarÄ±nÄ± ekleyeyim. Bu riskli bir aÃ§Ä±k.
Zeynep: Semantic search ÅŸu anda production'da aktif mi? SentenceTransformers entegre ettik ama emin olamadÄ±m.
Serhat: Evet, aktif. Modeli CPU Ã¼zerinde Ã§alÄ±ÅŸtÄ±rÄ±yoruz ki LLM ile GPU belleÄŸinde Ã§akÄ±ÅŸmasÄ±n.
Mehmet: Bu arada Local LLM extraction iÃ§in Llama 3.1 8B kullanÄ±yoruz ve oldukÃ§a baÅŸarÄ±lÄ±. Ama hallucination guard'Ä±n Ã§ok katÄ± olmasÄ± bazen doÄŸru cevaplarÄ± reddediyor.
AyÅŸe: Risk olarak not alalÄ±m: Hallucination guard bazen false positive verebilir.
Serhat: Tamam, guard kurallarÄ±nÄ± esnetelim.
AyÅŸe: Bence esnetmeyelim, gÃ¼venilirlik daha Ã¶nemli.
Serhat: HaklÄ±sÄ±n, kararÄ± deÄŸiÅŸtiriyorum: Hallucination guard kurallarÄ± esnetilmeyecek, ÅŸimdilik bu ÅŸekilde kalacak.
Mehmet: Local LLM fallback iÃ§in heuristic scriptlerini sileyim mi?
Zeynep: HayÄ±r, heuristic fallback kesinlikle silinmemeli. Zero-failure iÃ§in gerekli.
Serhat: Tamam, task olarak yazÄ±yorum: Zeynep heuristic fallback testlerini yazacak.
AyÅŸe: AÃ§Ä±k soru: Pyannote diarization'Ä± tamamen offline Ã§alÄ±ÅŸtÄ±rabilecek miyiz?
Serhat: Buna araÅŸtÄ±rma yapmamÄ±z lazÄ±m. AÃ§Ä±k soru olarak kalacak.
Mehmet: Bir task daha: Hybrid Query search performansÄ±nÄ± Ã¶lÃ§memiz lazÄ±m.
AyÅŸe: Topic olarak 'Hybrid Memory Query' diyebiliriz.
Serhat: BaÅŸka eklenecek bir ÅŸey var mÄ±?
Zeynep: Yok sanÄ±rÄ±m, toplantÄ±yÄ± bitirelim.
 (Score: 0.50, Matched By: ['keyword'])
2. [TASK] Export JSON formatÄ±na review_status, disabled, ve original_text alanlarÄ±nÄ± eklemek (Score: 0.50, Matched By: ['keyword'])

### Q: diarization (Hits: 21)
1. [SEGMENT] 
Serhat: Merhaba arkadaÅŸlar. Collective MindGraph projesi iÃ§in durum deÄŸerlendirme toplantÄ±sÄ±na hoÅŸ geldiniz.
AyÅŸe: Merhaba Serhat.
Mehmet: Merhaba.
Zeynep: Merhabalar.
Serhat: Ã–ncelikle Global Search tarafÄ±nda source trace Ã§alÄ±ÅŸÄ±yor ama Ask Memory sonuÃ§larÄ±nda evidence coverage gÃ¶rÃ¼nÃ¼rlÃ¼ÄŸÃ¼nÃ¼ artÄ±rmamÄ±z lazÄ±m. Bu Ã§ok Ã¶nemli bir eksik.
Mehmet: HaklÄ±sÄ±n. Bunu ben alayÄ±m. Ask Memory iÃ§in coverage UI eklemesi yapacaÄŸÄ±m.
Zeynep: VAD ayarlarÄ±nda silero VAD ile Faster-Whisper entegrasyonu iyi ama padding deÄŸerleri bazen kelime kesiyor. 
Serhat: Karar verelim: VAD padding deÄŸerini 100ms yerine 120ms olarak deÄŸiÅŸtireceÄŸiz.
AyÅŸe: Diarization konusunda ne durumdayÄ±z?
Serhat: Diarization ÅŸu an Ã¼retimde aktif deÄŸil, roadmap Ã¼zerinde. Local-first bir model kullanmamÄ±z ÅŸart. Bunu not edelim.
Mehmet: Export JSON iÃ§inde review_status alanÄ± eksik kalÄ±rsa import sonrasÄ± gÃ¼ven kaybÄ± olur. Export formatÄ±nÄ± gÃ¼ncellememiz lazÄ±m.
AyÅŸe: O zaman ben Export JSON formatÄ±na review_status, disabled, ve original_text alanlarÄ±nÄ± ekleyeyim. Bu riskli bir aÃ§Ä±k.
Zeynep: Semantic search ÅŸu anda production'da aktif mi? SentenceTransformers entegre ettik ama emin olamadÄ±m.
Serhat: Evet, aktif. Modeli CPU Ã¼zerinde Ã§alÄ±ÅŸtÄ±rÄ±yoruz ki LLM ile GPU belleÄŸinde Ã§akÄ±ÅŸmasÄ±n.
Mehmet: Bu arada Local LLM extraction iÃ§in Llama 3.1 8B kullanÄ±yoruz ve oldukÃ§a baÅŸarÄ±lÄ±. Ama hallucination guard'Ä±n Ã§ok katÄ± olmasÄ± bazen doÄŸru cevaplarÄ± reddediyor.
AyÅŸe: Risk olarak not alalÄ±m: Hallucination guard bazen false positive verebilir.
Serhat: Tamam, guard kurallarÄ±nÄ± esnetelim.
AyÅŸe: Bence esnetmeyelim, gÃ¼venilirlik daha Ã¶nemli.
Serhat: HaklÄ±sÄ±n, kararÄ± deÄŸiÅŸtiriyorum: Hallucination guard kurallarÄ± esnetilmeyecek, ÅŸimdilik bu ÅŸekilde kalacak.
Mehmet: Local LLM fallback iÃ§in heuristic scriptlerini sileyim mi?
Zeynep: HayÄ±r, heuristic fallback kesinlikle silinmemeli. Zero-failure iÃ§in gerekli.
Serhat: Tamam, task olarak yazÄ±yorum: Zeynep heuristic fallback testlerini yazacak.
AyÅŸe: AÃ§Ä±k soru: Pyannote diarization'Ä± tamamen offline Ã§alÄ±ÅŸtÄ±rabilecek miyiz?
Serhat: Buna araÅŸtÄ±rma yapmamÄ±z lazÄ±m. AÃ§Ä±k soru olarak kalacak.
Mehmet: Bir task daha: Hybrid Query search performansÄ±nÄ± Ã¶lÃ§memiz lazÄ±m.
AyÅŸe: Topic olarak 'Hybrid Memory Query' diyebiliriz.
Serhat: BaÅŸka eklenecek bir ÅŸey var mÄ±?
Zeynep: Yok sanÄ±rÄ±m, toplantÄ±yÄ± bitirelim.
 (Score: 0.50, Matched By: ['keyword'])
2. [TOPIC] Diarization (Score: 0.50, Matched By: ['keyword'])

### Q: semantic retrieval (Hits: 0)

### Q: review_status (Hits: 10)
1. [SEGMENT] 
Serhat: Merhaba arkadaÅŸlar. Collective MindGraph projesi iÃ§in durum deÄŸerlendirme toplantÄ±sÄ±na hoÅŸ geldiniz.
AyÅŸe: Merhaba Serhat.
Mehmet: Merhaba.
Zeynep: Merhabalar.
Serhat: Ã–ncelikle Global Search tarafÄ±nda source trace Ã§alÄ±ÅŸÄ±yor ama Ask Memory sonuÃ§larÄ±nda evidence coverage gÃ¶rÃ¼nÃ¼rlÃ¼ÄŸÃ¼nÃ¼ artÄ±rmamÄ±z lazÄ±m. Bu Ã§ok Ã¶nemli bir eksik.
Mehmet: HaklÄ±sÄ±n. Bunu ben alayÄ±m. Ask Memory iÃ§in coverage UI eklemesi yapacaÄŸÄ±m.
Zeynep: VAD ayarlarÄ±nda silero VAD ile Faster-Whisper entegrasyonu iyi ama padding deÄŸerleri bazen kelime kesiyor. 
Serhat: Karar verelim: VAD padding deÄŸerini 100ms yerine 120ms olarak deÄŸiÅŸtireceÄŸiz.
AyÅŸe: Diarization konusunda ne durumdayÄ±z?
Serhat: Diarization ÅŸu an Ã¼retimde aktif deÄŸil, roadmap Ã¼zerinde. Local-first bir model kullanmamÄ±z ÅŸart. Bunu not edelim.
Mehmet: Export JSON iÃ§inde review_status alanÄ± eksik kalÄ±rsa import sonrasÄ± gÃ¼ven kaybÄ± olur. Export formatÄ±nÄ± gÃ¼ncellememiz lazÄ±m.
AyÅŸe: O zaman ben Export JSON formatÄ±na review_status, disabled, ve original_text alanlarÄ±nÄ± ekleyeyim. Bu riskli bir aÃ§Ä±k.
Zeynep: Semantic search ÅŸu anda production'da aktif mi? SentenceTransformers entegre ettik ama emin olamadÄ±m.
Serhat: Evet, aktif. Modeli CPU Ã¼zerinde Ã§alÄ±ÅŸtÄ±rÄ±yoruz ki LLM ile GPU belleÄŸinde Ã§akÄ±ÅŸmasÄ±n.
Mehmet: Bu arada Local LLM extraction iÃ§in Llama 3.1 8B kullanÄ±yoruz ve oldukÃ§a baÅŸarÄ±lÄ±. Ama hallucination guard'Ä±n Ã§ok katÄ± olmasÄ± bazen doÄŸru cevaplarÄ± reddediyor.
AyÅŸe: Risk olarak not alalÄ±m: Hallucination guard bazen false positive verebilir.
Serhat: Tamam, guard kurallarÄ±nÄ± esnetelim.
AyÅŸe: Bence esnetmeyelim, gÃ¼venilirlik daha Ã¶nemli.
Serhat: HaklÄ±sÄ±n, kararÄ± deÄŸiÅŸtiriyorum: Hallucination guard kurallarÄ± esnetilmeyecek, ÅŸimdilik bu ÅŸekilde kalacak.
Mehmet: Local LLM fallback iÃ§in heuristic scriptlerini sileyim mi?
Zeynep: HayÄ±r, heuristic fallback kesinlikle silinmemeli. Zero-failure iÃ§in gerekli.
Serhat: Tamam, task olarak yazÄ±yorum: Zeynep heuristic fallback testlerini yazacak.
AyÅŸe: AÃ§Ä±k soru: Pyannote diarization'Ä± tamamen offline Ã§alÄ±ÅŸtÄ±rabilecek miyiz?
Serhat: Buna araÅŸtÄ±rma yapmamÄ±z lazÄ±m. AÃ§Ä±k soru olarak kalacak.
Mehmet: Bir task daha: Hybrid Query search performansÄ±nÄ± Ã¶lÃ§memiz lazÄ±m.
AyÅŸe: Topic olarak 'Hybrid Memory Query' diyebiliriz.
Serhat: BaÅŸka eklenecek bir ÅŸey var mÄ±?
Zeynep: Yok sanÄ±rÄ±m, toplantÄ±yÄ± bitirelim.
 (Score: 0.50, Matched By: ['keyword'])
2. [TASK] Export JSON formatÄ±na review_status, disabled, ve original_text alanlarÄ±nÄ± eklemek (Score: 0.50, Matched By: ['keyword'])

### Q: source reference (Hits: 0)

## Findings & TODOs
- **Diarization**: Remains unimplemented natively; simulated via text markers but graph does not natively separate speakers cleanly yet without pyannote.
- **Graph Expansion**: Hybrid query 1-hop expansion is currently a pass/placeholder.
- **Native Schema Expansion**: FIXED. ENTITY, RISK, OPEN_QUESTION, and FOLLOW_UP nodes are now natively supported with corresponding edges.
