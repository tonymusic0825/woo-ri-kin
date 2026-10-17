from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks

from services import worldstate_raw

WEEKLY_CHANNEL_ID = 1560292220261765210  # put your weekly reset channel ID here
EVERYONE = discord.AllowedMentions(everyone=True)
NO_PING = discord.AllowedMentions.none()

RESET_DELAY = timedelta(seconds=30)   # wait a little after reset so DE's data has rolled over
STALE_GRACE = timedelta(minutes=15)   # if the API still shows last week, keep retrying this long
MESSAGE_LIMIT = 6000                  # all embeds in one message together can hold 6000 chars

HEADER_COLOR = discord.Color.gold()
TESHIN_COLOR = discord.Color.orange()
CHECKLIST_COLOR = discord.Color.green()

# Teshin's ROTATING weekly item, in order. (name, Steel Essence cost)
TESHIN_ROTATION = [
    ("움브라 포르마 설계도 (Umbra Forma Blueprint)", 150),
    ("쿠바 50,000 (50,000 Kuva)", 55),
    ("킷건 리븐 모드 (Kitgun Riven Mod)", 75),
    ("포르마 3개 (3x Forma)", 75),
    ("자우 리븐 모드 (Zaw Riven Mod)", 75),
    ("엔도 30,000 (30,000 Endo)", 150),
    ("라이플 리븐 모드 (Rifle Riven Mod)", 75),
    ("샷건 리븐 모드 (Shotgun Riven Mod)", 75),
]
TESHIN_START = datetime(2020, 11, 16, tzinfo=timezone.utc)  # a week when Umbra Forma was the offer

ARCHIMEDEA_TYPES = {
    "CT_LAB": ("🧪 딥 아르키메디아 (Deep Archimedea)", discord.Color.purple()),
    "CT_HEX": ("⏳ 템포럴 아르키메디아 (Temporal Archimedea)", discord.Color.teal()),
}

# Manual reminders. Edit freely.
WEEKLY_CHECKLIST = [
    "아이언 웨이크 (Iron Wake) — 팔라디노에게 리븐 슬리버 교환",
    "테신 — 쿠바 10,000 (주 25회), 렐릭 팩 (주 25회), 베일드 리븐 사이퍼 (주 1회)",
    "테신 — 이번 주 로테이션 상품 구매",
    "넷라셀 / 아르키메디아 — 탐색 펄스 5개",
    "서킷 (The Circuit) — 일반 1회, 강철의 길 2회",
    "아콘 헌트 (Archon Hunt)",
    "나이트웨이브 (Nightwave) 주간 미션",
]


