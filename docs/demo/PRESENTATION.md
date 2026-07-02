# Tanıtım Senaryosu (Turkish Demo Script)

Bu senaryo, Collective MindGraph projesini bir öğretmene, TTO yetkilisine veya teknik bir jüriye sunarken kullanılmak üzere hazırlanmıştır.

## Açılış
"Merhaba, bugün sizlere kurumsal hafıza yönetiminde gizlilik ve yerelliği merkeze alan projemiz Collective MindGraph'i tanıtacağım."

## Problem ve Çözüm
"Teknik toplantılarda alınan kararlar ve görevler genellikle ya unutuluyor ya da bu verileri işlemek için bulut tabanlı sistemlere gönderilerek veri gizliliği riske atılıyor. Projemiz, tüm zekayı yerel donanımda tutarak teknik Türkçe konuşmalardan otomatik görev ve karar çıkaran bir yapı sunuyor."

## Mevcut MVP Yetenekleri
"Şu anki prototipimiz; sesin yerel olarak işlenmesi, teknik terimlerin (FastAPI, SQLite gibi) doğru tanınması, konuşmadan görev ve kararların ayıklanması ve tüm bu bilginin geriye dönük izlenebilir şekilde aranmasını kapsamaktadır."

## Demo Adımları

1.  **Hazırlık**: "Sistemi çalıştırmadan önce çevresel gereksinimlerin (ffmpeg, yerel modeller) tam olduğunu kontrol ediyoruz." (`./scripts/check_demo_readiness.sh`)
2.  **Veri Hazırlama**: "Ses kaydı gerektirmeyen, teknik bir Türkçe toplantı metnini sisteme örnek veri olarak yüklüyoruz." (`PYTHONPATH=. python realtime_backend/scripts/seed_demo_session.py`)
3.  **Servislerin Başlatılması**: "Arka planda ses işleme servisimiz olan FastAPI'yi 8080 portunda başlatıyoruz. Ardından, asıl kullanıcı arayüzümüz olan yerel masaüstü uygulamamızı açıyoruz." (`./scripts/dev_backend.sh` ve `./scripts/dev_desktop.sh`)
4.  **Oturum İnceleme**: "Oturum Listesi'nden az önce eklediğimiz 'demo_technical_turkish' oturumunu açıyoruz."
5.  **Temiz Metin (Cleaned Transcript)**: "Sistemin dolgu kelimeleri temizleyip teknik terimleri nasıl düzelttiğini gösteriyoruz."
6.  **Görev ve Kararlar**: "Heuristik yöntemlerle ayıklanan 'FastAPI testi' veya 'SQLite kaydı' gibi yapısal verileri sağ panelde gösteriyoruz."
7.  **Küresel Arama (Global Search)**: "Şimdi hafızada bir arama yapalım. 'FastAPI endpoint' anahtar kelimesini aratıyoruz."
8.  **İzlenebilirlik**: "Arama sonucuna çift tıklayarak, sistemin bizi ilgili oturuma ve tam olarak o bilginin geçtiği konuşma satırına nasıl yönlendirdiğini gösteriyoruz."

## Önemli Not (İddia Sınırı)
"Sistemimiz şu an keyword-tabanlı bir arama ve hiyerarşik bir saklama yapısı kullanmaktadır. Semantik (anlamsal) arama ve tam grafik muhakemesi gelecek planlarımız arasındadır."

## Kapanış
"Collective MindGraph, yerel çalışan bir kurumsal hafıza sisteminin temelini atmış durumdadır. İzlediğiniz için teşekkürler."

---
**Durum**: The project is local MVP demo ready and product-integration ready for local-first Turkish transcription and keyword-based memory exploration. It is not yet a production-validated meeting intelligence platform.
# Collective MindGraph: Türkçe Sunum Paketi

Bu paket, projenin mevcut "Yerel MVP" durumuna sadık kalarak, abartılı iddialardan kaçınan teknik ve genel sunum materyallerini içermektedir.

