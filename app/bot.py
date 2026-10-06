import json,html,asyncio
from telegram import InlineKeyboardButton,InlineKeyboardMarkup,Update
from telegram.ext import Application,CommandHandler,CallbackQueryHandler,ContextTypes
from app import config
from app.db import init_db,get_article,pending,set_status
from app.fetcher import scan_sources
from app.editor import prepare
from app.poster import make_poster, make_test_poster
from app.reels import make_reel_from_poster
from app.publishers.meta import post_instagram_reel

def kb(aid):
    return InlineKeyboardMarkup([[InlineKeyboardButton("✅ PUBLICAR",callback_data=f"pub:{aid}"),
                                  InlineKeyboardButton("❌ DESCARTAR",callback_data=f"drop:{aid}")]])

async def send_preview(bot,chat_id,a,ai):
    txt=(f"📰 <b>{html.escape(ai['headline'])}</b>\n\nFonte: {html.escape(a['source'])}\n"
         f"Risco: <b>{ai['risk'].upper()}</b>\nMotivo: {html.escape(ai.get('reason',''))}\n\n"
         f"{html.escape(ai['caption_instagram'][:1500])}")
    await bot.send_message(chat_id=chat_id,text=txt,parse_mode="HTML",reply_markup=kb(a["id"]))

async def scan_job(context: ContextTypes.DEFAULT_TYPE):
    rows=await asyncio.to_thread(scan_sources)
    for a in rows[:config.MAX_POSTS_PER_CYCLE]:
        ai=await asyncio.to_thread(prepare,a)
        if isinstance(ai, list):
            ai = ai[0] if ai else {}
        if not isinstance(ai, dict):
            ai = {"headline":a["title"].upper(),"caption_instagram":a["title"],"caption_tiktok":a["title"],"short_script":a["title"],"risk":"high","reason":"Formato inesperado da IA","hashtags":["#Rondonia","#ByteCurioso27"]}
        from app.db import set_ai
        set_ai(a["id"],ai)
        if ai.get("risk")=="low" and config.AUTO_PUBLISH_LOW_RISK and config.META_ENABLED:
            poster=make_poster(ai["headline"],a["category"],a["id"],a.get("image_url",""))
            reel=make_reel_from_poster(poster,a["id"])
            video_url=f"{config.PUBLIC_BASE_URL}/media/{reel.split('/')[-1]}"
            try:
                result=await asyncio.to_thread(post_instagram_reel,video_url,ai["caption_instagram"])
                set_status(a["id"],"published")
                await context.bot.send_message(config.TELEGRAM_OWNER_CHAT_ID,f"✅ Publicado no Instagram\n{ai['headline']}\nID: {result.get('id','')}")
            except Exception as e:
                set_status(a["id"],"review")
                await context.bot.send_message(config.TELEGRAM_OWNER_CHAT_ID,f"⚠️ Falha ao publicar automaticamente: {e}")
                await send_preview(context.bot,config.TELEGRAM_OWNER_CHAT_ID,a,ai)
        else:
            set_status(a["id"],"review" if ai.get("risk")=="high" else "prepared")
            await send_preview(context.bot,config.TELEGRAM_OWNER_CHAT_ID,a,ai)

async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🗞 Byte Curioso 27 News Bot ativo.\n/buscar /pendentes /status")

async def buscar(update:Update,context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔎 Buscando notícias de Rondônia...")
    await scan_job(context)
    await update.message.reply_text("✅ Busca concluída.")

async def pendentes_cmd(update:Update,context:ContextTypes.DEFAULT_TYPE):
    rows=pending()
    await update.message.reply_text("Sem pendências." if not rows else "\n".join(f"#{r['id']} — {r['title'][:80]}" for r in rows[:15]))

async def testinstagram(update:Update,context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🧪 Testando publicação no Instagram...")
    poster=make_test_poster()
    reel=make_reel_from_poster(poster,"instagram_test")
    video_url=f"{config.PUBLIC_BASE_URL}/media/{reel.split('/')[-1]}"
    try:
        result=await asyncio.to_thread(post_instagram_reel,video_url,"🧪 Teste automático do Byte Curioso 27 em Reels. #ByteCurioso27 #Rondonia")
        link=result.get("permalink","")
        msg=f"✅ Teste publicado no Instagram. ID: {result.get('id','')}"
        if link:
            msg += f"\n🔗 {link}"
        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f"❌ Falha no teste do Instagram: {e}")

async def status(update:Update,context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"✅ Ativo\nBusca: {config.SCAN_INTERVAL_MINUTES} min\nMeta: {config.META_ENABLED}\nTikTok: {config.TIKTOK_ENABLED}")

async def callback(update:Update,context:ContextTypes.DEFAULT_TYPE):
    q=update.callback_query
    await q.answer()
    action,sid=q.data.split(":")
    aid=int(sid)
    a=get_article(aid)
    if not a: return
    if action=="drop":
        set_status(aid,"discarded")
        await q.edit_message_reply_markup(reply_markup=None)
        await q.message.reply_text(f"❌ Matéria #{aid} descartada.")
    else:
        try:
            ai=json.loads(a.get("ai_json") or "{}") if isinstance(a,dict) else {}
        except Exception:
            ai={}
        headline=ai.get("headline") or a.get("title") or "Byte Curioso 27"
        category=a.get("category") or "notícia"
        caption=ai.get("caption_instagram") or a.get("title") or ""
        try:
            poster=make_poster(headline,category,aid,a.get("image_url",""))
            reel=make_reel_from_poster(poster,aid)
            video_url=f"{config.PUBLIC_BASE_URL}/media/{reel.split('/')[-1]}"
            result=await asyncio.to_thread(post_instagram_reel,video_url,caption)
            set_status(aid,"published")
            await q.edit_message_reply_markup(reply_markup=None)
            msg=f"✅ Matéria #{aid} publicada em Reels."
            if result.get("permalink"):
                msg+=f"\n🔗 {result['permalink']}"
            await q.message.reply_text(msg)
        except Exception as e:
            set_status(aid,"review")
            await q.message.reply_text(f"⚠️ Falha ao publicar a matéria #{aid} em Reels: {e}")

def run():
    init_db()
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_OWNER_CHAT_ID:
        raise SystemExit("Configure TELEGRAM_BOT_TOKEN e TELEGRAM_OWNER_CHAT_ID")
    app=Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("buscar",buscar))
    app.add_handler(CommandHandler("pendentes",pendentes_cmd))
    app.add_handler(CommandHandler("status",status))
    app.add_handler(CommandHandler("testinstagram",testinstagram))
    app.add_handler(CallbackQueryHandler(callback))
    app.job_queue.run_repeating(scan_job,interval=config.SCAN_INTERVAL_MINUTES*60,first=10)
    app.run_polling(drop_pending_updates=True)

if __name__=="__main__":
    run()
