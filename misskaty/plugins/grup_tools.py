import os
import textwrap
import time
from datetime import datetime, timedelta
from logging import getLogger

from PIL import Image, ImageChops, ImageDraw, ImageFont
from pyrogram import enums, filters
from pyrogram.errors import ChatAdminRequired, MessageTooLong, RPCError
from pyrogram.types import ChatMemberUpdated, InlineKeyboardButton, InlineKeyboardMarkup

from database.users_chats_db import db
from misskaty import BOT_USERNAME, app
from misskaty.core.decorator import asyncify, capture_err
from misskaty.core.decorator.ratelimiter import ratelimiter
from misskaty.helper.http import http
from misskaty.helper.localization import use_chat_lang
from misskaty.vars import COMMAND_HANDLER, SUDO, SUPPORT_CHAT
from utils import temp

LOGGER = getLogger(__name__)


def circle(pfp, size=(215, 215)):
    pfp = pfp.resize(size, Image.ANTIALIAS).convert("RGBA")
    bigsize = (pfp.size[0] * 3, pfp.size[1] * 3)
    mask = Image.new("L", bigsize, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0) + bigsize, fill=255)
    mask = mask.resize(pfp.size, Image.ANTIALIAS)
    mask = ImageChops.darker(mask, pfp.split()[-1])
    pfp.putalpha(mask)
    return pfp


def draw_multiple_line_text(image, text, font, text_start_height):
    """
    From unutbu on [python PIL draw multiline text on image](https://stackoverflow.com/a/7698300/395857)
    """
    draw = ImageDraw.Draw(image)
    image_width, image_height = image.size
    y_text = text_start_height
    lines = textwrap.wrap(text, width=50)
    for line in lines:
        line_width, line_height = font.getsize(line)
        draw.text(
            ((image_width - line_width) / 2, y_text), line, font=font, fill="black"
        )
        y_text += line_height


@asyncify
def welcomepic(pic, user, chat, id, strings):
    background = Image.open("assets/bg.png")  # <- Background Image (Should be PNG)
    background = background.resize((1024, 500), Image.ANTIALIAS)
    pfp = Image.open(pic).convert("RGBA")
    pfp = circle(pfp)
    pfp = pfp.resize(
        (265, 265)
    )  # Resizes the Profilepicture so it fits perfectly in the circle
    font = ImageFont.truetype(
        "assets/Calistoga-Regular.ttf", 37
    )  # <- Text Font of the Member Count. Change the text size for your preference
    member_text = strings("welcpic_msg").format(
        userr=user, id=id
    )  # <- Text under the Profilepicture with the Membercount
    draw_multiple_line_text(background, member_text, font, 395)
    draw_multiple_line_text(background, chat, font, 47)
    ImageDraw.Draw(background).text(
        (530, 460),
        f"Generated by @{BOT_USERNAME}",
        font=ImageFont.truetype("assets/Calistoga-Regular.ttf", 28),
        size=20,
        align="right",
    )
    background.paste(
        pfp, (379, 123), pfp
    )  # Pastes the Profilepicture on the Background Image
    background.save(
        f"downloads/welcome#{id}.png"
    )  # Saves the finished Image in the folder with the filename
    return f"downloads/welcome#{id}.png"


