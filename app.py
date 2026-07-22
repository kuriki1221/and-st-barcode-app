import datetime
import glob
import io
import os

import pandas as pd
import streamlit as st

from core.matching import load_master, load_zozo_list, run_matching, dedupe_skus, TARGET_BRANDS
from core.pdf_labels import generate_labels_pdf

st.set_page_config(page_title="JANバーコードラベル自動生成", layout="wide")
st.title("JANバーコードラベル自動生成")
st.caption("②ZOZO委託返却リストをアップロードすると、①andSTマスタと自動照合してラベルPDFを生成します。")

APP_DIR = os.path.dirname(os.path.abspath(__file__))


def find_master_candidates():
    patterns = [
        os.path.join(APP_DIR, "*GOODS_CODE*.xlsx"),
        os.path.join(APP_DIR, "①*.xlsx"),
    ]
    files = []
    for p in patterns:
        files.extend(glob.glob(p))
    # 重複除去・除外(一時ファイル)
    files = sorted({f for f in files if not os.path.basename(f).startswith("~$")})
    return files


with st.sidebar:
    st.header("①andSTマスタデータ")
    candidates = find_master_candidates()
    if candidates:
        master_path = st.selectbox(
            "マスタxlsxファイル",
            options=candidates,
            format_func=os.path.basename,
        )
    else:
        st.warning("マスタxlsxが自動検出できませんでした。パスを直接入力してください。")
        master_path = st.text_input("マスタxlsxのパス", value="")

    st.divider()
    st.header("対象ブランド")
    st.write("、".join(TARGET_BRANDS))

st.subheader("① ②ZOZO委託返却リストをアップロード")
uploaded_csv = st.file_uploader("委託返却リスト (CSV / cp932)", type=["csv"])

run_button = st.button("照合を実行", type="primary", disabled=not (uploaded_csv and master_path))

if "matched" not in st.session_state:
    st.session_state.matched = None
    st.session_state.unmatched = None
    st.session_state.skus = None

if run_button:
    if not master_path or not os.path.exists(master_path):
        st.error(f"マスタxlsxが見つかりません: {master_path}")
    else:
        with st.spinner("①マスタを読み込み中..."):
            master_index = load_master(master_path)

        with st.spinner("②委託返却リストを読み込み中..."):
            csv_bytes = uploaded_csv.getvalue()
            zozo_df = load_zozo_list(io.BytesIO(csv_bytes))

        if zozo_df.empty:
            st.warning("対象4ブランドのデータが見つかりませんでした。")
            st.session_state.matched = []
            st.session_state.unmatched = []
            st.session_state.skus = []
        else:
            with st.spinner("照合中..."):
                matched, unmatched = run_matching(master_index, zozo_df)
                skus = dedupe_skus(matched)

            st.session_state.matched = matched
            st.session_state.unmatched = unmatched
            st.session_state.skus = skus

if st.session_state.matched is not None:
    matched = st.session_state.matched
    unmatched = st.session_state.unmatched
    skus = st.session_state.skus

    st.subheader("② 照合結果")
    c1, c2, c3 = st.columns(3)
    c1.metric("マッチ行数", len(matched))
    c2.metric("要確認行数", len(unmatched))
    c3.metric("ラベルSKU数（PDFページ数）", len(skus))

    tab_matched, tab_unmatched = st.tabs(["マッチ結果", "要確認リスト"])

    with tab_matched:
        if matched:
            st.dataframe(pd.DataFrame(matched), use_container_width=True)
        else:
            st.info("マッチした行はありません。")

    with tab_unmatched:
        if unmatched:
            st.dataframe(pd.DataFrame(unmatched), use_container_width=True)
        else:
            st.success("要確認の行はありません。")

    st.subheader("③ 出力")
    col_pdf, col_csv = st.columns(2)

    with col_pdf:
        if skus:
            pdf_buffer = io.BytesIO()
            generate_labels_pdf(skus, pdf_buffer)
            today_str = datetime.date.today().strftime("%Y%m%d")
            st.download_button(
                "ラベルPDFをダウンロード",
                data=pdf_buffer.getvalue(),
                file_name=f"{today_str}_バーコード.pdf",
                mime="application/pdf",
                type="primary",
            )
        else:
            st.info("生成できるラベルがありません。")

    with col_csv:
        if unmatched:
            today_str = datetime.date.today().strftime("%Y%m%d")
            csv_out = pd.DataFrame(unmatched).to_csv(index=False)
            st.download_button(
                "要確認リストCSVをダウンロード",
                data=csv_out.encode("cp932", errors="replace"),
                file_name=f"{today_str}_要確認リスト.csv",
                mime="text/csv",
            )
        else:
            st.info("要確認リストはありません。")
