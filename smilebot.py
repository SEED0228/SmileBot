import asyncio
import discord
import random
from bs4 import BeautifulSoup
import requests
import json
from niconico_dl import NicoNicoVideoAsync
from typing import Tuple, Dict
from dotenv import load_dotenv
from os import getenv

ffmpeg_options = {
    'before_options':
    '-vn -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
}

client = discord.Client()

niconico_headers = {
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "ja",
    "Connection": "keep-alive",
    "Host": "nvapi.nicovideo.jp",
    "Origin": "https://www.nicovideo.jp",
    "Referer": "https://www.nicovideo.jp/",
    "sec-ch-ua-mobile": "?0",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "User-Agent":
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
    "X-Frontend-Id": "6",
    "X-Frontend-Version": "0",
    "X-Niconico-Language": "ja-jp"
}

class NicoNicoDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, url, volume=0.1):
        super().__init__(source, volume)

        self.url = url

    @classmethod
    async def from_url(cls, url, *, log=False, volume=0.1):
        niconico = NicoNicoVideoAsync(url=url)
        stream_url = await niconico.get_download_link()
        return (cls(discord.FFmpegPCMAudio(stream_url, **ffmpeg_options), url=stream_url, volume=volume), niconico)

async def create_ncnc_link(args) -> Tuple[str, Dict[str, str], Dict[str, str], bool]:
    params = {'q': '', 'targets': 'title', 'min_viewCounter': '0', 'sort': '-viewCounter', 'limit': '5', 'from': '2000-01-01', 'to': '2099-12-31'}
    errors = []
    if '-t' in args:
        args.remove('-t')
    for arg in args:
        attrs = arg.split('=')
        if len(attrs) == 1:
            params['q'] = attrs[0] if params['q'] == '' else params['q'] + ' ' + attrs[0]
        elif len(attrs) == 2:
            if attrs[0] in params:
                params[attrs[0]] = attrs[1].replace('+', '%2b')
            else:
                errors.append({'name': "invalid argument", 'value': arg})
        else:
            errors.append({'name': "invalid argument", 'value': arg})
    link = f"https://api.search.nicovideo.jp/api/v2/snapshot/video/contents/search?q={params['q']}&targets={params['targets']}&fields=lengthSeconds,mylistCounter,userId,thumbnailUrl,startTime,contentId,title,viewCounter&filters[viewCounter][gte]={params['min_viewCounter']}&_sort={params['sort']}&_offset=0&_limit={params['limit']}&_context=apiguide"
    return link, errors, params

async def get_user_information(userId):
    link = f'https://www.nicovideo.jp/user/{userId}'
    r = requests.get(link)
    html = r.text
    soup = BeautifulSoup(html, "html.parser")
    username = '非公開ユーザー'
    user_image_url = 'https://deliver.commons.nicovideo.jp/thumbnail/nc3040?size=l'
    if len(soup.find_all('meta')) > 10:
        username = soup.find('meta', {'property': 'profile:username'}).get('content')
        user_image_url = soup.find('meta', {'property': 'og:image'}).get('content')
    return username, user_image_url

async def get_ncnc_information(link, embed):
    url = requests.get(link)
    text = ''
    txt = json.loads(url.text)
    if txt['meta']['status'] == 200:
        for video in txt['data']:
            text = f"https://www.nicovideo.jp/watch/{video['contentId']}"
            embed.add_field(name=f"{video['title']}", value=f"{str(video['viewCounter'])} views, ([{video['contentId']}]({text}))", inline=False)
    else:
        embed.title = "ERROR"
        embed.description = "Something is wrong"
        embed.color = 0xff0000
        embed.add_field(name=f"errorMessage: {txt['meta']['errorMessage']}", value=f"errorCode: {txt['meta']['errorCode']}", inline=False)

