import os
import discord
import asyncio
import json
from dotenv import load_dotenv
load_dotenv()

import therun
settings = {}
with open("config.json") as f:
    settings = json.load(f)


def log(msg):
    print(f"[LOG]: {msg}")


class PacepalClient(discord.Client):
    run_every = settings["update-frequency"]
    channel_id = settings["output-channel-id"]
    archive_channel_id = settings["archive-channel-id"]
    prev_paces = [None]
    to_be_archived = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

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
            all_pace = therun.get_all_pace(settings["game"], settings)
            simple_pace = therun.simplify_pace(all_pace)

            if len(self.to_be_archived) > 0:
                users = { p["user"] for p in all_pace }
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
                    await channel.send(settings["no-pace-msg"])
                self.prev_paces = simple_pace 
            else:
                log("Skipping update because pace was unchanged")

            await asyncio.sleep(self.run_every)

client = PacepalClient(intents=discord.Intents.default())
client.run(os.getenv('DISCORD_SECRET'))
