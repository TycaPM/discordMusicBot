import os
import discord
import yt_dlp as youtube_dl
import asyncio
from discord.ext import commands
from dotenv import load_dotenv
from googleapiclient.discovery import build

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
YT_API_KEY = os.getenv('YT_API_KEY')

intents = discord.Intents.default()
intents.message_content = True

queue_cleared_by_stop = False
loop_flag = False
current_song = None 
skipto_in_progress = False
bot = discord.Bot()

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    await bot.change_presence(status=discord.Status.idle, activity=discord.Game("Just chillin :3"))

youtube = build('youtube', 'v3', developerKey=YT_API_KEY)

ytdl_format_options = {
     'format': 'bestaudio/best',
    'noplaylist': 'True',
    'extractaudio': True,
    'audioformat': 'mp3',
    'quiet': True,
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 2',
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)
music_queue = []

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.35):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))

        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url']
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

async def play_next(ctx, is_skipto=False):
    global queue_cleared_by_stop, loop_flag, current_song
    if not music_queue:
        if not queue_cleared_by_stop:
            if not ctx.interaction.response.is_done():
                await ctx.respond("``𝙌𝙪𝙚𝙪𝙚 𝙞𝙨 𝙚𝙢𝙥𝙩𝙮.``")
            else:
                await ctx.send_followup("``𝙌𝙪𝙚𝙪𝙚 𝙞𝙨 𝙚𝙢𝙥𝙩𝙮.``")
            await bot.change_presence(status=discord.Status.idle, activity=discord.Game("Just chillin :3"))
        return

    queue_cleared_by_stop = False

    if loop_flag:
        next_song = current_song
    elif not is_skipto:
        next_song = music_queue.pop(0)
    else:
        next_song = music_queue[0]

    current_player = await YTDLSource.from_url(next_song['url'], loop=bot.loop)

    if not ctx.voice_client.is_playing():
        current_song = next_song  # Update the currently playing song
        ctx.voice_client.play(current_player, after=lambda e: bot.loop.create_task(play_next(ctx)))
        if not ctx.interaction.response.is_done():
            await ctx.respond(f"```𝙉𝙤𝙬 𝙥𝙡𝙖𝙮𝙞𝙣𝙜: \n{next_song['title']}```")
        else:
            await ctx.send_followup(f"```𝙉𝙤𝙬 𝙥𝙡𝙖𝙮𝙞𝙣𝙜: \n{next_song['title']}```")
        await bot.change_presence(activity=discord.Game(" 𝙨𝙤𝙢𝙚 𝙩𝙪𝙣𝙚𝙨!"), status=discord.Status.online)
    else:
        print("**Already playing audio, not calling play_next again.**")

@bot.slash_command()
async def play(ctx, *, search_terms):
    global music_queue

    if not ctx.author.voice:
        await ctx.respond("**You need to be in a voice channel to use this command.**")
        return

    channel = ctx.author.voice.channel

    if ctx.voice_client is None:
        voice_client = await channel.connect()
    else:
        voice_client = ctx.voice_client

    search_terms_list = [term.strip() for term in search_terms.split(',')]

    for term in search_terms_list:
        if term.startswith("http"):
            video_url = term
            video_title = "Video from link"
            data = await YTDLSource.from_url(video_url)
            video_title = data.title
        else:
            request = youtube.search().list(
                part='snippet',
                maxResults=1,
                q=term,
                type='video'
            )
            response = request.execute()

            if not response['items']:
                await ctx.respond(f"**No results found for ``'{term}'.``**")
                continue

            video_id = response['items'][0]['id']['videoId']
            video_url = f'https://www.youtube.com/watch?v={video_id}'
            video_title = response['items'][0]['snippet']['title']
        
        music_queue.append({'title': video_title, 'url': video_url})
        await ctx.respond(f"```+ 𝘼𝙙𝙙𝙞𝙣𝙜 𝙨𝙤𝙣𝙜 𝙩𝙤 𝙦𝙪𝙚𝙪𝙚:\n{video_title}```")

        if not voice_client.is_playing() and not voice_client.is_paused():
            await play_next(ctx)
            await bot.change_presence(activity=discord.Game(" 𝙨𝙤𝙢𝙚 𝙩𝙪𝙣𝙚𝙨!"), status=discord.Status.online)
        else:
            await bot.change_presence(activity=discord.Game(" 𝙨𝙤𝙢𝙚 𝙩𝙪𝙣𝙚𝙨!"), status=discord.Status.online)