@app.on_chat_member_updated(
    filters.group & filters.chat([-1001128045651, -1001777794636])
)
@use_chat_lang()
async def member_has_joined(c: app, member: ChatMemberUpdated, strings):
    if (
        not member.new_chat_member
        or member.new_chat_member.status in {"banned", "left", "restricted"}
        or member.old_chat_member
    ):
        return
    user = member.new_chat_member.user if member.new_chat_member else member.from_user
    if user.id in SUDO:
        await c.send_message(
            member.chat.id,
            strings("sudo_join_msg"),
        )
        return
    elif user.is_bot:
        return  # ignore bots
    else:
        if (temp.MELCOW).get(f"welcome-{member.chat.id}") is not None:
            try:
                await temp.MELCOW[f"welcome-{member.chat.id}"].delete()
            except:
                pass
        mention = f"<a href='tg://user?id={user.id}'>{user.first_name}</a>"
        joined_date = datetime.fromtimestamp(time.time()).strftime("%Y.%m.%d %H:%M:%S")
        first_name = (
            f"{user.first_name} {user.last_name}" if user.last_name else user.first_name
        )
        id = user.id
        dc = user.dc_id or "Member tanpa PP"
        try:
            pic = await app.download_media(
                user.photo.big_file_id, file_name=f"pp{user.id}.png"
            )
        except AttributeError:
            pic = "assets/profilepic.png"
        try:
            welcomeimg = await welcomepic(
                pic, user.first_name, member.chat.title, user.id, strings
            )
            temp.MELCOW[f"welcome-{member.chat.id}"] = await c.send_photo(
                member.chat.id,
                photo=welcomeimg,
                caption=f"Hai {mention}, Selamat datang digrup {member.chat.title} harap baca rules di pinned message terlebih dahulu.\n\n<b>Nama :<b> <code>{first_name}</code>\n<b>ID :<b> <code>{id}</code>\n<b>DC ID :<b> <code>{dc}</code>\n<b>Tanggal Join :<b> <code>{joined_date}</code>",
            )
        except Exception as e:
            LOGGER.info(e)
        userspammer = ""
        # Combot API Detection
        try:
            apicombot = (
                await http.get(f"https://api.cas.chat/check?user_id={user.id}")
            ).json()
            if apicombot.get("ok") == "true":
                await app.ban_chat_member(
                    member.chat.id, user.id, datetime.now() + timedelta(seconds=30)
                )
                userspammer += strings("combot_msg").format(
                    umention=user.mention, uid=user.id
                )
        except Exception as err:
            LOGGER.error(f"ERROR in Combot API Detection. {err}")
        if userspammer != "":
            await c.send_message(member.chat.id, userspammer)
        try:
            os.remove(f"downloads/welcome#{user.id}.png")
            os.remove(f"downloads/pp{user.id}.png")
        except Exception:
            pass


@app.on_message(filters.new_chat_members & filters.group, group=4)
@use_chat_lang()
async def greet_group(bot, message, strings):
    for u in message.new_chat_members:
        try:
            pic = await app.download_media(
                u.photo.big_file_id, file_name=f"pp{u.id}.png"
            )
        except AttributeError:
            pic = "assets/profilepic.png"
        if (temp.MELCOW).get(f"welcome-{message.chat.id}") is not None:
            try:
                await temp.MELCOW[f"welcome-{message.chat.id}"].delete()
            except:
                pass
        try:
            welcomeimg = await welcomepic(
                pic, u.first_name, message.chat.title, u.id, strings
            )
            temp.MELCOW[f"welcome-{message.chat.id}"] = await app.send_photo(
                message.chat.id,
                photo=welcomeimg,
                caption=strings("capt_welc").format(
                    umention=u.mention, uid=u.id, ttl=message.chat.title
                ),
            )
            userspammer = ""
            # Combot API Detection
            try:
                apicombot = (
                    await http.get(f"https://api.cas.chat/check?user_id={u.id}")
                ).json()
                if apicombot.get("ok") == "true":
                    await app.ban_chat_member(
                        message.chat.id, u.id, datetime.now() + timedelta(seconds=30)
                    )
                    userspammer += strings("combot_msg").format(
                        umention=u.mention, uid=u.id
                    )
            except Exception as err:
                LOGGER.error(f"ERROR in Combot API Detection. {err}")
            if userspammer != "":
                await bot.send_message(message.chat.id, userspammer)
        except Exception as e:
            LOGGER.info(e)
        try:
            os.remove(f"downloads/welcome#{u.id}.png")
            os.remove(f"downloads/pp{u.id}.png")
        except Exception:
            pass


