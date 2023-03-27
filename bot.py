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


class PacepalClient(discord.Client):
    run_every = settings["update-frequency"]
    channel_id = settings["output-channel-id"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def setup_hook(self) -> None:
        self.bg_task = self.loop.create_task(self.my_background_task())

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')

    def is_me(self, msg):
        return msg.author == self.user

    async def wipe_old_pace(self):
        channel = self.get_channel(self.channel_id)
        await channel.purge(check=self.is_me)

    async def my_background_task(self):
        await self.wait_until_ready()
        channel = self.get_channel(self.channel_id)
        while not self.is_closed():
            all_pace = therun.get_all_pace(settings["game"])
            embeds = []
            for pace in all_pace:
                pace_embed = await therun.get_run_embed(pace, settings["minimum-split"], settings["only-show-live"])
                if pace_embed is not None:
                    embeds.append(pace_embed)
            await self.wipe_old_pace()
            for embed in embeds:
                await channel.send(embed=embed)
            if len(embeds) == 0:
                await channel.send(settings["no-pace-msg"])
            await asyncio.sleep(self.run_every)
client = PacepalClient(intents=discord.Intents.default())
client.run(os.getenv('DISCORD_SECRET'))