@bot.slash_command()
async def queue(ctx):
    if not music_queue:
        await ctx.respond("``𝙏𝙝𝙚 𝙦𝙪𝙚𝙪𝙚 𝙞𝙨 𝙘𝙪𝙧𝙧𝙚𝙣𝙩𝙡𝙮 𝙚𝙢𝙥𝙩𝙮.``")
        return

    current_song = ctx.voice_client.source.title if ctx.voice_client.is_playing() else "𝙉𝙤 𝙨𝙤𝙣𝙜 𝙘𝙪𝙧𝙧𝙚𝙣𝙩𝙡𝙮 𝙥𝙡𝙖𝙮𝙞𝙣𝙜."
    
    queue_list = "\n".join(f"{i+1}. {song['title']}" for i, song in enumerate(music_queue))
    await ctx.respond(f"```𝘾𝙪𝙧𝙧𝙚𝙣𝙩𝙡𝙮 𝙥𝙡𝙖𝙮𝙞𝙣𝙜: {current_song}\n\n𝘾𝙪𝙧𝙧𝙚𝙣𝙩 𝙦𝙪𝙚𝙪𝙚:\n{queue_list}```")

@bot.slash_command()
async def pause(ctx):
    if ctx.voice_client.is_playing():
        source = ctx.voice_client.source
        if isinstance(source, discord.PCMVolumeTransformer):
            fade_duration = 0.25
            fade_steps = 10
            step_duration = fade_duration / fade_steps
            volume_step = source.volume / fade_steps

            for _ in range(fade_steps):
                source.volume = max(0, source.volume - volume_step)
                await asyncio.sleep(step_duration)

            source.volume = 0
        
        ctx.voice_client.pause()
        await ctx.respond("``𝙈𝙪𝙨𝙞𝙘 𝙝𝙖𝙨 𝙥𝙖𝙪𝙨𝙚𝙙.``")
    else:
        await ctx.respond("``𝙉𝙤 𝙢𝙪𝙨𝙞𝙘 𝙞𝙨 𝙘𝙪𝙧𝙧𝙚𝙣𝙩𝙡𝙮 𝙥𝙡𝙖𝙮𝙞𝙣𝙜.``")

@bot.slash_command()
async def resume(ctx):
    if ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        source = ctx.voice_client.source
        if isinstance(source, discord.PCMVolumeTransformer):
            fade_duration = 0.25
            fade_steps = 10
            step_duration = fade_duration / fade_steps
            volume_step = 0.35 / fade_steps

            source.volume = 0

            for _ in range(fade_steps):
                source.volume = min(0.35, source.volume + volume_step)
                await asyncio.sleep(step_duration)
        await ctx.respond("``𝙈𝙪𝙨𝙞𝙘 𝙝𝙖𝙨 𝙧𝙚𝙨𝙪𝙢𝙚𝙙.``")
    else:
        await ctx.respond("``𝙉𝙤 𝙢𝙪𝙨𝙞𝙘 𝙞𝙨 𝙘𝙪𝙧𝙧𝙚𝙣𝙩𝙡𝙮 𝙥𝙖𝙪𝙨𝙚𝙙.``")

@bot.slash_command()
async def skip(ctx):
    if not ctx.voice_client or not ctx.voice_client.is_playing():
        await ctx.respond("``𝙏𝙝𝙚𝙧𝙚 𝙞𝙨 𝙣𝙤 𝙢𝙪𝙨𝙞𝙘 𝙘𝙪𝙧𝙧𝙚𝙣𝙩𝙡𝙮 𝙥𝙡𝙖𝙮𝙞𝙣𝙜.``")
        return

    ctx.voice_client.stop()

    if len(music_queue) == 0:
        await ctx.respond("``𝙌𝙪𝙚𝙪𝙚 𝙞𝙨 𝙚𝙢𝙥𝙩𝙮.``")
        return

    await play_next(ctx)

