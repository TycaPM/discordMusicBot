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
    'noplaylist': True
}

ffmpeg_options = {
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)
queue = []

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
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
    if not queue:
        if not queue_cleared_by_stop:
            await ctx.respond("Queue is empty.")
            await bot.change_presence(status=discord.Status.idle)
        return

    queue_cleared_by_stop = False

    # If loop is enabled, replay the current song
    if loop_flag:
        next_song = current_song  # Play the current song again
    elif not is_skipto:
        next_song = queue.pop(0)
    else:
        next_song = queue[0]

    current_player = await YTDLSource.from_url(next_song['url'], loop=bot.loop)

    if not ctx.voice_client.is_playing():
        current_song = next_song  # Update the currently playing song
        ctx.voice_client.play(current_player, after=lambda e: bot.loop.create_task(play_next(ctx)))
        await ctx.respond(f"Now playing: {next_song['title']}")
        await bot.change_presence(activity=discord.Game("Playin some tunes!"), status=discord.Status.online)
    else:
        print("Already playing audio, not calling play_next again.")

@bot.slash_command(guild_ids=[1292287390534078478])
async def play(ctx, *, search_terms):
    global queue

    if not ctx.author.voice:
        await ctx.respond("You need to be in a voice channel to use this command.")
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
                await ctx.respond(f"No results found for '{term}'.")
                continue

            video_id = response['items'][0]['id']['videoId']
            video_url = f'https://www.youtube.com/watch?v={video_id}'
            video_title = response['items'][0]['snippet']['title']
        
        queue.append({'title': video_title, 'url': video_url})
        await ctx.respond(f"Adding song to que.")

        if not voice_client.is_playing() and not voice_client.is_paused():
            await play_next(ctx)
            await ctx.respond(f"Added to queue: {video_title}")
            await bot.change_presence(activity=discord.Game("Playin some tunes!"), status=discord.Status.online)
        else:
            await ctx.respond(f"Added to queue: {video_title}")
            await bot.change_presence(activity=discord.Game("Playin some tunes!"), status=discord.Status.online)

@bot.slash_command(guild_ids=[1292287390534078478])
async def stop(ctx):
    global queue_cleared_by_stop, queue
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
    queue.clear()
    queue_cleared_by_stop = True
    await ctx.respond("Stopped playing music and cleared the queue.")
    await bot.change_presence(status=discord.Status.idle)
    await ctx.voice_client.disconnect()

@bot.slash_command(guild_ids=[1292287390534078478])
async def skipto(ctx, song_number: int):
    global queue, skipto_in_progress

    if not ctx.voice_client or not ctx.voice_client.is_playing():
        await ctx.respond("There is no audio currently playing.")
        return

    if song_number < 1 or song_number > len(queue):
        await ctx.respond(f"Invalid song number. Please choose a number between 1 and {len(queue)}.")
        return

    skipto_in_progress = True
    song_index = song_number - 1
    song_to_play = queue[song_index]

    print(f"Queue before skipto: {queue}")
    print(f"Skipping to index: {song_index}, Song to play: {song_to_play}")

    ctx.voice_client.stop()

    if queue:
        song_to_duplicate = queue[0]
        queue.insert(0, {'title': song_to_duplicate['title'], 'url': song_to_duplicate['url']})

    del queue[song_index]
    current_player = await YTDLSource.from_url(song_to_play['url'], loop=bot.loop)
    
    ctx.voice_client.play(current_player, after=lambda e: bot.loop.create_task(play_next(ctx, is_skipto=True)))
    await ctx.respond(f"Skipped to: {song_to_play['title']} and removed it from the queue. Duplicated the previous song and added it to the front of the queue.")
    skipto_in_progress = False

@bot.slash_command(guild_ids=[1292287390534078478])
async def que(ctx):
    if not queue:
        await ctx.respond("The queue is currently empty.")
        return

    current_song = ctx.voice_client.source.title if ctx.voice_client.is_playing() else "No song currently playing"
    
    queue_list = "\n".join(f"{i+1}. {song['title']}" for i, song in enumerate(queue))
    await ctx.respond(f"Currently playing: {current_song}\n\nCurrent queue:\n{queue_list}")

@bot.slash_command(guild_ids=[1292287390534078478])
async def remove(ctx, index: int):
    if 0 < index <= len(queue):
        removed_song = queue.pop(index - 1)
        await ctx.respond(f"Removed {removed_song['title']} from the queue.")
    else:
        await ctx.respond("Invalid song number.")

@bot.slash_command(guild_ids=[1292287390534078478])
async def skip(ctx):
    if not ctx.voice_client or not ctx.voice_client.is_playing():
        await ctx.respond("There is no audio currently playing.")
        return

    ctx.voice_client.stop()

    if len(queue) == 0:
        await ctx.respond("Queue is empty.")
        return

    await play_next(ctx)

@bot.slash_command(guild_ids=[1292287390534078478])
async def pause(ctx):
    if ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.respond(f"Paused the music.")
    else:
        await ctx.respond("No song is currently playing.")

@bot.slash_command(guild_ids=[1292287390534078478])
async def resume(ctx):
    if ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.respond("Resumed the music.")
    else:
        await ctx.respond("The music is not paused.")

@bot.slash_command(guild_ids=[1292287390534078478])
async def loop(ctx):
    global loop_flag, current_song

    if not ctx.voice_client or not ctx.voice_client.is_playing():
        await ctx.respond("There is no song currently playing to loop.")
        return

    loop_flag = not loop_flag

    if loop_flag:
        await ctx.respond(f"Looping: {current_song['title']}")
    else:
        await ctx.respond("Looping disabled.")

bot.run(TOKEN)