import streamlit as st
import pandas as pd
import gspread
import json
import re
from datetime import datetime, timedelta, timezone
from google.oauth2 import service_account
from googleapiclient.discovery import build

# 1. Sayfa Ayarları
st.set_page_config(page_title="Mod7 & SG Danışan Takip & Randevu Sistemi", layout="wide")

TR_TZ = timezone(timedelta(hours=3))
CALENDAR_ID = "df72b1757a4992324ec30b83ff62a2956242153f3a3f9ed65e48a56f8138b723@group.calendar.google.com"

GUNLER_TR = {
    0: "PAZARTESİ",
    1: "SALI",
    2: "ÇARŞAMBA",
    3: "PERŞEMBE",
    4: "CUMA",
    5: "CUMARTESİ",
    6: "PAZAR"
}

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

# 2. Google Servis Bağlantıları
@st.cache_resource
def get_services():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/calendar.events"
    ]
    if "credentials_json" in st.secrets:
        creds_dict = json.loads(st.secrets["credentials_json"])
        creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=scopes)
        gc = gspread.service_account_from_dict(creds_dict)
    else:
        creds = service_account.Credentials.from_service_account_file("credentials.json", scopes=scopes)
        gc = gspread.service_account(filename="credentials.json")
    
    cal_service = build("calendar", "v3", credentials=creds)
    sheet = gc.open("Danisan_Takip_Sistemi")
    return sheet, cal_service

try:
    sheet, calendar_service = get_services()
    danisanlar_sheet = sheet.worksheet("Danisanlar")
    
    try:
        musaitlik_sheet = sheet.worksheet("Musaitlikler")
    except Exception:
        musaitlik_sheet = sheet.add_worksheet(title="Musaitlikler", rows="100", cols="10")
        musaitlik_sheet.append_row(["ID", "Uzman", "Tarih", "Saat", "Durum", "Alinan_Danisan"])
except Exception as e:
    st.error(f"Google bağlantı hatası: {e}")

# 3. Yardımcı Fonksiyonlar
def tr_lower(metin):
    if not metin:
        return ""
    m = str(metin).strip()
    return m.replace("İ", "i").replace("I", "ı").replace("Ğ", "ğ").replace("Ü", "ü").replace("Ş", "ş").replace("Ö", "ö").replace("Ç", "ç").lower()

def tarih_gun_formatla(tarih_str):
    """'2026-08-19' formatını '2026-08-19 (ÇARŞAMBA)' şekline çevirir."""
    try:
        dt = datetime.strptime(str(tarih_str).strip(), "%Y-%m-%d")
        gun_adi = GUNLER_TR.get(dt.weekday(), "")
        return f"{tarih_str.strip()} ({gun_adi})"
    except Exception:
        return str(tarih_str)

def format_durum(deger):
    deger_str = tr_lower(deger)
    if deger_str in ["true", "1", "yapıldı", "✅ yapıldı", "yapildi"]:
        return "✅ Yapıldı"
    elif deger_str in ["iptal", "yapılmadı", "❌ yapılmadı", "yapilmadi", "iptal / yapılmadı"]:
        return "❌ Yapılmadı"
    return "⏳ Bekliyor"

def isim_temizle(isim):
    isim_str = tr_lower(isim)
    for unvan in ["hoca", "hocası", "psk", "psk.", "uzm", "uzm.", "dr", "dr."]:
        isim_str = isim_str.replace(unvan, "")
    return isim_str.strip()

def sutun_temizle(df):
    yeni_kolonlar = []
    for c in df.columns:
        temiz = re.sub(r'[^a-zA-Z0-9_ğüşıöçĞÜŞİÖÇ]', '', str(c)).strip()
        yeni_kolonlar.append(temiz.title())
    df.columns = yeni_kolonlar
    return df

def sutun_bul(headers, olasi_isimler):
    for isim in olasi_isimler:
        for idx, h in enumerate(headers):
            if tr_lower(h) == tr_lower(isim):
                return idx + 1
    return None

