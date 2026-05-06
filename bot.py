#!/usr/bin/env python3
"""
Kit Accounts Manager v3
- Saved providers: LR / AK / KN + NEW PROVIDER
- Saved buyers:    KP + NEW BUYER
- Kit fields:      Account No, Card No, Holder Name
- Date picker:     TODAY / YESTERDAY / 2 DAYS AGO / CUSTOM
- Full button UI, capital bold labels
"""

import logging, os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler,
)
from data_manager import DataManager

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
OWNER_ID  = int(os.getenv("OWNER_ID", "0"))

db = DataManager()

# ── States ─────────────────────────────────────────────────────────────────────
(
    MAIN_MENU,

    # Add kit flow
    AK_PROV_SELECT, AK_PROV_NAME,
    AK_BRAND, AK_ACCOUNT, AK_CARD, AK_HOLDER,
    AK_QTY, AK_PRICE, AK_PAID,
    AK_DATE, AK_DATE_CUSTOM,

    # Sell kit flow
    SK_KIT, SK_BUYER_SELECT, SK_BUYER_NAME,
    SK_PRICE, SK_PAID,
    SK_DATE, SK_DATE_CUSTOM,

    # Update buyer payment
    UBP_KIT, UBP_AMOUNT,

    # Pay provider
    PP_PROV, PP_AMOUNT,

    # View
    VL_FILTER,
) = range(24)

BRANDS = ["BOM", "CBI", "BB", "RBL"]

# ══════════════════════════════════════════════════════════════════════════════
# UI HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def kb(*rows):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t, callback_data=d) for t, d in row]
        for row in rows
    ])

def cancel_kb():
    return kb([("❌ CANCEL", "main")])

def back_kb():
    return kb([("🔙 BACK TO MENU", "main")])

def fmt(n):
    return f"₹{float(n):,.2f}"

def fdate(iso):
    return DataManager.fmt_display_date(iso)

def _auth(u):
    return OWNER_ID == 0 or u.effective_user.id == OWNER_ID

def date_picker_kb(prefix: str):
    """4-option date picker keyboard."""
    return kb(
        [("📅 TODAY",         f"{prefix}_today"),
         ("📅 YESTERDAY",     f"{prefix}_yest")],
        [("📅 2 DAYS AGO",    f"{prefix}_2days"),
         ("✏️ CUSTOM DATE",   f"{prefix}_custom")],
        [("❌ CANCEL",        "main")],
    )

# ══════════════════════════════════════════════════════════════════════════════
# MAIN MENU
# ══════════════════════════════════════════════════════════════════════════════

MAIN_TEXT = (
    "📦 *KIT ACCOUNTS MANAGER*\n"
    "━━━━━━━━━━━━━━━━━━━━━\n"
    "CHOOSE AN OPTION:"
)

def main_kb():
    return kb(
        [("➕ ADD KIT FROM PROVIDER",  "menu_add_kit")],
        [("🛒 SELL KIT TO BUYER",       "menu_sell_kit")],
        [("💰 UPDATE BUYER PAYMENT",    "menu_upd_buyer")],
        [("💸 PAY TO PROVIDER",         "menu_pay_prov")],
        [("📋 VIEW KIT LEDGER",         "menu_ledger")],
        [("👥 VIEW PROVIDERS",          "menu_providers")],
        [("📊 FULL REPORT",             "menu_report")],
    )

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _auth(update):
        await update.message.reply_text("⛔ UNAUTHORIZED.")
        return ConversationHandler.END
    await update.message.reply_text(MAIN_TEXT, parse_mode="Markdown", reply_markup=main_kb())
    return MAIN_MENU

async def go_main(q):
    await q.edit_message_text(MAIN_TEXT, parse_mode="Markdown", reply_markup=main_kb())

