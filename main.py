import os
import random
import asyncio
from typing import Optional
from datetime import datetime, timedelta

import discord
from discord.ext import commands
from discord import app_commands

from flask import Flask
from threading import Thread

# ==========================================
# 1. إعداد خادم Web Service لمنع نوم Render
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "البوت يعمل بنجاح على الاستضافة السحابية!"

def keep_alive():
    t = Thread(target=lambda: app.run(host='0.0.0.0', port=8080))
    t.start()

keep_alive()

# ==========================================
# 2. إعدادات البوت والـ Intents
# ==========================================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ==========================================
# 3. قاعدة البيانات المؤقتة (في الذاكرة)
# ==========================================
# بيانات المستخدمين
users_data = {}

# قائمة المهن المتاحة وترقياتها
JOBS = {
    "مبتدئ": {"salary": 200, "next_job": "موظف", "req_exp": 5},
    "موظف": {"salary": 500, "next_job": "مشرف", "req_exp": 15},
    "مشرف": {"salary": 1200, "next_job": "مدير", "req_exp": 30},
    "مدير": {"salary": 3000, "next_job": "رئيس شركة", "req_exp": 60},
    "رئيس شركة": {"salary": 7000, "next_job": None, "req_exp": 999999}
}

# قائمة السيارات للعرض والشراء
CARS = {
    "كامري": 15000,
    "مرسيدس": 50000,
    "فراري": 120000,
    "لامبورغيني": 250000
}

# قائمة العقارات
HOUSES = {
    "شقة سكنية": 30000,
    "فيلا مدرجة": 100000,
    "قصر فخم": 500000
}

def get_user_data(user_id: int):
    """جلب أو إنشاء بيانات المستخدم التلقائية"""
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
            "stocks": {}
        }
    return users_data[user_id]

# ==========================================
# 4. الواجهات التفاعلية (Buttons & Menus)
# ==========================================

class ShopDropdown(discord.ui.Select):
    """قائمة منسدلة لشراء السيارات والممتلكات"""
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
            await interaction.response.send_message(f"❌ لا تملك المال الكافي لشراء **{car_name}**! يحتاج إلى **${price:,}**.", ephemeral=True)
            return

        data["wallet"] -= price
        data["cars"].append(car_name)
        await interaction.response.send_message(f"🎉 مبروك! قمت بشراء **{car_name}** بنجاح مقابل **${price:,}**.", ephemeral=True)