def takvime_etkinlik_yaz(danisan, uzman, gorusme_tipi, tarih_str, saat_str, konum="online"):
    try:
        tarih_dt = datetime.strptime(tarih_str.strip(), "%Y-%m-%d").date()
        saat_dt = datetime.strptime(saat_str.strip(), "%H:%M").time()
        
        baslangic_dt = datetime.combine(tarih_dt, saat_dt, tzinfo=TR_TZ)
        bitis_dt = baslangic_dt + timedelta(hours=1)
        
        summary = f"{danisan} {uzman} {gorusme_tipi} {konum}".strip()
        event_body = {
            "summary": summary,
            "description": f"Mod7 & SG Randevu Sistemi: {gorusme_tipi} | Uzman: {uzman}",
            "start": {"dateTime": baslangic_dt.isoformat()},
            "end": {"dateTime": bitis_dt.isoformat()},
        }
        res = calendar_service.events().insert(calendarId=CALENDAR_ID, body=event_body).execute()
        return True, res.get("htmlLink", "")
    except Exception as e:
        return False, str(e)

# 4. URL Parametresi Kontrolü (Sporcu Özel Randevu Ekranı)
params = st.query_params
secilen_sporcu_param = params.get("danisan", None)

# --- SPORCU ÖZEL EKRANI ---
if secilen_sporcu_param:
    st.markdown(f"## 🏆 Sporcu Gelişimi & Mod7 – Randevu Seçim Ekranı")
    st.info(f"Hoş geldin **{secilen_sporcu_param}**, lütfen görüşme saatinizi seçiniz.")
    
    try:
        data = danisanlar_sheet.get_all_records()
        df = pd.DataFrame(data)
        
        df_cols = {c.strip(): c for c in df.columns}
        ad_col = df_cols.get("Ad Soyad", df_cols.get("Ad_Soyad", list(df.columns)[1]))
        
        danisan_row = df[df[ad_col].apply(tr_lower) == tr_lower(secilen_sporcu_param)]
        
        if not danisan_row.empty:
            row_data = danisan_row.iloc[0]
            atanan_uzman = str(row_data.get("Bu Haftaki Uzman") or row_data.get("Atanan FD") or "Sena").strip()
            atanan_gorusme = str(row_data.get("Bu Haftaki Görüşme") or "Felsefi Danışmanlık").strip()
            
            st.markdown(f"**Görüşeceğiniz Uzman:** `{atanan_uzman}` | **Seans Türü:** `{atanan_gorusme}`")
            
            m_data = musaitlik_sheet.get_all_records()
            m_df = pd.DataFrame(m_data)
            
            if not m_df.empty:
                m_df = sutun_temizle(m_df)
                uzman_kok = isim_temizle(atanan_uzman)
                
                tarih_col = [c for c in m_df.columns if "Tarih" in c][0] if any("Tarih" in c for c in m_df.columns) else "Tarih"
                saat_col = [c for c in m_df.columns if "Saat" in c][0] if any("Saat" in c for c in m_df.columns) else "Saat"
                durum_col = [c for c in m_df.columns if "Durum" in c][0] if any("Durum" in c for c in m_df.columns) else "Durum"
                uzman_col = [c for c in m_df.columns if "Uzman" in c][0] if any("Uzman" in c for c in m_df.columns) else "Uzman"

                uygun_slotlar = m_df[
                    (m_df[uzman_col].astype(str).apply(isim_temizle).str.contains(uzman_kok)) & 
                    (m_df[durum_col].astype(str).apply(tr_lower) == "müsait")
                ]
                
                if not uygun_slotlar.empty:
                    slot_map = {}
                    for _, r in uygun_slotlar.iterrows():
                        t_ham = str(r[tarih_col]).strip()
                        s_ham = str(r[saat_col]).strip()
                        etiket = f"{tarih_gun_formatla(t_ham)}  |  ⏰ {s_ham}"
                        slot_map[etiket] = (t_ham, s_ham)

                    secilen_etiket = st.selectbox("Size Uygun Randevu Saatini Seçin", list(slot_map.keys()))
                    
                    if st.button("Randevumu Onayla"):
                        secilen_tarih, secilen_saat = slot_map[secilen_etiket]
                        
                        cal_ok, cal_result = takvime_etkinlik_yaz(secilen_sporcu_param, atanan_uzman, atanan_gorusme, secilen_tarih, secilen_saat)
                        
                        if cal_ok:
                            m_headers = musaitlik_sheet.row_values(1)
                            matched_row = uygun_slotlar[
                                (uygun_slotlar[tarih_col].astype(str).str.strip() == secilen_tarih.strip()) & 
                                (uygun_slotlar[saat_col].astype(str).str.strip() == secilen_saat.strip())
                            ]
                            m_idx = matched_row.index[0] + 2
                            durum_col_idx = sutun_bul(m_headers, ["Durum"]) or 5
                            danisan_col_idx = sutun_bul(m_headers, ["Alinan_Danisan", "Alinan Danisan", "Danisan"]) or 6
                            
                            musaitlik_sheet.update_cell(m_idx, durum_col_idx, "Dolu")
                            musaitlik_sheet.update_cell(m_idx, danisan_col_idx, secilen_sporcu_param)
                            
                            d_satir_no = danisan_row.index[0] + 2
                            d_headers = danisanlar_sheet.row_values(1)
                            bu_hafta_col_idx = sutun_bul(d_headers, ["Bu Hafta Durum", "Bu Hafta", "Görüşme Durumu", "Durum"])
                            if bu_hafta_col_idx:
                                danisanlar_sheet.update_cell(d_satir_no, bu_hafta_col_idx, "Bekliyor")
                            
                            st.success(f"🎉 Randevunuz başarıyla oluşturuldu ve Google Takvim'e işlendi! ({tarih_gun_formatla(secilen_tarih)} - Saat {secilen_saat})")
                            st.balloons()
                            st.cache_resource.clear()
                        else:
                            st.error(f"Google Takvim'e eklenirken bir hata oluştu:\n`{cal_result}`")
                else:
                    st.warning(f"**{atanan_uzman}** için şu anda açık müsait saat bulunmamaktadır. Lütfen koordinatörünüz ile iletişime geçiniz.")
            else:
                st.warning("Sistemde henüz girilmiş bir müsaitlik bulunmuyor.")
        else:
            st.error("Danışan kaydınız bulunamadı. Lütfen bağlantınızı kontrol ediniz.")
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
    
    col_sync, col_space = st.columns([3, 4])
    with col_sync:
        if st.button("🔄 Google Takvimden Emojileri Tara & Senkronize Et"):
            with st.spinner("Takvim taranıyor (Tik ✅ -> Yapıldı, X ❌ -> Yapılmadı, Boş -> Bekliyor)..."):
                try:
                    data = danisanlar_sheet.get_all_records()
                    df = pd.DataFrame(data)
                    headers = danisanlar_sheet.row_values(1)
                    
                    bu_hafta_col_idx = sutun_bul(headers, ["Bu Hafta Durum", "Bu Hafta", "Görüşme Durumu", "Durum"])
                    gecen_hafta_col_idx = sutun_bul(headers, ["Geçen Hafta Durum", "Geçen Hafta"])
                    
                    if not bu_hafta_col_idx:
                        danisanlar_sheet.update_cell(1, len(headers) + 1, "Bu Hafta Durum")
                        headers.append("Bu Hafta Durum")
                        bu_hafta_col_idx = len(headers)
                        
                    if not gecen_hafta_col_idx:
                        danisanlar_sheet.update_cell(1, len(headers) + 1, "Geçen Hafta Durum")
                        headers.append("Geçen Hafta Durum")
                        gecen_hafta_col_idx = len(headers)

                    simdi = datetime.now(TR_TZ)
                    zaman_min = (simdi - timedelta(days=21)).isoformat()
                    zaman_max = (simdi + timedelta(days=7)).isoformat()
                    
                    events_result = calendar_service.events().list(
                        calendarId=CALENDAR_ID,
                        timeMin=zaman_min,
                        timeMax=zaman_max,
                        singleEvents=True,
                        orderBy="startTime"
                    ).execute()
                    events = events_result.get("items", [])

                    df_cols = {c.strip(): c for c in df.columns}
                    ad_col = df_cols.get("Ad Soyad", df_cols.get("Ad_Soyad", list(df.columns)[1]))

                    guncellenen_sayisi = 0
                    for idx, row in df.iterrows():
                        satir_no = idx + 2
                        ad_tam = str(row.get(ad_col, "")).strip()
                        if not ad_tam:
                            continue
                        
                        ad_parcalari = [tr_lower(p) for p in ad_tam.split() if len(p) >= 2]
                        
                        for ev in reversed(events):
                            summary = str(ev.get("summary", ""))
                            summary_tr = tr_lower(summary)
                            
                            if any(p in summary_tr for p in ad_parcalari):
                                start_iso = ev["start"].get("dateTime", ev["start"].get("date"))
                                event_dt = datetime.fromisoformat(start_iso.replace("Z", "+00:00")).astimezone(TR_TZ)
                                fark_gun = (simdi.date() - event_dt.date()).days
                                
                                if any(tik in summary for tik in ["✅", "✔️", "✓", "tik", "yapıldı"]):
                                    durum_degeri = "Yapıldı"
                                elif any(carpi in summary for carpi in ["❌", "✖️", "iptal", "katılmadı", "yapılmadı"]):
                                    durum_degeri = "Yapılmadı"
                                else:
                                    durum_degeri = "Bekliyor"
                                
                                if 0 <= fark_gun <= 7:
                                    danisanlar_sheet.update_cell(satir_no, bu_hafta_col_idx, durum_degeri)
                                    guncellenen_sayisi += 1
                                    break
                                elif 7 < fark_gun <= 14:
                                    danisanlar_sheet.update_cell(satir_no, gecen_hafta_col_idx, durum_degeri)
                                    guncellenen_sayisi += 1
                                    break
                    
                    st.cache_resource.clear()
                    st.success(f"Senkronizasyon tamamlandı! Toplam {guncellenen_sayisi} danışanın durumu güncellendi.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Senkronizasyon hatası: {e}")

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
                bu_hafta_durum = format_durum(row.get("Bu Hafta Durum") or row.get("Bu Hafta") or row.get("Görüşme Durumu"))

                gecen_hafta_gorusme = row.get("Geçen Haftaki Görüşme") or "-"
                gecen_hafta_uzman = row.get("Geçen Haftaki Uzman") or "-"
                gecen_hafta_durum = format_durum(row.get("Geçen Hafta Durum") or row.get("Geçen Hafta"))

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
            st.caption("💡 Takvim başlıklarına **✅** (Yapıldı) veya **❌** (Yapılmadı) emojisi koyup butona basarak tüm yoklamaları çekebilirsiniz.")
        else:
            st.info("Tabloda kayıtlı danışan bulunmuyor.")
    except Exception as e:
        st.warning(f"Veriler okunurken bir hata oluştu: {e}")

