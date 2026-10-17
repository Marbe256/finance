# チャート分析ツール 仕様書

## 概要

株・コモディティ・為替・仮想通貨のチャートデータを取得し、テクニカル指標を計算・表示するWebベースの分析ツール。
エージェントからHTTP APIで操作可能な設計とする。

---

## システム構成

```
finance/
├── server.py                  # FastAPI エントリーポイント（起動・ルーター登録）
├── agent.py                   # エージェントロジック（分析・判断・自動売買）
├── requirements.txt           # 依存パッケージ
├── routers/
│   ├── chart.py               # GET /api/chart, /api/symbols/search, /api/analyze
│   ├── portfolio.py           # GET /api/portfolio/summary, /api/portfolio/history
│   ├── simulator.py           # POST /api/sim/order, GET /api/sim/portfolio, etc.
│   ├── screen.py              # POST /api/screen, /api/screen/rules, /api/watchlist
│   └── lines.py               # GET /api/lines/detect, POST /api/lines, etc.
├── core/
│   ├── indicators.py          # テクニカル指標の計算（SMA/EMA/RSI/MACD/BB/ATR/HV/一目）
│   ├── line_detector.py       # ライン自動検出ロジック（ピボット・線形回帰）
│   ├── screener.py            # スクリーニングエンジン（フィルター・スコアリング）
│   ├── simulator.py           # シミュレータ状態管理（ポートフォリオ・注文処理）
│   └── fx.py                  # 為替レート取得・円換算
├── models/
│   ├── order.py               # 注文・ポートフォリオのデータモデル
│   ├── line.py                # ラインのデータモデル
│   └── screen.py              # スクリーニングルール・結果のデータモデル
└── web/
    ├── index.html             # チャート画面
    ├── dashboard.html         # 総資産ダッシュボード画面
    └── screen.html            # スクリーニング画面
```

---

## 技術スタック

| レイヤー | 技術 |
|----------|------|
| バックエンド | Python 3.10+, FastAPI, Uvicorn |
| データ取得 | yfinance |
| テクニカル指標 | pandas-ta または手動計算 |
| フロントエンド | HTML + JavaScript + Chart.js |
| APIフォーマット | REST / JSON |

---

## APIエンドポイント仕様

### GET /api/chart

チャートデータとテクニカル指標を取得する。

**クエリパラメータ**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|------------|----|------|-----------|------|
| symbol | string | ✓ | - | ティッカーシンボル（例: `AAPL`, `7203.T`, `USDJPY=X`, `GC=F`, `BTC-USD`）|
| period | string | - | `3mo` | 期間（`1d` `5d` `1mo` `3mo` `6mo` `1y` `2y` `5y`）|
| interval | string | - | `1d` | 足種（`1m` `5m` `15m` `1h` `1d` `1wk` `1mo`）|
| indicators | string | - | `sma` | カンマ区切りで複数指定（`sma,ema,rsi,macd,bbands,ichimoku,atr,hv,volume`）|

**レスポンス例**

```json
{
  "symbol": "AAPL",
  "period": "3mo",
  "interval": "1d",
  "candles": [
    {
      "date": "2026-07-01",
      "open": 195.2,
      "high": 198.5,
      "low": 194.1,
      "close": 197.3,
      "volume": 52000000
    }
  ],
  "indicators": {
    "sma": [
      { "period": 25, "values": [null, ..., 196.5] },
      { "period": 75, "values": [null, ..., 193.2] }
    ],
    "ema": [
      { "period": 12, "values": [...] },
      { "period": 26, "values": [...] }
    ],
    "rsi": {
      "period": 14,
      "values": [null, ..., 62.3]
    },
    "macd": {
      "macd": [...],
      "signal": [...],
      "histogram": [...]
    },
    "bbands": {
      "upper": [...],
      "middle": [...],
      "lower": [...]
    },
    "ichimoku": {
      "tenkan": [...],
      "kijun": [...],
      "senkou_a": [...],
      "senkou_b": [...],
      "chikou": [...]
    },
    "atr": {
      "period": 14,
      "values": [null, ..., 3.25]
    },
    "hv": {
      "period": 20,
      "values": [null, ..., 25.3]
    },
    "volume": [...]
  }
}
```

**エラーレスポンス**

```json
{
  "error": "symbol_not_found",
  "message": "Symbol 'XXXXX' could not be found."
}
```

---

### GET /api/symbols/search

ティッカーシンボルの候補を検索する。

**クエリパラメータ**

| パラメータ | 型 | 必須 | 説明 |
|------------|----|------|------|
| q | string | ✓ | 検索キーワード |
| type | string | - | アセットタイプでフィルタ（`stock` `commodity` `forex` `crypto`）|

**レスポンス例**

