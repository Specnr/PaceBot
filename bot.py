import os
import discord
import asyncio
import json
from discord import app_commands
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

import therun
import mongo
settings = {}
with open("config.json") as f:
    settings = json.load(f)


def log(msg):
    print(f"[LOG]: {msg}")


class PacepalClient(discord.Client):
    prev_paces = [None]
    to_be_archived = {}
    run_storage = {}

    def __init__(self, settings, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.run_every = settings["update-frequency"]

    async def setup_hook(self) -> None:
        self.bg_task = self.loop.create_task(self.send_pace())

    async def on_ready(self):
        if settings["watching-msg"] != "":
            await self.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=settings["watching-msg"]))

        print(f'Logged in as {self.user} (ID: {self.user.id})')

    def is_me(self, msg):
        return msg.author == self.user

    async def wipe_old_pace(self):
        channel = self.get_channel(self.channel_id)
        await channel.purge(check=self.is_me)

    async def send_archived_pace(self, pace):
        msg = therun.get_archive_run_msg(pace)
        channel = self.get_channel(self.archive_channel_id)
        await channel.send(msg)

    async def send_pace(self):
        await self.wait_until_ready()
        channel = self.get_channel(self.channel_id)
        while not self.is_closed():
            print("------")
            servers = await mongo.get_server_data()
            try:
                all_pace = therun.get_all_pace(settings["game"], settings, self.run_storage)
            except:
                log(f"Read failed, retrying in {self.run_every}s")
                await asyncio.sleep(self.run_every)
                continue

            simple_pace = therun.simplify_pace(all_pace)
            users = { p["user"] for p in all_pace }
            for server in servers:
                self.channel_id = server["paceChannel"]
                self.archive_channel_id = server["paceArchiveChannel"]

                if self.archive_channel_id != -1 and len(self.to_be_archived) > 0:
                    to_remove = set()
                    for user in self.to_be_archived:
                        # If not in users, pace has been removed, so run is over
                        if user not in users:
                            await self.send_archived_pace(self.to_be_archived[user])
                            to_remove.add(user)
                    for user in to_remove:
                        del self.to_be_archived[user]

                if simple_pace != self.prev_paces:
                    embeds = []
                    for pace in all_pace:
                        if self.archive_channel_id != -1:
                            self.run_storage[pace["user"]] = therun.get_storeable_run(pace)
                            if therun.can_run_be_archived(pace):
                                log(f"{pace['user']} achieved good pace and will be archived")
                                self.to_be_archived[pace["user"]] = pace

                        pace_embed = await therun.get_run_embed(pace, settings)
                        if pace_embed is not None:
                            embeds.append(pace_embed)

                    await self.wipe_old_pace()
                    for embed in embeds:
                        await channel.send(embed=embed)
                    if len(embeds) == 0:
                        await channel.send(server["noPaceMsg"])
                    self.prev_paces = simple_pace 
                else:
                    log("Skipping update because pace was unchanged")

                if self.archive_channel_id != -1:
                    to_remove = set()
                    for user in self.run_storage:
                        run_dt = datetime.fromtimestamp(self.run_storage[user]["insertedAt"]/1000.0)
                        diff = datetime.utcnow() - run_dt
                        if diff.seconds > 3600:
                            to_remove.add(user)
                    for user in to_remove:
                        del self.run_storage[user]

            await asyncio.sleep(self.run_every)

client = PacepalClient(settings, intents=discord.Intents.default())
tree = app_commands.CommandTree(client)

# COMMANDS

@tree.command(name="setup", description="[PaceBot] Setup all required info for PaceBot to work")
async def cmd_setup(interaction: discord.Interaction, pace_channel_id: int, archive_channel_id: int):
    if not interaction.message.author.guild_permissions.administrator:
        await interaction.response.send_message("This command is for admins only")
        return

    server_data = {
        "serverId": interaction.message.guild.id,
        "paceChannel": pace_channel_id,
        "paceArchiveChannel": archive_channel_id,
        "noPaceMsg": "No one currently on pace...",
        # "whitelist": [],
        # "archivePaceRequirements: []"
    }
    await mongo.update_server(interaction.guild.id, server_data)
    await interaction.response.send_message("PaceBot setup successfully!")

# UPDATE COMMANDS

@tree.command(name="updateChannel", description="Updates the channel which pace is sent to")
async def cmd_updateChannel(interaction: discord.Interaction, new_channel_id):
    if not interaction.message.author.guild_permissions.administrator:
        await interaction.response.send_message("This command is for admins only")
        return
    
    await mongo.update_server(interaction.guild.id, {"paceChannel": new_channel_id})
    await interaction.response.send_message("Pace channel updated successfully")

@tree.command(name="updateArchiveChannel", description="Updates the channel which pace archives are sent to. Set to -1 if you dont want archives")
async def cmd_updateArchiveChannel(interaction: discord.Interaction, new_channel_id):
    if not interaction.message.author.guild_permissions.administrator:
        await interaction.response.send_message("This command is for admins only")
        return
    
    await mongo.update_server(interaction.guild.id, {"paceArchiveChannel": new_channel_id})
    await interaction.response.send_message("Pace archive channel updated successfully")

@tree.command(name="updateNoPaceMsg", description="Updates the message sent when no pace is found")
async def cmd_updateNoPaceMsg(interaction: discord.Interaction, no_pace_msg):
    if not interaction.message.author.guild_permissions.administrator:
        await interaction.response.send_message("This command is for admins only")
        return
    
    await mongo.update_server(interaction.guild.id, {"noPaceMsg": no_pace_msg})
    await interaction.response.send_message("No pace message updated successfully")

client.run(os.getenv('DISCORD_SECRET'))
