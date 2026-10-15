import asyncio

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from services.warframe_market import find_attributes, find_weapons, get_attribute, search_rivens

CATEGORY_NAME = "리벤 추적"
RESULT_COUNT = 5
SELLER_STATUS = {"ingame": "🟢 게임 중", "online": "🟡 온라인", "offline": "⚫ 오프라인"}

# (key, label, placeholder, required) — a modal can hold at most 5 fields
FIELDS = [
    ("weapon", "무기", "예: 브래톤, braton", True),
    ("pos1", "긍정 속성 1", "예: 치명타 확률, multishot", False),
    ("pos2", "긍정 속성 2", "없으면 비워 두세요", False),
    ("pos3", "긍정 속성 3", "없으면 비워 두세요", False),
    ("neg", "부정 속성", "예: 줌, zoom (없으면 비워 두세요)", False),
]


def _label(item):
    """Korean name if we have one, otherwise English."""
    return item["name_ko"] or item["name_en"]


def _full_label(item):
    """Korean and English together, so the user can double-check the match."""
    if item["name_ko"] and item["name_ko"] != item["name_en"]:
        return f"**{item['name_ko']}** ({item['name_en']})"
    return f"**{item['name_en']}**"


def _best(finder, text):
    matches = finder(text, limit=1)
    return matches[0] if matches else None


def _topic(member):
    """Marker stored in the channel topic so we can find a member's channel again."""
    return f"riven-track:{member.id}"


# ---------- Turning form text into a riven ----------

def resolve(raw):
    """Match the typed text against the JSON lists. Returns (riven, errors)."""
    errors = []

    weapon = _best(find_weapons, raw["weapon"])
    if weapon is None:
        errors.append(f"❌ 무기: '{raw['weapon']}' 검색 결과가 없어요.")

    positives = []
    for key in ("pos1", "pos2", "pos3"):
        text = raw[key]
        if not text:
            continue
        attr = _best(find_attributes, text)
        if attr is None:
            errors.append(f"❌ 긍정 속성: '{text}' 검색 결과가 없어요.")
        elif attr in positives:
            errors.append(f"❌ 긍정 속성: {_label(attr)}이(가) 중복되었어요.")
        else:
            positives.append(attr)

    negative = None
    if raw["neg"]:
        negative = _best(find_attributes, raw["neg"])
        if negative is None:
            errors.append(f"❌ 부정 속성: '{raw['neg']}' 검색 결과가 없어요.")
        elif negative in positives:
            errors.append(f"❌ {_label(negative)}은(는) 긍정과 부정에 동시에 넣을 수 없어요.")

    riven = {"weapon": weapon, "positives": positives, "negative": negative}
    return riven, errors


def riven_embed(riven, title):
    e = discord.Embed(title=title, color=discord.Color.purple())
    e.add_field(name="무기", value=_full_label(riven["weapon"]), inline=False)

    positives = "\n".join(f"➕ {_full_label(a)}" for a in riven["positives"]) or "없음"
    e.add_field(name="긍정 속성", value=positives, inline=False)

    negative = f"➖ {_full_label(riven['negative'])}" if riven["negative"] else "없음"
    e.add_field(name="부정 속성", value=negative, inline=False)
    return e


# ---------- Cheapest listings ----------

async def find_cheapest(riven):
    """Search warframe.market using the riven's slugs."""
    return await search_rivens(
        riven["weapon"]["slug"],
        [a["slug"] for a in riven["positives"]],
        riven["negative"]["slug"] if riven["negative"] else None,
        limit=RESULT_COUNT,
    )


def _stat_line(stat):
    attr = get_attribute(stat["slug"])
    name = _label(attr) if attr else stat["slug"]
    sign = "➕" if stat["positive"] else "➖"
    return f"{sign} {name} {stat['value']:+g}"


def results_embed(riven, auctions):
    weapon = _label(riven["weapon"])
    e = discord.Embed(color=discord.Color.gold())

    if not auctions:
        e.title = f"{weapon} 리벤"
        e.description = "지금은 조건에 맞는 판매 중인 리벤이 없어요."
        return e

    e.title = f"{weapon} 최저가 리벤 TOP {len(auctions)}"
    for i, a in enumerate(auctions, 1):
        name = f"{riven['weapon']['name_en']} {(a['name'] or '').title()}"
        stats = "\n".join(_stat_line(s) for s in a["attributes"])
        status = SELLER_STATUS.get(a["status"], a["status"])
        details = (
            f"{status} · `{a['seller']}`\n"
            f"재굴림 {a['rerolls']}회 · MR {a['mastery']} · [판매글 보기]({a['url']})"
        )
        e.add_field(
            name=f"{i}. {name} — {a['price']} 플래티넘",
            value=f"{stats}\n{details}",
            inline=False,
        )
    return e


