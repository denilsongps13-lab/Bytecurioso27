from pathlib import Path
import subprocess, re
import imageio_ffmpeg

MEDIA_DIR='/tmp/media'
Path(MEDIA_DIR).mkdir(parents=True,exist_ok=True)

def validate_reel(path):
    reader=imageio_ffmpeg.read_frames(str(path),pix_fmt='rgb24')
    try:
        meta=next(reader)
        if tuple(meta['size'])!=(720,1280) or abs(meta['fps']-24)>0.01:
            raise RuntimeError('REEL_ERROR invalid_dimensions_or_fps')
        count=0
        for frame in reader: count+=1
        if count<140: raise RuntimeError('REEL_ERROR truncated_video')
    finally: reader.close()
    return {'width':720,'height':1280,'fps':24,'frames':count,'bytes':Path(path).stat().st_size}

def make_reel_from_poster(poster_path,article_id,seconds=6):
    safe=re.sub(r'[^A-Za-z0-9_-]','_',str(article_id))
    out=Path(MEDIA_DIR)/f'reel_{safe}.mp4';tmp=out.with_suffix('.tmp.mp4')
    ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
    cmd=[ffmpeg,'-y','-threads','1','-loop','1','-i',str(poster_path),'-t',str(seconds),'-vf','scale=720:1280,format=yuv420p','-r','24','-an','-c:v','libx264','-preset','ultrafast','-threads','1','-filter_threads','1','-pix_fmt','yuv420p','-movflags','+faststart',str(tmp)]
    try:
        subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=90)
        result=validate_reel(tmp);tmp.replace(out)
    except Exception:
        tmp.unlink(missing_ok=True);raise
    print(f'REEL_DONE id={safe} validation={result}',flush=True)
    return str(out)
