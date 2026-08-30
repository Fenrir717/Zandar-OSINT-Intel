"""Adapter transkrip YouTube — closed captions publik via youtube-transcript-api.

Melengkapi adapter komentar YouTube resmi: transkrip (CC) tidak memakai kuota Data
API dan memberi ISI video untuk analisis narasi/sentimen — bukan hanya komentar.
Caption yang tersedia publik; tanpa kredensial.

query = {
    "video_ids": ["abc123", ...],
    "languages": ["id", "en"],   # prioritas bahasa
    "chunk": false,               # true = pecah per segmen; false = satu dokumen/video
}
"""

from collections.abc import Iterator

from workers.adapters.base import BaseAdapter, RawItem


class YouTubeTranscriptAdapter(BaseAdapter):
    platform = "youtube"
    key = "youtube_transcript"
    tier = "free"
    requires_credentials = False
    rate_note = "Tanpa kuota Data API; ambil closed captions publik per video."
    legal_note = "Caption publik. Menghormati ketersediaan/pembatasan per video."

    def collect(self, query: dict) -> Iterator[RawItem]:
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "Adapter transkrip butuh youtube-transcript-api. Pasang: pip install youtube-transcript-api"
            ) from exc

        languages = query.get("languages", ["id", "en"])
        chunk = query.get("chunk", False)
        ytt = YouTubeTranscriptApi()  # API v1.x: instance.fetch()

        for vid in query.get("video_ids", []):
            try:
                fetched = ytt.fetch(vid, languages=languages)
                # FetchedTranscript -> list[{text,start,duration}]
                segments = fetched.to_raw_data() if hasattr(fetched, "to_raw_data") else list(fetched)
            except Exception:  # video tanpa caption / dinonaktifkan — lewati
                continue

            if chunk:
                for i, seg in enumerate(segments):
                    text = (seg.get("text") or "").strip()
                    if not text:
                        continue
                    yield RawItem(
                        platform=self.platform,
                        external_id=f"{vid}:cc:{i}",
                        author=vid,
                        content=text,
                        url=f"https://www.youtube.com/watch?v={vid}&t={int(seg.get('start', 0))}",
                        title=f"Transkrip {vid}",
                        raw=seg,
                    )
            else:
                full = " ".join((s.get("text") or "").strip() for s in segments).strip()
                if not full:
                    continue
                yield RawItem(
                    platform=self.platform,
                    external_id=f"{vid}:transcript",
                    author=vid,
                    content=full,
                    url=f"https://www.youtube.com/watch?v={vid}",
                    title=f"Transkrip {vid}",
                    raw={"video_id": vid, "segments": len(segments)},
                )
