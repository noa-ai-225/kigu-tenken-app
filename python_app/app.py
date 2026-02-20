import streamlit as st
import pandas as pd
import os
import qrcode
from io import BytesIO
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- ページ設定 ---
st.set_page_config(page_title="設備点検DXアプリ", layout="centered")

# --- Googleスプレッドシート接続 ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_master():
    try:
        # スプレッドシートの master シートから読み込み
        return conn.read(worksheet="master", ttl=5)
    except:
        return pd.DataFrame([{"生産ライン": "Line-A", "設備名": "マシン1", "カテゴリ": "本体", "点検項目": "異音なし"}])

def save_results(data_list):
    new_df = pd.DataFrame(data_list)
    try:
        # results シートの既存データを取得して結合
        existing_df = conn.read(worksheet="results", ttl=0)
        updated_df = pd.concat([existing_df, new_df], ignore_index=True)
        conn.update(worksheet="results", data=updated_df)
    except:
        conn.create(worksheet="results", data=new_df)

# --- QRコード生成 ---
def generate_qr_code(url):
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# --- メインロジック ---
query_params = st.query_params
url_line = query_params.get("line")

st.sidebar.title("🛠 アプリメニュー")
mode = st.sidebar.radio("機能を選択", ["📋 現場点検入力", "🛠 設備項目設定", "表示確認（履歴）"])

# サイドバー：ライン切替QR（クラウド対応）
st.sidebar.divider()
df_master = load_master()
line_list = df_master["生産ライン"].unique()

with st.sidebar.expander("📲 ライン切替QR"):
    # 自分のアプリのURLに変更してください
    app_url = "https://kigu-tenken-app.streamlit.app" 
    for line in line_list:
        line_url = f"{app_url}/?line={line}"
        st.write(f"**{line}**")
        qr_img = generate_qr_code(line_url)
        st.image(qr_img)

# --- 1. 現場点検入力 ---
if mode == "📋 現場点検入力":
    st.title("現場点検入力")
    idx_line = list(line_list).index(url_line) if url_line in line_list else 0
    selected_line = st.selectbox("対象ラインを選択", line_list, index=idx_line)
    
    df_line = df_master[df_master["生産ライン"] == selected_line]
    st.header(f"🚩 {selected_line} 点検リスト")
    
    equip_results = {}

    for equipment in df_line["設備名"].unique():
        with st.expander(f"🤖 設備: {equipment}", expanded=True):
            df_equip = df_line[df_line["設備名"] == equipment]
            status_summary = []
            
            for category in df_equip["カテゴリ"].unique():
                st.markdown(f"**【{category}】**")
                df_cat = df_equip[df_equip["カテゴリ"] == category]
                for i, item in enumerate(df_cat["点検項目"]):
                    key = f"{selected_line}_{equipment}_{category}_{item}_{i}"
                    choice = st.radio("判定", ["未実施", "正常", "異常(NG)"], key=key, horizontal=True)
                    status_summary.append({"item": item, "status": choice})
            
            # 異常と未実施を同時に特定
            ng_list = [s["item"] for s in status_summary if s["status"] == "異常(NG)"]
            unperformed_list = [s["item"] for s in status_summary if s["status"] == "未実施"]
            
            res_parts = []
            if ng_list: res_parts.append(f"❌NG: {', '.join(ng_list)}")
            if unperformed_list: res_parts.append(f"⚠️未実施: {', '.join(unperformed_list)}")
            
            equip_results[equipment] = " / ".join(res_parts) if res_parts else "正常"

    if st.button("このラインの点検結果を送信", type="primary", use_container_width=True):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data_to_save = []
        for equipment, final_status in equip_results.items():
            data_to_save.append({
                "日付": timestamp, "ライン": selected_line, "設備名": equipment,
                "結果": final_status, "備考": "", "写真名": ""
            })
        
        save_results(data_to_save)
        st.success("スプレッドシートへ保存完了！")
        st.balloons()

# --- 2. 設備項目設定 ---
elif mode == "🛠 設備項目設定":
    st.title("設備項目設定")
    df_master = load_master()
    edited_df = st.data_editor(df_master, num_rows="dynamic", width="stretch")
    if st.button("設定を保存"):
        conn.update(worksheet="master", data=edited_df)
        st.success("マスターデータを更新しました。")

# --- 3. 履歴確認 ---
elif mode == "表示確認（履歴）":
    st.title("点検履歴の確認")
    try:
        df_res = conn.read(worksheet="results", ttl=0)
        
        def style_rows(row):
            res_str = str(row.結果)
            if "❌NG" in res_str:
                return ['background-color: #d00000; color: white; font-weight: bold'] * len(row)
            if "⚠️未実施" in res_str:
                return ['background-color: #ff8c00; color: black; font-weight: bold'] * len(row)
            return [''] * len(row)
        
        st.dataframe(
            df_res.sort_values(by="日付", ascending=False).style.apply(style_rows, axis=1), 
            use_container_width=True
        )
    except:
        st.info("データがありません。")
