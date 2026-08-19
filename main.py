import os
import random
import asyncio
import threading
from typing import Optional
from datetime import datetime, timedelta

import discord
from discord.ext import commands
from discord import app_commands
from flask import Flask

# ==========================================
# 1. إعداد خادم Web Service لمنع نوم Render
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "البوت يعمل بنجاح على الاستضافة السحابية!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

threading.Thread(target=run_flask, daemon=True).start()

# ==========================================
# 2. إعدادات البوت والـ Intents
# ==========================================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ⚠️ إزالة أمر help المدمج لمنع الخطأ الذي ظهر في اللوق
bot.remove_command("help")

# ==========================================
# 3. قواعد البيانات والبيانات الأساسية
# ==========================================
users_data = {}
gangs_data = {}

# سوق الأسهم المباشر (أسعار مبدئية)
STOCKS = {
    "ARAMCO": {"name": "أرامكو", "price": 100},
    "STC": {"name": "الاتصالات", "price": 50},
    "RAJHI": {"name": "مصرف الراجحي", "price": 80},
    "TESLA": {"name": "تسلا", "price": 200}
}

JOBS = {
    "مبتدئ": {"salary": 200, "next_job": "موظف", "req_exp": 5},
    "موظف": {"salary": 500, "next_job": "مشرف", "req_exp": 15},
    "مشرف": {"salary": 1200, "next_job": "مدير", "req_exp": 30},
    "مدير": {"salary": 3000, "next_job": "رئيس شركة", "req_exp": 60},
    "رئيس شركة": {"salary": 7000, "next_job": None, "req_exp": 999999}
}

CARS = {
    "كامري": 15000,
    "مرسيدس": 50000,
    "فراري": 120000,
    "لامبورغيني": 250000
}

HOUSES = {
    "شقة سكنية": 30000,
    "فيلا مدرجة": 100000,
    "قصر فخم": 500000
}

def get_user_data(user_id: int):
    if user_id not in users_data:
        users_data[user_id] = {
            "wallet": 1000,
            "bank": 0,
            "job": "مبتدئ",
            "job_exp": 0,
            "in_jail": False,
            "jail_release_time": None,
            "has_insurance": False,
            "insurance_expiry": None,
            "cars": [],
            "houses": [],
            "gang": None,
            "stocks": {} # {"ARAMCO": 5, "STC": 10}
        }
    return users_data[user_id]

# ==========================================
# 4. الواجهات التفاعلية (Buttons & Menus)
# ==========================================

