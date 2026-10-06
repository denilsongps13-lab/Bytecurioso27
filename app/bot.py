import json,html,asyncio,random
from telegram import InlineKeyboardButton,InlineKeyboardMarkup,Update
from telegram.ext import Application,CommandHandler,CallbackQueryHandler,ContextTypes
from app import config
from app.db import init_db,get_article,pending,set_status,queued_articles,fp,claim_article
from app.fetcher import scan_sources,enrich_image,valid_story,classify_category
from app.editor import prepare,public_title,finish_caption
from app.poster import make_poster,make_test_poster,asset_status
from app.reels import make_reel_from_poster
from app.publishers.meta import post_instagram_image,post_instagram_reel,recent_marker_exists,check_instagram_connection,safe_error

SCAN_LOCK=asyncio.Lock()

def owner_only(handler):
    async def checked(update,context):
        if str(update.effective_chat.id)!=str(config.TELEGRAM_OWNER_CHAT_ID):
            return
        return await handler(update,context)
    return checked

def kb(aid):
    return InlineKeyboardMarkup([[InlineKeyboardButton("✅ PUBLICAR",callback_data=f"pub:{aid}"),
                                  InlineKeyboardButton("❌ DESCARTAR",callback_data=f"drop:{aid}")]])

async def send_preview(bot,chat_id,a,ai):
    txt=f"📰 <b>{html.escape(public_title(a))}</b>\n\nLegenda completa enviada abaixo."
    poster=await asyncio.to_thread(
        make_poster,ai["headline"],a.get("category","notícia"),
        f"preview_{a['id']}",a.get("image_url",""),a.get("source","")
    )
    with open(poster,"rb") as f:
        await bot.send_photo(chat_id=chat_id,photo=f,caption=txt,parse_mode="HTML",reply_markup=kb(a["id"]))
    caption=finish_caption(a,ai['caption_instagram'])
    await bot.send_message(chat_id=chat_id,text=caption,reply_markup=kb(a['id']),disable_web_page_preview=True)
    print(f"PREVIEW_CAPTION_OK id={a['id']} chars={len(caption)}",flush=True)
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
    pool=sorted(rows,key=_published_score,reverse=True)[:10]
    if not pool:
        return []
    chosen=[pool[0]]
    used={(pool[0].get("category") or "geral").strip().lower()}
    diverse=[x for x in pool[1:] if (x.get("category") or "geral").strip().lower() not in used]
    random.shuffle(diverse)
    for x in diverse:
        if len(chosen)>=limit:
            break
        chosen.append(x)
        used.add((x.get("category") or "geral").strip().lower())
    if len(chosen)<limit:
        selected_ids={x["id"] for x in chosen}
        rest=[x for x in pool[1:] if x["id"] not in selected_ids]
        random.shuffle(rest)
        chosen.extend(rest[:max(0,limit-len(chosen))])
    print(f"SELECTION_POOL pool={len(pool)} chosen={[(x.get('id'),x.get('category')) for x in chosen]}",flush=True)
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
    if SCAN_LOCK.locked():
        print('SCAN_SKIP already_running=True',flush=True)
        return
    async with SCAN_LOCK:
        await _scan_job(context)

async def _scan_job(context):
    print("SCAN_START",flush=True)
    added=await asyncio.to_thread(scan_sources)
    rows=await asyncio.to_thread(queued_articles,300)
    fresh=[a for a in rows if _fresh_enough(a) and valid_story(a)]
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
            # Artwork uses only the source headline; AI must not introduce facts.
            ai['headline']=a['title']
            ai.setdefault('caption_instagram',a['title'])
            from app.db import set_ai
            set_ai(aid,ai)
            print(f"AI_DONE id={aid}",flush=True)

            if not (config.META_ENABLED and config.AUTO_PUBLISH_LOW_RISK and ai.get('risk')=='low'):
                set_status(aid,"prepared")
                await send_preview(context.bot,config.TELEGRAM_OWNER_CHAT_ID,a,ai)
                continue

            marker="#BC27"+fp(a.get("title",""),a.get("url",""))[:12]
            if await asyncio.to_thread(recent_marker_exists,marker):
                set_status(aid,"duplicate")
                print(f"DUPLICATE_SKIP id={aid}",flush=True)
                continue

            if not await asyncio.to_thread(claim_article,aid):
                print(f'DUPLICATE_CLAIM_SKIP id={aid}',flush=True)
                continue
            poster=await asyncio.to_thread(make_poster,ai["headline"],a["category"],aid,a.get("image_url",""),a.get("source",""))
            image_url=f"{config.PUBLIC_BASE_URL}/media/{poster.split('/')[-1]}"
            caption=(finish_caption(a,ai["caption_instagram"])+"\n\n"+marker).strip()
            result=await asyncio.to_thread(post_instagram_image,image_url,caption)
            if result.get("status")!="published":
                raise RuntimeError(f"Meta não publicou: {result}")
            set_status(aid,"published")
            print(f"PUBLISH_OK id={aid} media_id={result.get('id','')} type=feed_image",flush=True)
            msg=f"✅ Publicado automaticamente no Feed\n{ai['headline']}"
            if result.get("permalink"): msg+=f"\n🔗 {result['permalink']}"
            await context.bot.send_message(config.TELEGRAM_OWNER_CHAT_ID,msg)
        except Exception as e:
            print(f"ARTICLE_ERROR id={aid} error={type(e).__name__}:{safe_error(e)}",flush=True)
            set_status(aid,"review")
            try:
                await context.bot.send_message(config.TELEGRAM_OWNER_CHAT_ID,f"⚠️ Falha na matéria #{aid}: {safe_error(e)}")
            except Exception:
                pass


