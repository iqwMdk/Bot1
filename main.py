import sqlite3
import discord
from discord.ext import commands

# --- إعداد قاعدة البيانات ---
conn = sqlite3.connect("economy.db")
cursor = conn.cursor()

# إنشاء جدول المستخدمين إذا لم يكن موجوداً
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    wallet INTEGER DEFAULT 1000,
    bank INTEGER DEFAULT 0
)
""")
conn.commit()


# مساعد لتسجيل العضو تلقائياً إذا كان جديداً
def get_user(user_id):
  cursor.execute("SELECT wallet, bank FROM users WHERE user_id = ?", (user_id,))
  user = cursor.fetchone()
  if user is None:
    cursor.execute(
        "INSERT INTO users (user_id, wallet, bank) VALUES (?, 1000, 0)",
        (user_id,),
    )
    conn.commit()
    return (1000, 0)
  return user


# --- إعداد البوت ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
  print(f"تم تشغيل البوت بنجاح باسم: {bot.user}")


# --- أوامر الاقتصاد ---


# 1. أمر عرض الرصيد
@bot.command()
async def balance(ctx):
  wallet, bank = get_user(ctx.author.id)
  embed = discord.Embed(
      title=f"💳 حساب {ctx.author.display_name}", color=discord.Color.blue()
  )
  embed.add_field(name="الرصيد الكاش 💵", value=f"{wallet}$", inline=True)
  embed.add_field(name="البنك 🏦", value=f"{bank}$", inline=True)
  embed.add_field(name="الإجمالي 💰", value=f"{wallet + bank}$", inline=False)
  await ctx.send(embed=embed)


# 2. أمر التحويل من شخص لآخر
@bot.command()
async def pay(ctx, member: discord.Member, amount: int):
  if amount <= 0:
    await ctx.send("❌ يرجى كتابة مبلغ أكبر من الصفر.")
    return

  if member.id == ctx.author.id:
    await ctx.send("❌ لا يمكنك التحويل لنفسك!")
    return

  sender_wallet, _ = get_user(ctx.author.id)
  get_user(member.id)  # للتأكد من وجود المستلم في قاعدة البيانات

  if sender_wallet < amount:
    await ctx.send("❌ لا تملك هذا المبلغ في الكاش!")
    return

  # خصم من المرسل وإضافة للمستلم
  cursor.execute(
      "UPDATE users SET wallet = wallet - ? WHERE user_id = ?",
      (amount, ctx.author.id),
  )
  cursor.execute(
      "UPDATE users SET wallet = wallet + ? WHERE user_id = ?",
      (amount, member.id),
  )
  conn.commit()

  await ctx.send(
      f"✅ تم تحويل **{amount}$** بنجاح إلى {member.mention}!"
  )


# تشغيل البوت (ضع التوكن الخاص بك هنا)
bot.run("MTUzOTI3MDg5NjM4MzE3MjYyMA.GS6rnn.W5sKifHCCVf7pvWRwtjApVxzo88j749JDxdcoM")
