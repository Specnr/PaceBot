import requests
import discord
import twitch
from functools import cmp_to_key

API = "https://therun.gg/api/live"


def get_split_idx(player):
    for i in range(len(player["splits"]) - 1, -1, -1):
        curr_split = player["splits"][i]["splitTime"]
        if curr_split != None:
            return i
    return -1


def compare_pace(p1, p2):
    # Get split levels
    p1_split_level, p2_split_level = get_split_idx(p1), get_split_idx(p2)
    p1_curr_split, p2_curr_split = p1["splits"][p1_split_level]["splitTime"], p2["splits"][p2_split_level]["splitTime"]
    if p1_split_level > p2_split_level:
        return 1
    if p2_split_level > p1_split_level:
        return -1
    # At the same split, prioritize player on better pace
    if p1_split_level == -1:    # Not in nether yet
        return 0
    if p1_curr_split > p2_curr_split:
        return -1
    if p2_curr_split > p1_curr_split:
        return 1
    return 0


def get_all_pace(game):
    data = requests.get(API).json()
    filtered = filter(lambda x: x["game"] == game, data)
    return sorted(list(filtered), key=cmp_to_key(compare_pace))


def ms_to_time(ms):
    if ms is None:
        return "0:00"
    total_s = ms / 1000
    m = int(total_s // 60)
    s = int(total_s % 60)
    pref = "0" if s < 10 else ""
    m_pref = "0" if m < 10 else ""
    return f"{m_pref}{m}:{pref}{s}"


async def get_run_embed(pace, min_split, only_live):
    if pace["hasReset"] or pace["currentSplitIndex"] < min_split:
        return None
    if only_live and not pace["currentlyStreaming"]:
        return None

    twitch_username = pace['user']
    embed_msg = discord.Embed(title=twitch_username,
                              url=f"https://twitch.tv/{twitch_username}",
                              color=discord.Color.purple())
    pfp_url = await twitch.get_pfp(twitch_username)
    embed_msg.set_thumbnail(url=pfp_url)
    embed_msg.set_footer(text=f"Current Time - {ms_to_time(pace['currentTime'])}")

    for split in pace["splits"]:
        s_time, s_name = split["splitTime"], split["name"]
        if s_time is None:
            break
        embed_msg.add_field(
            name=f"**{ms_to_time(s_time)}** {s_name}", value="", inline=False)

    return embed_msg