# --- MENÜ 2: HOCA MÜSAİTLİK GİRİŞİ & YÖNETİMİ ---
elif sayfa == "🗓️ Hoca Müsaitlik Girişi":
    st.subheader("🗓️ Uzman Müsaitlik Saatleri Tanımlama & Yönetimi")
    
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        st.markdown("#### ➕ Yeni Müsaitlik Ekle")
        with st.form("musaitlik_ekle_formu"):
            secilen_hoca = st.selectbox("Uzman Seçin", UZMAN_LISTESI)
            m_tarih = st.date_input("Müsait Olduğunuz Tarih", datetime.now().date() + timedelta(days=1))
            
            secilen_gun_adi = GUNLER_TR.get(m_tarih.weekday(), "")
            st.info(f"Seçilen Gün: **{secilen_gun_adi}**")
            
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
                    st.success(f"{secilen_hoca} için {tarih_gun_formatla(m_tarih.strftime('%Y-%m-%d'))} saat {m_saat.strftime('%H:%M')} eklendi!")
                    st.cache_resource.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Slot eklenirken hata oluştu: {e}")

    with col_m2:
        st.markdown("#### 📋 Mevcut Müsaitlik Listesi")
        try:
            m_data = musaitlik_sheet.get_all_records()
            if m_data:
                gosterim_df = pd.DataFrame(m_data)
                if "Tarih" in gosterim_df.columns:
                    gosterim_df["Tarih (Gün)"] = gosterim_df["Tarih"].apply(tarih_gun_formatla)
                st.dataframe(gosterim_df, use_container_width=True)
            else:
                st.info("Kayıtlı müsaitlik bulunmuyor.")
        except Exception as e:
            st.error(f"Veriler listelenirken hata: {e}")

    st.markdown("---")
    st.markdown("#### ⚙️ Müsaitlik Durumunu Manuel Güncelle veya Sil")
    
    try:
        m_data = musaitlik_sheet.get_all_records()
        m_df = pd.DataFrame(m_data)
        
        if not m_df.empty:
            m_df = sutun_temizle(m_df)
            
            id_col = [c for c in m_df.columns if "Id" in c][0] if any("Id" in c for c in m_df.columns) else m_df.columns[0]
            uzman_col = [c for c in m_df.columns if "Uzman" in c][0] if any("Uzman" in c for c in m_df.columns) else m_df.columns[1]
            tarih_col = [c for c in m_df.columns if "Tarih" in c][0] if any("Tarih" in c for c in m_df.columns) else m_df.columns[2]
            saat_col = [c for c in m_df.columns if "Saat" in c][0] if any("Saat" in c for c in m_df.columns) else m_df.columns[3]
            durum_col = [c for c in m_df.columns if "Durum" in c][0] if any("Durum" in c for c in m_df.columns) else m_df.columns[4]
            danisan_col = [c for c in m_df.columns if "Danisan" in c][0] if any("Danisan" in c for c in m_df.columns) else (m_df.columns[5] if len(m_df.columns) > 5 else "Alinan_Danisan")
            
            slot_etiketleri = [
                f"ID: {r[id_col]} | {r[uzman_col]} | {tarih_gun_formatla(r[tarih_col])} {r[saat_col]} | Durum: {r[durum_col]} | Danışan: {r.get(danisan_col, '-')}"
                for _, r in m_df.iterrows()
            ]
            secilen_yonetim_slot = st.selectbox("İşlem Yapmak İstediğiniz Slotu Seçin", slot_etiketleri)
            secilen_slot_id = int(secilen_yonetim_slot.split("|")[0].replace("ID:", "").strip())
            
            slot_satir_no = m_df[m_df[id_col] == secilen_slot_id].index[0] + 2
            
            m_headers = musaitlik_sheet.row_values(1)
            durum_col_idx = sutun_bul(m_headers, ["Durum"]) or 5
            danisan_col_idx = sutun_bul(m_headers, ["Alinan_Danisan", "Alinan Danisan", "Danisan"]) or 6

            c_btn1, c_btn2, c_btn3 = st.columns(3)
            with c_btn1:
                if st.button("🔴 'Dolu' Olarak İşaretle"):
                    musaitlik_sheet.update_cell(slot_satir_no, durum_col_idx, "Dolu")
                    st.success("Slot 'Dolu' olarak güncellendi.")
                    st.cache_resource.clear()
                    st.rerun()
            
            with c_btn2:
                if st.button("🟢 'Müsait' (Boş) Yap"):
                    musaitlik_sheet.update_cell(slot_satir_no, durum_col_idx, "Müsait")
                    musaitlik_sheet.update_cell(slot_satir_no, danisan_col_idx, "-")
                    st.success("Slot tekrar 'Müsait' yapıldı.")
                    st.cache_resource.clear()
                    st.rerun()
            
            with c_btn3:
                if st.button("🗑️ Bu Slotu Tamamen Sil"):
                    musaitlik_sheet.delete_rows(slot_satir_no)
                    st.warning("Müsaitlik slotu tablodan silindi.")
                    st.cache_resource.clear()
                    st.rerun()
        else:
            st.info("İşlem yapılacak müsaitlik kaydı bulunmuyor.")
    except Exception as e:
        st.error(f"Yönetim işlemi sırasında hata: {e}")

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
                    
                    gecen_gorusme_col = sutun_bul(headers, ["Geçen Haftaki Görüşme"]) or len(headers) + 1
                    gecen_uzman_col = sutun_bul(headers, ["Geçen Haftaki Uzman"]) or len(headers) + 2
                    gecen_durum_col = sutun_bul(headers, ["Geçen Hafta Durum", "Geçen Hafta"]) or len(headers) + 3
                    
                    bu_gorusme_col = sutun_bul(headers, ["Bu Haftaki Görüşme"]) or len(headers) + 4
                    bu_uzman_col = sutun_bul(headers, ["Bu Haftaki Uzman"]) or len(headers) + 5
                    bu_durum_col = sutun_bul(headers, ["Bu Hafta Durum", "Bu Hafta", "Görüşme Durumu", "Durum"]) or len(headers) + 6

                    danisanlar_sheet.update_cell(satir_no, gecen_gorusme_col, str(yeni_gecen_gorusme))
                    danisanlar_sheet.update_cell(satir_no, gecen_uzman_col, str(gecen_uzman_input))
                    danisanlar_sheet.update_cell(satir_no, gecen_durum_col, "Yapıldı" if gecen_yapildi_mi else "Bekliyor")
                    
                    danisanlar_sheet.update_cell(satir_no, bu_gorusme_col, str(yeni_bu_gorusme))
                    danisanlar_sheet.update_cell(satir_no, bu_uzman_col, str(bu_uzman_input))
                    danisanlar_sheet.update_cell(satir_no, bu_durum_col, "Yapıldı" if bu_yapildi_mi else "Bekliyor")
                    
                    st.success(f"{secilen_danisan} kaydı güncellendi!")
                    st.cache_resource.clear()
                    st.rerun()
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
                st.rerun()
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