async def startup_selftest(context:ContextTypes.DEFAULT_TYPE):
    try:
        poster=await asyncio.to_thread(make_test_poster)
        reel=await asyncio.to_thread(make_reel_from_poster,poster,"selftest_v3")
        size=__import__("os").path.getsize(reel)
        print(f"REEL_SELFTEST_OK bytes={size}",flush=True)
    except Exception as e:
        print(f"REEL_SELFTEST_ERROR {type(e).__name__}:{safe_error(e)}",flush=True)
    try:
        meta=await asyncio.to_thread(check_instagram_connection)
        print(f"META_CONNECTION_CHECK {meta}",flush=True)
    except Exception as e:
        print(f"META_CONNECTION_ERROR {type(e).__name__}:{safe_error(e)}",flush=True)

async def visual_audit(context):
    async with SCAN_LOCK:
        await _visual_audit(context)

async def _visual_audit(context):
    if config.META_ENABLED:
        raise RuntimeError('AUDIT_ERROR publishing_must_be_disabled')
    from app.poster import category_key
    from app.db import set_ai
    from pathlib import Path
    await asyncio.to_thread(scan_sources)
    rows=await asyncio.to_thread(queued_articles,500)
    rows+=await asyncio.to_thread(pending,500)
    fresh=sorted([a for a in rows if _fresh_enough(a) and valid_story(a)],key=_published_score,reverse=True)
    for a in fresh:
        a['category']=classify_category(a['title'],a['category'])
    groups=[{'saude'},{'economia','tecnologia','ia'},{'eleicoes','politica','cidades'}]
    outputs=[]
    for group in groups:
        a=next((a for a in fresh if category_key(a.get('category')) in group),None)
        if not a:
            print(f'VISUAL_AUDIT_MISSING category={sorted(group)}',flush=True)
            continue
        a=await asyncio.to_thread(enrich_image,a)
        ai=await asyncio.to_thread(prepare,a)
        ai['headline']=a['title'];ai.setdefault('caption_instagram',a['title'])
        await asyncio.to_thread(set_ai,a['id'],ai)
        await send_preview(context.bot,config.TELEGRAM_OWNER_CHAT_ID,a,ai)
        path=await asyncio.to_thread(make_poster,ai['headline'],a['category'],f'audit_{a["id"]}',a.get('image_url',''),a['source'])
        outputs.append({'id':a['id'],'headline':a['title'],'source':a['source'],'category':a['category'],'url':a['url'],'published':a['published'],'image':Path(path).name})
    if outputs:
        reel=await asyncio.to_thread(make_reel_from_poster,str(Path('/tmp/media')/outputs[0]['image']),'visual_audit')
        with open(reel,'rb') as video:
            await context.bot.send_video(chat_id=config.TELEGRAM_OWNER_CHAT_ID,video=video,caption='Reel de teste: 720×1280, 24 fps, 6 segundos. Não publicado no Instagram.')
    print('VISUAL_AUDIT_MANIFEST '+json.dumps(outputs,ensure_ascii=False),flush=True)
    Path('/tmp/media/audit.json').write_text(json.dumps(outputs,ensure_ascii=False),encoding='utf-8')
    print(f'VISUAL_AUDIT_DONE previews={len(outputs)} publishing=False',flush=True)

async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🗞 Byte Curioso 27 ativo.\n/buscar /testarte /status /pendentes")