---

## 1. 2 Dakikalık Tanıtım Konuşması (Genel)

"Merhaba, bugün sizlere teknik toplantılar için geliştirdiğimiz yerel ve gizlilik odaklı kurumsal hafıza sistemi olan **Collective MindGraph**'i tanıtacağım.

**Problem:** Günümüzde teknik toplantılarda alınan kritik kararlar ve görevler genellikle ya unutuluyor ya da bu verileri işlemek için bulut tabanlı yapay zeka servislerine gönderilerek veri gizliliği riske atılıyor.

**Çözüm:** Collective MindGraph, tüm zekayı yerel donanımda tutarak teknik Türkçe konuşmaları işleyen bir yapı sunar. Mevcut MVP (Minimum Uygulanabilir Ürün) aşamamızda sistem; sesi yerel olarak metne dönüştürüyor, dolgu kelimeleri temizleyerek teknik terimleri (FastAPI, SQLite vb.) düzeltiyor ve konuşmadan otomatik olarak görev ve kararları ayıklıyor.

**Gizlilik Odaklılık:** Sistemimiz 'Local-First' prensibiyle çalışır. Yani hiçbir ses verisi veya metin dış sunuculara gönderilmez. Bu, kurumsal sırların ve teknik detayların kurum dışına çıkmasını engeller.

**Demo Akışı:** Bugün sizlere sistemin hazır bir teknik toplantı kaydı üzerinden nasıl anlık analiz yaptığını, görevleri nasıl listelediğini ve 'Global Search' arayüzü ile bu bilgilere kaynak konuşma satırına kadar nasıl ulaştığını göstereceğiz.

**Durum:** Projemiz şu an yerel MVP demo aşamasındadır. Anahtar kelime bazlı hafıza taraması için entegrasyona hazırdır. Otomatik konuşmacı ayrımı (diarization) henüz uygulanmamıştır ve gelecek planları arasındadır. İzlediğiniz için teşekkürler."

---

## 2. 5 Dakikalık Teknik Detay Konuşması

"Collective MindGraph'in teknik mimarisi, verinin yerelliğini ve izlenebilirliğini garanti altına alacak şekilde tasarlanmıştır.

**Mimari Akış:** Sistem, mikrofon veya WebSocket üzerinden gelen ham sesi önce bir normalizasyon katmanına (FFmpeg) sokar. Ardından, yerel olarak çalışan **Faster-Whisper** motoru ile sesi metne dönüştürürüz. Burada teknik Türkçe sözlüğümüzü kullanarak STT motorunun 'FastAPI' veya 'VAD' gibi terimlerdeki isabet oranını artırıyoruz.

**Dual-Transcript Modeli:** En önemli teknik yeniliklerimizden biri, ham ASR çıktısı (Raw Transcript) ile temizlenmiş metni (Cleaned Transcript) ayrı tutmamızdır. Ham metin denetlenebilirlik için saklanırken, temiz metin üzerinde deterministik Türkçe heuristikleri çalıştırılarak 'yapılacak', 'karar verildi' gibi dil kalıpları üzerinden görev ve kararlar ayıklanır.

**Hafıza ve Sorgulama:** Ayıklanan bu bilgiler, SQLite tabanlı hiyerarşik bir düğüm yapısında (Graph-Node Persistence) saklanır. Mevcut sürümde **KeywordMemoryQueryService** aracılığıyla, tüm geçmiş toplantılar içinde anahtar kelime bazlı arama yapabiliyoruz. Her arama sonucu, ilgili ses kaydının tam saniyesine ve transkript satırına (UUID bazlı) bağlıdır.

**Doğrulama:** Sistemimizi Mozilla Common Voice Türkçe veri setiyle test ettik ve temiz konuşmalarda %91 civarında bir anahtar kelime isabet oranına ulaştık. Ancak gerçek toplantı odalarındaki çoklu konuşmacı ve gürültü durumları için manuel doğrulama sürecimiz devam etmektedir.

