import json,html,asyncio
from telegram import InlineKeyboardButton,InlineKeyboardMarkup,Update
from telegram.ext import Application,CommandHandler,CallbackQueryHandler,ContextTypes
from app import config
from app.db import init_db,get_article,pending,set_status,queued_articles,fp
from app.fetcher import scan_sources,enrich_image
from app.editor import prepare
from app.poster import make_poster,make_test_poster,asset_status
from app.reels import make_reel_from_poster
from app.publishers.meta import post_instagram_reel,recent_marker_exists

def kb(aid):
    return InlineKeyboardMarkup([[InlineKeyboardButton("✅ PUBLICAR",callback_data=f"pub:{aid}"),
                                  InlineKeyboardButton("❌ DESCARTAR",callback_data=f"drop:{aid}")]])

async def send_preview(bot,chat_id,a,ai):
    txt=(f"📰 <b>{html.escape(ai['headline'])}</b>\n\nFonte: {html.escape(a['source'])}\n"
         f"{html.escape(ai['caption_instagram'][:1100])}")
    poster=await asyncio.to_thread(
        make_poster,ai["headline"],a.get("category","notícia"),
        f"preview_{a['id']}",a.get("image_url",""),a.get("source","")
    )
    with open(poster,"rb") as f:
        await bot.send_photo(chat_id=chat_id,photo=f,caption=txt,parse_mode="HTML",reply_markup=kb(a["id"]))
    print(f"PREVIEW_IMAGE_OK id={a['id']}",flush=True)

def _published_score(a):
    from email.utils import parsedate_to_datetime
    from datetime import timezone
    raw=(a.get("published") or "").strip()
    if raw:
        try:
            dt=parsedate_to_datetime(raw)
            if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except Exception:
            pass
    return float(a.get("id") or 0)

def _select_for_cycle(rows,limit):
    ordered=sorted(rows,key=_published_score,reverse=True)
    chosen=[]; used=set()
    for a in ordered:
        cat=(a.get("category") or "geral").strip().lower()
        if cat not in used:
            chosen.append(a); used.add(cat)
            if len(chosen)>=limit: return chosen
    ids={a["id"] for a in chosen}
    for a in ordered:
        if a["id"] not in ids:
            chosen.append(a)
            if len(chosen)>=limit: break
    return chosen

def _fresh_enough(a):
    from datetime import datetime,timezone
    from email.utils import parsedate_to_datetime
    raw=(a.get("published") or "").strip()
    if not raw: return False
    try:
        dt=parsedate_to_datetime(raw)
        if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
        age=(datetime.now(timezone.utc)-dt.astimezone(timezone.utc)).total_seconds()/3600
        return 0 <= age <= config.MAX_ARTICLE_AGE_HOURS
    except Exception:
        return False

async def scan_job(context:ContextTypes.DEFAULT_TYPE):
    print("SCAN_START",flush=True)
    added=await asyncio.to_thread(scan_sources)
    rows=await asyncio.to_thread(queued_articles,300)
    fresh=[a for a in rows if _fresh_enough(a)]
    selected=_select_for_cycle(fresh,config.MAX_POSTS_PER_CYCLE)
    print(f"SCAN_FOUND added={len(added)} queued={len(rows)} fresh={len(fresh)} selected={len(selected)}",flush=True)

    for a in selected:
        aid=a["id"]
        try:
            print(f"ARTICLE_START id={aid}",flush=True)
            a=await asyncio.to_thread(enrich_image,a)
            print(f"IMAGE_DONE id={aid} has_image={bool(a.get('image_url'))}",flush=True)

            ai=await asyncio.to_thread(prepare,a)
            if isinstance(ai,list): ai=ai[0] if ai else {}
            if not isinstance(ai,dict):
                raise ValueError("Resposta da IA inválida")
            from app.db import set_ai
            set_ai(aid,ai)
            print(f"AI_DONE id={aid}",flush=True)

            if not config.META_ENABLED:
                set_status(aid,"prepared")
                await send_preview(context.bot,config.TELEGRAM_OWNER_CHAT_ID,a,ai)
                continue

            marker="#BC27"+fp(a.get("title",""),a.get("url",""))[:12]
            if await asyncio.to_thread(recent_marker_exists,marker):
                set_status(aid,"duplicate")
                print(f"DUPLICATE_SKIP id={aid}",flush=True)
                continue

            poster=await asyncio.to_thread(make_poster,ai["headline"],a["category"],aid,a.get("image_url",""),a.get("source",""))
            reel=await asyncio.to_thread(make_reel_from_poster,poster,aid)
            video_url=f"{config.PUBLIC_BASE_URL}/media/{reel.split('/')[-1]}"
            caption=(ai["caption_instagram"]+"\n\n"+marker).strip()
            result=await asyncio.to_thread(post_instagram_reel,video_url,caption)
            if result.get("status")!="published":
                raise RuntimeError(f"Meta não publicou: {result}")
            set_status(aid,"published")
            print(f"PUBLISH_OK id={aid} media_id={result.get('id','')}",flush=True)
            msg=f"✅ Publicado automaticamente em Reels\n{ai['headline']}"
            if result.get("permalink"): msg+=f"\n🔗 {result['permalink']}"
            await context.bot.send_message(config.TELEGRAM_OWNER_CHAT_ID,msg)
        except Exception as e:
            print(f"ARTICLE_ERROR id={aid} error={type(e).__name__}:{e}",flush=True)
            set_status(aid,"review")
            try:
                await context.bot.send_message(config.TELEGRAM_OWNER_CHAT_ID,f"⚠️ Falha na matéria #{aid}: {e}")
            except Exception:
                pass

