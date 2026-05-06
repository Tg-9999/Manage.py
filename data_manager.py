"""
data_manager.py — Kit Accounts Manager v3
New: saved providers (LR/AK/KN), saved buyers (KP), holder name, custom dates
"""

import json, os, uuid
from datetime import datetime, timedelta
from typing import List, Dict, Optional

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")
BRANDS    = ["BOM", "CBI", "BB", "RBL"]

# ── Default seed data (pre-loaded providers & buyers) ─────────────────────────
SEED_PROVIDERS = [
    {"short": "LR", "name": "LR"},
    {"short": "AK", "name": "AK"},
    {"short": "KN", "name": "KN"},
]
SEED_BUYERS = [
    {"short": "KP", "name": "KP"},
]


class DataManager:
    def __init__(self):
        self._d: Dict = {}
        self._load()

    # ── Persistence ────────────────────────────────────────────────────────────

    def _load(self):
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                self._d = json.load(f)
        else:
            self._d = {}

        self._d.setdefault("next_kit_no", 1)
        self._d.setdefault("providers", {})
        self._d.setdefault("buyers", {})
        self._d.setdefault("kits", {})

        # Seed default providers if not present
        existing_names = {p["name"].upper() for p in self._d["providers"].values()}
        for sp in SEED_PROVIDERS:
            if sp["name"].upper() not in existing_names:
                pid = self._uid()
                self._d["providers"][pid] = {
                    "id": pid, "name": sp["name"], "contact": "",
                    "total_kits": 0, "total_cost": 0.0,
                    "total_paid": 0.0, "outstanding": 0.0,
                    "payments": [], "created": self._now(),
                }

        # Seed default buyers if not present
        existing_buyers = {b["name"].upper() for b in self._d["buyers"].values()}
        for sb in SEED_BUYERS:
            if sb["name"].upper() not in existing_buyers:
                bid = self._uid()
                self._d["buyers"][bid] = {
                    "id": bid, "name": sb["name"], "contact": "",
                    "total_kits": 0, "total_paid": 0.0,
                    "total_pending": 0.0, "created": self._now(),
                }

        self._save()

    def _save(self):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(self._d, f, indent=2, ensure_ascii=False)

    def _now(self) -> str:
        return datetime.now().isoformat(timespec="seconds")

    def _uid(self) -> str:
        return str(uuid.uuid4())[:8]

    def _new_kit_no(self) -> str:
        n = self._d["next_kit_no"]
        self._d["next_kit_no"] = n + 1
        return str(n).zfill(4)

    # ══════════════════════════════════════════════════════════════════════════
    # PROVIDERS
    # ══════════════════════════════════════════════════════════════════════════

    def get_all_providers(self) -> List[Dict]:
        return list(self._d["providers"].values())

    def get_provider(self, prov_id: str) -> Dict:
        return self._d["providers"][prov_id]

    def get_providers_with_outstanding(self) -> List[Dict]:
        return [p for p in self._d["providers"].values() if p["outstanding"] > 0.009]

    def add_new_provider(self, name: str, contact: str = "") -> Dict:
        pid = self._uid()
        self._d["providers"][pid] = {
            "id": pid, "name": name, "contact": contact,
            "total_kits": 0, "total_cost": 0.0,
            "total_paid": 0.0, "outstanding": 0.0,
            "payments": [], "created": self._now(),
        }
        self._save()
        return self._d["providers"][pid]

    def update_provider_payment(self, prov_id: str, amount: float) -> Dict:
        p = self._d["providers"][prov_id]
        p["total_paid"]  = round(p["total_paid"] + amount, 2)
        p["outstanding"] = round(p["total_cost"] - p["total_paid"], 2)
        p.setdefault("payments", []).append({"amount": amount, "date": self._now()})
        self._save()
        return p

    # ══════════════════════════════════════════════════════════════════════════
    # BUYERS
    # ══════════════════════════════════════════════════════════════════════════

    def get_all_buyers(self) -> List[Dict]:
        return list(self._d["buyers"].values())

    def get_buyer(self, buyer_id: str) -> Dict:
        return self._d["buyers"][buyer_id]

    def add_new_buyer(self, name: str, contact: str = "") -> Dict:
        bid = self._uid()
        self._d["buyers"][bid] = {
            "id": bid, "name": name, "contact": contact,
            "total_kits": 0, "total_paid": 0.0,
            "total_pending": 0.0, "created": self._now(),
        }
        self._save()
        return self._d["buyers"][bid]

    # ══════════════════════════════════════════════════════════════════════════
    # KITS
    # ══════════════════════════════════════════════════════════════════════════

    def add_provider_kits(
        self,
        provider_id: str,
        brand: str,
        account_no: str,
        card_no: str,
        holder_name: str,
        qty: int,
        cost_per_kit: float,
        paid_now: float,
        kit_date: str,          # ISO date string
    ) -> List[Dict]:
        p = self._d["providers"][provider_id]
        total_cost       = round(cost_per_kit * qty, 2)
        p["total_cost"]  = round(p.get("total_cost", 0) + total_cost, 2)
        p["total_paid"]  = round(p.get("total_paid", 0) + paid_now, 2)
        p["total_kits"]  = p.get("total_kits", 0) + qty
        p["outstanding"] = round(p["total_cost"] - p["total_paid"], 2)
        if paid_now > 0:
            p.setdefault("payments", []).append({
                "amount": paid_now, "date": self._now(),
                "note": f"Initial — {qty} kit(s)"
            })

        created = []
        for _ in range(qty):
            kit_no = self._new_kit_no()
            kit = {
                "kit_no":        kit_no,
                "brand":         brand,
                "account_no":    account_no,
                "card_no":       card_no,
                "holder_name":   holder_name,
                "provider_id":   provider_id,
                "provider_name": p["name"],
                "cost_price":    cost_per_kit,
                "status":        "unsold",
                "date_added":    kit_date,
                "buyer_id":      "",
                "buyer_name":    "",
                "buyer_contact": "",
                "sell_price":    0.0,
                "buyer_paid":    0.0,
                "date_sold":     "",
            }
            self._d["kits"][kit_no] = kit
            created.append(kit)

        self._save()
        return created

    def get_kit(self, kit_no: str) -> Dict:
        return self._d["kits"][kit_no]

    def get_unsold_kits(self) -> List[Dict]:
        kits = [k for k in self._d["kits"].values() if k["status"] == "unsold"]
        kits.sort(key=lambda k: int(k["kit_no"]))
        return kits

    def get_pending_buyer_kits(self) -> List[Dict]:
        kits = [
            k for k in self._d["kits"].values()
            if k["status"] == "sold" and k["sell_price"] - k["buyer_paid"] > 0.009
        ]
        kits.sort(key=lambda k: int(k["kit_no"]), reverse=True)
        return kits

    def get_all_kits(self, filter: str = "all") -> List[Dict]:
        kits = list(self._d["kits"].values())
        if filter == "unsold":
            kits = [k for k in kits if k["status"] == "unsold"]
        elif filter == "sold":
            kits = [k for k in kits if k["status"] == "sold"]
        elif filter in BRANDS:
            kits = [k for k in kits if k["brand"] == filter]
        kits.sort(key=lambda k: int(k["kit_no"]), reverse=True)
        return kits

    def sell_kit(
        self,
        kit_no: str,
        buyer_id: str,
        buyer_name: str,
        buyer_contact: str,
        sell_price: float,
        paid_now: float,
        date_sold: str,
    ) -> Dict:
        kit = self._d["kits"][kit_no]
        kit.update({
            "status":        "sold",
            "buyer_id":      buyer_id,
            "buyer_name":    buyer_name,
            "buyer_contact": buyer_contact,
            "sell_price":    round(sell_price, 2),
            "buyer_paid":    round(paid_now, 2),
            "date_sold":     date_sold,
        })
        # Update buyer stats
        if buyer_id and buyer_id in self._d["buyers"]:
            b = self._d["buyers"][buyer_id]
            b["total_kits"]    = b.get("total_kits", 0) + 1
            b["total_paid"]    = round(b.get("total_paid", 0) + paid_now, 2)
            b["total_pending"] = round(b.get("total_pending", 0) + sell_price - paid_now, 2)
        self._save()
        return kit

    def update_buyer_payment(self, kit_no: str, amount: float) -> Dict:
        kit = self._d["kits"][kit_no]
        old_paid = kit["buyer_paid"]
        kit["buyer_paid"] = round(old_paid + amount, 2)
        # Update buyer stats
        bid = kit.get("buyer_id", "")
        if bid and bid in self._d["buyers"]:
            b = self._d["buyers"][bid]
            b["total_paid"]    = round(b.get("total_paid", 0) + amount, 2)
            b["total_pending"] = round(b.get("total_pending", 0) - amount, 2)
        self._save()
        return kit

    # ══════════════════════════════════════════════════════════════════════════
    # SUMMARY
    # ══════════════════════════════════════════════════════════════════════════

    def get_full_summary(self) -> Dict:
        kits      = list(self._d["kits"].values())
        providers = list(self._d["providers"].values())
        sold   = [k for k in kits if k["status"] == "sold"]

        total_billed     = sum(k["sell_price"] for k in sold)
        buyer_received   = sum(k["buyer_paid"]  for k in sold)
        total_cost       = sum(p["total_cost"]  for p in providers)
        provider_paid    = sum(p["total_paid"]  for p in providers)

        by_brand = {}
        for brand in BRANDS:
            bk = [k for k in kits if k["brand"] == brand]
            bs = [k for k in bk   if k["status"] == "sold"]
            by_brand[brand] = {
                "kits":   len(bk),
                "billed": sum(k["sell_price"] for k in bs),
                "cost":   sum(k["cost_price"] for k in bk),
            }

        return {
            "total_kits":       len(kits),
            "sold":             len(sold),
            "unsold":           len(kits) - len(sold),
            "total_billed":     round(total_billed, 2),
            "buyer_received":   round(buyer_received, 2),
            "buyer_pending":    round(total_billed - buyer_received, 2),
            "total_cost":       round(total_cost, 2),
            "provider_paid":    round(provider_paid, 2),
            "provider_pending": round(total_cost - provider_paid, 2),
            "by_brand":         by_brand,
        }

    # ── Date helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def date_today() -> str:
        return datetime.now().date().isoformat()

    @staticmethod
    def date_yesterday() -> str:
        return (datetime.now().date() - timedelta(days=1)).isoformat()

    @staticmethod
    def date_2days_ago() -> str:
        return (datetime.now().date() - timedelta(days=2)).isoformat()

    @staticmethod
    def parse_custom_date(text: str) -> Optional[str]:
        """Parse DD/MM/YYYY → ISO YYYY-MM-DD. Returns None if invalid."""
        text = text.strip()
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d %m %Y"):
            try:
                return datetime.strptime(text, fmt).date().isoformat()
            except ValueError:
                continue
        return None

    @staticmethod
    def fmt_display_date(iso: str) -> str:
        try:
            return datetime.fromisoformat(iso).strftime("%d %b %Y")
        except Exception:
            return iso
