import os
import random
import asyncio
import threading
import time
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

# متجر الأسلحة (كل سلاح يقلل نسبة الخطر في السرقات)
WEAPONS_MARKET = {
    "1": {"name": "سكين", "price": 10000, "bonus": 0.03}, # يقلل الخطر 3%
    "2": {"name": "مسدس", "price": 35000, "bonus": 0.07}, # يقلل الخطر 7%
    "3": {"name": "رشاش", "price": 80000, "bonus": 0.12}, # يقلل الخطر 12%
    "4": {"name": "قناص", "price": 150000, "bonus": 0.20} # يقلل الخطر 20%
}

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
    "سسكي": 20000,
    "كامري": 80000,
    "لكزس": 200000
}

ROBBERIES = {
    "1": {"name": "متجر صغير", "reward": 5000, "risk": 0.2},
    "2": {"name": "بنك محلي", "reward": 25000, "risk": 0.5},
    "3": {"name": "البنك المركزي", "reward": 100000, "risk": 0.8}
}

# ==========================================
# 3. قواعد البيانات وسوق الأسهم المتطور
# ==========================================
users_data = {}
gangs_data = {}

# سوق الأسهم المتطور مع نسب وتغييرات عشوائية
STOCKS = {
    "ARAMCO": {"name": "أرامكو", "price": 100, "change": 2.5, "trend": "📈"},
    "STC": {"name": "الاتصالات", "price": 50, "change": -1.2, "trend": "📉"},
    "RAJHI": {"name": "الراجحي", "price": 80, "change": 4.1, "trend": "📈"}
}

def update_stocks_market():
    """دالة تحديث أسعار الأسهم وتوليد نسب تغيير عشوائية"""
    for code, info in STOCKS.items():
        change_pct = round(random.uniform(-5.0, 5.0), 2)
        multiplier = 1 + (change_pct / 100)
        new_price = max(10, int(info["price"] * multiplier))
        
        info["price"] = new_price
        info["change"] = change_pct
        info["trend"] = "📈" if change_pct >= 0 else "📉"

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
            "dirty_money": 0,
            "inventory": [],
            "contract": None,
            "last_profit_collect": 0  # لمنع قلتش جمع الأرباح
        }
    return users_data[user_id]