```json
{
  "results": [
    { "symbol": "AAPL",     "name": "Apple Inc.",       "type": "stock",     "exchange": "NASDAQ" },
    { "symbol": "7203.T",   "name": "トヨタ自動車",       "type": "stock",     "exchange": "TSE" },
    { "symbol": "GC=F",     "name": "Gold Futures",     "type": "commodity", "exchange": "COMEX" },
    { "symbol": "CL=F",     "name": "Crude Oil WTI",    "type": "commodity", "exchange": "NYMEX" },
    { "symbol": "USDJPY=X", "name": "USD/JPY",          "type": "forex",     "exchange": "FX" },
    { "symbol": "BTC-USD",  "name": "Bitcoin USD",      "type": "crypto",    "exchange": "CoinMarketCap" }
  ]
}
```

---

### GET /api/analyze

エージェント向けの分析サマリーを返す。チャートデータをもとに簡易シグナルを生成する。

**クエリパラメータ**

`/api/chart` と同様。

**レスポンス例**

```json
{
  "symbol": "AAPL",
  "signals": {
    "rsi": { "value": 62.3, "state": "neutral" },
    "macd": { "state": "bullish_cross" },
    "bbands": { "state": "near_upper" },
    "ichimoku": { "state": "sanraku_koten", "above_cloud": true, "tenkan_kijun": "bullish_cross" },
    "atr": { "value": 3.25, "stop_loss_2atr": 190.8 },
    "hv": { "value": 25.3, "state": "high" }
  },
  "summary": "RSIは中立圏。MACDはゴールデンクロス直後。ボリンジャーバンド上限に接近。一目均衡表は三役好転。HV25.3%で高ボラティリティ圏。"
}
```

---

## 対応アセットタイプ

| タイプ | type値 | ティッカー例 | データソース |
|--------|--------|-------------|-------------|
| 株（国内） | `stock` | `7203.T`（トヨタ）、`6758.T`（ソニー） | yfinance |
| 株（米国） | `stock` | `AAPL`、`TSLA`、`NVDA` | yfinance |
| コモディティ | `commodity` | `GC=F`（金）、`CL=F`（原油WTI）、`SI=F`（銀）、`NG=F`（天然ガス）、`ZW=F`（小麦）| yfinance |
| 為替 | `forex` | `USDJPY=X`、`EURUSD=X`、`GBPJPY=X` | yfinance |
| 仮想通貨 | `crypto` | `BTC-USD`、`ETH-USD`、`SOL-USD` | yfinance |

yfinanceはすべてのタイプに対応しており、ティッカーシンボルの命名規則で種別を識別できる。

---

## テクニカル指標仕様

### SMA（単純移動平均）
- デフォルト期間: 25, 75
- 計算: 直近N本の終値平均

### EMA（指数移動平均）
- デフォルト期間: 12, 26
- 計算: 指数加重移動平均

### RSI（相対力指数）
- デフォルト期間: 14
- 範囲: 0〜100
- シグナル: 30以下＝売られすぎ、70以上＝買われすぎ

### MACD
- 設定: EMA(12) - EMA(26)、シグナル: EMA(9)
- ヒストグラム: MACD - シグナル

### ボリンジャーバンド
- 設定: SMA(20) ± 2σ

### ATR（Average True Range）
- デフォルト期間: 14
- 計算: True Range（当日高値-安値、当日高値-前日終値、前日終値-当日安値の最大値）のEMA
- 用途: ストップロス幅の自動計算（例: `stop_loss = 現値 - 2×ATR`）、ポジションサイジング

### ヒストリカルボラティリティ（HV）
- デフォルト期間: 20
- 計算: 過去N日の対数リターンの標準偏差を年率換算（× √252）
- 単位: %（例: 25.3%）
- 用途: リスク管理・ポジションサイジング・オプション理論価格の参考値

### 一目均衡表
- 転換線: 過去9本の高値・安値の中値
- 基準線: 過去26本の高値・安値の中値
- 先行スパン1: （転換線 + 基準線）÷ 2 を26本先にプロット
- 先行スパン2: 過去52本の高値・安値の中値を26本先にプロット
- 遅行スパン: 当日終値を26本前にプロット
- 雲（くも）: 先行スパン1と先行スパン2の間を塗りつぶし（陽雲・陰雲で色分け）
- シグナル: 三役好転（転換線が基準線を上抜け、価格が雲の上、遅行スパンが価格を上抜け）/ 三役逆転

### 出来高（Volume）
- ローソク足と別パネルで表示

---

## 総資産ダッシュボード

### 概要

保有全ポジションを円換算に統一し、アセットタイプ別・銘柄別の内訳をリアルタイムで把握できる。WebUIにグラフで表示し、エージェントもAPIで取得可能。

---

### 総資産APIエンドポイント

#### GET /api/portfolio/summary

全ポジションを円換算した総資産サマリーを返す。

**レスポンス例**