**Yol Haritası:** Gelecek aşamalarda, anahtar kelime aramasının ötesine geçerek yerel 'embedding' modelleri ile semantik (anlamsal) aramayı sisteme dahil edeceğiz. Ayrıca hiyerarşik ağ yapısını, toplantılar arası ilişkileri kurabilen tam bir semantik grafik yapısına dönüştürmeyi hedefliyoruz.

Collective MindGraph, kurumsal hafızayı yerelde ve güvenli bir şekilde inşa etmek için sağlam bir temel sunmaktadır."

---

## 3. Teknik Özet (Patent ve Form Başvuruları İçin)

**Sistem Tanımı:** Teknik Türkçe konuşma verilerini yerel altyapıda işleyen ve yapısal kurumsal hafıza düğümleri (görev, karar, konu) üreten bir sistemdir.

**Mimari Özellikler:**
- **Donanım/Yazılım Entegrasyonu:** Sistem, özelleştirilmiş bir donanım ünitesi ile entegre edilebilecek şekilde tasarlanmış bir yazılım mimarisine sahiptir.
- **Yerel Öncelikli İşleme:** Ses normalizasyonu, ses aktivite algılama (VAD) ve konuşma-metin dönüşümü (STT) süreçleri tamamen kullanıcı donanımında gerçekleşir.
- **Çift Katmanlı Transkripsiyon:** Ham çıkarım verisi ile temizlenmiş metinsel gösterimin eşzamanlı olarak saklanması ve izlenebilirliğin sağlanması.
- **Yapısal Hafıza Çıkarımı:** Deterministik dil kalıpları kullanılarak, serbest konuşma metinlerinden yapılandırılmış veri (Action Items, Decisions) üretilmesi.
- **Sorgulanabilir Veri Yapısı:** Saklanan verilerin kaynak segmentlere referanslı şekilde hiyerarşik olarak dizinlenmesi ve sorgulanması.

**Gelişim Aşaması:** Prototip/MVP aşamasındadır; belirli teknik Türkçe sözlükler ve kontrollü ortamlar için optimize edilmiştir.

---

## 4. 7 Slaytlık Sunum İçeriği

### Slayt 1: Kapak ve Değer Önerisi
- **Başlık:** Collective MindGraph
- **Alt Başlık:** Teknik Toplantılar İçin Yerel ve Güvenli Kurumsal Hafıza
- **Motto:** Veriniz sizde kalsın, hafızanız otomatikleşsin.

### Slayt 2: Problem
- Teknik toplantılarda kararların ve görevlerin kaybolması.
- Bulut AI servislerinin kullanımındaki veri gizliliği riskleri.
- Yerel araçların teknik Türkçe terimlerdeki yetersizliği.

### Slayt 3: Çözüm
- %100 çevrimdışı (offline) çalışan transkripsiyon ve analiz hattı.
- Ham ve temizlenmiş transkriptlerin eşzamanlı saklanması.
- Teknik Türkçe terimler için optimize edilmiş ayıklama mantığı.

### Slayt 4: Mevcut MVP Mimarisi
- **STT:** Faster-Whisper (Yerel).
- **Analiz:** Türkçe heuristik (kural bazlı) görev ve karar ayıklama.
- **Depolama:** SQLite hiyerarşik düğüm yapısı.
- **Güvenlik:** İnternet erişimini engelleyen 'Offline Safety' korumaları.

### Slayt 5: Demo Akışı
- Çevresel gereksinim kontrolü ve örnek veri yükleme.
- Teknik bir toplantının transkripsiyonu ve temizlenmesi.
- Ayıklanan görevlerin izlenebilir şekilde 'Global Search' üzerinden bulunması.

