#!/usr/bin/env python3
"""Text-to-speech via edge-tts (free Microsoft neural voices)."""
import asyncio, edge_tts

VOICE_MAIN = "en-US-AndrewNeural"     # warm, deep male — perfect for meditation
VOICE_SHORT = "en-US-ChristopherNeural"  # slightly brighter for Shorts

async def _speak(text, path, voice, rate, pitch):
    c = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    await c.save(str(path))

def tts(text, path, voice=VOICE_MAIN, rate="-10%", pitch="-2Hz", retries=3):
    for i in range(retries):
        try:
            asyncio.run(_speak(text, path, voice, rate, pitch))
            return path
        except Exception as e:
            if i == retries - 1:
                raise
            import time; time.sleep(5 * (i + 1))
