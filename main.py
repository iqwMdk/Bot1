import os
import sqlite3
import random
import time
import discord
from discord.ext import commands
from discord.ui import Button, View, Select

from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive and running!"

def keep_alive():
    t = Thread(target=lambda: app.run(host='0.0.0.0', port=8080))
    t.start()

# تشغيل الخادم الوهمي فوراً
keep_alive()

# إعداد البوت
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# ---------------------------------------------------------
# 1. إعداد قاعدة البيانات الشاملة
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
    gang_id INTEGER DEFAULT NULL,
    last_income_claim INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS properties (
    property_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    price INTEGER NOT NULL,
    daily_income INTEGER NOT NULL,
    owner_id INTEGER DEFAULT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS user_cars (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    car_name TEXT
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

# البيانات الإفتراضية
cursor.execute("INSERT OR IGNORE INTO settings VALUES ('immunity_price', 5000)")
cursor.execute("INSERT OR IGNORE INTO stocks VALUES ('TECH', 'شركة التكنولوجيا', 500)")
cursor.execute("INSERT OR IGNORE INTO stocks VALUES ('REAL', 'شركة العقارات', 1200)")
cursor.execute("INSERT OR IGNORE INTO stocks VALUES ('ENG', 'شركة الطاقة', 800)")

cursor.execute("SELECT COUNT(*) FROM properties")
if cursor.fetchone()[0] == 0:
    cursor.execute("INSERT INTO properties (name, price, daily_income) VALUES ('شقة فاخرة', 50000, 2500)")
    cursor.execute("INSERT INTO properties (name, price, daily_income) VALUES ('فيلا مودرن', 150000, 8000)")
    cursor.execute("INSERT INTO properties (name, price, daily_income) VALUES ('مجمع سكني', 500000, 30000)")

conn.commit()

# قائمة السيارات المتاحة
CARS = {
    "سسكي": {"price": 15000, "speed": "عادية"},
    "كامري": {"price": 45000, "speed": "متوسطة"},
    "جيب": {"price": 120000, "speed": "عالية"},
    "روز": {"price": 500000, "speed": "خارقة"}
}

# السرقات المتاحة للعصابات
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

def set_setting(key, value):
    cursor.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", (key, value))
    conn.commit()

# ---------------------------------------------------------
# 2. الواجهات والتفاعلات بالأزرار (UI Components)
# ---------------------------------------------------------

class BuyPropertySelect(Select):
    def __init__(self):
        cursor.execute("SELECT property_id, name, price, daily_income FROM properties WHERE owner_id IS NULL")
        props = cursor.fetchall()
        
        options = []
        if props:
            for p_id, name, price, income in props:
                options.append(discord.SelectOption(
                    label=f"{name} (#{p_id})",
                    description=f"السعر: {price:,} ريال | الدخل: {income:,} ريال",
                    value=str(p_id)
                ))
        else:
            options.append(discord.SelectOption(label="لا توجد عقارات متاحة للشراء", value="none"))

        super().__init__(placeholder="اختر عقاراً لشراءه...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.send_message("❌ لا توجد عقارات متاحة حالياً.", ephemeral=True)
            return

        prop_id = int(self.values[0])
        cursor.execute("SELECT name, price, owner_id FROM properties WHERE property_id = ?", (prop_id,))
        prop = cursor.fetchone()

        if not prop or prop[2] is not None:
            await interaction.response.send_message("❌ هذا العقار لم يعد متاحاً!", ephemeral=True)
            return

        name, price, _ = prop
        wallet, _, _, _, _ = get_user(interaction.user.id)

        if wallet < price:
            await interaction.response.send_message(f"❌ لا تملك المبلغ الكافي! تحتاج **{price:,} ريال**.", ephemeral=True)
            return

        update_wallet(interaction.user.id, -price)
        cursor.execute("UPDATE properties SET owner_id = ? WHERE property_id = ?", (interaction.user.id, prop_id))
        conn.commit()

        await interaction.response.send_message(f"🎉 **مبروك!** اشتريت **{name}** بمبلغ **{price:,} ريال**!", ephemeral=False)


class MainControlView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="💳 رصيدي", style=discord.ButtonStyle.primary, custom_id="btn_balance", row=0)
    async def balance_btn(self, interaction: discord.Interaction, button: Button):
        wallet, bank, dirty, immunity, _ = get_user(interaction.user.id)
        has_immunity = "🛡️ مفعلة" if immunity > time.time() else "❌ غير مفعلة"
        embed = discord.Embed(title=f"💳 رصيد {interaction.user.display_name}", color=discord.Color.gold())
        embed.add_field(name="💵 الكاش", value=f"{wallet:,} ريال", inline=True)
        embed.add_field(name="🏦 البنك", value=f"{bank:,} ريال", inline=True)
        embed.add_field(name="🧼 أموال سوداء", value=f"{dirty:,} ريال", inline=True)
        embed.add_field(name="🛡️ الحصانة", value=has_immunity, inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🏢 سوق العقارات", style=discord.ButtonStyle.success, custom_id="btn_props", row=0)
    async def props_btn(self, interaction: discord.Interaction, button: Button):
        cursor.execute("SELECT property_id, name, price, daily_income, owner_id FROM properties")
        props = cursor.fetchall()
        embed = discord.Embed(title="🏢 سوق العقارات المتاحة", color=discord.Color.blue())
        for p_id, name, price, income, owner_id in props:
            status = "🟢 متاح" if not owner_id else "🔴 مملوك"
            embed.add_field(name=f"#{p_id} - {name}", value=f"💰 السعر: **{price:,}** | 📈 الدخل: **{income:,}**\n📌 الحالة: {status}", inline=False)
        
        view = View()
        view.add_item(BuyPropertySelect())
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="🏎️ معرض السيارات", style=discord.ButtonStyle.primary, custom_id="btn_cars", row=0)
    async def cars_btn(self, interaction: discord.Interaction, button: Button):
        embed = discord.Embed(title="🏎️ معرض السيارات والدبابات المتاحة", color=discord.Color.gold())
        for car_name, info in CARS.items():
            embed.add_field(
                name=f"🚗 {car_name}", 
                value=f"💵 السعر: **{info['price']:,} ريال**\n⚡ السرعة: {info['speed']}", 
                inline=False
            )
        embed.set_footer(text="للشراء استخدم الأمر: !شراء_سيارة [اسم_السيارة]")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="💰 جمع أرباح العقارات", style=discord.ButtonStyle.success, custom_id="btn_claim_income", row=1)
    async def claim_income_btn(self, interaction: discord.Interaction, button: Button):
        cursor.execute("SELECT daily_income FROM properties WHERE owner_id = ?", (interaction.user.id,))
        props = cursor.fetchall()
        if not props:
            await interaction.response.send_message("❌ لا تمتلك عقارات لجمع أرباحها!", ephemeral=True)
            return

        cursor.execute("SELECT last_income_claim FROM users WHERE user_id = ?", (interaction.user.id,))
        last_claim = cursor.fetchone()[0] or 0

        if time.time() - last_claim < 86400:
            remaining = int((86400 - (time.time() - last_claim)) / 3600)
            await interaction.response.send_message(f"⏳ يمكنك جمع الأرباح بعد **{remaining} ساعة**.", ephemeral=True)
            return

        total_income = sum(p[0] for p in props)
        update_wallet(interaction.user.id, total_income)
        cursor.execute("UPDATE users SET last_income_claim = ? WHERE user_id = ?", (int(time.time()), interaction.user.id))
        conn.commit()
        await interaction.response.send_message(f"💵 تم جمع أرباحك بقيمة **{total_income:,} ريال** كاش!", ephemeral=True)

    @discord.ui.button(label="📈 سوق الأسهم", style=discord.ButtonStyle.secondary, custom_id="btn_stocks", row=1)
    async def stocks_btn(self, interaction: discord.Interaction, button: Button):
        cursor.execute("SELECT symbol, name, price FROM stocks")
        stocks = cursor.fetchall()
        embed = discord.Embed(title="📈 سوق الأسهم الاستثماري", color=discord.Color.blue())
        for sym, name, price in stocks:
            embed.add_field(name=f"{name} [{sym}]", value=f"💵 سعر السهم: **{price:,} ريال**", inline=False)
        embed.set_footer(text="للشراء استخدم: !شراء_سهم [الرمز] [العدد]")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🏴 عصابتي", style=discord.ButtonStyle.danger, custom_id="btn_my_gang", row=1)
    async def my_gang_btn(self, interaction: discord.Interaction, button: Button):
        _, _, _, _, gang_id = get_user(interaction.user.id)
        if not gang_id:
            await interaction.response.send_message("❌ أنت لست عضواً في أي عصابة.", ephemeral=True)
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
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🎟️ شراء تذكرة يانصيب", style=discord.ButtonStyle.secondary, custom_id="btn_lottery", row=1)
    async def lottery_btn(self, interaction: discord.Interaction, button: Button):
        cost = 1000
        wallet, _, _, _, _ = get_user(interaction.user.id)
        if wallet < cost:
            await interaction.response.send_message("❌ لا تملك 1,000 ريال كاش لشراء تذكرة!", ephemeral=True)
            return
        update_wallet(interaction.user.id, -cost)
        cursor.execute("INSERT INTO lottery VALUES (?)", (interaction.user.id,))
        conn.commit()
        await interaction.response.send_message("🎟️ تم شراء تذكرة يانصيب بنجاح!", ephemeral=True)

# ---------------------------------------------------------
# 3. الأحداث وقائمة الأوامر النصية
# ---------------------------------------------------------
@bot.event
async def on_ready():
    bot.add_view(MainControlView())
    print(f"✅ تم تشغيل البوت المحدث بنجاح باسم: {bot.user.name}")

@bot.command(name="لوحة", aliases=["العقارات", "الرئيسية", "الاوامر", "الأوامر", "مساعدة"])
async def open_panel(ctx):
    embed = discord.Embed(
        title="🏦 لوحة التحكم والاقتصاد الشاملة",
        description="يمكنك استخدام الأزرار أدناه للخدمات السريعة، أو كتابة الأوامر النصية الموضحة بالأسفل:",
        color=discord.Color.gold()
    )
    embed.add_field(
        name="💰 المال والبنك",
        value="`!رصيدي` | `!تحويل` | `!ايداع` | `!سحب` | `!يومية` | `!عمل` | `!التوب`",
        inline=False
    )
    embed.add_field(
        name="🏢 العقارات والأعمال",
        value="`!العقارات` | `!شراء عقار [الرقم]` | `!عقاراتي` | `!جمع ارباح`",
        inline=False
    )
    embed.add_field(
        name="🏎️ السيارات والمركبات",
        value="`!معرض_السيارات` | `!شراء_سيارة [الاسم]` | `!سياراتي`",
        inline=False
    )
    embed.add_field(
        name="💀 العصابات والسوق الأسود",
        value="`!انشاء عصابة [الاسم]` | `!العصابات` | `!عصابتي` | `!دعوة @عضو المبلغ` | `!قبول` | `!طرد @عضو` | `!مغادرة` | `!السرقات` | `!بدء_سرقة [الرقم]`",
        inline=False
    )
    embed.add_field(
        name="📈 الاستثمار والألعاب",
        value="`!الاسهم` | `!شراء_سهم [الرمز] [العدد]` | `!بيع_سهم [الرمز] [العدد]` | `!سرقة @عضو` | `!غسيل [المبلغ]` | `!حصانة` | `!مزايدة [المبلغ]` | `!اليانصيب`",
        inline=False
    )
    embed.add_field(
        name="⚙️ الأوامر الإدارية (للإدارة)",
        value="`!اعطاء @عضو المبلغ` | `!خصم @عضو المبلغ` | `!تصفير @عضو` | `!تصفير الكل` | `!تحديد_الحصانة المبلغ` | `!اضافة_عقار [الاسم] [السعر] [الدخل]` | `!حذف_عقار [الرقم]` | `!سحب_عقار [الرقم]` | `!تحديث_الاسهم` | `!بدء_مزاد [السلعة] [السعر]` | `!انهاء_المزاد` | `!سحب_اليانصيب`",
        inline=False
    )
    await ctx.send(embed=embed, view=MainControlView())

# ---------------------------------------------------------
# 4. الأوامر العامة والأفراد
# ---------------------------------------------------------

@bot.command(name="رصيدي", aliases=["رصيد", "فلوسي"])
async def my_balance(ctx):
    wallet, bank, dirty, immunity, _ = get_user(ctx.author.id)
    has_immunity = "🛡️ مفعلة" if immunity > time.time() else "❌ غير مفعلة"
    embed = discord.Embed(title=f"💳 رصيد {ctx.author.display_name}", color=discord.Color.green())
    embed.add_field(name="💵 الكاش", value=f"{wallet:,} ريال", inline=True)
    embed.add_field(name="🏦 البنك", value=f"{bank:,} ريال", inline=True)
    embed.add_field(name="🧼 فلوس سوداء", value=f"{dirty:,} ريال", inline=True)
    embed.add_field(name="🛡️ الحصانة", value=has_immunity, inline=True)
    await ctx.send(embed=embed)

@bot.command(name="تحويل")
async def transfer_money(ctx, member: discord.Member = None, amount: int = None):
    if not member or not amount or amount <= 0 or member.id == ctx.author.id:
        await ctx.send("❌ الصيغة الصحيحة: `!تحويل @العضو المبلغ`")
        return
    wallet, _, _, _, _ = get_user(ctx.author.id)
    if wallet < amount:
        await ctx.send("❌ لا تملك المبلغ الكافي في الكاش!")
        return
    update_wallet(ctx.author.id, -amount)
    update_wallet(member.id, amount)
    await ctx.send(f"✅ تم تحويل **{amount:,} ريال** إلى {member.mention}.")

@bot.command(name="ايداع")
async def deposit_money(ctx, amount: int = None):
    if not amount or amount <= 0:
        await ctx.send("❌ الصيغة الصحيحة: `!ايداع المبلغ`")
        return
    wallet, _, _, _, _ = get_user(ctx.author.id)
    if wallet < amount:
        await ctx.send("❌ لا تملك هذا المبلغ في الكاش!")
        return
    update_wallet(ctx.author.id, -amount)
    update_bank(ctx.author.id, amount)
    await ctx.send(f"🏦 تم إيداع **{amount:,} ريال** في البنك.")

@bot.command(name="سحب")
async def withdraw_money(ctx, amount: int = None):
    if not amount or amount <= 0:
        await ctx.send("❌ الصيغة الصحيحة: `!سحب المبلغ`")
        return
    _, bank, _, _, _ = get_user(ctx.author.id)
    if bank < amount:
        await ctx.send("❌ لا تملك هذا المبلغ في البنك!")
        return
    update_bank(ctx.author.id, -amount)
    update_wallet(ctx.author.id, amount)
    await ctx.send(f"💵 تم سحب **{amount:,} ريال** من البنك.")

@bot.command(name="يومية")
@commands.cooldown(1, 86400, commands.BucketType.user)
async def daily_reward(ctx):
    update_wallet(ctx.author.id, 500)
    await ctx.send("🎉 حصلت على مكافأتك اليومية بقيمة **500 ريال**!")

@bot.command(name="عمل")
@commands.cooldown(1, 3600, commands.BucketType.user)
async def work_cmd(ctx):
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

@bot.command(name="عقاراتي")
async def my_properties(ctx):
    cursor.execute("SELECT property_id, name, daily_income FROM properties WHERE owner_id = ?", (ctx.author.id,))
    props = cursor.fetchall()
    if not props:
        await ctx.send("🏚️ أنت لا تمتلك أي عقارات حالياً.")
        return
    embed = discord.Embed(title=f"🏢 عقارات {ctx.author.display_name}", color=discord.Color.green())
    total_income = 0
    for p_id, name, income in props:
        embed.add_field(name=f"#{p_id} - {name}", value=f"📈 الدخل اليومي: **{income:,} ريال**", inline=False)
        total_income += income
    embed.set_footer(text=f"إجمالي الدخل اليومي: {total_income:,} ريال")
    await ctx.send(embed=embed)

# ---------------------------------------------------------
# 5. أوامر المعرض والسيارات
# ---------------------------------------------------------

@bot.command(name="معرض_السيارات", aliases=["السيارات", "معرض", "معرض السيارات"])
async def show_cars(ctx):
    embed = discord.Embed(title="🏎️ معرض السيارات والدبابات", color=discord.Color.gold())
    for car_name, info in CARS.items():
        embed.add_field(
            name=f"🚗 {car_name}", 
            value=f"💵 السعر: **{info['price']:,} ريال**\n⚡ السرعة: {info['speed']}", 
            inline=False
        )
    embed.set_footer(text="الشراء عبر الأمر: !شراء_سيارة [اسم_السيارة]")
    await ctx.send(embed=embed)

@bot.command(name="شراء_سيارة", aliases=["شراء سيارة", "شراء_سياره", "شراء سياره"])
async def buy_car(ctx, car_name: str = None):
    if not car_name or car_name not in CARS:
        await ctx.send("❌ يرجى كتابة اسم المركبة بشكل صحيح من المعرض!\nمثال: `!شراء سيارة كامري` أو `!شراء سيارة دباب`")
        return
    
    price = CARS[car_name]["price"]
    wallet, _, _, _, _ = get_user(ctx.author.id)
    
    if wallet < price:
        await ctx.send(f"❌ رصيدك غير كافٍ! تحتاج إلى **{price:,} ريال** كاش لشراء {car_name}.")
        return
    
    update_wallet(ctx.author.id, -price)
    cursor.execute("INSERT INTO user_cars (user_id, car_name) VALUES (?, ?)", (ctx.author.id, car_name))
    conn.commit()
    
    await ctx.send(f"🎉 ألف مبروك! قمت بشراء **{car_name}** بسعر **{price:,} ريال**!")

@bot.command(name="سياراتي", aliases=["مركباتي", "كراج"])
async def my_cars(ctx):
    cursor.execute("SELECT car_name FROM user_cars WHERE user_id = ?", (ctx.author.id,))
    cars = cursor.fetchall()
    
    if not cars:
        await ctx.send("🚗 أنت لا تمتلك أي سيارات أو دبابات حالياً.")
        return
        
    car_list = "\n".join([f"• 🚗 {car[0]}" for car in cars])
    embed = discord.Embed(title=f"🏎️ كراج {ctx.author.display_name}", description=car_list, color=discord.Color.blue())
    await ctx.send(embed=embed)

# ---------------------------------------------------------
# 6. أوامر العصابات
# ---------------------------------------------------------
@bot.command(name="انشاء_عصابة", aliases=["انشاء", "إنشاء", "انشاء عصابة"])
async def create_gang(ctx, *, name: str = None):
    if not name:
        await ctx.send("❌ الصيغة الصحيحة: `!انشاء_عصابة [اسم_العصابة]`")
        return
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
        await ctx.send("❌ فقط رئيس العصابة يمكنه تقديم عقود للأعضاء!")
        return

    if vault < contract_amount:
        await ctx.send(f"❌ خزينة العصابة لا تكفي! المتوفر: **{vault:,} ريال**.")
        return

    _, _, _, _, target_gang = get_user(member.id)
    if target_gang:
        await ctx.send("❌ هذا العضو ينتمي لعصابة أخرى بالفعل!")
        return

    cursor.execute("INSERT OR REPLACE INTO gang_invites VALUES (?, ?, ?)", (member.id, gang_id, contract_amount))
    conn.commit()
    await ctx.send(f"📜 تم إرسال عقد انضمام لـ {member.mention} للانضمام لعصابة **[{g_name}]** بمبلغ **{contract_amount:,} ريال**!\nللقبول اكتب: `!قبول`")

@bot.command(name="قبول")
async def accept_invite(ctx):
    cursor.execute("SELECT gang_id, contract_amount FROM gang_invites WHERE user_id = ?", (ctx.author.id,))
    invite = cursor.fetchone()
    
    if not invite:
        await ctx.send("❌ لا توجد لديك أي عقود معلقة!")
        return

    gang_id, contract_amount = invite
    cursor.execute("SELECT name, vault FROM gangs WHERE gang_id = ?", (gang_id,))
    g_name, vault = cursor.fetchone()

    if vault < contract_amount:
        await ctx.send("❌ أفلست خزينة العصابة ولم تعد تستطيع دفع قيمة العقد!")
        return

    cursor.execute("UPDATE gangs SET vault = vault - ? WHERE gang_id = ?", (contract_amount, gang_id))
    cursor.execute("UPDATE users SET gang_id = ? WHERE user_id = ?", (gang_id, ctx.author.id))
    cursor.execute("DELETE FROM gang_invites WHERE user_id = ?", (ctx.author.id,))
    conn.commit()

    update_wallet(ctx.author.id, contract_amount)
    await ctx.send(f"🎉 انضم {ctx.author.mention} إلى عصابة **[{g_name}]** واستلم **{contract_amount:,} ريال**!")

@bot.command(name="طرد")
async def kick_gang_member(ctx, member: discord.Member = None):
    if not member:
        await ctx.send("❌ الصيغة الصحيحة: `!طرد @العضو`")
        return
    _, _, _, _, gang_id = get_user(ctx.author.id)
    if not gang_id:
        await ctx.send("❌ أنت لست في عصابة!")
        return

    cursor.execute("SELECT leader_id FROM gangs WHERE gang_id = ?", (gang_id,))
    leader_id = cursor.fetchone()[0]

    if ctx.author.id != leader_id:
        await ctx.send("❌ فقط رئيس العصابة يمكنه طرد الأعضاء!")
        return

    if member.id == ctx.author.id:
        await ctx.send("❌ لا يمكنك طرد نفسك!")
        return

    cursor.execute("UPDATE users SET gang_id = NULL WHERE user_id = ? AND gang_id = ?", (member.id, gang_id))
    conn.commit()
    await ctx.send(f"🚪 تم طرد {member.mention} من العصابة.")

@bot.command(name="مغادرة")
async def leave_gang(ctx):
    _, _, _, _, gang_id = get_user(ctx.author.id)
    if not gang_id:
        await ctx.send("❌ أنت لست عضواً في أي عصابة!")
        return

    cursor.execute("SELECT leader_id FROM gangs WHERE gang_id = ?", (gang_id,))
    leader_id = cursor.fetchone()[0]

    if ctx.author.id == leader_id:
        await ctx.send("❌ القائد لا يستطيع المغادرة! يمكنك حل العصابة بدلاً من ذلك.")
        return

    cursor.execute("UPDATE users SET gang_id = NULL WHERE user_id = ?", (ctx.author.id,))
    conn.commit()
    await ctx.send("🚪 لقد غادرت العصابة بنجاح.")

@bot.command(name="السرقات")
async def list_heists(ctx):
    embed = discord.Embed(title="💣 قائمة سرقات العصابات المتاحة (للرؤساء)", color=discord.Color.red())
    for h_id, info in GANG_HEISTS.items():
        embed.add_field(
            name=f"#{h_id} - {info['name']}",
            value=f"💵 الأرباح المحتملة: **{info['min_loot']:,} - {info['max_loot']:,} ريال**\n🎯 نسبة النجاح الأساسية: **{int(info['base_chance']*100)}%**",
            inline=False
        )
    embed.set_footer(text="لبدء سرقة اكتب: !بدء_سرقة [رقم_السرقة]")
    await ctx.send(embed=embed)

@bot.command(name="بدء_سرقة", aliases=["بدء سرقة", "بداية_سرقة"])
@commands.cooldown(1, 10800, commands.BucketType.guild)
async def start_heist(ctx, heist_id: int = None):
    if heist_id in GANG_HEISTS:
        _, _, _, _, gang_id = get_user(ctx.author.id)
        if not gang_id:
            await ctx.send("❌ يجب أن تكون في عصابة لتنفذ سرقة!")
            return

        cursor.execute("SELECT leader_id, name FROM gangs WHERE gang_id = ?", (gang_id,))
        leader_id, g_name = cursor.fetchone()

        if ctx.author.id != leader_id:
            await ctx.send("❌ فقط رئيس العصابة يمكنه بدء السرقات!")
            return

        cursor.execute("SELECT user_id FROM users WHERE gang_id = ?", (gang_id,))
        members = cursor.fetchall()
        member_count = len(members)

        heist = GANG_HEISTS[heist_id]
        final_chance = min(heist["base_chance"] + ((member_count - 1) * 0.05), 0.90)

        if random.random() <= final_chance:
            total_loot = random.randint(heist["min_loot"], heist["max_loot"])
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
            await ctx.send(f"🚓 **فشلت عملية {heist['name']}!** تم إحباط الخطة من قبل الشرطة!")
    else:
        await ctx.send("❌ يرجى تحديد رقم سرقة صحيح من القائمة (`!السرقات`).")

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

# ---------------------------------------------------------
# 7. الأسهم، الغسيل، والسرقات الفردية
# ---------------------------------------------------------
@bot.command(name="الاسهم", aliases=["أسهم", "الأسهم"])
async def show_stocks(ctx):
    cursor.execute("SELECT symbol, name, price FROM stocks")
    stocks = cursor.fetchall()
    embed = discord.Embed(title="📈 سوق الأسهم الاستثماري", color=discord.Color.blue())
    for sym, name, price in stocks:
        embed.add_field(name=f"{name} [{sym}]", value=f"💵 سعر السهم: **{price:,} ريال**", inline=False)
    embed.set_footer(text="للشراء استخدم: !شراء_سهم [الرمز] [العدد]")
    await ctx.send(embed=embed)

@bot.command(name="شراء_سهم", aliases=["شراء سهم"])
async def buy_stock(ctx, symbol: str = None, count: int = 1):
    if not symbol:
        await ctx.send("❌ الصيغة الصحيحة: `!شراء_سهم [الرمز] [العدد]`")
        return
    symbol = symbol.upper()
    cursor.execute("SELECT price, name FROM stocks WHERE symbol = ?", (symbol,))
    stock = cursor.fetchone()
    if not stock:
        await ctx.send("❌ لم يتم العثور على شركة بهذا الرمز!")
        return
    price, name = stock
    total_cost = price * count
    wallet, _, _, _, _ = get_user(ctx.author.id)
    if wallet < total_cost:
        await ctx.send("❌ لا تملك المال الكافي لشراء هذه الأسهم!")
        return
    update_wallet(ctx.author.id, -total_cost)
    cursor.execute("INSERT INTO user_stocks VALUES (?, ?, ?) ON CONFLICT(user_id, symbol) DO UPDATE SET shares = shares + ?", (ctx.author.id, symbol, count, count))
    conn.commit()
    await ctx.send(f"✅ تم شراء **{count}** أسهم في **{name}** بـ **{total_cost:,} ريال**!")

@bot.command(name="بيع_سهم", aliases=["بيع سهم"])
async def sell_stock(ctx, symbol: str = None, count: str = "1"):
    if not symbol:
        await ctx.send("❌ الصيغة الصحيحة: `!بيع_سهم [الرمز] [العدد أو الكل]`")
        return
    symbol = symbol.upper()
    cursor.execute("SELECT shares FROM user_stocks WHERE user_id = ? AND symbol = ?", (ctx.author.id, symbol))
    res = cursor.fetchone()
    if not res or res[0] <= 0:
        await ctx.send("❌ لا تملك أسهماً في هذه الشركة!")
        return

    owned = res[0]
    sell_count = owned if count.lower() in ["الكل", "all"] else int(count)

    if owned < sell_count or sell_count <= 0:
        await ctx.send("❌ لا تملك هذا العدد من الأسهم لبيعه!")
        return

    cursor.execute("SELECT price, name FROM stocks WHERE symbol = ?", (symbol,))
    price, name = cursor.fetchone()
    total_return = price * sell_count
    cursor.execute("UPDATE user_stocks SET shares = shares - ? WHERE user_id = ? AND symbol = ?", (sell_count, ctx.author.id, symbol))
    conn.commit()
    update_wallet(ctx.author.id, total_return)
    await ctx.send(f"💵 تم بيع **{sell_count}** أسهم بـ **{total_return:,} ريال**!")

@bot.command(name="اسهمي")
async def my_stocks(ctx):
    cursor.execute("SELECT us.symbol, s.name, us.shares, s.price FROM user_stocks us JOIN stocks s ON us.symbol = s.symbol WHERE us.user_id = ? AND us.shares > 0", (ctx.author.id,))
    stocks = cursor.fetchall()
    if not stocks:
        await ctx.send("📊 لا تمتلك أي أسهم حالياً.")
        return
    embed = discord.Embed(title=f"📊 محفظة {ctx.author.display_name}", color=discord.Color.teal())
    for sym, name, shares, price in stocks:
        embed.add_field(name=f"{name} [{sym}]", value=f"📦 العدد: **{shares}** | 💰 القيمة: **{shares * price:,} ريال**", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="غسيل")
async def wash_money(ctx, amount: int = None):
    if not amount or amount <= 0:
        await ctx.send("❌ الصيغة الصحيحة: `!غسيل المبلغ`")
        return
    _, _, dirty, _, _ = get_user(ctx.author.id)
    if dirty < amount:
        await ctx.send("❌ لا تملك هذا المبلغ من الأموال السوداء!")
        return
    if random.random() <= 0.10:
        update_dirty_money(ctx.author.id, -amount)
        await ctx.send(f"🚨 **تم مصادرة {amount:,} ريال سوداء من قبل الشرطة!**")
        return
    clean_amount = int(amount * 0.85)
    update_dirty_money(ctx.author.id, -amount)
    update_wallet(ctx.author.id, clean_amount)
    await ctx.send(f"🧼 **تمت العملية!** تحول المبلغ إلى **{clean_amount:,} ريال** كاش.")

@bot.command(name="سرقة")
@commands.cooldown(1, 7200, commands.BucketType.user)
async def rob_user(ctx, target: discord.Member = None):
    if not target or target.id == ctx.author.id:
        await ctx.send("❌ الصيغة الصحيحة: `!سرقة @العضو`")
        return
    s_wallet, _, _, _, _ = get_user(ctx.author.id)
    t_wallet, _, _, t_immunity, _ = get_user(target.id)
    if t_immunity > time.time():
        await ctx.send("🛡️ هذا الشخص محمي بالحصانة!")
        return
    if t_wallet < 200:
        await ctx.send("❌ هذا الشخص لا يملك مالاً كافياً لسرقته!")
        return

    if random.random() <= 0.35:
        stolen = random.randint(100, int(t_wallet * 0.5))
        update_wallet(target.id, -stolen)
        update_dirty_money(ctx.author.id, stolen)
        await ctx.send(f"🥷 سرقت **{stolen:,} ريال** أموال سوداء من {target.mention}!")
    else:
        penalty = min(s_wallet, random.randint(100, 500))
        update_wallet(ctx.author.id, -penalty)
        update_wallet(target.id, penalty)
        await ctx.send(f"🚨 تم القبض عليك وغرمت **{penalty:,} ريال** لصالح {target.mention}!")

@bot.command(name="حصانة")
async def buy_immunity(ctx):
    price = get_setting('immunity_price', 5000)
    wallet, _, _, immunity, _ = get_user(ctx.author.id)
    if immunity > time.time():
        await ctx.send("🛡️ الحصانة مفعلة لديك بالفعل!")
        return
    if wallet < price:
        await ctx.send(f"❌ تكلفة الحصانة **{price:,} ريال**!")
        return
    update_wallet(ctx.author.id, -price)
    until = int(time.time()) + 86400
    cursor.execute("UPDATE users SET immunity_until = ? WHERE user_id = ?", (until, ctx.author.id))
    conn.commit()
    await ctx.send("🛡️ تم تفعيل الحصانة لمدة 24 ساعة!")

@bot.command(name="مزايدة")
async def bid_auction(ctx, amount: int = None):
    if not current_auction["active"]:
        await ctx.send("❌ لا يوجد مزاد قائم حالياً!")
        return
    if not amount or amount <= current_auction["highest_bid"]:
        await ctx.send(f"❌ يجب أن تزايد بمبلغ أكبر من **{current_auction['highest_bid']:,} ريال**!")
        return
    wallet, _, _, _, _ = get_user(ctx.author.id)
    if wallet < amount:
        await ctx.send("❌ لا تملك هذا المبلغ في الكاش!")
        return
    current_auction["highest_bid"] = amount
    current_auction["highest_bidder"] = ctx.author
    await ctx.send(f"🔨 {ctx.author.mention} رفع السعر لـ **{amount:,} ريال**!")

@bot.command(name="اليانصيب")
async def show_lottery(ctx):
    cursor.execute("SELECT COUNT(*) FROM lottery")
    tickets = cursor.fetchone()[0]
    await ctx.send(f"🎟️ إجمالي التذاكر المباعة: **{tickets}** | الجائزة الكبرى الحالية: **{tickets * 1000:,} ريال**!")

# ---------------------------------------------------------
# 8. الأوامر الإدارية الكاملة (Admin Commands)
# ---------------------------------------------------------

@bot.command(name="اعطاء", aliases=["إعطاء"])
@commands.has_permissions(administrator=True)
async def give_money(ctx, member: discord.Member = None, amount: int = None):
    if not member or not amount:
        await ctx.send("❌ الصيغة الصحيحة: `!اعطاء @العضو المبلغ`")
        return
    update_wallet(member.id, amount)
    await ctx.send(f"✅ تم إضافة **{amount:,} ريال** إلى حساب {member.mention}.")

@bot.command(name="خصم")
@commands.has_permissions(administrator=True)
async def remove_money(ctx, member: discord.Member = None, amount: int = None):
    if not member or not amount:
        await ctx.send("❌ الصيغة الصحيحة: `!خصم @العضو المبلغ`")
        return
    update_wallet(member.id, -amount)
    await ctx.send(f"✅ تم خصم **{amount:,} ريال** من حساب {member.mention}.")

@bot.command(name="تصفير")
@commands.has_permissions(administrator=True)
async def reset_user(ctx, target: str = None, member: discord.Member = None):
    if target == "الكل":
        cursor.execute("UPDATE users SET wallet = 100, bank = 0, dirty_money = 0")
        conn.commit()
        await ctx.send("⚠️ **تم تصفير جميع أرصدة الأعضاء بالسيرفر!**")
    elif member:
        cursor.execute("UPDATE users SET wallet = 100, bank = 0, dirty_money = 0 WHERE user_id = ?", (member.id,))
        conn.commit()
        await ctx.send(f"✅ تم تصفير حساب {member.mention} بنجاح.")
    else:
        await ctx.send("❌ الصيغة الصحيحة: `!تصفير الكل` أو `!تصفير شخص @العضو`")

@bot.command(name="تحديد_الحصانة", aliases=["تحديد الحصانة"])
@commands.has_permissions(administrator=True)
async def set_immunity_price(ctx, price: int = None):
    if not price or price <= 0:
        await ctx.send("❌ الصيغة الصحيحة: `!تحديد_الحصانة [السعر]`")
        return
    set_setting('immunity_price', price)
    await ctx.send(f"⚙️ تم تغيير سعر شراء الحصانة إلى **{price:,} ريال**.")

@bot.command(name="اضافة_عقار", aliases=["اضافة عقار", "إضافة_عقار"])
@commands.has_permissions(administrator=True)
async def add_property(ctx, name: str = None, price: int = None, income: int = None):
    if not name or not price or not income:
        await ctx.send("❌ الصيغة الصحيحة: `!اضافة_عقار [الاسم] [السعر] [الدخل]`")
        return
    cursor.execute("INSERT INTO properties (name, price, daily_income) VALUES (?, ?, ?)", (name, price, income))
    conn.commit()
    await ctx.send(f"🏢 تم إضافة عقار جديد: **{name}** بسعر **{price:,}** ودخل **{income:,}**.")

@bot.command(name="حذف_عقار", aliases=["حذف عقار"])
@commands.has_permissions(administrator=True)
async def delete_property_cmd(ctx, prop_id: int = None):
    if not prop_id:
        await ctx.send("❌ الصيغة الصحيحة: `!حذف_عقار [رقم_العقار]`")
        return
    cursor.execute("SELECT name FROM properties WHERE property_id = ?", (prop_id,))
    prop = cursor.fetchone()
    if not prop:
        await ctx.send("❌ لم يتم العثور على عقار بهذا الرقم!")
        return
    cursor.execute("DELETE FROM properties WHERE property_id = ?", (prop_id,))
    conn.commit()
    await ctx.send(f"🗑️ تم حذف العقار **{prop[0]}** (رقم #{prop_id}) نهائياً.")

@bot.command(name="سحب_عقار", aliases=["سحب عقار"])
@commands.has_permissions(administrator=True)
async def revoke_property_cmd(ctx, prop_id: int = None):
    if not prop_id:
        await ctx.send("❌ الصيغة الصحيحة: `!سحب_عقار [رقم_العقار]`")
        return
    cursor.execute("SELECT name, owner_id FROM properties WHERE property_id = ?", (prop_id,))
    prop = cursor.fetchone()
    if not prop:
        await ctx.send("❌ لم يتم العثور على عقار بهذا الرقم!")
        return
    if prop[1] is None:
        await ctx.send("❌ هذا العقار غير مملوك لأحد بالفعل!")
        return
    cursor.execute("UPDATE properties SET owner_id = NULL WHERE property_id = ?", (prop_id,))
    conn.commit()
    await ctx.send(f"🏢 تم سحب ملكية العقار **{prop[0]}** (رقم #{prop_id}) وإعادة عرضه للبيع.")

@bot.command(name="تحديث_الاسهم", aliases=["تحديث_أسهم", "تحديث الأسهم", "تحديث الاسهم"])
@commands.has_permissions(administrator=True)
async def update_stocks_price(ctx):
    cursor.execute("SELECT symbol, price FROM stocks")
    stocks = cursor.fetchall()
    for sym, price in stocks:
        change = random.choice([-0.15, -0.05, 0.05, 0.15])
        new_price = max(10, int(price * (1 + change)))
        cursor.execute("UPDATE stocks SET price = ? WHERE symbol = ?", (new_price, sym))
    conn.commit()
    await ctx.send("📈📉 تم تحديث أسعار الأسهم بنجاح!")

@bot.command(name="بدء_مزاد", aliases=["بدء مزاد", "بداية_مزاد"])
@commands.has_permissions(administrator=True)
async def start_auction_cmd(ctx, item: str = None, start_price: int = 1000):
    if not item:
        await ctx.send("❌ الصيغة الصحيحة: `!بدء_مزاد [السلعة] [السعر_الابتدائي]`")
        return
    current_auction["item"] = item
    current_auction["highest_bid"] = start_price
    current_auction["highest_bidder"] = None
    current_auction["active"] = True
    await ctx.send(f"🔨 **بدأ المزاد!** السلعة: **{item}** | بدء المزاد بـ **{start_price:,} ريال**!")

@bot.command(name="انهاء_المزاد", aliases=["انهاء المزاد", "إنهاء_المزاد"])
@commands.has_permissions(administrator=True)
async def end_auction_cmd(ctx):
    if not current_auction["active"]:
        await ctx.send("❌ لا يوجد مزاد قائم حالياً لإنهائه!")
        return
    current_auction["active"] = False
    winner = current_auction["highest_bidder"]
    bid = current_auction["highest_bid"]
    item = current_auction["item"]
    if winner:
        update_wallet(winner.id, -bid)
        await ctx.send(f"🎉 الفائز بالمزاد هو {winner.mention} بـ **{item}** مقابل **{bid:,} ريال**!")
    else:
        await ctx.send("🔨 انتهى المزاد دون وجود أي مزايدات.")

@bot.command(name="سحب_اليانصيب", aliases=["سحب اليانصيب"])
@commands.has_permissions(administrator=True)
async def draw_lottery_cmd(ctx):
    cursor.execute("SELECT user_id FROM lottery")
    tickets = cursor.fetchall()
    if not tickets:
        await ctx.send("🎟️ لم يتم شراء أي تذاكر بعد.")
        return
    winner_id = random.choice(tickets)[0]
    total_jackpot = len(tickets) * 1000
    update_wallet(winner_id, total_jackpot)
    cursor.execute("DELETE FROM lottery")
    conn.commit()
    winner = bot.get_user(winner_id)
    w_name = winner.mention if winner else f"مستخدم ({winner_id})"
    await ctx.send(f"🎉 الفائز بالجائزة الكبرى لليانصيب هو {w_name} بـ **{total_jackpot:,} ريال**!")

# تشغيل البوت
TOKEN = os.environ.get("BOT_TOKEN") or os.environ.get("DISCORD_TOKEN")
bot.run(TOKEN)
