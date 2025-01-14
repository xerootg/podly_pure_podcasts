import datetime
import re
import urllib.parse
from pathlib import Path
from typing import Any, Optional, Tuple, cast

import feedparser  # type: ignore[import-untyped]
import flask
import PyRSS2Gen  # type: ignore[import-untyped]
import validators
from flask import Blueprint, abort, request, send_file, url_for

from app import config, logger
from podcast_processor.podcast_processor import PodcastProcessor, PodcastProcessorTask
from shared.podcast_downloader import download_episode, find_audio_link

old_bp = Blueprint("old", __name__)


PARAM_SEP = "PODLYPARAMSEP"  # had some issues with ampersands in the URL


# kept for backwards compatibility where download link is full url
@old_bp.route("/download/<path:episode_name>")
def download(episode_name: str) -> flask.Response:
    episode_name = urllib.parse.unquote(episode_name)
    podcast_title, episode_url = get_args(request.url)
    logger.info(f"Downloading episode {episode_name} from podcast {podcast_title}...")
    if episode_url is None or not validators.url(episode_url):
        return flask.make_response(("Invalid episode URL", 404))

    download_path = download_episode(podcast_title, episode_name, fix_url(episode_url))
    if download_path is None:
        return flask.make_response(("Failed to download episode", 500))
    task = PodcastProcessorTask(podcast_title, download_path, episode_name)
    processor = PodcastProcessor(config)
    output_path = processor.process(task)
    if output_path is None:
        return flask.make_response(("Failed to process episode", 500))

    try:
        return send_file(path_or_file=Path(output_path).resolve())
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error(f"Error sending file: {e}")
        return flask.make_response(("Error sending file", 500))


def get_args(full_request_url: str) -> Tuple[str, str]:
    args = urllib.parse.parse_qs(
        urllib.parse.urlparse(full_request_url.replace(PARAM_SEP, "&")).query
    )
    return args["podcast_title"][0], args["episode_url"][0]


def fix_url(url: str) -> str:
    url = re.sub(r"(http(s)?):/([^/])", r"\1://\3", url)
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url
    return url


# kept for backwards compatibility,
@old_bp.get("/<path:podcast_rss>")
def rss(podcast_rss: str) -> flask.Response:
    logger.info(f"getting rss for {podcast_rss}...")
    if podcast_rss == "favicon.ico":
        abort(404)
    # short URL for user favorite podcast
    if podcast_rss in config.podcasts:
        url = config.podcasts[podcast_rss]
    else:
        url = fix_url(podcast_rss)
    if not validators.url(url):
        abort(404)
    feed = feedparser.parse(url)
    feed = cast(feedparser.FeedParserDict, feed)
    if "feed" not in feed or "title" not in feed.feed:
        abort(404)
    transformed_items = []
    for entry in feed.entries:
        dl_link = get_download_link(entry, feed.feed.title)
        if dl_link is None:
            continue

        transformed_items.append(
            PyRSS2Gen.RSSItem(
                title=entry.title,
                link=dl_link,
                description=entry.description,
                guid=PyRSS2Gen.Guid(dl_link),
                enclosure=PyRSS2Gen.Enclosure(
                    dl_link,
                    str(entry.get("enclosures", [{}])[0].get("length", 0)),
                    "audio/mp3",
                ),
                pubDate=datetime.datetime(*entry.published_parsed[:6]),
            )
        )
    rss_feed = PyRSS2Gen.RSS2(
        title="[podly] " + feed.feed.title,
        link=request.url_root,
        description=feed.feed.description,
        lastBuildDate=datetime.datetime.now(),
        items=transformed_items,
    )
    return flask.make_response(
        (rss_feed.to_xml("utf-8"), 200, {"Content-Type": "application/xml"})
    )


def get_download_link(entry: Any, podcast_title: str) -> Optional[str]:
    audio_link = find_audio_link(entry)
    if audio_link is None:
        return None

    server = config.server if config.server is not None else ""
    assert isinstance(server, str)

    return (
        server
        + url_for(
            "old.download",
            episode_name=f"{remove_odd_characters(entry.title)}.mp3",
            _external=config.server is None,
        )
        + f"?podcast_title={urllib.parse.quote('[podly] ' + remove_odd_characters(podcast_title))}"
        + f"{PARAM_SEP}episode_url={urllib.parse.quote(audio_link)}"
    )


def remove_odd_characters(title: str) -> str:
    return re.sub(r"[^a-zA-Z0-9\s]", "", title)
