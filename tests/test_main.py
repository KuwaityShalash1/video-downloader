"""Unit tests for the pure helpers in main.py (no network, no ffmpeg needed)."""

from __future__ import annotations

from pathlib import Path

import pytest

import main


# ── Formatting helpers ───────────────────────────────────────────────────────
@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (None, ""),
        (0, ""),
        (5, "00:05"),
        (59, "00:59"),
        (65, "01:05"),
        (3600, "01:00:00"),
        (3725, "01:02:05"),
        (86400, "24:00:00"),
    ],
)
def test_format_duration(seconds, expected):
    assert main._format_duration(seconds) == expected


@pytest.mark.parametrize(
    ("size", "expected"),
    [
        (None, "?"),
        (0, "?"),
        (512, "512 B"),
        (1024, "1.00 KiB"),
        (1536, "1.50 KiB"),
        (1024**2, "1.00 MiB"),
        (3 * 1024**3, "3.00 GiB"),
    ],
)
def test_format_bytes(size, expected):
    assert main._format_bytes(size) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("", None),
        ("best", None),
        ("0", None),
        ("1080", 1080),
        ("1080p", 1080),
        ("720P", 720),
        ("2160", 2160),
        ("abc", None),
        ("1080p60", None),
        (480, 480),
    ],
)
def test_parse_height(value, expected):
    assert main.parse_height(value) == expected


# ── URL handling ────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://youtu.be/abc123", "https://youtu.be/abc123"),
        ('  "https://example.com/watch?v=1"  ', "https://example.com/watch?v=1"),
        ("ftp://example.com/x", None),
        ("youtube.com/watch?v=1", None),
        ("not a url", None),
        ("", None),
        (None, None),
        ("https://localhost/video", None),
    ],
)
def test_normalize_url(raw, expected):
    assert main.normalize_url(raw) == expected


def test_analyze_url_single_video():
    info = main.analyze_url("https://www.youtube.com/watch?v=abc123")
    assert info.has_playlist is False
    assert info.has_video is True
    assert info.url == "https://www.youtube.com/watch?v=abc123"


def test_analyze_url_video_inside_playlist_strips_playlist_params():
    info = main.analyze_url(
        "https://www.youtube.com/watch?v=abc123&list=PL123&index=4&start_radio=1"
    )
    assert info.has_playlist is True
    assert info.has_video is True
    assert "list=" not in info.url
    assert "index=" not in info.url
    assert "start_radio" not in info.url
    assert "v=abc123" in info.url


def test_analyze_url_pure_playlist():
    info = main.analyze_url("https://www.youtube.com/playlist?list=PL123")
    assert info.has_playlist is True
    assert info.has_video is False


def test_analyze_url_short_link():
    info = main.analyze_url("https://youtu.be/abc123")
    assert info.has_video is True
    assert info.has_playlist is False


@pytest.mark.parametrize(
    ("url", "flag", "interactive", "expected_url", "expected_noplaylist"),
    [
        # Plain video: untouched.
        (
            "https://www.youtube.com/watch?v=abc",
            None,
            True,
            "https://www.youtube.com/watch?v=abc",
            True,
        ),
        # Video inside a playlist with --playlist.
        (
            "https://www.youtube.com/watch?v=abc&list=PL1",
            True,
            False,
            "https://www.youtube.com/watch?v=abc&list=PL1",
            False,
        ),
        # Video inside a playlist with --no-playlist.
        (
            "https://www.youtube.com/watch?v=abc&list=PL1",
            False,
            False,
            "https://www.youtube.com/watch?v=abc",
            True,
        ),
        # Non-interactive default for a video+playlist link: single video.
        (
            "https://www.youtube.com/watch?v=abc&list=PL1",
            None,
            False,
            "https://www.youtube.com/watch?v=abc",
            True,
        ),
        # Pure playlist cannot be narrowed down to one video.
        (
            "https://www.youtube.com/playlist?list=PL1",
            None,
            False,
            "https://www.youtube.com/playlist?list=PL1",
            False,
        ),
    ],
)
def test_resolve_target(url, flag, interactive, expected_url, expected_noplaylist):
    target, noplaylist = main.resolve_target(url, flag, interactive)
    assert target == expected_url
    assert noplaylist is expected_noplaylist


# ── Format selection ────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    ("mode", "height", "expected"),
    [
        ("video", None, "bestvideo+bestaudio/best"),
        ("video", 1080, "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best"),
        ("video-only", None, "bestvideo/best"),
        ("video-only", 720, "bestvideo[height<=720]"),
        ("audio", None, "bestaudio/best"),
        ("audio", 1080, "bestaudio/best"),
    ],
)
def test_build_format_selector(mode, height, expected):
    assert main.build_format_selector(mode, height) == expected


def test_build_audio_postprocessors_mp3():
    processors = main.build_audio_postprocessors("mp3", "320")
    keys = [processor["key"] for processor in processors]
    assert keys[0] == "FFmpegExtractAudio"
    assert processors[0]["preferredcodec"] == "mp3"
    assert processors[0]["preferredquality"] == "320"
    assert "EmbedThumbnail" in keys
    assert "FFmpegMetadata" in keys


def test_build_audio_postprocessors_original_keeps_source_stream():
    keys = [processor["key"] for processor in main.build_audio_postprocessors("original", "320")]
    assert "FFmpegExtractAudio" not in keys
    assert "EmbedThumbnail" in keys