```json
{
  "total_value_jpy": 5234500.0,
  "cash_jpy": 850000.0,
  "invested_jpy": 4384500.0,
  "total_pnl_jpy": 234500.0,
  "total_pnl_pct": 4.69,
  "fx_rates": {
    "USDJPY": 149.5,
    "BTCJPY": 9525000.0
  },
  "as_of": "2026-10-14T10:00:00Z",
  "by_type": [
    { "type": "stock",     "value_jpy": 2150000.0, "pct": 41.1, "pnl_jpy":  95000.0 },
    { "type": "crypto",    "value_jpy": 1430000.0, "pct": 27.3, "pnl_jpy": 110000.0 },
    { "type": "commodity", "value_jpy":  512000.0, "pct":  9.8, "pnl_jpy":  18000.0 },
    { "type": "forex",     "value_jpy":  292500.0, "pct":  5.6, "pnl_jpy":  11500.0 },
    { "type": "cash",      "value_jpy":  850000.0, "pct": 16.2, "pnl_jpy":       0.0 }
  ],
  "by_position": [
    {
      "symbol": "AAPL",
      "name": "Apple Inc.",
      "type": "stock",
      "quantity": 10,
      "current_price_usd": 197.3,
      "current_price_jpy": 29496.0,
      "value_jpy": 294960.0,
      "pct": 5.64,
      "unrealized_pnl_jpy": 3450.0,
      "unrealized_pnl_pct": 1.18
    }
  ]
}
```

---

#### GET /api/portfolio/history

総資産の時系列推移を返す（グラフ用）。

**クエリパラメータ**

| パラメータ | 型 | デフォルト | 説明 |
|------------|----|-----------|------|
| period | string | `1mo` | 取得期間（`1w` `1mo` `3mo` `6mo` `1y` `all`）|
| interval | string | `1d` | 記録粒度（`1h` `1d` `1wk`）|

**レスポンス例**

```json
{
  "history": [
    {
      "date": "2026-09-01",
      "total_jpy": 5000000.0,
      "by_type": {
        "stock": 2050000.0,
        "crypto": 1320000.0,
        "commodity": 500000.0,
        "forex": 280000.0,
        "cash": 850000.0
      }
    }
  ]
}
```

---

### WebUI ダッシュボード画面

#### 画面構成

```
┌──────────────────────────────────────────────┐
│ 総資産: ¥5,234,500        前日比: +¥12,300 (+0.24%) │
│ 更新時刻: 2026-10-14 10:00                        │
├──────────────────────────────────────────────┤
│ [円グラフ] アセットタイプ別配分                      │
│   株式 41% / 仮想通貨 27% / コモディティ 10%         │
│   為替 6% / 現金 16%                              │
├──────────────────────────────────────────────┤
│ [積み上げ面グラフ] 総資産推移（期間切替: 1w/1mo/3mo/1y）│
│   タイプ別に色分けして積み上げ表示                   │
├──────────────────────────────────────────────┤
│ [テーブル] 保有銘柄一覧（円換算）                    │
│   銘柄 / 種別 / 保有数 / 現在値(円) / 評価額 / 損益  │
└──────────────────────────────────────────────┘
```

#### グラフ仕様

| グラフ | 種別 | 説明 |
|--------|------|------|
| アセット配分 | ドーナツチャート | タイプ別割合。ホバーで金額・損益を表示 |
| 総資産推移 | 積み上げ面グラフ | タイプ別を色分けして積み上げ。期間ボタンで切替 |
| 銘柄別損益 | 横棒グラフ | 銘柄ごとの評価損益（円）。プラス/マイナスで色分け |

#### 為替レート表示

- USD/JPY・主要通貨レートをヘッダーに常時表示
- yfinanceから定期取得（ペーパートレード中は数分間隔で自動更新）

---

## 銘柄スクリーニング機能

### 概要

テクニカル指標・ファンダメンタル・独自ロジックを組み合わせて、上昇候補銘柄をスキャンしてリストアップする。対象はウォッチリストと市場インデックス構成銘柄の両方から選択可能。全アセットタイプ（株・コモディティ・為替・仮想通貨）横断対応。

---

### 対象母集団

| グループ | 説明 | 銘柄数目安 |
|----------|------|-----------|
| ウォッチリスト | ユーザーが登録した銘柄 | 任意 |
| 日経225 | 東証プライム主要225銘柄 | 225 |
| S&P500 | 米国主要500銘柄 | 500 |
| TOPIX100 | 東証時価総額上位100銘柄 | 100 |
| 主要コモディティ | 金・原油・銀・天然ガス・小麦など | 20 |
| 主要通貨ペア | USD/JPY・EUR/USD・GBP/JPYなど | 20 |
| 主要仮想通貨 | BTC・ETH・SOLなど時価総額上位 | 20 |

---

### スクリーニングAPIエンドポイント

#### POST /api/screen

スクリーニングを実行して候補銘柄をリストアップする。

**リクエストボディ**

```json
{
  "universe": ["watchlist", "nikkei225"],
  "interval": "1d",
  "period": "6mo",
  "filters": [
    { "type": "rsi", "condition": "lt", "value": 40 },
    { "type": "macd", "condition": "bullish_cross" },
    { "type": "price_above_cloud" },
    { "type": "hv", "condition": "lt", "value": 30 },
    { "type": "custom", "rule_id": "rule_001" }
  ],
  "sort_by": "score",
  "limit": 20
}
```

