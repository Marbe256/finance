# Raspberry Pi セットアップ手順

## 環境
- Raspberry Pi 3
- IP: 192.168.10.45
- ユーザー: raspberry
- ポート: 8081
- URL: http://192.168.10.45:8081/

## 初回セットアップ（完了済み）

```bash
git clone https://github.com/Marbe256/finance.git
cd finance
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 手動起動

```bash
cd ~/finance
source venv/bin/activate
uvicorn server:app --host 0.0.0.0 --port 8081
```

## 自動起動設定（再起動後も動かしたい場合）

```bash
sudo cp /tmp/finance.service /etc/systemd/system/finance.service
sudo systemctl daemon-reload
sudo systemctl enable finance
sudo systemctl start finance
```

service ファイルの内容（`/tmp/finance.service` に作成済み、再起動後は消える）:

```ini
[Unit]
Description=Finance Analysis Server
After=network.target

[Service]
User=raspberry
WorkingDirectory=/home/raspberry/finance
ExecStart=/home/raspberry/finance/venv/bin/uvicorn server:app --host 0.0.0.0 --port 8081
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

service ファイルを再作成する場合:

```bash
sudo tee /etc/systemd/system/finance.service << 'EOF'
[Unit]
Description=Finance Analysis Server
After=network.target

[Service]
User=raspberry
WorkingDirectory=/home/raspberry/finance
ExecStart=/home/raspberry/finance/venv/bin/uvicorn server:app --host 0.0.0.0 --port 8081
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable finance
sudo systemctl start finance
```

## コードの更新

```bash
cd ~/finance
git pull
sudo systemctl restart finance  # 自動起動設定済みの場合
# または手動起動の場合は再起動
```
