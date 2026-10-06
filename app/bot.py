import json,html,asyncio
from telegram import InlineKeyboardButton,InlineKeyboardMarkup,Update
from telegram.ext import Application,CommandHandler,CallbackQueryHandler,ContextTypes
from app import config
from app.db import init_db,get_article,pending,set_status,queued_articles,fp
from app.fetcher import scan_sources,enrich_image
from app.editor import prepare
from app.poster import make_poster, make_test_poster
from app.reels import make_reel_from_poster
from app.publishers.meta import post_instagram_reel, recent_marker_exists

def kb(aid):
    return InlineKeyboardMarkup([[InlineKeyboardButton("✅ PUBLICAR",callback_data=f"pub:{aid}"),
                                  InlineKeyboardButton("❌ DESCARTAR",callback_data=f"drop:{aid}")]])

async def send_preview(bot,chat_id,a,ai):
    txt=(f"📰 <b>{html.escape(ai['headline'])}</b>\n\nFonte: {html.escape(a['source'])}\n"
         f"{html.escape(ai['caption_instagram'][:1100])}")
    try:
        poster=await asyncio.to_thread(
            make_poster,
            ai["headline"],
            a.get("category","notícia"),
            f"preview_{a['id']}",
            a.get("image_url",""),
            a.get("source","")
        )
        with open(poster,"rb") as f:
            await bot.send_photo(
                chat_id=chat_id,
                photo=f,
                caption=txt,
                parse_mode="HTML",
                reply_markup=kb(a["id"])
            )
        print(f"PREVIEW_IMAGE_OK id={a['id']}", flush=True)
    except Exception as e:
        print(f"PREVIEW_IMAGE_ERROR id={a['id']} error={type(e).__name__}: {e}", flush=True)
        await bot.send_message(chat_id=chat_id,text=txt,parse_mode="HTML",reply_markup=kb(a["id"]))

def _published_score(a):
    from email.utils import parsedate_to_datetime
    from datetime import timezone
    raw=(a.get("published") or "").strip()
    if raw:
        try:
            dt=parsedate_to_datetime(raw)
            if dt.tzinfo is None:
                dt=dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except Exception:
            pass
    return float(a.get("id") or 0)

def _select_for_cycle(rows, limit=3):
    # Breaking/newest items jump ahead. Older queued items remain for next cycles.
    ordered=sorted(rows,key=_published_score,reverse=True)
    chosen=[]
    used_categories=set()

    # First pass: favor variety among the newest items.
    for a in ordered:
        cat=(a.get("category") or "geral").strip().lower()
        if cat not in used_categories:
            chosen.append(a)
            used_categories.add(cat)
            if len(chosen)>=limit:
                return chosen

    # Second pass: fill any remaining slots strictly by freshness.
    chosen_ids={a["id"] for a in chosen}
    for a in ordered:
        if a["id"] not in chosen_ids:
            chosen.append(a)
            if len(chosen)>=limit:
                break
    return chosen

async def scan_job(context: ContextTypes.DEFAULT_TYPE):
    from datetime import datetime, timezone
    from email.utils import parsedate_to_datetime

    def fresh_enough(a):
        raw=(a.get("published") or "").strip()
        if not raw:
            return True
        try:
            dt=parsedate_to_datetime(raw)
            if dt.tzinfo is None:
                dt=dt.replace(tzinfo=timezone.utc)
            age=(datetime.now(timezone.utc)-dt.astimezone(timezone.utc)).total_seconds()/3600
            return age <= config.MAX_ARTICLE_AGE_HOURS
        except Exception:
            return True

    print("SCAN_START", flush=True)
    added=await asyncio.to_thread(scan_sources)
    rows=await asyncio.to_thread(queued_articles,300)
    fresh=[a for a in rows if fresh_enough(a)]
    selected=_select_for_cycle(fresh,config.MAX_POSTS_PER_CYCLE)
    print(f"SCAN_FOUND added={len(added)} queued={len(rows)} fresh={len(fresh)} selected={len(selected)}", flush=True)

    for a in selected:
        aid=a["id"]
        try:
            print(f"ARTICLE_START id={aid}", flush=True)

            print(f"IMAGE_START id={aid}", flush=True)
            a=await asyncio.to_thread(enrich_image,a)
            print(f"IMAGE_DONE id={aid} has_image={bool(a.get('image_url'))}", flush=True)

            print(f"AI_START id={aid}", flush=True)
            ai=await asyncio.to_thread(prepare,a)
            if isinstance(ai, list):
                ai = ai[0] if ai else {}
            if not isinstance(ai, dict):
                ai = {"headline":a["title"].upper(),"caption_instagram":a["title"],"caption_tiktok":a["title"],"short_script":a["title"],"risk":"high","reason":"Formato inesperado da IA","hashtags":["#Rondonia","#ByteCurioso27"]}
            print(f"AI_DONE id={aid}", flush=True)

            from app.db import set_ai
            set_ai(aid,ai)

            if config.META_ENABLED:
                marker="#BC27"+fp(a.get("title",""),a.get("url",""))[:12]
                if await asyncio.to_thread(recent_marker_exists,marker):
                    set_status(aid,"duplicate")
                    print(f"DUPLICATE_SKIP id={aid} marker={marker}", flush=True)
                    continue
                caption=(ai["caption_instagram"]+"\n\n"+marker).strip()

                print(f"POSTER_START id={aid}", flush=True)
                poster=await asyncio.to_thread(make_poster,ai["headline"],a["category"],aid,a.get("image_url",""),a.get("source",""))
                print(f"POSTER_DONE id={aid}", flush=True)

                print(f"REEL_START id={aid}", flush=True)
                reel=await asyncio.to_thread(make_reel_from_poster,poster,aid)
                print(f"REEL_DONE id={aid}", flush=True)

                video_url=f"{config.PUBLIC_BASE_URL}/media/{reel.split('/')[-1]}"
                print(f"PUBLISH_START id={aid} category={a.get('category','')}", flush=True)
                result=await asyncio.to_thread(post_instagram_reel,video_url,caption)
                set_status(aid,"published")
                print(f"PUBLISH_OK id={aid} media_id={result.get('id','')}", flush=True)
                msg=f"✅ Publicado automaticamente em Reels\n{ai['headline']}\nID: {result.get('id','')}"
                if result.get("permalink"):
                    msg+=f"\n🔗 {result['permalink']}"
                await context.bot.send_message(config.TELEGRAM_OWNER_CHAT_ID,msg)
            else:
                set_status(aid,"prepared")
                await send_preview(context.bot,config.TELEGRAM_OWNER_CHAT_ID,a,ai)

        except Exception as e:
            print(f"ARTICLE_ERROR id={aid} error={type(e).__name__}: {e}", flush=True)
            set_status(aid,"review")
            try:
                await context.bot.send_message(config.TELEGRAM_OWNER_CHAT_ID,f"⚠️ Falha ao processar matéria #{aid}: {e}")
            except Exception:
                pass

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
            poster=make_poster(headline,category,aid,a.get("image_url",""),a.get("source",""))
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

async def bot_error_handler(update, context):
    err=context.error
    if err and err.__class__.__name__=="Conflict":
        print("TELEGRAM_POLLING_HANDOFF", flush=True)
        return
    print(f"TELEGRAM_ERROR {type(err).__name__}: {err}", flush=True)

def run():
    init_db()
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_OWNER_CHAT_ID:
        raise SystemExit("Configure TELEGRAM_BOT_TOKEN e TELEGRAM_OWNER_CHAT_ID")
    app=Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    app.add_error_handler(bot_error_handler)
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