| フィールド | 説明 |
|------------|------|
| universe | スキャン対象グループ（複数指定可）|
| filters | 絞り込み条件（AND結合）|
| sort_by | `score`（総合スコア）/ `rsi` / `hv` / `volume_surge`（出来高急増率）|
| limit | 返す銘柄数（デフォルト20）|

**フィルター条件一覧**

| type | condition / params | 説明 |
|------|--------------------|------|
| `rsi` | `lt` / `gt` + value | RSIが閾値以下/以上 |
| `macd` | `bullish_cross` / `bearish_cross` | MACDクロス発生 |
| `sma_cross` | `golden` / `dead` | SMAクロス発生 |
| `price_above_cloud` | — | 価格が一目均衡表の雲の上 |
| `price_below_cloud` | — | 価格が雲の下 |
| `bbands` | `near_lower` / `near_upper` | ボリンジャーバンド下限/上限付近 |
| `atr_breakout` | `value`（ATR倍率）| 直近N本でATR×N以上の値動き |
| `hv` | `lt` / `gt` + value | ヒストリカルボラティリティの閾値 |
| `volume_surge` | `value`（倍率）| 出来高が平均のN倍以上 |
| `near_support` | `pct`（許容距離%）| サポートライン付近 |
| `near_resistance` | `pct`（許容距離%）| レジスタンスライン付近 |
| `custom` | `rule_id` | 独自ルール（後述）|

**レスポンス例**

```json
{
  "scanned": 725,
  "matched": 8,
  "results": [
    {
      "symbol": "7203.T",
      "name": "トヨタ自動車",
      "type": "stock",
      "score": 0.88,
      "price": 2850.0,
      "signals": {
        "rsi": 38.2,
        "macd": "bullish_cross",
        "ichimoku": "above_cloud",
        "hv": 18.5,
        "volume_surge": 1.8
      },
      "matched_filters": ["rsi", "macd", "price_above_cloud"],
      "custom_signals": { "rule_001": true }
    }
  ]
}
```

---

#### GET /api/screen/universe

利用可能な母集団グループの一覧と銘柄数を返す。

---

### ウォッチリストAPI

#### GET /api/watchlist

登録銘柄の一覧を取得する。

#### POST /api/watchlist

銘柄を追加する。

```json
{ "symbol": "AAPL", "note": "決算後に注目" }
```

#### DELETE /api/watchlist/{symbol}

銘柄を削除する。

---

### 独自スクリーニングルール

ユーザーまたはエージェントが独自の判断ロジックをルールとして登録し、スクリーニングで再利用できる。

#### POST /api/screen/rules

独自ルールを登録する。

**リクエストボディ**

```json
{
  "rule_id": "rule_001",
  "name": "三役好転 + 出来高急増",
  "description": "一目均衡表の三役好転かつ出来高が5日平均の1.5倍以上",
  "conditions": [
    { "type": "ichimoku_sanraku_koten" },
    { "type": "volume_surge", "value": 1.5 }
  ],
  "logic": "AND"
}
```

| フィールド | 説明 |
|------------|------|
| conditions | 組み合わせる条件リスト |
| logic | `AND`（全条件一致）/ `OR`（いずれか一致）|

#### GET /api/screen/rules

登録済みルールの一覧を取得する。

#### DELETE /api/screen/rules/{rule_id}

ルールを削除する。

---

### スコアリング

スクリーニング結果の `score`（0〜1）は以下の重み付きスコアで算出する。デフォルト重みはAPIパラメータで上書き可能。

| 要素 | デフォルト重み |
|------|--------------|
| テクニカル一致数（マッチしたfilter数 / 全filter数） | 40% |
| RSI（売られすぎに近いほど高スコア） | 20% |
| 出来高急増率 | 20% |
| 一目均衡表の強さ（三役好転 > 雲の上 > 中立） | 20% |

---

### WebUIでの操作フロー

```
1. スクリーニング画面を開く
2. 対象母集団をチェックボックスで選択（ウォッチリスト・日経225・S&P500など）
3. フィルター条件を追加（プリセット or 独自ルールを選択）
4. 「スキャン実行」ボタン → POST /api/screen
5. 結果テーブルに候補銘柄・スコア・シグナルを表示
6. 銘柄をクリック → チャート画面に遷移してライン検出・詳細分析
7. 気になった銘柄を「ウォッチリストに追加」
```

---

### エージェント連携

エージェントは `/api/screen` を定期実行して上昇候補をスキャンし、条件を満たした銘柄を自動でウォッチリストに追加、または直接 `/api/sim/order` で注文を発行できる。

```
エージェント
  ├─ POST /api/screen → 候補銘柄リスト取得
  ├─ GET /api/analyze?symbol=... → 各候補の詳細シグナル確認
  └─ POST /api/sim/order → 条件を満たした銘柄を自動注文
```

---

## ライン描画機能（半自動）