async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🗞 Byte Curioso 27 ativo.\n/buscar /testarte /status /pendentes")

async def buscar(update:Update,context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔎 Buscando notícias...")
    await scan_job(context)
    await update.message.reply_text("✅ Busca concluída.")

async def testarte(update:Update,context:ContextTypes.DEFAULT_TYPE):
    poster=await asyncio.to_thread(make_test_poster)
    with open(poster,"rb") as f:
        await update.message.reply_photo(photo=f,caption=f"🎨 Teste visual v2\nMascote: {asset_status().get('avatar_ok')}")
    print("TESTARTE_OK",flush=True)

async def pendentes_cmd(update:Update,context:ContextTypes.DEFAULT_TYPE):
    rows=pending()
    await update.message.reply_text("Sem pendências." if not rows else "\n".join(f"#{r['id']} — {r['title'][:80]}" for r in rows[:15]))

async def testinstagram(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if not config.META_ENABLED:
        await update.message.reply_text("⏸ Instagram continua PAUSADO. O teste visual deve ser feito com /testarte.")
        return
    poster=await asyncio.to_thread(make_test_poster)
    reel=await asyncio.to_thread(make_reel_from_poster,poster,"instagram_test")
    video_url=f"{config.PUBLIC_BASE_URL}/media/{reel.split('/')[-1]}"
    try:
        result=await asyncio.to_thread(post_instagram_reel,video_url,"🧪 Teste Byte Curioso 27. #ByteCurioso27 #Rondonia")
        if result.get("status")!="published":
            raise RuntimeError(str(result))
        msg=f"✅ Teste publicado. ID: {result.get('id','')}"
        if result.get("permalink"): msg+=f"\n🔗 {result['permalink']}"
        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f"❌ Falha no teste: {e}")

async def status(update:Update,context:ContextTypes.DEFAULT_TYPE):
    s=asset_status()
    await update.message.reply_text(
        f"✅ Serviço ativo\nBusca: {config.SCAN_INTERVAL_MINUTES} min\nMeta: {config.META_ENABLED}\n"
        f"TikTok: {config.TIKTOK_ENABLED}\nMascote: {s.get('avatar_ok')}"
    )

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
        return
    if not config.META_ENABLED:
        await q.message.reply_text("⏸ Publicação pausada. Nada foi enviado ao Instagram.")
        return
    try:
        ai=json.loads(a.get("ai_json") or "{}")
        headline=ai.get("headline") or a.get("title") or "Byte Curioso 27"
        caption=ai.get("caption_instagram") or a.get("title") or ""
        poster=await asyncio.to_thread(make_poster,headline,a.get("category") or "notícia",aid,a.get("image_url",""),a.get("source",""))
        reel=await asyncio.to_thread(make_reel_from_poster,poster,aid)
        video_url=f"{config.PUBLIC_BASE_URL}/media/{reel.split('/')[-1]}"
        result=await asyncio.to_thread(post_instagram_reel,video_url,caption)
        if result.get("status")!="published":
            raise RuntimeError(str(result))
        set_status(aid,"published")
        await q.edit_message_reply_markup(reply_markup=None)
        await q.message.reply_text(f"✅ Matéria #{aid} publicada.")
    except Exception as e:
        set_status(aid,"review")
        await q.message.reply_text(f"⚠️ Falha ao publicar #{aid}: {e}")

async def bot_error_handler(update,context):
    err=context.error
    if err and err.__class__.__name__=="Conflict":
        print("TELEGRAM_POLLING_HANDOFF",flush=True)
        return
    print(f"TELEGRAM_ERROR {type(err).__name__}:{err}",flush=True)

def run():
    init_db()
    print(f"BOOT v2 meta={config.META_ENABLED} mascot={asset_status()}",flush=True)
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_OWNER_CHAT_ID:
        raise SystemExit("Configure TELEGRAM_BOT_TOKEN e TELEGRAM_OWNER_CHAT_ID")
    app=Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    app.add_error_handler(bot_error_handler)
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("buscar",buscar))
    app.add_handler(CommandHandler("testarte",testarte))
    app.add_handler(CommandHandler("pendentes",pendentes_cmd))
    app.add_handler(CommandHandler("status",status))
    app.add_handler(CommandHandler("testinstagram",testinstagram))
    app.add_handler(CallbackQueryHandler(callback))
    app.job_queue.run_repeating(scan_job,interval=config.SCAN_INTERVAL_MINUTES*60,first=15)
    app.run_polling(drop_pending_updates=True)

if __name__=="__main__":
    run()
