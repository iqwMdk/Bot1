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
# 1. خادم Web Service لضمان استمرار التشغيل على Render
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "Bot is online!"

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

# ⚠️ إزالة أمر help المدمج لمنع تعارض الأسماء والانهيار
bot.remove_command("help")

# ==========================================
# 3. قواعد البيانات المؤقتة
# ==========================================
users_data = {}
gangs_data = {}
real_estate_market = {
    1: {"name": "محل تجاري", "price": 50000, "income": 1500},
    2: {"name": "مبنى مكاتب", "price": 150000, "income": 5000},
    3: {"name": "برج استثماري", "price": 500000, "income": 20000}
}
STOCKS = {
    "ARAMCO": {"name": "أرامكو", "price": 100},
    "STC": {"name": "الاتصالات", "price": 50},
    "RAJHI": {"name": "الراجحي", "price": 80}
}
CARS_MARKET = {
    "كامري": 20000,
    "مرسيدس": 80000,
    "فراري": 200000
}
ROBBERIES = {
    1: {"name": "متجر صغير", "reward": 5000, "risk": 0.2},
    2: {"name": "بنك محلي", "reward": 25000, "risk": 0.5},
    3: {"name": "البنك المركزي", "reward": 100000, "risk": 0.8}
}
current_auction = {"active": False, "item": None, "price": 0, "highest_bidder": None}
lottery_tickets = []

def get_user_data(user_id: int):
    if user_id not in users_data:
        users_data[user_id] = {
            "wallet": 1000,
            "bank": 0,
            "real_estates": [],
            "cars": [],
            "gang": None,
            "gang_invite": None,
            "immunity_until": None,
            "stocks": {},
            "dirty_money": 0
        }
    return users_data[user_id]