### 概要

システムが高値・安値のラインをスコア上位4本自動検出してチャートに即表示する。ユーザーは不要なラインを削除するだけでよい。手動での追加・微調整も可能。水平線（サポート・レジスタンス）とトレンドライン（斜め）の両方に対応。

---

### ライン種別

| 種別 | 説明 |
|------|------|
| 水平線（サポート） | 安値が複数回反発したライン |
| 水平線（レジスタンス） | 高値が複数回跳ね返されたライン |
| トレンドライン（上昇） | 切り上がる安値を結ぶ斜めライン |
| トレンドライン（下降） | 切り下がる高値を結ぶ斜めライン |

---

### 自動検出ロジック

**水平線検出**
1. ローカル高値・安値をピボットポイントアルゴリズムで抽出（前後N本より高い/低い点）
2. 近い価格帯のピボットをクラスタリングして代表価格を算出
3. タッチ回数・直近からの距離・価格の丸さ（キリ番）でスコアリング
4. スコア上位をライン候補として返す

**トレンドライン検出**
1. 連続する安値（上昇トレンド）または高値（下降トレンド）を線形回帰でフィット
2. R²値（直線への当てはまり度）でスコアリング
3. 候補ラインの傾きと現在価格からブレイクアウト距離を計算

---

### ラインAPIエンドポイント

#### GET /api/lines/detect

チャートデータからライン候補を自動検出して返す。

**クエリパラメータ**

| パラメータ | 型 | デフォルト | 説明 |
|------------|----|-----------|------|
| symbol | string | 必須 | ティッカーシンボル |
| period | string | `6mo` | 検出対象期間 |
| interval | string | `1d` | 足種 |
| types | string | `horizontal,trend` | 検出するライン種別 |
| max_lines | int | 4 | 返すライン数の上限（スコア上位から選出）|

**レスポンス例**

```json
{
  "symbol": "AAPL",
  "lines": [
    {
      "id": "line_001",
      "type": "horizontal",
      "role": "resistance",
      "price": 200.0,
      "touches": 3,
      "score": 0.91,
      "status": "active"
    },
    {
      "id": "line_002",
      "type": "trend",
      "direction": "ascending",
      "point1": { "date": "2026-07-01", "price": 180.0 },
      "point2": { "date": "2026-09-01", "price": 190.0 },
      "slope": 0.17,
      "r_squared": 0.94,
      "score": 0.87,
      "status": "active"
    }
  ]
}
```

`status` の値: `active`（表示中）/ `deleted`（削除済）

---

#### POST /api/lines

ラインを手動で作成する（ユーザーがチャート上でクリックして起点を指定）。

**リクエストボディ**

```json
{
  "symbol": "AAPL",
  "type": "horizontal",
  "role": "support",
  "price": 185.0
}
```

```json
{
  "symbol": "AAPL",
  "type": "trend",
  "direction": "ascending",
  "point1": { "date": "2026-07-01", "price": 180.0 },
  "point2": { "date": "2026-09-01", "price": 190.0 }
}
```

---

#### PATCH /api/lines/{line_id}

ラインを手動調整する（価格・座標の微調整）。

**リクエストボディ**

```json
{ "price": 200.5 }
```

```json
{
  "point1": { "date": "2026-07-01", "price": 179.5 },
  "point2": { "date": "2026-09-01", "price": 189.5 }
}
```

---

#### DELETE /api/lines/{line_id}

ラインを削除する。

---

#### GET /api/lines

承認済みラインの一覧を取得する。

**クエリパラメータ**

| パラメータ | 型 | 説明 |
|------------|----|------|
| symbol | string | 銘柄フィルタ |
| status | string | `active` / `deleted` / `all`（デフォルト: `active`）|

---

### WebUIでの操作フロー

**自動検出 → 不要ライン削除フロー**
```
1. 「ライン検出」ボタンを押す
2. GET /api/lines/detect?max_lines=4 → スコア上位4本を即座に実線表示
3. ユーザーは不要なラインだけ操作
   └─ ラインをクリック → ×ボタン または Deleteキー → DELETE で削除
```

**手動描画 → 自動スナップフロー**
```
1. ツールバーで「水平線」または「トレンドライン」を選択
2. チャート上でクリック（水平線: 1点、トレンドライン: 2点）
3. システムが近傍の高値・安値に自動スナップ（Shiftキーで無効化）
4. POST /api/lines → ラインを保存・表示
5. ドラッグで価格・角度を微調整 → PATCH で更新
```

---

### ライン情報の `/api/analyze` への統合

`/api/analyze` のレスポンスにライン情報を追加する。

```json
{
  "lines": {
    "nearest_resistance": { "price": 200.0, "distance_pct": 1.37 },
    "nearest_support": { "price": 190.0, "distance_pct": -3.71 },
    "trend": { "type": "ascending", "breakout_distance_pct": 2.1 }
  }
}
```

エージェントはこの情報を使って、サポート/レジスタンスへの接近や、ブレイクアウトをトリガーに注文を出せる。