### Slayt 6: Doğrulama ve Sınırlar
- **Doğrulama:** Common Voice Türkçe veri seti ile %91 keyword başarısı.
- **Sınırlar:** Şu an için keyword bazlı arama (anlamsal değil), hiyerarşik düğüm yapısı (karmaşık grafik değil).
- **Not:** Gerçek toplantı odası doğrulaması planlanmaktadır.

### Slayt 7: Yol Haritası
- **Faz 1:** Gerçek toplantı odası ses doğrulamaları ve kullanıcı deneyimi iyileştirme.
- **Faz 2:** Yerel embedding modelleri ile semantik (anlamsal) arama desteği.
- **Faz 3:** Toplantılar arası ilişki kurabilen tam grafik (graph) yapısı.
- **Faz 4:** Donanım prototipi ve mikrofon dizisi entegrasyonu.

---
**Resmi Durum Beyanı:** The project is local MVP demo ready and product-integration ready for local-first Turkish transcription and keyword-based memory exploration. It does not currently include validated diarization or production meeting-room speaker separation.
# Demo Presentation Notes: Collective MindGraph MVP

These notes guide you through presenting the current local-first software MVP. 

## Preparation
1.  **Check Readiness**: Run `./scripts/check_demo_readiness.sh`.
2.  **Seed Data**: Run `PYTHONPATH=. python realtime_backend/scripts/seed_demo_session.py`.
3.  **Start Services**: Launch `./scripts/dev_backend.sh` and `./scripts/dev_desktop.sh`.

---

## 2-Minute Demo: The Knowledge Loop
1.  **Open Seeded Session**: Select `demo_technical_turkish` in the Session Explorer.
2.  **Highlight Cleaned Transcript**: Show how technical terms like *FastAPI* and *MindGraph* are correctly capitalized and readable.
3.  **Show Extracted Insights**: Point to the "Decision" and "Action" nodes in the right panel.
4.  **Quick Search**: Open **Global Search**, type `FastAPI endpoint`, and double-click the result to show immediate navigation back to the source.

## 5-Minute Technical Demo: Architecture & Privacy
1.  **Offline Proof**: Explain that no internet connection is active.
2.  **Audio Audit**: Open the **Analysis** tab. Compare **Raw ASR** (with fillers like *şey, ııı*) vs. **Corrected Text**.
3.  **Heuristic Extraction**: Explain how the system uses local regex/glossaries to find tasks and decisions without cloud LLMs.
4.  **Cross-Session Retrieval**: Perform multiple searches:
    - `raw transcript`: Shows how the system remembers architectural decisions across meetings.
    - `VAD ayarları`: Shows extracted technical tasks.
    - `Collective MindGraph`: Shows topic-level indexing.
5.  **Source Traceability**: Explain the score logic and how every result is pinned to a session ID and segment UUID.

---

## Demonstration Query Guide
| Query | Expected Result | Proves |
| :--- | :--- | :--- |
| `FastAPI endpoint` | Task | Heuristic future-action extraction. |
| `raw transcript` | Decision | Passive-voice decision detection. |
| `VAD ayarları` | Task / Topic | Technical term recognition. |
| `kararlar` | Decision | Turkish agreement marker detection. |
| `Collective MindGraph`| Session / Topic | Multi-type keyword relevance. |

---

## Important Caveats (What NOT to claim)
- **Production-Ready**: Do not claim it is ready for critical production meeting rooms without further audio validation.
- **Full Semantic AI**: The current search is keyword-based. Do not claim it "understands" concepts semantically yet.
- **Full Graph Reasoning**: The system uses hierarchical nodes, not a multi-hop graph reasoning engine.
- **Diarization**: Clarify that automatic speaker separation is NOT currently active and is planned for future roadmap validation.

---
**Status**: The project is local MVP demo ready and product-integration ready for local-first Turkish transcription and keyword-based memory exploration. It is not yet a production-validated meeting intelligence platform.
# Slide Outline: Collective MindGraph MVP

