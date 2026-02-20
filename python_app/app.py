import streamlit as st
import pandas as pd
import os
import qrcode
import socket
from io import BytesIO
from datetime import datetime

# --- 設定 ---
MASTER_FILE = "master_data.csv"
RESULT_FILE = "inspection_results.csv"
PHOTO_DIR = "photos"

if not os.path.exists(PHOTO_DIR):
    os.makedirs(PHOTO_DIR)

st.set_page_config(page_title="設備点検DXアプリ", layout="centered")

# --- 便利機能 ---
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def generate_qr_code(url):
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def load_master():
    if os.path.exists(MASTER_FILE):
        return pd.read_csv(MASTER_FILE)
    else:
        return pd.DataFrame([
            {"生産ライン": "Line-A", "設備名": "マシン1", "カテゴリ": "本体", "点検項目": "異音なし"},
            {"生産ライン": "Line-A", "設備名": "マシン1", "カテゴリ": "配線", "点検項目": "被覆破損なし"},
            {"生産ライン": "Line-B", "設備名": "マシン2", "カテゴリ": "本体", "点検項目": "油漏れなし"}
        ])

def save_results(data_list):
    df = pd.DataFrame(data_list)
    columns_order = ["日付", "ライン", "設備名", "結果", "備考", "写真名"]
    if os.path.exists(RESULT_FILE):
        df_old = pd.read_csv(RESULT_FILE)
        df = pd.concat([df_old, df], ignore_index=True)
    df = df.reindex(columns=columns_order)
    df.to_csv(RESULT_FILE, index=False, encoding='utf_8_sig')

# --- メイン処理 ---
query_params = st.query_params
url_line = query_params.get("line")

st.sidebar.title("🛠 アプリメニュー")
mode = st.sidebar.radio("機能を選択", ["📋 現場点検入力", "🛠 設備項目設定", "表示確認（履歴）"])

# QRコード表示
st.sidebar.divider()
st.sidebar.subheader("📲 ライン切替QR")
df_master = load_master()
line_list = df_master["生産ライン"].unique()
local_ip = get_local_ip()

with st.sidebar.expander("各ラインのQRコードを開く"):
    for line in line_list:
        line_url = f"http://{local_ip}:8501/?line={line}"
        st.write(f"**{line}**")
        qr_img = generate_qr_code(line_url)
        st.image(qr_img, caption=f"{line}用")

# --- 1. 現場点検入力 ---
if mode == "📋 現場点検入力":
    st.title("現場点検入力")
    line_list = df_master["生産ライン"].unique()
    idx_line = list(line_list).index(url_line) if url_line in line_list else 0
    selected_line = st.selectbox("対象ラインを選択", line_list, index=idx_line)
    
    df_line = df_master[df_master["生産ライン"] == selected_line]
    st.header(f"🚩 {selected_line} 点検リスト")
    
    equip_results = {}
    photo_files = {}

    for equipment in df_line["設備名"].unique():
        with st.expander(f"🤖 設備: {equipment}", expanded=True):
            df_equip = df_line[df_line["設備名"] == equipment]
            
            status_summary = []
            for category in df_equip["カテゴリ"].unique():
                st.markdown(f"**【{category}】**")
                df_cat = df_equip[df_equip["カテゴリ"] == category]
                
                for i, item in enumerate(df_cat["点検項目"]):
                    st.write(f"項目: {item}")
                    key = f"{selected_line}_{equipment}_{category}_{item}_{i}"
                    choice = st.radio(
                        "判定", 
                        ["未実施", "正常", "異常(NG)"], 
                        key=key, 
                        horizontal=True,
                        label_visibility="collapsed"
                    )
                    status_summary.append({"item": item, "status": choice})
            
            # --- 改善ポイント：NGと未実施を独立して集計し、併記する ---
            ng_list = [s["item"] for s in status_summary if s["status"] == "異常(NG)"]
            unperformed_list = [s["item"] for s in status_summary if s["status"] == "未実施"]
            
            status_parts = []
            if ng_list:
                status_parts.append(f"❌NG: {', '.join(ng_list)}")
            if unperformed_list:
                status_parts.append(f"⚠️未実施: {', '.join(unperformed_list)}")
            
            if status_parts:
                # 異常と未実施を「 / 」で区切って両方表示
                equip_results[equipment] = " / ".join(status_parts)
            else:
                equip_results[equipment] = "正常"
            
            st.write("---")
            photo_key = f"photo_{selected_line}_{equipment}"
            photo_files[equipment] = st.file_uploader(f"📷 {equipment} 写真（異常・未実施時は推奨）", type=['jpg', 'jpeg', 'png'], key=photo_key)
    
    st.divider()
    memo = st.text_area("📝 備考（未実施の理由や異常の詳細）")
    
    if st.button("このラインの点検結果を送信", type="primary", use_container_width=True):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data_to_save = []
        
        for equipment, final_status in equip_results.items():
            photo_name = ""
            uploaded = photo_files.get(equipment)
            if uploaded:
                photo_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{equipment}.jpg"
                with open(os.path.join(PHOTO_DIR, photo_name), "wb") as f:
                    f.write(uploaded.getbuffer())

            data_to_save.append({
                "日付": timestamp, "ライン": selected_line, "設備名": equipment,
                "結果": final_status, "備考": memo, "写真名": photo_name
            })
        
        save_results(data_to_save)
        
        res_values = " ".join(equip_results.values())
        if "❌NG" in res_values:
            st.warning("異常(NG)が記録されました。未実施項目がある場合はそちらも確認してください。")
        elif "⚠️未実施" in res_values:
            st.info("未実施項目を含めて保存しました。後ほど点検を完了させてください。")
        else:
            st.success("全項目正常に完了しました！")
            st.balloons()

# --- 2. 設備項目設定 / 3. 履歴確認 モード ---
elif mode == "🛠 設備項目設定":
    st.title("設備項目設定")
    df_master = load_master()
    edited_df = st.data_editor(df_master, num_rows="dynamic", width="stretch")
    if st.button("設定を保存"):
        edited_df.to_csv(MASTER_FILE, index=False, encoding='utf_8_sig')
        st.success("マスターデータを更新しました。")

elif mode == "表示確認（履歴）":
    st.title("点検履歴の確認")
    if os.path.exists(RESULT_FILE):
        df_res = pd.read_csv(RESULT_FILE)
        
        def style_rows(row):
            res_str = str(row.結果)
            # 異常（❌NG）が1文字でも含まれていれば赤色（最優先）
            if "❌NG" in res_str:
                return ['background-color: #d00000; color: white; font-weight: bold'] * len(row)
            # 異常はないが、未実施（⚠️未実施）が含まれていればオレンジ色
            if "⚠️未実施" in res_str:
                return ['background-color: #ff8c00; color: black; font-weight: bold'] * len(row)
            return [''] * len(row)
        
        st.dataframe(
            df_res.sort_values(by="日付", ascending=False).style.apply(style_rows, axis=1), 
            use_container_width=True
        )
        
        st.subheader("最新の点検写真")
        photos_with_names = df_res[df_res["写真名"].notna()]["写真名"].tolist()
        if photos_with_names:
            st.image(os.path.join(PHOTO_DIR, photos_with_names[-1]))
    else:
        st.info("履歴データがありません。")
