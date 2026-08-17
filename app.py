import streamlit as st
import pandas as pd
import gspread
import json
from datetime import datetime

# 1. Sayfa Ayarları
st.set_page_config(page_title="Mod7 & SG Danışan Takip Paneli", layout="wide")
st.title("⚽ Mod7 & Sporcu Gelişimi Platformu – Danışan Takip Paneli")

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
except Exception as e:
    st.error(f"Google Sheets bağlantı hatası: {e}")

# 3. Sol Menü - Navigasyon
sayfa = st.sidebar.radio("Menü", ["Haftalık Görüşme Takvimi", "Haftalık Planı Manuel Düzenle", "Yeni Danışan Ekle", "Tüm Danışan Listesi"])

# --- SAYFA 1: HAFTALIK GÖRÜŞME TAKVİMİ ---
if sayfa == "Haftalık Görüşme Takvimi":
    st.subheader("🗓️ Bu Haftanın Görüşme Planı")
    
    try:
        data = danisanlar_sheet.get_all_records()
        df = pd.DataFrame(data)
        
        if not df.empty:
            bugun = datetime.now()
            haftalik_liste = []
            
            for index, row in df.iterrows():
                tarih_val = row.get("Baslangic Tarihi") or row.get("Başlangıç Tarihi") or row.get("Baslangic_Tarihi") or str(bugun.date())
                try:
                    baslangic = datetime.strptime(str(tarih_val).strip(), "%Y-%m-%d")
                except Exception:
                    baslangic = bugun

                gecen_hafta = max(1, ((bugun - baslangic).days // 7) + 1)
                dongu_haftasi = gecen_hafta % 4
                if dongu_haftasi == 0:
                    dongu_haftasi = 4

                platform_val = str(row.get("Platform", "")).strip().upper()
                atanan_fd = row.get("Atanan FD") or row.get("Atanan Felsefi Danışman", "-")
                atanan_psk = row.get("Atanan Psikolog", "-")

                # Otomatik kural
                if platform_val == "SG":
                    if dongu_haftasi in [1, 3]:
                        oto_gorusme = "Felsefi Danışmanlık"
                        oto_uzman = atanan_fd
                    elif dongu_haftasi == 2:
                        oto_gorusme = "Psikolog"
                        oto_uzman = atanan_psk
                    elif dongu_haftasi == 4:
                        oto_gorusme = "Psikolog + Aile Görüşmesi"
                        oto_uzman = atanan_psk
                else:
                    oto_gorusme = "Mod7 Seans"
                    oto_uzman = atanan_fd

                # Manuel atama varsa öncelikli al, yoksa otomatiği kullan
                gorusme_tipi = row.get("Bu Haftaki Görüşme") or oto_gorusme
                uzman = row.get("Bu Haftaki Uzman") or oto_uzman

                haftalik_liste.append({
                    "ID": row.get("ID", index + 1),
                    "Danışan": row.get("Ad Soyad") or row.get("Ad_Soyad", "-"),
                    "Platform": platform_val,
                    "Hafta": f"{gecen_hafta}. Hafta (Döngü: {dongu_haftasi})",
                    "Görüşme Tipi": gorusme_tipi,
                    "Sorumlu Uzman": uzman,
                    "Kulüp/Mevki": f"{row.get('Kulup', row.get('Kulübü', ''))} / {row.get('Mevki', row.get('Mevkisi', ''))}",
                    "İletişim": row.get("Telefon") or row.get("İletişim", "-")
                })
                
            st.dataframe(pd.DataFrame(haftalik_liste), use_container_width=True)
            st.caption("💡 Otomatik atanan uzmanı veya görüşme tipini değiştirmek için sol menüden 'Haftalık Planı Manuel Düzenle' sekmesini kullanabilirsiniz.")
        else:
            st.info("ℹ️ Henüz kayıtlı danışan bulunmuyor.")
    except Exception as e:
        st.warning(f"Veriler okunurken bir hata oluştu: {e}")

# --- SAYFA 2: MANUEL DÜZENLEME & ÖZEL UZMAN ATAMA ---
elif sayfa == "Haftalık Planı Manuel Düzenle":
    st.subheader("✍️ Bu Haftalık Uzman ve Görüşme Ataması")
    
    try:
        data = danisanlar_sheet.get_all_records()
        df = pd.DataFrame(data)
        
        if not df.empty:
            danisan_adlari = df["Ad Soyad"].tolist() if "Ad Soyad" in df.columns else df["Ad_Soyad"].tolist()
            secilen_danisan = st.selectbox("Düzenlemek İstediğiniz Danışanı Seçin", danisan_adlari)
            
            secilen_satir = df[df["Ad Soyad"] == secilen_danisan].iloc[0] if "Ad Soyad" in df.columns else df[df["Ad_Soyad"] == secilen_danisan].iloc[0]
            satir_no = df[df["Ad Soyad"] == secilen_danisan].index[0] + 2
            
            with st.form("manuel_duzenleme_formu"):
                col1, col2 = st.columns(2)
                
                with col1:
                    gorusme_secenekleri = [
                        "Felsefi Danışmanlık",
                        "Psikolog Seansı",
                        "Aile Görüşmesi",
                        "İletişim & Medya Seansı",
                        "Sosyal Medya Çalışması",
                        "İngilizce / Dil Seansı",
                        "Pas / Görüşme Yok",
                        "Özel Seans"
                    ]
                    yeni_gorusme = st.selectbox("Bu Haftaki Görüşme Tipi", gorusme_secenekleri)
                
                with col2:
                    yeni_uzman = st.text_input("Bu Haftaki Sorumlu Uzman", value=str(secilen_satir.get("Atanan FD", "")))
                
                kaydet = st.form_submit_button("Haftalık Atamayı Güncelle")
                
                if kaydet:
                    headers = danisanlar_sheet.row_values(1)
                    if "Bu Haftaki Görüşme" not in headers:
                        danisanlar_sheet.update_cell(1, len(headers) + 1, "Bu Haftaki Görüşme")
                        headers.append("Bu Haftaki Görüşme")
                    if "Bu Haftaki Uzman" not in headers:
                        danisanlar_sheet.update_cell(1, len(headers) + 1, "Bu Haftaki Uzman")
                        headers.append("Bu Haftaki Uzman")
                    
                    gorusme_col = headers.index("Bu Haftaki Görüşme") + 1
                    uzman_col = headers.index("Bu Haftaki Uzman") + 1
                    
                    danisanlar_sheet.update_cell(satir_no, gorusme_col, yeni_gorusme)
                    danisanlar_sheet.update_cell(satir_no, uzman_col, yeni_uzman)
                    
                    st.success(f"{secilen_danisan} için bu haftaki atama '{yeni_uzman} ({yeni_gorusme})' olarak güncellendi!")
                    st.cache_resource.clear()
        else:
            st.info("Kayıtlı danışan bulunamadı.")
    except Exception as e:
        st.error(f"Hata: {e}")

# --- SAYFA 3: YENİ DANIŞAN EKLE ---
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
            baslangic_tarihi = st.date_input("Süreç Başlangıç Tarihi", datetime.now())
        
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
            except Exception as e:
                st.error(f"Kayıt eklenirken bir hata oluştu: {e}")

# --- SAYFA 4: TÜM DANIŞAN LİSTESİ ---
elif sayfa == "Tüm Danışan Listesi":
    st.subheader("📋 Sistemdeki Tüm Danışanlar")
    try:
        data = danisanlar_sheet.get_all_records()
        st.dataframe(pd.DataFrame(data), use_container_width=True)
    except Exception as e:
        st.error(f"Veriler listelenirken hata oluştu: {e}")
