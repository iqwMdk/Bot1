import os
import random
import asyncio
import threading
from typing import Optional
from datetime import datetime, timedelta

import discord
from discord.ext import commands
from flask import Flask

# ==========================================
# 1. خادم Web Service لضمان الاستقرار على Render
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "Bot is running online 24/7!"

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
bot.remove_command("help")

# ==========================================
# 3. قواعد البيانات
# ==========================================
users_data = {}
gangs_data = {}

real_estate_market = {
    "1": {"name": "محل تجاري", "price": 50000, "income": 1500},
    "2": {"name": "مبنى مكاتب", "price": 150000, "income": 5000},
    "3": {"name": "شركة استثمارية", "price": 500000, "income": 20000}
}

GANG_CONTRACTS = {
    "1": {"name": "عقد تهريب بضائع", "reward": 15000, "cost": 3000},
    "2": {"name": "عقد حماية منشآت", "reward": 35000, "cost": 7000},
    "3": {"name": "عقد توريد بالسوق الأسود", "reward": 80000, "cost": 15000}
}

BLACK_MARKET = {
    "1": {"name": "درع حماية (حصانة 24h)", "price": 10000, "type": "immunity"},
    "2": {"name": "سلاح سرقات خفيف (+10% نجاح)", "price": 25000, "type": "weapon"},
    "3": {"name": "حقيبة غسيل أموال سريعة", "price": 15000, "type": "wash_kit"}
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
    "1": {"name": "متجر صغير", "reward": 5000, "risk": 0.2},
    "2": {"name": "بنك محلي", "reward": 25000, "risk": 0.5},
    "3": {"name": "البنك المركزي", "reward": 100000, "risk": 0.8}
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
# 4. المكونات التفاعلية القوائم والأزرار (UI Modals & Selects)
# ==========================================

# --- قائمة شراء العقارات المنسدلة ---
class RealEstateSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=item['name'], value=key, description=f"السعر: ${item['price']:,} | الدخل: ${item['income']:,}")
            for key, item in real_estate_market.items()
        ]
        super().__init__(placeholder="اختر عقاراً لشراؤه...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]
        estate = real_estate_market[selected]
        data = get_user_data(interaction.user.id)
        if data["wallet"] < estate["price"]:
            await interaction.response.send_message(f"❌ لا تملك المبلغ الكافي لشراء {estate['name']}!", ephemeral=True)
            return
        data["wallet"] -= estate["price"]
        data["real_estates"].append(estate["name"])
        await interaction.response.send_message(f"🎉 تم شراء **{estate['name']}** بنجاح وتم خصم ${estate['price']:,}!", ephemeral=True)

# --- قائمة اختيار السرقات المباشرة ---
class RobberySelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=item['name'], value=key, description=f"المكافأة: ${item['reward']:,} | نسبة الخطر: {int(item['risk']*100)}%")
            for key, item in ROBBERIES.items()
        ]
        super().__init__(placeholder="اختر هدف السرقة...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        data = get_user_data(interaction.user.id)
        if not data["gang"]:
            await interaction.response.send_message("❌ ينبغي أن تكون عضواً في عصابة لبدء السرقة!", ephemeral=True)
            return
        selected = self.values[0]
        rob = ROBBERIES[selected]
        if random.random() > rob["risk"]:
            gangs_data[data["gang"]]["bank"] += rob["reward"]
            await interaction.response.send_message(f"🔥 **نجحت السرقة!** تمت إضافة **${rob['reward']:,}** إلى خزينة العصابة!", ephemeral=True)
        else:
            await interaction.response.send_message("🚨 **فشلت السرقة!** حاصرت قوات الشرطة المكان وهربت العصابة.", ephemeral=True)

# --- قائمة العقود المنسدلة ---
class ContractSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=item['name'], value=key, description=f"التكلفة: ${item['cost']:,} | الربح: ${item['reward']:,}")
            for key, item in GANG_CONTRACTS.items()
        ]
        super().__init__(placeholder="اختر عقداً لتنفيذه مع عصابتك/شركتك...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        data = get_user_data(interaction.user.id)
        if not data["gang"]:
            await interaction.response.send_message("❌ يجب أن تكون في عصابة/شركة لتنفيذ العقود!", ephemeral=True)
            return
        selected = self.values[0]
        c = GANG_CONTRACTS[selected]
        if data["wallet"] < c["cost"]:
            await interaction.response.send_message(f"❌ لا تملك تكلفة التجهيز للعقد (${c['cost']:,})!", ephemeral=True)
            return
        data["wallet"] -= c["cost"]
        gangs_data[data["gang"]]["bank"] += c["reward"]
        await interaction.response.send_message(f"📜 تم إبرام وتنفيذ **{c['name']}** ونزول **${c['reward']:,}** في خزينة العصابة!", ephemeral=True)

# --- قائمة السوق الأسود (Black Market) ---
class BlackMarketSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=item['name'], value=key, description=f"السعر: ${item['price']:,}")
            for key, item in BLACK_MARKET.items()
        ]
        super().__init__(placeholder="اختر عنصرًا من السوق الأسود...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]
        item = BLACK_MARKET[selected]
        data = get_user_data(interaction.user.id)
        if data["wallet"] < item["price"]:
            await interaction.response.send_message("❌ لا تملك المال الكافي للشراء من السوق الأسود!", ephemeral=True)
            return
        data["wallet"] -= item["price"]
        if item["type"] == "immunity":
            data["immunity_until"] = datetime.now() + timedelta(days=1)
            await interaction.response.send_message("🛡️ تم تفعيل الحصانة الكاملة لمدة 24 ساعة!", ephemeral=True)
        elif item["type"] == "wash_kit":
            if data["dirty_money"] > 0:
                data["wallet"] += data["dirty_money"]
                data["dirty_money"] = 0
                await interaction.response.send_message("🧼 تم غسيل جميع أموالك المشبوهة بنسبة 100%!", ephemeral=True)
            else:
                await interaction.response.send_message("❌ ليس لديك أموال غير مغسولة حالياً.", ephemeral=True)

# --- لوحة التحكم التفاعلية الشاملة للأزرار والقوائم ---
class CompleteInteractiveDashboardView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    # 1. الصف الأول: سوق العقارات + الحساب والمال
    @discord.ui.button(label="🏢 سوق العقارات والشركات", style=discord.ButtonStyle.success, row=0)
    async def btn_real_estate(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = discord.ui.View()
        view.add_item(RealEstateSelect())
        await interaction.response.send_message("🏬 **اختر العقار أو الشائعة التي ترغب بشراؤها مباشرة:**", view=view, ephemeral=True)

    @discord.ui.button(label="💳 رصيدي وحسابي", style=discord.ButtonStyle.primary, row=0)
    async def btn_balance(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = get_user_data(interaction.user.id)
        msg = (
            f"👤 **بيانات {interaction.user.display_name}:**\n"
            f"💵 المحفظة الكاش: **${data['wallet']:,}**\n"
            f"🏦 البنك: **${data['bank']:,}**\n"
            f"🧼 أموال مشبوهة: **${data['dirty_money']:,}**"
        )
        await interaction.response.send_message(msg, ephemeral=True)

    # 2. الصف الثاني: جمع الأرباح + السيارات + الأسهم
    @discord.ui.button(label="💰 جمع أرباح العقارات", style=discord.ButtonStyle.success, row=1)
    async def btn_collect_profit(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = get_user_data(interaction.user.id)
        if not data["real_estates"]:
            await interaction.response.send_message("❌ لا تملك عقارات أو شركات حالياً!", ephemeral=True)
            return
        total = 0
        for name in data["real_estates"]:
            for item in real_estate_market.values():
                if item["name"] == name:
                    total += item["income"]
        data["wallet"] += total
        await interaction.response.send_message(f"💰 تم استلام كافة أرباح العقارات والشركات بقيمة **${total:,}**!", ephemeral=True)

    @discord.ui.button(label="🏎️ معرض السيارات", style=discord.ButtonStyle.primary, row=1)
    async def btn_cars(self, interaction: discord.Interaction, button: discord.ui.Button):
        msg = "🏎️ **معرض المركبات المتاحة:**\n"
        for name, price in CARS_MARKET.items():
            msg += f"• **{name}**: ${price:,}\n"
        await interaction.response.send_message(msg, ephemeral=True)

    @discord.ui.button(label="📈 سوق الأسهم", style=discord.ButtonStyle.secondary, row=1)
    async def btn_stocks(self, interaction: discord.Interaction, button: discord.ui.Button):
        msg = "📈 **مؤشرات أسعار الأسهم:**\n"
        for code, info in STOCKS.items():
            msg += f"• **[{code}]** {info['name']}: ${info['price']}\n"
        await interaction.response.send_message(msg, ephemeral=True)

    # 3. الصف الثالث: عصابتي + العقود + السرقات
    @discord.ui.button(label="⬛ عصابتي والشركات", style=discord.ButtonStyle.danger, row=2)
    async def btn_my_gang(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = get_user_data(interaction.user.id)
        if not data["gang"]:
            await interaction.response.send_message("❌ أنت لست عضواً في أي عصابة حالياً!", ephemeral=True)
            return
        g_name = data["gang"]
        g_info = gangs_data.get(g_name, {"members": [], "bank": 0, "owner": None})
        msg = (
            f"🏴‍☠️ **بيانات العصابة [{g_name}]:**\n"
            f"• القائد: <@{g_info.get('owner', 'غير معروف')}>\n"
            f"• الأعضاء: {len(g_info['members'])}\n"
            f"• الخزينة: **${g_info['bank']:,}**"
        )
        await interaction.response.send_message(msg, ephemeral=True)

    @discord.ui.button(label="📜 عقود العصابة", style=discord.ButtonStyle.secondary, row=2)
    async def btn_contracts(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = discord.ui.View()
        view.add_item(ContractSelect())
        await interaction.response.send_message("📜 **اختر العقد المراد تنفيذه لصالح عصابتك:**", view=view, ephemeral=True)

    @discord.ui.button(label="💣 السرقات الجماعية", style=discord.ButtonStyle.danger, row=2)
    async def btn_robberies(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = discord.ui.View()
        view.add_item(RobberySelect())
        await interaction.response.send_message("💣 **اختر المنشأة المراد تنفيذ السرقة عليها:**", view=view, ephemeral=True)

    # 4. الصف الرابع: اليانصيب + السوق الأسود + الحصانة
    @discord.ui.button(label="🎟️ شراء تذكرة يانصيب", style=discord.ButtonStyle.secondary, row=3)
    async def btn_lottery(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = get_user_data(interaction.user.id)
        if data["wallet"] < 5000:
            await interaction.response.send_message("❌ سعر التذكرة $5,000 ولا تملك الرصيد!", ephemeral=True)
            return
        data["wallet"] -= 5000
        lottery_tickets.append(interaction.user.id)
        await interaction.response.send_message(f"🎟️ تم شراء التذكرة بنجاح! إجمالي التذاكر المباعة: {len(lottery_tickets)}", ephemeral=True)

    @discord.ui.button(label="💀 السوق الأسود", style=discord.ButtonStyle.danger, row=3)
    async def btn_black_market(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = discord.ui.View()
        view.add_item(BlackMarketSelect())
        await interaction.response.send_message("💀 **قائمة المبيعات في السوق الأسود:**", view=view, ephemeral=True)

# ==========================================
# 5. الأوامر المباشرة والنصية
# ==========================================

@bot.command(name="مساعدة", aliases=["اوامر", "لوحة", "داشبورد"])
async def cmd_dashboard(ctx):
    embed = discord.Embed(
        title="🌐 اللوحة الاقتصادية التفاعلية العامة",
        description="استخدم الأزرار والقوائم المنسدلة للتحكم في عمليات الحساب، الشركات، العقارات، والعصابات بنقرة واحدة:",
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed, view=CompleteInteractiveDashboardView())

@bot.command(name="رصيدي")
async def cmd_balance(ctx):
    data = get_user_data(ctx.author.id)
    await ctx.send(f"👤 **حساب {ctx.author.display_name}:**\n💵 المحفظة: **${data['wallet']:,}**\n🏦 البنك: **${data['bank']:,}**")

@bot.command(name="تحويل")
async def cmd_transfer(ctx, member: discord.Member = None, amount: int = None):
    if not member or not amount or amount <= 0: return await ctx.send("❌ الاستخدام: `!تحويل @عضو المبلغ`")
    sender = get_user_data(ctx.author.id)
    receiver = get_user_data(member.id)
    if sender["wallet"] < amount: return await ctx.send("❌ لا تملك هذا المبلغ الكاش!")
    sender["wallet"] -= amount
    receiver["wallet"] += amount
    await ctx.send(f"✅ تم تحويل **${amount:,}** إلى {member.mention}")

@bot.command(name="ايداع")
async def cmd_deposit(ctx, amount: str = None):
    data = get_user_data(ctx.author.id)
    if amount == "الكل": val = data["wallet"]
    else:
        try: val = int(amount)
        except: return await ctx.send("❌ اكتب المبلغ أو 'الكل'")
    if val <= 0 or data["wallet"] < val: return await ctx.send("❌ مبلغ غير كافٍ!")
    data["wallet"] -= val
    data["bank"] += val
    await ctx.send(f"🏦 تم إيداع **${val:,}** في البنك.")

@bot.command(name="سحب")
async def cmd_withdraw(ctx, amount: str = None):
    data = get_user_data(ctx.author.id)
    if amount == "الكل": val = data["bank"]
    else:
        try: val = int(amount)
        except: return await ctx.send("❌ اكتب المبلغ أو 'الكل'")
    if val <= 0 or data["bank"] < val: return await ctx.send("❌ لا تملك هذا الرصيد بالبنك!")
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

@bot.command(name="انشاء_عصابة")
async def cmd_create_gang(ctx, *, name: str = None):
    if not name: return await ctx.send("❌ اكتب اسم العصابة/الشركة!")
    data = get_user_data(ctx.author.id)
    if data["wallet"] < 50000: return await ctx.send("❌ التأسيس يتطلب $50,000!")
    if name in gangs_data: return await ctx.send("❌ الاسم مستخدم!")
    data["wallet"] -= 50000
    data["gang"] = name
    gangs_data[name] = {"owner": ctx.author.id, "members": [ctx.author.id], "bank": 0}
    await ctx.send(f"🏴‍☠️ تم إنشاء **{name}** بنجاح!")

# ==========================================
# 6. الأوامر الإدارية (Admin Commands)
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
# 7. تشغيل البوت
# ==========================================
TOKEN = os.environ.get("DISCORD_TOKEN") or os.environ.get("BOT_TOKEN")

if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ لم يتم العثور على التوكين في متغيرات البيئة!")
