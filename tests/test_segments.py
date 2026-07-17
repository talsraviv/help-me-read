import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from fetch_item import parse_ts, seconds_to_hms, hms_to_seconds, extract_video_id, clean_vtt_to_segments

HUMAN_VTT = """WEBVTT
Kind: captions
Language: en

00:00:06.500 --> 00:00:08.080
>> Thank you so much for being here.

00:00:08.160 --> 00:00:08.600
>> Thank you.

00:02:56.120 --> 00:02:58.540
00:02:56,120 --&gt; 00:02:58,540
"""

AUTO_VTT = """WEBVTT
Kind: captions
Language: en

00:00:06.600 --> 00:00:08.230 align:start position:0%

Hello,<00:00:07.000><c> thank</c><00:00:07.240><c> you.</c>

00:00:08.230 --> 00:00:08.240 align:start position:0%
Hello, thank you.


00:00:08.240 --> 00:00:09.950 align:start position:0%
Hello, thank you.
&gt;&gt; Next<00:00:08.480><c> part.</c>
"""

def test_parse_ts_hms():
    assert parse_ts("00:01:06.500") == 66.5
    assert parse_ts("01:06.500") == 66.5
    assert parse_ts("00:02:58,540") == 178.54

def test_seconds_to_hms():
    assert seconds_to_hms(66) == "1:06"
    assert seconds_to_hms(3666) == "1:01:06"

def test_hms_to_seconds():
    assert hms_to_seconds("1:06") == 66
    assert hms_to_seconds("1:01:06") == 3666

def test_extract_video_id():
    assert extract_video_id("https://www.youtube.com/watch?v=agSRMrhNTf4") == "agSRMrhNTf4"
    assert extract_video_id("https://youtu.be/agSRMrhNTf4?t=10") == "agSRMrhNTf4"

def test_human_segments_keep_timestamps_and_drop_stray_timestamp():
    segs = clean_vtt_to_segments(HUMAN_VTT)
    assert segs[0] == {"start": 6.5, "text": ">> Thank you so much for being here.", "speaker": ">>"}
    assert segs[1]["text"] == ">> Thank you."
    # the escaped stray SRT timestamp must not appear as a segment
    assert all("-->" not in s["text"] for s in segs)
    assert len(segs) == 2

def test_auto_segments_dedupe_rolling_window():
    segs = clean_vtt_to_segments(AUTO_VTT)
    texts = [s["text"] for s in segs]
    assert texts == ["Hello, thank you.", ">> Next part."]
    assert segs[0]["start"] == 6.6