def test_build_outtmpl_single_and_playlist(tmp_path: Path):
    single = main.build_outtmpl(tmp_path, playlist=False)
    assert single.endswith("%(title).120s.%(ext)s")
    assert "playlist" not in single

    playlist = main.build_outtmpl(tmp_path, playlist=True)
    assert "playlist_title" in playlist
    assert "playlist_index" in playlist


# ── Metadata helpers ────────────────────────────────────────────────────────
def test_available_heights_filters_and_sorts():
    info = {
        "formats": [
            {"height": 720, "vcodec": "avc1"},
            {"height": 1080, "vcodec": "avc1"},
            {"height": 1080, "vcodec": "vp9"},
            {"height": None, "vcodec": "avc1"},
            {"height": 144, "vcodec": "none"},
            {"acodec": "opus", "vcodec": "none"},
        ]
    }
    assert main._available_heights(info) == [1080, 720]


def test_available_heights_empty():
    assert main._available_heights({}) == []


def test_estimate_size_combines_video_and_audio():
    info = {
        "formats": [
            {"height": 1080, "vcodec": "avc1", "filesize": 50 * 1024**2},
            {"height": 720, "vcodec": "avc1", "filesize": 20 * 1024**2},
            {"acodec": "opus", "vcodec": "none", "filesize": 5 * 1024**2, "abr": 128},
        ]
    }
    assert main.estimate_size(info, "video") == 55 * 1024**2
    assert main.estimate_size(info, "video", height=720) == 25 * 1024**2
    assert main.estimate_size(info, "video-only") == 50 * 1024**2
    assert main.estimate_size(info, "audio") == 5 * 1024**2


def test_estimate_size_returns_none_when_unknown():
    assert main.estimate_size({"formats": []}, "video") is None


def test_primary_info_drills_into_playlist():
    playlist = {"_type": "playlist", "entries": [{"title": "First", "formats": []}]}
    assert main._primary_info(playlist)["title"] == "First"
    assert main._primary_info({"_type": "playlist", "entries": []}) == {}
    assert main._primary_info(None) == {}


def test_describe_error():
    assert "age" in main._describe_error("ERROR: Sign in to confirm your age").lower()
    assert main._describe_error("Private video") == "This video is private."
    assert main._describe_error("totally random") == ""


# ── Cookie resolution ───────────────────────────────────────────────────────
def test_parse_browser_spec():
    assert main._parse_browser_spec("chrome") == ("chrome", None)
    assert main._parse_browser_spec("Firefox:default-release") == ("firefox", "default-release")
    assert main._parse_browser_spec("  edge : Profile 1 ") == ("edge", "Profile 1")


def test_build_ydl_options_reliability_defaults(tmp_path: Path):
    options = main.build_ydl_options(
        mode="video",
        output_dir=tmp_path,
        height=1080,
        bitrate="320",
        audio_format="mp3",
        playlist=False,
        cookie_opts={"cookiefile": "/tmp/cookies.txt"},
        use_archive=True,
        verbose=False,
    )
    assert options["retries"] >= 1
    assert options["fragment_retries"] >= 1
    assert options["continuedl"] is True
    assert options["noplaylist"] is True
    assert options["merge_output_format"] == "mp4"
    assert options["cookiefile"] == "/tmp/cookies.txt"
    assert options["download_archive"] == str(main.ARCHIVE_FILE)
    assert "postprocessors" not in options


def test_build_ydl_options_audio_and_no_archive(tmp_path: Path):
    options = main.build_ydl_options(
        mode="audio",
        output_dir=tmp_path,
        height=None,
        bitrate="192",
        audio_format="mp3",
        playlist=True,
        cookie_opts={},
        use_archive=False,
        verbose=True,
    )
    assert options["noplaylist"] is False
    assert options["writethumbnail"] is True
    assert "download_archive" not in options
    assert options["postprocessors"][0]["preferredquality"] == "192"
    assert "merge_output_format" not in options


# ── CLI surface ─────────────────────────────────────────────────────────────
def test_parser_defaults():
    args = main.build_parser().parse_args([])
    assert args.url is None
    assert args.mode is None
    assert args.playlist is None
    assert args.archive is True
    assert args.no_clipboard is False


def test_parser_playlist_flags():
    parser = main.build_parser()
    assert parser.parse_args(["-p"]).playlist is True
    assert parser.parse_args(["--no-playlist"]).playlist is False


def test_parser_full_non_interactive():
    args = main.build_parser().parse_args(
        ["https://youtu.be/abc", "-m", "audio", "-b", "192", "-f", "mp3", "--no-archive"]
    )
    assert args.url == "https://youtu.be/abc"
    assert args.mode == "audio"
    assert args.bitrate == "192"
    assert args.audio_format == "mp3"
    assert args.archive is False


def test_prompt_choice_reprompts_on_invalid_input(monkeypatch, capsys):
    answers = iter(["x", "2"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    assert main._prompt_choice("? ", {"1", "2"}, default="1") == "2"
    assert "Invalid selection" in capsys.readouterr().out


def test_prompt_choice_uses_default_on_empty_input(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _prompt="": "")
    assert main._prompt_choice("? ", {"1", "2"}, default="1") == "1"
