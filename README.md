# Vault

Claimify is a Discord bot that simplifies reward distribution for server admins.
Users can claim rewards containing text, gift codes, or even accounts quickly and securely.
The bot can be configured to allow specific roles to claim rewards at specific times,
making it ideal for communities that frequently give away prizes.
If you're a server admin looking for a tool to streamline reward distribution,
Claimify is the bot for you!

[![Github](https://img.shields.io/badge/Github-MrSnifo-blue.svg)](https://github.com/MrSniFo)
[![Discord](https://img.shields.io/badge/Discord-Snifo-blue.svg)](https://discord.gg/hH4ZkNg6cA)
[![Shoppy](https://img.shields.io/badge/Shoppy-Snifo-blue.svg)](https://shoppy.gg/@snifo)

Note: Run the Bot using `launcher.py` and keep it running for an hour, so it syncs all the slash commands.

## Commands

`/vault *[open/create/remove] *[code]`

`/create *[code] *[role]`

## Installation
Python 3.11.3 (Recommended)

```shell
pip install -r requirements.txt
```

## Configuration
#### Token
- You need to [Create a Bot](https://discordpy.readthedocs.io/en/stable/discord.html) (Skip the Invitation part)
- Add your Bot Token to the .env file

The invitation link will be generated when launching the Bot.