class ProfileView(discord.ui.View):
    """أزرار تفاعلية لعرض الملف الشخصي وشراء التأمين"""
    def __init__(self, user: discord.Member):
        super().__init__(timeout=60)
        self.user = user

    @discord.ui.button(label="شراء/تجديد التأمين ($2,000)", style=discord.ButtonStyle.green, emoji="🛡️")
    async def buy_insurance(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ لا يمكنك استخدام أزرار هذا الملف الشخصي!", ephemeral=True)
            return

        data = get_user_data(self.user.id)
        cost = 2000

        if data["wallet"] < cost:
            await interaction.response.send_message(f"❌ ليس لديك محفظة بها **${cost}** لشراء التأمين!", ephemeral=True)
            return

        data["wallet"] -= cost
        data["has_insurance"] = True
        data["insurance_expiry"] = datetime.now() + timedelta(days=3)
        await interaction.response.send_message("🛡️ تم تفعيل التأمين الشامل لمدة 3 أيام ضد السرقة والحوادث!", ephemeral=True)

# ==========================================
# 5. أحداث البوت ومعالجة الأخطاء
# ==========================================

@bot.event
async def on_ready():
    print(f"✅ تم تشغيل البوت بنجاح باسم: {bot.user.name}")
    try:
        synced = await bot.tree.sync()
        print(f"🔄 تم مزامنة {len(synced)} من أوامر السلاش (Slash Commands).")
    except Exception as e:
        print(f"خطأ أثناء مزامنة الأوامر: {e}")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        hours, remainder = divmod(int(error.retry_after), 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours > 0:
            await ctx.send(f"⏳ هذا الأمر في فترة انتظار! يرجى المحاولة بعد **{hours} ساعة و {minutes} دقيقة**.")
        else:
            await ctx.send(f"⏳ يرجى الانتظار **{minutes} دقيقة و {seconds} ثانية** قبل إعادة الاستخدام.")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ لا تملك الصلاحيات الكافية لاستخدام هذا الأمر!")

# ==========================================
# 6. نظام المهن والعمل المطور
# ==========================================

@bot.command(name="عمل", aliases=["work"])
@commands.cooldown(1, 3600, commands.BucketType.user)  # مرة كل ساعة
async def work_cmd(ctx):
    data = get_user_data(ctx.author.id)

    # التحقق من السجن
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

    msg = f"💼 عملت بوظيفتك كـ **{data['job']}** وحصلت على راتب قدره **${salary:,}**!"

    # التحقق من الترقيات
    next_job = job_info["next_job"]
    if next_job and data["job_exp"] >= job_info["req_exp"]:
        data["job"] = next_job
        msg += f"\n🎉 **تهانينا!** لقد تمت ترقيتك إلى مهنة: **{next_job}**!"

    await ctx.send(msg)

@bot.command(name="مهنتي", aliases=["job"])
async def my_job(ctx):
    data = get_user_data(ctx.author.id)
    job_info = JOBS[data["job"]]
    next_job = job_info["next_job"]

    embed = discord.Embed(title=f"💼 المهنة الخاصة بـ {ctx.author.display_name}", color=discord.Color.blue())
    embed.add_field(name="المهنة الحالية", value=data["job"], inline=True)
    embed.add_field(name="الخبرة الحالية", value=f"{data['job_exp']} نقطة", inline=True)
    embed.add_field(name="الراتب الأساسي", value=f"${job_info['salary']:,}", inline=False)

    if next_job:
        req = job_info["req_exp"]
        embed.add_field(name="الترقية القادمة", value=f"**{next_job}** (يحتاج {req} نقطة خبرة)", inline=False)
    else:
        embed.add_field(name="الترقية القادمة", value="وصلت للقمة! (أعلى رتبة)", inline=False)

    await ctx.send(embed=embed)

# ==========================================
# 7. نظام الجرائم والسجن والتأمين
# ==========================================

@bot.command(name="سرقة", aliases=["rob"])
@commands.cooldown(1, 1800, commands.BucketType.user)  # كولدون 30 دقيقة
async def rob_cmd(ctx, target: discord.Member = None):
    if not target or target.id == ctx.author.id:
        await ctx.send("❌ يرجى تحديد الشخص الذي تريد سرقته! مثال: `!سرقة @عضو`")
        return

    thief_data = get_user_data(ctx.author.id)
    victim_data = get_user_data(target.id)

    # التحقق مما إذا كان السارق مسجوناً
    if thief_data["in_jail"]:
        if datetime.now() < thief_data["jail_release_time"]:
            remaining = int((thief_data["jail_release_time"] - datetime.now()).total_seconds() // 60)
            await ctx.send(f"🔒 أنت مسجون! لا يمكنك القيام بجرائم قبل **{remaining} دقيقة**.")
            return
        else:
            thief_data["in_jail"] = False

    # التحقق من رصيد الضحية
    if victim_data["wallet"] < 500:
        await ctx.send("❌ الضحية مفلس تماماً ولا يمتلك كاش كافٍ للسرقة!")
        return

    # التحقق من وجود تأمين لدى الضحية
    if victim_data["has_insurance"] and victim_data["insurance_expiry"] and datetime.now() < victim_data["insurance_expiry"]:
        stolen = random.randint(200, min(1000, victim_data["wallet"]))
        thief_data["in_jail"] = True
        thief_data["jail_release_time"] = datetime.now() + timedelta(minutes=10)

        # التأمين يعوض الضحية فوراً
        await ctx.send(
            f"🛡️ **فشلت الجريمة!** حاول {ctx.author.mention} سرقة {target.mention}، "
            f"ولكن الضحية يمتلك **تأميناً شاملاً**!\n"
            f"🚓 تم القبض على السارق وسجنه **10 دقائق**، وعوضت شركة التأمين الضحية بـ **${stolen:,}**!"
        )
        return

    # نسبة نجاح السرقة (40% نجاح - 60% فشل)
    success = random.random() < 0.40

    if success:
        stolen_amount = random.randint(200, int(victim_data["wallet"] * 0.40))
        victim_data["wallet"] -= stolen_amount
        thief_data["wallet"] += stolen_amount
        await ctx.send(f"🥷 **نجحت الجريمة!** سرق {ctx.author.mention} مبلغ **${stolen_amount:,}** من {target.mention}!")
    else:
        fine = random.randint(300, 1000)
        thief_data["wallet"] = max(0, thief_data["wallet"] - fine)
        thief_data["in_jail"] = True
        thief_data["jail_release_time"] = datetime.now() + timedelta(minutes=5)
        await ctx.send(
            f"🚓 **قبضت عليك الشرطة!** فشل {ctx.author.mention} في سرقة {target.mention}.\n"
            f"⚖️ العقوبة: سجن لمدة **5 دقائق** وغرامة **${fine:,}**!"
        )

@bot.command(name="كفالة", aliases=["bail"])
async def bail_cmd(ctx):
    data = get_user_data(ctx.author.id)

    if not data["in_jail"] or (data["jail_release_time"] and datetime.now() >= data["jail_release_time"]):
        data["in_jail"] = False
        await ctx.send("✅ أنت لست مسجوناً حالياً!")
        return

    bail_cost = 2500
    if data["wallet"] < bail_cost:
        await ctx.send(f"❌ قيمة الكفالة للخروج من السجن **${bail_cost:,}** كاش، وأنت لا تملك المال الكافي!")
        return

    data["wallet"] -= bail_cost
    data["in_jail"] = False
    data["jail_release_time"] = None
    await ctx.send(f"🔓 تم دفع الكفالة بمبلغ **${bail_cost:,}** وتم إطلاق سراحك فوراً!")

@bot.command(name="تأمين", aliases=["insurance"])
async def insurance_cmd(ctx):
    data = get_user_data(ctx.author.id)
    cost = 2000

    if data["has_insurance"] and data["insurance_expiry"] and datetime.now() < data["insurance_expiry"]:
        remaining_hours = int((data["insurance_expiry"] - datetime.now()).total_seconds() // 3600)
        await ctx.send(f"🛡️ لديك تأمين مفعل بالفعل! متبقي على انتهائه: **{remaining_hours} ساعة**.")
        return

    if data["wallet"] < cost:
        await ctx.send(f"❌ سعر التأمين ضد السرقات هو **${cost:,}** كاش لمدة 3 أيام!")
        return

    data["wallet"] -= cost
    data["has_insurance"] = True
    data["insurance_expiry"] = datetime.now() + timedelta(days=3)
    await ctx.send("🛡️ تم شراء التأمين بنجاح! أنت الآن محمي ضد السرقات والحوادث لمدة **3 أيام**.")

# ==========================================
# 8. المعرض والأزرار والتفاعل بالواجهات (UI)
# ==========================================

class MainStoreView(discord.ui.View):
    """واجهة المتجر والمعرض الرئيسي بالأزرار والقوائم"""
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ShopDropdown())

    @discord.ui.button(label="عرض السيارات", style=discord.ButtonStyle.primary, emoji="🏎️")
    async def show_cars_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="🏎️ معرض السيارات الفاخرة", color=discord.Color.gold())
        for car, price in CARS.items():
            embed.add_field(name=f"🚗 {car}", value=f"السعر: **${price:,}**", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="عرض العقارات", style=discord.ButtonStyle.success, emoji="🏠")
    async def show_houses_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="🏠 سوق العقارات والمنازل", color=discord.Color.green())
        for house, price in HOUSES.items():
            embed.add_field(name=f"🏡 {house}", value=f"السعر: **${price:,}**", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.command(name="معرض", aliases=["متجر", "store", "shop"])
async def open_store(ctx):
    embed = discord.Embed(
        title="🛒 المتجر والمعرض التفاعلي",
        description="اختر من الأزرار القائمة القادمة لرؤية المعروضات أو الشراء الشامل عبر القائمة المنسدلة:",
        color=discord.Color.blurple()
    )
    await ctx.send(embed=embed, view=MainStoreView())

@bot.command(name="بروفايل", aliases=["رصيدي", "profile", "bal"])
async def profile_cmd(ctx, member: discord.Member = None):
    target = member or ctx.author
    data = get_user_data(target.id)

    # مراجعة حالة السجن والتأمين
    jail_status = "❌ غير مسجون"
    if data["in_jail"]:
        if data["jail_release_time"] and datetime.now() < data["jail_release_time"]:
            jail_status = "🔒 مسجون"
        else:
            data["in_jail"] = False

    ins_status = "❌ غير محمي"
    if data["has_insurance"] and data["insurance_expiry"] and datetime.now() < data["insurance_expiry"]:
        ins_status = "🛡️ محمي"

    embed = discord.Embed(title=f"👤 الملف الشخصي - {target.display_name}", color=discord.Color.purple())
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="💵 المحفظة", value=f"${data['wallet']:,}", inline=True)
    embed.add_field(name="🏦 البنك", value=f"${data['bank']:,}", inline=True)
    embed.add_field(name="💼 المهنة", value=data["job"], inline=True)
    embed.add_field(name="🛡️ التأمين", value=ins_status, inline=True)
    embed.add_field(name="⚖️ الحالة القضائية", value=jail_status, inline=True)

    cars_list = ", ".join(data["cars"]) if data["cars"] else "لا يوجد"
    embed.add_field(name="🚗 السيارات المملوكة", value=cars_list, inline=False)

    view = ProfileView(target)
    await ctx.send(embed=embed, view=view)

# ==========================================
# 9. الأوامر المالية والتحويلات
# ==========================================

@bot.command(name="تحويل", aliases=["pay", "transfer"])
async def transfer_cmd(ctx, member: discord.Member = None, amount: int = None):
    if not member or not amount or amount <= 0 or member.id == ctx.author.id:
        await ctx.send("❌ طريقة الاستخدام: `!تحويل @عضو المبلغ`")
        return

    sender = get_user_data(ctx.author.id)
    receiver = get_user_data(member.id)

    if sender["wallet"] < amount:
        await ctx.send("❌ لا تملك هذا المبلغ الكافي في محفظتك!")
        return

    sender["wallet"] -= amount
    receiver["wallet"] += amount
    await ctx.send(f"✅ تم تحويل **${amount:,}** بنجاح إلى {member.mention}!")

@bot.command(name="ايداع", aliases=["dep", "deposit"])
async def deposit_cmd(ctx, amount: str = None):
    data = get_user_data(ctx.author.id)

    if not amount:
        await ctx.send("❌ حدد المبلغ أو اكتب `الكل`! مثال: `!ايداع 1000`")
        return

    if amount in ["الكل", "all"]:
        val = data["wallet"]
    else:
        try:
            val = int(amount)
        except ValueError:
            await ctx.send("❌ يرجى إدخال رقم صحيح!")
            return

    if val <= 0 or data["wallet"] < val:
        await ctx.send("❌ ليس لديك هذا المبلغ في المحفظة!")
        return

    data["wallet"] -= val
    data["bank"] += val
    await ctx.send(f"🏦 تم إيداع **${val:,}** في حسابك البنكي بنجاح.")

@bot.command(name="سحب", aliases=["with", "withdraw"])
async def withdraw_cmd(ctx, amount: str = None):
    data = get_user_data(ctx.author.id)

    if not amount:
        await ctx.send("❌ حدد المبلغ أو اكتب `الكل`! مثال: `!سحب 1000`")
        return

    if amount in ["الكل", "all"]:
        val = data["bank"]
    else:
        try:
            val = int(amount)
        except ValueError:
            await ctx.send("❌ يرجى إدخال رقم صحيح!")
            return

    if val <= 0 or data["bank"] < val:
        await ctx.send("❌ لا يملك حسابك البنكي هذا المبلغ!")
        return

    data["bank"] -= val
    data["wallet"] += val
    await ctx.send(f"💵 تم سحب **${val:,}** من البنك إلى المحفظة.")

# ==========================================
# 10. الأوامر الإدارية الكاملة (Admin Commands)
# ==========================================

@bot.command(name="اعطاء", aliases=["give"])
@commands.has_permissions(administrator=True)
async def admin_give(ctx, member: discord.Member = None, amount: int = None):
    if not member or not amount or amount <= 0:
        await ctx.send("❌ الاستخدام الإداري: `!اعطاء @عضو المبلغ`")
        return

    data = get_user_data(member.id)
    data["wallet"] += amount
    await ctx.send(f"👑 تم إضافة **${amount:,}** كاش إلى حساب {member.mention} بواسطة الإدارة.")

@bot.command(name="تصفير", aliases=["reset"])
@commands.has_permissions(administrator=True)
async def admin_reset(ctx, target: Optional[discord.Member] = None):
    if target:
        users_data[target.id] = {
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
            "stocks": {}
        }
        await ctx.send(f"⚙️ تم إعادة تصفير بيانات الحساب الاقتصادية لـ {target.mention} بنجاح.")
    else:
        users_data.clear()
        await ctx.send("⚠️ **تم تصفير جميع أرصدة وبيانات السيرفر الاقتصادية بنجاح!**")

@bot.command(name="عفو", aliases=["unjail"])
@commands.has_permissions(administrator=True)
async def admin_unjail(ctx, member: discord.Member = None):
    if not member:
        await ctx.send("❌ حدد العضو للإفراج عنه: `!عفو @عضو`")
        return

    data = get_user_data(member.id)
    data["in_jail"] = False
    data["jail_release_time"] = None
    await ctx.send(f"⚖️ تم إصدار عفو إداري والإفراج عن {member.mention} فوراً.")
# ==========================================
# أمر اليومية (!يومية)
# ==========================================
@bot.command(name="يومية", aliases=["daily"])
@commands.cooldown(1, 86400, commands.BucketType.user) # مرة كل 24 ساعة (86400 ثانية)
async def daily_cmd(ctx):
    data = get_user_data(ctx.author.id)
    
    # مكافأة اليومية (مبلغ عشوائي بين 1000 و 2500)
    reward = random.randint(1000, 2500)
    data["wallet"] += reward
    
    await ctx.send(f"🎁 أهلاً {ctx.author.mention}! لقد حصلت على مكافأتك اليومية بقيمة **${reward:,}**!")

# ==========================================
# أمر المساعدة (!مساعدة)
# ==========================================
@bot.command(name="مساعدة", aliases=["help"])
async def help_cmd(ctx):
    embed = discord.Embed(
        title="📜 قائمة أوامر البوت الاقتصادية",
        description="إليك جميع الأوامر المتاحة لاستخدامها في السيرفر:",
        color=discord.Color.gold()
    )
    
    embed.add_field(
        name="💼 الأوامر العامة والعمل",
        value="• `!عمل` - للعمل كسب المال والترقية في المهن\n"
              "• `!مهنتي` - لعرض مستواك الوظيفي والراتب\n"
              "• `!يومية` - لاستلام المكافأة اليومية كل 24 ساعة\n"
              "• `!بروفايل` - لعرض بطاقتك الشخصية ورصيدك",
        inline=False
    )
    
    embed.add_field(
        name="🛒 المتجر والتأمين",
        value="• `!معرض` - لفتح المعرض التفاعلي والشراء بالأزرار\n"
              "• `!تأمين` - لشراء تأمين ضد السرقات والحوادث",
        inline=False
    )
    
    embed.add_field(
        name="⚖️ الجرائم والقضاء",
        value="• `!سرقة @عضو` - لمحاولة سرقة عضو آخر\n"
              "• `!كفالة` - لدفع كفالة الخروج من السجن",
        inline=False
    )
    
    embed.add_field(
        name="🏦 المعاملات المالية",
        value="• `!تحويل @عضو المبلغ` - لتحويل كاش لعضو آخر\n"
              "• `!ايداع المبلغ` - لإيداع الكاش في البنك\n"
              "• `!سحب المبلغ` - لسحب المال من البنك",
        inline=False
    )
    
    await ctx.send(embed=embed)

# ==========================================
# 11. تشغيل البوت
# ==========================================
TOKEN = os.environ.get("DISCORD_TOKEN") or os.environ.get("BOT_TOKEN")

if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ خطأ: لم يتم العثور على التوكين في متغيرات البيئة! تأكد من ضبط DISCORD_TOKEN في Render.")
