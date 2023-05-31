import os
from dotenv import load_dotenv
from twitchAPI.twitch import Twitch
from twitchAPI.helper import first

load_dotenv()
API = "https://api.twitch.tv/helix/users?login="
CLIENT = os.getenv('TWITCH_CLIENT')
SECRET = os.getenv('TWITCH_SECRET')
DEFAULT_PFP = "https://static-cdn.jtvnw.net/user-default-pictures-uv/13e5fa74-defa-11e9-809c-784f43822e80-profile_image-300x300.png"


async def get_pfp(username):
    twitch = await Twitch(CLIENT, SECRET)
    user = await first(twitch.get_users(logins=username))
    return user.profile_image_url if user is not None else DEFAULT_PFP
