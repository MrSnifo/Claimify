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
from ..models import Database, VaultType
from ..utils import embed_wrong
# ------ Discord ------
from discord import Interaction, app_commands, ui, Embed, TextStyle
from discord.ext.commands import Cog
# ------ Typing ------
from typing import Literal, Optional


class Vault(Cog, name="Vault"):
    __slots__ = "bot"

    def __init__(self, bot: Bot) -> None:
        """
        Vault slash command
        """
        self.bot = bot

    @app_commands.default_permissions(administrator=True)
    @app_commands.command(name="vault", description="Securely store and manage data.")
    @app_commands.describe(code="Vault unique identifier.")
    async def slash(self, interaction: Interaction, option: Literal["open", "create", "remove"], code: str) -> None:
        code = code.lower()
        async with Database(guild_id=interaction.guild_id, owner_id=interaction.guild.owner_id,
                            secret_key=self.bot.secret_key) as db:
            vault: Optional[VaultType] = await db.get_vault(code=code)
            if option in ["open", "remove"] and (vault is None):
                embed = embed_wrong(msg=f"The code you entered does not match any existing vault.")
                await interaction.response.send_message(embed=embed, ephemeral=True)  # type: ignore
            else:
                # Open the vault
                if option == "open":
                    modal = MyModal(vault=vault, code=code, secret_key=self.bot.secret_key)
                    await interaction.response.send_modal(modal)  # type: ignore
                # Remove the vault.
                elif option == "remove":
                    messages = await db.remove_vault(vault_id=vault["id"])
                    embed = Embed(title=f":card_box: Vault #{code}",
                                  description="`Vault Successfully Removed` :x:", colour=0xe74c3c)
                    await interaction.response.send_message(embed=embed, ephemeral=True)  # type: ignore
                    # Deleting cards.
                    for message in messages:
                        channel = interaction.guild.get_channel(message["channel_id"])
                        if channel is not None:
                            card = channel.get_partial_message(message["message_id"])
                            if card is not None:
                                try:
                                    await card.delete()
                                except Exception as error:
                                    self.bot.logger.error(f"[Vault] {error}")

                # Create a new Vault.
                elif option == "create":
                    if vault is None:
                        modal = MyModal(vault=vault, code=code, secret_key=self.bot.secret_key)
                        await interaction.response.send_modal(modal)  # type: ignore
                    else:
                        embed = embed_wrong(msg=f"There is already a vault with that code.")
                        await interaction.response.send_message(embed=embed, ephemeral=True)  # type: ignore


class MyModal(ui.Modal):
    __slots__ = ("code", "secret_key", "vault", "storage_ui")

    def __init__(self, vault: Optional[VaultType], code: str, secret_key: str):
        super().__init__(title=f"Vault #{code}")
        self.code = code
        self.secret_key = secret_key
        self.vault = vault

        if self.vault is None:
            storage = None
        else:
            storage = vault["storage"]

        self.storage_ui = ui.TextInput(label="Storage",
                                       style=TextStyle.long,
                                       default=storage,
                                       required=False)
        self.add_item(self.storage_ui)

    async def on_submit(self, interaction: Interaction) -> None:
        if (self.vault is None) or (str(self.storage_ui.value) != self.vault["storage"]):
            async with Database(guild_id=interaction.guild_id, owner_id=interaction.guild.owner_id,
                                secret_key=self.secret_key) as db:
                if self.vault is None:
                    await db.create_vault(code=self.code, storage=str(self.storage_ui.value))
                    embed = Embed(title=f":card_box: Vault #{self.code}",
                                  description="`Vault Created Successfully!`", colour=0x2ecc71)
                else:
                    await db.update_vault(vault_id=self.vault["id"], storage=str(self.storage_ui.value))
                    embed = Embed(title=f":card_box: Vault #{self.code}",
                                  description="`Vault Updated Successfully!`", colour=0x2ecc71)
                await interaction.response.send_message(embed=embed, ephemeral=True)  # type: ignore
        else:
            embed = Embed(title=f":card_box: Vault #{self.code}",
                          description="`No Changes Made`")
            await interaction.response.send_message(embed=embed, ephemeral=True)  # type: ignore


async def setup(bot) -> None: await bot.add_cog(Vault(bot))
