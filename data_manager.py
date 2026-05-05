"""
data_manager.py — Complete data layer for Kit Accounts Manager
Storage: data.json (auto-created in same folder)

Structure:
{
  "next_kit_no": 1,
  "providers": { "<id>": { ...provider fields... } },
  "kits": { "0001": { ...kit fields... } }
}
"""

import json, os, uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")

BRANDS = ["BOM", "CBI", "BB", "RBL"]


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
        self._d.setdefault("kits", {})
        self._save()

    def _save(self):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(self._d, f, indent=2, ensure_ascii=False)

    def _now(self) -> str:
        return datetime.now().isoformat(timespec="seconds")

    def _new_kit_no(self) -> str:
        n = self._d["next_kit_no"]
        self._d["next_kit_no"] = n + 1
        return str(n).zfill(4)   # "0001", "0002", ...

    def _uid(self) -> str:
        return str(uuid.uuid4())[:8]

    # ══════════════════════════════════════════════════════════════════════════
    # PROVIDERS
    # ══════════════════════════════════════════════════════════════════════════

    def add_provider_kits(
        self,
        provider_name: str,
        provider_contact: str,
        brand: str,
        account_no: str,
        card_no: str,
        qty: int,
        cost_per_kit: float,
        paid_now: float,
    ) -> List[Dict]:
        """
        Register a provider (or find existing by name+contact),
        create `qty` kit records, return list of created kits.
        """
        # Find existing provider or create new
        prov_id = self._find_or_create_provider(provider_name, provider_contact)
        prov    = self._d["providers"][prov_id]

        total_cost = cost_per_kit * qty
        prov["total_cost"]  = round(prov.get("total_cost", 0) + total_cost, 2)
        prov["total_paid"]  = round(prov.get("total_paid", 0) + paid_now, 2)
        prov["total_kits"]  = prov.get("total_kits", 0) + qty
        prov["outstanding"] = round(prov["total_cost"] - prov["total_paid"], 2)

        # Log payment entry
        if paid_now > 0:
            prov.setdefault("payments", []).append({
                "amount": paid_now,
                "date": self._now(),
                "note": f"Initial payment for {qty} kit(s)"
            })

        # Create kit records
        created = []
        for _ in range(qty):
            kit_no = self._new_kit_no()
            kit = {
                "kit_no":        kit_no,
                "brand":         brand,
                "account_no":    account_no,
                "card_no":       card_no,
                "provider_id":   prov_id,
                "provider_name": provider_name,
                "cost_price":    cost_per_kit,
                "status":        "unsold",
                "date_added":    self._now(),
                # Buyer fields (filled on sale)
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

    def _find_or_create_provider(self, name: str, contact: str) -> str:
        # Try to find existing by name (case-insensitive)
        for pid, p in self._d["providers"].items():
            if p["name"].lower() == name.lower():
                return pid
        # Create new
        pid = self._uid()
        self._d["providers"][pid] = {
            "id":          pid,
            "name":        name,
            "contact":     contact,
            "total_kits":  0,
            "total_cost":  0.0,
            "total_paid":  0.0,
            "outstanding": 0.0,
            "payments":    [],
            "created":     self._now(),
        }
        return pid

    def get_provider(self, prov_id: str) -> Dict:
        return self._d["providers"][prov_id]

    def get_all_providers(self) -> List[Dict]:
        return list(self._d["providers"].values())

    def get_providers_with_outstanding(self) -> List[Dict]:
        return [p for p in self._d["providers"].values() if p["outstanding"] > 0]

    def update_provider_payment(self, prov_id: str, amount: float) -> Dict:
        prov = self._d["providers"][prov_id]
        prov["total_paid"]  = round(prov["total_paid"] + amount, 2)
        prov["outstanding"] = round(prov["total_cost"] - prov["total_paid"], 2)
        prov.setdefault("payments", []).append({
            "amount": amount,
            "date":   self._now(),
        })
        self._save()
        return prov

    # ══════════════════════════════════════════════════════════════════════════
    # KITS
    # ══════════════════════════════════════════════════════════════════════════

    def get_kit(self, kit_no: str) -> Dict:
        return self._d["kits"][kit_no]

    def get_unsold_kits(self) -> List[Dict]:
        return [k for k in self._d["kits"].values() if k["status"] == "unsold"]

    def get_pending_buyer_kits(self) -> List[Dict]:
        return [
            k for k in self._d["kits"].values()
            if k["status"] == "sold" and k["sell_price"] - k["buyer_paid"] > 0.01
        ]

    def get_all_kits(self, filter: str = "all") -> List[Dict]:
        kits = list(self._d["kits"].values())
        if filter == "unsold":
            kits = [k for k in kits if k["status"] == "unsold"]
        elif filter == "sold":
            kits = [k for k in kits if k["status"] == "sold"]
        elif filter in BRANDS:
            kits = [k for k in kits if k["brand"] == filter]
        # Sort by kit_no desc (newest first)
        kits.sort(key=lambda k: int(k["kit_no"]), reverse=True)
        return kits

    def sell_kit(
        self,
        kit_no: str,
        buyer_name: str,
        buyer_contact: str,
        sell_price: float,
        paid_now: float,
    ) -> Dict:
        kit = self._d["kits"][kit_no]
        kit["status"]        = "sold"
        kit["buyer_name"]    = buyer_name
        kit["buyer_contact"] = buyer_contact
        kit["sell_price"]    = round(sell_price, 2)
        kit["buyer_paid"]    = round(paid_now, 2)
        kit["date_sold"]     = self._now()
        self._save()
        return kit

    def update_buyer_payment(self, kit_no: str, amount: float) -> Dict:
        kit = self._d["kits"][kit_no]
        kit["buyer_paid"] = round(kit["buyer_paid"] + amount, 2)
        self._save()
        return kit

    # ══════════════════════════════════════════════════════════════════════════
    # SUMMARY / REPORT
    # ══════════════════════════════════════════════════════════════════════════

    def get_full_summary(self) -> Dict:
        kits      = list(self._d["kits"].values())
        providers = list(self._d["providers"].values())

        sold   = [k for k in kits if k["status"] == "sold"]
        unsold = [k for k in kits if k["status"] == "unsold"]

        total_billed    = sum(k["sell_price"]  for k in sold)
        buyer_received  = sum(k["buyer_paid"]  for k in sold)
        buyer_pending   = total_billed - buyer_received

        total_cost      = sum(p["total_cost"]  for p in providers)
        provider_paid   = sum(p["total_paid"]  for p in providers)
        provider_pending= total_cost - provider_paid

        by_brand = {}
        for brand in BRANDS:
            bkits = [k for k in kits if k["brand"] == brand]
            bsold = [k for k in bkits if k["status"] == "sold"]
            by_brand[brand] = {
                "kits":   len(bkits),
                "billed": sum(k["sell_price"] for k in bsold),
                "cost":   sum(k["cost_price"] for k in bkits),
            }

        return {
            "total_kits":       len(kits),
            "sold":             len(sold),
            "unsold":           len(unsold),
            "total_billed":     round(total_billed, 2),
            "buyer_received":   round(buyer_received, 2),
            "buyer_pending":    round(buyer_pending, 2),
            "total_cost":       round(total_cost, 2),
            "provider_paid":    round(provider_paid, 2),
            "provider_pending": round(provider_pending, 2),
            "by_brand":         by_brand,
        }