async def search_ncnc(ctx):
    embed = discord.Embed(title='hoge', description='fuga', color=0x00ff00)
    args = ctx.content.replace('　', ' ').split(' ')[1:]
    while '' in args:
        args.remove('')
    if len(args) < 1:
        embed.title = "ERROR"
        embed.description = "Something is wrong"
        embed.color = 0xff0000
    else:
        link, errors, params = await create_ncnc_link(args)
        if len(errors) > 0:
            embed.title = "ERROR"
            embed.description = "Something is wrong"
            embed.color = 0xff0000
            for err in errors:
                embed.add_field(name=err['name'], value=err['value'], inline=False)
        else:
            embed.title = f"search_word: {params['q']}"
            embed.description = f"targets: {params['targets']}, min_viewCounter: {params['min_viewCounter']} sort: {params['sort']}, limit: {params['limit']}"
            await get_ncnc_information(link, embed)
            await ctx.channel.send(embed=embed)

async def get_time_str(time):
    h = time // 3600
    m = (time - h * 3600) // 60
    s = time - h * 3600 - m * 60
    text = ''
    if h > 0:
        text += str(h).zfill(2) + ':'
    text += str(m).zfill(2) + ':'
    text += str(s).zfill(2)
    return text

async def get_ncnc_information_with_thumbnail(link, ctx):
    url = requests.get(link)
    txt = json.loads(url.text)
    if txt['meta']['status'] == 200:
        for video in txt['data']:
            text = f"https://www.nicovideo.jp/watch/{video['contentId']}"
            embed = discord.Embed(title=f"{video['title']}", description=f"([{video['contentId']}]({text}))", color=0x00ff00)
            embed.set_thumbnail(url=video['thumbnailUrl'])
            embed.add_field(name="再生時間", value=(await get_time_str(int(video['lengthSeconds']))))
            embed.add_field(name="再生数", value=video['viewCounter'])
            embed.add_field(name="マイリス数", value=video['mylistCounter'])
            username, user_image_url = await get_user_information(video['userId'])
            embed.set_author(name=username, url=f"https://www.nicovideo.jp/user/{video['userId']}", icon_url=user_image_url)
            await ctx.channel.send(embed=embed)
    else:
        embed = discord.Embed(title=f"errorctx: {txt['meta']['errorctx']}", description=f"errorCode: {txt['meta']['errorCode']}", color=0x00ff00)
        await ctx.channel.send(embed=embed)

async def get_one_ncnc_information(link, ctx):
    txt = json.loads(requests.get(link).text)
    if txt['meta']['status'] == 200:
        video = random.choice(txt['data'])
        text = f"https://www.nicovideo.jp/watch/{video['contentId']}"
        embed = discord.Embed(title=f"{video['title']}", description=f"([{video['contentId']}]({text}))", color=0x00ff00)
        embed.set_thumbnail(url=video['thumbnailUrl'])
        embed.add_field(name="再生時間", value=(await get_time_str(int(video['lengthSeconds']))))
        embed.add_field(name="再生数", value=video['viewCounter'])
        embed.add_field(name="マイリス数", value=video['mylistCounter'])
        username, user_image_url = await get_user_information(video['userId'])
        embed.set_author(name=username, url=f"https://www.nicovideo.jp/user/{video['userId']}", icon_url=user_image_url)
        await ctx.channel.send(embed=embed)
        await play_music(text, ctx)
    else:
        embed = discord.Embed(title=f"errorctx: {txt['meta']['errorctx']}", description=f"errorCode: {txt['meta']['errorCode']}", color=0x00ff00)
        await ctx.channel.send(embed=embed)

async def search_ncnc_with_thumbnail(ctx):
    args = ctx.content.replace('　', ' ').split(' ')[1:]
    while '' in args:
        args.remove('')
    if len(args) < 1:
        embed = discord.Embed(title='error invalid argument', description='please input search word', color=0xff0000)
        await ctx.channel.send(embed=embed)
    else:
        link, errors, params = await create_ncnc_link(args)
        if len(errors) > 0:
            embed = discord.Embed(title='ERROR', description='Something is wrong', color=0xff0000)
            for err in errors:
                embed.add_field(name=err['name'], value=err['value'], inline=False)
            await ctx.channel.send(embed=embed)
        else:
            embed = discord.Embed(title=f"search_word: {params['q']}", description=f"targets: {params['targets']}, min_viewCounter: {params['min_viewCounter']} sort: {params['sort']}, limit: {params['limit']}", color=0xffffff)
            await ctx.channel.send(embed=embed)
            await get_ncnc_information_with_thumbnail(link, ctx)


