import streamlit as st
import pandas as pd
import gspread
import json
from datetime import datetime, timedelta, timezone

# 1. Sayfa Ayarları
st.set_page_config(page_title="Mod7 & SG Danışan Takip & Randevu Sistemi", layout="wide")

# Türkiye Saat Dilimi (UTC+3)
TR_TZ = timezone(timedelta(hours=3))

GORUSME_SECENEKLERI = [
    "Felsefi Danışmanlık",
    "Psikolojik Performans Seansı",
    "Psikoloji Seansı (Bireysel)",
    "Aile Görüşmesi",
    "İletişim & Medya Seansı",
    "Sosyal Medya Çalışması",
    "İngilizce / Dil Seansı",
    "Pas / Görüşme Yok",
    "Özel Seans"
]

UZMAN_LISTESI = [
    "Sena", "Dilara", "Mehmet", "Salih", "Gülşah", "Busenaz", "Canan", "Beste", "Ebru", "Koray", "Burak"
]

# 2. Google Sheets Bağlantısı
@st.cache_resource
def get_google_sheet():
    if "credentials_json" in st.secrets:
        creds_dict = json.loads(st.secrets["credentials_json"])
        gc = gspread.service_account_from_dict(creds_dict)
    else:
        gc = gspread.service_account(filename="credentials.json")
    
    sheet = gc.open("Danisan_Takip_Sistemi")
    return sheet

try:
    sheet = get_google_sheet()
    danisanlar_sheet = sheet.worksheet("Danisanlar")
    
    try:
        musaitlik_sheet = sheet.worksheet("Musaitlikler")
    except Exception:
        musaitlik_sheet = sheet.add_worksheet(title="Musaitlikler", rows="100", cols="10")
        musaitlik_sheet.append_row(["ID", "Uzman", "Tarih", "Saat", "Durum", "Alinan_Danisan"])
except Exception as e:
    st.error(f"Google Sheets bağlantı hatası: {e}")

# 3. Yardımcı Fonksiyonlar
def format_durum(deger):
    if deger in [True, "Yapıldı", "True", "true", "TRUE", 1, "1"]:
        return "✅ Yapıldı"
    elif deger in ["İptal", "Yapılmadı", "❌ İptal / Yapılmadı"]:
        return "❌ Yapılmadı"
    return "⏳ Bekliyor"

def isim_temizle(isim):
    """'Sena Hoca', 'Psk. Sena' gibi unvanları temizler, kök ismi bulur."""
    isim_str = str(isim).lower()
    for unvan in ["hoca", "hocası", "psk", "psk.", "uzm", "uzm.", "dr", "dr."]:
        isim_str = isim_str.replace(unvan, "")
    return isim_str.strip()

# 4. URL Parametresi Kontrolü (Sporcu Özel Randevu Ekranı)
params = st.query_params
secilen_sporcu_param = params.get("danisan", None)