---

## WebUI仕様

### 画面一覧

| ファイル | 画面名 | 説明 |
|----------|--------|------|
| `index.html` | チャート画面 | メインのチャート分析・売買シミュレータ |
| `dashboard.html` | 総資産ダッシュボード | 円換算総資産・タイプ別グラフ |
| `screen.html` | スクリーニング画面 | 銘柄スキャン・候補リスト |

ナビゲーションバーで3画面を切り替える。

---

### チャート画面（index.html）

```
┌──────────────────────────────────────────────────┐
│ナビゲーション: [チャート] [ダッシュボード] [スクリーニング]│
│ヘッダー: 銘柄入力 / 期間ボタン / 為替レート表示         │
├──────────────────────────────────────────────────┤
│ツールバー: [指標▼] [ライン検出] [水平線] [トレンドライン] │
├──────────────────────────────────────────────────┤
│ メインチャート（ローソク足 + 移動平均 + 一目均衡表）      │
│  ※ ラインオーバーレイ（自動検出 + 手動描画）             │
│  ※ 売買シグナル・注文マーカーをオーバーレイ表示          │
├──────────────────────────────────────────────────┤
│ サブチャート1: 出来高                                │
├──────────────────────────────────────────────────┤
│ サブチャート2: RSI / MACD / ATR / HV（タブ切替）       │
├──────────────────────────────────────────────────┤
│ シミュレータパネル                                   │
│  ├ モード切替: バックテスト / ペーパートレード           │
│  ├ エージェント状態: [稼働中▶] [一時停止⏸]             │
│  ├ 手動注文フォーム（銘柄・数量・売買・成行/指値/逆指値） │
│  ├ ポートフォリオ一覧（保有銘柄・評価損益・円換算）       │
│  └ 注文履歴ログ（agent / manual フィルタ）             │
└──────────────────────────────────────────────────┘
```

### 総資産ダッシュボード画面（dashboard.html）

```
┌──────────────────────────────────────────────────┐
│ナビゲーション                                        │
│総資産: ¥5,234,500   前日比: +¥12,300 (+0.24%)        │
│為替: USD/JPY 149.5  BTC/JPY 9,525,000              │
├──────────────────────────────────────────────────┤
│ [ドーナツチャート]       │ [横棒グラフ]               │
│  アセットタイプ別配分    │  銘柄別評価損益（円）       │
├──────────────────────────────────────────────────┤
│ [積み上げ面グラフ] 総資産推移（1w / 1mo / 3mo / 1y）  │
│  タイプ別色分けで積み上げ表示                         │
├──────────────────────────────────────────────────┤
│ [テーブル] 保有銘柄一覧（円換算）                      │
│  銘柄 / 種別 / 保有数 / 現在値(円) / 評価額 / 損益     │
└──────────────────────────────────────────────────┘
```

### スクリーニング画面（screen.html）

```
┌──────────────────────────────────────────────────┐
│ナビゲーション                                        │
├──────────────────────────────────────────────────┤
│ 母集団選択（チェックボックス）                         │
│  □ ウォッチリスト  □ 日経225  □ S&P500  □ 仮想通貨  │
├──────────────────────────────────────────────────┤
│ フィルター条件（プリセット or 独自ルール選択）           │
│  [+ 条件追加]  [独自ルール管理]  [スキャン実行]        │
├──────────────────────────────────────────────────┤
│ 結果テーブル（スキャン: 725件 / マッチ: 8件）          │
│  銘柄 / スコア / RSI / MACD / 一目 / HV / 出来高比   │
│  → クリックでチャート画面に遷移 / ウォッチリストに追加  │
└──────────────────────────────────────────────────┘
```

### 共通操作

- 銘柄入力: テキストボックスで入力 → Enter または候補選択
- 期間選択: `1mo` `3mo` `6mo` `1y` `2y` ボタン
- 指標切替: チェックボックスで表示/非表示をトグル
- ホバー: クロスヘア表示 + OHLCV値のツールチップ
- ライン操作: クリックで選択 → ×ボタン/Deleteキーで削除、ドラッグで微調整

---

## 売買シミュレータ仕様

### モード

| モード | 説明 |
|--------|------|
| バックテスト | 過去データに対して戦略を適用し、損益・勝率・最大ドローダウンを検証 |
| ペーパートレード | リアルタイムデータで仮想売買。エージェント自動注文 + 手動オーバーライド対応 |

### ポートフォリオ管理

- 複数銘柄を同時保有可能
- 現金残高・保有ポジション・評価損益・実現損益を管理
- アセットタイプ横断（株・コモディティ・為替・仮想通貨を混在保有可能）

### シミュレータAPIエンドポイント

#### POST /api/sim/order

注文を発注する（エージェントまたは手動）。

**リクエストボディ**

```json
{
  "symbol": "AAPL",
  "side": "buy",
  "quantity": 10,
  "order_type": "market",
  "limit_price": null,
  "stop_price": null,
  "take_profit": null,
  "stop_loss": null,
  "source": "agent"
}
```

