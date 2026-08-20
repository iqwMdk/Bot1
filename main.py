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

async def update_user_role(member: discord.Member, work_count):
    # مسميات الرولات كما هي في سيرفر الديسكورد
    role_mapping = {
        "🔰 متدرب": "🔰 متدرب", 
        "💼 موظف": "💼 موظف", 
        "👔 مشرف": "👔 مشرف", 
        "👑 مدير": "👑 مدير"
    }
    
    current_rank, _ = get_user_rank(work_count)
    role_name = role_mapping.get(current_rank["name"])
    role = discord.utils.get(member.guild.roles, name=role_name)
    
    if role:
        # إزالة الرولات القديمة للوظائف
        all_job_roles = [discord.utils.get(member.guild.roles, name=n) for n in role_mapping.values()]
        await member.remove_roles(*[r for r in all_job_roles if r in member.roles])
        
        # إضافة الرول الجديد
        if role not in member.roles:
            await member.add_roles(role)


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

JOB_RANKS = [
    {"name": "🔰 متدرب", "min_work": 0, "min_salary": 1000, "max_salary": 3000},
    {"name": "💼 موظف", "min_work": 5, "min_salary": 3000, "max_salary": 5000},
    {"name": "👔 مشرف", "min_work": 20, "min_salary": 5000, "max_salary": 7500},
    {"name": "👑 مدير", "min_work": 30, "min_salary": 8000, "max_salary": 12000}
]