# ==========================================
# 4. الواجهات التفاعلية والأزرار
# ==========================================
class QuickDashboardView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="💳 رصيدي", style=discord.ButtonStyle.primary)
    async def btn_balance(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = get_user_data(interaction.user.id)
        await interaction.response.send_message(f"💵 المحفظة: **${data['wallet']:,}**\n🏦 البنك: **${data['bank']:,}**", ephemeral=True)

    @discord.ui.button(label="🏢 سوق العقارات", style=discord.ButtonStyle.success)
    async def btn_estates(self, interaction: discord.Interaction, button: discord.ui.Button):
        msg = "🏢 **قائمة العقارات والأعمال:**\n"
        for idx, item in real_estate_market.items():
            msg += f"[{idx}] {item['name']} - السعر: ${item['price']:,} | الدخل: ${item['income']:,}\n"
        await interaction.response.send_message(msg, ephemeral=True)

    @discord.ui.button(label="🏎️ معرض السيارات", style=discord.ButtonStyle.secondary)
    async def btn_cars(self, interaction: discord.Interaction, button: discord.ui.Button):
        msg = "🏎️ **معرض المركبات:**\n"
        for name, price in CARS_MARKET.items():
            msg += f"• {name}: ${price:,}\n"
        await interaction.response.send_message(msg, ephemeral=True)

    @discord.ui.button(label="📈 سوق الأسهم", style=discord.ButtonStyle.secondary)
    async def btn_stocks(self, interaction: discord.Interaction, button: discord.ui.Button):
        msg = "📈 **أسعار الأسهم الحالية:**\n"
        for code, info in STOCKS.items():
            msg += f"• [{code}] {info['name']}: ${info['price']}\n"
        await interaction.response.send_message(msg, ephemeral=True)

    @discord.ui.button(label="🎟️ شراء تذكرة يانصيب", style=discord.ButtonStyle.danger)
    async def btn_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = get_user_data(interaction.user.id)
        if data["wallet"] < 5000:
            await interaction.response.send_message("❌ سعر التذكرة $5,000 ولا تملك المبلغ!", ephemeral=True)
            return
        data["wallet"] -= 5000
        lottery_tickets.append(interaction.user.id)
        await interaction.response.send_message("🎟️ تم شراء تذكرة يانصيب بنجاح مقابل **$5,000**!", ephemeral=True)

# ==========================================
# 5. المال والبنك
# ==========================================
@bot.command(name="رصيدي")
async def cmd_balance(ctx):
    data = get_user_data(ctx.author.id)
    await ctx.send(f"👤 **حساب {ctx.author.display_name}:**\n💵 المحفظة: **${data['wallet']:,}**\n🏦 البنك: **${data['bank']:,}**")

@bot.command(name="تحويل")
async def cmd_transfer(ctx, member: discord.Member = None, amount: int = None):
    if not member or not amount or amount <= 0:
        return await ctx.send("❌ الاستخدام: `!تحويل @عضو المبلغ`")
    sender = get_user_data(ctx.author.id)
    receiver = get_user_data(member.id)
    if sender["wallet"] < amount:
        return await ctx.send("❌ لا تملك هذا المبلغ الكاش!")
    sender["wallet"] -= amount
    receiver["wallet"] += amount
    await ctx.send(f"✅ تم تحويل **${amount:,}** إلى {member.mention}")

@bot.command(name="ايداع")
async def cmd_deposit(ctx, amount: str = None):
    data = get_user_data(ctx.author.id)
    if amount == "الكل":
        val = data["wallet"]
    else:
        try: val = int(amount)
        except: return await ctx.send("❌ اكتب المبلغ أو 'الكل'")
    if val <= 0 or data["wallet"] < val:
        return await ctx.send("❌ مبلغ غير كافٍ!")
    data["wallet"] -= val
    data["bank"] += val
    await ctx.send(f"🏦 تم إيداع **${val:,}** في البنك.")

@bot.command(name="سحب")
async def cmd_withdraw(ctx, amount: str = None):
    data = get_user_data(ctx.author.id)
    if amount == "الكل":
        val = data["bank"]
    else:
        try: val = int(amount)
        except: return await ctx.send("❌ اكتب المبلغ أو 'الكل'")
    if val <= 0 or data["bank"] < val:
        return await ctx.send("❌ لا تملك هذا الرصيد بالبنك!")
    data["bank"] -= val
    data["wallet"] += val
    await ctx.send(f"💵 تم سحب **${val:,}** من البنك.")

@bot.command(name="يومية")
@commands.cooldown(1, 86400, commands.BucketType.user)
async def cmd_daily(ctx):
    data = get_user_data(ctx.author.id)
    reward = random.randint(2000, 5000)
    data["wallet"] += reward
    await ctx.send(f"🎁 استلمت مكافأتك اليومية: **${reward:,}**!")

@bot.command(name="عمل")
@commands.cooldown(1, 3600, commands.BucketType.user)
async def cmd_work(ctx):
    data = get_user_data(ctx.author.id)
    salary = random.randint(300, 1000)
    data["wallet"] += salary
    await ctx.send(f"💼 عملت بجد وحصلت على **${salary:,}**!")

@bot.command(name="التوب")
async def cmd_top(ctx):
    sorted_users = sorted(users_data.items(), key=lambda x: x[1]["wallet"] + x[1]["bank"], reverse=True)[:5]
    msg = "🏆 **قائمة أثرى أثرياء السيرفر:**\n"
    for idx, (u_id, data) in enumerate(sorted_users, 1):
        total = data["wallet"] + data["bank"]
        msg += f"{idx}. <@{u_id}> - ${total:,}\n"
    await ctx.send(msg)

# ==========================================
# 6. العقارات والأعمال
# ==========================================
@bot.command(name="العقارات")
async def cmd_estates_list(ctx):
    msg = "🏢 **قائمة العقارات والشركات المتاحة:**\n"
    for idx, item in real_estate_market.items():
        msg += f"**[{idx}] {item['name']}** - السعر: ${item['price']:,} | الدخل الدوري: ${item['income']:,}\n"
    await ctx.send(msg)

@bot.command(name="شراء_عقار")
async def cmd_buy_estate(ctx, num: int = None):
    if not num or num not in real_estate_market:
        return await ctx.send("❌ حدد رقم العقار من قائمة `!العقارات`")
    estate = real_estate_market[num]
    data = get_user_data(ctx.author.id)
    if data["wallet"] < estate["price"]:
        return await ctx.send("❌ لا تملك المبلغ الكافي!")
    data["wallet"] -= estate["price"]
    data["real_estates"].append(estate["name"])
    await ctx.send(f"🎉 تم شراء **{estate['name']}** بنجاح!")

@bot.command(name="عقاراتي")
async def cmd_my_estates(ctx):
    data = get_user_data(ctx.author.id)
    estates = ", ".join(data["real_estates"]) if data["real_estates"] else "لا تملك عقارات."
    await ctx.send(f"🏘️ **عقاراتك وأعمالك:**\n{estates}")

@bot.command(name="جمع_ارباح")
@commands.cooldown(1, 43200, commands.BucketType.user)
async def cmd_collect_income(ctx):
    data = get_user_data(ctx.author.id)
    if not data["real_estates"]:
        return await ctx.send("❌ لا تملك أي عقار لجمع أرباحه!")
    total_income = 0
    for name in data["real_estates"]:
        for item in real_estate_market.values():
            if item["name"] == name:
                total_income += item["income"]
    data["wallet"] += total_income
    await ctx.send(f"💰 تم جمع أرباح عقاراتك بقيمة **${total_income:,}**!")

# ==========================================
# 7. السيارات والمركبات
# ==========================================
@bot.command(name="معرض_السيارات")
async def cmd_cars_list(ctx):
    msg = "🏎️ **معرض المركبات:**\n"
    for name, price in CARS_MARKET.items():
        msg += f"• **{name}**: ${price:,}\n"
    await ctx.send(msg)

@bot.command(name="شراء_سيارة")
async def cmd_buy_car(ctx, *, name: str = None):
    if not name or name not in CARS_MARKET:
        return await ctx.send("❌ اكتب اسم السيارة بشكل صحيح من المعرض!")
    price = CARS_MARKET[name]
    data = get_user_data(ctx.author.id)
    if data["wallet"] < price:
        return await ctx.send("❌ لا تملك المبلغ الكافي!")
    data["wallet"] -= price
    data["cars"].append(name)
    await ctx.send(f"🏎️ مبروك! قمت بشراء **{name}** بنجاح.")

@bot.command(name="سياراتي")
async def cmd_my_cars(ctx):
    data = get_user_data(ctx.author.id)
    cars = ", ".join(data["cars"]) if data["cars"] else "لا تملك سيارات."
    await ctx.send(f"🚗 **مركباتك:** {cars}")

# ==========================================
# 8. العصابات والسوق الأسود
# ==========================================
@bot.command(name="انشاء_عصابة")
async def cmd_create_gang(ctx, *, name: str = None):
    if not name: return await ctx.send("❌ اكتب اسم العصابة!")
    data = get_user_data(ctx.author.id)
    if data["wallet"] < 50000: return await ctx.send("❌ تأسيس عصابة يتطلب $50,000!")
    if name in gangs_data: return await ctx.send("❌ الاسم مستخدم!")
    data["wallet"] -= 50000
    data["gang"] = name
    gangs_data[name] = {"owner": ctx.author.id, "members": [ctx.author.id], "bank": 0}
    await ctx.send(f"🏴‍☠️ تم إنشاء عصابة **{name}**!")

@bot.command(name="العصابات")
async def cmd_gangs_list(ctx):
    if not gangs_data: return await ctx.send("🏴‍☠️ لا توجد عصابات حالياً.")
    msg = "🏴‍☠️ **قائمة العصابات المسجلة:**\n"
    for g_name, g_info in gangs_data.items():
        msg += f"• **{g_name}** - الأعضاء: {len(g_info['members'])}\n"
    await ctx.send(msg)

@bot.command(name="عصابتي")
async def cmd_my_gang_info(ctx):
    data = get_user_data(ctx.author.id)
    if not data["gang"]: return await ctx.send("❌ أنت لست في عصابة!")
    g_info = gangs_data[data["gang"]]
    await ctx.send(f"🏴‍☠️ **عصابة {data['gang']}:**\nالأعضاء: {len(g_info['members'])}\nخزينة العصابة: ${g_info['bank']:,}")

@bot.command(name="دعوة")
async def cmd_gang_invite(ctx, member: discord.Member = None):
    data = get_user_data(ctx.author.id)
    if not data["gang"]: return await ctx.send("❌ أنت لست صاحب أو عضو عصابة!")
    if not member: return await ctx.send("❌ حدد العضو!")
    target = get_user_data(member.id)
    target["gang_invite"] = data["gang"]
    await ctx.send(f"📩 تم إرسال دعوة انضمام لعصابة **{data['gang']}** إلى {member.mention}")

@bot.command(name="قبول")
async def cmd_gang_accept(ctx):
    data = get_user_data(ctx.author.id)
    if not data["gang_invite"]: return await ctx.send("❌ ليس لديك دعوات معلقة!")
    g_name = data["gang_invite"]
    data["gang"] = g_name
    data["gang_invite"] = None
    gangs_data[g_name]["members"].append(ctx.author.id)
    await ctx.send(f"🎉 انضممت بنجاح إلى عصابة **{g_name}**!")

@bot.command(name="طرد")
async def cmd_gang_kick(ctx, member: discord.Member = None):
    data = get_user_data(ctx.author.id)
    if not data["gang"]: return await ctx.send("❌ لست في عصابة!")
    g_info = gangs_data[data["gang"]]
    if g_info["owner"] != ctx.author.id: return await ctx.send("❌ فقط رئيس العصابة يمكنه الطرد!")
    if member.id in g_info["members"]:
        g_info["members"].remove(member.id)
        get_user_data(member.id)["gang"] = None
        await ctx.send(f"👞 تم طرد {member.mention} من العصابة.")

@bot.command(name="مغادرة")
async def cmd_gang_leave(ctx):
    data = get_user_data(ctx.author.id)
    if not data["gang"]: return await ctx.send("❌ أنت لست في عصابة!")
    g_name = data["gang"]
    gangs_data[g_name]["members"].remove(ctx.author.id)
    data["gang"] = None
    await ctx.send(f"🚪 غادرت عصابة **{g_name}**.")

@bot.command(name="السرقات")
async def cmd_robberies_list(ctx):
    msg = "💣 **سرقات العصابات المتاحة:**\n"
    for idx, r in ROBBERIES.items():
        msg += f"**[{idx}] {r['name']}** - الغنيمة: ${r['reward']:,} | نسبة الخطر: {int(r['risk']*100)}%\n"
    await ctx.send(msg)

@bot.command(name="بدء_سرقة")
@commands.cooldown(1, 7200, commands.BucketType.user)
async def cmd_start_robbery(ctx, num: int = None):
    data = get_user_data(ctx.author.id)
    if not data["gang"]: return await ctx.send("❌ يجب أن تكون في عصابة لبدء السرقة!")
    if not num or num not in ROBBERIES: return await ctx.send("❌ حدد رقم السرقة من قائمة `!السرقات`")
    rob = ROBBERIES[num]
    if random.random() > rob["risk"]:
        gangs_data[data["gang"]]["bank"] += rob["reward"]
        await ctx.send(f"🔥 **نجحت السرقة!** تمت إضافة **${rob['reward']:,}** لخزينة العصابة!")
    else:
        await ctx.send(f"ارات **فشلت السرقة!** حاصرتكم الشرطة وهربتم بدون الغنائم.")

# ==========================================
# 9. الاستثمار والألعاب والبلاك ماركت
# ==========================================
@bot.command(name="الاسهم")
async def cmd_stocks(ctx):
    msg = "📈 **أسعار الأسهم الحالية:**\n"
    for code, info in STOCKS.items():
        msg += f"• **[{code}]** {info['name']}: ${info['price']}\n"
    await ctx.send(msg)

@bot.command(name="شراء_سهم")
async def cmd_buy_stock(ctx, code: str = None, amount: int = None):
    if not code or not amount or amount <= 0: return await ctx.send("❌ الاستخدام: `!شراء_سهم ARAMCO 5`")
    code = code.upper()
    if code not in STOCKS: return await ctx.send("❌ الرمز غير صحيح!")
    cost = STOCKS[code]["price"] * amount
    data = get_user_data(ctx.author.id)
    if data["wallet"] < cost: return await ctx.send("❌ لا تملك كاش كافٍ!")
    data["wallet"] -= cost
    data["stocks"][code] = data["stocks"].get(code, 0) + amount
    await ctx.send(f"✅ تم شراء **{amount}** أسهم في {code}!")

@bot.command(name="بيع_سهم")
async def cmd_sell_stock(ctx, code: str = None, amount: int = None):
    if not code or not amount or amount <= 0: return await ctx.send("❌ الاستخدام: `!بيع_سهم ARAMCO 5`")
    code = code.upper()
    data = get_user_data(ctx.author.id)
    if data["stocks"].get(code, 0) < amount: return await ctx.send("❌ لا تملك هذا العدد من الأسهم!")
    rev = STOCKS[code]["price"] * amount
    data["stocks"][code] -= amount
    data["wallet"] += rev
    await ctx.send(f"💵 تم بيع الأسهم واستلمت **${rev:,}**!")

@bot.command(name="سرقة")
@commands.cooldown(1, 1800, commands.BucketType.user)
async def cmd_rob_user(ctx, member: discord.Member = None):
    if not member or member.id == ctx.author.id: return await ctx.send("❌ حدد العضو!")
    thief = get_user_data(ctx.author.id)
    victim = get_user_data(member.id)
    if victim["immunity_until"] and datetime.now() < victim["immunity_until"]:
        return await ctx.send("🛡️ هذا الشخص لديه حصانة مفعلة!")
    if victim["wallet"] < 500: return await ctx.send("❌ الشخص مفلس!")
    if random.random() < 0.4:
        stolen = random.randint(100, int(victim["wallet"] * 0.3))
        victim["wallet"] -= stolen
        thief["wallet"] += stolen
        await ctx.send(f"🥷 نجحت وسرقت **${stolen:,}** من {member.mention}!")
    else:
        await ctx.send("🚓 فشلت السرقة وفررت هارباً!")

@bot.command(name="غسيل")
async def cmd_wash_money(ctx, amount: int = None):
    if not amount or amount <= 0: return await ctx.send("❌ حدد مبلغ أموال العصابات المُراد غسلها!")
    data = get_user_data(ctx.author.id)
    if data["dirty_money"] < amount: return await ctx.send("❌ لا تملك هذا القدر من الأموال غير المغسولة!")
    clean = int(amount * 0.8)
    data["dirty_money"] -= amount
    data["wallet"] += clean
    await ctx.send(f"🧼 تم غسيل المبلغ واستلمت **${clean:,}** كاش (عمولة 20%).")

@bot.command(name="حصانة")
async def cmd_immunity(ctx):
    data = get_user_data(ctx.author.id)
    if data["wallet"] < 10000: return await ctx.send("❌ سعر الحصانة $10,000 لكامل اليوم!")
    data["wallet"] -= 10000
    data["immunity_until"] = datetime.now() + timedelta(days=1)
    await ctx.send("🛡️ تم تفعيل الحصانة ضد السرقات لمدة 24 ساعة!")

@bot.command(name="المزاد")
async def cmd_auction_info(ctx):
    if not current_auction["active"]:
        return await ctx.send("❌ لا يوجد مزاد قائم حالياً!")
    bidder = f"<@{current_auction['highest_bidder']}>" if current_auction['highest_bidder'] else "لا يوجد مزايدين حتى الآن"
    await ctx.send(f"🔨 **المزاد القائم:**\n• السلعة: **{current_auction['item']}**\n• أعلى سعر حالي: **${current_auction['price']:,}**\n• صاحب أعلى مزايدة: {bidder}")

@bot.command(name="مزايدة")
async def cmd_bid(ctx, amount: int = None):
    global current_auction
    if not current_auction["active"]: return await ctx.send("❌ لا يوجد مزاد قائم الآن!")
    if not amount or amount <= current_auction["price"]: return await ctx.send(f"❌ يجب أن تتزايد بأعلى من **${current_auction['price']:,}**!")
    data = get_user_data(ctx.author.id)
    if data["wallet"] < amount: return await ctx.send("❌ لا تملك المبلغ!")
    current_auction["price"] = amount
    current_auction["highest_bidder"] = ctx.author.id
    await ctx.send(f"🔨 {ctx.author.mention} رفع المزاد إلى **${amount:,}**!")

@bot.command(name="اليانصيب")
async def cmd_lottery(ctx):
    await ctx.send(f"🎟️ عدد التذاكر المباعة حالياً: **{len(lottery_tickets)}** تذكرة! لشراء تذكرة اكتب `!شراء_تذكرة`.")

@bot.command(name="شراء_تذكرة")
async def cmd_buy_ticket(ctx):
    data = get_user_data(ctx.author.id)
    cost = 5000
    if data["wallet"] < cost:
        return await ctx.send(f"❌ سعر التذكرة **${cost:,}** كاش ولا تملك المبلغ!")
    data["wallet"] -= cost
    lottery_tickets.append(ctx.author.id)
    await ctx.send(f"🎟️ تم شراء تذكرة يانصيب بنجاح لمسابقة هذا الأسبوع!")

# ==========================================
# 10. الأوامر الإدارية (للإدارة)
# ==========================================
@bot.command(name="اعطاء")
@commands.has_permissions(administrator=True)
async def admin_give_money(ctx, member: discord.Member = None, amount: int = None):
    if not member or not amount: return await ctx.send("❌ الاستخدام: `!اعطاء @عضو المبلغ`")
    get_user_data(member.id)["wallet"] += amount
    await ctx.send(f"👑 تم إعطاء **${amount:,}** إلى {member.mention}")

@bot.command(name="خصم")
@commands.has_permissions(administrator=True)
async def admin_take_money(ctx, member: discord.Member = None, amount: int = None):
    if not member or not amount: return await ctx.send("❌ الاستخدام: `!خصم @عضو المبلغ`")
    get_user_data(member.id)["wallet"] = max(0, get_user_data(member.id)["wallet"] - amount)
    await ctx.send(f"⚙️ تم خصم **${amount:,}** من {member.mention}")

@bot.command(name="تصفير")
@commands.has_permissions(administrator=True)
async def admin_reset_user(ctx, member: discord.Member = None):
    if not member: return await ctx.send("❌ حدد العضو!")
    users_data.pop(member.id, None)
    await ctx.send(f"⚙️ تم تصفير بيانات {member.mention}")

@bot.command(name="تصفير_الكل")
@commands.has_permissions(administrator=True)
async def admin_reset_all(ctx):
    users_data.clear()
    await ctx.send("⚠️ تم تصفير جميع بيانات السيرفر!")

@bot.command(name="تحديد_الحصانة")
@commands.has_permissions(administrator=True)
async def admin_set_immunity(ctx, member: discord.Member = None, hours: int = 24):
    if not member: return await ctx.send("❌ حدد العضو!")
    get_user_data(member.id)["immunity_until"] = datetime.now() + timedelta(hours=hours)
    await ctx.send(f"⚙️ تم منح حصانة لـ {member.mention} لمدة {hours} ساعة.")

@bot.command(name="اضافة_عقار")
@commands.has_permissions(administrator=True)
async def admin_add_estate(ctx, name: str = None, price: int = None, income: int = None):
    if not name or not price or not income: return await ctx.send("❌ الاستخدام: `!اضافة_عقار الاسم السعر الدخل`")
    new_id = len(real_estate_market) + 1
    real_estate_market[new_id] = {"name": name, "price": price, "income": income}
    await ctx.send(f"🏢 تم إضافة عقار جديد: **[{new_id}] {name}**")

@bot.command(name="حذف_عقار")
@commands.has_permissions(administrator=True)
async def admin_remove_estate(ctx, num: int = None):
    if num in real_estate_market:
        del real_estate_market[num]
        await ctx.send(f"⚙️ تم حذف العقار رقم {num}")

@bot.command(name="سحب_عقار")
@commands.has_permissions(administrator=True)
async def admin_take_estate(ctx, member: discord.Member = None, *, name: str = None):
    if not member or not name: return await ctx.send("❌ الاستخدام: `!سحب_عقار @عضو اسم_العقار`")
    data = get_user_data(member.id)
    if name in data["real_estates"]:
        data["real_estates"].remove(name)
        await ctx.send(f"⚙️ تم سحب عقار **{name}** من {member.mention}")

@bot.command(name="تحديث_الاسهم")
@commands.has_permissions(administrator=True)
async def admin_update_stocks(ctx):
    for code, info in STOCKS.items():
        info["price"] = max(10, info["price"] + random.randint(-15, 15))
    await ctx.send("📈 تم تحديث أسعار الأسهم العشوائية!")

@bot.command(name="بدء_مزاد")
@commands.has_permissions(administrator=True)
async def admin_start_auction(ctx, item: str = None, price: int = None):
    global current_auction
    if not item or not price: return await ctx.send("❌ الاستخدام: `!بدء_مزاد السلعة السعر`")
    current_auction = {"active": True, "item": item, "price": price, "highest_bidder": None}
    await ctx.send(f"📢 **بدأ المزاد على: {item}** بسعر افتتاحي **${price:,}**! للتزايد اكتب `!مزايدة المبلغ`")

@bot.command(name="انهاء_المزاد")
@commands.has_permissions(administrator=True)
async def admin_end_auction(ctx):
    global current_auction
    if not current_auction["active"]: return await ctx.send("❌ لا يوجد مزاد قائم!")
    if current_auction["highest_bidder"]:
        winner_id = current_auction["highest_bidder"]
        price = current_auction["price"]
        get_user_data(winner_id)["wallet"] -= price
        await ctx.send(f"🎉 **انتهى المزاد!** فاز بالمزاد <@{winner_id}> بسعر **${price:,}**!")
    else:
        await ctx.send("🔨 انتهى المزاد بدون مزايدين.")
    current_auction["active"] = False

@bot.command(name="سحب_اليانصيب")
@commands.has_permissions(administrator=True)
async def admin_draw_lottery(ctx):
    global lottery_tickets
    if not lottery_tickets: return await ctx.send("❌ لا يوجد تذاكر مباعة!")
    winner = random.choice(lottery_tickets)
    prize = len(lottery_tickets) * 5000
    get_user_data(winner)["wallet"] += prize
    lottery_tickets.clear()
    await ctx.send(f"🎉 **فاز باليانصيب <@{winner}> بمبلغ ${prize:,}**!")

# ==========================================
# 11. أمر المساعدة وعرض الداشبورد
# ==========================================
@bot.command(name="مساعدة", aliases=["اوامر"])
async def help_command(ctx):
    embed = discord.Embed(
        title="📜 قائمة أوامر السيرفر الاقتصادية",
        description="يمكنك استخدام الأزرار أدناه للخدمات السريعة، أو كتابة الأوامر النصية موضحاً أدناه:",
        color=discord.Color.gold()
    )
    embed.add_field(name="💰 المال والبنك", value="`!رصيدي` `!تحويل` `!ايداع` `!سحب` `!يومية` `!عمل` `!التوب`", inline=False)
    embed.add_field(name="🏢 العقارات والأعمال", value="`!العقارات` `!شراء_عقار [الرقم]` `!عقاراتي` `!جمع_ارباح`", inline=False)
    embed.add_field(name="🏎️ السيارات والمركبات", value="`!معرض_السيارات` `!شراء_سيارة [الاسم]` `!سياراتي`", inline=False)
    embed.add_field(name="💀 العصابات والسوق الأسود", value="`!انشاء_عصابة` `!العصابات` `!عصابتي` `!دعوة` `!قبول` `!طرد` `!مغادرة` `!السرقات` `!بدء_سرقة`", inline=False)
    embed.add_field(name="📈 الاستثمار والألعاب", value="`!الاسهم` `!شراء_سهم` `!بيع_سهم` `!سرقة` `!غسيل` `!حصانة` `!المزاد` `!مزايدة` `!اليانصيب` `!شراء_تذكرة`", inline=False)
    embed.add_field(name="⚙️ الأوامر الإدارية (للإدارة)", value="`!اعطاء` `!خصم` `!تصفير` `!تصفير_الكل` `!تحديد_الحصانة` `!اضافة_عقار` `!حذف_عقار` `!سحب_عقار` `!تحديث_الاسهم` `!بدء_مزاد` `!انهاء_المزاد` `!سحب_اليانصيب`", inline=False)

    await ctx.send(embed=embed, view=QuickDashboardView())

# ==========================================
# 12. التشغيل المباشر
# ==========================================
TOKEN = os.environ.get("DISCORD_TOKEN") or os.environ.get("BOT_TOKEN")

if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ لم يتم العثور على التوكين في متغيرات البيئة Environment Variables!") 
