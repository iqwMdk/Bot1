import os
import random
import asyncio
from typing import Optional
from datetime import datetime, timedelta

import discord
from discord.ext import commands

# ==========================================
# 1. إعدادات البوت والـ Intents
# ==========================================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ⚠️ هذا السطر المهم لمنع الخطأ الظاهر في اللوق:
bot.remove_command("help")

# ==========================================
# 2. قواعد البيانات والوظائف
# ==========================================
users_data = {}
gangs_data = {}

JOBS = {
    "مبتدئ": {"salary": 200, "next_job": "موظف", "req_exp": 5},
    "موظف": {"salary": 500, "next_job": "مشرف", "req_exp": 15},
    "مشرف": {"salary": 1200, "next_job": "مدير", "req_exp": 30},
    "مدير": {"salary": 3000, "next_job": "رئيس شركة", "req_exp": 60},
    "رئيس شركة": {"salary": 7000, "next_job": None, "req_exp": 999999}
}

CARS = {"كامري": 15000, "مرسيدس": 50000, "فراري": 120000, "لامبورغيني": 250000}
HOUSES = {"شقة سكنية": 30000, "فيلا مدرجة": 100000, "قصر فخم": 500000}

def get_user_data(user_id: int):
    if user_id not in users_data:
        users_data[user_id] = {
            "wallet": 1000, "bank": 0, "job": "مبتدئ", "job_exp": 0,
            "in_jail": False, "jail_release_time": None,
            "has_insurance": False, "insurance_expiry": None,
            "cars": [], "houses": [], "gang": None
        }
    return users_data[user_id]

# ==========================================
# 3. الأحداث
# ==========================================
@bot.event
async def on_ready():
    print(f"✅ تم تشغيل البوت بنجاح باسم: {bot.user.name}")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        minutes, seconds = divmod(int(error.retry_after), 60)
        await ctx.send(f"⏳ يرجى الانتظار **{minutes} دقيقة و {seconds} ثانية**.")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ لا تملك الصلاحيات الكافية!")

# ==========================================
# 4. أوامر المهن والعمل
# ==========================================
@bot.command(name="عمل", aliases=["work"])
@commands.cooldown(1, 3600, commands.BucketType.user)
async def work_cmd(ctx):
    data = get_user_data(ctx.author.id)
    if data["in_jail"]:
        await ctx.send("🔒 أنت مسجون! لا يمكنك العمل.")
        return
    job_info = JOBS[data["job"]]
    salary = job_info["salary"] + random.randint(10, 100)
    data["wallet"] += salary
    data["job_exp"] += 1
    msg = f"💼 عملت كـ **{data['job']}** وحصلت على **${salary:,}**!"
    if job_info["next_job"] and data["job_exp"] >= job_info["req_exp"]:
        data["job"] = job_info["next_job"]
        msg += f"\n🎉 تم ترقيتك إلى: **{data['job']}**!"
    await ctx.send(msg)

@bot.command(name="مهنتي", aliases=["job"])
async def my_job(ctx):
    data = get_user_data(ctx.author.id)
    job_info = JOBS[data["job"]]
    embed = discord.Embed(title=f"💼 مهنة {ctx.author.display_name}", color=discord.Color.blue())
    embed.add_field(name="المهنة الحالية", value=data["job"], inline=True)
    embed.add_field(name="الخبرة", value=f"{data['job_exp']} نقطة", inline=True)
    embed.add_field(name="الراتب", value=f"${job_info['salary']:,}", inline=False)
    await ctx.send(embed=embed)

# ==========================================
# 5. أوامر السرقات والتأمين
# ==========================================
@bot.command(name="سرقة", aliases=["rob"])
@commands.cooldown(1, 1800, commands.BucketType.user)
async def rob_cmd(ctx, target: discord.Member = None):
    if not target or target.id == ctx.author.id:
        await ctx.send("❌ حدد الشخص المُراد سرقته!")
        return
    thief = get_user_data(ctx.author.id)
    victim = get_user_data(target.id)

    if victim["wallet"] < 500:
        await ctx.send("❌ الضحية مفلس!")
        return

    if random.random() < 0.4:
        stolen = random.randint(200, int(victim["wallet"] * 0.3))
        victim["wallet"] -= stolen
        thief["wallet"] += stolen
        await ctx.send(f"🥷 نجحت وسرقت **${stolen:,}** من {target.mention}!")
    else:
        thief["in_jail"] = True
        await ctx.send(f"🚓 قبضت عليك الشرطة وسُجنت!")