def get_user_rank(work_count):
    current_rank = JOB_RANKS[0]
    next_rank = None
    for i, rank in enumerate(JOB_RANKS):
        if work_count >= rank["min_work"]:
            current_rank = rank
            if i + 1 < len(JOB_RANKS):
                next_rank = JOB_RANKS[i + 1]
        else:
            break
    return current_rank, next_rank

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

        # ==========================================
    # زر بدء العمل الوظيفي
    # ==========================================
    @discord.ui.button(label="💼 ابدأ العمل", style=discord.ButtonStyle.green, row=2)
    async def btn_do_work(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        user_data = get_user_data(user_id)
        
        import time
        current_time = time.time()
        cooldowns = user_data.setdefault("work_cooldown", 0)
        
        if current_time < cooldowns:
            remaining = int(cooldowns - current_time)
            hours = remaining // 3600
            minutes = (remaining % 3600) // 60
            return await interaction.response.send_message(f"⏳ يجب عليك الانتظار **{hours} ساعة و {minutes} دقيقة** قبل أن تتمكن من العمل مرة أخرى.", ephemeral=True)
        
        user_data["work_cooldown"] = current_time + 3600
        
        # 1. زيادة مرات العمل
        work_count = user_data.get("work_count", 0) + 1
        user_data["work_count"] = work_count
        
        # ⬅️ 2. [حط هذا السطر هنا] تحديث رول العضو في الديسكورد تلقائياً
        try:
            await update_user_role(interaction.user, work_count)
        except Exception as e:
            print(f"خطأ في إعطاء الرول: {e}")

        # 3. حساب الراتب وباقي الكود...
        current_rank, _ = get_user_rank(work_count)
        salary = random.randint(current_rank["min_salary"], current_rank["max_salary"])
        user_data["wallet"] = user_data.get("wallet", 0) + salary
        
        embed = discord.Embed(title="💼 لوحة العمل الوظيفي", color=discord.Color.blue())
        embed.add_field(name="الرتبة الحالية", value=current_rank["name"], inline=True)
        embed.add_field(name="الراتب المستلم", value=f"**${salary:,}** 💵", inline=True)
        embed.add_field(name="إجمالي مرات العمل", value=str(work_count), inline=False)
        embed.set_footer(text="يمكنك العمل مرة أخرى بعد ساعة كاملة.")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ==========================================
    # زر السجل الوظيفي
    # ==========================================
    @discord.ui.button(label="📊 وثائق وظيفتي", style=discord.ButtonStyle.secondary, row=2)
    async def btn_job_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        user_data = get_user_data(user_id)
        work_count = user_data.get("work_count", 0)
        
        current_rank, next_rank = get_user_rank(work_count)
        
        embed = discord.Embed(title=f"📋 السجل الوظيفي لـ {interaction.user.display_name}", color=discord.Color.gold())
        embed.add_field(name="الرتبة الحالية", value=current_rank["name"], inline=True)
        embed.add_field(name="عدد مرات العمل", value=str(work_count), inline=True)
        
        if next_rank:
            needed = next_rank["min_work"] - work_count
            embed.add_field(name="الترقية القادمة", value=f"إلى **{next_rank['name']}** (متبقي **{needed}** مرات عمل)", inline=False)
        else:
            embed.add_field(name="الترقية القادمة", value="لقد وصلت إلى أعلى رتبة متاحـة! 👑", inline=False)
            
        await interaction.response.send_message(embed=embed, ephemeral=True)

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

    @discord.ui.button(label="💰 جمع الأرباح (3h)", style=discord.ButtonStyle.success, row=0)
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
        update_stocks_market()
        embed = discord.Embed(title="📈 مؤشرات وسوق الأسهم المحلية", color=discord.Color.green())
        for code, info in STOCKS.items():
            sign = "+" if info["change"] >= 0 else ""
            embed.add_field(
                name=f"{info['trend']} {info['name']} ({code})",
                value=f"السعر: **${info['price']}**\nالتغير: **{sign}{info['change']}%**",
                inline=True
            )
        embed.set_footer(text="الشراء والبيع عبر الأوامر النصية: !شراء_سهم | !بيع_سهم | !اسهمي")
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
    @discord.ui.button(label="🚨 بدء عملية سطو", style=discord.ButtonStyle.danger, row=3)
    async def btn_start_heist(self, interaction: discord.Interaction, button: discord.ui.Button):
        class TargetSelectView(View):
            @discord.ui.button(label="🏦 السطو على بنك المدينة (البوت)", style=discord.ButtonStyle.primary)
            async def target_bank(self, inter: discord.Interaction, btn: Button):
                session = HeistSession("bank", "بنك المدينة المركزي", "عصابتك")
                await inter.response.send_message("🚨 **تم تجهيز خطة السطو على البنك!** ليقم باقي الأعضاء باختيار أدوارهم خلال 3 دقائق:", view=HeistLobbyView(session))

            @discord.ui.button(label="💀 السطو على عصابة منافسة", style=discord.ButtonStyle.danger)
            async def target_gang(self, inter: discord.Interaction, btn: Button):
                session = HeistSession("gang", "خزنة العصابة المنافسة", "عصابتك")
                await inter.response.send_message("🚨 **تم تجهيز خطة السطو على العصابة!** ليقم باقي الأعضاء باختيار أدوارهم خلال 3 دقائق:", view=HeistLobbyView(session))

        await interaction.response.send_message("🎯 **اختر هدف عملية السطو:**", view=TargetSelectView(), ephemeral=True)

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

# ==========================================
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
# 📈 نظام تداول الأسهم (شراء / بيع / محفظة)
# ==========================================

@bot.command(name="شراء_سهم")
async def buy_stock(ctx, code: str = None, amount: int = None):
    if not code or not amount or amount <= 0:
        return await ctx.send("❌ الاستخدام الصحيح: `!شراء_سهم [رمز_السهم] [العدد]`\nمثال: `!شراء_سهم ARAMCO 5`")
    
    code = code.upper()
    if code not in STOCKS:
        return await ctx.send("❌ رمز السهم غير صحيح! الرموز المتاحة: `ARAMCO`, `STC`, `RAJHI`")
    
    stock = STOCKS[code]
    total_cost = stock["price"] * amount
    user_data = get_user_data(ctx.author.id)
    
    if user_data["wallet"] < total_cost:
        return await ctx.send(f"❌ لا تملك كاش كافي! تكلفة شراء {amount} أسهم هي **${total_cost:,}**.")
    
    user_data["wallet"] -= total_cost
    user_stocks = user_data.setdefault("stocks", {})
    user_stocks[code] = user_stocks.get(code, 0) + amount
    
    await ctx.send(f"✅ تم شراء **{amount}** سهم في **{stock['name']}** بسعر **${total_cost:,}**!")

@bot.command(name="بيع_سهم")
async def sell_stock(ctx, code: str = None, amount: int = None):
    if not code or not amount or amount <= 0:
        return await ctx.send("❌ الاستخدام الصحيح: `!بيع_سهم [رمز_السهم] [العدد]`\nمثال: `!بيع_سهم ARAMCO 2`")
    
    code = code.upper()
    if code not in STOCKS:
        return await ctx.send("❌ رمز السهم غير صحيح!")
    
    user_data = get_user_data(ctx.author.id)
    user_stocks = user_data.get("stocks", {})
    
    if user_stocks.get(code, 0) < amount:
        return await ctx.send(f"❌ لا تملك هذا العدد من الأسهم! عدد أسهمك المتاحة في {code}: **{user_stocks.get(code, 0)}**")
    
    update_stocks_market()
    stock = STOCKS[code]
    total_return = stock["price"] * amount
    
    user_stocks[code] -= amount
    user_data["wallet"] += total_return
    
    await ctx.send(f"💰 تم بيع **{amount}** سهم في **{stock['name']}** بسعر اليوم واستلمت **${total_return:,}**!")

@bot.command(name="اسهمي")
async def my_stocks(ctx):
    user_data = get_user_data(ctx.author.id)
    user_stocks = user_data.get("stocks", {})
    
    active_stocks = {k: v for k, v in user_stocks.items() if v > 0}
    if not active_stocks:
        return await ctx.send("📊 لا تملك أي أسهم في محفظتك حالياً.")
    
    update_stocks_market()
    msg = f"📊 **محفظة أسهم {ctx.author.display_name}:**\n\n"
    total_value = 0
    
    for code, count in active_stocks.items():
        stock_info = STOCKS[code]
        current_val = stock_info["price"] * count
        total_value += current_val
        msg += f"• **{stock_info['name']} ({code})**: {count} سهم | القيمة الحالية: **${current_val:,}** ({stock_info['trend']})\n"
    
    msg += f"\n💵 **إجمالي قيمة محفظتك:** **${total_value:,}**"
    await ctx.send(msg)


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
    await ctx.send(f"🎉 انتهت مدة العقد بنجاح! تم تحويل **${amount:,}** إلى محفظتك")
import asyncio
import random
import discord
from discord.ui import View, Button

#import os
import random
import asyncio
import threading
import time
from typing import Optional
from datetime import datetime, timedelta

import discord
from discord.ext import commands
from discord.ui import View, Button
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
# 3. قواعد البيانات والأسواق
# ==========================================
users_data = {}
gangs_data = {
    "عصابة الفرسان": {"owner": 12345678, "members": [12345678], "bank": 250000},
    "عصابة الصقور": {"owner": 87654321, "members": [87654321], "bank": 500000}
}
lottery_tickets = []
current_auction = {"active": False, "item": None, "price": 0, "highest_bidder": None}

WEAPONS_MARKET = {
    "1": {"name": "سكين", "price": 10000, "bonus": 0.03},
    "2": {"name": "مسدس", "price": 35000, "bonus": 0.07},
    "3": {"name": "رشاش", "price": 80000, "bonus": 0.12},
    "4": {"name": "قناص", "price": 150000, "bonus": 0.20}
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
    "ARAMCO": {"name": "أرامكو", "price": 100, "change": 2.5, "trend": "📈"},
    "STC": {"name": "الاتصالات", "price": 50, "change": -1.2, "trend": "📉"},
    "RAJHI": {"name": "الراجحي", "price": 80, "change": 4.1, "trend": "📈"}
}

ROBBERIES = {
    "1": {"name": "متجر صغير", "reward": 5000, "risk": 0.2},
    "2": {"name": "بنك محلي", "reward": 25000, "risk": 0.5},
    "3": {"name": "البنك المركزي", "reward": 100000, "risk": 0.8}
}

JOB_RANKS = [
    {"name": "🔰 متدرب", "min_work": 0, "min_salary": 1000, "max_salary": 3000},
    {"name": "💼 موظف", "min_work": 5, "min_salary": 3000, "max_salary": 5000},
    {"name": "👔 مشرف", "min_work": 20, "min_salary": 5000, "max_salary": 7500},
    {"name": "👑 مدير", "min_work": 30, "min_salary": 8000, "max_salary": 12000}
]

def update_stocks_market():
    for code, info in STOCKS.items():
        change_pct = round(random.uniform(-5.0, 5.0), 2)
        multiplier = 1 + (change_pct / 100)
        info["price"] = max(10, int(info["price"] * multiplier))
        info["change"] = change_pct
        info["trend"] = "📈" if change_pct >= 0 else "📉"

def get_user_data(user_id: int):
    if user_id not in users_data:
        users_data[user_id] = {
            "wallet": 1000, "bank": 0, "real_estates": [], "cars": [],
            "gang": None, "gang_invite": None, "immunity_until": None,
            "stocks": {}, "dirty_money": 0, "inventory": [], "contract": None,
            "last_profit_collect": 0, "work_count": 0, "work_cooldown": 0
        }
    return users_data[user_id]

def get_user_rank(work_count):
    current_rank = JOB_RANKS[0]
    next_rank = None
    for i, rank in enumerate(JOB_RANKS):
        if work_count >= rank["min_work"]:
            current_rank = rank
            if i + 1 < len(JOB_RANKS): next_rank = JOB_RANKS[i + 1]
        else: break
    return current_rank, next_rank

async def update_user_role(member: discord.Member, work_count):
    role_mapping = {"🔰 متدرب": "🔰 متدرب", "💼 موظف": "💼 موظف", "👔 مشرف": "👔 مشرف", "👑 مدير": "👑 مدير"}
    current_rank, _ = get_user_rank(work_count)
    role_name = role_mapping.get(current_rank["name"])
    role = discord.utils.get(member.guild.roles, name=role_name)
    if role:
        all_job_roles = [discord.utils.get(member.guild.roles, name=n) for n in role_mapping.values()]
        await member.remove_roles(*[r for r in all_job_roles if r and r in member.roles])
        if role not in member.roles:
            await member.add_roles(role)

# === 1. إعداد قاعدة البيانات ===
async def init_db():
    async with aiosqlite.connect("gangs.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS gangs (
                name TEXT PRIMARY KEY,
                leader_id INTEGER,
                balance INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS players (
                user_id INTEGER PRIMARY KEY,
                wallet INTEGER DEFAULT 100000,
                gang_name TEXT,
                FOREIGN KEY(gang_name) REFERENCES gangs(name)
            )
        """)
        await db.commit()

heist_cooldowns = {}

# === 2. لوحة التهكير للأدوار (3 دقائق كحد أقصى) ===
class RoleHackingView(discord.ui.View):
    def __init__(self, hacker, tech, attacker_gang, target_gang, target_balance):
        super().__init__(timeout=180) # 180 ثانية = 3 دقائق
        self.hacker = hacker
        self.tech = tech
        self.attacker_gang = attacker_gang
        self.target_gang = target_gang
        self.target_balance = target_balance
        
        self.hacker_done = False
        self.tech_done = False

    # زر المهندس (Hacker)
    @discord.ui.button(label="💻 [المهندس] اختراق جدار الحماية", style=discord.ButtonStyle.primary, row=0)
    async def hacker_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.hacker:
            return await interaction.response.send_message("❌ هذا الزر مخصص لـ **المهندس** فقط!", ephemeral=True)
        
        if self.hacker_done:
            return await interaction.response.send_message("✅ لقد أنهيت مهمتك بالفعل!", ephemeral=True)

        self.hacker_done = True
        button.disabled = True
        button.style = discord.ButtonStyle.success
        button.label = "✅ تم كسر التشفير"
        
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(f"🔓 نجح المهندس {interaction.user.mention} في اختراق جدار الحماية!")
        await self.check_completion(interaction)

    # زر الفني (Technician)
    @discord.ui.button(label="🔧 [الفني] تعطيل أجهزة الإنذار", style=discord.ButtonStyle.primary, row=1)
    async def tech_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.tech:
            return await interaction.response.send_message("❌ هذا الزر مخصص لـ **الفني** فقط!", ephemeral=True)

        if self.tech_done:
            return await interaction.response.send_message("✅ لقد أنهيت مهمتك بالفعل!", ephemeral=True)

        self.tech_done = True
        button.disabled = True
        button.style = discord.ButtonStyle.success
        button.label = "✅ تم تعطيل الإنذار"
        
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(f"⚡ نجح الفني {interaction.user.mention} في قطوع أسلاك الإنذار!")
        await self.check_completion(interaction)

    # التحقق من إكمال المهمة أو الفشل
    async def check_completion(self, interaction: discord.Interaction):
        if self.hacker_done and self.tech_done:
            self.stop()
            # نجاح العملية - سرقة 30% إلى 50%
            stolen_percent = random.randint(30, 50)
            stolen_amount = int(self.target_balance * (stolen_percent / 100))

            async with aiosqlite.connect("gangs.db") as db:
                await db.execute("UPDATE gangs SET balance = balance - ? WHERE name = ?", (stolen_amount, self.target_balance))
                await db.execute("UPDATE gangs SET balance = balance + ? WHERE name = ?", (stolen_amount, self.attacker_gang))
                await db.commit()

            embed = discord.Embed(title="🎉 نجحت عملية السرقة بالكامل!", color=discord.Color.green())
            embed.description = f"تم فتح الخزنة وسرقة **${stolen_amount:,}** بنجاح لحساب عصابة **{self.attacker_gang}**!"
            await interaction.channel.send(embed=embed)

    async def on_timeout(self):
        # في حال انتهت الـ 3 دقائق دون إكمال المهمة
        for child in self.children:
            child.disabled = True
            
        penalty = 10000 # خصم 10,000 كضرر وفشل
        async with aiosqlite.connect("gangs.db") as db:
            await db.execute("UPDATE gangs SET balance = MAX(0, balance - ?) WHERE name = ?", (penalty, self.attacker_gang))
            await db.commit()

        embed = discord.Embed(title="💥 انتهى الوقت وفشلت العملية!", color=discord.Color.red())
        embed.description = f"مرت 3 دقائق دون إكمال التهكير! فعلت الشرطة أجهزة الأمان وتضررت خزنتكم بخصم **${penalty:,}**."
        # يحتاج إرسال رسالة التايم أوت للمناهج المتاحة عبر الـ channel إذا لزم

# === 3. واجهة التجمع وتوزيع الأدوار ===
class HeistLobbyView(discord.ui.View):
    def __init__(self, leader, attacker_gang, target_gang, target_balance):
        super().__init__(timeout=120)
        self.leader = leader
        self.attacker_gang = attacker_gang
        self.target_gang = target_gang
        self.target_balance = target_balance
        
        self.hacker = None
        self.tech = None

    @discord.ui.button(label="الانضمام كـ [مهندس 💻]", style=discord.ButtonStyle.secondary)
    async def join_hacker(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.hacker:
            return await interaction.response.send_message("❌ دور المهندس مأخوذ بالفعل!", ephemeral=True)
        self.hacker = interaction.user
        await interaction.response.send_message(f"✅ انضم {interaction.user.mention} كـ **مهندس** للعملية.")

    @discord.ui.button(label="الانضمام كـ [فني 🔧]", style=discord.ButtonStyle.secondary)
    async def join_tech(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.tech:
            return await interaction.response.send_message("❌ دور الفني مأخوذ بالفعل!", ephemeral=True)
        self.tech = interaction.user
        await interaction.response.send_message(f"✅ انضم {interaction.user.mention} كـ **فني** للعملية.")

    @discord.ui.button(label="انطلاق العملية 🚀", style=discord.ButtonStyle.success, row=1)
    async def start_heist(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.leader:
            return await interaction.response.send_message("❌ القائد فقط من يستطيع بدء الهجوم!", ephemeral=True)
        
        if not self.hacker or not self.tech:
            return await interaction.response.send_message("❌ يجب اكتمال الطاقم (مهندس + فني) لبدء العملية!", ephemeral=True)

        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()

        # فتح لوحة التهكير الخاصة بالأدوار والتوقيت (3 دقائق)
        hack_view = RoleHackingView(self.hacker, self.tech, self.attacker_gang, self.target_gang, self.target_balance)
        embed = discord.Embed(
            title="⏱️ بدأت التغطية والتهكير! (معكم 3 دقائق)",
            description=f"**المهندس:** {self.hacker.mention}\n**الفني:** {self.tech.mention}\n\nاضغطوا على أزراركم المخصصة أدناه لإكمال العملية قبل فوات الوقت!",
            color=discord.Color.gold()
        )
        await interaction.followup.send(embed=embed, view=hack_view)

# === 4. أمر البدء بالسرقة ===
@bot.command(name="سرقة_عصابة")
async def rob_gang(ctx, *, target_gang: str):
    user_id = ctx.author.id
    now = asyncio.get_event_loop().time()

    # كول داون 15 دقيقة
    if user_id in heist_cooldowns and now < heist_cooldowns[user_id]:
        remaining = int(heist_cooldowns[user_id] - now)
        return await ctx.send(f"⏳ يجب الانتظار **{remaining // 60} دقيقة** قبل التخطيط لسرقة جديدة.")

    async with aiosqlite.connect("gangs.db") as db:
        # فحص عصابة اللاعب وخزنتها
        async with db.execute("SELECT g.name, g.balance FROM players p JOIN gangs g ON p.gang_name = g.name WHERE p.user_id = ?", (user_id,)) as cursor:
            attacker_data = await cursor.fetchone()
            if not attacker_data:
                return await ctx.send("❌ أنت لست عضواً في أي عصابة!")
            attacker_gang, attacker_balance = attacker_data

        # شرط الـ 10,000 في الخزنة
        if attacker_balance < 10000:
            return await ctx.send(f"❌ يجب توفر **$10,000** على الأقل في خزنة عصابتكم (**{attacker_gang}**) للبدء.")

        # فحص عصابة الهدف
        async with db.execute("SELECT balance FROM gangs WHERE name = ?", (target_gang,)) as cursor:
            target_data = await cursor.fetchone()
            if not target_data:
                return await ctx.send("❌ العصابة المستهدفة غير موجودة!")
            target_balance = target_data[0]

    heist_cooldowns[user_id] = now + 900 # 15 دقيقة كول داون

    embed = discord.Embed(
        title=f"⚔️ التخطيط لسرقة عصابة [{target_gang}]",
        description=f"القائد: {ctx.author.mention}\nالعصابة: **{attacker_gang}**\n\n**الرجاء اختيار الأدوار ثم الضغط على انطلاق العملية.**",
        color=discord.Color.dark_red()
    )
    view = HeistLobbyView(ctx.author, attacker_gang, target_gang, target_balance)
    await ctx.send(embed=embed, view=view)

@bot.event
async def on_ready():
    await init_db()
    print("بوت الديسكورد جاهز للعمل بالكامل!")


# ==========================================
# 5. المكونات التفاعلية للقوائم (Selects)
# ==========================================

class WeaponsShopSelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=item['name'], value=key, description=f"السعر: ${item['price']:,} | +{int(item['bonus']*100)}%") for key, item in WEAPONS_MARKET.items()]
        super().__init__(placeholder="اختر سلاحاً لشراؤه...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]
        weapon = WEAPONS_MARKET[selected]
        user_data = get_user_data(interaction.user.id)
        if weapon["name"] in user_data.get("inventory", []):
            return await interaction.response.send_message("❌ أنت تملك هذا السلاح مسبقاً!", ephemeral=True)
        if user_data["wallet"] < weapon["price"]:
            return await interaction.response.send_message("❌ لا تملك كاش كافي!", ephemeral=True)
        user_data["wallet"] -= weapon["price"]
        user_data.setdefault("inventory", []).append(weapon["name"])
        await interaction.response.send_message(f"🔫 تم شراء **{weapon['name']}** بنجاح!", ephemeral=True)

class RealEstateSelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=item['name'], value=key, description=f"السعر: ${item['price']:,} | الدخل: ${item['income']:,}") for key, item in real_estate_market.items()]
        super().__init__(placeholder="اختر عقاراً لشراؤه...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]
        estate = real_estate_market[selected]
        data = get_user_data(interaction.user.id)
        if data["wallet"] < estate["price"]:
            return await interaction.response.send_message(f"❌ لا تملك المبلغ الكافي لشراء {estate['name']}!", ephemeral=True)
        data["wallet"] -= estate["price"]
        data["real_estates"].append(estate["name"])
        await interaction.response.send_message(f"🎉 تم شراء **{estate['name']}** بنجاح!", ephemeral=True)

class RobberySelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=item['name'], value=key, description=f"المكافأة: ${item['reward']:,} | الخطر: {int(item['risk']*100)}%") for key, item in ROBBERIES.items()]
        super().__init__(placeholder="اختر هدف السرقة...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        data = get_user_data(interaction.user.id)
        if not data["gang"]:
            return await interaction.response.send_message("❌ ينبغي أن تكون عضواً في عصابة لبدء السرقة!", ephemeral=True)
        selected = self.values[0]
        rob = ROBBERIES[selected]
        gang_name = data["gang"]
        members_count = len(gangs_data[gang_name]["members"])
        gang_bonus = (members_count - 1) * 0.03
        weapon_bonus = max([w_info["bonus"] for w in data.get("inventory", []) for w_id, w_info in WEAPONS_MARKET.items() if w_info["name"] == w] or [0])
        effective_risk = max(0.05, rob["risk"] - gang_bonus - weapon_bonus)

        if random.random() > effective_risk:
            gangs_data[gang_name]["bank"] += rob["reward"]
            await interaction.response.send_message(f"🔥 **نجحت السرقة!** تمت إضافة **${rob['reward']:,}** إلى خزينة العصابة.", ephemeral=True)
        else:
            await interaction.response.send_message("🚨 **فشلت السرقة!** حاصرتكم الشرطة وهربتم بصعوبة بدون أرباح.", ephemeral=True)

class ContractSelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=item['name'], value=key, description=f"التكلفة: ${item['cost']:,} | الربح: ${item['reward']:,}") for key, item in GANG_CONTRACTS.items()]
        super().__init__(placeholder="اختر عقداً لتنفيذه...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        data = get_user_data(interaction.user.id)
        if not data["gang"]: return await interaction.response.send_message("❌ يجب أن تكون في عصابة لتنفيذ العقود!", ephemeral=True)
        selected = self.values[0]
        c = GANG_CONTRACTS[selected]
        if data["wallet"] < c["cost"]: return await interaction.response.send_message(f"❌ لا تملك تكلفة العقد (${c['cost']:,})!", ephemeral=True)
        data["wallet"] -= c["cost"]
        gangs_data[data["gang"]]["bank"] += c["reward"]
        await interaction.response.send_message(f"📜 تم تنفيذ **{c['name']}** ونزول **${c['reward']:,}** في خزينة العصابة!", ephemeral=True)

class BlackMarketSelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=item['name'], value=key, description=f"السعر: ${item['price']:,}") for key, item in BLACK_MARKET.items()]
        super().__init__(placeholder="اختر عنصرًا من السوق الأسود...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]
        item = BLACK_MARKET[selected]
        data = get_user_data(interaction.user.id)
        if data["wallet"] < item["price"]: return await interaction.response.send_message("❌ لا تملك المال الكافي!", ephemeral=True)
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

# ==========================================
# 6. لوحة التحكم التفاعلية العامة (الداشبورد)
# ==========================================

class CompleteInteractiveDashboardView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🏢 سوق العقارات والشركات", style=discord.ButtonStyle.success, row=0)
    async def btn_real_estate(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = View(); view.add_item(RealEstateSelect())
        await interaction.response.send_message("🏬 **اختر العقار الذي ترغب بشراؤه مباشرة:**", view=view, ephemeral=True)

    @discord.ui.button(label="💳 رصيدي وحسابي", style=discord.ButtonStyle.primary, row=0)
    async def btn_balance(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = get_user_data(interaction.user.id)
        msg = f"👤 **بيانات {interaction.user.display_name}:**\n💵 المحفظة الكاش: **${data['wallet']:,}**\n🏦 البنك: **${data['bank']:,}**\n🧼 أموال مشبوهة: **${data['dirty_money']:,}**"
        await interaction.response.send_message(msg, ephemeral=True)

    @discord.ui.button(label="💰 جمع الأرباح (3h)", style=discord.ButtonStyle.success, row=0)
    async def btn_collect_profit(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = get_user_data(interaction.user.id)
        if not data["real_estates"]: return await interaction.response.send_message("❌ لا تملك عقارات أو شركات حالياً!", ephemeral=True)
        last_collect = data.get("last_profit_collect", 0)
        now = time.time()
        cooldown = 10800
        if now - last_collect < cooldown:
            remaining = int(cooldown - (now - last_collect))
            return await interaction.response.send_message(f"⏳ **استلمت أرباحك مسبقاً!** متبقي: **{remaining // 3600} ساعة و {(remaining % 3600) // 60} دقيقة**.", ephemeral=True)
        total = sum([item["income"] for name in data["real_estates"] for item in real_estate_market.values() if item["name"] == name])
        data["wallet"] += total
        data["last_profit_collect"] = now
        await interaction.response.send_message(f"💰 تم استلام أرباحك اليومية بقيمة **${total:,}**!", ephemeral=True)

    @discord.ui.button(label="🔫 متجر الأسلحة", style=discord.ButtonStyle.danger, row=1)
    async def btn_weapons_shop(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = View(); view.add_item(WeaponsShopSelect())
        await interaction.response.send_message("🔫 **اختر السلاح المراد شراؤه لزيادة نسبة نجاح السرقات:**", view=view, ephemeral=True)

    @discord.ui.button(label="🎒 حقيبتي", style=discord.ButtonStyle.secondary, row=1)
    async def btn_my_inv(self, interaction: discord.Interaction, button: discord.ui.Button):
        inv = get_user_data(interaction.user.id).get("inventory", [])
        if not inv: return await interaction.response.send_message("🎒 حقيبتك فارغة حالياً.", ephemeral=True)
        await interaction.response.send_message(f"🎒 **محتويات حقيبتك الشخصية:**\n" + "\n".join([f"🔸 {w}" for w in inv]), ephemeral=True)

    @discord.ui.button(label="📈 سوق الأسهم", style=discord.ButtonStyle.secondary, row=1)
    async def btn_stocks(self, interaction: discord.Interaction, button: discord.ui.Button):
        update_stocks_market()
        embed = discord.Embed(title="📈 مؤشرات وسوق الأسهم المحلية", color=discord.Color.green())
        for code, info in STOCKS.items():
            sign = "+" if info["change"] >= 0 else ""
            embed.add_field(name=f"{info['trend']} {info['name']} ({code})", value=f"السعر: **${info['price']}**\nالتغير: **{sign}{info['change']}%**", inline=True)
        embed.set_footer(text="الشراء والبيع عبر الأوامر النصية: !شراء_سهم | !بيع_سهم | !اسهمي")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="💼 ابدأ العمل", style=discord.ButtonStyle.green, row=2)
    async def btn_do_work(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_data = get_user_data(interaction.user.id)
        current_time = time.time()
        cooldowns = user_data.setdefault("work_cooldown", 0)
        if current_time < cooldowns:
            remaining = int(cooldowns - current_time)
            return await interaction.response.send_message(f"⏳ يجب الانتظار **{remaining // 3600} ساعة و {(remaining % 3600) // 60} دقيقة**.", ephemeral=True)
        user_data["work_cooldown"] = current_time + 3600
        work_count = user_data.get("work_count", 0) + 1
        user_data["work_count"] = work_count
        try: await update_user_role(interaction.user, work_count)
        except Exception as e: print(f"خطأ رول: {e}")
        current_rank, _ = get_user_rank(work_count)
        salary = random.randint(current_rank["min_salary"], current_rank["max_salary"])
        user_data["wallet"] += salary
        embed = discord.Embed(title="💼 لوحة العمل الوظيفي", color=discord.Color.blue())
        embed.add_field(name="الرتبة", value=current_rank["name"], inline=True)
        embed.add_field(name="الراتب المستلم", value=f"**${salary:,}** 💵", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🏴‍☠️ عصابتي والشركات", style=discord.ButtonStyle.primary, row=2)
    async def btn_my_gang(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = get_user_data(interaction.user.id)
        if not data["gang"]: return await interaction.response.send_message("❌ أنت لست عضواً في أي عصابة حالياً!", ephemeral=True)
        g_name = data["gang"]
        g_info = gangs_data.get(g_name, {"members": [], "bank": 0, "owner": None})
        await interaction.response.send_message(f"🏴‍☠️ **بيانات العصابة [{g_name}]:**\n• القائد: <@{g_info.get('owner', 'غير معروف')}>\n• الأعضاء: {len(g_info['members'])}\n• الخزينة: **${g_info['bank']:,}**", ephemeral=True)

    @discord.ui.button(label="📜 عقود العصابة", style=discord.ButtonStyle.secondary, row=2)
    async def btn_contracts(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = View(); view.add_item(ContractSelect())
        await interaction.response.send_message("📜 **اختر العقد المراد تنفيذه لصالح عصابتك:**", view=view, ephemeral=True)

    @discord.ui.button(label="💣 السرقات الجماعية", style=discord.ButtonStyle.danger, row=2)
    async def btn_robberies(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = View(); view.add_item(RobberySelect())
        await interaction.response.send_message("💣 **اختر المنشأة المراد تنفيذ السرقة عليها:**", view=view, ephemeral=True)

    @discord.ui.button(label="💀 السوق الأسود", style=discord.ButtonStyle.danger, row=3)
    async def btn_black_market(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = View(); view.add_item(BlackMarketSelect())
        await interaction.response.send_message("💀 **قائمة المبيعات في السوق الأسود:**", view=view, ephemeral=True)

    @discord.ui.button(label="🚨 بدء عملية سطو", style=discord.ButtonStyle.danger, row=3)
    async def btn_start_heist(self, interaction: discord.Interaction, button: discord.ui.Button):
        class TargetSelectView(View):
            @discord.ui.button(label="🏦 السطو على البنك المركزي", style=discord.ButtonStyle.primary)
            async def target_bank(self, inter: discord.Interaction, btn: Button):
                session = HeistSession("bank", "البنك المركزي", "عصابتك", 500000)
                await inter.response.send_message("🚨 **تم تجهيز خطة السطو على البنك المركزي!** اختر أعضاء السرقة للبدء:", view=HeistLobbyView(session))

            @discord.ui.button(label="💀 السطو على عصابة منافسة", style=discord.ButtonStyle.danger)
            async def target_gang(self, inter: discord.Interaction, btn: Button):
                await inter.response.send_message("🎯 **اختر العصابة المستهدفة من القائمة:**", view=GangSelectView(), ephemeral=True)

        await interaction.response.send_message("🎯 **اختر هدف عملية السطو المسلح:**", view=TargetSelectView(), ephemeral=True)

    @discord.ui.button(label="📖 دليل الأوامر الكتابية", style=discord.ButtonStyle.primary, row=3)
    async def btn_help_guide(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="📖 دليل الأوامر الكتابية المطلوبة", color=discord.Color.blue())
        embed.add_field(name="📜 عقد العمل", value="`!عقد @اسم_اللاعب [المبلغ] [الأيام]`", inline=False)
        embed.add_field(name="💸 تحويل كاش", value="`!تحويل @اسم_اللاعب [المبلغ]`", inline=False)
        embed.add_field(name="🏴‍☠️ إنشاء عصابة", value="`!انشاء_عصابة [الاسم]`", inline=False)
        embed.add_field(name="💼 الأسهم", value="`!شراء_سهم` | `!بيع_سهم` | `!اسهمي`", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

# ==========================================
# 7. الأوامر المباشرة والنصية
# ==========================================

@bot.command(name="مساعدة", aliases=["اوامر", "لوحة", "داشبورد", "الاوامر"])
async def cmd_dashboard(ctx):
    embed = discord.Embed(
        title="🌐 اللوحة الاقتصادية والتفاعلية العامة",
        description="أهلاً بك! يمكنك التحكم بجميع الأنشطة عبر الأزرار أدناه.",
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
    val = data["wallet"] if amount == "الكل" else int(amount) if amount and amount.isdigit() else 0
    if val <= 0 or data["wallet"] < val: return await ctx.send("❌ مبلغ غير كافٍ!")
    data["wallet"] -= val; data["bank"] += val
    await ctx.send(f"🏦 تم إيداع **${val:,}** في البنك.")

@bot.command(name="سحب")
async def cmd_withdraw(ctx, amount: str = None):
    data = get_user_data(ctx.author.id)
    val = data["bank"] if amount == "الكل" else int(amount) if amount and amount.isdigit() else 0
    if val <= 0 or data["bank"] < val: return await ctx.send("❌ لا تملك هذا الرصيد بالبنك!")
    data["bank"] -= val; data["wallet"] += val
    await ctx.send(f"💵 تم سحب **${val:,}** من البنك.")

@bot.command(name="انشاء_عصابة")
async def cmd_create_gang(ctx, *, name: str = None):
    if not name: return await ctx.send("❌ اكتب اسم العصابة!")
    data = get_user_data(ctx.author.id)
    if data["wallet"] < 50000: return await ctx.send("❌ التأسيس يتطلب $50,000!")
    if name in gangs_data: return await ctx.send("❌ الاسم مستخدم!")
    data["wallet"] -= 50000
    data["gang"] = name
    gangs_data[name] = {"owner": ctx.author.id, "members": [ctx.author.id], "bank": 100000}
    await ctx.send(f"🏴‍☠️ تم إنشاء عصابة **{name}** بنجاح!")

@bot.command(name="شراء_سهم")
async def buy_stock(ctx, code: str = None, amount: int = None):
    if not code or not amount or amount <= 0: return await ctx.send("❌ الاستخدام: `!شراء_سهم [الرمز] [العدد]`")
    code = code.upper()
    if code not in STOCKS: return await ctx.send("❌ رمز السهم غير صحيح!")
    total_cost = STOCKS[code]["price"] * amount
    user_data = get_user_data(ctx.author.id)
    if user_data["wallet"] < total_cost: return await ctx.send(f"❌ لا تملك كاش كافي! المطلوب: **${total_cost:,}**.")
    user_data["wallet"] -= total_cost
    user_data.setdefault("stocks", {})[code] = user_data["stocks"].get(code, 0) + amount
    await ctx.send(f"✅ تم شراء **{amount}** سهم في **{STOCKS[code]['name']}**!")

@bot.command(name="بيع_سهم")
async def sell_stock(ctx, code: str = None, amount: int = None):
    if not code or not amount or amount <= 0: return await ctx.send("❌ الاستخدام: `!بيع_سهم [الرمز] [العدد]`")
    code = code.upper()
    user_data = get_user_data(ctx.author.id)
    if user_data.get("stocks", {}).get(code, 0) < amount: return await ctx.send("❌ لا تملك هذا العدد من الأسهم!")
    update_stocks_market()
    total_return = STOCKS[code]["price"] * amount
    user_data["stocks"][code] -= amount
    user_data["wallet"] += total_return
    await ctx.send(f"💰 تم بيع **{amount}** سهم واستلمت **${total_return:,}**!")

@bot.command(name="اسهمي")
async def my_stocks(ctx):
    user_data = get_user_data(ctx.author.id)
    active = {k: v for k, v in user_data.get("stocks", {}).items() if v > 0}
    if not active: return await ctx.send("📊 لا تملك أي أسهم حالياً.")
    update_stocks_market()
    msg = f"📊 **محفظة أسهم {ctx.author.display_name}:**\n\n"
    for code, count in active.items():
        val = STOCKS[code]["price"] * count
        msg += f"• **{STOCKS[code]['name']} ({code})**: {count} سهم | القيمة: **${val:,}**\n"
    await ctx.send(msg)

# ==========================================
# 8. الأوامر الإدارية
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

# ==========================================
# 9. تشغيل البوت
# ==========================================
TOKEN = os.environ.get("DISCORD_TOKEN") or os.environ.get("BOT_TOKEN")
if TOKEN:
    bot.run(TOKEN)



# ==========================================
# 7. تشغيل البوت
# ==========================================
TOKEN = os.environ.get("DISCORD_TOKEN") or os.environ.get("BOT_TOKEN")

if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ لم يتم العثور على التوكين في متغيرات البيئة!") 
