import streamlit as st
import folium
from streamlit_folium import folium_static
import json
import pandas as pd
import googlemaps
from shapely.geometry import shape, Point
import io

# 🔑 Google Maps APIキーを設定（ここに自分のAPIキーを入れる）
API_KEY = st.secrets["GOOGLE_MAPS_API_KEY"]

# Google Maps APIのクライアントを作成
gmaps = googlemaps.Client(key=API_KEY)

# GeoJSONファイルの読み込み関数
def load_geojson(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

# 住所を緯度・経度に変換（Google Maps APIを使用）
def geocode_address(address):
    try:
        result = gmaps.geocode(address)
        if result and "geometry" in result[0]:
            location = result[0]["geometry"]["location"]
            return location["lat"], location["lng"]
    except Exception as e:
        st.error(f"ジオコーディングエラー: {e}")
    return None, None

# 住所の緯度経度がどの地区に属するか判定
def get_district(lat, lon, geojson_data):
    if lat is None or lon is None:
        return "住所が見つかりません"

    point = Point(lon, lat)
    for feature in geojson_data["features"]:
        polygon = shape(feature["geometry"])
        if polygon.contains(point):
            return feature["properties"]["name"]
    return "該当なし"

# 児童数・世帯数を集計する
def aggregate_data(df):
    # 世帯数のカウント（同じ住所は1つの世帯とする）
    household_counts = df.groupby(['地区', '住所']).size().reset_index(name='世帯数')
    
    # 地区ごとに集計
    district_summary = household_counts.groupby('地区').agg(
        世帯数=('住所', 'count'),  # 世帯数の合計
        児童数=('世帯数', 'sum')  # 児童数の合計
    ).reset_index()

    return district_summary

# 地図を作成し、GeoJSONを表示
def draw_map():
    # 仙台市立長町小学校を中心に、ズームレベルを上げる
    m = folium.Map(location=[38.23235365491255, 140.88057791684378], zoom_start=15)
    geojson_data = load_geojson("school-district-export.geojson")

    folium.GeoJson(
        geojson_data,
        name="地区境界",
        tooltip=folium.GeoJsonTooltip(fields=["name"], aliases=["地区名"])
    ).add_to(m)

    return folium_static(m)

# Streamlit UI
def main():
    st.title("長町小学校・地区別児童数集計アプリ")
    
    # 地図をページの一番上に表示
    draw_map()
    
    geojson_data = load_geojson("school-district-export.geojson")
    
    # CSVアップロード
    uploaded_file = st.file_uploader("児童の住所データをアップロード（CSV形式）", type=["csv"])
    
    if uploaded_file is not None:
        student_data = pd.read_csv(uploaded_file)

        # 住所を緯度経度に変換し、地区を判定
        results = []
        for index, row in student_data.iterrows():
            lat, lon = geocode_address(row["address"])
            district = get_district(lat, lon, geojson_data)
            results.append([row["address"], lat, lon, district])

        # 結果をDataFrameに変換
        result_df = pd.DataFrame(results, columns=["住所", "緯度", "経度", "地区"])
        result_df.index = result_df.index + 1  # インデックスを1から始める
        
        # 地区ごとの児童数・世帯数
        district_summary = aggregate_data(result_df)
        st.subheader("地区ごとの児童数・世帯数")
        st.dataframe(district_summary, hide_index=True)  # インデックスを非表示

        # CSVダウンロード機能
        csv = district_summary.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="CSVダウンロード",
            data=csv,
            file_name="district_summary.csv",
            mime="text/csv"
        )
        
        # 児童の住所一覧を最後に表示
        st.subheader("児童の住所を地区に分類 & 集計")
        st.dataframe(result_df)

if __name__ == "__main__":
    main()