### Slide 1: Title
- **Title**: Collective MindGraph
- **Subtitle**: Local-First Organizational Memory for Technical Meetings
- **Visual**: Project logo or a stylized graph connecting a microphone to a technical tree.
- **Speaker Notes**: Welcome. Introducing a privacy-first way to capture and retrieve meeting intelligence.

### Slide 2: The Problem
- **Bullet Points**:
  - Information loss in technical discussions.
  - Privacy risks with cloud-based AI.
  - Language gap in local-first Turkish tools.
- **Visual**: Icons representing a leaking bucket (info loss) and a "cloud" with a warning sign (privacy).
- **Speaker Notes**: Decisions are forgotten, and proprietary data shouldn't leave the building.

### Slide 3: The Solution
- **Bullet Points**:
  - Strictly offline-capable processing.
  - Dual-transcript preservation (Raw + Cleaned).
  - Automated technical Turkish extraction.
- **Visual**: Diagram showing audio staying on-device and turning into structured nodes.
- **Speaker Notes**: We keep everything local, ensuring data sovereignty while automating meeting minutes.

### Slide 4: Current MVP Architecture
- **Bullet Points**:
  - Local STT: Optimized Faster-Whisper.
  - Heuristic Extraction: Technical Turkish linguistic patterns.
  - Hierarchical Storage: Basic graph-node persistence in SQLite.
- **Visual**: A pipeline flow diagram (Audio -> VAD -> ASR -> Cleanup -> SQLite).
- **Speaker Notes**: Our software MVP handles the end-to-end flow entirely on local hardware.

### Slide 5: Product Loop Demo
- **Bullet Points**:
  - Automated transcript cleaning.
  - Heuristic detection of tasks and decisions.
  - Traceable Global Search.
- **Visual**: Screenshot of the Search UI navigating back to a specific transcript line.
- **Speaker Notes**: We don't just search text; we find extracted insights and link them back to their source.

### Slide 6: Validation Status
- **Bullet Points**:
  - 91% Keyword Overlap on clean Turkish speech.
  - Strictly verified offline safety guards.
  - 170+ automated regression tests.
- **Visual**: A bar chart showing the Common Voice benchmark results.
- **Speaker Notes**: We've proven the core logic on clean speech; meeting-room validation is our next step.

### Slide 8: Project Status
- **Implemented**: Local pipeline, clean-speech regression, Global Search.
- **Claim Boundary**: The project is local MVP demo ready and product-integration ready for local-first Turkish transcription and keyword-based memory exploration. It is not yet a production-validated meeting intelligence platform.
- **Next Step**: Real meeting-room audio validation.
- **Speaker Notes**: We are demo-ready and integration-ready, and we know exactly what's next.
# Pitch Summary: Collective MindGraph

## One-Sentence Explanation
Collective MindGraph is a local-first, privacy-focused system that transcribes technical Turkish conversations and automatically extracts structured organizational memory like tasks and decisions.

## 30-Second Explanation
Most organizations lose critical context after technical meetings or risk privacy by sending data to cloud AI. Collective MindGraph solves this by running a complete intelligence pipeline—from speech-to-text to task extraction—entirely on local hardware. It specifically handles technical Turkish terminology and provides a traceable memory where every decision is linked back to the exact moment it was discussed.

## 2-Minute Explanation
Collective MindGraph is more than a transcription app; it is a prototype for an autonomous organizational memory. It uses a specialized local pipeline (Faster-Whisper + heuristic extraction) to process audio. It maintains a dual-transcript model: preserving the raw ASR for auditability while providing a cleaned, readable version for intelligence extraction. 

The current MVP demonstrates a full product loop: it captures speech, cleans it, identifies tasks and decisions using Turkish-specific linguistic patterns, and stores them in a hierarchical node structure. Users can then query this memory across multiple sessions. For example, asking about a "FastAPI endpoint" retrieves the specific task and allows the user to jump straight back to that segment in the original meeting.

