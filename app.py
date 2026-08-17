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
sayfa = st.sidebar.radio("Menü", ["Haftalık Görüşme Takvimi", "Yeni Danışan Ekle", "Tüm Danışan Listesi"])

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

                if platform_val == "SG":
                    if dongu_haftasi in [1, 3]:
                        gorusme_tipi = "Felsefi Danışmanlık (Çocuk)"
                        uzman = atanan_fd
                    elif dongu_haftasi == 2:
                        gorusme_tipi = "Psikolog (Çocuk)"
                        uzman = atanan_psk
                    elif dongu_haftasi == 4:
                        gorusme_tipi = "Psikolog (Çocuk) + Aile Görüşmesi"
                        uzman = atanan_psk
                else:
                    gorusme_tipi = "Mod7 Bireysel Seans"
                    uzman = atanan_fd

                haftalik_liste.append({
                    "Danışan": row.get("Ad Soyad") or row.get("Ad_Soyad", "-"),
                    "Platform": platform_val,
                    "Hafta": f"{gecen_hafta}. Hafta (Döngü: {dongu_haftasi})",
                    "Görüşme Tipi": gorusme_tipi,
                    "Sorumlu Uzman": uzman,
                    "Kulüp/Mevki": f"{row.get('Kulup', row.get('Kulübü', ''))} / {row.get('Mevki', row.get('Mevkisi', ''))}",
                    "İletişim": row.get("Telefon") or row.get("İletişim", "-")
                })
                
            st.dataframe(pd.DataFrame(haftalik_liste), use_container_width=True)
        else:
            st.info("ℹ️ Henüz kayıtlı danışan bulunmuyor. Sol menüden 'Yeni Danışan Ekle' bölümünden kayıt oluşturabilirsiniz.")
    except Exception as e:
        st.warning(f"Veriler okunurken bir hata oluştu: {e}")

# --- SAYFA 2: YENİ DANIŞAN EKLE ---
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

# --- SAYFA 3: TÜM DANIŞAN LİSTESİ ---
elif sayfa == "Tüm Danışan Listesi":
    st.subheader("📋 Sistemdeki Tüm Danışanlar")
    try:
        data = danisanlar_sheet.get_all_records()
        st.dataframe(pd.DataFrame(data), use_container_width=True)
    except Exception as e:
        st.error(f"Veriler listelenirken hata oluştu: {e}")
