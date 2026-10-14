import discord
from discord import app_commands
from discord.ext import commands

from services.warframe_market import find_attributes, find_weapons

CATEGORY_NAME = "리벤 추적"
MAX_POSITIVES = 3

def _label(item):
    """Korean name if we have one, otherwise English."""
    return item["name_ko"] or item["name_en"]


def _topic(member):
    """Marker stored in the channel topic so we can find a member's channel again."""
    return f"riven-track:{member.id}"


# ---------- Search popup -> dropdown of matches ----------

class PickView(discord.ui.View):
    """Private dropdown of search matches. Calls on_pick(item) with the chosen one."""

    def __init__(self, matches, on_pick):
        super().__init__(timeout=180)
        self.by_slug = {m["slug"]: m for m in matches}
        self.on_pick = on_pick

        self.select = discord.ui.Select(
            placeholder="목록에서 선택하세요",
            options=[
                discord.SelectOption(
                    label=_label(m),
                    value=m["slug"],
                    description=m["name_en"] if m["name_ko"] else None,
                )
                for m in matches
            ],
        )
        self.select.callback = self.picked
        self.add_item(self.select)

    async def picked(self, interaction):
        item = self.by_slug[self.select.values[0]]
        await interaction.response.edit_message(content=f"✅ {_label(item)} 선택됨", view=None)
        await self.on_pick(item)


class SearchModal(discord.ui.Modal):
    """Popup with one text box. Shows matching results as a dropdown."""

    def __init__(self, title, label, placeholder, finder, exclude, on_pick):
        super().__init__(title=title)
        self.finder = finder
        self.exclude = exclude  # slugs already chosen, hidden from results
        self.on_pick = on_pick

        self.query = discord.ui.TextInput(label=label, placeholder=placeholder, max_length=50)
        self.add_item(self.query)

    async def on_submit(self, interaction):
        query = self.query.value
        matches = [m for m in self.finder(query) if m["slug"] not in self.exclude]

        if not matches:
            await interaction.response.send_message(f"'{query}'에 해당하는 결과가 없어요.", ephemeral=True)
            return

        await interaction.response.send_message(
            f"'{query}' 검색 결과:", view=PickView(matches, self.on_pick), ephemeral=True
        )


# ---------- Main setup panel ----------

class TrackerView(discord.ui.View):
    def __init__(self, owner):
        super().__init__(timeout=None)
        self.owner = owner
        self.message = None  # set after the panel is sent

        self.weapon = None
        self.positives = []
        self.negative = None
        self.refresh_buttons()

    # --- state ---

    def chosen_slugs(self):
        slugs = {a["slug"] for a in self.positives}
        if self.negative:
            slugs.add(self.negative["slug"])
        return slugs

    def embed(self):
        e = discord.Embed(title="리벤 추적 설정", color=discord.Color.purple())
        e.add_field(name="무기", value=_label(self.weapon) if self.weapon else "선택 안 됨", inline=False)

        positives = "\n".join(f"➕ {_label(a)}" for a in self.positives) or "없음"
        e.add_field(name=f"긍정 속성 ({len(self.positives)}/{MAX_POSITIVES})", value=positives, inline=False)

        negative = f"➖ {_label(self.negative)}" if self.negative else "없음"
        e.add_field(name="부정 속성", value=negative, inline=False)
        return e

    def refresh_buttons(self):
        self.positive_button.disabled = len(self.positives) >= MAX_POSITIVES
        self.done_button.disabled = self.weapon is None

    async def update(self):
        self.refresh_buttons()
        await self.message.edit(embed=self.embed(), view=self)

    # --- called by PickView when something is chosen ---

    async def set_weapon(self, item):
        self.weapon = item
        await self.update()

    async def add_positive(self, item):
        if len(self.positives) < MAX_POSITIVES:
            self.positives.append(item)
        await self.update()

    async def set_negative(self, item):
        self.negative = item
        await self.update()

    # --- only the owner can use the panel ---

    async def interaction_check(self, interaction):
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message("본인의 추적 설정만 수정할 수 있어요.", ephemeral=True)
            return False
        return True

    # --- buttons ---

    @discord.ui.button(label="무기 선택", style=discord.ButtonStyle.primary, row=0)
    async def weapon_button(self, interaction, button):
        await interaction.response.send_modal(SearchModal(
            title="무기 선택",
            label="무기 이름",
            placeholder="예: 브래톤, braton",
            finder=find_weapons,
            exclude=set(),
            on_pick=self.set_weapon,
        ))

    @discord.ui.button(label="긍정 속성 추가", style=discord.ButtonStyle.success, row=0)
    async def positive_button(self, interaction, button):
        await interaction.response.send_modal(SearchModal(
            title="긍정 속성 추가",
            label="속성 이름",
            placeholder="예: 치명타 확률, multishot",
            finder=find_attributes,
            exclude=self.chosen_slugs(),
            on_pick=self.add_positive,
        ))

    @discord.ui.button(label="부정 속성 선택", style=discord.ButtonStyle.danger, row=0)
    async def negative_button(self, interaction, button):
        await interaction.response.send_modal(SearchModal(
            title="부정 속성 선택",
            label="속성 이름",
            placeholder="예: 줌, zoom",
            finder=find_attributes,
            exclude=self.chosen_slugs(),
            on_pick=self.set_negative,
        ))

    @discord.ui.button(label="초기화", style=discord.ButtonStyle.secondary, row=1)
    async def reset_button(self, interaction, button):
        self.weapon = None
        self.positives = []
        self.negative = None
        self.refresh_buttons()
        await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(label="완료", style=discord.ButtonStyle.success, row=1)
    async def done_button(self, interaction, button):
        # TODO: save self.weapon / self.positives / self.negative to the database
        for item in self.children:
            item.disabled = True

        embed = self.embed()
        embed.set_footer(text="추적 설정이 완료되었어요.")
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()


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

        view = TrackerView(interaction.user)
        view.message = await channel.send(
            content=interaction.user.mention, embed=view.embed(), view=view
        )

        status = "개인 채널을 만들었어요" if created else "기존 개인 채널에 설정 창을 올렸어요"
        await interaction.followup.send(f"{status}: {channel.mention}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(RivenTrack(bot))