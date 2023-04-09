"""
The MIT License (MIT)

Copyright (c) 2023-present MrSniFo

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NON-INFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""

# ------ Core ------
from ..bot import Bot
from ..models import Database, VaultType, Errors
from ..utils import embed_wrong, text_to_seconds, period
# ------ Discord ------
from discord import Interaction, app_commands, ui, Embed, TextStyle, ButtonStyle, Role, DiscordException
from discord.ext.commands import Cog
from discord.ui import button, Button
# ------ Typing ------
from typing import Optional
# ------ Datetime ------
from datetime import datetime, timedelta


class Create(Cog, name="Create"):
    __slots__ = "bot"

    def __init__(self, bot: Bot) -> None:
        """
        Create slash command
        """
        self.bot = bot

    @Cog.listener()
    async def on_guild_available(self, guild):
        async with Database(guild_id=guild.id, owner_id=guild.owner_id, secret_key=self.bot.secret_key) as db:
            async for card in db.get_cards(guild_id=guild.id):
                try:
                    self.bot.add_view(MyView(secret_key=self.bot.secret_key), message_id=card["message_id"])
                except Exception as error:
                    self.bot.logger.error(f"[Create] [on_guild_available] {error}")

    @app_commands.default_permissions(administrator=True)
    @app_commands.command(name="create", description="Create a reward card.")
    @app_commands.describe(code="Vault unique identifier.")
    async def slash(self, interaction: Interaction, code: str, role: Role) -> None:
        code = code.lower()
        async with Database(guild_id=interaction.guild_id, owner_id=interaction.guild.owner_id,
                            secret_key=self.bot.secret_key) as db:
            vault: Optional[VaultType] = await db.get_vault(code=code)
            if vault is not None:
                modal = MyModal(vault=vault, secret_key=self.bot.secret_key, role=role)
                await interaction.response.send_modal(modal)  # type: ignore
            else:
                embed = embed_wrong(msg=f"The code you entered does not match any existing vault.")
                await interaction.response.send_message(embed=embed, ephemeral=True)  # type: ignore


class MyView(ui.View):
    __slots__ = "secret_key"

    def __init__(self, secret_key: str):
        super().__init__(timeout=None)
        self.secret_key = secret_key

    @button(label='Claim', style=ButtonStyle.green, custom_id="Claim-KbPdSgVkYp3s6v9y$B&E")
    async def green(self, interaction: Interaction, _: Button):
        async with Database(guild_id=interaction.guild_id, owner_id=interaction.guild.owner_id,
                            secret_key=self.secret_key) as db:
            card = await db.get_card(message_id=interaction.message.id)
            if card is not None:
                if card["role_id"] in [role.id for role in interaction.user.roles]:
                    try:
                        claim = await db.claim(member_id=interaction.user.id, card=card)
                        if type(claim) is not int:
                            lines = "\n".join(claim)
                            embed = Embed(title="Claimed!", description=f"```{lines}```", colour=0x248046)
                        else:
                            time = f"<t:{int(datetime.timestamp(datetime.now() + timedelta(seconds=claim)))}:R>"
                            embed = embed_wrong(msg=f"You have reached the maximum limit.\n"
                                                    f"Please try again {time}.")

                    except Errors.VaultNotFound:
                        embed = embed_wrong(msg=f"The vault is currently unreachable. Please try again later.")
                    except Errors.VaultOverLimit as error:
                        embed = embed_wrong(msg=str(error))
                else:
                    embed = embed_wrong(msg=f"You do not have the required role.")
            else:
                await interaction.message.delete()
                embed = embed_wrong(msg=f"Card not found.")

        await interaction.response.send_message(embed=embed, ephemeral=True)  # type: ignore


class MyModal(ui.Modal):
    __slots__ = ("secret_key", "vault", "role", "title_ui", "description_ui", "thumbnail_ui", "max_lines_ui",
                 "timeout_ui")

    def __init__(self, vault: VaultType, role: Role, secret_key: str):
        super().__init__(title=f"Creating a Card")
        self.secret_key = secret_key
        self.vault = vault
        self.role = role

        self.title_ui = ui.TextInput(label="Title", placeholder="Card title", required=True)
        self.description_ui = ui.TextInput(label="Description", placeholder="Card description",
                                           style=TextStyle.long, required=False)
        self.thumbnail_ui = ui.TextInput(label="Thumbnai", placeholder="url", required=False)
        self.max_lines_ui = ui.TextInput(label="Lines", default="1",
                                         placeholder="Amount of lines to claim", required=True)
        self.timeout_ui = ui.TextInput(label="Timeout", placeholder="Example: 1d 5h 10m 30s", required=True)

        for item in [self.title_ui, self.description_ui, self.thumbnail_ui, self.max_lines_ui, self.timeout_ui]:
            self.add_item(item)

    async def on_submit(self, interaction: Interaction) -> None:
        try:
            max_lines = int(self.max_lines_ui.value)
            timeout = int(text_to_seconds(text=self.timeout_ui.value))
            # Card message.
            view = MyView(secret_key=self.secret_key)
            embed = Embed(title=str(self.title_ui.value), colour=0x248046)
            # Card description is not required.
            if self.description_ui.value is not None and str(self.description_ui.value) != "":
                embed.description = str(self.description_ui.value)
            # Card thumbnail  is not required.
            if self.thumbnail_ui.value is not None and str(self.thumbnail_ui.value) != "":
                embed.set_thumbnail(url=str(self.thumbnail_ui.value))
            embed.add_field(name="Requirement", value=self.role.mention, inline=True)
            embed.add_field(name="Total", value=str(max_lines), inline=True)
            try:
                message = await interaction.channel.send(embed=embed, view=view)
                async with Database(guild_id=interaction.guild_id, owner_id=interaction.guild.owner_id,
                                    secret_key=self.secret_key) as db:
                    await db.create_card(vault=self.vault,
                                         channel_id=message.channel.id,
                                         message_id=message.id,
                                         role_id=self.role.id,
                                         max_lines=max_lines,
                                         timeout=timeout)
                    # Response message.
                    url = f"https://discord.com/channels/{interaction.guild_id}/{message.channel.id}/{message.id} "
                    response_embed = Embed(title=str(self.title_ui.value),
                                           url=url,
                                           description=f"\nVault: `#{self.vault['code']}`"
                                                       f"\nTimeout: `{period(delta=timedelta(seconds=timeout))}`"
                                                       f"\n\n`Card Created Successfully!` :white_check_mark:",
                                           colour=0x2ecc71)

                    await interaction.response.send_message(embed=response_embed, ephemeral=True)  # type: ignore
            except DiscordException:
                """
                there is a chance that when opening modal and the channel has been removed at the same time
                it may lead to an error.
                """
                pass

        except ValueError:
            embed = embed_wrong(msg=f"Format not recognized. Please enter a valid format.")
            await interaction.response.send_message(embed=embed, ephemeral=True)  # type: ignore


async def setup(bot) -> None: await bot.add_cog(Create(bot))
