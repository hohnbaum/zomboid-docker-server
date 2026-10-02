"""Six German commands over the private API. No RCON, filesystem or shell access."""
import asyncio
import json
import os
import uuid
from pathlib import Path
import discord
from discord import app_commands
from pzops.api_client import Client
from pzops.util import PZError


def role_allowed(member, role):
    return any(x.name.casefold() == role.casefold() for x in getattr(member, "roles", []))


class Pages(discord.ui.View):
    def __init__(self, owner, pages):
        super().__init__(timeout=300)
        self.owner, self.pages, self.index = owner, pages, 0

    async def interaction_check(self, interaction):
        if interaction.user.id == self.owner:
            return True
        await interaction.response.send_message("Diese Auswahl gehört einer anderen Person.", ephemeral=True)
        return False

    @discord.ui.button(label="Zurück", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction, _):
        self.index = (self.index - 1) % len(self.pages)
        await interaction.response.edit_message(embed=self.pages[self.index], view=self)

    @discord.ui.button(label="Weiter", style=discord.ButtonStyle.secondary)
    async def following(self, interaction, _):
        self.index = (self.index + 1) % len(self.pages)
        await interaction.response.edit_message(embed=self.pages[self.index], view=self)


class Bot(discord.Client):
    def __init__(self):
        intents = discord.Intents.none()
        intents.guilds = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.ops = Client()
        self.guild = discord.Object(id=int(os.environ["PZ_DISCORD_GUILD_ID"]))

    async def setup_hook(self):
        self.tree.copy_global_to(guild=self.guild)
        await self.tree.sync(guild=self.guild)

    async def read(self, action):
        return await asyncio.to_thread(self.ops.request, action)


