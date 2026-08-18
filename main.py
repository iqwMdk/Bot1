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
# إعداد قاعدة البيانات الشاملة
# ---------------------------------------------------------
conn = sqlite3.connect("economy.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    wallet INTEGER DEFAULT 5000,
    bank INTEGER DEFAULT 0,
    dirty_money INTEGER DEFAULT 0,
    immunity_until INTEGER DEFAULT 0,
    gang_id INTEGER DEFAULT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS cars (
    car_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    price INTEGER NOT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS user_cars (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    car_id TEXT,
    FOREIGN KEY(car_id) REFERENCES cars(car_id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS bounties (
    target_id INTEGER PRIMARY KEY,
    amount INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS inventory (
    user_id INTEGER,
    item_id TEXT,
    quantity INTEGER DEFAULT 0,
    PRIMARY KEY(user_id, item_id)
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

# إضافة قائمة السيارات الواقعية تلقائياً
cars_data = [
    ('ACCENT', 'هيونداي أكسنت', 65000),
    ('CAMRY', 'تويوتا كامري', 115000),
    ('CAPRICE', 'شيفروليه كابرس كلاسيك', 140000),
    ('PATROL', 'نيسان باترول', 280000),
    ('LANDCRUISER', 'تويوتا لاندكروزر VX-R', 330000),
    ('LEXUS', 'لكزس LX600 (فخمة ونادرة)', 550000),
    ('G63', 'مرسيدس G63 AMG', 950000),
    ('ROLLS', 'روز رايز فانتوم', 2200000)
]
for c_id, c_name, c_price in cars_data:
    cursor.execute("INSERT OR REPLACE INTO cars VALUES (?, ?, ?)", (c_id, c_name, c_price))

# إضافة الأسهم والشركات بأسعار واقعية
stocks_data = [
    ('ARAMCO', 'أرامكو السعودية', 30),
    ('STC', 'شركة الاتصالات STC', 40),
    ('RAJHI', 'مصرف الراجحي', 85),
    ('SABIC', 'شركة سابك', 75)
]
for s_sym, s_name, s_price in stocks_data:
    cursor.execute("INSERT OR REPLACE INTO stocks VALUES (?, ?, ?)", (s_sym, s_name, s_price))

conn.commit()

# متغيرات المزاد والتحديات المؤقتة
current_auction = {"item": None, "highest_bid": 0, "highest_bidder": None, "active": False}

# --- Helper Functions ---
def get_user(user_id):
    cursor.execute("SELECT wallet, bank, dirty_money, immunity_until, gang_id FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    if not res:
        cursor.execute("INSERT INTO users (user_id, wallet, bank, dirty_money) VALUES (?, 5000, 0, 0)", (user_id,))
        conn.commit()
        return 5000, 0, 0, 0, None
    return res

def update_wallet(user_id, amount):
    get_user(user_id)
    cursor.execute("UPDATE users SET wallet = wallet + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()

def update_bank(user_id, amount):
    get_user(user_id)
    cursor.execute("UPDATE users SET bank = bank + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()

def add_item(user_id, item_id, qty=1):
    cursor.execute("INSERT INTO inventory VALUES (?, ?, ?) ON CONFLICT(user_id, item_id) DO UPDATE SET quantity = quantity + ?", (user_id, item_id, qty, qty))
    conn.commit()

def get_item_qty(user_id, item_id):
    cursor.execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_id = ?", (user_id, item_id))
    res = cursor.fetchone()
    return res[0] if res else 0

# ---------------------------------------------------------
# الأحداث والقائمة الرئيسية
# ---------------------------------------------------------
@bot.event
async def on_ready():
    print(f"✅ تم تشغيل البوت بنجاح باسم: {bot.user.name}")

@bot.command(aliases=["اوامر", "الأوامر", "مساعدة"])
async def help_cmd(ctx):
    embed = discord.Embed(title="📜 دليل أوامر البوت الشامل", color=discord.Color.gold())
    embed.add_field(name="💰 المالية والتداول", value="`!رصيدي` | `!تحويل` | `!ايداع` | `!سحب` | `!يومية` | `!عمل` | `!التوب`", inline=False)
    embed.add_field(name="🏎️ حراج السيارات الواقعي", value="`!معرض_السيارات` | `!شراء_سيارة` | `!سياراتي` | `!بيع_سيارة`", inline=False)
    embed.add_field(name="🎯 الاغتيالات والمطلوبين", value="`!مكافأة @عضو [المبلغ]` | `!اغتيال @عضو` | `!المطلوبين`", inline=False)
    embed.add_field(name="🕶️ السوق المظلم والحقيبة", value="`!السوق_المظلم` | `!شراء_أداة` | `!حقيبتي`", inline=False)
    embed.add_field(name="⚔️ التحديات والمواجهات", value="`!روليت @عضو [المبلغ]` | `!تحدي @عضو [المبلغ] [حجر/ورقة/مقص]`", inline=False)
    embed.add_field(name="📈 الأسهم والمزادات", value="`!الأسهم` | `!شراء_سهم` | `!بيع_سهم` | `!مزايدة` | `!شراء_تذكرة`", inline=False)
    await ctx.send(embed=embed)

# ---------------------------------------------------------
# 1. نظام المالية والاقتصاد
# ---------------------------------------------------------
@bot.command(aliases=["رصيد", "فلوسي"])
async def رصيدي(ctx):
    wallet, bank, dirty, immunity, _ = get_user(ctx.author.id)
    embed = discord.Embed(title=f"💳 المحفظة المالية لـ {ctx.author.display_name}", color=discord.Color.green())
    embed.add_field(name="💵 الكاش", value=f"{wallet:,} ريال", inline=True)
    embed.add_field(name="🏦 الحساب البنكي", value=f"{bank:,} ريال", inline=True)
    embed.add_field(name="🧼 أموال مشبوهة", value=f"{dirty:,} ريال", inline=True)
    await ctx.send(embed=embed)

@bot.command()
@commands.cooldown(1, 86400, commands.BucketType.user)
async def يومية(ctx):
    reward = 3000
    update_wallet(ctx.author.id, reward)
    await ctx.send(f"🎉 استلمت مكافأتك اليومية بقيمة **{reward:,} ريال**!")

@bot.command()
@commands.cooldown(1, 1800, commands.BucketType.user)
async def عمل(ctx):
    earnings = random.randint(800, 2500)
    update_wallet(ctx.author.id, earnings)
    await ctx.send(f"💼 أتممت عملك وحصلت على **{earnings:,} ريال** كاش!")

@bot.command()
async def تحويل(ctx, member: discord.Member = None, amount: int = None):
    if not member or not amount or amount <= 0 or member.id == ctx.author.id: return
    wallet, _, _, _, _ = get_user(ctx.author.id)
    if wallet < amount:
        await ctx.send("❌ رصيدك الكاش لا يكفي إجراء هذه الحوالة!")
        return
    update_wallet(ctx.author.id, -amount)
    update_wallet(member.id, amount)
    await ctx.send(f"✅ تم تحويل **{amount:,} ريال** إلى {member.mention}.")

# ---------------------------------------------------------
# 2. حراج ومعرض السيارات الواقعي 🏎️
# ---------------------------------------------------------
@bot.command()
async def معرض_السيارات(ctx):
    cursor.execute("SELECT car_id, name, price FROM cars ORDER BY price ASC")
    cars = cursor.fetchall()
    embed = discord.Embed(title="🏎️ معرض وحراج السيارات الواقعي", color=discord.Color.red())
    for c_id, name, price in cars:
        embed.add_field(name=f"🚗 {name} [{c_id}]", value=f"💰 السعر: **{price:,} ريال**", inline=False)
    embed.set_footer(text="الشراء عبر أمر: !شراء_سيارة [رمز_السيارة]")
    await ctx.send(embed=embed)

@bot.command()
async def شراء_سيارة(ctx, car_id: str = None):
    if not car_id: return
    car_id = car_id.upper()
    cursor.execute("SELECT name, price FROM cars WHERE car_id = ?", (car_id,))
    car = cursor.fetchone()
    if not car:
        await ctx.send("❌ رمز السيارة غير موجود في المعرض!")
        return
    name, price = car
    wallet, _, _, _, _ = get_user(ctx.author.id)
    if wallet < price:
        await ctx.send(f"❌ لا تملك المبلغ الكافي لشراء **{name}**. السعر: **{price:,} ريال**")
        return

    update_wallet(ctx.author.id, -price)
    cursor.execute("INSERT INTO user_cars (user_id, car_id) VALUES (?, ?)", (ctx.author.id, car_id))
    conn.commit()
    await ctx.send(f"🎉 ألف مبروك! قمت بشراء **{name}** بمبلغ **{price:,} ريال**!")

@bot.command()
async def سياراتي(ctx):
    cursor.execute("SELECT uc.id, c.name, c.price FROM user_cars uc JOIN cars c ON uc.car_id = c.car_id WHERE uc.user_id = ?", (ctx.author.id,))
    my_cars = cursor.fetchall()
    if not my_cars:
        await ctx.send("🚘 لا تمتلك أي سيارات حالياً في كراجك.")
        return
    embed = discord.Embed(title=f"🚘 كراج سيارات {ctx.author.display_name}", color=discord.Color.blue())
    for u_id, name, price in my_cars:
        embed.add_field(name=f"• {name} (رقم اللوحة: #{u_id})", value=f"💵 قيمتها: **{price:,} ريال**", inline=False)
    await ctx.send(embed=embed)

# ---------------------------------------------------------
# 3. نظام عقود القتلة المأجورين (Bounty / Hitman) 🎯
# ---------------------------------------------------------
@bot.command()
async def مكافأة(ctx, member: discord.Member = None, amount: int = None):
    if not member or not amount or amount < 10000 or member.id == ctx.author.id:
        await ctx.send("❌ الحد الأدنى لوضع مكافأة قتل على عضو هو **10,000 ريال**!")
        return
    wallet, _, _, _, _ = get_user(ctx.author.id)
    if wallet < amount:
        await ctx.send("❌ لا تملك هذا المبلغ الكافي بالرصيد!")
        return

    update_wallet(ctx.author.id, -amount)
    cursor.execute("INSERT INTO bounties VALUES (?, ?) ON CONFLICT(target_id) DO UPDATE SET amount = amount + ?", (member.id, amount, amount))
    conn.commit()
    await ctx.send(f"🎯 تم وضع مكافأة قدرها **{amount:,} ريال** على رأس {member.mention}! أصبح هدفاً للمأجورين.")

@bot.command()
@commands.cooldown(1, 3600, commands.BucketType.user)
async def اغتيال(ctx, member: discord.Member = None):
    if not member or member.id == ctx.author.id: return
    cursor.execute("SELECT amount FROM bounties WHERE target_id = ?", (member.id,))
    bounty = cursor.fetchone()
    if not bounty or bounty[0] <= 0:
        await ctx.send("❌ هذا العضو ليس مطلوباً ولا توجد مكافأة على رأسه!")
        return

    # التحقق من وجود سترة مضادة للاغتيال
    if get_item_qty(member.id, "VEST") > 0:
        cursor.execute("UPDATE inventory SET quantity = quantity - 1 WHERE user_id = ? AND item_id = 'VEST'", (member.id,))
        conn.commit()
        await ctx.send(f"🛡️ فشلت محاولة الاغتيال! {member.mention} كان يرتدي **سترة مضادة للرصاص** وتم تدميرها!")
        return

    reward = bounty[0]
    if random.random() <= 0.40: # نسبة النجاح 40%
        cursor.execute("DELETE FROM bounties WHERE target_id = ?", (member.id,))
        conn.commit()
        update_wallet(ctx.author.id, reward)
        await ctx.send(f"🗡️ **تمت عملية الاغتيال بنجاح!** قمت بتصفية {member.mention} واستلمت مكافأة قدرها **{reward:,} ريال**!")
    else:
        penalty = 5000
        update_wallet(ctx.author.id, -penalty)
        await ctx.send(f"🚨 فشلت محاولة الاغتيال وتم القبض عليك ودفعت غرامة **{penalty:,} ريال**!")

@bot.command()
async def المطلوبين(ctx):
    cursor.execute("SELECT target_id, amount FROM bounties WHERE amount > 0 ORDER BY amount DESC")
    targets = cursor.fetchall()
    if not targets:
        await ctx.send("🕊️ لا يوجد أي شخص مطلوب حالياً.")
        return
    embed = discord.Embed(title="🎯 قائمة المطلوبين للقتل المأجور", color=discord.Color.dark_red())
    for t_id, amount in targets:
        user = bot.get_user(t_id)
        name = user.display_name if user else f"مستخدم ({t_id})"
        embed.add_field(name=f"💀 {name}", value=f"💰 المكافأة: **{amount:,} ريال**", inline=False)
    await ctx.send(embed=embed)

# ---------------------------------------------------------
# 4. نظام السوق المظلم (Black Market) 🕶️
# ---------------------------------------------------------
@bot.command()
async def السوق_المظلم(ctx):
    embed = discord.Embed(title="🕶️ السوق المظلم السرّي", color=discord.Color.purple())
    embed.add_field(name="🛡️ سترة حماية [VEST]", value="الحماية من أول محاولة اغتيال تقابلك.\n💵 السعر: **25,000 ريال**", inline=False)
    embed.add_field(name="💻 جهاز تهكير البنك [HACK]", value="يرفع نسبة نجاح السرقة إلى 80%.\n💵 السعر: **50,000 ريال**", inline=False)
    embed.set_footer(text="للشراء استخدم: !شراء_أداة [رمز_الأداة]")
    await ctx.send(embed=embed)

@bot.command()
async def شراء_أداة(ctx, item_id: str = None):
    if not item_id: return
    item_id = item_id.upper()
    prices = {"VEST": 25000, "HACK": 50000}
    if item_id not in prices:
        await ctx.send("❌ أداة غير معروفة بالسوق المظلم!")
        return

    price = prices[item_id]
    wallet, _, _, _, _ = get_user(ctx.author.id)
    if wallet < price:
        await ctx.send(f"❌ لا تملك المبلغ الكافي! سعر الأداة: **{price:,} ريال**")
        return

    update_wallet(ctx.author.id, -price)
    add_item(ctx.author.id, item_id, 1)
    await ctx.send(f"📦 تم شراء الأداة **[{item_id}]** بنجاح وتمت إضافتها لحقيبتك!")

@bot.command()
async def حقيبتي(ctx):
    cursor.execute("SELECT item_id, quantity FROM inventory WHERE user_id = ? AND quantity > 0", (ctx.author.id,))
    items = cursor.fetchall()
    if not items:
        await ctx.send("🎒 حقيبتك فارغة حالياً.")
        return
    embed = discord.Embed(title=f"🎒 حقيبة {ctx.author.display_name}", color=discord.Color.dark_purple())
    for i_id, qty in items:
        embed.add_field(name=f"📦 {i_id}", value=f"الكمية: **{qty}**", inline=True)
    await ctx.send(embed=embed)

# ---------------------------------------------------------
# 5. نظام التحديات والمواجهات المباشرة (PvP) ⚔️
# ---------------------------------------------------------
@bot.command()
async def روليت(ctx, member: discord.Member = None, amount: int = None):
    if not member or not amount or amount <= 0 or member.id == ctx.author.id: return
    w1, _, _, _, _ = get_user(ctx.author.id)
    w2, _, _, _, _ = get_user(member.id)

    if w1 < amount or w2 < amount:
        await ctx.send("❌ أحدهكما لا يملك المبلغ الكافي لتحدي الروليت!")
        return

    loser = random.choice([ctx.author, member])
    winner = member if loser == ctx.author else ctx.author

    update_wallet(loser.id, -amount)
    update_wallet(winner.id, amount)
    await ctx.send(f"🎲 **انتهت جولة الروليت الروسية!**\n💀 خسِر {loser.mention} المراهنة، وحصل {winner.mention} على **{amount:,} ريال**!")

@bot.command()
async def تحدي(ctx, member: discord.Member = None, amount: int = None, choice: str = None):
    choices = ["حجر", "ورقة", "مقص"]
    if not member or not amount or not choice or choice not in choices or member.id == ctx.author.id:
        await ctx.send("❌ الصيغة الصحيحة: `!تحدي @عضو 5000 حجر` (خياراتك: حجر / ورقة / مقص)")
        return

    w1, _, _, _, _ = get_user(ctx.author.id)
    w2, _, _, _, _ = get_user(member.id)
    if w1 < amount or w2 < amount:
        await ctx.send("❌ أحد الطرفين لا يملك المبلغ الكافي!")
        return

    bot_choice = random.choice(choices)
    await ctx.send(f"✂️ اختار المنافس {member.mention}: **{bot_choice}** مقابل اختيارك: **{choice}**")

    if choice == bot_choice:
        await ctx.send("🤝 تعادل! لم يخسر أي شخص أمواله.")
    elif (choice == "حجر" and bot_choice == "مقص") or (choice == "ورقة" and bot_choice == "حجر") or (choice == "مقص" and bot_choice == "ورقة"):
        update_wallet(member.id, -amount)
        update_wallet(ctx.author.id, amount)
        await ctx.send(f"🎉 **فزت بالتحدي!** وأخذت **{amount:,} ريال** من {member.mention}!")
    else:
        update_wallet(ctx.author.id, -amount)
        update_wallet(member.id, amount)
        await ctx.send(f"😭 **خسرت التحدي!** وتم تحويل **{amount:,} ريال** إلى {member.mention}.")

# تشغيل البوت
TOKEN = os.environ.get("BOT_TOKEN") or os.environ.get("BOT_TOKEN")
bot.run(TOKEN)
