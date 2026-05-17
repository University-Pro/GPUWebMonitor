# GPUWebMonitor - GPU サーバークラスター監視ダッシュボード

[中文](README.md) | [English](README.en.md) | [日本語](README.ja.md)

[![License](https://img.shields.io/badge/license-GPL_V3-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12+-green.svg)](https://www.python.org/)
[![Vue](https://img.shields.io/badge/Vue-3-4FC08D.svg)](https://vuejs.org/)
[![Flask](https://img.shields.io/badge/Flask-2.x-000000.svg)](https://flask.palletsprojects.com/)

**GPUWebMonitor** は、複数の GPU サーバーのリアルタイム状態、システム指標、GPU プロセス情報を一元的に確認するための軽量な監視システムです。

> このプロジェクトは現在開発中です。信頼できるイントラネットまたは管理されたテスト環境での利用を推奨します。現時点では本番環境への直接導入は推奨しません。

![GPUWebMonitor プレビュー](pictures/readme1.png)

## 機能

- **複数サーバーの集中監視**: Dashboard から複数の Agent ノードをまとめて確認できます。
- **リアルタイム更新**: フロントエンドは手動更新と自動更新に対応しています。
- **GPU 指標表示**: 使用率、VRAM 使用量、温度、消費電力、ファン速度などを表示します。
- **プロセス単位の監視**: GPU を使用しているプロセスの PID、ユーザー、プロセス名、GPU メモリ使用量、コマンドラインを表示します。
- **システムリソース監視**: CPU、メモリ、ネットワーク送受信量を表示します。
- **履歴データ記録**: Agent はデフォルトで 30 秒ごとに SQLite へ履歴を書き込み、30 日間保持します。
- **シンプルな静的フロントエンド配信**: Dashboard サービスが `front/` 配下のフロントエンドファイルを直接配信します。

## アーキテクチャ

```text
ブラウザ
  |
  | Dashboard にアクセス: http://<dashboard-host>:28456
  v
Dashboard サービス backend/dashboard.py
  |
  | front/config.json を読み込み、選択された Agent へリクエストをプロキシ
  v
Agent サービス backend/app.py
  |
  | nvitop / NVML / psutil を利用
  v
GPU とシステム状態
```

デフォルトポート:

| サービス | ファイル | デフォルトポート | 説明 |
| --- | --- | ---: | --- |
| Agent | `backend/app.py` | `15896` | 監視対象の各 GPU サーバーで実行します |
| Dashboard | `backend/dashboard.py` | `28456` | 監視入口として実行します。Agent と同じマシンで動かすこともできます |

## 要件

- Python 3.12+
- NVIDIA ドライバーと利用可能な NVML 環境
- 監視対象ノードで `nvidia-smi` が正常に実行できることを推奨
- Linux では systemd によるサービス管理を推奨

## クイックスタート

### 1. プロジェクトをクローン

```bash
git clone https://github.com/University-Pro/GPUWebMonitor.git
cd GPUWebMonitor
```

### 2. Python 環境を作成

依存関係がシステム環境と混ざらないよう、専用の Python 環境を作成することを推奨します。`venv` または `conda` のどちらかを選んでください。

`venv` を使用する場合:

```bash
python -m venv .venv
source .venv/bin/activate
```

`conda` を使用する場合:

```bash
conda create -n gpuwebmonitor python=3.12
conda activate gpuwebmonitor
```

環境を有効化した後、現在使用している Python のパスを確認できます:

```bash
where python
```

Linux/macOS では次も使用できます:

```bash
which python
```

後で systemd を設定する際は、この Python の絶対パスを `ExecStart` に指定してください。

### 3. バックエンド依存関係をインストール

Dashboard サーバーと各 Agent サーバーで依存関係をインストールします:

```bash
cd backend
pip install -r requirements.txt
```

### 4. サーバーリストを設定

`front/config.json` を編集し、各 Agent を `servers` に追加します:

```json
{
  "servers": [
    {
      "id": "server1",
      "name": "2080Ti Server",
      "url": "http://192.168.30.246:15896"
    },
    {
      "id": "server2",
      "name": "4090D Server",
      "url": "http://192.168.30.223:15896"
    }
  ]
}
```

フィールド説明:

| フィールド | 説明 |
| --- | --- |
| `id` | ノードの一意な ID。英数字やハイフンを推奨します |
| `name` | フロントエンドに表示される名前 |
| `url` | Agent サービスの URL。デフォルトポートは `15896` です |

### 5. Agent を起動

監視対象の各 GPU サーバーで実行します:

```bash
cd backend
python app.py
```

Agent が正常に動作しているか確認します:

```bash
curl http://127.0.0.1:15896/
curl http://127.0.0.1:15896/api/status
```

### 6. Dashboard を起動

監視入口となるサーバーで実行します:

```bash
cd backend
python dashboard.py
```

ブラウザで開きます:

```text
http://<dashboard-host>:28456
```

Dashboard とブラウザが同じマシン上にある場合は、次を使用できます:

```text
http://127.0.0.1:28456
```

## systemd デプロイ例

### Agent サービス

まず、現在の環境で使用している Python インタープリターのパスを確認します:

```bash
where python
# Linux/macOS では次も使用できます: which python
```

`/etc/systemd/system/gpu-monitor-agent.service` を作成し、`ExecStart` の `/path/to/python` を上で確認した絶対パスに置き換えます:

```ini
[Unit]
Description=GPU Monitor Agent
After=network.target

[Service]
User=YOUR_USER
Group=YOUR_GROUP
WorkingDirectory=/path/to/GPUWebMonitor/backend
ExecStart=/path/to/python app.py
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

### Dashboard サービス

同様に、`ExecStart` の `/path/to/python` を現在の環境の Python 絶対パスに置き換えます。

`/etc/systemd/system/gpu-monitor-dashboard.service` を作成します:

```ini
[Unit]
Description=GPU Monitor Dashboard
After=network.target

[Service]
User=YOUR_USER
Group=YOUR_GROUP
WorkingDirectory=/path/to/GPUWebMonitor/backend
ExecStart=/path/to/python dashboard.py
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

サービスを有効化して起動します:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now gpu-monitor-agent
sudo systemctl enable --now gpu-monitor-dashboard
```

状態とログを確認します:

```bash
systemctl status gpu-monitor-agent
systemctl status gpu-monitor-dashboard
journalctl -u gpu-monitor-agent -f
journalctl -u gpu-monitor-dashboard -f
```

## 設定

### Agent 設定

Agent の主な設定は `backend/app.py` の先頭にあります:

| 設定 | デフォルト | 説明 |
| --- | ---: | --- |
| `PORT` | `15896` | Agent の待ち受けポート |
| `RECORD_INTERVAL` | `30` | 履歴データの収集間隔。単位は秒 |
| `KEEP_HISTORY_DAYS` | `30` | SQLite 履歴データの保持日数 |
| `DB_FILE` | `backend/monitor_data.db` | 履歴データファイルのパス |

### Dashboard 設定

Dashboard は次のファイルを読み込みます:

```text
front/config.json
```

`/api/proxy?id=<server_id>` を通じて、フロントエンドのリクエストを選択された Agent の `/api/status` エンドポイントへ転送します。

## API

### Agent

| メソッド | パス | 説明 |
| --- | --- | --- |
| `GET` | `/` | ヘルスチェック |
| `GET` | `/api/status` | 現在の GPU とシステム状態を取得 |
| `GET` | `/api/history?limit=100` | 履歴監視データを取得。`limit` の最大値は 1000 |

### Dashboard

| メソッド | パス | 説明 |
| --- | --- | --- |
| `GET` | `/` | フロントエンドページ |
| `GET` | `/api/config` | サーバー設定を取得 |
| `GET` | `/api/proxy?id=<server_id>` | 選択された Agent へリクエストをプロキシ |

## プロジェクト構成

```text
GPUWebMonitor/
├── backend/
│   ├── app.py             # Agent サービス。監視対象サーバーで実行
│   ├── dashboard.py       # Dashboard サービス。フロントエンド配信と Agent リクエストのプロキシ
│   ├── gpu_monitor.py     # GPU とシステム指標の収集ロジック
│   ├── stress.py          # ストレステストスクリプト
│   └── requirements.txt   # Python 依存関係
├── front/
│   ├── index.html         # フロントエンドページ
│   ├── app.js             # フロントエンドの業務ロジック
│   ├── style.css          # フロントエンドスタイル
│   ├── config.json        # 監視対象サーバー設定
│   └── favicon / icon     # ブラウザーアイコン素材
├── pictures/
│   └── readme1.png        # README プレビュー画像
├── LICENSE
└── README.md
```

## 技術スタック

- **バックエンド**: Python、Flask、Flask-CORS、nvitop、psutil、SQLite
- **フロントエンド**: Vue 3、Element Plus、バニラ JavaScript
- **デプロイ**: Python サービスを直接実行、または systemd で管理

## トラブルシューティング

### Dashboard がサーバーリストを読み込めない

- Dashboard が起動しており、`http://<dashboard-host>:28456` にアクセスしていることを確認してください。
- `front/config.json` が有効な JSON であることを確認してください。
- Dashboard ログに設定ファイルパスや JSON パースエラーが出ていないか確認してください。

### 特定ノードからデータを取得できない

- 対象 Agent が起動していることを確認してください: `curl http://<agent-host>:15896/api/status`。
- Dashboard サーバーから Agent URL に到達できることを確認してください。
- `front/config.json` の該当ノードの `url` に正しいポートが含まれているか確認してください。

### GPU 情報が空、または権限が不足している

- NVIDIA ドライバーがインストールされ、`nvidia-smi` が正常に動作することを確認してください。
- Agent を実行しているユーザーに GPU とプロセス情報を読み取る権限があることを確認してください。
- 他ユーザー所有プロセスの完全なコマンドラインを表示するには、システム権限の調整、または必要な権限を持つユーザーでの Agent 実行が必要な場合があります。

### ポートが使用中

```bash
ss -ltnp | grep -E '15896|28456'
```

ポートを変更する場合は、`backend/app.py` の `PORT` と `backend/dashboard.py` の `app.run(..., port=28456)` を変更してください。

## ライセンス

このプロジェクトは GNU General Public License v3.0 のもとで公開されています。詳細は [LICENSE](LICENSE) を参照してください。

## 謝辞

- [nvitop](https://github.com/XuehaiPan/nvitop)
- [psutil](https://github.com/giampaolo/psutil)
- [Vue](https://vuejs.org/)
- [Element Plus](https://element-plus.org/)
