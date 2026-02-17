import streamlit as st
import pandas as pd
import os
from datetime import datetime

# 保存先ファイル名
DATA_FILE = "inspection_results.csv"

# データの読み込み関数
def load_data():
    if os.path.exists(DATA_FILE):
        return pd.read_csv(DATA_FILE)
    else:
        return pd.DataFrame(columns=["点検日", "設備名", "点検者", "判定", "備考"])

# アプリのタイトル
st.title("🛠️ 設備点検記録アプリ")

# --- 入力セクション ---
st.header("点検結果の入力")
with st.form("inspection_form", clear_on_submit=True):
    date = st.date_input("点検日", datetime.now())
    equip_name = st.text_input("設備名")
    inspector = st.text_input("点検者")
    status = st.selectbox("判定", ["異常なし", "要点検", "修理中"])
    notes = st.text_area("備考")
    
    submitted = st.form_submit_button("保存する")
    
    if submitted:
        if equip_name and inspector:
            new_data = pd.DataFrame([[date, equip_name, inspector, status, notes]], 
                                    columns=["点検日", "設備名", "点検者", "判定", "備考"])
            df = load_data()
            df = pd.concat([df, new_data], ignore_index=True)
            df.to_csv(DATA_FILE, index=False)
            st.success("データを保存しました！")
        else:
            st.error("設備名と点検者は必須入力です。")

# --- 一覧表示セクション ---
st.divider()
st.header("点検結果一覧")
df_display = load_data()

if not df_display.empty:
    st.dataframe(df_display.sort_values(by="点検日", ascending=False), use_container_width=True)
    csv = df_display.to_csv(index=False).encode('utf_8_sig')
    st.download_button(label="CSVをダウンロード", data=csv, file_name="inspection_report.csv", mime="text/csv")
else:
    st.info("まだデータがありません。")