async def main_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    d = q.data
    if   d == "main":            await go_main(q); return MAIN_MENU
    elif d == "menu_add_kit":    return await ak_prov_select(q, ctx)
    elif d == "menu_sell_kit":   return await sk_kit_select(q, ctx)
    elif d == "menu_upd_buyer":  return await ubp_start(q, ctx)
    elif d == "menu_pay_prov":   return await pp_start(q, ctx)
    elif d == "menu_ledger":     return await vl_start(q, ctx)
    elif d == "menu_providers":  return await view_providers(q, ctx)
    elif d == "menu_report":     return await full_report(q, ctx)
    return MAIN_MENU

# ══════════════════════════════════════════════════════════════════════════════
# FLOW 1 — ADD KIT FROM PROVIDER
# ══════════════════════════════════════════════════════════════════════════════

async def ak_prov_select(q, ctx):
    providers = db.get_all_providers()
    rows = [
        [(f"🏭 {p['name'].upper()}", f"akp_{p['id']}")]
        for p in providers
    ]
    rows.append([("➕ NEW PROVIDER", "akp_new")])
    rows.append([("❌ CANCEL",       "main")])
    await q.edit_message_text(
        "🏭 *ADD KIT — SELECT PROVIDER:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(rows)
    )
    return AK_PROV_SELECT

