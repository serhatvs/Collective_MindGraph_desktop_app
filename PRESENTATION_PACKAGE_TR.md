# Collective MindGraph: Türkçe Sunum Paketi

Bu paket, projenin mevcut "Yerel MVP" durumuna sadık kalarak, abartılı iddialardan kaçınan teknik ve genel sunum materyallerini içermektedir.

---

## 1. 2 Dakikalık Tanıtım Konuşması (Genel)

"Merhaba, bugün sizlere teknik toplantılar için geliştirdiğimiz yerel ve gizlilik odaklı kurumsal hafıza sistemi olan **Collective MindGraph**'i tanıtacağım.

**Problem:** Günümüzde teknik toplantılarda alınan kritik kararlar ve görevler genellikle ya unutuluyor ya da bu verileri işlemek için bulut tabanlı yapay zeka servislerine gönderilerek veri gizliliği riske atılıyor.

**Çözüm:** Collective MindGraph, tüm zekayı yerel donanımda tutarak teknik Türkçe konuşmaları işleyen bir yapı sunar. Mevcut MVP (Minimum Uygulanabilir Ürün) aşamamızda sistem; sesi yerel olarak metne dönüştürüyor, dolgu kelimeleri temizleyerek teknik terimleri (FastAPI, SQLite vb.) düzeltiyor ve konuşmadan otomatik olarak görev ve kararları ayıklıyor.

**Gizlilik Odaklılık:** Sistemimiz 'Local-First' prensibiyle çalışır. Yani hiçbir ses verisi veya metin dış sunuculara gönderilmez. Bu, kurumsal sırların ve teknik detayların kurum dışına çıkmasını engeller.

**Demo Akışı:** Bugün sizlere sistemin hazır bir teknik toplantı kaydı üzerinden nasıl anlık analiz yaptığını, görevleri nasıl listelediğini ve 'Global Search' arayüzü ile bu bilgilere kaynak konuşma satırına kadar nasıl ulaştığını göstereceğiz.

**Durum:** Projemiz şu an yerel MVP demo aşamasındadır. Anahtar kelime bazlı hafıza taraması için entegrasyona hazırdır, ancak henüz yüksek gürültülü gerçek toplantı odaları için tam üretim sürümü değildir. İzlediğiniz için teşekkürler."

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
**Resmi Durum Beyanı:** The project is local MVP demo ready and product-integration ready for local-first Turkish transcription and keyword-based memory exploration. It is not yet a production-validated meeting intelligence platform.
