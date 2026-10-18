# Japan Stock Market Data MCP（東証株価・市場データ・日本株 screener）

TSE 株式・市場データ MCP サーバー — 東京証券取引所の株価・市場データを AI エージェントに提供。

公式 API（J-Quants / JPX）を使用するため **TOS リスクなし・無料枠あり**。

## Tools（MCP ツール一覧）

| ツール名 | 機能 |
|---|---|
| `get_quote(code, days)` | 指定銘柄の最新日足 OHLCV（高値・安値・出来高含む） |
| `screener(market, sector, min_market_cap, ...)` | 市場・業種・時価総額・価格・値幅で株をスクリーニング |
| `get_valuation(code)` | 時価総額・PER・PBR・配当利回り |
| `get_financial_summary(code, period)` | 売上高・営業利益・純利益（四半期累計） |
| `get_calendar(year, month)` | 取引カレンダー（休日リスト） |
| `sector_list()` | 33業種 / 17業種 分類コードマッピング |

## 動作要件

- Python >= 3.10、fastmcp / mcp
- 無料枠: J-Quants 無料プラン（12週間データラグ）
- 認証: `JQUANTS_API_KEY` 環境変数（https://jpx-jquants.com で無料登録）
- 完全ローカル実行（stdio / HTTP 両対応）

## Quickstart

```bash
# 1. クローン
git clone https://github.com/atushi1841/japan-stock-mcp.git
cd japan-stock-mcp

# 2. 依存
pip install fastmcp

# 3. stdio mode で起動（Claude Desktop 等から接続）
export JQUANTS_API_KEY="your-free-key"
python server.py

# 4. HTTP mode で起動
python server.py --http --port 8000
```

### 動作確認

```bash
python server.py --http --port 8000 &
sleep 2
curl -s -X POST http://localhost:8000/mcp/tools/list \
  -H "Content-Type: application/json" \
  -d '{}' | jq '.tools[].name'
```

## MCP 公開レジストリ登録状況

| レジストリ | 状態 | 備考 |
|---|---|---|
| MCP 公式レジストリ | ✅ 登録済み | `io.github.atushi1841/japan-stock-mcp` |
| Smithery | 📝 未登録 | MCPB バンドル作成済（v0.1.0）— 公開はユーザー手動操作待ち |
| mcp.so | 📝 未登録 | YAML テンプレ準備中 |

## 関連プロジェクト

- 既存 Japan MCP 系列: japan-ec-mcp, japan-price-alert-mcp, japan-intel-mcp, japan-market-mcp, japan-jepx-mcp, jartic-japan-traffic-mcp 等

## Apify Actor

関連するApifyアクターで同じデータをAPI経由で取得可能:

| Actor名 | 説明 | URL |
|---|---|---|
| [japan-market-mcp](https://apify.com/fruitful_quintessence/japan-market-mcp) | 中古品価格比較MCP（カメラ・時計・ブランド品・楽器・車・楽天） | apify.actor |
| [japan-market-mcp GitHub](https://github.com/atushi1841/japan-market-mcp) | 上記のオープンソース版 | github.com |

J-Quants公式APIを使用する本リポジトリとは別に、スクレイピング型Actorsも提供。

## License

MIT License.

---
## Data & Store

- **Apify Store:** https://apify.com/fruitful_quintessence
- **Gumroad datasets:** https://atushi5.gumroad.com/l/kutuxe