@app.on_message(filters.command("leave") & filters.user(SUDO))
async def leave_a_chat(bot, message):
    if len(message.command) == 1:
        return await message.reply("Give me a chat id")
    chat = message.command[1]
    try:
        chat = int(chat)
    except:
        pass
    try:
        buttons = [
            [InlineKeyboardButton("Support", url=f"https://t.me/{SUPPORT_CHAT}")]
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        await bot.send_message(
            chat_id=chat,
            text="<b>Hai kawan, \nOwner aku bilang saya harus pergi! Jika kamu ingin menambahkan bot ini lagi silahkan kontak owner bot ini.</b>",
            reply_markup=reply_markup,
        )
        await bot.leave_chat(chat)
    except Exception as e:
        await message.reply(f"Error - {e}")
        await bot.leave_chat(chat)


# Not to be used
# @app.on_message(filters.command('invite') & filters.user(SUDO))
async def gen_invite(bot, message):
    if len(message.command) == 1:
        return await message.reply("Give me a chat id")
    chat = message.command[1]
    try:
        chat = int(chat)
    except:
        return await message.reply("Give Me A Valid Chat ID")
    try:
        link = await bot.create_chat_invite_link(chat)
    except ChatAdminRequired:
        return await message.reply(
            "Invite Link Generation Failed, Iam Not Having Sufficient Rights"
        )
    except Exception as e:
        return await message.reply(f"Error {e}")
    await message.reply(f"Here is your Invite Link {link.invite_link}")


@app.on_message(filters.command(["adminlist"], COMMAND_HANDLER))
@capture_err
@ratelimiter
async def adminlist(_, message):
    if message.chat.type == enums.ChatType.PRIVATE:
        return await message.reply("Perintah ini hanya untuk grup")
    try:
        msg = await message.reply_msg(f"Getting admin list in {message.chat.title}..")
        administrators = []
        async for m in app.get_chat_members(
            message.chat.id, filter=enums.ChatMembersFilter.ADMINISTRATORS
        ):
            uname = f"@{m.user.username}" if m.user.username else ""
            administrators.append(f"{m.user.first_name} [{uname}]")

        res = "".join(f"💠 {i}\n" for i in administrators)
        return await msg.edit_msg(
            f"Admin in <b>{message.chat.title}</b> ({message.chat.id}):\n{res}"
        )
    except Exception as e:
        await message.reply(f"ERROR: {str(e)}")


@app.on_message(filters.command(["kickme"], COMMAND_HANDLER))
@capture_err
@ratelimiter
async def kickme(_, message):
    reason = None
    if len(message.text.split()) >= 2:
        reason = message.text.split(None, 1)[1]
    try:
        await message.chat.ban_member(message.from_user.id)
        txt = f"Pengguna {message.from_user.mention} menendang dirinya sendiri. Mungkin dia sedang frustasi 😕"
        txt += f"\n<b>Alasan</b>: {reason}" if reason else "-"
        await message.reply_text(txt)
        await message.chat.unban_member(message.from_user.id)
    except RPCError as ef:
        await message.reply_text(
            f"Sepertinya ada error, silahkan report ke owner saya. \nERROR: {str(ef)}"
        )
    except Exception as err:
        await message.reply(f"ERROR: {err}")


@app.on_message(filters.command("users") & filters.user(SUDO))
async def list_users(bot, message):
    # https://t.me/GetTGLink/4184
    msg = await message.reply("Getting List Of Users")
    users = await db.get_all_users()
    out = "Users Saved In DB Are:\n\n"
    async for user in users:
        out += f"User ID: {user.get('id')} -> {user.get('name')}"
        if user["ban_status"]["is_banned"]:
            out += "( Banned User )"
        out += "\n"
    try:
        await msg.edit_text(out)
    except MessageTooLong:
        with open("users.txt", "w+") as outfile:
            outfile.write(out)
        await message.reply_document("users.txt", caption="List Of Users")
        await msg.delete_msg()


@app.on_message(filters.command("chats") & filters.user(SUDO))
async def list_chats(bot, message):
    msg = await message.reply("Getting List Of chats")
    chats = await db.get_all_chats()
    out = "Chats Saved In DB Are:\n\n"
    async for chat in chats:
        out += f"Title: {chat.get('title')} ({chat.get('id')}) "
        if chat["chat_status"]["is_disabled"]:
            out += "( Disabled Chat )"
        out += "\n"
    try:
        await msg.edit_text(out)
    except MessageTooLong:
        with open("chats.txt", "w+") as outfile:
            outfile.write(out)
        await message.reply_document("chats.txt", caption="List Of Chats")
        await msg.delete_msg()