@bot.slash_command()
async def skipto(ctx, song_number: int):
    global music_queue, skipto_in_progress

    if not ctx.voice_client or not ctx.voice_client.is_playing():
        await ctx.respond("``𝙏𝙝𝙚𝙧𝙚 𝙞𝙨 𝙣𝙤 𝙢𝙪𝙨𝙞𝙘 𝙘𝙪𝙧𝙧𝙚𝙣𝙩𝙡𝙮 𝙥𝙡𝙖𝙮𝙞𝙣𝙜.``")
        return

    if song_number < 1 or song_number > len(music_queue):
        await ctx.respond(f"```𝙄𝙣𝙫𝙖𝙡𝙞𝙙 𝙨𝙤𝙣𝙜 𝙣𝙪𝙢𝙗𝙚𝙧. \nPlease choose a number between [1 and {len(music_queue)}].```")
        return

    skipto_in_progress = True
    song_index = song_number 
    song_to_play = music_queue[song_index - 1]

    ctx.voice_client.stop()

    if music_queue:
        song_to_duplicate = music_queue[0]
        music_queue.insert(0, {'title': song_to_duplicate['title'], 'url': song_to_duplicate['url']})

    del music_queue[song_index]
    current_player = await YTDLSource.from_url(song_to_play['url'], loop=bot.loop)
    
    ctx.voice_client.play(current_player, after=lambda e: bot.loop.create_task(play_next(ctx, is_skipto=True)))
    await ctx.respond(f"```𝙎𝙠𝙞𝙥𝙥𝙚𝙙 𝙩𝙤: {song_to_play['title']} \n𝙖𝙣𝙙 𝙧𝙚𝙢𝙤𝙫𝙚𝙙 𝙞𝙩 𝙛𝙧𝙤𝙢 𝙩𝙝𝙚 𝙦𝙪𝙚𝙪𝙚.```")
    skipto_in_progress = False

@bot.slash_command()
async def leave(ctx):
    global queue_cleared_by_stop, music_queue
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
    music_queue.clear()
    queue_cleared_by_stop = True
    await ctx.respond("``𝙎𝙩𝙤𝙥𝙥𝙚𝙙 𝙥𝙡𝙖𝙮𝙞𝙣𝙜 𝙢𝙪𝙨𝙞𝙘 𝙖𝙣𝙙 𝙘𝙡𝙚𝙖𝙧𝙚𝙙 𝙩𝙝𝙚 𝙦𝙪𝙚𝙪𝙚.``")
    await bot.change_presence(status=discord.Status.idle, activity=discord.Game("Just chillin :3"))
    await ctx.voice_client.disconnect()

@bot.slash_command()
async def remove(ctx, index: int):
    if 0 < index <= len(music_queue):
        removed_song = music_queue.pop(index - 1)
        await ctx.respond(f"```𝙍𝙚𝙢𝙤𝙫𝙚𝙙: {removed_song['title']} 𝙛𝙧𝙤𝙢 𝙩𝙝𝙚 𝙦𝙪𝙚𝙪𝙚.```")
    else:
        await ctx.respond("``𝙄𝙣𝙫𝙖𝙡𝙞𝙙 𝙨𝙤𝙣𝙜 𝙣𝙪𝙢𝙗𝙚𝙧.``")

@bot.slash_command()
async def help(ctx):
    help_text = """
    **Music Bot Commands:**
    
    `/play <youtube link>` - Plays audio from url(s). Can take multiple urls seperated with ","s
    `/stop` - Stops the current song, clears the queue, and disconnects the bot from the voice channel.
    `/skipto <song_number>` - Skips to a specific song in the queue and removes that song from the queue.
    `/queue` - Displays the current queue and the song currently playing.
    `/remove <song number>` - Removes a song from the queue based on its position.
    `/skip` - Skips the currently playing song and plays the next song in the queue.
    `/pause` - Pauses the currently playing music.
    `/resume` - Resumes from where the song was paused.
    """
    
    await ctx.respond(help_text)

# @bot.slash_command()
# async def loop(ctx):
#     global loop_flag, current_song

#     if not ctx.voice_client or not ctx.voice_client.is_playing():
#         await ctx.respond("There is no song currently playing to loop.")
#         return

#     loop_flag = not loop_flag

#     if loop_flag:
#         await ctx.respond(f"Looping: {current_song['title']}")
#     else:
#         await ctx.respond("Looping disabled.")

bot.run(TOKEN)