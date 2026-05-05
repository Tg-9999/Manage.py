# Kit Accounts Manager Bot v2

## Bot Flow (Full Button System)

```
/start → Main Menu
├── ➕ Add Kit from Provider
│     Provider naam → Contact → Brand (button) → Account No → Card No
│     → Qty → Cost per kit → Paid now
│     ✅ Kits auto-assigned (0001, 0002, ...)
│
├── 🛒 Sell Kit to Buyer
│     Kit select (button list) → Buyer naam → Contact → Sell price → Paid now
│
├── 💰 Update Buyer Payment
│     Pending kits list (button) → Amount → ✅ Updated
│
├── 💸 Pay to Provider
│     Outstanding providers list (button) → Amount → ✅ Updated
│
├── 📋 View Kit Ledger
│     Filter: All / Unsold / Sold / BOM / CBI / BB / RBL
│     Shows: Kit# | Brand | Account | Card | Provider | Buyer | Payments
│
├── 👥 View Providers
│     All providers with cost / paid / pending
│
└── 📊 Full Report
      Revenue, Cost, Net, Brand-wise breakdown
```

---

## Setup

### Step 1 — Get Bot Token
1. Telegram → search @BotFather
2. `/newbot` → follow steps → copy token

### Step 2 — Get Your User ID
1. Search @userinfobot → `/start` → note your ID

### Step 3 — Install
```bash
pip install -r requirements.txt
```

### Step 4 — Configure
Edit `bot.py` lines 16-17:
```python
BOT_TOKEN = "your_token_here"
OWNER_ID  = 123456789
```
Or use environment variables:
```bash
export BOT_TOKEN="your_token"
export OWNER_ID="your_id"
```

### Step 5 — Run
```bash
python bot.py
```

---

## Files
```
kit_accounts_bot/
├── bot.py           # Bot logic
├── data_manager.py  # Data layer
├── data.json        # Auto-created, all records here
└── requirements.txt
```

**Backup `data.json` regularly!**