@bot.command(name="تأمين", aliases=["insurance"])
async def insurance_cmd(ctx):
    data = get_user_data(ctx.author.id)
    if data["wallet"] < 2000:
        await ctx.send("❌ سعر التأمين $2,000!")
        return
    data["wallet"] -= 2000
    data["has_insurance"] = True
    await ctx.send("🛡️ تم تفعيل التأمين بنجاح!")

# ==========================================
# 6. نظام العصابات (Gang System)
# ==========================================
@bot.command(name="انشاء_عصابة")
async def create_gang(ctx, name: str = None):
    if not name:
        await ctx.send("❌ اكتب اسم العصابة! مثال: `!انشاء_عصابة الفرسان`")
        return
    data = get_user_data(ctx.author.id)
    if data["wallet"] < 50000:
        await ctx.send("❌ تحتاج إلى **$50,000** إنشاء عصابة!")
        return
    if name in gangs_data:
        await ctx.send("❌ هذا الاسم مستخدم بالفعل!")
        return

    data["wallet"] -= 50000
    data["gang"] = name
    gangs_data[name] = {"owner": ctx.author.id, "members": [ctx.author.id], "bank": 0}
    await ctx.send(f"🏴‍☠️ تم تأسيس عصابة **{name}** بنجاح!")

@bot.command(name="عصابتي")
async def my_gang(ctx):
    data = get_user_data(ctx.author.id)
    if not data["gang"]:
        await ctx.send("❌ أنت لست في أي عصابة!")
        return
    gang = gangs_data[data["gang"]]
    embed = discord.Embed(title=f"🏴‍☠️ عصابة {data['gang']}", color=discord.Color.dark_red())
    embed.add_field(name="عدد الأعضاء", value=len(gang["members"]))
    embed.add_field(name="خزينة العصابة", value=f"${gang['bank']:,}")
    await ctx.send(embed=embed)

# ==========================================
# 7. المال والبروفايل
# ==========================================
@bot.command(name="تحويل", aliases=["pay"])
async def transfer_cmd(ctx, member: discord.Member = None, amount: int = None):
    if not member or not amount or amount <= 0:
        await ctx.send("❌ الاستخدام: `!تحويل @عضو المبلغ`")
        return
    sender = get_user_data(ctx.author.id)
    receiver = get_user_data(member.id)
    if sender["wallet"] < amount:
        await ctx.send("❌ لا تملك هذا المبلغ!")
        return
    sender["wallet"] -= amount
    receiver["wallet"] += amount
    await ctx.send(f"✅ تم تحويل **${amount:,}** إلى {member.mention}.")

@bot.command(name="بروفايل", aliases=["profile", "bal"])
async def profile_cmd(ctx, member: discord.Member = None):
    target = member or ctx.author
    data = get_user_data(target.id)
    embed = discord.Embed(title=f"👤 بروفايل - {target.display_name}", color=discord.Color.purple())
    embed.add_field(name="💵 المحفظة", value=f"${data['wallet']:,}", inline=True)
    embed.add_field(name="🏦 البنك", value=f"${data['bank']:,}", inline=True)
    embed.add_field(name="💼 المهنة", value=data["job"], inline=True)
    embed.add_field(name="🏴‍☠️ العصابة", value=data["gang"] or "لا يوجد", inline=True)
    await ctx.send(embed=embed)

@bot.command(name="يومية", aliases=["daily"])
@commands.cooldown(1, 86400, commands.BucketType.user)
async def daily_cmd(ctx):
    data = get_user_data(ctx.author.id)
    reward = random.randint(1000, 3000)
    data["wallet"] += reward
    await ctx.send(f"🎁 استلمت مكافأتك اليومية بقيمة **${reward:,}**!")

@bot.command(name="مساعدة", aliases=["help"])
async def help_cmd(ctx):
    embed = discord.Embed(title="📜 قائمة الأوامر", color=discord.Color.gold())
    embed.add_field(name="الوظائف والمال", value="`!عمل` `!مهنتي` `!بروفايل` `!يومية` `!تحويل`", inline=False)
    embed.add_field(name="الجرائم والعصابات", value="`!سرقة` `!تأمين` `!انشاء_عصابة` `!عصابتي`", inline=False)
    await ctx.send(embed=embed)

# ==========================================
# 8. التشغيل المباشر
# ==========================================
TOKEN = os.environ.get("DISCORD_TOKEN") or os.environ.get("BOT_TOKEN")

if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ لم يتم العثور على التوكين!")
