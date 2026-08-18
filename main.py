import os
import sqlite3
import random
import time
import discord
from discord.ext import commands

# إعداد البوت
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# ---------------------------------------------------------
# إعداد قاعدة البيانات
# ---------------------------------------------------------
conn = sqlite3.connect("economy.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    wallet INTEGER DEFAULT 100,
    bank INTEGER DEFAULT 0,
    dirty_money INTEGER DEFAULT 0,
    immunity_until INTEGER DEFAULT 0,
    gang_id INTEGER DEFAULT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS properties (
    property_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    price INTEGER NOT NULL,
    daily_income INTEGER NOT NULL,
    owner_id INTEGER DEFAULT NULL,
    is_for_sale INTEGER DEFAULT 0,
    sale_price INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS gangs (
    gang_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    leader_id INTEGER NOT NULL,
    vault INTEGER DEFAULT 0,
    successful_heists INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS gang_invites (
    user_id INTEGER PRIMARY KEY,
    gang_id INTEGER NOT NULL,
    contract_amount INTEGER NOT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS stocks (
    symbol TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    price INTEGER NOT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS user_stocks (
    user_id INTEGER,
    symbol TEXT,
    shares INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, symbol)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS lottery (
    user_id INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value INTEGER
)
""")

# القيم الافتراضية
cursor.execute("INSERT OR IGNORE INTO settings VALUES ('immunity_price', 5000)")
cursor.execute("INSERT OR IGNORE INTO stocks VALUES ('TECH', 'شركة التكنولوجيا', 500)")
cursor.execute("INSERT OR IGNORE INTO stocks VALUES ('REAL', 'شركة العقارات', 1200)")
cursor.execute("INSERT OR IGNORE INTO stocks VALUES ('ENG', 'شركة الطاقة', 800)")
conn.commit()

# قائمة السرقات المتاحة للعصابات
GANG_HEISTS = {
    1: {"name": "سطو على متجر تجاري", "min_loot": 15000, "max_loot": 30000, "base_chance": 0.50},
    2: {"name": "سطو على شاحنة أموال", "min_loot": 40000, "max_loot": 80000, "base_chance": 0.35},
    3: {"name": "سرقة البنك المركزي", "min_loot": 100000, "max_loot": 250000, "base_chance": 0.20}
}

current_auction = {
    "item": None,
    "highest_bid": 0,
    "highest_bidder": None,
    "active": False
}

# --- Helper Functions ---
def get_user(user_id):
    cursor.execute("SELECT wallet, bank, dirty_money, immunity_until, gang_id FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    if not res:
        cursor.execute("INSERT INTO users (user_id, wallet, bank, dirty_money) VALUES (?, 100, 0, 0)", (user_id,))
        conn.commit()
        return 100, 0, 0, 0, None
    return res

def update_wallet(user_id, amount):
    get_user(user_id)
    cursor.execute("UPDATE users SET wallet = wallet + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()

def update_bank(user_id, amount):
    get_user(user_id)
    cursor.execute("UPDATE users SET bank = bank + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()

def update_dirty_money(user_id, amount):
    get_user(user_id)
    cursor.execute("UPDATE users SET dirty_money = dirty_money + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()

def get_setting(key, default):
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    res = cursor.fetchone()
    return res[0] if res else default

# ---------------------------------------------------------
# الأحداث وقائمة الأوامر
# ---------------------------------------------------------
@bot.event
async def on_ready():
    print(f"✅ تم تشغيل البوت مع نظام العقود والسرقات المحدث باسم: {bot.user.name}")

@bot.command(name="اوامر", aliases=["الأوامر", "مساعدة", "أوامر"])
async def help_cmd(ctx):
    embed = discord.Embed(title="📜 قائمة الأوامر المحدثة", color=discord.Color.gold())
    embed.add_field(
        name="💰 المال والبنك",
        value="`!رصيدي` | `!تحويل` | `!ايداع` | `!سحب` | `!يومية` | `!عمل` | `!التوب`",
        inline=False
    )
    embed.add_field(
        name="💀 نظام العصابات والعقود",
        value="`!انشاء عصابة` | `!العصابات` | `!عصابتي` | `!دعوة @عضو المبلغ` | `!قبول الدعوة` | `!السرقات` | `!بدء سرقة [الرقم]`",
        inline=False
    )
    embed.add_field(
        name="📈 الأسهم الاستثمارية",
        value="`!الاسهم` | `!شراء سهم` | `!بيع سهم` | `!اسهمي`",
        inline=False
    )
    embed.add_field(
        name="🧼 غسيل الأموال والسرقة",
        value="`!سرقة` | `!حصانة` | `!غسيل [المبلغ]`",
        inline=False
    )
    embed.add_field(
        name="🔨 المزادات والعقارات واليانصيب",
        value="`!العقارات` | `!شراء عقار` | `!مزايدة` | `!شراء تذكرة` | `!اليانصيب`",
        inline=False
    )
    await ctx.send(embed=embed)

# ---------------------------------------------------------
# 1. نظام المالية والرصيد
# ---------------------------------------------------------
@bot.command(aliases=["رصيد", "فلوسي"])
async def رصيدي(ctx):
    wallet, bank, dirty, immunity, _ = get_user(ctx.author.id)
    has_immunity = "🛡️ مفعلة" if immunity > time.time() else "❌ غير مفعلة"
    embed = discord.Embed(title=f"💳 رصيد {ctx.author.display_name}", color=discord.Color.green())
    embed.add_field(name="💵 الكاش", value=f"{wallet:,} ريال", inline=True)
    embed.add_field(name="🏦 البنك", value=f"{bank:,} ريال", inline=True)
    embed.add_field(name="🧼 فلوس سوداء", value=f"{dirty:,} ريال", inline=True)
    embed.add_field(name="🛡️ الحصانة", value=has_immunity, inline=True)
    await ctx.send(embed=embed)

@bot.command()
async def تحويل(ctx, member: discord.Member = None, amount: int = None):
    if not member or not amount or amount <= 0 or member.id == ctx.author.id: return
    wallet, _, _, _, _ = get_user(ctx.author.id)
    if wallet < amount:
        await ctx.send("❌ لا تملك المبلغ الكافي في الكاش!")
        return
    update_wallet(ctx.author.id, -amount)
    update_wallet(member.id, amount)
    await ctx.send(f"✅ تم تحويل **{amount:,} ريال** إلى {member.mention}.")

@bot.command()
async def ايداع(ctx, amount: int = None):
    if not amount or amount <= 0: return
    wallet, _, _, _, _ = get_user(ctx.author.id)
    if wallet < amount:
        await ctx.send("❌ لا تملك هذا المبلغ في الكاش!")
        return
    update_wallet(ctx.author.id, -amount)
    update_bank(ctx.author.id, amount)
    await ctx.send(f"🏦 تم إيداع **{amount:,} ريال** في البنك.")

@bot.command()
async def سحب(ctx, amount: int = None):
    if not amount or amount <= 0: return
    _, bank, _, _, _ = get_user(ctx.author.id)
    if bank < amount:
        await ctx.send("❌ لا تملك هذا المبلغ في البنك!")
        return
    update_bank(ctx.author.id, -amount)
    update_wallet(ctx.author.id, amount)
    await ctx.send(f"💵 تم سحب **{amount:,} ريال** من البنك.")

@bot.command()
@commands.cooldown(1, 86400, commands.BucketType.user)
async def يومية(ctx):
    update_wallet(ctx.author.id, 500)
    await ctx.send("🎉 حصلت على مكافأتك اليومية بقيمة **500 ريال**!")

@bot.command()
@commands.cooldown(1, 3600, commands.BucketType.user)
async def عمل(ctx):
    earnings = random.randint(50, 200)
    update_wallet(ctx.author.id, earnings)
    await ctx.send(f"💼 عملت بجد وحصلت على **{earnings:,} ريال**!")

@bot.command(name="التوب", aliases=["توب", "الأغنياء"])
async def top_rich(ctx):
    cursor.execute("SELECT user_id, (wallet + bank) as total FROM users ORDER BY total DESC LIMIT 10")
    top_users = cursor.fetchall()
    embed = discord.Embed(title="🏆 قائمة أغنى 10 أعضاء", color=discord.Color.gold())
    for idx, (u_id, total) in enumerate(top_users, 1):
        user = bot.get_user(u_id)
        name = user.display_name if user else f"مستخدم ({u_id})"
        embed.add_field(name=f"#{idx} - {name}", value=f"💰 **{total:,} ريال**", inline=False)
    await ctx.send(embed=embed)

# ---------------------------------------------------------
# 2. نظام العصابات المطور (العقود + تحديد السرقات + الأرباح)
# ---------------------------------------------------------
@bot.command(name="انشاء", aliases=["إنشاء"])
async def create_gang(ctx, sub: str = None, name: str = None):
    if sub == "عصابة" and name:
        cost = 100000
        wallet, _, _, _, gang_id = get_user(ctx.author.id)
        if gang_id:
            await ctx.send("❌ أنت مشترك في عصابة بالفعل!")
            return
        if wallet < cost:
            await ctx.send(f"❌ تكلفة إنشاء العصابة **{cost:,} ريال**!")
            return
        try:
            update_wallet(ctx.author.id, -cost)
            cursor.execute("INSERT INTO gangs (name, leader_id) VALUES (?, ?)", (name, ctx.author.id))
            g_id = cursor.lastrowid
            cursor.execute("UPDATE users SET gang_id = ? WHERE user_id = ?", (g_id, ctx.author.id))
            conn.commit()
            await ctx.send(f"🔥 تم تأسيس عصابة **[{name}]** بنجاح!")
        except:
            await ctx.send("❌ هذا الاسم مستخدم لعصابة أخرى.")

@bot.command(name="دعوة")
async def invite_member(ctx, member: discord.Member = None, contract_amount: int = None):
    if not member or contract_amount is None or contract_amount < 0:
        await ctx.send("❌ الصيغة الصحيحة: `!دعوة @العضو [مبلغ_العقد]`")
        return
    
    _, _, _, _, gang_id = get_user(ctx.author.id)
    if not gang_id:
        await ctx.send("❌ أنت لست قائد عصابة!")
        return

    cursor.execute("SELECT leader_id, vault, name FROM gangs WHERE gang_id = ?", (gang_id,))
    leader_id, vault, g_name = cursor.fetchone()

    if ctx.author.id != leader_id:
        await ctx.send("❌ فقط رئيس العصابة يمكنه تقديم عقود وانضمام للأعضاء!")
        return

    if vault < contract_amount:
        await ctx.send(f"❌ خزينة العصابة لا تكفي لمبلغ العقد! المتوفر في الخزينة: **{vault:,} ريال**.")
        return

    _, _, _, _, target_gang = get_user(member.id)
    if target_gang:
        await ctx.send("❌ هذا العضو ينتمي لعصابة أخرى بالفعل!")
        return

    cursor.execute("INSERT OR REPLACE INTO gang_invites VALUES (?, ?, ?)", (member.id, gang_id, contract_amount))
    conn.commit()
    await ctx.send(f"📜 تم إرسال عقد انضمام لـ {member.mention} للانضمام لعصابة **[{g_name}]** بمبلغ عقد قدره **{contract_amount:,} ريال**!\nللقبول اكتب: `!قبول الدعوة`")

@bot.command(name="قبول", aliases=["قبول الدعوة"])
async def accept_invite(ctx, sub: str = None):
    cursor.execute("SELECT gang_id, contract_amount FROM gang_invites WHERE user_id = ?", (ctx.author.id,))
    invite = cursor.fetchone()
    
    if not invite:
        await ctx.send("❌ لا توجد لديك أي عقود انضمام معلقة!")
        return

    gang_id, contract_amount = invite
    cursor.execute("SELECT name, vault FROM gangs WHERE gang_id = ?", (gang_id,))
    g_name, vault = cursor.fetchone()

    if vault < contract_amount:
        await ctx.send("❌ أفلست خزينة العصابة ولم تعد تستطيع دفع قيمة العقد!")
        return

    # تخصم قيمة العقد من الخزينة وتتحول للعضو
    cursor.execute("UPDATE gangs SET vault = vault - ? WHERE gang_id = ?", (contract_amount, gang_id))
    cursor.execute("UPDATE users SET gang_id = ? WHERE user_id = ?", (gang_id, ctx.author.id))
    cursor.execute("DELETE FROM gang_invites WHERE user_id = ?", (ctx.author.id,))
    conn.commit()

    update_wallet(ctx.author.id, contract_amount)
    await ctx.send(f"🎉 **مبروك!** انضم {ctx.author.mention} إلى عصابة **[{g_name}]** واستلم مبلغ العقد **{contract_amount:,} ريال** كاش!")

@bot.command(name="السرقات")
async def list_heists(ctx):
    embed = discord.Embed(title="💣 قائمة سرقات العصابات المتاحة (للرؤساء)", color=discord.Color.red())
    for h_id, info in GANG_HEISTS.items():
        embed.add_field(
            name=f"#{h_id} - {info['name']}",
            value=f"💵 الأرباح المحتملة: **{info['min_loot']:,} - {info['max_loot']:,} ريال**\n🎯 نسبة النجاح الأساسية: **{int(info['base_chance']*100)}%** (+5% لكل عضو إضافي)",
            inline=False
        )
    embed.set_footer(text="لبدء سرقة اكتب: !بدء سرقة [رقم_السرقة]")
    await ctx.send(embed=embed)

@bot.command(name="بدء", aliases=["بدء سرقة"])
@commands.cooldown(1, 10800, commands.BucketType.guild)
async def start_heist(ctx, sub: str = None, heist_id: int = None):
    if sub == "سرقة" and heist_id in GANG_HEISTS:
        _, _, _, _, gang_id = get_user(ctx.author.id)
        if not gang_id:
            await ctx.send("❌ يجب أن تكون في عصابة لتنفذ سرقة!")
            return

        cursor.execute("SELECT leader_id, name FROM gangs WHERE gang_id = ?", (gang_id,))
        leader_id, g_name = cursor.fetchone()

        if ctx.author.id != leader_id:
            await ctx.send("❌ فقط رئيس العصابة يمكنه تحديد وبدء السرقات!")
            return

        # عدد الأعضاء ونسبة النجاح
        cursor.execute("SELECT user_id FROM users WHERE gang_id = ?", (gang_id,))
        members = cursor.fetchall()
        member_count = len(members)

        heist = GANG_HEISTS[heist_id]
        # زيادة نسبة النجاح بناءً على عدد الأعضاء
        final_chance = min(heist["base_chance"] + ((member_count - 1) * 0.05), 0.90)

        if random.random() <= final_chance:
            total_loot = random.randint(heist["min_loot"], heist["max_loot"])
            
            # توزيع الأرباح: 40% للأعضاء و 60% لخزينة العصابة
            member_share = int((total_loot * 0.40) / member_count)
            vault_share = total_loot - (member_share * member_count)

            for m in members:
                update_wallet(m[0], member_share)

            cursor.execute("UPDATE gangs SET vault = vault + ?, successful_heists = successful_heists + 1 WHERE gang_id = ?", (vault_share, gang_id))
            conn.commit()

            embed = discord.Embed(title=f"💥 نجحت عملية: {heist['name']}!", color=discord.Color.green())
            embed.add_field(name="🏴 العصابة", value=f"[{g_name}]", inline=True)
            embed.add_field(name="💰 الغنيمة الإجمالية", value=f"{total_loot:,} ريال", inline=True)
            embed.add_field(name="👥 حصة كل عضو كاش", value=f"{member_share:,} ريال", inline=False)
            embed.add_field(name="🏦 أرباح الخزينة", value=f"{vault_share:,} ريال", inline=False)
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"🚓 **فشلت عملية {heist['name']}!** حاصرت الشرطة عصابة **[{g_name}]** وتم إحباط الخطة!")

@bot.command(name="العصابات", aliases=["عصابات"])
async def list_gangs(ctx):
    cursor.execute("SELECT gang_id, name, vault, successful_heists FROM gangs")
    gangs = cursor.fetchall()
    if not gangs:
        await ctx.send("🏴 لا يوجد عصابات مسجلة حالياً.")
        return
    embed = discord.Embed(title="☠️ قائمة العصابات", color=discord.Color.dark_red())
    for g_id, name, vault, heists in gangs:
        cursor.execute("SELECT COUNT(*) FROM users WHERE gang_id = ?", (g_id,))
        m_count = cursor.fetchone()[0]
        embed.add_field(name=f"عصابة [{name}]", value=f"👥 الأعضاء: {m_count} | 💰 الخزينة: {vault:,} ريال | 💣 السرقات: {heists}", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="عصابتي")
async def my_gang(ctx):
    _, _, _, _, gang_id = get_user(ctx.author.id)
    if not gang_id:
        await ctx.send("❌ أنت لست عضواً في أي عصابة.")
        return
    cursor.execute("SELECT name, leader_id, vault, successful_heists FROM gangs WHERE gang_id = ?", (gang_id,))
    g_name, leader_id, vault, heists = cursor.fetchone()
    leader = bot.get_user(leader_id)
    l_name = leader.display_name if leader else f"مستخدم ({leader_id})"
    
    cursor.execute("SELECT COUNT(*) FROM users WHERE gang_id = ?", (gang_id,))
    m_count = cursor.fetchone()[0]

    embed = discord.Embed(title=f"🏴 عصابة [{g_name}]", color=discord.Color.dark_purple())
    embed.add_field(name="👑 القائد", value=l_name, inline=True)
    embed.add_field(name="👥 عدد الأعضاء", value=f"{m_count} أعضاء", inline=True)
    embed.add_field(name="💰 الخزينة", value=f"{vault:,} ريال", inline=True)
    embed.add_field(name="💣 السرقات الناجحة", value=f"{heists} مرة", inline=True)
    await ctx.send(embed=embed)

# ---------------------------------------------------------
# 3. باقي الأنظمة (الأسهم، الغسيل، المزادات، اليانصيب)
# ---------------------------------------------------------
@bot.command(name="الاسهم", aliases=["أسهم", "الأسهم"])
async def stocks_list(ctx):
    cursor.execute("SELECT symbol, name, price FROM stocks")
    stocks = cursor.fetchall()
    embed = discord.Embed(title="📈 سوق الأسهم الاستثماري", color=discord.Color.blue())
    for sym, name, price in stocks:
        embed.add_field(name=f"{name} [{sym}]", value=f"💵 سعر السهم: **{price:,} ريال**", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="شراء", aliases=["شراء سهم"])
async def buy_stock(ctx, sub: str = None, symbol: str = None, count: int = 1):
    if sub == "سهم" and symbol:
        symbol = symbol.upper()
        cursor.execute("SELECT price, name FROM stocks WHERE symbol = ?", (symbol,))
        stock = cursor.fetchone()
        if not stock: return
        price, name = stock
        total_cost = price * count
        wallet, _, _, _, _ = get_user(ctx.author.id)
        if wallet < total_cost: return
        update_wallet(ctx.author.id, -total_cost)
        cursor.execute("INSERT INTO user_stocks VALUES (?, ?, ?) ON CONFLICT(user_id, symbol) DO UPDATE SET shares = shares + ?", (ctx.author.id, symbol, count, count))
        conn.commit()
        await ctx.send(f"✅ تم شراء **{count}** أسهم في **{name}** بـ **{total_cost:,} ريال**!")

@bot.command(name="بيع", aliases=["بيع سهم"])
async def sell_stock(ctx, sub: str = None, symbol: str = None, count: int = 1):
    if sub == "سهم" and symbol:
        symbol = symbol.upper()
        cursor.execute("SELECT shares FROM user_stocks WHERE user_id = ? AND symbol = ?", (ctx.author.id, symbol))
        res = cursor.fetchone()
        if not res or res[0] < count: return
        cursor.execute("SELECT price, name FROM stocks WHERE symbol = ?", (symbol,))
        price, name = cursor.fetchone()
        total_return = price * count
        cursor.execute("UPDATE user_stocks SET shares = shares - ? WHERE user_id = ? AND symbol = ?", (count, ctx.author.id, symbol))
        conn.commit()
        update_wallet(ctx.author.id, total_return)
        await ctx.send(f"💵 تم بيع **{count}** أسهم بـ **{total_return:,} ريال**!")

@bot.command(name="اسهمي")
async def my_stocks(ctx):
    cursor.execute("SELECT us.symbol, s.name, us.shares, s.price FROM user_stocks us JOIN stocks s ON us.symbol = s.symbol WHERE us.user_id = ? AND us.shares > 0", (ctx.author.id,))
    stocks = cursor.fetchall()
    if not stocks: return
    embed = discord.Embed(title=f"📊 محفظة {ctx.author.display_name}", color=discord.Color.teal())
    for sym, name, shares, price in stocks:
        embed.add_field(name=f"{name} [{sym}]", value=f"📦 العدد: **{shares}** | 💰 القيمة: **{shares * price:,} ريال**", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="غسيل")
async def wash_money(ctx, amount: int = None):
    if not amount or amount <= 0: return
    _, _, dirty, _, _ = get_user(ctx.author.id)
    if dirty < amount: return
    if random.random() <= 0.10:
        update_dirty_money(ctx.author.id, -amount)
        await ctx.send(f"🚨 **تم مصادرة {amount:,} ريال سوداء!**")
        return
    clean_amount = int(amount * 0.85)
    update_dirty_money(ctx.author.id, -amount)
    update_wallet(ctx.author.id, clean_amount)
    await ctx.send(f"🧼 **تمت العملية!** تحول المبلغ إلى **{clean_amount:,} ريال** كاش.")

@bot.command()
@commands.cooldown(1, 7200, commands.BucketType.user)
async def سرقة(ctx, target: discord.Member = None):
    if not target or target.id == ctx.author.id: return
    s_wallet, _, _, _, _ = get_user(ctx.author.id)
    t_wallet, _, _, t_immunity, _ = get_user(target.id)
    if t_immunity > time.time() or t_wallet < 200: return

    if random.random() <= 0.35:
        stolen = random.randint(100, int(t_wallet * 0.5))
        update_wallet(target.id, -stolen)
        update_dirty_money(ctx.author.id, stolen)
        await ctx.send(f"🥷 سرقت **{stolen:,} ريال** أموال سوداء!")
    else:
        penalty = min(s_wallet, random.randint(100, 500))
        update_wallet(ctx.author.id, -penalty)
        update_wallet(target.id, penalty)
        await ctx.send(f"🚨 تم القبض عليك وغرمت **{penalty:,} ريال**!")

@bot.command()
async def حصانة(ctx):
    price = get_setting('immunity_price', 5000)
    wallet, _, _, immunity, _ = get_user(ctx.author.id)
    if immunity > time.time() or wallet < price: return
    update_wallet(ctx.author.id, -price)
    until = int(time.time()) + 86400
    cursor.execute("UPDATE users SET immunity_until = ? WHERE user_id = ?", (until, ctx.author.id))
    conn.commit()
    await ctx.send("🛡️ تم تفعيل الحصانة 24 ساعة!")

@bot.command()
async def مزايدة(ctx, amount: int = None):
    if not current_auction["active"] or not amount or amount <= current_auction["highest_bid"]: return
    wallet, _, _, _, _ = get_user(ctx.author.id)
    if wallet < amount: return
    current_auction["highest_bid"] = amount
    current_auction["highest_bidder"] = ctx.author
    await ctx.send(f"🔨 {ctx.author.mention} رفع السعر لـ **{amount:,} ريال**!")

@bot.command(name="شراء تذكرة")
async def buy_ticket(ctx):
    cost = 1000
    wallet, _, _, _, _ = get_user(ctx.author.id)
    if wallet < cost: return
    update_wallet(ctx.author.id, -cost)
    cursor.execute("INSERT INTO lottery VALUES (?)", (ctx.author.id,))
    conn.commit()
    await ctx.send("🎟️ تم شراء تذكرة يانصيب!")

@bot.command(name="اليانصيب")
async def show_lottery(ctx):
    cursor.execute("SELECT COUNT(*) FROM lottery")
    tickets = cursor.fetchone()[0]
    await ctx.send(f"🎟️ التذاكر: **{tickets}** | الجائزة: **{tickets * 1000:,} ريال**!")

@bot.command(name="العقارات")
async def list_properties(ctx):
    cursor.execute("SELECT property_id, name, price, daily_income, owner_id FROM properties")
    props = cursor.fetchall()
    if not props: return
    embed = discord.Embed(title="🏢 العقارات", color=discord.Color.blue())
    for p_id, name, price, income, owner_id in props:
        status = "🟢 متاح" if not owner_id else "🔴 مملوك"
        embed.add_field(name=f"#{p_id} {name}", value=f"💰 السعر: {price:,} | 📈 الربح: {income:,}\n📌 {status}", inline=False)
    await ctx.send(embed=embed)

# ---------------------------------------------------------
# 4. أوامر الأونر الإدارية
# ---------------------------------------------------------
@bot.command(name="تحديث الاسهم")
@commands.is_owner()
async def update_stocks_price(ctx):
    cursor.execute("SELECT symbol, price FROM stocks")
    stocks = cursor.fetchall()
    for sym, price in stocks:
        change = random.choice([-0.15, -0.05, 0.05, 0.15])
        new_price = max(10, int(price * (1 + change)))
        cursor.execute("UPDATE stocks SET price = ? WHERE symbol = ?", (new_price, sym))
    conn.commit()
    await ctx.send("📈📉 تم تحديث أسعار الأسهم!")

@bot.command(name="بدء مزاد")
@commands.is_owner()
async def start_auction_cmd(ctx, item: str = None, start_price: int = 1000):
    if not item: return
    current_auction["item"] = item
    current_auction["highest_bid"] = start_price
    current_auction["highest_bidder"] = None
    current_auction["active"] = True
    await ctx.send(f"🔨 **بدأ المزاد!** السلعة: **{item}** | البدء بـ **{start_price:,} ريال**!")

@bot.command(name="انهاء المزاد")
@commands.is_owner()
async def end_auction_cmd(ctx):
    if not current_auction["active"]: return
    current_auction["active"] = False
    winner = current_auction["highest_bidder"]
    bid = current_auction["highest_bid"]
    item = current_auction["item"]
    if winner:
        update_wallet(winner.id, -bid)
        await ctx.send(f"🎉 الفائز هو {winner.mention} بـ **{item}** مقابل **{bid:,} ريال**!")

@bot.command(name="سحب اليانصيب")
@commands.is_owner()
async def draw_lottery_cmd(ctx):
    cursor.execute("SELECT user_id FROM lottery")
    tickets = cursor.fetchall()
    if not tickets: return
    winner_id = random.choice(tickets)[0]
    total_jackpot = len(tickets) * 1000
    update_wallet(winner_id, total_jackpot)
    cursor.execute("DELETE FROM lottery")
    conn.commit()
    winner = bot.get_user(winner_id)
    w_name = winner.mention if winner else f"مستخدم ({winner_id})"
    await ctx.send(f"🎉 الفائز باليانصيب هو {w_name} بـ **{total_jackpot:,} ريال**!")

# تشغيل البوت
TOKEN = os.environ.get("BOT_TOKEN") or os.environ.get("DISCORD_TOKEN")
bot.run(TOKEN)
