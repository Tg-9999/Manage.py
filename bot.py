#!/usr/bin/env python3
"""
Kit Accounts Manager — Full Button System
Tracks: Providers, Kits (auto-numbered), Buyers, Payments (both ways)
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

# ── Conversation states ────────────────────────────────────────────────────────
(
    MAIN_MENU,
    PROV_NAME, PROV_CONTACT, PROV_BRAND, PROV_ACCOUNT, PROV_CARD,
    PROV_KIT_QTY, PROV_KIT_PRICE, PROV_PAID_NOW,
    BUY_KIT_SELECT, BUY_NAME, BUY_CONTACT, BUY_PRICE, BUY_PAID_NOW,
    UPD_SELECT_KIT, UPD_AMOUNT,
    PROV_PAY_SELECT, PROV_PAY_AMOUNT,
    VIEW_KIT_DETAIL,
) = range(19)

BRANDS = ["BOM", "CBI", "BB", "RBL"]

# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def kb(*rows):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t, callback_data=d) for t, d in row]
        for row in rows
    ])

def cancel_kb():
    return kb([("❌ Cancel", "main")])

def back_kb():
    return kb([("🔙 Back to Menu", "main")])

def fmt(amount):
    return f"₹{float(amount):,.2f}"

def _auth(update):
    return OWNER_ID == 0 or update.effective_user.id == OWNER_ID

# ══════════════════════════════════════════════════════════════════════════════
# MAIN MENU
# ══════════════════════════════════════════════════════════════════════════════

MAIN_TEXT = (
    "📦 *Kit Accounts Manager*\n"
    "━━━━━━━━━━━━━━━━━━━━━\n"
    "Choose an option:"
)

def main_menu_kb():
    return kb(
        [("➕ Add Kit from Provider",  "menu_add_provider")],
        [("🛒 Sell Kit to Buyer",       "menu_sell_kit")],
        [("💰 Update Buyer Payment",    "menu_upd_buyer")],
        [("💸 Pay to Provider",         "menu_pay_provider")],
        [("📋 View Kit Ledger",         "menu_view_ledger")],
        [("👥 View Providers",          "menu_view_providers")],
        [("📊 Full Report",             "menu_report")],
    )

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _auth(update):
        await update.message.reply_text("⛔ Unauthorized.")
        return ConversationHandler.END
    await update.message.reply_text(
        MAIN_TEXT, parse_mode="Markdown", reply_markup=main_menu_kb()
    )
    return MAIN_MENU

async def main_menu_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data

    if d == "main":
        await q.edit_message_text(MAIN_TEXT, parse_mode="Markdown", reply_markup=main_menu_kb())
        return MAIN_MENU
    elif d == "menu_add_provider":
        ctx.user_data.clear()
        await q.edit_message_text(
            "🏭 *Add Kit from Provider*\n\nProvider ka naam likhein:",
            parse_mode="Markdown", reply_markup=cancel_kb()
        )
        return PROV_NAME
    elif d == "menu_sell_kit":
        return await sell_kit_start(q, ctx)
    elif d == "menu_upd_buyer":
        return await upd_buyer_start(q, ctx)
    elif d == "menu_pay_provider":
        return await pay_provider_start(q, ctx)
    elif d == "menu_view_ledger":
        return await view_ledger(q, ctx)
    elif d == "menu_view_providers":
        return await view_providers(q, ctx)
    elif d == "menu_report":
        return await full_report(q, ctx)

    return MAIN_MENU

# ══════════════════════════════════════════════════════════════════════════════
# FLOW 1 — ADD KIT FROM PROVIDER
# ══════════════════════════════════════════════════════════════════════════════

async def prov_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["prov_name"] = update.message.text.strip()
    await update.message.reply_text("📞 Provider ka contact number:", reply_markup=cancel_kb())
    return PROV_CONTACT

async def prov_contact(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["prov_contact"] = update.message.text.strip()
    brand_buttons = [[InlineKeyboardButton(b, callback_data=f"pb_{b}")] for b in BRANDS]
    brand_buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="main")])
    await update.message.reply_text(
        "🏷️ Kit ka brand select karein:",
        reply_markup=InlineKeyboardMarkup(brand_buttons)
    )
    return PROV_BRAND

async def prov_brand(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "main":
        await q.edit_message_text(MAIN_TEXT, parse_mode="Markdown", reply_markup=main_menu_kb())
        return MAIN_MENU
    ctx.user_data["prov_brand"] = q.data.replace("pb_", "")
    await q.edit_message_text(
        "🔢 Kit ka *Account Number* likhein:", parse_mode="Markdown", reply_markup=cancel_kb()
    )
    return PROV_ACCOUNT

async def prov_account(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["prov_account"] = update.message.text.strip()
    await update.message.reply_text("💳 Kit ka *Card Number* likhein:", parse_mode="Markdown",
                                    reply_markup=cancel_kb())
    return PROV_CARD

async def prov_card(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["prov_card"] = update.message.text.strip()
    await update.message.reply_text("📦 Kitne kits aaye? (quantity):", reply_markup=cancel_kb())
    return PROV_KIT_QTY

async def prov_kit_qty(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        qty = int(update.message.text.strip())
        assert qty > 0
    except Exception:
        await update.message.reply_text("❌ Valid number likhein (e.g. 1, 5, 10).")
        return PROV_KIT_QTY
    ctx.user_data["prov_qty"] = qty
    await update.message.reply_text(
        f"💵 Provider ko per-kit cost kya hai?\n_(Total {qty} kits)_",
        parse_mode="Markdown", reply_markup=cancel_kb()
    )
    return PROV_KIT_PRICE

async def prov_kit_price(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text.strip().replace(",", ""))
        assert price > 0
    except Exception:
        await update.message.reply_text("❌ Valid amount likhein.")
        return PROV_KIT_PRICE
    ctx.user_data["prov_price"] = price
    qty = ctx.user_data["prov_qty"]
    total = price * qty
    await update.message.reply_text(
        f"💸 Abhi kitna payment diya provider ko?\n"
        f"_(Total due: {fmt(total)} for {qty} kits)_\n"
        f"_(0 likhein agar abhi nahi diya)_",
        parse_mode="Markdown", reply_markup=cancel_kb()
    )
    return PROV_PAID_NOW

async def prov_paid_now(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        paid = float(update.message.text.strip().replace(",", ""))
        assert paid >= 0
    except Exception:
        await update.message.reply_text("❌ Valid amount likhein (0 bhi chalega).")
        return PROV_PAID_NOW

    u = ctx.user_data
    qty   = u["prov_qty"]
    price = u["prov_price"]
    total = price * qty

    kits = db.add_provider_kits(
        provider_name    = u["prov_name"],
        provider_contact = u["prov_contact"],
        brand            = u["prov_brand"],
        account_no       = u["prov_account"],
        card_no          = u["prov_card"],
        qty              = qty,
        cost_per_kit     = price,
        paid_now         = paid,
    )

    kit_list = "\n".join([
        f"  • Kit *#{k['kit_no']}* — {k['brand']} | Acc: `{k['account_no']}` | Card: `{k['card_no']}`"
        for k in kits
    ])

    await update.message.reply_text(
        f"✅ *{qty} Kit(s) Added!*\n\n"
        f"👤 Provider: {u['prov_name']} ({u['prov_contact']})\n"
        f"💵 Cost: {fmt(price)} × {qty} = {fmt(total)}\n"
        f"✅ Paid: {fmt(paid)}   |   🔴 Pending: {fmt(total - paid)}\n\n"
        f"🎫 *Kits Assigned:*\n{kit_list}",
        parse_mode="Markdown", reply_markup=main_menu_kb()
    )
    return MAIN_MENU

# ══════════════════════════════════════════════════════════════════════════════
# FLOW 2 — SELL KIT TO BUYER
# ══════════════════════════════════════════════════════════════════════════════

async def sell_kit_start(q, ctx):
    unsold = db.get_unsold_kits()
    if not unsold:
        await q.edit_message_text(
            "⚠️ Koi unsold kit available nahi.\nPehle provider se kit add karein.",
            reply_markup=back_kb()
        )
        return MAIN_MENU
    buttons = [
        [InlineKeyboardButton(
            f"#{k['kit_no']} | {k['brand']} | Acc:...{k['account_no'][-4:]}",
            callback_data=f"sk_{k['kit_no']}"
        )]
        for k in unsold
    ]
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="main")])
    await q.edit_message_text(
        "🛒 *Sell Kit — Kit Select Karein:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    return BUY_KIT_SELECT

async def buy_kit_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "main":
        await q.edit_message_text(MAIN_TEXT, parse_mode="Markdown", reply_markup=main_menu_kb())
        return MAIN_MENU
    kit_no = q.data.replace("sk_", "")
    kit = db.get_kit(kit_no)
    ctx.user_data["sell_kit_no"] = kit_no
    ctx.user_data["sell_kit"] = kit
    await q.edit_message_text(
        f"🛒 Kit *#{kit_no}* ({kit['brand']})\n"
        f"Acc: `{kit['account_no']}` | Card: `{kit['card_no']}`\n\n"
        f"👤 Buyer ka naam likhein:",
        parse_mode="Markdown", reply_markup=cancel_kb()
    )
    return BUY_NAME

async def buy_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["buy_name"] = update.message.text.strip()
    await update.message.reply_text("📞 Buyer ka contact number:", reply_markup=cancel_kb())
    return BUY_CONTACT

async def buy_contact(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["buy_contact"] = update.message.text.strip()
    await update.message.reply_text("💵 Selling price kya hai?", reply_markup=cancel_kb())
    return BUY_PRICE

async def buy_price(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text.strip().replace(",", ""))
        assert price > 0
    except Exception:
        await update.message.reply_text("❌ Valid amount likhein.")
        return BUY_PRICE
    ctx.user_data["buy_price"] = price
    await update.message.reply_text(
        f"💸 Abhi kitna payment mila buyer se?\n_(Total: {fmt(price)})_\n_(0 likhein agar abhi nahi mila)_",
        parse_mode="Markdown", reply_markup=cancel_kb()
    )
    return BUY_PAID_NOW

async def buy_paid_now(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        paid = float(update.message.text.strip().replace(",", ""))
        assert paid >= 0
    except Exception:
        await update.message.reply_text("❌ Valid amount likhein.")
        return BUY_PAID_NOW

    u = ctx.user_data
    db.sell_kit(
        kit_no        = u["sell_kit_no"],
        buyer_name    = u["buy_name"],
        buyer_contact = u["buy_contact"],
        sell_price    = u["buy_price"],
        paid_now      = paid,
    )
    pending = u["buy_price"] - paid
    await update.message.reply_text(
        f"✅ *Kit #{u['sell_kit_no']} Sold!*\n\n"
        f"👤 Buyer: {u['buy_name']} ({u['buy_contact']})\n"
        f"🏷️ Brand: {u['sell_kit']['brand']}\n"
        f"🔢 Acc: `{u['sell_kit']['account_no']}` | 💳 Card: `{u['sell_kit']['card_no']}`\n"
        f"💵 Sell Price: {fmt(u['buy_price'])}\n"
        f"✅ Received: {fmt(paid)}   |   🔴 Pending: {fmt(pending)}",
        parse_mode="Markdown", reply_markup=main_menu_kb()
    )
    return MAIN_MENU

# ══════════════════════════════════════════════════════════════════════════════
# FLOW 3 — UPDATE BUYER PAYMENT
# ══════════════════════════════════════════════════════════════════════════════

async def upd_buyer_start(q, ctx):
    pending_kits = db.get_pending_buyer_kits()
    if not pending_kits:
        await q.edit_message_text("✅ Koi buyer payment pending nahi!", reply_markup=back_kb())
        return MAIN_MENU
    buttons = [
        [InlineKeyboardButton(
            f"#{k['kit_no']} | {k['buyer_name']} | Due: {fmt(k['sell_price'] - k['buyer_paid'])}",
            callback_data=f"upd_{k['kit_no']}"
        )]
        for k in pending_kits
    ]
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="main")])
    await q.edit_message_text(
        "💰 *Update Buyer Payment — Kit Select Karein:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    return UPD_SELECT_KIT

async def upd_select_kit(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "main":
        await q.edit_message_text(MAIN_TEXT, parse_mode="Markdown", reply_markup=main_menu_kb())
        return MAIN_MENU
    kit_no = q.data.replace("upd_", "")
    kit = db.get_kit(kit_no)
    ctx.user_data["upd_kit_no"] = kit_no
    pending = kit["sell_price"] - kit["buyer_paid"]
    await q.edit_message_text(
        f"💰 *Kit #{kit_no} — {kit['buyer_name']}*\n"
        f"Total: {fmt(kit['sell_price'])} | Paid: {fmt(kit['buyer_paid'])} | Pending: {fmt(pending)}\n\n"
        f"Kitna payment aaya abhi?",
        parse_mode="Markdown", reply_markup=cancel_kb()
    )
    return UPD_AMOUNT

async def upd_amount(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        amt = float(update.message.text.strip().replace(",", ""))
        assert amt > 0
    except Exception:
        await update.message.reply_text("❌ Valid amount likhein.")
        return UPD_AMOUNT

    kit_no = ctx.user_data["upd_kit_no"]
    kit    = db.update_buyer_payment(kit_no, amt)
    remaining = kit["sell_price"] - kit["buyer_paid"]
    status = "✅ *FULLY PAID!*" if remaining <= 0 else f"🔴 Still Pending: {fmt(remaining)}"

    await update.message.reply_text(
        f"✅ *Payment Updated — Kit #{kit_no}*\n"
        f"👤 {kit['buyer_name']}\n"
        f"💵 Added: {fmt(amt)}\n"
        f"Total Paid: {fmt(kit['buyer_paid'])} / {fmt(kit['sell_price'])}\n"
        f"{status}",
        parse_mode="Markdown", reply_markup=main_menu_kb()
    )
    return MAIN_MENU

# ══════════════════════════════════════════════════════════════════════════════
# FLOW 4 — PAY TO PROVIDER
# ══════════════════════════════════════════════════════════════════════════════

async def pay_provider_start(q, ctx):
    providers = db.get_providers_with_outstanding()
    if not providers:
        await q.edit_message_text("✅ Kisi bhi provider ka outstanding nahi!", reply_markup=back_kb())
        return MAIN_MENU
    buttons = [
        [InlineKeyboardButton(
            f"{p['name']} | Pending: {fmt(p['outstanding'])}",
            callback_data=f"pp_{p['id']}"
        )]
        for p in providers
    ]
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="main")])
    await q.edit_message_text(
        "💸 *Pay to Provider — Select Karein:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    return PROV_PAY_SELECT

async def prov_pay_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "main":
        await q.edit_message_text(MAIN_TEXT, parse_mode="Markdown", reply_markup=main_menu_kb())
        return MAIN_MENU
    prov_id = q.data.replace("pp_", "")
    prov = db.get_provider(prov_id)
    ctx.user_data["pay_prov_id"] = prov_id
    await q.edit_message_text(
        f"💸 *{prov['name']}*\n"
        f"Total: {fmt(prov['total_cost'])} | Paid: {fmt(prov['total_paid'])} | Pending: {fmt(prov['outstanding'])}\n\n"
        f"Kitna payment karna hai?",
        parse_mode="Markdown", reply_markup=cancel_kb()
    )
    return PROV_PAY_AMOUNT

async def prov_pay_amount(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        amt = float(update.message.text.strip().replace(",", ""))
        assert amt > 0
    except Exception:
        await update.message.reply_text("❌ Valid amount likhein.")
        return PROV_PAY_AMOUNT

    prov_id = ctx.user_data["pay_prov_id"]
    prov    = db.update_provider_payment(prov_id, amt)
    remaining = prov["outstanding"]
    status = "✅ *FULLY PAID!*" if remaining <= 0 else f"🔴 Still Pending: {fmt(remaining)}"

    await update.message.reply_text(
        f"✅ *Payment Done to {prov['name']}*\n"
        f"💵 Paid Now: {fmt(amt)}\n"
        f"Total Paid: {fmt(prov['total_paid'])} / {fmt(prov['total_cost'])}\n"
        f"{status}",
        parse_mode="Markdown", reply_markup=main_menu_kb()
    )
    return MAIN_MENU

# ══════════════════════════════════════════════════════════════════════════════
# VIEW — KIT LEDGER
# ══════════════════════════════════════════════════════════════════════════════

async def view_ledger(q, ctx):
    filter_buttons = [
        [
            InlineKeyboardButton("📋 All",    callback_data="lf_all"),
            InlineKeyboardButton("🔵 Unsold", callback_data="lf_unsold"),
            InlineKeyboardButton("🟢 Sold",   callback_data="lf_sold"),
        ],
        [InlineKeyboardButton(b, callback_data=f"lf_{b}") for b in BRANDS],
        [InlineKeyboardButton("🔙 Back", callback_data="main")],
    ]
    await q.edit_message_text(
        "📋 *Kit Ledger — Filter Select Karein:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(filter_buttons)
    )
    return VIEW_KIT_DETAIL

async def view_kit_detail(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "main":
        await q.edit_message_text(MAIN_TEXT, parse_mode="Markdown", reply_markup=main_menu_kb())
        return MAIN_MENU

    flt  = q.data.replace("lf_", "")
    kits = db.get_all_kits(filter=flt)

    if not kits:
        await q.edit_message_text(
            f"⚠️ '{flt}' filter mein koi kit nahi mili.",
            reply_markup=back_kb()
        )
        return MAIN_MENU

    lines = [f"📋 *Kit Ledger — {flt.upper()}* ({len(kits)} kits)\n"]
    for k in kits:
        icon = "🟢" if k["status"] == "sold" else "🔵"
        line = (
            f"{icon} *#{k['kit_no']}* | {k['brand']}\n"
            f"  📂 Acc: `{k['account_no']}` | 💳 Card: `{k['card_no']}`\n"
            f"  🏭 Provider: {k['provider_name']} | 📅 {k['date_added'][:10]}"
        )
        if k["status"] == "sold":
            pending = k["sell_price"] - k["buyer_paid"]
            pay_status = "✅ Clear" if pending <= 0 else f"🔴 Due: {fmt(pending)}"
            line += (
                f"\n  🛒 Buyer: {k['buyer_name']} ({k['buyer_contact']})"
                f"\n  💵 Price: {fmt(k['sell_price'])} | Paid: {fmt(k['buyer_paid'])} | {pay_status}"
            )
        lines.append(line)

    text = "\n\n".join(lines)
    if len(text) > 3900:
        text = text[:3900] + "\n\n_(... aur records hain, filter karke dekhein)_"

    await q.edit_message_text(text, parse_mode="Markdown", reply_markup=back_kb())
    return MAIN_MENU

# ══════════════════════════════════════════════════════════════════════════════
# VIEW — PROVIDERS
# ══════════════════════════════════════════════════════════════════════════════

async def view_providers(q, ctx):
    providers = db.get_all_providers()
    if not providers:
        await q.edit_message_text("👥 Koi provider record nahi hai.", reply_markup=back_kb())
        return MAIN_MENU

    lines = [f"👥 *Providers ({len(providers)})*\n"]
    for p in providers:
        lines.append(
            f"👤 *{p['name']}* | 📞 {p['contact']}\n"
            f"  Kits: {p['total_kits']} | Cost: {fmt(p['total_cost'])}\n"
            f"  ✅ Paid: {fmt(p['total_paid'])} | 🔴 Pending: {fmt(p['outstanding'])}"
        )

    await q.edit_message_text(
        "\n\n".join(lines), parse_mode="Markdown", reply_markup=back_kb()
    )
    return MAIN_MENU

# ══════════════════════════════════════════════════════════════════════════════
# FULL REPORT
# ══════════════════════════════════════════════════════════════════════════════

async def full_report(q, ctx):
    s = db.get_full_summary()
    lines = [
        "📊 *Full Business Report*\n",
        f"📦 Total Kits: {s['total_kits']}  |  🔵 Unsold: {s['unsold']}  |  🟢 Sold: {s['sold']}",
        "",
        "💵 *Revenue (Buyers)*",
        f"  Billed:    {fmt(s['total_billed'])}",
        f"  Received:  {fmt(s['buyer_received'])}",
        f"  🔴 Pending: {fmt(s['buyer_pending'])}",
        "",
        "💸 *Cost (Providers)*",
        f"  Total Cost: {fmt(s['total_cost'])}",
        f"  Paid:       {fmt(s['provider_paid'])}",
        f"  🔴 Pending: {fmt(s['provider_pending'])}",
        "",
        "🏦 *Net*",
        f"  Cash in Hand: {fmt(s['buyer_received'] - s['provider_paid'])}",
        f"  Projected:    {fmt(s['total_billed'] - s['total_cost'])}",
        "",
        "─── Brand-wise ───",
    ]
    for brand, bs in s["by_brand"].items():
        lines.append(
            f"*{brand}*: {bs['kits']} kits | Billed {fmt(bs['billed'])} | Cost {fmt(bs['cost'])}"
        )

    await q.edit_message_text(
        "\n".join(lines), parse_mode="Markdown", reply_markup=back_kb()
    )
    return MAIN_MENU

# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("menu",  start),
        ],
        states={
            MAIN_MENU:       [CallbackQueryHandler(main_menu_handler)],
            PROV_NAME:       [MessageHandler(filters.TEXT & ~filters.COMMAND, prov_name)],
            PROV_CONTACT:    [MessageHandler(filters.TEXT & ~filters.COMMAND, prov_contact)],
            PROV_BRAND:      [CallbackQueryHandler(prov_brand)],
            PROV_ACCOUNT:    [MessageHandler(filters.TEXT & ~filters.COMMAND, prov_account)],
            PROV_CARD:       [MessageHandler(filters.TEXT & ~filters.COMMAND, prov_card)],
            PROV_KIT_QTY:    [MessageHandler(filters.TEXT & ~filters.COMMAND, prov_kit_qty)],
            PROV_KIT_PRICE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, prov_kit_price)],
            PROV_PAID_NOW:   [MessageHandler(filters.TEXT & ~filters.COMMAND, prov_paid_now)],
            BUY_KIT_SELECT:  [CallbackQueryHandler(buy_kit_select)],
            BUY_NAME:        [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_name)],
            BUY_CONTACT:     [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_contact)],
            BUY_PRICE:       [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_price)],
            BUY_PAID_NOW:    [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_paid_now)],
            UPD_SELECT_KIT:  [CallbackQueryHandler(upd_select_kit)],
            UPD_AMOUNT:      [MessageHandler(filters.TEXT & ~filters.COMMAND, upd_amount)],
            PROV_PAY_SELECT: [CallbackQueryHandler(prov_pay_select)],
            PROV_PAY_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, prov_pay_amount)],
            VIEW_KIT_DETAIL: [CallbackQueryHandler(view_kit_detail)],
        },
        fallbacks=[
            CommandHandler("start", start),
            CommandHandler("menu",  start),
        ],
        allow_reentry=True,
        per_message=False,
    )

    app.add_handler(conv)
    logger.info("✅ Bot started!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