| フィールド | 型 | 説明 |
|------------|----|------|
| symbol | string | ティッカーシンボル |
| side | string | `buy` または `sell` |
| quantity | number | 数量 |
| order_type | string | `market`（成行）/ `limit`（指値）/ `stop`（逆指値）/ `oco`（指値＋逆指値）|
| limit_price | number\|null | 指値価格 |
| stop_price | number\|null | 逆指値価格（ストップ注文・OCO時に使用）|
| take_profit | number\|null | 利確価格（自動決済トリガー）|
| stop_loss | number\|null | 損切り価格（自動決済トリガー）|
| source | string | `agent`（自動）または `manual`（手動）|

**レスポンス例**

```json
{
  "order_id": "ord_001",
  "status": "filled",
  "filled_price": 197.3,
  "slippage": 0.05,
  "commission": 9.95,
  "filled_at": "2026-10-14T09:32:00Z",
  "pnl_realized": null
}
```

---

#### GET /api/sim/portfolio

現在のポートフォリオ状態を取得する。

**レスポンス例**

```json
{
  "cash": 850000.0,
  "base_currency": "JPY",
  "positions": [
    {
      "symbol": "AAPL",
      "type": "stock",
      "quantity": 10,
      "avg_price": 195.0,
      "current_price": 197.3,
      "market_value_usd": 1973.0,
      "market_value_jpy": 295950.0,
      "unrealized_pnl": 23.0,
      "unrealized_pnl_pct": 1.18,
      "allocation_pct": 29.2,
      "leverage": 1.0
    },
    {
      "symbol": "BTC-USD",
      "type": "crypto",
      "quantity": 0.5,
      "avg_price": 60000.0,
      "current_price": 63500.0,
      "market_value_usd": 31750.0,
      "market_value_jpy": 4762500.0,
      "unrealized_pnl": 1750.0,
      "unrealized_pnl_pct": 5.83,
      "allocation_pct": 47.1,
      "leverage": 1.0
    }
  ],
  "allocation_by_type": {
    "stock": 29.2,
    "crypto": 47.1,
    "cash": 23.7
  },
  "total_value_jpy": 1015000.0,
  "total_unrealized_pnl": 15000.0,
  "total_realized_pnl": 32000.0,
  "total_commission_paid": 450.0,
  "total_pnl_pct": 1.50,
  "max_drawdown_pct": -3.2
}
```

---

#### DELETE /api/sim/order/{order_id}

未約定の指値・逆指値注文をキャンセルする。

---

#### GET /api/sim/orders

注文履歴を取得する。

**クエリパラメータ**

| パラメータ | 型 | 説明 |
|------------|----|------|
| symbol | string | 銘柄フィルタ（省略時は全銘柄）|
| source | string | `agent` / `manual` でフィルタ |
| limit | int | 取得件数（デフォルト50）|

---

#### GET /api/sim/summary

実現損益・手数料・シャープレシオなどの集計サマリーを返す。

**レスポンス例**

```json
{
  "total_trades": 42,
  "win_rate": 0.61,
  "total_realized_pnl": 32000.0,
  "total_commission_paid": 450.0,
  "net_pnl": 31550.0,
  "sharpe_ratio": 1.42,
  "profit_factor": 2.15,
  "avg_holding_days": 4.3,
  "max_drawdown_pct": -3.2,
  "agent_orders": 38,
  "manual_orders": 4
}
```

---

#### POST /api/sim/backtest

バックテストを実行する。

**リクエストボディ**

```json
{
  "symbol": "AAPL",
  "period": "1y",
  "interval": "1d",
  "strategy": {
    "type": "sma_cross",
    "params": { "short": 25, "long": 75 }
  },
  "initial_cash": 1000000
}
```

**レスポンス例**

```json
{
  "symbol": "AAPL",
  "strategy": "sma_cross",
  "initial_cash": 1000000,
  "final_value": 1123500,
  "total_return_pct": 12.35,
  "benchmark_return_pct": 9.10,
  "max_drawdown_pct": -8.2,
  "sharpe_ratio": 1.38,
  "profit_factor": 2.05,
  "win_rate": 0.62,
  "total_trades": 13,
  "avg_holding_days": 18.4,
  "total_commission": 1250.0,
  "net_return_pct": 12.22,
  "trades": [
    {
      "date": "2025-11-03",
      "side": "buy",
      "price": 180.5,
      "quantity": 55,
      "commission": 99.0,
      "slippage": 0.05,
      "pnl": null
    }
  ]
}
```

---

#### POST /api/sim/reset

シミュレータの状態（ポートフォリオ・注文履歴）をリセットする。

```json
{
  "initial_cash": 1000000,
  "base_currency": "JPY",
  "commission_model": {
    "stock_pct": 0.1,
    "forex_pct": 0.02,
    "crypto_pct": 0.1,
    "commodity_pct": 0.05
  },
  "slippage_pct": 0.05,
  "risk_limits": {
    "max_drawdown_pct": 20.0,
    "max_position_pct": 30.0,
    "leverage_limit": 3.0
  }
}
```