## The Problem
- **Information Loss**: High-value technical decisions and action items are often lost or misremembered after meetings.
- **Privacy Risks**: Sensitive corporate data is frequently sent to external cloud providers (AWS, OpenAI) for processing.
- **Language Gap**: Most local-first tools are English-biased and fail to correctly process technical Turkish meeting contexts.

## The Solution
A strictly offline-capable platform that provides:
1. **Sovereign Transcription**: Local technical Turkish STT.
2. **Automated Memory**: Heuristic extraction of organizational "nodes" (Tasks, Decisions, Topics).
3. **Traceable Knowledge**: A search interface that links every insight back to its source session.

## Current MVP Capabilities
- **Local Pipeline**: Standardized audio normalization and offline transcription.
- **Turkish Optimization**: Glossary-aware STT and necessity/future-form task extraction.
- **Traceability**: Keyword-based search with direct source-segment navigation.
- **Offline Safety**: Mandatory guards ensuring zero data egress.

## Implemented vs. Pending
- **Implemented**: ASR pipeline, raw/clean separation, heuristic extraction, basic node storage, keyword query, desktop UI.
- **Pending**: Semantic/vector search, multi-hop reasoning, hardware integration, and large-scale meeting-room validation.

## Project Status
**The project is local MVP demo ready and product-integration ready for local-first Turkish transcription and keyword-based memory exploration. It is not yet a production-validated meeting intelligence platform.**

## Why Local-First Matters
In technical and corporate environments, privacy is a functional requirement. By removing cloud dependencies, Collective MindGraph ensures that proprietary technical discussions, architectural decisions, and internal tasks remain within the organization’s secure perimeter.
# Demo Script (English)

This script is designed for presenting Collective MindGraph to professors, reviewers, or technical partners.

## Opening
"Hello, today I will present Collective MindGraph—a local-first, privacy-focused organizational memory system."

## Problem & Solution
"During technical meetings, critical decisions and tasks are often lost or misrecorded. Relying on cloud AI services creates privacy risks for sensitive data. Our solution provides a strictly offline pipeline that transcribes technical Turkish conversations and automatically extracts structured memory."

## Current MVP Capabilities
"The current prototype handles standardized audio normalization, local STT optimized for Turkish technical terms (like FastAPI and SQLite), heuristic extraction of tasks and decisions, and traceable keyword-based retrieval."

## Demo Steps

1.  **Readiness**: "First, we verify that the local environment and models are correctly configured." (`./scripts/check_demo_readiness.sh`)
2.  **Seeding Data**: "We seed the system with a technical Turkish meeting sample to demonstrate the extraction logic without requiring live audio." (`PYTHONPATH=. python realtime_backend/scripts/seed_demo_session.py`)
3.  **Launch**: "We start the local backend service on port 8080 and launch the native PySide6 desktop UI, which is our primary user interface." (`./scripts/dev_backend.sh` and `./scripts/dev_desktop.sh`)
4.  **Session Review**: "We open the 'demo_technical_turkish' session from the explorer."
5.  **Cleaned Transcript**: "Note how the system handles technical casing and filters out filler words for better readability."
6.  **Structured Insights**: "Observe the automatically extracted Tasks and Decisions in the side panel, such as 'FastAPI testing' or 'SQLite storage decisions'."
7.  **Global Search**: "Let's perform a cross-session search. I'll query for 'FastAPI endpoint'."
8.  **Traceability**: "By double-clicking the search result, the system navigates directly back to the source session and highlights the exact segment where this was mentioned."

## Important Caveats
"Current retrieval is keyword-based. We have established placeholders for semantic vector search and complex graph reasoning as part of our future roadmap."

## Closing
"Collective MindGraph establishes a stable foundation for sovereign organizational memory. Thank you for your time."

---
**Status**: The project is local MVP demo ready and product-integration ready for local-first Turkish transcription and keyword-based memory exploration. It is not yet a production-validated meeting intelligence platform.