async def buscar(update:Update,context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔎 Buscando notícias...")
    await scan_job(context)
    await update.message.reply_text("✅ Busca concluída.")

async def testarte(update:Update,context:ContextTypes.DEFAULT_TYPE):
    poster=await asyncio.to_thread(make_test_poster)
    with open(poster,"rb") as f:
        await update.message.reply_photo(photo=f,caption=f"🎨 Teste visual v3\nMascote: {asset_status().get('avatar_ok')}")
    print("TESTARTE_OK",flush=True)

async def pendentes_cmd(update:Update,context:ContextTypes.DEFAULT_TYPE):
    rows=pending()
    await update.message.reply_text("Sem pendências." if not rows else "\n".join(f"#{r['id']} — {r['title'][:80]}" for r in rows[:15]))

async def testinstagram(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if not config.META_ENABLED:
        await update.message.reply_text("⏸ Instagram continua PAUSADO. O teste visual deve ser feito com /testarte.")
        return
    poster=await asyncio.to_thread(make_test_poster)
    image_url=f"{config.PUBLIC_BASE_URL}/media/{poster.split('/')[-1]}"
    try:
        result=await asyncio.to_thread(post_instagram_image,image_url,"🧪 Teste Byte Curioso 27. #ByteCurioso27 #Rondonia")
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
    if action=="pub" and not (valid_story(a) and _fresh_enough(a)):
        await q.message.reply_text("Matéria fora dos critérios de fonte, título ou prazo. Publicação bloqueada.")
        return
    if action=="drop":
        set_status(aid,"discarded")
        await q.edit_message_reply_markup(reply_markup=None)
        await q.message.reply_text(f"❌ Matéria #{aid} descartada.")
        return
    if not config.META_ENABLED:
        await q.message.reply_text("⏸ Publicação pausada. Nada foi enviado ao Instagram.")
        return
    try:
        marker='#BC27'+fp(a.get('title',''),a.get('url',''))[:12]
        if a.get('status')=='published' or await asyncio.to_thread(recent_marker_exists,marker):
            await q.message.reply_text('Esta notícia já foi publicada.')
            return
        if not await asyncio.to_thread(claim_article,aid,a.get('status')):
            await q.message.reply_text('Esta notícia já está em processamento.')
            return
        ai=json.loads(a.get("ai_json") or "{}")
        headline=a.get("title") or "Byte Curioso 27"
        caption=finish_caption(a,ai.get("caption_instagram") or a.get("title") or "")
        poster=await asyncio.to_thread(make_poster,headline,a.get("category") or "notícia",aid,a.get("image_url",""),a.get("source",""))
        image_url=f"{config.PUBLIC_BASE_URL}/media/{poster.split('/')[-1]}"
        result=await asyncio.to_thread(post_instagram_image,image_url,caption+"\n\n"+marker)
        if result.get("status")!="published":
            raise RuntimeError(str(result))
        set_status(aid,"published")
        await q.edit_message_reply_markup(reply_markup=None)
        await q.message.reply_text(f"✅ Matéria #{aid} publicada no Feed.")
    except Exception as e:
        set_status(aid,"review")
        await q.message.reply_text(f"⚠️ Falha ao publicar #{aid}: {safe_error(e)}")

async def bot_error_handler(update,context):
    err=context.error
    if err and err.__class__.__name__=="Conflict":
        print("TELEGRAM_POLLING_HANDOFF",flush=True)
        return
    print(f"TELEGRAM_ERROR {type(err).__name__}:{safe_error(err)}",flush=True)

def run():
    init_db()
    print(f"BOOT v3 meta={config.META_ENABLED} mascot={asset_status()}",flush=True)
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_OWNER_CHAT_ID:
        raise SystemExit("Configure TELEGRAM_BOT_TOKEN e TELEGRAM_OWNER_CHAT_ID")
    app=Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    app.add_error_handler(bot_error_handler)
    app.add_handler(CommandHandler("start",owner_only(start)))
    app.add_handler(CommandHandler("buscar",owner_only(buscar)))
    app.add_handler(CommandHandler("testarte",owner_only(testarte)))
    app.add_handler(CommandHandler("pendentes",owner_only(pendentes_cmd)))
    app.add_handler(CommandHandler("status",owner_only(status)))
    app.add_handler(CommandHandler("testinstagram",owner_only(testinstagram)))
    app.add_handler(CallbackQueryHandler(owner_only(callback)))
    app.job_queue.run_once(startup_selftest,when=5)
    if config.VISUAL_AUDIT_PREVIEWS:
        app.job_queue.run_once(visual_audit,when=15)
    app.job_queue.run_repeating(scan_job,interval=config.SCAN_INTERVAL_MINUTES*60,first=120)
    app.run_polling(drop_pending_updates=True)

if __name__=="__main__":
    run()

