"""
JANバーコードラベル自動生成 - 照合ロジック

①andST商品登録データ(xlsx) と ②ZOZO委託返却リスト(csv) を
メーカー品番・カラー・サイズで突合し、JANコードを特定する。
詳細ロジックは CLAUDE.md 参照。
"""
import re
import pandas as pd

TARGET_BRANDS = ["ap retro", "sakishimatokyo", "LAC-VERT", "B.R.U"]

SIZE_MAP = {
    "LARGE": "L", "L": "L",
    "MEDIUM": "M", "M": "M",
    "SMALL": "S", "S": "S",
    "X-LARGE": "XL", "XLARGE": "XL", "XL": "XL",
    "XX-LARGE": "XXL", "XXLARGE": "XXL", "XXL": "XXL",
    "FREE": "FREE", "F": "FREE", "ONE SIZE": "FREE",
}

REASON_NOT_FOUND_HINBAN_SIZE = "品番・サイズが①に見つからない"
REASON_COLOR_NOT_FOUND = "品番・サイズは一致したが、カラーが①に見つからない"
REASON_COLOR_AMBIGUOUS = "カラーがあいまい（①に複数候補あり）"


def normalize_size(size_raw):
    if size_raw is None:
        return ""
    s = str(size_raw).strip().upper()
    if s == "" or s == "NAN":
        return ""
    return SIZE_MAP.get(s, s)


def strip_color_code(raw_color):
    """①のカラー名称から「カラー基本名」を作る（括弧内除去→末尾2桁コード除去）"""
    s = str(raw_color).strip()
    s = re.sub(r"\([^)]*\)", "", s)
    s = re.sub(r"\s*\d{2}$", "", s)
    return s.strip()


def strip_trailing_number(name):
    """カラー名末尾の数字を除去（あいまい判定・再照合用）"""
    return re.sub(r"\d+$", "", str(name).strip()).strip()


def load_master(xlsx_path):
    """①andST商品登録データを読み込み、突合用インデックスを作る"""
    df = pd.read_excel(xlsx_path, sheet_name="xlsxWorkbook", dtype=str)
    df = df.dropna(subset=["メーカー品番", "JAN"])
    df["メーカー品番"] = df["メーカー品番"].str.strip()
    df["JAN"] = df["JAN"].str.strip()
    df = df[df["JAN"] != ""]
    df["カラー基本名"] = df["カラー名称"].apply(strip_color_code)
    df["サイズ_norm"] = df["サイズ名称"].apply(normalize_size)

    index = {}
    for _, row in df.iterrows():
        key = (row["メーカー品番"], row["サイズ_norm"])
        base_color = row["カラー基本名"]
        entry = {
            "hinban": row["メーカー品番"],
            "color_name": row["カラー名称"],
            "size_name": row["サイズ名称"],
            "jan": row["JAN"],
        }
        index.setdefault(key, {}).setdefault(base_color, []).append(entry)
    return index


def load_zozo_list(csv_path):
    """②ZOZO委託返却リストを読み込み、対象4ブランドのみに絞り込む"""
    df = pd.read_csv(csv_path, encoding="cp932", dtype=str)
    df = df[df["親カテゴリ"].isin(TARGET_BRANDS)].copy()
    return df


def match_row(master_index, hinban, size_raw, color_raw):
    """1行分の突合。戻り値: (matched_entry or None, reason or None)"""
    hinban = str(hinban).strip()
    size_norm = normalize_size(size_raw)
    color_raw_s = str(color_raw).strip()

    group = master_index.get((hinban, size_norm))
    if not group:
        return None, REASON_NOT_FOUND_HINBAN_SIZE

    # 1. カラー名そのまま完全一致
    if color_raw_s in group:
        return group[color_raw_s][0], None

    # 2. 末尾の数字を除去して再照合（あいまい判定つき）
    stripped = strip_trailing_number(color_raw_s)
    matched_bases = {
        base for base in group.keys() if strip_trailing_number(base) == stripped
    }
    if len(matched_bases) == 1:
        base = next(iter(matched_bases))
        return group[base][0], None
    if len(matched_bases) > 1:
        return None, REASON_COLOR_AMBIGUOUS

    return None, REASON_COLOR_NOT_FOUND


def run_matching(master_index, zozo_df):
    """②の各行を突合し、(matched_rows, unmatched_rows) を返す"""
    matched_rows = []
    unmatched_rows = []

    for _, row in zozo_df.iterrows():
        hinban = row.get("ブランド品番", "")
        color_raw = row.get("カラー", "")
        size_raw = row.get("サイズ", "")
        entry, reason = match_row(master_index, hinban, size_raw, color_raw)

        if entry is not None:
            matched_rows.append({
                "hinban": entry["hinban"],
                "color_name": entry["color_name"],
                "size_name": entry["size_name"],
                "jan": entry["jan"],
                "親カテゴリ": row.get("親カテゴリ", ""),
                "商品名": row.get("商品名", ""),
                "数量": row.get("数量", ""),
            })
        else:
            unmatched_rows.append({
                "親カテゴリ": row.get("親カテゴリ", ""),
                "ブランド品番": hinban,
                "カラー": color_raw,
                "サイズ": size_raw,
                "商品名": row.get("商品名", ""),
                "数量": row.get("数量", ""),
                "理由": reason,
            })

    return matched_rows, unmatched_rows


def dedupe_skus(matched_rows):
    """同一SKU（品番・カラー・サイズ・JAN）をまとめ、ラベルPDF用に1件ずつにする"""
    seen = {}
    for row in matched_rows:
        key = (row["hinban"], row["color_name"], row["size_name"], row["jan"])
        if key not in seen:
            seen[key] = dict(row)
            seen[key]["数量"] = 0
        try:
            seen[key]["数量"] += int(row["数量"])
        except (TypeError, ValueError):
            pass
    return list(seen.values())
