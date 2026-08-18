import os
import sqlite3
import random
import discord
from discord.ext import commands

# إعداد البوت
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# ---------------------------------------------------------
# إعداد قاعدة البيانات
# ---------------------------------------------------------
conn = sqlite3.connect("economy.db")
cursor = conn.cursor()

# جدول المستخدمين
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    wallet INTEGER DEFAULT 100,
    bank INTEGER DEFAULT 0,
    last_daily TEXT,
    last_work TEXT
)
""")

# جدول العقارات
cursor.execute("""
CREATE TABLE IF NOT EXISTS properties (
    property_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    price INTEGER NOT NULL,
    daily_income INTEGER NOT NULL,
    owner_id INTEGER DEFAULT NULL,
    is_for_sale INTEGER DEFAULT 0,
    sale_price INTEGER DEFAULT 0,
    last_claim TEXT
)
""")
conn.commit()


def get_user(user_id):
  cursor.execute(
      "SELECT wallet, bank FROM users WHERE user_id = ?", (user_id,)
  )
  res = cursor.fetchone()
  if not res:
    cursor.execute(
        "INSERT INTO users (user_id, wallet, bank) VALUES (?, 100, 0)",
        (user_id,),
    )
    conn.commit()
    return 100, 0
  return res[0], res[1]


def update_wallet(user_id, amount):
  get_user(user_id)
  cursor.execute(
      "UPDATE users SET wallet = wallet + ? WHERE user_id = ?",
      (amount, user_id),
  )
  conn.commit()


def update_bank(user_id, amount):
  get_user(user_id)
  cursor.execute(
      "UPDATE users SET bank = bank + ? WHERE user_id = ?", (amount, user_id)
  )
  conn.commit()


# ---------------------------------------------------------
# الأحداث الأساسية
# ---------------------------------------------------------
@bot.event
async def on_ready():
  print(f"تم تسجيل الدخول بنجاح باسم: {bot.user.name}")


# ---------------------------------------------------------
# 1. أمر المساعدة (أوامر المستخدمين فقط)
# ---------------------------------------------------------
@bot.command(aliases=["اوامر", "الأوامر", "مساعدة"])
async def help_cmd(ctx):
  embed = discord.Embed(
      title="📜 قائمة أوامر البوت الاقتصادية",
      description="جميع الأوامر متاحة للاستخدام المباشر:",
      color=discord.Color.gold(),
  )

  embed.add_field(
      name="💰 الأوامر المالية الأساسية",
      value=(
          "`!رصيدي` - لعرض رصيدك في الكاش والبنك\n"
          "`!تحويل @عضو المبلغ` - لتحويل مبلغ مالي لعضو آخر\n"
          "`!ايداع المبلغ` - لإيداع أموال من الكاش للبنك\n"
          "`!سحب المبلغ` - لسحب أموال من البنك للكاش\n"
          "`!يومية` - للحصول على راتبك/مكافأتك اليومية\n"
          "`!عمل` - للعمل والتحصل على مبلغ عشوائي"
      ),
      inline=False,
  )

  embed.add_field(
      name="🏢 أوامر العقارات والمزاد",
      value=(
          "`!العقارات` - لعرض قائمة جميع العقارات وحالتها\n"
          "`!عقاراتي` - لعرض العقارات التي تمتلكها\n"
          "`!شراء_عقار [رقم_العقار]` - لشراء عقار معروض للبيع\n"
          "`!ارباح_العقارات` - لجمع أرباح جميع عقاراتك اليومية\n"
          "`!عرض_للبيع [رقم_العقار] [السعر]` - لعرض عقارك في المزاد/السوق\n"
          "`!الغاء_البيع [رقم_العقار]` - لإلغاء عرض عقارك من البيع"
      ),
      inline=False,
  )

  embed.set_footer(text="استخدم الأوامر بدون أقواس [ ]")
  await ctx.send(embed=embed)


# ---------------------------------------------------------
# 2. الأوامر المالية الأساسية
# ---------------------------------------------------------
@bot.command(aliases=["رصيد", "فلوسي"])
async def رصيدي(ctx):
  wallet, bank = get_user(ctx.author.id)
  embed = discord.Embed(
      title=f"💳 رصيد {ctx.author.display_name}", color=discord.Color.green()
  )
  embed.add_field(
      name="💵 الكاش (المحفظة)", value=f"{wallet:,} ريال", inline=True
  )
  embed.add_field(name="🏦 البنك", value=f"{bank:,} ريال", inline=True)
  embed.add_field(
      name="📊 المجموع", value=f"{(wallet + bank):,} ريال", inline=False
  )
  await ctx.send(embed=embed)


@bot.command(aliases=["تحويل_فلوس"])
async def تحويل(ctx, member: discord.Member = None, amount: int = None):
  if not member or not amount or amount <= 0:
    await ctx.send("❌ الصيغة الصحيحة: `!تحويل @العضو المبلغ`")
    return
  if member.id == ctx.author.id:
    await ctx.send("❌ لا يمكنك التحويل لنفسك!")
    return

  wallet, _ = get_user(ctx.author.id)
  if wallet < amount:
    await ctx.send("❌ لا تملك هذا المبلغ في محفظتك (الكاش)!")
    return

  update_wallet(ctx.author.id, -amount)
  update_wallet(member.id, amount)
  await ctx.send(f"✅ تم تحويل **{amount:,} ريال** بنجاح إلى {member.mention}.")


@bot.command(aliases=["إيداع"])
async def ايداع(ctx, amount: int = None):
  if not amount or amount <= 0:
    await ctx.send("❌ يرجى تحديد مبلغ صحيح للإيداع. مثال: `!ايداع 100`")
    return
  wallet, _ = get_user(ctx.author.id)
  if wallet < amount:
    await ctx.send("❌ لا تملك هذا المبلغ في الكاش!")
    return
  update_wallet(ctx.author.id, -amount)
  update_bank(ctx.author.id, amount)
  await ctx.send(f"🏦 تم إيداع **{amount:,} ريال** في بنكك بنجاح.")


@bot.command()
async def سحب(ctx, amount: int = None):
  if not amount or amount <= 0:
    await ctx.send("❌ يرجى تحديد مبلغ صحيح للسحب. مثال: `!سحب 100`")
    return
  _, bank = get_user(ctx.author.id)
  if bank < amount:
    await ctx.send("❌ لا تملك هذا المبلغ في البنك!")
    return
  update_bank(ctx.author.id, -amount)
  update_wallet(ctx.author.id, amount)
  await ctx.send(f"💵 تم سحب **{amount:,} ريال** من بنكك إلى محفظتك.")


@bot.command()
@commands.cooldown(1, 86400, commands.BucketType.user)  # مرة كل 24 ساعة
async def يومية(ctx):
  reward = 500
  update_wallet(ctx.author.id, reward)
  await ctx.send(f"🎉 حصلت على مكافأتك اليومية بقيمة **{reward:,} ريال**!")


@يومية.error
async def daily_error(ctx, error):
  if isinstance(error, commands.CommandOnCooldown):
    hours = int(error.retry_after // 3600)
    minutes = int((error.retry_after % 3600) // 60)
    await ctx.send(
        f"⏳ يمكنك أخذ اليومية بعد: **{hours} ساعة و {minutes} دقيقة**"
    )


@bot.command()
@commands.cooldown(1, 3600, commands.BucketType.user)  # مرة كل ساعة
async def عمل(ctx):
  earnings = random.randint(50, 200)
  update_wallet(ctx.author.id, earnings)
  jobs = [
      "عملت في المقهى",
      "قمت بتوصيل بعض الطلبات",
      "صلحت جهاز كمبيوتر",
      "عملت في كتابة المقالات",
  ]
  job = random.choice(jobs)
  await ctx.send(f"💼 {job} وحصلت على **{earnings:,} ريال**!")


@عمل.error
async def work_error(ctx, error):
  if isinstance(error, commands.CommandOnCooldown):
    minutes = int(error.retry_after // 60)
    await ctx.send(
        f"⏳ أنت متعب الآن! يمكنك العمل مجدداً بعد **{minutes} دقيقة**."
    )


# ---------------------------------------------------------
# 3. نظام العقارات والمزادات
# ---------------------------------------------------------
@bot.command()
async def العقارات(ctx):
  cursor.execute(
      "SELECT property_id, name, price, daily_income, owner_id, is_for_sale,"
      " sale_price FROM properties"
  )
  props = cursor.fetchall()

  if not props:
    await ctx.send("🏚️ لا يوجد أي عقارات مسجلة في النظام حالياً.")
    return

  embed = discord.Embed(
      title="🏢 سوق العقارات والمنشآت", color=discord.Color.blue()
  )
  for prop in props:
    p_id, name, price, income, owner_id, is_sale, sale_price = prop

    status = "🟢 متاح للشراء الأساسي"
    price_tag = f"{price:,} ريال"

    if owner_id:
      owner_user = bot.get_user(owner_id)
      owner_name = (
          owner_user.display_name if owner_user else f"مستخدم ({owner_id})"
      )
      if is_sale:
        status = f"🏷️ معروض للبيع/مزاد بواسطة {owner_name}"
        price_tag = f"{sale_price:,} ريال"
      else:
        status = f"🔴 مملوك لـ {owner_name}"
        price_tag = "غير معروض للبيع"

    embed.add_field(
        name=f"العقار #{p_id}: {name}",
        value=(
            f"💰 **السعر:** {price_tag}\n"
            f"📈 **الربح اليومي:** {income:,} ريال\n"
            f"📌 **الحالة:** {status}"
        ),
        inline=False,
    )
  await ctx.send(embed=embed)


@bot.command()
async def عقاراتي(ctx):
  cursor.execute(
      "SELECT property_id, name, daily_income, is_for_sale, sale_price FROM"
      " properties WHERE owner_id = ?",
      (ctx.author.id,),
  )
  props = cursor.fetchall()
  if not props:
    await ctx.send("🏠 أنت لا تمتلك أي عقارات حالياً!")
    return

  embed = discord.Embed(
      title=f"🏢 عقارات {ctx.author.display_name}",
      color=discord.Color.purple(),
  )
  for prop in props:
    p_id, name, income, is_sale, sale_price = prop
    sale_status = (
        f"متاح للبيع بسعر {sale_price:,} ريال"
        if is_sale
        else "غير معروض للبيع"
    )
    embed.add_field(
        name=f"#{p_id} - {name}",
        value=f"💵 الربح اليومي: {income:,} ريال\n🏷️ الحالة: {sale_status}",
        inline=False,
    )
  await ctx.send(embed=embed)


@bot.command()
async def شراء_عقار(ctx, property_id: int = None):
  if not property_id:
    await ctx.send(
        "❌ يرجى كتابة رقم العقار المراد شراؤه. مثال: `!شراء_عقار 1`"
    )
    return

  cursor.execute(
      "SELECT property_id, name, price, owner_id, is_for_sale, sale_price FROM"
      " properties WHERE property_id = ?",
      (property_id,),
  )
  prop = cursor.fetchone()
  if not prop:
    await ctx.send("❌ هذا العقار غير موجود!")
    return

  p_id, name, price, owner_id, is_sale, sale_price = prop
  wallet, _ = get_user(ctx.author.id)

  # حالة العقار بدون مالك
  if owner_id is None:
    if wallet < price:
      await ctx.send(
          f"❌ لا تملك المبلغ الكافي لشراء {name}. السعر المطلوب: **{price:,}"
          " ريال**"
      )
      return
    update_wallet(ctx.author.id, -price)
    cursor.execute(
        "UPDATE properties SET owner_id = ? WHERE property_id = ?",
        (ctx.author.id, p_id),
    )
    conn.commit()
    await ctx.send(
        f"🎉 مبروك! قمت بشراء **{name}** بمبلغ **{price:,} ريال** وحصرياً أصبحت"
        " مالكه!"
    )
    return

  # حالة العقار مملوك وشخص عارضه للبيع
  if is_sale:
    if owner_id == ctx.author.id:
      await ctx.send("❌ هذا العقار ملكك بالفعل!")
      return
    if wallet < sale_price:
      await ctx.send(
          "❌ لا تملك المبلغ الكافي لشراء العقار من المزاد. المطلوب:"
          f" **{sale_price:,} ريال**"
      )
      return

    # نقل الأموال والملكية
    update_wallet(ctx.author.id, -sale_price)
    update_wallet(owner_id, sale_price)
    cursor.execute(
        "UPDATE properties SET owner_id = ?, is_for_sale = 0, sale_price = 0"
        " WHERE property_id = ?",
        (ctx.author.id, p_id),
    )
    conn.commit()
    await ctx.send(
        f"🤝 تم الشراء! انتقلت ملكية **{name}** إليك من المالك السابق بمبلغ"
        f" **{sale_price:,} ريال**."
    )
    return

  await ctx.send("❌ هذا العقار مملوك لشخص آخر وليس معروضاً للبيع حالياً.")


@bot.command()
@commands.cooldown(1, 86400, commands.BucketType.user)  # مرة كل 24 ساعة
async def ارباح_العقارات(ctx):
  cursor.execute(
      "SELECT daily_income FROM properties WHERE owner_id = ?", (ctx.author.id,)
  )
  user_props = cursor.fetchall()

  if not user_props:
    await ctx.send("❌ أنت لا تمتلك أي عقارات لجمع أرباح منها!")
    return

  total_income = sum(p[0] for p in user_props)
  update_wallet(ctx.author.id, total_income)
  await ctx.send(
      "📈 تم جمع أرباح عقاراتك اليومية بنجاح! تم إضافة **{total_income:,}"
      " ريال** لملاحظتك/الكاش."
  )


@ارباح_العقارات.error
async def claims_error(ctx, error):
  if isinstance(error, commands.CommandOnCooldown):
    hours = int(error.retry_after // 3600)
    minutes = int((error.retry_after % 3600) // 60)
    await ctx.send(
        "⏳ لقد جمعت أرباحك مؤخراً! يمكنك الجمع مجدداً بعد: **{hours} ساعة و"
        f" {minutes} دقيقة**"
    )


@bot.command()
async def عرض_للبيع(ctx, property_id: int = None, price: int = None):
  if not property_id or not price or price <= 0:
    await ctx.send(
        "❌ الصيغة الصحيحة: `!عرض_للبيع [رقم_العقار] [السعر_المطلوب]`"
    )
    return

  cursor.execute(
      "SELECT name, owner_id FROM properties WHERE property_id = ?",
      (property_id,),
  )
  prop = cursor.fetchone()
  if not prop or prop[1] != ctx.author.id:
    await ctx.send("❌ أنت لا تمتلك هذا العقار لكي تعرضه للبيع!")
    return

  cursor.execute(
      "UPDATE properties SET is_for_sale = 1, sale_price = ? WHERE"
      " property_id = ?",
      (price, property_id),
  )
  conn.commit()
  await ctx.send(
      f"🏷️ تم عرض عقارك **({prop[0]})** في السوق/المزاد بسعر **{price:,}"
      " ريال**."
  )


@bot.command()
async def الغاء_البيع(ctx, property_id: int = None):
  if not property_id:
    await ctx.send("❌ يرجى كتابة رقم العقار. مثال: `!الغاء_البيع 1`")
    return

  cursor.execute(
      "SELECT name, owner_id FROM properties WHERE property_id = ?",
      (property_id,),
  )
  prop = cursor.fetchone()
  if not prop or prop[1] != ctx.author.id:
    await ctx.send("❌ هذا العقار ليس ملكك!")
    return

  cursor.execute(
      "UPDATE properties SET is_for_sale = 0, sale_price = 0 WHERE"
      " property_id = ?",
      (property_id,),
  )
  conn.commit()
  await ctx.send(f"❌ تم إلغاء عرض **({prop[0]})** من السوق.")


# ---------------------------------------------------------
# 4. أوامر المسؤول / الأونر فقط (إدارة النظام)
# ---------------------------------------------------------
@bot.command()
@commands.is_owner()
async def اضافة_عقار(ctx, name: str, price: int, daily_income: int):
  cursor.execute(
      "INSERT INTO properties (name, price, daily_income) VALUES (?, ?, ?)",
      (name, price, daily_income),
  )
  conn.commit()
  await ctx.send(
      f"✅ تم إضافة عقار جديد: **{name}** بسعر **{price:,} ريال** وربح يومي"
      f" **{daily_income:,} ريال**."
  )


# تشغيل البوت
TOKEN = os.environ.get("BOT_TOKEN") or os.environ.get("BOT_TOKEN")
bot.run(TOKEN)