# --- SPORCU LİNKE TIKLADIĞINDA ÇIKACAK ÖZEL EKRAN ---
if secilen_sporcu_param:
    st.markdown(f"## 🏆 Sporcu Gelişimi & Mod7 – Randevu Seçim Ekranı")
    st.info(f"Hoş geldin **{secilen_sporcu_param}**, lütfen görüşme saatinizi seçiniz.")
    
    try:
        data = danisanlar_sheet.get_all_records()
        df = pd.DataFrame(data)
        
        # Danışan adını esnek bulma
        df_cols = {c.strip(): c for c in df.columns}
        ad_col = df_cols.get("Ad Soyad", df_cols.get("Ad_Soyad", list(df.columns)[1]))
        
        danisan_row = df[df[ad_col].astype(str).str.lower().str.strip() == secilen_sporcu_param.lower().strip()]
        
        if not danisan_row.empty:
            row_data = danisan_row.iloc[0]
            atanan_uzman = str(row_data.get("Bu Haftaki Uzman") or row_data.get("Atanan FD") or "Sena").strip()
            atanan_gorusme = str(row_data.get("Bu Haftaki Görüşme") or "Felsefi Danışmanlık").strip()
            
            st.markdown(f"**Görüşeceğiniz Uzman:** `{atanan_uzman}` | **Seans Türü:** `{atanan_gorusme}`")
            
            # Musaitlikler sayfasını oku
            m_data = musaitlik_sheet.get_all_records()
            m_df = pd.DataFrame(m_data)
            
            if not m_df.empty:
                # Sütun başlıklarını normalize et
                m_df.columns = [str(c).strip().title() for c in m_df.columns]
                
                uzman_kok = isim_temizle(atanan_uzman)
                
                # Eşleşen ve durumu 'Müsait' olan slotları filtrele
                uygun_slotlar = m_df[
                    (m_df["Uzman"].astype(str).apply(isim_temizle).str.contains(uzman_kok)) & 
                    (m_df["Durum"].astype(str).str.strip().str.lower() == "müsait")
                ]
                
                if not uygun_slotlar.empty:
                    slot_secenekleri = [f"{str(r['Tarih']).strip()} | {str(r['Saat']).strip()}" for _, r in uygun_slotlar.iterrows()]
                    secilen_slot = st.selectbox("Size Uygun Randevu Saatini Seçin", slot_secenekleri)
                    
                    if st.button("Randevumu Onayla"):
                        secilen_tarih, secilen_saat = secilen_slot.split(" | ")
                        
                        # Musaitlik slotunu Dolu yap
                        m_headers = [str(h).strip().title() for h in musaitlik_sheet.row_values(1)]
                        orj_headers = musaitlik_sheet.row_values(1)
                        
                        matched_row = uygun_slotlar[
                            (uygun_slotlar["Tarih"].astype(str).str.strip() == secilen_tarih.strip()) & 
                            (uygun_slotlar["Saat"].astype(str).str.strip() == secilen_saat.strip())
                        ]
                        
                        m_idx = matched_row.index[0] + 2
                        durum_col_idx = m_headers.index("Durum") + 1 if "Durum" in m_headers else 5
                        danisan_col_idx = m_headers.index("Alinan_Danisan") + 1 if "Alinan_Danisan" in m_headers else 6
                        
                        musaitlik_sheet.update_cell(m_idx, durum_col_idx, "Dolu")
                        musaitlik_sheet.update_cell(m_idx, danisan_col_idx, secilen_sporcu_param)
                        
                        # Danışanlar sayfasında bu haftalık durumu 'Yapıldı' yap
                        d_satir_no = danisan_row.index[0] + 2
                        d_headers = danisanlar_sheet.row_values(1)
                        if "Bu Hafta Durum" in d_headers:
                            danisanlar_sheet.update_cell(d_satir_no, d_headers.index("Bu Hafta Durum") + 1, "Yapıldı")
                        
                        st.success(f"🎉 Randevunuz başarıyla oluşturuldu! {secilen_tarih} saat {secilen_saat} için randevunuz kaydedildi.")
                        st.balloons()
                        st.cache_resource.clear()
                else:
                    st.warning(f"**{atanan_uzman}** için şu anda açık müsait saat bulunmamaktadır. Lütfen koordinatörünüz ile iletişime geçiniz.")
            else:
                st.warning("Sistemde henüz girilmiş bir müsaitlik bulunmuyor.")
        else:
            st.error("Danışan kaydınız bulunamadı. Lütfen size iletilen bağlantıyı kontrol ediniz.")
    except Exception as e:
        st.error(f"Hata oluştu: {e}")
    st.stop()

# --- YÖNETİM & KOORDİNASYON PANELİ ---
st.title("⚽ Mod7 & Sporcu Gelişimi Platformu – Yönetim Paneli")

sayfa = st.sidebar.radio("Menü", [
    "Haftalık Görüşme Takvimi", 
    "🗓️ Hoca Müsaitlik Girişi",
    "🔗 Sporcu Randevu Linkleri",
    "Haftalık Planı Manuel Düzenle & Yoklama", 
    "Yeni Danışan Ekle", 
    "Tüm Danışan Listesi"
])