async def ak_prov_selected(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if q.data == "main": await go_main(q); return MAIN_MENU

    if q.data == "akp_new":
        await q.edit_message_text(
            "✏️ *NEW PROVIDER — NAME LIKHEIN:*",
            parse_mode="Markdown", reply_markup=cancel_kb()
        )
        return AK_PROV_NAME

    prov_id = q.data.replace("akp_", "")
    ctx.user_data["ak_prov_id"] = prov_id
    prov = db.get_provider(prov_id)
    ctx.user_data["ak_prov_name"] = prov["name"]
    return await _ak_ask_brand(q)

async def ak_prov_name_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    prov = db.add_new_provider(name)
    ctx.user_data["ak_prov_id"]   = prov["id"]
    ctx.user_data["ak_prov_name"] = prov["name"]
    brand_rows = [[InlineKeyboardButton(b, callback_data=f"akb_{b}")] for b in BRANDS]
    brand_rows.append([InlineKeyboardButton("❌ CANCEL", callback_data="main")])
    await update.message.reply_text(
        f"✅ *PROVIDER '{name.upper()}' SAVED!*\n\n🏷️ *BRAND SELECT KAREIN:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(brand_rows)
    )
    return AK_BRAND

async def _ak_ask_brand(q):
    brand_rows = [[InlineKeyboardButton(b, callback_data=f"akb_{b}")] for b in BRANDS]
    brand_rows.append([InlineKeyboardButton("❌ CANCEL", callback_data="main")])
    await q.edit_message_text(
        "🏷️ *BRAND SELECT KAREIN:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(brand_rows)
    )
    return AK_BRAND

async def ak_brand(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if q.data == "main": await go_main(q); return MAIN_MENU
    ctx.user_data["ak_brand"] = q.data.replace("akb_", "")
    await q.edit_message_text(
        "🔢 *ACCOUNT NUMBER LIKHEIN:*", parse_mode="Markdown", reply_markup=cancel_kb()
    )
    return AK_ACCOUNT

async def ak_account(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["ak_account"] = update.message.text.strip()
    await update.message.reply_text(
        "💳 *CARD NUMBER LIKHEIN:*", parse_mode="Markdown", reply_markup=cancel_kb()
    )
    return AK_CARD

async def ak_card(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["ak_card"] = update.message.text.strip()
    await update.message.reply_text(
        "👤 *HOLDER NAME LIKHEIN:*", parse_mode="Markdown", reply_markup=cancel_kb()
    )
    return AK_HOLDER

async def ak_holder(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["ak_holder"] = update.message.text.strip()
    await update.message.reply_text(
        "📦 *QUANTITY — KITNE KITS AAYE?*", parse_mode="Markdown", reply_markup=cancel_kb()
    )
    return AK_QTY

async def ak_qty(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        qty = int(update.message.text.strip()); assert qty > 0
    except Exception:
        await update.message.reply_text("❌ VALID NUMBER LIKHEIN."); return AK_QTY
    ctx.user_data["ak_qty"] = qty
    await update.message.reply_text(
        f"💵 *PER-KIT COST KYA HAI?*\n_(TOTAL {qty} KITS)_",
        parse_mode="Markdown", reply_markup=cancel_kb()
    )
    return AK_PRICE

async def ak_price(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text.strip().replace(",","")); assert price > 0
    except Exception:
        await update.message.reply_text("❌ VALID AMOUNT LIKHEIN."); return AK_PRICE
    ctx.user_data["ak_price"] = price
    qty   = ctx.user_data["ak_qty"]
    total = price * qty
    await update.message.reply_text(
        f"💸 *PROVIDER KO ABHI KITNA PAID KIYA?*\n"
        f"_(TOTAL DUE: {fmt(total)} FOR {qty} KITS)_\n"
        f"_(0 LIKHEIN AGAR ABHI NAHI DIYA)_",
        parse_mode="Markdown", reply_markup=cancel_kb()
    )
    return AK_PAID

async def ak_paid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        paid = float(update.message.text.strip().replace(",","")); assert paid >= 0
    except Exception:
        await update.message.reply_text("❌ VALID AMOUNT LIKHEIN."); return AK_PAID
    ctx.user_data["ak_paid"] = paid
    await update.message.reply_text(
        "📅 *KIT AANE KI DATE SELECT KAREIN:*",
        parse_mode="Markdown",
        reply_markup=date_picker_kb("akd")
    )
    return AK_DATE

async def ak_date(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if q.data == "main": await go_main(q); return MAIN_MENU

    if   q.data == "akd_today":  ctx.user_data["ak_date"] = DataManager.date_today();      return await _ak_finish(q.message, ctx)
    elif q.data == "akd_yest":   ctx.user_data["ak_date"] = DataManager.date_yesterday();  return await _ak_finish(q.message, ctx)
    elif q.data == "akd_2days":  ctx.user_data["ak_date"] = DataManager.date_2days_ago();  return await _ak_finish(q.message, ctx)
    elif q.data == "akd_custom":
        await q.edit_message_text(
            "✏️ *CUSTOM DATE LIKHEIN (DD/MM/YYYY):*",
            parse_mode="Markdown", reply_markup=cancel_kb()
        )
        return AK_DATE_CUSTOM
    return AK_DATE

async def ak_date_custom(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    iso = DataManager.parse_custom_date(update.message.text)
    if not iso:
        await update.message.reply_text("❌ FORMAT GALAT HAI. DD/MM/YYYY LIKHEIN (E.G. 04/05/2025).")
        return AK_DATE_CUSTOM
    ctx.user_data["ak_date"] = iso
    return await _ak_finish(update.message, ctx)

async def _ak_finish(msg, ctx):
    u = ctx.user_data
    qty   = u["ak_qty"]
    price = u["ak_price"]
    total = price * qty
    paid  = u["ak_paid"]

    kits = db.add_provider_kits(
        provider_id  = u["ak_prov_id"],
        brand        = u["ak_brand"],
        account_no   = u["ak_account"],
        card_no      = u["ak_card"],
        holder_name  = u["ak_holder"],
        qty          = qty,
        cost_per_kit = price,
        paid_now     = paid,
        kit_date     = u["ak_date"],
    )

    kit_lines = "\n".join([
        f"  • *#{k['kit_no']}* | {k['brand']} | HOLDER: {k['holder_name'].upper()}\n"
        f"    ACC: `{k['account_no']}` | CARD: `{k['card_no']}`"
        for k in kits
    ])

    await msg.reply_text(
        f"✅ *{qty} KIT(S) ADDED!*\n\n"
        f"🏭 PROVIDER: *{u['ak_prov_name'].upper()}*\n"
        f"📅 DATE: {fdate(u['ak_date'])}\n"
        f"💵 COST: {fmt(price)} × {qty} = *{fmt(total)}*\n"
        f"✅ PAID: {fmt(paid)}   |   🔴 PENDING: {fmt(total - paid)}\n\n"
        f"🎫 *KITS ASSIGNED:*\n{kit_lines}",
        parse_mode="Markdown", reply_markup=main_kb()
    )
    return MAIN_MENU

# ══════════════════════════════════════════════════════════════════════════════
# FLOW 2 — SELL KIT TO BUYER
# ══════════════════════════════════════════════════════════════════════════════

async def sk_kit_select(q, ctx):
    unsold = db.get_unsold_kits()
    if not unsold:
        await q.edit_message_text(
            "⚠️ *KOI UNSOLD KIT AVAILABLE NAHI.*\nPEHLE PROVIDER SE KIT ADD KAREIN.",
            parse_mode="Markdown", reply_markup=back_kb()
        )
        return MAIN_MENU
    rows = [
        [(f"#{k['kit_no']} | {k['brand']} | {k['holder_name'].upper()} | ACC:...{k['account_no'][-4:]}",
          f"sk_{k['kit_no']}")]
        for k in unsold
    ]
    rows.append([("❌ CANCEL", "main")])
    await q.edit_message_text(
        "🛒 *SELL KIT — KIT SELECT KAREIN:*",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(rows)
    )
    return SK_KIT

async def sk_kit(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if q.data == "main": await go_main(q); return MAIN_MENU
    kit_no = q.data.replace("sk_", "")
    kit    = db.get_kit(kit_no)
    ctx.user_data["sk_kit_no"] = kit_no
    ctx.user_data["sk_kit"]    = kit

    buyers = db.get_all_buyers()
    rows   = [[(f"👤 {b['name'].upper()}", f"skb_{b['id']}")] for b in buyers]
    rows.append([("➕ NEW BUYER", "skb_new")])
    rows.append([("❌ CANCEL",    "main")])
    await q.edit_message_text(
        f"🛒 KIT *#{kit_no}* — {kit['brand']}\n"
        f"HOLDER: {kit['holder_name'].upper()}\n"
        f"ACC: `{kit['account_no']}`\n\n"
        f"👤 *BUYER SELECT KAREIN:*",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(rows)
    )
    return SK_BUYER_SELECT

async def sk_buyer_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if q.data == "main": await go_main(q); return MAIN_MENU

    if q.data == "skb_new":
        await q.edit_message_text(
            "✏️ *NEW BUYER — NAAM LIKHEIN:*",
            parse_mode="Markdown", reply_markup=cancel_kb()
        )
        return SK_BUYER_NAME

    buyer_id = q.data.replace("skb_", "")
    buyer    = db.get_buyer(buyer_id)
    ctx.user_data["sk_buyer_id"]      = buyer_id
    ctx.user_data["sk_buyer_name"]    = buyer["name"]
    ctx.user_data["sk_buyer_contact"] = buyer.get("contact", "")
    await q.edit_message_text(
        f"✅ BUYER: *{buyer['name'].upper()}*\n\n💵 *SELLING PRICE KYA HAI?*",
        parse_mode="Markdown", reply_markup=cancel_kb()
    )
    return SK_PRICE

async def sk_buyer_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    name  = update.message.text.strip()
    buyer = db.add_new_buyer(name)
    ctx.user_data["sk_buyer_id"]      = buyer["id"]
    ctx.user_data["sk_buyer_name"]    = buyer["name"]
    ctx.user_data["sk_buyer_contact"] = ""
    await update.message.reply_text(
        f"✅ *BUYER '{name.upper()}' SAVED!*\n\n💵 *SELLING PRICE KYA HAI?*",
        parse_mode="Markdown", reply_markup=cancel_kb()
    )
    return SK_PRICE

async def sk_price(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text.strip().replace(",","")); assert price > 0
    except Exception:
        await update.message.reply_text("❌ VALID AMOUNT LIKHEIN."); return SK_PRICE
    ctx.user_data["sk_price"] = price
    await update.message.reply_text(
        f"💸 *ABHI KITNA PAYMENT MILA BUYER SE?*\n_(TOTAL: {fmt(price)})_\n_(0 LIKHEIN AGAR ABHI NAHI MILA)_",
        parse_mode="Markdown", reply_markup=cancel_kb()
    )
    return SK_PAID

async def sk_paid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        paid = float(update.message.text.strip().replace(",","")); assert paid >= 0
    except Exception:
        await update.message.reply_text("❌ VALID AMOUNT LIKHEIN."); return SK_PAID
    ctx.user_data["sk_paid"] = paid
    await update.message.reply_text(
        "📅 *SALE KI DATE SELECT KAREIN:*",
        parse_mode="Markdown", reply_markup=date_picker_kb("skd")
    )
    return SK_DATE

async def sk_date(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if q.data == "main": await go_main(q); return MAIN_MENU

    if   q.data == "skd_today":  ctx.user_data["sk_date"] = DataManager.date_today();      return await _sk_finish(q.message, ctx)
    elif q.data == "skd_yest":   ctx.user_data["sk_date"] = DataManager.date_yesterday();  return await _sk_finish(q.message, ctx)
    elif q.data == "skd_2days":  ctx.user_data["sk_date"] = DataManager.date_2days_ago();  return await _sk_finish(q.message, ctx)
    elif q.data == "skd_custom":
        await q.edit_message_text(
            "✏️ *CUSTOM DATE LIKHEIN (DD/MM/YYYY):*",
            parse_mode="Markdown", reply_markup=cancel_kb()
        )
        return SK_DATE_CUSTOM
    return SK_DATE

async def sk_date_custom(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    iso = DataManager.parse_custom_date(update.message.text)
    if not iso:
        await update.message.reply_text("❌ FORMAT GALAT HAI. DD/MM/YYYY LIKHEIN."); return SK_DATE_CUSTOM
    ctx.user_data["sk_date"] = iso
    return await _sk_finish(update.message, ctx)

async def _sk_finish(msg, ctx):
    u      = ctx.user_data
    kit_no = u["sk_kit_no"]
    kit    = u["sk_kit"]
    price  = u["sk_price"]
    paid   = u["sk_paid"]

    db.sell_kit(
        kit_no        = kit_no,
        buyer_id      = u["sk_buyer_id"],
        buyer_name    = u["sk_buyer_name"],
        buyer_contact = u["sk_buyer_contact"],
        sell_price    = price,
        paid_now      = paid,
        date_sold     = u["sk_date"],
    )
    pending = price - paid
    await msg.reply_text(
        f"✅ *KIT #{kit_no} SOLD!*\n\n"
        f"🏷️ BRAND: {kit['brand']}\n"
        f"👤 HOLDER: {kit['holder_name'].upper()}\n"
        f"🔢 ACC: `{kit['account_no']}` | 💳 CARD: `{kit['card_no']}`\n"
        f"🛒 BUYER: *{u['sk_buyer_name'].upper()}*\n"
        f"📅 DATE: {fdate(u['sk_date'])}\n"
        f"💵 SELL PRICE: {fmt(price)}\n"
        f"✅ RECEIVED: {fmt(paid)}   |   🔴 PENDING: {fmt(pending)}",
        parse_mode="Markdown", reply_markup=main_kb()
    )
    return MAIN_MENU

# ══════════════════════════════════════════════════════════════════════════════
# FLOW 3 — UPDATE BUYER PAYMENT
# ══════════════════════════════════════════════════════════════════════════════

async def ubp_start(q, ctx):
    kits = db.get_pending_buyer_kits()
    if not kits:
        await q.edit_message_text("✅ *KOI BUYER PAYMENT PENDING NAHI!*", parse_mode="Markdown", reply_markup=back_kb())
        return MAIN_MENU
    rows = [
        [(f"#{k['kit_no']} | {k['buyer_name'].upper()} | DUE: {fmt(k['sell_price']-k['buyer_paid'])}",
          f"ubp_{k['kit_no']}")]
        for k in kits
    ]
    rows.append([("❌ CANCEL", "main")])
    await q.edit_message_text(
        "💰 *UPDATE BUYER PAYMENT — KIT SELECT KAREIN:*",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(rows)
    )
    return UBP_KIT

async def ubp_kit(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if q.data == "main": await go_main(q); return MAIN_MENU
    kit_no = q.data.replace("ubp_", "")
    kit    = db.get_kit(kit_no)
    ctx.user_data["ubp_kit_no"] = kit_no
    pending = kit["sell_price"] - kit["buyer_paid"]
    await q.edit_message_text(
        f"💰 *KIT #{kit_no} — {kit['buyer_name'].upper()}*\n"
        f"TOTAL: {fmt(kit['sell_price'])} | PAID: {fmt(kit['buyer_paid'])} | PENDING: {fmt(pending)}\n\n"
        f"KITNA PAYMENT AAYA?",
        parse_mode="Markdown", reply_markup=cancel_kb()
    )
    return UBP_AMOUNT

async def ubp_amount(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        amt = float(update.message.text.strip().replace(",","")); assert amt > 0
    except Exception:
        await update.message.reply_text("❌ VALID AMOUNT LIKHEIN."); return UBP_AMOUNT
    kit_no = ctx.user_data["ubp_kit_no"]
    kit    = db.update_buyer_payment(kit_no, amt)
    rem    = kit["sell_price"] - kit["buyer_paid"]
    status = "✅ *FULLY PAID!*" if rem <= 0.009 else f"🔴 STILL PENDING: {fmt(rem)}"
    await update.message.reply_text(
        f"✅ *PAYMENT UPDATED — KIT #{kit_no}*\n"
        f"👤 {kit['buyer_name'].upper()}\n"
        f"💵 ADDED: {fmt(amt)}\n"
        f"TOTAL PAID: {fmt(kit['buyer_paid'])} / {fmt(kit['sell_price'])}\n"
        f"{status}",
        parse_mode="Markdown", reply_markup=main_kb()
    )
    return MAIN_MENU

# ══════════════════════════════════════════════════════════════════════════════
# FLOW 4 — PAY TO PROVIDER
# ══════════════════════════════════════════════════════════════════════════════

async def pp_start(q, ctx):
    provs = db.get_providers_with_outstanding()
    if not provs:
        await q.edit_message_text("✅ *KISI PROVIDER KA OUTSTANDING NAHI!*", parse_mode="Markdown", reply_markup=back_kb())
        return MAIN_MENU
    rows = [
        [(f"🏭 {p['name'].upper()} | PENDING: {fmt(p['outstanding'])}", f"pp_{p['id']}")]
        for p in provs
    ]
    rows.append([("❌ CANCEL", "main")])
    await q.edit_message_text(
        "💸 *PAY TO PROVIDER — SELECT KAREIN:*",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(rows)
    )
    return PP_PROV

async def pp_prov(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if q.data == "main": await go_main(q); return MAIN_MENU
    prov_id = q.data.replace("pp_", "")
    prov    = db.get_provider(prov_id)
    ctx.user_data["pp_prov_id"] = prov_id
    await q.edit_message_text(
        f"💸 *{prov['name'].upper()}*\n"
        f"TOTAL: {fmt(prov['total_cost'])} | PAID: {fmt(prov['total_paid'])} | PENDING: {fmt(prov['outstanding'])}\n\n"
        f"KITNA PAYMENT KARNA HAI?",
        parse_mode="Markdown", reply_markup=cancel_kb()
    )
    return PP_AMOUNT

async def pp_amount(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        amt = float(update.message.text.strip().replace(",","")); assert amt > 0
    except Exception:
        await update.message.reply_text("❌ VALID AMOUNT LIKHEIN."); return PP_AMOUNT
    prov_id = ctx.user_data["pp_prov_id"]
    prov    = db.update_provider_payment(prov_id, amt)
    rem     = prov["outstanding"]
    status  = "✅ *FULLY PAID!*" if rem <= 0.009 else f"🔴 STILL PENDING: {fmt(rem)}"
    await update.message.reply_text(
        f"✅ *PAYMENT DONE TO {prov['name'].upper()}*\n"
        f"💵 PAID NOW: {fmt(amt)}\n"
        f"TOTAL PAID: {fmt(prov['total_paid'])} / {fmt(prov['total_cost'])}\n"
        f"{status}",
        parse_mode="Markdown", reply_markup=main_kb()
    )
    return MAIN_MENU

# ══════════════════════════════════════════════════════════════════════════════
# VIEW — KIT LEDGER
# ══════════════════════════════════════════════════════════════════════════════

async def vl_start(q, ctx):
    await q.edit_message_text(
        "📋 *KIT LEDGER — FILTER SELECT KAREIN:*",
        parse_mode="Markdown",
        reply_markup=kb(
            [("📋 ALL",    "lf_all"),   ("🔵 UNSOLD", "lf_unsold"), ("🟢 SOLD",  "lf_sold")],
            [("BOM",       "lf_BOM"),   ("CBI",       "lf_CBI"),    ("BB",       "lf_BB"), ("RBL", "lf_RBL")],
            [("🔙 BACK TO MENU", "main")],
        )
    )
    return VL_FILTER

async def vl_filter(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if q.data == "main": await go_main(q); return MAIN_MENU
    flt  = q.data.replace("lf_", "")
    kits = db.get_all_kits(filter=flt)

    if not kits:
        await q.edit_message_text(f"⚠️ '{flt.upper()}' MEIN KOI KIT NAHI MILI.", reply_markup=back_kb())
        return MAIN_MENU

    lines = [f"📋 *KIT LEDGER — {flt.upper()}* ({len(kits)} KITS)\n"]
    for k in kits:
        icon = "🟢" if k["status"] == "sold" else "🔵"
        line = (
            f"{icon} *#{k['kit_no']}* | {k['brand']} | {k['holder_name'].upper()}\n"
            f"  📂 ACC: `{k['account_no']}` | 💳 CARD: `{k['card_no']}`\n"
            f"  🏭 PROVIDER: {k['provider_name'].upper()} | 📅 {fdate(k['date_added'])}"
        )
        if k["status"] == "sold":
            pending = k["sell_price"] - k["buyer_paid"]
            pay_st  = "✅ CLEAR" if pending <= 0.009 else f"🔴 DUE: {fmt(pending)}"
            line += (
                f"\n  🛒 BUYER: {k['buyer_name'].upper()}"
                f"\n  💵 PRICE: {fmt(k['sell_price'])} | PAID: {fmt(k['buyer_paid'])} | {pay_st}"
                f"\n  📅 SOLD: {fdate(k['date_sold'])}"
            )
        lines.append(line)

    text = "\n\n".join(lines)
    if len(text) > 3900:
        text = text[:3900] + "\n\n_(... AAGE AUR RECORDS HAIN — FILTER KARKE DEKHEIN)_"

    await q.edit_message_text(text, parse_mode="Markdown", reply_markup=back_kb())
    return MAIN_MENU

# ══════════════════════════════════════════════════════════════════════════════
# VIEW — PROVIDERS
# ══════════════════════════════════════════════════════════════════════════════

async def view_providers(q, ctx):
    provs = db.get_all_providers()
    if not provs:
        await q.edit_message_text("👥 KOI PROVIDER RECORD NAHI HAI.", reply_markup=back_kb())
        return MAIN_MENU
    lines = [f"👥 *PROVIDERS ({len(provs)})*\n"]
    for p in provs:
        lines.append(
            f"🏭 *{p['name'].upper()}*\n"
            f"  KITS: {p['total_kits']} | COST: {fmt(p['total_cost'])}\n"
            f"  ✅ PAID: {fmt(p['total_paid'])} | 🔴 PENDING: {fmt(p['outstanding'])}"
        )
    await q.edit_message_text("\n\n".join(lines), parse_mode="Markdown", reply_markup=back_kb())
    return MAIN_MENU

# ══════════════════════════════════════════════════════════════════════════════
# FULL REPORT
# ══════════════════════════════════════════════════════════════════════════════

async def full_report(q, ctx):
    s = db.get_full_summary()
    lines = [
        "📊 *FULL BUSINESS REPORT*\n",
        f"📦 TOTAL KITS: {s['total_kits']}  |  🔵 UNSOLD: {s['unsold']}  |  🟢 SOLD: {s['sold']}",
        "",
        "💵 *REVENUE (BUYERS)*",
        f"  BILLED:    {fmt(s['total_billed'])}",
        f"  RECEIVED:  {fmt(s['buyer_received'])}",
        f"  🔴 PENDING: {fmt(s['buyer_pending'])}",
        "",
        "💸 *COST (PROVIDERS)*",
        f"  TOTAL COST: {fmt(s['total_cost'])}",
        f"  PAID:       {fmt(s['provider_paid'])}",
        f"  🔴 PENDING: {fmt(s['provider_pending'])}",
        "",
        "🏦 *NET*",
        f"  CASH IN HAND: {fmt(s['buyer_received'] - s['provider_paid'])}",
        f"  PROJECTED:    {fmt(s['total_billed'] - s['total_cost'])}",
        "",
        "─── *BRAND-WISE* ───",
    ]
    for brand, bs in s["by_brand"].items():
        lines.append(
            f"*{brand}*: {bs['kits']} KITS | BILLED {fmt(bs['billed'])} | COST {fmt(bs['cost'])}"
        )
    await q.edit_message_text("\n".join(lines), parse_mode="Markdown", reply_markup=back_kb())
    return MAIN_MENU

# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start), CommandHandler("menu", start)],
        states={
            MAIN_MENU:       [CallbackQueryHandler(main_handler)],
            AK_PROV_SELECT:  [CallbackQueryHandler(ak_prov_selected)],
            AK_PROV_NAME:    [MessageHandler(filters.TEXT & ~filters.COMMAND, ak_prov_name_text)],
            AK_BRAND:        [CallbackQueryHandler(ak_brand)],
            AK_ACCOUNT:      [MessageHandler(filters.TEXT & ~filters.COMMAND, ak_account)],
            AK_CARD:         [MessageHandler(filters.TEXT & ~filters.COMMAND, ak_card)],
            AK_HOLDER:       [MessageHandler(filters.TEXT & ~filters.COMMAND, ak_holder)],
            AK_QTY:          [MessageHandler(filters.TEXT & ~filters.COMMAND, ak_qty)],
            AK_PRICE:        [MessageHandler(filters.TEXT & ~filters.COMMAND, ak_price)],
            AK_PAID:         [MessageHandler(filters.TEXT & ~filters.COMMAND, ak_paid)],
            AK_DATE:         [CallbackQueryHandler(ak_date)],
            AK_DATE_CUSTOM:  [MessageHandler(filters.TEXT & ~filters.COMMAND, ak_date_custom)],
            SK_KIT:          [CallbackQueryHandler(sk_kit)],
            SK_BUYER_SELECT: [CallbackQueryHandler(sk_buyer_select)],
            SK_BUYER_NAME:   [MessageHandler(filters.TEXT & ~filters.COMMAND, sk_buyer_name)],
            SK_PRICE:        [MessageHandler(filters.TEXT & ~filters.COMMAND, sk_price)],
            SK_PAID:         [MessageHandler(filters.TEXT & ~filters.COMMAND, sk_paid)],
            SK_DATE:         [CallbackQueryHandler(sk_date)],
            SK_DATE_CUSTOM:  [MessageHandler(filters.TEXT & ~filters.COMMAND, sk_date_custom)],
            UBP_KIT:         [CallbackQueryHandler(ubp_kit)],
            UBP_AMOUNT:      [MessageHandler(filters.TEXT & ~filters.COMMAND, ubp_amount)],
            PP_PROV:         [CallbackQueryHandler(pp_prov)],
            PP_AMOUNT:       [MessageHandler(filters.TEXT & ~filters.COMMAND, pp_amount)],
            VL_FILTER:       [CallbackQueryHandler(vl_filter)],
        },
        fallbacks=[CommandHandler("start", start), CommandHandler("menu", start)],
        allow_reentry=True,
        per_message=False,
    )

    app.add_handler(conv)
    logger.info("✅ BOT STARTED!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
