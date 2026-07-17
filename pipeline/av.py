#!/usr/bin/env python3
"""FFmpeg helpers: audio assembly, Ken Burns segments, concat, music mix."""
import subprocess, json, pathlib

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{' '.join(map(str, cmd))}\n{r.stderr[-3000:]}")
    return r

def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return float(r.stdout.strip())

def combine_audio(parts, out_path, tail_silence=0.8):
    """parts: list of (audio_path | None, gap_seconds_after). None path = pure silence of gap length."""
    inputs, filters, labels = [], [], []
    idx = 0
    for p, gap in parts:
        if p is not None:
            inputs += ["-i", str(p)]
            filters.append(f"[{idx}:a]aresample=44100,aformat=channel_layouts=mono[a{idx}]")
            labels.append(f"[a{idx}]")
            idx += 1
        if gap and gap > 0:
            filters.append(f"anullsrc=r=44100:cl=mono,atrim=0:{gap}[s{len(labels)}]")
            labels.append(f"[s{len(labels)}]")
    if tail_silence > 0:
        filters.append(f"anullsrc=r=44100:cl=mono,atrim=0:{tail_silence}[tail]")
        labels.append("[tail]")
    fc = ";".join(filters) + ";" + "".join(labels) + f"concat=n={len(labels)}:v=0:a=1[out]"
    run(["ffmpeg", "-y", *inputs, "-filter_complex", fc, "-map", "[out]",
         "-c:a", "aac", "-b:a", "160k", str(out_path)])
    return out_path

def kenburns_segment(bg, card_png, audio, out_path, w, h, fps=24, zoom_total=0.10, direction=1):
    """Still image -> slow zoom video with text card overlay + narration audio."""
    dur = duration(audio)
    frames = max(int(dur * fps) + 1, fps)
    if direction > 0:
        z = f"1+{zoom_total}*on/{frames}"
    else:
        z = f"{1+zoom_total}-{zoom_total}*on/{frames}"
    vf = (f"[0:v]scale={w*2}:{h*2}:force_original_aspect_ratio=increase,crop={w*2}:{h*2},"
          f"zoompan=z='{z}':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2':d={frames}:s={w}x{h}:fps={fps}[bg];"
          f"[bg][1:v]overlay=0:0,fade=t=in:st=0:d=0.6,fade=t=out:st={max(dur-0.6,0):.2f}:d=0.6,format=yuv420p[v]")
    af = f"afade=t=in:st=0:d=0.15,afade=t=out:st={max(dur-0.25,0):.2f}:d=0.25"
    run(["ffmpeg", "-y", "-i", str(bg), "-i", str(card_png), "-i", str(audio),
         "-filter_complex", vf, "-map", "[v]", "-map", "2:a", "-af", af,
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
         "-c:a", "aac", "-b:a", "160k", "-t", f"{dur:.3f}", "-r", str(fps), str(out_path)])
    return out_path

def concat_segments(segment_paths, out_path, workdir):
    lst = pathlib.Path(workdir) / "concat.txt"
    lst.write_text("\n".join(f"file '{p}'" for p in segment_paths))
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
         "-c", "copy", str(out_path)])
    return out_path

def _seamless_music(music, needed_dur, workdir):
    """Extend music to needed_dur with 4s crossfades at loop points (no abrupt restarts)."""
    src_dur = duration(music)
    if src_dur >= needed_dur:
        return music
    import math
    xf = 4.0
    n = math.ceil((needed_dur - src_dur) / (src_dur - xf)) + 1
    inputs, chain = [], ""
    for i in range(n):
        inputs += ["-i", str(music)]
    prev = "[0:a]"
    for i in range(1, n):
        outl = f"[x{i}]" if i < n - 1 else "[out]"
        chain += f"{prev}[{i}:a]acrossfade=d={xf}:c1=tri:c2=tri{outl};"
        prev = f"[x{i}]"
    out = pathlib.Path(workdir) / "music_loop.m4a"
    run(["ffmpeg", "-y", *inputs, "-filter_complex", chain.rstrip(";"),
         "-map", "[out]", "-c:a", "aac", "-b:a", "160k", "-t", f"{needed_dur:.2f}", str(out)])
    return out

def mix_music(video_in, music, out_path, music_vol=0.14):
    dur = duration(video_in)
    music = _seamless_music(music, dur + 5, pathlib.Path(out_path).parent)
    run(["ffmpeg", "-y", "-i", str(video_in), "-stream_loop", "-1", "-i", str(music),
         "-filter_complex",
         f"[1:a]volume={music_vol},afade=t=in:st=0:d=2,afade=t=out:st={max(dur-3,0):.2f}:d=3[m];"
         f"[0:a][m]amix=inputs=2:duration=first:dropout_transition=3,dynaudnorm=f=300:g=15[a]",
         "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
         "-t", f"{dur:.3f}", str(out_path)])
    return out_path
