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
3.  **Servislerin Başlatılması**: "Arka planda ses işleme servisimiz olan FastAPI'yi 8081 portunda başlatıyoruz. Ardından, asıl kullanıcı arayüzümüz olan yerel masaüstü uygulamamızı açıyoruz." (`./scripts/dev_backend.sh` ve `./scripts/dev_desktop.sh`)
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
