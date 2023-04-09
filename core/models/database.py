"""
The MIT License (MIT)

Copyright (c) 2022-present MrSniFo

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without max_linesation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT max_linesED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NON-INFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""

# ------ Core ------
from .errors import Errors
from ..utils import encrypt, decrypt
# ------ sqlite ------
from aiosqlite import connect, Connection, Cursor
# ------ Datetime ------
from datetime import datetime
# ------ Typing ------
from typing import TypedDict, Optional, Iterable, List
# ------ Re ------
from re import sub


class Guild(TypedDict):
    id: int
    created_at: datetime


class Vault(TypedDict):
    id: int
    code: str
    guild_id: int
    storage: str
    length: int
    updated_at: datetime
    created_at: datetime


class Card(TypedDict):
    id: int
    vault_id: int
    guild_id: int
    channel_id: int
    message_id: int
    role_id: int
    max_lines: int
    timeout: int
    created_at: datetime


class Message(TypedDict):
    channel_id: int
    message_id: int


class Claim(TypedDict):
    card_id: int
    guild_id: int
    member_id: int
    claim_time: datetime


class Database(object):
    __slots__ = ("guild_id", "owner_id", "secret_key", "guild", "connection", "cursor")

    def __init__(self, guild_id: int, owner_id: int, secret_key: str):
        self.guild_id = guild_id
        self.owner_id = owner_id
        self.secret_key = secret_key
        self.guild: Guild = None  # type: ignore
        self.connection: Connection | None = None
        self.cursor: Cursor | None = None

    async def __aenter__(self):
        self.connection = await connect(database="guilds.db", detect_types=3)
        self.cursor = await self.connection.cursor()

        # Guilds(*id)
        await self.cursor.execute("""CREATE TABLE IF NOT EXISTS guilds(
                                                            id INTEGER PRIMARY KEY,
                                                            created_at TIMESTAMP NOT NULL);
                                                            """)

        # Vaults(*id, code, #guild_id, storage, length, updated_at, created_at)
        await self.cursor.execute("""CREATE TABLE IF NOT EXISTS vaults(
                                                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                            code TEXT NOT NULL,
                                                            guild_id INTEGER NOT NULL,
                                                            storage TEXT DEFAULT '' NOT NULL,
                                                            length INTEGER NOT NULL,
                                                            updated_at TIMESTAMP NOT NULL,
                                                            created_at TIMESTAMP NOT NULL,
                                                            FOREIGN KEY(guild_id) REFERENCES guilds(id));
                                                            """)

        # Cards(id, #vault_id, #guild_id, message_id, role_id, max_lines, timeout, created_at)
        await self.cursor.execute("""CREATE TABLE IF NOT EXISTS cards(
                                                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                            vault_id INTEGER NOT NULL,
                                                            guild_id INTEGER NOT NULL,
                                                            channel_id INTEGER NOT NULL,
                                                            message_id INTEGER NOT NULL,
                                                            role_id INTEGER NOT NULL,
                                                            max_lines INTEGER NOT NULL,
                                                            timeout INTEGER default 5 NOT NULL,
                                                            created_at TIMESTAMP NOT NULL,
                                                            FOREIGN KEY(vault_id) REFERENCES vaults(id),
                                                            FOREIGN KEY(guild_id) REFERENCES guilds(id));
                                                            """)

        # Claims(*#card_id, #guild_id, member_id, claim_time)
        await self.cursor.execute("""CREATE TABLE IF NOT EXISTS claims(
                                                            card_id INTEGER PRIMARY KEY REFERENCES Cards(id),
                                                            guild_id INTEGER NOT NULL,
                                                            member_id INTEGER NOT NULL,
                                                            claim_time TIMESTAMP NOT NULL,
                                                            FOREIGN KEY(guild_id) REFERENCES guilds(id),
                                                            FOREIGN KEY(card_id) REFERENCES cards(id));
                                                            """)

        # Get guild
        self.guild = await self.get_guild(guild_id=self.guild_id)

        return self

    def encrypt_storage(self, storage: str) -> str:
        """
        This function encrypt storage.

        :return:`str`
       """
        faze1 = encrypt(key=str(self.owner_id), source=storage)
        faze2 = encrypt(key=self.secret_key, source=faze1)
        return faze2

    def decrypt_storage(self, storage: str) -> str:
        """
        This function decrypt storage.

        :return:`str`
       """
        dec1 = decrypt(key=self.secret_key, source=storage)
        dec2 = decrypt(key=str(self.owner_id), source=dec1)
        return dec2

    async def get_guild(self, guild_id: int) -> Guild:
        # -------------------------
        # Checks if the guild exists.
        request = await self.cursor.execute("""SELECT * FROM guilds WHERE id = ?;""", (guild_id,))
        fetch = await request.fetchone()
        if fetch is None:
            created_at = datetime.utcnow().replace(microsecond=0)
            await self.cursor.execute("""INSERT INTO guilds(id, created_at) VALUES(?, ?);""", (guild_id, created_at))
            await self.connection.commit()
            return {"id": guild_id, "created_at": created_at}
        else:
            return {"id": int(fetch[0]), "created_at": fetch[1]}

    async def get_vault(self, code: str) -> Optional[Vault]:
        """
        This function retrieve a vault.

        :return:`dict`
       """
        sql: str = """SELECT * FROM vaults WHERE code = ? AND guild_id = ?;"""
        request = await self.cursor.execute(sql, (code, self.guild["id"]))
        fetch = await request.fetchone()
        # Checks if the vault exists.
        if fetch is not None:
            try:
                decrypt_storage = self.decrypt_storage(storage=fetch[3])
                return {"id": fetch[0],
                        "code": fetch[1],
                        "guild_id": fetch[2],
                        "storage": decrypt_storage,
                        "length": fetch[4],
                        "updated_at": fetch[5],
                        "created_at": fetch[6]}
            except ValueError:
                await self.remove_vault(vault_id=fetch[0])
                return None
        else:
            return None

    async def create_vault(self, code: str, storage: str) -> None:
        """
        This function creates a new vault.

        :return:`None`
        """
        storage = sub("\n+", "\n", storage.strip())
        utc = datetime.utcnow().replace(microsecond=0)
        sql: str = """INSERT INTO vaults(code, guild_id, storage, length, updated_at, created_at) 
        VALUES(?, ?, ?, ?, ?, ?);"""
        await self.cursor.execute(sql, (code, self.guild["id"],
                                        self.encrypt_storage(storage=storage),
                                        0 if len(storage) == 0 else len(storage.split("\n")), utc, utc))
        await self.connection.commit()

    async def update_vault(self, vault_id: int, storage: str) -> None:
        """
        This function updates a vault.

        :return:`None`
        """
        storage = sub("\n+", "\n", storage.strip())
        utc = datetime.utcnow().replace(microsecond=0)
        sql = """UPDATE vaults SET storage = ?, length = ?,
         updated_at = ? WHERE id = ?;"""
        await self.cursor.execute(sql, (self.encrypt_storage(storage=storage),
                                        0 if len(storage) == 0 else len(storage.split("\n")), utc, vault_id))
        await self.connection.commit()

    async def remove_vault(self, vault_id: int) -> List[Message]:
        """
        This function delete a vault and its related cards.

        :return:`List[int]` messages
        """

        messages: List[Message] = []

        # Deleting the vault.
        sql = """DELETE FROM vaults WHERE id = ?;"""
        await self.cursor.execute(sql, (vault_id,))

        sql: str = """SELECT * FROM cards WHERE vault_id = ?;"""
        request = await self.cursor.execute(sql, (vault_id,))
        fetch = await request.fetchall()
        for card in fetch:
            # Deleting from the 'Claims' table where we keep track of members' claims.
            sql = """DELETE FROM claims WHERE card_id = ?;"""
            await self.cursor.execute(sql, (card[0],))
            messages.append({"channel_id": card[3], "message_id": card[4]})
        # Deleting the related cards.
        sql = """DELETE FROM cards WHERE vault_id = ?;"""
        await self.cursor.execute(sql, (vault_id,))
        await self.connection.commit()
        return messages

    async def get_card(self, message_id: int) -> Optional[Card]:
        """
        This function retrieve a card.

        :return:`dict`
       """
        sql: str = """SELECT * FROM cards WHERE message_id = ?;"""
        request = await self.cursor.execute(sql, (message_id,))
        fetch = await request.fetchone()
        # Checks if the card exists.
        if fetch is not None:
            return {"id": fetch[0],
                    "vault_id": fetch[1],
                    "guild_id": fetch[2],
                    "channel_id": fetch[3],
                    "message_id": fetch[4],
                    "role_id": fetch[5],
                    "max_lines": fetch[6],
                    "timeout": fetch[7],
                    "created_at": fetch[8]}
        else:
            return None

    async def create_card(self, vault: Vault, channel_id: int,
                          message_id: int, role_id: int, max_lines: int, timeout: int) -> None:
        """
        This function creates a new card.

        :return:`None`
        """
        utc = datetime.utcnow().replace(microsecond=0)
        sql: str = """INSERT INTO cards(vault_id, guild_id, channel_id, message_id, role_id, max_lines, timeout, 
        created_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?);"""
        await self.cursor.execute(sql, (vault["id"], self.guild["id"], channel_id,
                                        message_id, role_id, max_lines, timeout, utc))
        await self.connection.commit()

    async def remove_card(self, card: Card) -> None:
        """
        This function delete a card and its related claims.

        :return:`None`
        """
        # Deleting the card.
        sql = """DELETE FROM cards WHERE id = ?;"""
        await self.cursor.execute(sql, (card["id"],))

        # Deleting from the 'Claims' table where we keep track of members' claims.
        sql = """DELETE FROM claims WHERE card_id = ?;"""
        await self.cursor.execute(sql, (card["id"],))
        await self.connection.commit()

    async def get_cards(self, guild_id: int) -> Iterable[Card]:
        """
        This function retrieves all cards.

        :return:`iter[Card]`
       """
        sql: str = """SELECT * FROM cards WHERE guild_id = ?;"""
        request = await self.cursor.execute(sql, (guild_id,))
        fetch = await request.fetchall()
        # Checks if the card exists.
        for card in fetch:
            yield {"id": card[0],
                   "vault_id": card[1],
                   "guild_id": card[2],
                   "channel_id": card[3],
                   "message_id": card[4],
                   "role_id": card[5],
                   "max_lines": card[6],
                   "timeout": card[7],
                   "created_at": card[8]}

    async def get_claimer(self, member_id: int, card: Card) -> Optional[Claim]:
        """
        This function retrieve a card claimer.

        :return:`int` (seconds)
       """
        sql: str = """SELECT * FROM claims WHERE member_id = ? AND card_id = ?;"""
        request = await self.cursor.execute(sql, (member_id, card["id"]))
        fetch = await request.fetchone()
        if fetch is not None:
            return {"card_id": fetch[0],
                    "guild_id": fetch[1],
                    "member_id": fetch[2],
                    "claim_time": fetch[3]}
        else:
            return None

    async def claim(self, member_id: int, card: Card) -> List[str] | int:
        """
        This function claim length.

        :return:`List[str] | int (timeout)`
       """

        # Retrieving a vault by its ID.
        sql: str = """SELECT * FROM vaults WHERE id = ? AND guild_id = ?;"""
        request = await self.cursor.execute(sql, (card["vault_id"], self.guild["id"]))
        fetch = await request.fetchone()
        if fetch is not None:
            try:
                decrypt_storage = self.decrypt_storage(storage=fetch[3])
                # Checks if there is length available.
                if fetch[4] >= card["max_lines"]:
                    # Checks for timeout.
                    get_claimer = await self.get_claimer(member_id=member_id, card=card)
                    utc = datetime.utcnow().replace(microsecond=0)
                    if get_claimer is not None:
                        tm = max(card["timeout"] - (datetime.utcnow() - get_claimer["claim_time"]).seconds, 0)
                        if tm != 0:
                            return tm
                        else:
                            sql = """UPDATE claims SET claim_time = ? WHERE member_id = ? AND card_id = ? 
                            AND guild_id = ?;"""
                    else:
                        sql = """INSERT INTO claims(claim_time, member_id, card_id, guild_id) VALUES(?, ?, ?, ?);"""

                    storage = sub("\n+", "\n", str(decrypt_storage).strip()).split("\n")
                    claim = storage[:card["max_lines"]]
                    # Updating vault
                    await self.update_vault(vault_id=fetch[0], storage="\n".join(storage[card["max_lines"]:]))
                    # Updating timeout.
                    await self.cursor.execute(sql, (utc, member_id, card["id"], self.guild["id"]))
                    await self.connection.commit()
                    return claim
                else:
                    raise Errors.VaultOverLimit(code=fetch[1])
            except ValueError:
                raise Errors.VaultNotFound()
        else:
            raise Errors.VaultNotFound()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.connection.close()