def parse_time(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def current_reset(now):
    """Most recent Monday 00:00 UTC."""
    monday = now - timedelta(days=now.weekday())  # weekday(): Monday = 0
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


def teshin_offer(week_start):
    """This week's and next week's rotating Teshin item."""
    weeks = (week_start - TESHIN_START).days // 7
    return TESHIN_ROTATION[weeks % 8], TESHIN_ROTATION[(weeks + 1) % 8]


# -------------------------- EMBEDS --------------------------
def build_header_embed(reset):
    next_reset = reset + timedelta(days=7)
    return discord.Embed(
        title="🗓️ 주간 리셋!",
        description=(
            f"새로운 한 주가 시작되었습니다.\n"
            f"⏳ **다음 리셋:** {discord.utils.format_dt(next_reset, 'F')} ({discord.utils.format_dt(next_reset, 'R')})"
        ),
        color=HEADER_COLOR,
    )


def build_teshin_embed(reset):
    (name, cost), (next_name, _) = teshin_offer(reset)
    return discord.Embed(
        title="🗡️ 테신 강철의 길 주간 상품",
        description=(
            f"**이번 주:** {name} — {cost} 강철 정수\n"
            f"**다음 주:** {next_name}"
        ),
        color=TESHIN_COLOR,
    )


def build_archimedea_embed(kind, conquest):
    title, color = ARCHIMEDEA_TYPES[kind]
    if conquest is None:
        return discord.Embed(title=title, description="정보를 불러오지 못했습니다.", color=color)

    lines = []
    for i, m in enumerate(conquest["missions"], 1):
        lines.append(f"**{i}. {m['missionType']}** · {m['faction']}")
        lines.append(f"└ 편차: {m['deviation']}")
        if m["risks"]:
            lines.append(f"└ 위험: {', '.join(m['risks'])}")
        if m["eliteRisks"]:
            lines.append(f"└ 엘리트 추가 위험: {', '.join(m['eliteRisks'])}")
        lines.append("")

    return discord.Embed(title=title, description="\n".join(lines) or "미션 정보 없음", color=color)


def build_checklist_embed():
    return discord.Embed(
        title="✅ 주간 체크리스트",
        description="\n".join(f"⬜ {item}" for item in WEEKLY_CHECKLIST),
        color=CHECKLIST_COLOR,
    )


def build_weekly_embeds(reset, conquests):
    by_type = {c["type"]: c for c in conquests}
    return [
        build_header_embed(reset),
        build_teshin_embed(reset),
        build_archimedea_embed("CT_LAB", by_type.get("CT_LAB")),
        build_archimedea_embed("CT_HEX", by_type.get("CT_HEX")),
        build_checklist_embed(),
    ]


def group_for_messages(embeds):
    """Pack embeds into as few messages as possible (max 10 embeds / 6000 chars each)."""
    groups, current, size = [], [], 0
    for e in embeds:
        if current and (len(current) == 10 or size + len(e) > MESSAGE_LIMIT):
            groups.append(current)
            current, size = [], 0
        current.append(e)
        size += len(e)
    if current:
        groups.append(current)
    return groups


class WeeklyResetPing(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.next_check = None
        self.posted_week = None  # reset time of the week the channel currently shows

    async def cog_load(self):
        self.check_weekly.start()

    async def cog_unload(self):
        self.check_weekly.cancel()

    # -------------------------- WEEKLY LOOP --------------------------
    @tasks.loop(minutes=1)
    async def check_weekly(self):
        now = datetime.now(timezone.utc)

        if self.next_check and now < self.next_check:
            return

        reset = current_reset(now)

        try:
            conquests = await worldstate_raw.get_conquests()
        except Exception as e:
            print(f"Weekly check failed: {e}")
            return

        # Last week's Archimedeas expire exactly at reset, so "expires in the future" = this week's data
        fresh = bool(conquests) and all(parse_time(c["expiry"]) > now for c in conquests)
        if not fresh:
            if now - reset < STALE_GRACE:
                print("Weekly: API still shows last week's data, retrying next minute")
                return
            conquests = []  # give up waiting; post the rest and show "no info" for Archimedea

        week_key = reset.isoformat()
        if week_key != self.posted_week:
            channel = self.bot.get_channel(WEEKLY_CHANNEL_ID)
            if channel is None:
                print("Weekly channel not found. Check WEEKLY_CHANNEL_ID.")
                return

            # Ping only when we SEE the reset happen (not when the bot just started up)
            ping = self.posted_week is not None

            embeds = build_weekly_embeds(reset, conquests)
            if not await self.replace_channel_post(channel, embeds, ping):
                return  # posting failed, retry next minute
            self.posted_week = week_key

        self.next_check = reset + timedelta(days=7) + RESET_DELAY  # sleep until next Monday

    @check_weekly.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    # -------------------------- POSTING --------------------------
    async def post_embeds(self, channel, embeds, ping):
        """Post embeds in as few messages as possible. Returns the first message, or None if it failed."""
        groups = group_for_messages(embeds)

        try:
            if ping:
                first = await channel.send(content="@everyone", embeds=groups[0], allowed_mentions=EVERYONE)
            else:
                first = await channel.send(embeds=groups[0], allowed_mentions=NO_PING)
        except Exception as e:
            print(f"Failed to post weekly reset: {e}")
            return None

        # Any extra messages: no ping
        for group in groups[1:]:
            try:
                await channel.send(embeds=group, allowed_mentions=NO_PING)
            except Exception as e:
                print(f"Failed to post a weekly follow-up message: {e}")

        return first

    async def replace_channel_post(self, channel, embeds, ping):
        """Post the new message(s) FIRST, then delete everything older."""
        first = await self.post_embeds(channel, embeds, ping)
        if first is None:
            return False

        try:
            await channel.purge(limit=100, before=first)  # delete last week's post
        except Exception as e:
            print(f"Couldn't clean up old weekly messages: {e}")
        return True

    # -------------------------- TESTING --------------------------
    @app_commands.command(name="testweekly", description="주간 리셋 알림 테스트 (이 채널에 핑 없이 게시)")
    @app_commands.default_permissions(administrator=True)
    async def test_weekly(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            conquests = await worldstate_raw.get_conquests()
        except Exception as e:
            await interaction.followup.send(f"API 호출 실패: {e}", ephemeral=True)
            return

        reset = current_reset(datetime.now(timezone.utc))
        # Posts in THIS channel without deleting anything
        first = await self.post_embeds(interaction.channel, build_weekly_embeds(reset, conquests), ping=False)
        result = "게시 완료" if first else "게시 실패 (콘솔 확인)"
        await interaction.followup.send(result, ephemeral=True)


async def setup(bot):
    await bot.add_cog(WeeklyResetPing(bot))