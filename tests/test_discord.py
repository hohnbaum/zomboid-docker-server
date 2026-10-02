import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

try:
    import discord
    AVAILABLE = hasattr(discord, 'Client')
except ImportError:
    AVAILABLE = False


@unittest.skipUnless(AVAILABLE, 'Optional pinned Discord dependency is tested in its image and CI')
class DiscordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import sys
        root = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(root / 'ops'))
        spec = importlib.util.spec_from_file_location('private_bot', root / 'discord/bot.py')
        cls.bot = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.bot)

    def test_six_commands_only(self):
        async def check():
            client = discord.Client(intents=discord.Intents.none())
            from discord import app_commands
            fake = SimpleNamespace(tree=app_commands.CommandTree(client))
            self.bot.install_commands(fake)
            self.assertEqual({x.name for x in fake.tree.get_commands()}, {'pzstatus', 'pzinfo', 'pzmods', 'pzip', 'pzhealth', 'pzrestart'})
            await client.close()
        asyncio.run(check())

    def test_role_is_case_insensitive_and_missing_denied(self):
        member = SimpleNamespace(roles=[SimpleNamespace(name='ZoMbOiD')])
        self.assertTrue(self.bot.role_allowed(member, 'zomboid'))
        self.assertFalse(self.bot.role_allowed(member, 'OtherRole'))
        self.assertFalse(self.bot.role_allowed(SimpleNamespace(), 'zomboid'))

    def test_page_owner_and_wraparound(self):
        async def check():
            pages = self.bot.Pages(7, ['one', 'two'])
            good = SimpleNamespace(user=SimpleNamespace(id=7), response=SimpleNamespace(edit_message=AsyncMock()))
            bad = SimpleNamespace(user=SimpleNamespace(id=8), response=SimpleNamespace(send_message=AsyncMock()))
            self.assertTrue(await pages.interaction_check(good))
            self.assertFalse(await pages.interaction_check(bad))
            await pages.children[0].callback(good)
            self.assertEqual(pages.index, 1)
            await pages.children[1].callback(good)
            self.assertEqual(pages.index, 0)
        asyncio.run(check())