class CarSelectMenu(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="كامري", description="السعر: $15,000", emoji="🚗"),
            discord.SelectOption(label="مرسيدس", description="السعر: $50,000", emoji="🚘"),
            discord.SelectOption(label="فراري", description="السعر: $120,000", emoji="🏎️"),
            discord.SelectOption(label="لامبورغيني", description="السعر: $250,000", emoji="🏎️"),
        ]
        super().__init__(placeholder="اختر سيارة لشرائها...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        data = get_user_data(user_id)
        car_name = self.values[0]
        price = CARS[car_name]

        if data["wallet"] < price:
            await interaction.response.send_message(f"❌ لا تملك المال الكافي لشراء **{car_name}**! (المطلوب: **${price:,}**)", ephemeral=True)
            return

        data["wallet"] -= price
        data["cars"].append(car_name)
        await interaction.response.send_message(f"🎉 مبروك! قمت بشراء **{car_name}** بنجاح مقابل **${price:,}**.", ephemeral=True)


class HouseSelectMenu(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="شقة سكنية", description="السعر: $30,000", emoji="🏢"),
            discord.SelectOption(label="فيلا مدرجة", description="السعر: $100,000", emoji="🏡"),
            discord.SelectOption(label="قصر فخم", description="السعر: $500,000", emoji="🏰"),
        ]
        super().__init__(placeholder="اختر عقاراً لشراءه...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        data = get_user_data(user_id)
        house_name = self.values[0]
        price = HOUSES[house_name]

        if data["wallet"] < price:
            await interaction.response.send_message(f"❌ لا تملك المال الكافي لشراء **{house_name}**! (المطلوب: **${price:,}**)", ephemeral=True)
            return

        data["wallet"] -= price
        data["houses"].append(house_name)
        await interaction.response.send_message(f"🎉 مبروك! قمت بشراء **{house_name}** بنجاح مقابل **${price:,}**.", ephemeral=True)


class MainStoreView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(CarSelectMenu())
        self.add_item(HouseSelectMenu())

    @discord.ui.button(label="عرض قائمة السيارات", style=discord.ButtonStyle.primary, emoji="🏎️")
    async def show_cars(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="🏎️ معرض السيارات الفاخرة", color=discord.Color.gold())
        for car, price in CARS.items():
            embed.add_field(name=f"🚗 {car}", value=f"السعر: **${price:,}**", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="عرض قائمة العقارات", style=discord.ButtonStyle.success, emoji="🏠")
    async def show_houses(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="🏠 سوق العقارات والمنازل", color=discord.Color.green())
        for house, price in HOUSES.items():
            embed.add_field(name=f"🏡 {house}", value=f"السعر: **${price:,}**", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class ProfileView(discord.ui.View):
    def __init__(self, user: discord.Member):
        super().__init__(timeout=60)
        self.user = user

    @discord.ui.button(label="تجديد التأمين ($2,000)", style=discord.ButtonStyle.green, emoji="🛡️")
    async def buy_insurance(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ لا يمكنك التحكم بملف شخص آخر!", ephemeral=True)
            return

        data = get_user_data(self.user.id)
        cost = 2000

        if data["wallet"] < cost:
            await interaction.response.send_message(f"❌ تحتاج **${cost}** كاش لتفعيل التأمين!", ephemeral=True)
            return

        data["wallet"] -= cost
        data["has_insurance"] = True
        data["insurance_expiry"] = datetime.now() + timedelta(days=3)
        await interaction.response.send_message("🛡️ تم تفعيل التأمين الشامل لمدة 3 أيام ضد السرقة والحوادث!", ephemeral=True)

# ==========================================
# 5. الأحداث
# ==========================================

@bot.event
async def on_ready():
    print(f"✅ تم تشغيل البوت بنجاح باسم: {bot.user.name}")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        hours, remainder = divmod(int(error.retry_after), 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours > 0:
            await ctx.send(f"⏳ هذا الأمر في فترة انتظار! حاول بعد **{hours} ساعة و {minutes} دقيقة**.")
        else:
            await ctx.send(f"⏳ يرجى الانتظار **{minutes} دقيقة و {seconds} ثانية**.")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ لا تملك الصلاحيات الكافية لاستخدام هذا الأمر!")

# ==========================================
# 6. نظام سوق الأسهم (Stock Market)
# ==========================================

@bot.command(name="الاسهم", aliases=["أسهم", "stocks"])
async def stocks_market(ctx):
    embed = discord.Embed(title="📈 سوق الأسهم المالي", color=discord.Color.blue())
    embed.description = "الأسعار تتغير عشوائياً! استخدم `!شراء_سهم` أو `!بيع_سهم` للتداول."
    
    for code, info in STOCKS.items():
        # تغيير سعر السهم عشوائياً قليلاً محاكاة للسوق
        change = random.randint(-5, 5)
        info["price"] = max(10, info["price"] + change)
        embed.add_field(name=f"{info['name']} ({code})", value=f"السعر الحالي: **${info['price']}**", inline=False)
        
    await ctx.send(embed=embed)

@bot.command(name="شراء_سهم")
async def buy_stock(ctx, code: str = None, amount: int = None):
    if not code or not amount or amount <= 0:
        await ctx.send("❌ الاستخدام الصحيح: `!شراء_سهم [رمز السهم] [العدد]`\nمثال: `!شراء_سهم ARAMCO 5`")
        return

    code = code.upper()
    if code not in STOCKS:
        await ctx.send("❌ رمز السهم غير صحيح! اكتب `!الاسهم` لرؤية الرموز المتاحة.")
        return

    stock = STOCKS[code]
    total_cost = stock["price"] * amount
    data = get_user_data(ctx.author.id)

    if data["wallet"] < total_cost:
        await ctx.send(f"❌ لا تملك المبلغ الكافي! تكلفة شراء {amount} أسهم في {stock['name']} هي **${total_cost:,}**.")
        return

    data["wallet"] -= total_cost
    data["stocks"][code] = data["stocks"].get(code, 0) + amount
    await ctx.send(f"✅ تم شراء **{amount}** أسهم في شركة **{stock['name']}** بنجاح مقابل **${total_cost:,}**!")

@bot.command(name="بيع_سهم")
async def sell_stock(ctx, code: str = None, amount: int = None):
    if not code or not amount or amount <= 0:
        await ctx.send("❌ الاستخدام الصحيح: `!بيع_سهم [رمز السهم] [العدد]`")
        return

    code = code.upper()
    data = get_user_data(ctx.author.id)
    owned = data["stocks"].get(code, 0)

    if owned < amount:
        await ctx.send(f"❌ لا تملك هذا العدد من الأسهم! عدد أسهمك في {code} هو **{owned}** فقط.")
        return

    stock = STOCKS[code]
    total_revenue = stock["price"] * amount

    data["stocks"][code] -= amount
    data["wallet"] += total_revenue
    await ctx.send(f"💵 تم بيع **{amount}** أسهم في شركة **{stock['name']}** بنجاح واستلمت **${total_revenue:,}**!")

# ==========================================
# 7. نظام المهن والعمل
# ==========================================

@bot.command(name="عمل", aliases=["work"])
@commands.cooldown(1, 3600, commands.BucketType.user)
async def work_cmd(ctx):
    data = get_user_data(ctx.author.id)

    if data["in_jail"]:
        if datetime.now() < data["jail_release_time"]:
            remaining = int((data["jail_release_time"] - datetime.now()).total_seconds() // 60)
            await ctx.send(f"🔒 أنت مسجون حالياً! باقي على إطلاق سراحك **{remaining} دقيقة**.")
            return
        else:
            data["in_jail"] = False

    job_info = JOBS[data["job"]]
    salary = job_info["salary"] + random.randint(10, 100)
    data["wallet"] += salary
    data["job_exp"] += 1

    msg = f"💼 عملت بوظيفتك كـ **{data['job']}** وحصلت على راتب **${salary:,}**!"

    next_job = job_info["next_job"]
    if next_job and data["job_exp"] >= job_info["req_exp"]:
        data["job"] = next_job
        msg += f"\n🎉 **مبروك!** تمت ترقيتك إلى مهنة: **{next_job}**!"

    await ctx.send(msg)

@bot.command(name="مهنتي", aliases=["job"])
async def my_job(ctx):
    data = get_user_data(ctx.author.id)
    job_info = JOBS[data["job"]]

    embed = discord.Embed(title=f"💼 المهنة - {ctx.author.display_name}", color=discord.Color.blue())
    embed.add_field(name="المهنة الحالية", value=data["job"], inline=True)
    embed.add_field(name="الخبرة الحالية", value=f"{data['job_exp']} نقطة", inline=True)
    embed.add_field(name="الراتب الأساسي", value=f"${job_info['salary']:,}", inline=False)
    await ctx.send(embed=embed)

# ==========================================
# 8. نظام الجرائم والسجن والتأمين
# ==========================================

@bot.command(name="سرقة", aliases=["rob"])
@commands.cooldown(1, 1800, commands.BucketType.user)
async def rob_cmd(ctx, target: discord.Member = None):
    if not target or target.id == ctx.author.id:
        await ctx.send("❌ حدد الشخص المُراد سرقته! مثال: `!سرقة @عضو`")
        return

    thief = get_user_data(ctx.author.id)
    victim = get_user_data(target.id)

    if thief["in_jail"]:
        await ctx.send("🔒 أنت مسجون حالياً ولا يمكنك السرقة!")
        return

    if victim["wallet"] < 500:
        await ctx.send("❌ الضحية مفلس تماماً ولا يملك كاش كافٍ!")
        return

    if victim["has_insurance"] and victim["insurance_expiry"] and datetime.now() < victim["insurance_expiry"]:
        thief["in_jail"] = True
        thief["jail_release_time"] = datetime.now() + timedelta(minutes=10)
        await ctx.send(f"🛡️ **فشلت السرقة!** {target.mention} لديه تأمين شامل! تم القبض على {ctx.author.mention} وسجنه 10 دقائق!")
        return

    if random.random() < 0.40:
        stolen = random.randint(200, int(victim["wallet"] * 0.35))
        victim["wallet"] -= stolen
        thief["wallet"] += stolen
        await ctx.send(f"🥷 **نجحت السرقة!** سرق {ctx.author.mention} مبلغ **${stolen:,}** من {target.mention}!")
    else:
        thief["in_jail"] = True
        thief["jail_release_time"] = datetime.now() + timedelta(minutes=5)
        await ctx.send(f"🚓 **قبضت عليك الشرطة!** تم سجن {ctx.author.mention} لمدة 5 دقائق!")

@bot.command(name="كفالة", aliases=["bail"])
async def bail_cmd(ctx):
    data = get_user_data(ctx.author.id)
    if not data["in_jail"]:
        await ctx.send("✅ أنت لست مسجوناً!")
        return

    cost = 2500
    if data["wallet"] < cost:
        await ctx.send(f"❌ قيمة الكفالة **${cost:,}** كاش، ولا تملك هذا المبلغ!")
        return

    data["wallet"] -= cost
    data["in_jail"] = False
    data["jail_release_time"] = None
    await ctx.send(f"🔓 تم دفع الكفالة (**${cost:,}**) وتم إطلاق سراحك!")

# ==========================================
# 9. نظام العصابات (Gang System)
# ==========================================

@bot.command(name="انشاء_عصابة")
async def create_gang(ctx, *, name: str = None):
    if not name:
        await ctx.send("❌ حدد اسم العصابة! مثال: `!انشاء_عصابة الفرسان`")
        return

    data = get_user_data(ctx.author.id)
    if data["wallet"] < 50000:
        await ctx.send("❌ تأسيس عصابة يتطلب **$50,000** كاش!")
        return

    if name in gangs_data:
        await ctx.send("❌ هذا الاسم مستخدم لعصابة أخرى!")
        return

    data["wallet"] -= 50000
    data["gang"] = name
    gangs_data[name] = {"owner": ctx.author.id, "members": [ctx.author.id], "bank": 0}
    await ctx.send(f"🏴‍☠️ تم تأسيس عصابة **{name}** بنجاح بواسطة {ctx.author.mention}!")

@bot.command(name="عصابتي")
async def my_gang(ctx):
    data = get_user_data(ctx.author.id)
    if not data["gang"]:
        await ctx.send("❌ أنت لست عضواً في أي عصابة!")
        return

    gang = gangs_data[data["gang"]]
    embed = discord.Embed(title=f"🏴‍☠️ عصابة: {data['gang']}", color=discord.Color.dark_red())
    embed.add_field(name="عدد الأعضاء", value=f"{len(gang['members'])} عضو", inline=True)
    embed.add_field(name="خزينة العصابة", value=f"${gang['bank']:,}", inline=True)
    await ctx.send(embed=embed)

# ==========================================
# 10. المتجر، البروفايل والمعاملات
# ==========================================

@bot.command(name="متجر", aliases=["معرض", "store", "shop"])
async def open_store(ctx):
    embed = discord.Embed(
        title="🛒 السوق والمعرض الشامل",
        description="استخدم الأزرار والقوائم المنسدلة أدناه لتصفح وشراء السيارات والعقارات:",
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed, view=MainStoreView())

@bot.command(name="بروفايل", aliases=["رصيدي", "profile", "bal"])
async def profile_cmd(ctx, member: discord.Member = None):
    target = member or ctx.author
    data = get_user_data(target.id)

    embed = discord.Embed(title=f"👤 بروفايل - {target.display_name}", color=discord.Color.purple())
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="💵 المحفظة", value=f"${data['wallet']:,}", inline=True)
    embed.add_field(name="🏦 البنك", value=f"${data['bank']:,}", inline=True)
    embed.add_field(name="💼 المهنة", value=data["job"], inline=True)
    embed.add_field(name="🏴‍☠️ العصابة", value=data["gang"] or "لا يوجد", inline=True)

    cars = ", ".join(data["cars"]) if data["cars"] else "لا يوجد"
    houses = ", ".join(data["houses"]) if data["houses"] else "لا يوجد"
    embed.add_field(name="🚗 السيارات", value=cars, inline=False)
    embed.add_field(name="🏠 العقارات", value=houses, inline=False)

    view = ProfileView(target)
    await ctx.send(embed=embed, view=view)

@bot.command(name="تحويل", aliases=["pay"])
async def transfer_cmd(ctx, member: discord.Member = None, amount: int = None):
    if not member or not amount or amount <= 0 or member.id == ctx.author.id:
        await ctx.send("❌ الاستخدام: `!تحويل @عضو المبلغ`")
        return

    sender = get_user_data(ctx.author.id)
    receiver = get_user_data(member.id)

    if sender["wallet"] < amount:
        await ctx.send("❌ لا تملك هذا المبلغ في المحفظة!")
        return

    sender["wallet"] -= amount
    receiver["wallet"] += amount
    await ctx.send(f"✅ تم تحويل **${amount:,}** بنجاح إلى {member.mention}.")

@bot.command(name="يومية", aliases=["daily"])
@commands.cooldown(1, 86400, commands.BucketType.user)
async def daily_cmd(ctx):
    data = get_user_data(ctx.author.id)
    reward = random.randint(1000, 3000)
    data["wallet"] += reward
    await ctx.send(f"🎁 استلمت مكافأتك اليومية بقيمة **${reward:,}**!")

# ==========================================
# 11. الأوامر الإدارية وأمر المساعدة
# ==========================================

@bot.command(name="اعطاء", aliases=["give"])
@commands.has_permissions(administrator=True)
async def admin_give(ctx, member: discord.Member = None, amount: int = None):
    if not member or not amount or amount <= 0:
        await ctx.send("❌ الاستخدام الإداري: `!اعطاء @عضو المبلغ`")
        return

    data = get_user_data(member.id)
    data["wallet"] += amount
    await ctx.send(f"👑 تم إعطاء **${amount:,}** إلى {member.mention} بواسطة الإدارة.")

@bot.command(name="تصفير", aliases=["reset"])
@commands.has_permissions(administrator=True)
async def admin_reset(ctx, target: Optional[discord.Member] = None):
    if target:
        users_data.pop(target.id, None)
        await ctx.send(f"⚙️ تم تصفير بيانات {target.mention}.")
    else:
        users_data.clear()
        await ctx.send("⚠️ تم تصفير جميع البيانات الاقتصادية للسيرفر!")

@bot.command(name="مساعدة", aliases=["اوامر"])
async def help_cmd(ctx):
    embed = discord.Embed(title="📜 قائمة أوامر البوت الاقتصادية", color=discord.Color.gold())
    embed.add_field(name="💼 الوظائف والمال", value="`!عمل` `!مهنتي` `!بروفايل` `!يومية` `!تحويل`", inline=False)
    embed.add_field(name="📈 تداول الأسهم", value="`!الاسهم` `!شراء_سهم` `!بيع_سهم`", inline=False)
    embed.add_field(name="🛒 المعرض والمتجر", value="`!متجر` (سيارات وعقارات عبر الأزرار والقوائم)", inline=False)
    embed.add_field(name="⚖️ الجرائم والعصابات", value="`!سرقة` `!كفالة` `!انشاء_عصابة` `!عصابتي`", inline=False)
    await ctx.send(embed=embed)

# ==========================================
# 12. تشغيل البوت
# ==========================================
TOKEN = os.environ.get("DISCORD_TOKEN") or os.environ.get("BOT_TOKEN")

if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ لم يتم العثور على التوكين!") 