# --- MENÜ 1: HAFTALIK GÖRÜŞME TAKVİMİ ---
if sayfa == "Haftalık Görüşme Takvimi":
    st.subheader("🗓️ Bu Haftanın Görüşme Planı")
    
    try:
        data = danisanlar_sheet.get_all_records()
        df = pd.DataFrame(data)
        
        if not df.empty:
            bugun = datetime.now(TR_TZ)
            haftalik_liste = []
            
            for index, row in df.iterrows():
                tarih_val = row.get("Baslangic Tarihi") or row.get("Başlangıç Tarihi") or row.get("Baslangic_Tarihi") or str(bugun.date())
                try:
                    baslangic = datetime.strptime(str(tarih_val).strip(), "%Y-%m-%d").replace(tzinfo=TR_TZ)
                except Exception:
                    baslangic = bugun

                gecen_hafta = max(1, ((bugun.date() - baslangic.date()).days // 7) + 1)
                dongu_haftasi = gecen_hafta % 4
                if dongu_haftasi == 0:
                    dongu_haftasi = 4

                platform_val = str(row.get("Platform", "")).strip().upper()
                atanan_fd = row.get("Atanan FD") or row.get("Atanan Felsefi Danışman", "-")
                atanan_psk = row.get("Atanan Psikolog", "-")

                if platform_val == "SG":
                    if dongu_haftasi in [1, 3]:
                        oto_gorusme = "Felsefi Danışmanlık"
                        oto_uzman = atanan_fd
                    elif dongu_haftasi == 2:
                        oto_gorusme = "Psikoloji Seansı (Bireysel)"
                        oto_uzman = atanan_psk
                    elif dongu_haftasi == 4:
                        oto_gorusme = "Aile Görüşmesi"
                        oto_uzman = atanan_psk
                else:
                    oto_gorusme = "Mod7 Seans"
                    oto_uzman = atanan_fd

                bu_hafta_gorusme = row.get("Bu Haftaki Görüşme") or oto_gorusme
                bu_hafta_uzman = row.get("Bu Haftaki Uzman") or oto_uzman
                bu_hafta_durum = format_durum(row.get("Bu Hafta Durum") or row.get("Görüşme Durumu"))

                gecen_hafta_gorusme = row.get("Geçen Haftaki Görüşme") or "-"
                gecen_hafta_uzman = row.get("Geçen Haftaki Uzman") or "-"
                gecen_hafta_durum = format_durum(row.get("Geçen Hafta Durum"))

                haftalik_liste.append({
                    "Danışan": row.get("Ad Soyad") or row.get("Ad_Soyad", "-"),
                    "Platform": platform_val,
                    "Hafta": f"{gecen_hafta}. Hafta (Döngü: {dongu_haftasi})",
                    "Bu Haftaki Görüşme": bu_hafta_gorusme,
                    "Bu Haftaki Uzman": bu_hafta_uzman,
                    "Bu Hafta": bu_hafta_durum,
                    "Geçen Haftaki Görüşme": gecen_hafta_gorusme,
                    "Geçen Haftaki Uzman": gecen_hafta_uzman,
                    "Geçen Hafta": gecen_hafta_durum,
                    "Kulüp/Mevki": f"{row.get('Kulup', row.get('Kulübü', ''))} / {row.get('Mevki', row.get('Mevkisi', ''))}",
                    "İletişim": row.get("Telefon") or row.get("İletişim", "-")
                })
                
            st.dataframe(pd.DataFrame(haftalik_liste), use_container_width=True)
            st.caption("💡 Seans onaylarını (tikleri) güncellemek veya uzman/seans tipi değiştirmek için sol menüden **'Haftalık Planı Manuel Düzenle & Yoklama'** sekmesine geçin.")
        else:
            st.info("Tabloda kayıtlı danışan bulunmuyor.")
    except Exception as e:
        st.warning(f"Veriler okunurken bir hata oluştu: {e}")

# --- MENÜ 2: HOCA MÜSAİTLİK GİRİŞİ ---
elif sayfa == "🗓️ Hoca Müsaitlik Girişi":
    st.subheader("🗓️ Uzman Müsaitlik Saatleri Tanımlama")
    st.markdown("Hocalar bu alandan uygun oldukları tarih ve saat aralıklarını ekleyebilir.")
    
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        with st.form("musaitlik_ekle_formu"):
            secilen_hoca = st.selectbox("Uzman Seçin", UZMAN_LISTESI)
            m_tarih = st.date_input("Müsait Olduğunuz Tarih", datetime.now().date() + timedelta(days=1))
            m_saat = st.time_input("Müsait Başlangıç Saati", datetime.strptime("14:00", "%H:%M").time())
            
            m_kaydet = st.form_submit_button("Müsaitlik Slotunu Ekle")
            if m_kaydet:
                try:
                    m_records = musaitlik_sheet.get_all_records()
                    yeni_m_id = len(m_records) + 1
                    yeni_slot = [
                        yeni_m_id, 
                        secilen_hoca, 
                        m_tarih.strftime("%Y-%m-%d"), 
                        m_saat.strftime("%H:%M"), 
                        "Müsait", 
                        "-"
                    ]
                    musaitlik_sheet.append_row(yeni_slot)
                    st.success(f"{secilen_hoca} için {m_tarih} {m_saat.strftime('%H:%M')} saati başarıyla eklendi!")
                    st.cache_resource.clear()
                except Exception as e:
                    st.error(f"Slot eklenirken hata oluştu: {e}")

    with col_m2:
        st.markdown("#### Mevcut Müsaitlik Listesi")
        try:
            m_data = musaitlik_sheet.get_all_records()
            if m_data:
                st.dataframe(pd.DataFrame(m_data), use_container_width=True)
            else:
                st.info("Kayıtlı müsaitlik bulunmuyor.")
        except Exception as e:
            st.error(f"Veriler listelenirken hata: {e}")

# --- MENÜ 3: SPORCUYA ÖZEL RANDEVU LİNKLERİ ---
elif sayfa == "🔗 Sporcu Randevu Linkleri":
    st.subheader("🔗 Sporculara Gönderilecek Kişisel Randevu Linkleri")
    st.caption("Aşağıdaki bağlantıları sporculara ilettiğinizde, sporcu doğrudan kendi hocasının müsaitlik saatlerinden seçim yapabilir.")
    
    try:
        data = danisanlar_sheet.get_all_records()
        df = pd.DataFrame(data)
        
        if not df.empty:
            linkler = []
            base_url = "https://mod7-sg-takip.streamlit.app"
            
            for _, r in df.iterrows():
                ad = r.get("Ad Soyad") or r.get("Ad_Soyad", "-")
                uzman = r.get("Bu Haftaki Uzman") or r.get("Atanan FD", "-")
                gorusme = r.get("Bu Haftaki Görüşme") or "Felsefi Danışmanlık"
                link = f"{base_url}/?danisan={ad.replace(' ', '+')}"
                
                linkler.append({
                    "Danışan": ad,
                    "Bu Haftaki Uzmanı": uzman,
                    "Görüşme Türü": gorusme,
                    "Kişisel Randevu Linki": link
                })
            
            st.dataframe(pd.DataFrame(linkler), use_container_width=True)
        else:
            st.info("Kayıtlı danışan bulunmuyor.")
    except Exception as e:
        st.error(f"Hata: {e}")

# --- MENÜ 4: MANUEL DÜZENLEME & ÇİFT YOKLAMA ---
elif sayfa == "Haftalık Planı Manuel Düzenle & Yoklama":
    st.subheader("✍️ Manuel Düzenleme & Seans Takibi")
    
    try:
        data = danisanlar_sheet.get_all_records()
        df = pd.DataFrame(data)
        
        if not df.empty:
            danisan_adlari = df["Ad Soyad"].tolist() if "Ad Soyad" in df.columns else df["Ad_Soyad"].tolist()
            secilen_danisan = st.selectbox("Düzenlemek İstediğiniz Danışanı Seçin", danisan_adlari)
            
            secilen_satir = df[df["Ad Soyad"] == secilen_danisan].iloc[0] if "Ad Soyad" in df.columns else df[df["Ad_Soyad"] == secilen_danisan].iloc[0]
            satir_no = df[df["Ad Soyad"] == secilen_danisan].index[0] + 2

            mevcut_bu_uzman = secilen_satir.get("Bu Haftaki Uzman") or secilen_satir.get("Atanan FD", "-")
            mevcut_bu_gorusme = secilen_satir.get("Bu Haftaki Görüşme") or "Felsefi Danışmanlık"
            mevcut_bu_durum = secilen_satir.get("Bu Hafta Durum") in [True, "Yapıldı", "True", "true", "TRUE", 1, "1"]

            mevcut_gecen_uzman = secilen_satir.get("Geçen Haftaki Uzman") or "-"
            mevcut_gecen_gorusme = secilen_satir.get("Geçen Haftaki Görüşme") or "Psikolojik Performans Seansı"
            mevcut_gecen_durum = secilen_satir.get("Geçen Hafta Durum") in [True, "Yapıldı", "True", "true", "TRUE", 1, "1"]

            st.markdown("---")
            col_info1, col_info2, col_info3, col_info4 = st.columns(4)
            with col_info1:
                st.metric("Geçen Hafta", f"{mevcut_gecen_uzman}", help=f"Görüşme: {mevcut_gecen_gorusme}")
            with col_info2:
                st.metric("Geçen Hafta Durumu", "✅ Yapıldı" if mevcut_gecen_durum else "⏳ Bekliyor")
            with col_info3:
                st.metric("Bu Hafta", f"{mevcut_bu_uzman}", help=f"Görüşme: {mevcut_bu_gorusme}")
            with col_info4:
                st.metric("Bu Hafta Durumu", "✅ Yapıldı" if mevcut_bu_durum else "⏳ Bekliyor")
            st.markdown("---")

            with st.form("manuel_duzenleme_ve_yoklama_formu"):
                col_g, col_b = st.columns(2)
                
                with col_g:
                    st.markdown("#### ⏮️ Geçen Haftanın Durumu")
                    idx_gecen = GORUSME_SECENEKLERI.index(mevcut_gecen_gorusme) if mevcut_gecen_gorusme in GORUSME_SECENEKLERI else 1
                    yeni_gecen_gorusme = st.selectbox("Geçen Haftaki Görüşme Tipi", GORUSME_SECENEKLERI, index=idx_gecen, key="gecen_gorusme")
                    gecen_uzman_input = st.text_input("Geçen Haftaki Uzman", value=str(mevcut_gecen_uzman), key="gecen_uzman")
                    gecen_yapildi_mi = st.checkbox("✅ Geçen haftaki görüşme yapıldı", value=mevcut_gecen_durum)

                with col_b:
                    st.markdown("#### ⏭️ Bu Haftanın Durumu & Ataması")
                    idx_bu = GORUSME_SECENEKLERI.index(mevcut_bu_gorusme) if mevcut_bu_gorusme in GORUSME_SECENEKLERI else 0
                    yeni_bu_gorusme = st.selectbox("Bu Haftaki Görüşme Tipi", GORUSME_SECENEKLERI, index=idx_bu, key="bu_gorusme")
                    bu_uzman_input = st.text_input("Bu Haftaki Uzman", value=str(mevcut_bu_uzman), key="bu_uzman")
                    bu_yapildi_mi = st.checkbox("✅ Bu haftaki görüşme yapıldı", value=mevcut_bu_durum)

                st.markdown("---")
                kaydet = st.form_submit_button("Bilgileri Kaydet ve Tabloyu Güncelle")
                
                if kaydet:
                    headers = danisanlar_sheet.row_values(1)
                    gerekli_sutunlar = [
                        "Bu Haftaki Görüşme", "Bu Haftaki Uzman", "Bu Hafta Durum",
                        "Geçen Haftaki Görüşme", "Geçen Haftaki Uzman", "Geçen Hafta Durum"
                    ]
                    for sutun in gerekli_sutunlar:
                        if sutun not in headers:
                            danisanlar_sheet.update_cell(1, len(headers) + 1, sutun)
                            headers.append(sutun)

                    danisanlar_sheet.update_cell(satir_no, headers.index("Geçen Haftaki Görüşme") + 1, str(yeni_gecen_gorusme))
                    danisanlar_sheet.update_cell(satir_no, headers.index("Geçen Haftaki Uzman") + 1, str(gecen_uzman_input))
                    danisanlar_sheet.update_cell(satir_no, headers.index("Geçen Hafta Durum") + 1, "Yapıldı" if gecen_yapildi_mi else "Bekliyor")
                    
                    danisanlar_sheet.update_cell(satir_no, headers.index("Bu Haftaki Görüşme") + 1, str(yeni_bu_gorusme))
                    danisanlar_sheet.update_cell(satir_no, headers.index("Bu Haftaki Uzman") + 1, str(bu_uzman_input))
                    danisanlar_sheet.update_cell(satir_no, headers.index("Bu Hafta Durum") + 1, "Yapıldı" if bu_yapildi_mi else "Bekliyor")
                    
                    st.success(f"{secilen_danisan} kaydı güncellendi!")
                    st.cache_resource.clear()
        else:
            st.info("Kayıtlı danışan bulunamadı.")
    except Exception as e:
        st.error(f"Hata: {e}")

# --- MENÜ 5: YENİ DANIŞAN EKLE ---
elif sayfa == "Yeni Danışan Ekle":
    st.subheader("➕ Yeni Danışan Kaydı")
    
    with st.form("yeni_danisan_formu"):
        col1, col2 = st.columns(2)
        with col1:
            ad_soyad = st.text_input("Ad Soyad")
            platform = st.selectbox("Platform", ["SG", "Mod7"])
            kulup = st.text_input("Kulübü")
            mevki = st.text_input("Mevkisi / Branşı")
            tur = st.selectbox("Spor Türü", ["Takım Sporu", "Bireysel Spor"])
            cinsiyet = st.selectbox("Cinsiyet", ["Erkek", "Kadın"])
        
        with col2:
            atanan_fd = st.text_input("Atanan Felsefi Danışman")
            atanan_psk = st.text_input("Atanan Psikolog")
            telefon = st.text_input("İletişim / Telefon")
            gorsel = st.selectbox("Maç Görseli Hazırlanacak mı?", ["Hayır", "Evet"])
            baslangic_tarihi = st.date_input("Süreç Başlangıç Tarihi", datetime.now().date())
        
        submit = st.form_submit_button("Danışanı Kaydet")
        
        if submit:
            try:
                mevcut_kayitlar = danisanlar_sheet.get_all_records()
                yeni_id = len(mevcut_kayitlar) + 1
                yeni_satir = [
                    yeni_id, ad_soyad, platform, kulup, mevki, tur, 
                    cinsiyet, atanan_fd, atanan_psk, telefon, gorsel, 
                    baslangic_tarihi.strftime("%Y-%m-%d")
                ]
                danisanlar_sheet.append_row(yeni_satir)
                st.success(f"{ad_soyad} başarıyla sisteme eklendi!")
                st.cache_resource.clear()
            except Exception as e:
                st.error(f"Kayıt eklenirken bir hata oluştu: {e}")

# --- MENÜ 6: TÜM DANIŞAN LİSTESİ ---
elif sayfa == "Tüm Danışan Listesi":
    st.subheader("📋 Sistemdeki Tüm Danışanlar")
    try:
        data = danisanlar_sheet.get_all_records()
        st.dataframe(pd.DataFrame(data), use_container_width=True)
    except Exception as e:
        st.error(f"Veriler listelenirken hata oluştu: {e}")