# ==========================================
# 4. المكونات التفاعلية القوائم والأزرار (UI Modals & Selects)
# ==========================================
# --- قائمة متجر الأسلحة المنسدلة ---
class WeaponsShopSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label=item['name'], 
                value=key, 
                description=f"السعر: ${item['price']:,} | تقليل الخطر: +{int(item['bonus']*100)}%"
            )
            for key, item in WEAPONS_MARKET.items()
        ]
        super().__init__(placeholder="اختر سلاحاً لشراؤه...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]
        weapon = WEAPONS_MARKET[selected]
        user_data = get_user_data(interaction.user.id)
        
        if weapon["name"] in user_data.get("inventory", []):
            await interaction.response.send_message("❌ أنت تملك هذا السلاح مسبقاً في حقيبتك!", ephemeral=True)
            return
            
        if user_data["wallet"] < weapon["price"]:
            await interaction.response.send_message("❌ لا تملك كاش كافي في محفظتك للشراء!", ephemeral=True)
            return
            
        user_data["wallet"] -= weapon["price"]
        user_data.setdefault("inventory", []).append(weapon["name"])
        await interaction.response.send_message(f"🔫 تم شراء **{weapon['name']}** بنجاح وإضافته إلى حقيبتك!", ephemeral=True)

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
# --- قائمة اختيار السرقات المباشرة ---
class RobberySelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=item['name'], value=key, description=f"المكافأة: ${item['reward']:,} | نسبة الخطر الأساسية: {int(item['risk']*100)}%")
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
        gang_name = data["gang"]
        
        # 1. حساب بونص الأعضاء (تقليل الخطر 3% لكل عضو إضافي)
        members_count = len(gangs_data[gang_name]["members"])
        gang_bonus = (members_count - 1) * 0.03

        # 2. حساب بونص أقوى سلاح في حقيبة اللاعب
        weapon_bonus = 0
        user_inv = data.get("inventory", [])
        for w in user_inv:
            for w_id, w_info in WEAPONS_MARKET.items():
                if w_info["name"] == w and w_info["bonus"] > weapon_bonus:
                    weapon_bonus = w_info["bonus"]

        # 3. حساب نسبة الخطر النهائية بعد الخصم (حد أدنى 5% خطر)
        effective_risk = max(0.05, rob["risk"] - gang_bonus - weapon_bonus)

        if random.random() > effective_risk:
            gangs_data[gang_name]["bank"] += rob["reward"]
            await interaction.response.send_message(
                f"🔥 **نجحت السرقة بفضل سلاحك ودعم {members_count} أعضاء!**\nتمت إضافة **${rob['reward']:,}** إلى خزينة العصابة.", 
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "🚨 **فشلت السرقة!** حاصرتكم الشرطة وهربتم بصعوبة بدون أرباح.", 
                ephemeral=True
            )

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
# --- لوحة التحكم التفاعلية الشاملة المحدثة بالكامل ---
class CompleteInteractiveDashboardView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    # 1. الصف الأول: العقارات، الحساب، جمع الأرباح (بدون قلتش)
    @discord.ui.button(label="🏢 سوق العقارات والشركات", style=discord.ButtonStyle.success, row=0)
    async def btn_real_estate(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = discord.ui.View()
        view.add_item(RealEstateSelect())
        await interaction.response.send_message("🏬 **اختر العقار الذي ترغب بشراؤه مباشرة:**", view=view, ephemeral=True)

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

    @discord.ui.button(label="💰 جمع الأرباح (24h)", style=discord.ButtonStyle.success, row=0)
    async def btn_collect_profit(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = get_user_data(interaction.user.id)
        if not data["real_estates"]:
            await interaction.response.send_message("❌ لا تملك عقارات أو شركات حالياً!", ephemeral=True)
            return

                # فحص كولد داون 3 ساعات (10800 ثانية)
        last_collect = data.get("last_profit_collect", 0)
        now = time.time()
        cooldown = 10800  # <--- غير الرقم هنا إلى 10800

        if now - last_collect < cooldown:
            remaining = int(cooldown - (now - last_collect))  # <--- وهنا أيضاً
            hours = remaining // 3600
            minutes = (remaining % 3600) // 60
            await interaction.response.send_message(
                f"⏳ **استلمت أرباحك مسبقاً!**\nيمكنك الجمع مجدداً بعد: **{hours} ساعة و {minutes} دقيقة**.", 
                ephemeral=True
            )
            return


        total = 0
        for name in data["real_estates"]:
            for item in real_estate_market.values():
                if item["name"] == name:
                    total += item["income"]

        data["wallet"] += total
        data["last_profit_collect"] = now
        await interaction.response.send_message(f"💰 تم استلام أرباحك اليومية لكافة العقارات بقيمة **${total:,}**!", ephemeral=True)

    # 2. الصف الثاني: الأسلحة، الحقيبة، السيارات، والأسهم المحدثة
    @discord.ui.button(label="🔫 متجر الأسلحة", style=discord.ButtonStyle.danger, row=1)
    async def btn_weapons_shop(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = discord.ui.View()
        view.add_item(WeaponsShopSelect())
        await interaction.response.send_message("🔫 **اختر السلاح المراد شراؤه لزيادة نسبة نجاح السرقات:**", view=view, ephemeral=True)

    @discord.ui.button(label="🎒 حقيبتي", style=discord.ButtonStyle.secondary, row=1)
    async def btn_my_inv(self, interaction: discord.Interaction, button: discord.ui.Button):
        inv = get_user_data(interaction.user.id).get("inventory", [])
        if not inv:
            await interaction.response.send_message("🎒 حقيبتك فارغة حالياً.", ephemeral=True)
            return
        weapons_list = "\n".join([f"🔸 {w}" for w in inv])
        await interaction.response.send_message(f"🎒 **محتويات حقيبتك الشخصية:**\n{weapons_list}", ephemeral=True)

    @discord.ui.button(label="📈 سوق الأسهم", style=discord.ButtonStyle.secondary, row=1)
    async def btn_stocks(self, interaction: discord.Interaction, button: discord.ui.Button):
        update_stocks_market() # تحديث الأسعار والنسب عند كل فتح
        embed = discord.Embed(title="📈 مؤشرات وسوق الأسهم المحلية", color=discord.Color.green())
        for code, info in STOCKS.items():
            sign = "+" if info["change"] >= 0 else ""
            embed.add_field(
                name=f"{info['trend']} {info['name']} ({code})",
                value=f"السعر: **${info['price']}**\nالتغير: **{sign}{info['change']}%**",
                inline=True
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # 3. الصف الثالث: العصابات، العقود، السرقات
    @discord.ui.button(label="🏴‍☠️ عصابتي", style=discord.ButtonStyle.primary, row=2)
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

    # 4. الصف الرابع: السوق الأسود، اليانصيب، ودليل الأوامر الكتابية
    @discord.ui.button(label="💀 السوق الأسود", style=discord.ButtonStyle.danger, row=3)
    async def btn_black_market(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = discord.ui.View()
        view.add_item(BlackMarketSelect())
        await interaction.response.send_message("💀 **قائمة المبيعات في السوق الأسود:**", view=view, ephemeral=True)

    @discord.ui.button(label="📖 دليل الأوامر الكتابية", style=discord.ButtonStyle.primary, row=3)
    async def btn_help_guide(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="📖 دليل الأوامر الكتابية المطلوبة",
            description="هناك بعض العمليات المتقدمة التي تتطلب إدخال أسماء أو مبالغ محددة عبر الشات:",
            color=discord.Color.blue()
        )
        embed.add_field(name="📜 عقد العمل بالأزرار", value="`!عقد @اسم_اللاعب [المبلغ] [الأيام]`\nارسال عقد وظيفي براتب محدد للاعب.", inline=False)
        embed.add_field(name="💸 تحويل كاش", value="`!تحويل @اسم_اللاعب [المبلغ]`\nتحويل أموال شخصية للاعب آخر.", inline=False)
        embed.add_field(name="🏴‍☠️ إنشاء عصابة", value="`!انشاء_عصابة [الاسم]`\nتأسيس مقر جديد بـ $50,000.", inline=False)
        embed.add_field(name="🧼 تغسيل أموال", value="`!تغسيل [المبلغ]`\nتحويل كاش غير مشروع لكاش نظيف.", inline=False)
        embed.add_field(name="💼 العمل واليومية", value="`!عمل` | `!يومية` | `!استلام_العقد`", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


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

@# ==========================================
# 5. الأوامر المباشرة والنصية المحدثة
# ==========================================

@bot.command(name="مساعدة", aliases=["اوامر", "لوحة", "داشبورد", "الاوامر"])
async def cmd_dashboard(ctx):
    embed = discord.Embed(
        title="🌐 اللوحة الاقتصادية والتفاعلية العامة",
        description=(
            "أهلاً بك! يمكنك التحكم بجميع الأنشطة (شراء، بيع، أسهم، أسلحة، وسرقات) عبر الأزرار.\n\n"
            "💡 **الأوامر التي تحتاج كتابة فقط:** اضغط على زر **[📖 دليل الأوامر الكتابية]** بالأسفل لمعرفة كيفية كتابتها!"
        ),
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
## ==========================================
# 6. الأوامر الإدارية (للإدارة والأونر)
# ==========================================

# --- إعطاء وخصم الأموال ---
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

# --- إدارة العقارات (إضافة وحذف) ---
@bot.command(name="اضافة_عقار")
@commands.has_permissions(administrator=True)
async def admin_add_estate(ctx, name: str = None, price: int = None, income: int = None):
    if not name or not price or not income:
        return await ctx.send("❌ الاستخدام: `!اضافة_عقار [اسم_العقار] [السعر] [الدخل_الدوري]`\nمثال: `!اضافة_عقار فندق 1000000 50000`")
    
    # توليد رقم تعريف تلقائي للعقار الجديد
    new_id = str(len(real_estate_market) + 1)
    real_estate_market[new_id] = {"name": name, "price": price, "income": income}
    await ctx.send(f"✅ تم إضافة العقار الجديد برقم **[{new_id}]**: **{name}** | السعر: **${price:,}** | الدخل: **${income:,}**")

@bot.command(name="حذف_عقار")
@commands.has_permissions(administrator=True)
async def admin_remove_estate(ctx, estate_id: str = None):
    if not estate_id or estate_id not in real_estate_market:
        return await ctx.send("❌ اكتب رقم العقار الصحيح لحذفه! مثال: `!حذف_عقار 1`")
    
    removed = real_estate_market.pop(estate_id)
    await ctx.send(f"🗑️ تم حذف عقار **{removed['name']}** من السوق بنجاح.")

# --- إدارة المزاد ---
@bot.command(name="بدء_مزاد")
@commands.has_permissions(administrator=True)
async def admin_start_auction(ctx, item: str = None, price: int = None):
    global current_auction
    if not item or not price:
        return await ctx.send("❌ الاستخدام: `!بدء_مزاد [السلعة] [السعر_الافتتاحي]`\nمثال: `!بدء_مزاد سيارة_نادرة 50000`")
    
    current_auction = {"active": True, "item": item, "price": price, "highest_bidder": None}
    await ctx.send(f"📢 **بدأ المزاد العلني على: {item}** بسعر افتتاحي **${price:,}**!\n💡 للمزايدة اكتب: `!مزايدة [المبلغ]`")

@bot.command(name="انهاء_المزاد")
@commands.has_permissions(administrator=True)
async def admin_end_auction(ctx):
    global current_auction
    if not current_auction["active"]:
        return await ctx.send("❌ لا يوجد مزاد قائم حالياً!")
    
    if current_auction["highest_bidder"]:
        winner_id = current_auction["highest_bidder"]
        price = current_auction["price"]
        get_user_data(winner_id)["wallet"] -= price
        await ctx.send(f"🎉 **انتهى المزاد!** فاز بالمزاد <@{winner_id}> بسعر **${price:,}** لسلعة ({current_auction['item']})!")
    else:
        await ctx.send("🔨 انتهى المزاد دون تقديم أي مزايدات.")
    
    current_auction["active"] = False

# --- سحب اليانصيب ---
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
# 🔫 متجر الأسلحة والحقيبة
# ==========================================

@bot.command(name="متجر_الاسلحة")
async def weapons_shop(ctx):
    shop_text = "🔫 **متجر الأسلحة** (تزيد نسبة نجاح السرقات):\n\n"
    for w_id, w_info in WEAPONS_MARKET.items():
        shop_text += f"**[{w_id}] {w_info['name']}** | السعر: **${w_info['price']:,}** | نسبة النجاح المضافة: **+{int(w_info['bonus']*100)}%**\n"
    shop_text += "\nلشراء سلاح اكتب: `!شراء_سلاح [رقم_السلاح]`"
    await ctx.send(shop_text)

@bot.command(name="شراء_سلاح")
async def buy_weapon(ctx, weapon_id: str = None):
    if not weapon_id or weapon_id not in WEAPONS_MARKET:
        return await ctx.send("❌ يرجى كتابة رقم سلاح صحيح. مثال: `!شراء_سلاح 1`")
    
    weapon = WEAPONS_MARKET[weapon_id]
    user_data = get_user_data(ctx.author.id)
    
    if weapon["name"] in user_data.get("inventory", []):
        return await ctx.send("❌ أنت تملك هذا السلاح مسبقاً في حقيبتك!")
        
    if user_data["wallet"] < weapon["price"]:
        return await ctx.send("❌ لا تملك كاش كافي في محفظتك لشراء هذا السلاح!")
        
    user_data["wallet"] -= weapon["price"]
    user_data.setdefault("inventory", []).append(weapon["name"])
    await ctx.send(f"🔫 تم شراء **{weapon['name']}** بنجاح! السلاح الآن في حقيبتك وستزيد فرصك في السرقات.")

@bot.command(name="حقيبتي")
async def my_inventory(ctx):
    inv = get_user_data(ctx.author.id).get("inventory", [])
    if not inv: 
        return await ctx.send("🎒 حقيبتك فارغة حالياً.")
    
    weapons_list = "\n".join([f"🔸 {w}" for w in inv])
    await ctx.send(f"🎒 **حقيبتك الشخصية تحتوي على:**\n{weapons_list}")

# ==========================================
# 📜 نظام العقود التفاعلي بالأزرار
# ==========================================

class ContractButtonsView(discord.ui.View):
    def __init__(self, target_member, gang_name, amount, days):
        super().__init__(timeout=86400) # مهلة يوم كامل
        self.target_member = target_member
        self.gang_name = gang_name
        self.amount = amount
        self.days = days

    @discord.ui.button(label="✍️ قبول وتوقيع العقد", style=discord.ButtonStyle.success)
    async def accept_contract(self, interaction: discord.Interaction, button: discord.ui.Button):
        # التأكد أن من يضغط الزر هو العضو المعني بالعقد فقط
        if interaction.user.id != self.target_member.id:
            await interaction.response.send_message("❌ هذا العقد ليس موجهاً لك!", ephemeral=True)
            return

        # التأكد من توفر المبلغ في الخزينة عند التوقيع
        if gangs_data[self.gang_name]["bank"] < self.amount:
            await interaction.response.send_message("❌ تعذر التوقيع! خزينة العصابة لا تملك المبلغ الكافي حالياً.", ephemeral=True)
            return

        # خصم المبلغ من الخزينة وإضافة العضو
        gangs_data[self.gang_name]["bank"] -= self.amount
        gangs_data[self.gang_name]["members"].append(interaction.user.id)

        user_data = get_user_data(interaction.user.id)
        user_data["gang"] = self.gang_name
        claim_time = time.time() + (self.days * 86400)
        user_data["contract"] = {"amount": self.amount, "claim_time": claim_time}

        # تعطيل الأزرار بعد التوقيع
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)

        await interaction.response.send_message(
            f"🎉 **مبروك!** تم توقيع العقد وانضمامك رسمياً لعصابة **{self.gang_name}**!\n"
            f"يمكنك استلام مستحقاتك (${self.amount:,}) بعد انتهاء المدة بأمر: `!استلام_العقد`"
        )

    @discord.ui.button(label="❌ رفض العقد", style=discord.ButtonStyle.danger)
    async def reject_contract(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target_member.id:
            await interaction.response.send_message("❌ هذا العقد ليس موجهاً لك!", ephemeral=True)
            return

        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.send_message(f"🚫 تم رفض العقد الموجه من عصابة **{self.gang_name}**.")

@bot.command(name="عقد")
async def invite_contract(ctx, member: discord.Member = None, amount: int = None, days: int = None):
    leader_data = get_user_data(ctx.author.id)
    gang_name = leader_data.get("gang")
    
    if not gang_name or gangs_data[gang_name]["owner"] != ctx.author.id:
        return await ctx.send("❌ يجب أن تكون قائد عصابة لتقديم عقود للأعضاء!")
    if not member or not amount or not days:
        return await ctx.send("❌ الاستخدام الصحيح: `!عقد @العضو [المبلغ] [عدد_الايام]`\nمثال: `!عقد @محمد 50000 3`")
    if member.id == ctx.author.id:
        return await ctx.send("❌ لا يمكنك تقديم عقد لنفسك!")
        
    if gangs_data[gang_name]["bank"] < amount:
        return await ctx.send("❌ خزينة العصابة لا تملك هذا المبلغ لتغطية العقد!")

    view = ContractButtonsView(target_member=member, gang_name=gang_name, amount=amount, days=days)
    
    embed = discord.Embed(
        title="📜 عرض عقد انضمام رسمي",
        description=(
            f"يقدم القائد {ctx.author.mention} عقداً للعضو {member.mention} للانضمام إلى **{gang_name}**.\n\n"
            f"💵 **قيمة العقد:** ${amount:,}\n"
            f"⏳ **مدة العقد:** {days} أيام\n\n"
            f"اضغط على الأزرار أدناه للقبول والتوقيع أو الرفض:"
        ),
        color=discord.Color.blue()
    )
    
    await ctx.send(content=f"{member.mention} لديك عرض عقد جديد!", embed=embed, view=view)

@bot.command(name="استلام_العقد")
async def claim_contract(ctx):
    user_data = get_user_data(ctx.author.id)
    contract = user_data.get("contract")
    
    if not contract: 
        return await ctx.send("❌ ليس لديك أي عقد مستحق للاستلام!")
    
    if time.time() < contract["claim_time"]:
        remaining_hours = int((contract["claim_time"] - time.time()) / 3600)
        return await ctx.send(f"⏳ لم يحن وقت استلام قيمة العقد بعد! المتبقي تقريباً: **{remaining_hours} ساعة**.")
        
    user_data["wallet"] += contract["amount"]
    amount = contract["amount"]
    user_data["contract"] = None
    await ctx.send(f"🎉 انتهت مدة العقد بنجاح! تم تحويل **${amount:,}** إلى محفظتك الشخصية.")


# ==========================================
# 7. تشغيل البوت
# ==========================================
TOKEN = os.environ.get("DISCORD_TOKEN") or os.environ.get("BOT_TOKEN")

if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ لم يتم العثور على التوكين في متغيرات البيئة!")
