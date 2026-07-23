# JANバーコードラベル自動生成Webアプリ

サンクラウドEC業務向け。ZOZOTOWN委託返却リスト（②）を①andSTマスタと自動照合し、
JANバーコードラベルPDFと要確認リストCSVを生成するローカルWebアプリです。

詳細仕様は [CLAUDE.md](./CLAUDE.md) を参照してください。

## セットアップ

```bash
pip install -r requirements.txt
```

## データファイルの置き方（重要・社外秘）

①②のデータファイルは社外秘のため、このリポジトリには含まれていません（`.gitignore`で除外）。
以下のファイルをローカルの プロジェクトルート（`app.py` と同じ階層）に配置してください。

| ファイル | 説明 | 配置ルール |
| --- | --- | --- |
| ①andST商品登録データ | xlsx（シート名 `xlsxWorkbook`） | ファイル名に `GOODS_CODE` を含む、または `①` で始まる `.xlsx` を配置。アプリが自動検出します（サイドバーのプルダウンから選択も可） |
| ②ZOZO委託返却リスト | csv（cp932/Shift-JIS） | 配置不要。アプリ起動後、ブラウザの画面からアップロードします |

## 起動方法

```bash
streamlit run app.py
```

ブラウザで `http://localhost:8501` を開き、②のCSVをアップロード→「照合を実行」で
ラベルPDF(ZIP)・要確認リストCSVをダウンロードできます。

## Googleドライブ自動アップロードのセットアップ

ラベルPDF(ZIP)は生成後、自動でGoogleドライブの指定フォルダにもアップロードされます
（フォルダID: `0ACoZiydC-wX3Uk9PVA`）。
サービスアカウントの鍵ファイル(JSON)は**リポジトリに含めず**、Streamlitのsecrets機能で管理します。

### ローカルでのテスト手順

1. プロジェクト直下に `.streamlit` フォルダを作成（`.gitignore`で除外済みのためGitHubには上がりません）
2. `.streamlit/secrets.toml` を新規作成し、サービスアカウントの鍵JSONの中身を以下の形式で転記する

   ```toml
   [gcp_service_account]
   type = "service_account"
   project_id = "your-project-id"
   private_key_id = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
   private_key = """-----BEGIN PRIVATE KEY-----
   xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   -----END PRIVATE KEY-----
   """
   client_email = "xxxx@your-project-id.iam.gserviceaccount.com"
   client_id = "xxxxxxxxxxxxxxxxxxxxx"
   auth_uri = "https://accounts.google.com/o/oauth2/auth"
   token_uri = "https://oauth2.googleapis.com/token"
   auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
   client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/xxxx%40your-project-id.iam.gserviceaccount.com"
   ```

   - 鍵JSONファイルの各キーの値をそのままコピーしてください（`private_key`は改行を含むため`"""`で囲みます）
3. アップロード先のGoogleドライブフォルダを、鍵JSON内の `client_email` のアドレスに対して
   **「編集者」権限で共有**してください（サービスアカウントは自分のマイドライブを持たないため、
   共有されていないフォルダにはアップロードできません）
4. `streamlit run app.py` で起動し、照合を実行すると自動でアップロードされます。
   未設定の場合はアップロードをスキップし、ダウンロードボタンのみ表示されます。

### 本番環境（Streamlit Community Cloudなど）

アプリの管理画面の「Secrets」設定に、上記と同じ内容を貼り付けてください。