def awaitable_voice_client_play(func, player, loop):
    f = asyncio.Future()
    after = lambda e: loop.call_soon_threadsafe(lambda: f.set_result(e))
    func(player, after=after)
    return f

async def play_music(url, ctx):
    if ctx.author.voice is None:
        await ctx.channel.send("あなたはボイスチャンネルに接続していません。")
        return
    # ボイスチャンネルに接続する
    if ctx.guild.voice_client is None:
        await ctx.author.voice.channel.connect()

    if ctx.guild.voice_client.is_playing():
        ctx.guild.voice_client.stop()
    player, niconico = await NicoNicoDLSource.from_url(url)

    # 再生する
    await awaitable_voice_client_play(ctx.guild.voice_client.play, player, client.loop)
    niconico.close()

    await ctx.guild.voice_client.stop()

async def stop(ctx):
    if ctx.guild.voice_client is None:
        await ctx.channel.send("not connecting now")
        return
    elif not ctx.guild.voice_client.is_playing():
        await ctx.channel.send("not playing now")
        return

    ctx.guild.voice_client.stop()

    await ctx.channel.send("playback has stopped")

async def play(ctx, args):
    if args[1].startswith('sm') or args[1].startswith('nm') or args[1].startswith('so'):
        url = f'https://www.nicovideo.jp/watch/{args[1]}'
        contentId = url[31:]
        link = f'https://api.search.nicovideo.jp/api/v2/snapshot/video/contents/search?q=&targets=tags&fields=lengthSeconds,mylistCounter,userId,thumbnailUrl,startTime,contentId,title,viewCounter&filters[contentId][0]={contentId}&_sort=viewCounter&_offset=0&_limit=1&_context=apiguide'
    elif args[1].startswith('https://www.nicovideo.jp/watch/'):
        url = args[1]
        contentId = url[31:]
        link = f'https://api.search.nicovideo.jp/api/v2/snapshot/video/contents/search?q=&targets=tags&fields=lengthSeconds,mylistCounter,userId,thumbnailUrl,startTime,contentId,title,viewCounter&filters[contentId][0]={contentId}&_sort=viewCounter&_offset=0&_limit=1&_context=apiguide'
    else:
        link, errors, params = await create_ncnc_link(args[1:])
        if len(errors) > 0:
            embed = discord.Embed(title='ERROR', description='Something is wrong', color=0xff0000)
            for err in errors:
                embed.add_field(name=err['name'], value=err['value'], inline=False)
            await ctx.channel.send(embed=embed)
            return
        else:
            embed = discord.Embed(title=f"search_word: {params['q']}", description=f"targets: {params['targets']}, min_viewCounter: {params['min_viewCounter']} sort: {params['sort']}, limit: {params['limit']}", color=0xffffff)
            await ctx.channel.send(embed=embed)
    await get_one_ncnc_information(link, ctx)

@client.event
async def on_ready():
    print('サーバーを起動します。')

@client.event
async def on_message(ctx):
    if ctx.author.bot:
        return
    args = ctx.content.replace('　', ' ').split(' ')
    while '' in args:
        args.remove('')
    is_ncnc = args[0] == '!ncs'
    if is_ncnc and '-t' in args:
        await search_ncnc_with_thumbnail(ctx)
    elif is_ncnc:
        await search_ncnc(ctx)
    elif args[0] == '!ncp' and len(args) >= 2:
        await play(ctx, args)
    elif args[0] == '!ncst':
        await stop(ctx)
    elif args[0] == '!ncq':
        if ctx.guild.voice_client is None:
            await ctx.channel.send("not connecting now")
        else:
            await ctx.guild.voice_client.disconnect()
        

client.run(getenv('DISCORD_BOT_TOKEN'))