# ---------- The popup form ----------

class RivenForm(discord.ui.Modal):
    def __init__(self, values=None):
        super().__init__(title="리벤 추가")
        values = values or {}

        self.inputs = {}
        for key, label, placeholder, required in FIELDS:
            box = discord.ui.TextInput(
                label=label,
                placeholder=placeholder,
                required=required,
                default=values.get(key) or None,  # prefill when editing
                max_length=50,
            )
            self.inputs[key] = box
            self.add_item(box)

    async def on_submit(self, interaction):
        raw = {key: box.value.strip() for key, box in self.inputs.items()}
        riven, errors = resolve(raw)

        if errors:
            await interaction.response.send_message(
                "\n".join(errors), view=ReviewView(raw), ephemeral=True
            )
            return

        await interaction.response.send_message(
            embed=riven_embed(riven, "이 리벤을 추적할까요?"),
            view=ReviewView(raw, riven),
            ephemeral=True,
        )


class ReviewView(discord.ui.View):
    """Shown after the form. 확인 saves (only if valid); 수정 reopens the filled-in form."""

    def __init__(self, raw, riven=None):
        super().__init__(timeout=300)
        self.raw = raw
        self.riven = riven
        if riven is None:  # there were errors, so only allow editing
            self.remove_item(self.confirm_button)
            self.edit_button.label = "다시 입력"

    @discord.ui.button(label="확인", style=discord.ButtonStyle.success)
    async def confirm_button(self, interaction, button):
        # TODO: save the slugs in self.riven to the database
        await interaction.response.edit_message(
            embed=riven_embed(self.riven, "✅ 추적 목록에 추가했어요"), view=None
        )
        self.stop()

        try:
            auctions = await find_cheapest(self.riven)
        except (aiohttp.ClientError, asyncio.TimeoutError):
            await interaction.followup.send(
                "warframe.market 검색에 실패했어요. 잠시 후 다시 시도해 주세요.", ephemeral=True
            )
            return

        await interaction.followup.send(embed=results_embed(self.riven, auctions))

    @discord.ui.button(label="수정", style=discord.ButtonStyle.secondary)
    async def edit_button(self, interaction, button):
        await interaction.response.send_modal(RivenForm(self.raw))


# ---------- Panel in the private channel ----------

class TrackerView(discord.ui.View):
    def __init__(self, owner):
        super().__init__(timeout=None)
        self.owner = owner

    async def interaction_check(self, interaction):
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message("본인의 추적 설정만 수정할 수 있어요.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="➕ 리벤 추가", style=discord.ButtonStyle.primary)
    async def add_button(self, interaction, button):
        await interaction.response.send_modal(RivenForm())


# ---------- Cog ----------

class RivenTrack(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_or_create_channel(self, member):
        """Return (channel, created). Only creates a channel if the member has none."""
        guild = member.guild

        for channel in guild.text_channels:
            if channel.topic == _topic(member):
                return channel, False

        category = discord.utils.get(guild.categories, name=CATEGORY_NAME)
        if category is None:
            category = await guild.create_category(CATEGORY_NAME)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, embed_links=True, read_message_history=True
            ),
        }

        channel = await guild.create_text_channel(
            name=f"리벤-{member.display_name}",
            category=category,
            topic=_topic(member),
            overwrites=overwrites,
        )
        return channel, True

    @app_commands.command(name="리벤추적", description="리벤 추적 설정을 시작합니다")
    @app_commands.guild_only()
    async def riven_track(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)

        channel, created = await self.get_or_create_channel(interaction.user)

        embed = discord.Embed(
            title="리벤 추적",
            description="아래 버튼을 눌러 추적할 리벤을 추가하세요.",
            color=discord.Color.purple(),
        )
        await channel.send(
            content=interaction.user.mention, embed=embed, view=TrackerView(interaction.user)
        )

        status = "개인 채널을 만들었어요" if created else "기존 개인 채널에 설정 창을 올렸어요"
        await interaction.followup.send(f"{status}: {channel.mention}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(RivenTrack(bot))