def install_commands(bot):
    @bot.tree.command(name="pzstatus", description="Serverstatus und Spielerzahl anzeigen")
    @app_commands.guild_only()
    async def status(interaction: discord.Interaction):
        await interaction.response.defer()
        value = await bot.read("status")
        count = value["players"] if value["players_known"] else "unbekannt"
        embed = discord.Embed(title="Project Zomboid", description=f"Status: **{value['state']}**\nSpieler: **{count}**")
        embed.add_field(name="Betrieb", value=f"Gewünscht: {value['desired']}\nWartung: {value['maintenance']}\nMod-Neustart ausstehend: {value['pending']}")
        embed.add_field(name="Version", value=f"{value['version'] or 'unbekannt'} / Build {value['build'] or 'unbekannt'}")
        if value.get("uptime_seconds") is not None:
            embed.add_field(name="Laufzeit", value=f"{int(value['uptime_seconds'] // 60)} Minuten")
        if value.get("player_names"):
            embed.add_field(name="Spieler", value=", ".join(discord.utils.escape_markdown(x) for x in value["player_names"])[:1000])
        await interaction.followup.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())

    @bot.tree.command(name="pzinfo", description="Freigegebene Servereinstellungen anzeigen")
    @app_commands.guild_only()
    async def info(interaction: discord.Interaction):
        await interaction.response.defer()
        value = await bot.read("info")
        pages = []
        for title, content in (("Server", value["settings"]), ("Welt", value.get("world", {})), ("Mods und Karten", {"Workshop": len(value['managed']['WorkshopItems']), "Mods": len(value['managed']['Mods']), "Karten": "; ".join(value['managed']['Maps'])})):
            pages.append(discord.Embed(title=title, description="\n".join(f"{k}: {v}" for k, v in content.items())[:3800] or "Keine Angaben"))
        await interaction.followup.send(embed=pages[0], view=Pages(interaction.user.id, pages), allowed_mentions=discord.AllowedMentions.none())

    @bot.tree.command(name="pzmods", description="Workshop-Inhalte in konfigurierter Reihenfolge anzeigen")
    @app_commands.guild_only()
    async def mods(interaction: discord.Interaction):
        await interaction.response.defer()
        value = await bot.read("workshop-status")
        items = value["Items"]
        pages = []
        for off in range(0, max(1, len(items)), 25):
            lines = [f"{off+i+1}. [{discord.utils.escape_markdown(x['Title'] or x['Id'])[:70]}](https://steamcommunity.com/sharedfiles/filedetails/?id={x['Id']}) — {x['Status']}" for i, x in enumerate(items[off:off+25])]
            pages.append(discord.Embed(title=f"Workshop ({len(items)}) · Seite {len(pages)+1}", description="\n".join(lines)[:3900] or "Keine Workshop-Inhalte konfiguriert."))
        await interaction.followup.send(embed=pages[0], view=Pages(interaction.user.id, pages), allowed_mentions=discord.AllowedMentions.none())

    @bot.tree.command(name="pzip", description="Konfigurierte Verbindungsadressen anzeigen")
    @app_commands.guild_only()
    async def endpoints(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        value = await bot.read("endpoints")
        lines = [f"{name.upper()}: {address}" for name, address in value.items() if address]
        await interaction.followup.send("\n".join(lines) or "Keine Verbindungsadressen konfiguriert.", ephemeral=True, allowed_mentions=discord.AllowedMentions.none())

    @bot.tree.command(name="pzhealth", description="Betrieb, Sicherung und Update-Diagnose anzeigen")
    @app_commands.guild_only()
    async def health(interaction: discord.Interaction):
        await interaction.response.defer()
        value = await bot.read("health")
        embed = discord.Embed(title="Betriebsdiagnose", description=f"Status: {value['state']}\nRCON: {value['rcon']}\nUDP: {value['udp']}\nSicherungsalter (Stunden): {value['backup_age_hours']}\nUpdate verfügbar: {value['update']['available']}\nWorkshop: {value['workshop']['State']}\nConfig: {value['config']['state']}\nHinweise: {', '.join(value['detail']) or 'keine'}")
        await interaction.followup.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())

    @bot.tree.command(name="pzrestart", description="Sicheren Neustart oder Serverupdate anfordern")
    @app_commands.guild_only()
    async def restart(interaction: discord.Interaction):
        if not role_allowed(interaction.user, os.getenv("PZ_DISCORD_RESTART_ROLE", "Zomboid")):
            await interaction.response.send_message("Dir fehlt die freigegebene Neustart-Rolle.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        # Zero-player safety is enforced inside the serialized ops job as well.
        job = await asyncio.to_thread(bot.ops.request, "jobs", {"action": "discord-restart", "args": {}, "request_id": uuid.uuid4().hex})
        await interaction.followup.send(f"Auftrag `{job['id']}` angenommen. Der Auftrag läuft unabhängig von Discord weiter.", ephemeral=True)
        last = None
        for _ in range(420):
            job = await bot.read("jobs/" + job["id"])
            if job.get("phase") != last or job["state"] not in ("queued", "running"):
                last = job.get("phase")
                try:
                    await interaction.edit_original_response(content=f"Auftrag `{job['id']}`: {job['state']} · {last}\n{job.get('error', '')}")
                except discord.HTTPException:
                    return
            if job["state"] not in ("queued", "running"):
                return
            await asyncio.sleep(2)
        await interaction.edit_original_response(content=f"Auftrag `{job['id']}` läuft weiter. Status kann über `pz job {job['id']}` geprüft werden.")

    @bot.tree.error
    async def error(interaction, exc):
        original = getattr(exc, "original", exc)
        code = original.code if isinstance(original, PZError) else "DISCORD_COMMAND_FAILED"
        message = "Aktion fehlgeschlagen: " + code
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)


def main():
    token = Path("/run/secrets/discord_token").read_text().strip()
    if not token or not os.getenv("PZ_DISCORD_GUILD_ID", "").isdigit():
        raise SystemExit("DISCORD_CONFIGURATION_REQUIRED")
    bot = Bot()
    install_commands(bot)
    bot.run(token, log_handler=None)


if __name__ == "__main__":
    main()