| フィールド | 説明 |
|------------|------|
| base_currency | ポートフォリオ表示通貨（`JPY` or `USD`）|
| commission_model | アセットタイプ別手数料率（%）|
| slippage_pct | 成行注文のスリッページ想定値（%）|
| risk_limits.max_drawdown_pct | この値を超えたらエージェント自動停止 |
| risk_limits.max_position_pct | 1銘柄の最大保有比率（%）|
| risk_limits.leverage_limit | 最大レバレッジ倍率 |

---

### 組み込み戦略（バックテスト用）

| strategy.type | 説明 |
|---------------|------|
| `sma_cross` | SMAゴールデンクロス/デッドクロスで売買 |
| `rsi_threshold` | RSIが閾値を下回ったら買い、上回ったら売り |
| `macd_cross` | MACDラインとシグナルラインのクロスで売買 |
| `bbands_revert` | ボリンジャーバンド下限タッチで買い、上限で売り |
| `custom` | エージェントが外部から注文APIを直接叩く |

---

### エージェント制御API

#### POST /api/sim/agent/pause

エージェントの自動売買を一時停止する。既存ポジションは保持。

#### POST /api/sim/agent/resume

一時停止中のエージェントを再開する。

#### GET /api/sim/agent/status

エージェントの稼働状態を返す。

```json
{
  "status": "running",
  "stopped_reason": null,
  "last_order_at": "2026-10-14T09:32:00Z",
  "drawdown_current_pct": 2.1,
  "drawdown_limit_pct": 20.0
}
```

`status` の値: `running` / `paused` / `stopped_by_risk`（ドローダウン超過による自動停止）

---

### エージェント自動売買フロー（ペーパートレード）

```
エージェント
  │
  ├─ GET /api/sim/agent/status  → 稼働確認（stopped_by_risk なら中断）
  │
  ├─ GET /api/analyze  → シグナル取得
  │
  ├─ 判断ロジック（エージェント内部）
  │    ├─ ポジションサイジング（risk_limits.max_position_pct を参照）
  │    ├─ bullish → POST /api/sim/order { side:"buy", stop_loss:..., take_profit:... }
  │    └─ bearish → POST /api/sim/order { side:"sell", stop_loss:..., take_profit:... }
  │
  ├─ GET /api/sim/portfolio  → 損益確認・ドローダウン監視
  │    └─ max_drawdown_pct 超過 → サーバー側で自動停止（status: stopped_by_risk）
  │
  └─ （次のポーリングへ）

人間（WebUI）
  ├─ 手動注文フォームから POST /api/sim/order { source: "manual" }
  │    ※ エージェント判断をオーバーライド可能
  └─ POST /api/sim/agent/pause / resume でエージェントを制御
```

---

## エージェント連携設計

FastAPIサーバーはHTTPで操作できるため、エージェントは以下のように利用できる。

1. `/api/chart` でデータ取得 → `/api/analyze` でシグナル取得 → `/api/sim/order` で注文
2. `/api/sim/portfolio` で損益監視・ポジション調整判断
3. `/api/sim/backtest` で戦略を事前検証してからペーパートレードに移行
4. 複数銘柄を並列ポーリングしてポートフォリオ全体を最適化

エージェントが使いやすいよう、全レスポンスはJSON形式で統一する。

---

## 開発フェーズ

| フェーズ | 内容 |
|----------|------|
| Phase 1 | FastAPIサーバー + yfinanceでデータ取得API |
| Phase 2 | テクニカル指標の計算実装 |
| Phase 3 | WebUI（ローソク足チャート）実装 |
| Phase 4 | `/api/analyze` によるシグナル生成 |
| Phase 5 | シミュレータ基盤（ポートフォリオ管理・注文API・通貨換算）|
| Phase 6 | コスト計算（手数料・スリッページ）+ リスク制限設定 |
| Phase 7 | バックテストエンジン（シャープレシオ・PF・ベンチマーク比較）|
| Phase 8 | ペーパートレード + エージェント制御API（pause/resume/自動停止）|
| Phase 9 | WebUIシミュレータパネル統合 |
| Phase 10 | スクリーニング基盤（母集団管理・フィルターエンジン）|
| Phase 11 | 独自ルール登録・ウォッチリスト |
| Phase 12 | WebUIスクリーニング画面 |
| Phase 13 | 総資産ダッシュボード（円換算・グラフ）|

---

## 依存パッケージ（requirements.txt）

```
# サーバー
fastapi
uvicorn[standard]
python-multipart

# データ取得
yfinance

# データ処理・指標計算
pandas
numpy
pandas-ta
scipy               # 線形回帰（トレンドライン検出）

# 非同期・スケジューリング
httpx               # 非同期HTTPクライアント
apscheduler         # 定期スキャン・ペーパートレードのポーリング

# ユーティリティ
python-dateutil
```
