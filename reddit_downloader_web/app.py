import os
import re
from urllib.parse import urlparse

from flask import (
    Flask,
    make_response,
    render_template,
    request,
)
import praw
import markdown
import requests
from weasyprint import HTML
import yaml


app = Flask(__name__)

file_dir = os.path.dirname(__file__)


class Config:
    def __init__(self):
        with open(os.path.join(file_dir, "../secrets.yaml"), "r") as stream:
            try:
                secrets = yaml.safe_load(stream)
            except yaml.YAMLError as exc:
                print(exc)
        self.hcaptcha_secret_key = secrets["hcaptcha"]["secret_key"]
        self.hcaptcha_verify_url = secrets["hcaptcha"]["verify_url"]

        self.reddit_client_id = secrets["reddit"]["client_id"]
        self.reddit_secret_key = secrets["reddit"]["secret_key"]


CONFIG = Config()

PATH_REGEX = re.compile(r"/r/\S+/comments/\S+/\S+/")


def clean_comment(comment: str) -> str:
    return comment.replace("\n", "  ")


def is_url_ok(url: str) -> bool:
    parsed_url = urlparse(url)

    if (
        parsed_url.netloc != "www.reddit.com"
        or not parsed_url.path
        or not PATH_REGEX.match(parsed_url.path)
    ):
        raise RuntimeError(
            "URL must be the full URL of the thread. "
            "For example: https://www.reddit.com/r/subreddit/comments/abc123/thread_title/"
        )

    return True


def download(comment_url) -> None:
    reddit = praw.Reddit(
        user_agent="User-Agent: ThreadBackupMakerforReddit:v1.0 (by /u/pmheavy)",
        client_id=CONFIG.reddit_client_id,
        client_secret=CONFIG.reddit_secret_key,
    )
    submission = reddit.submission(url=comment_url)

    comments = [
        f"# {submission.title} #",
        f"#### Author: {submission.author} ####",
        f"#### URL: {submission.permalink} ####",
        "\n-----",
        f"{submission.url}",
        f"\n{submission.selftext}" if submission.selftext else "",
        "\n-----",
    ]
    submission.comments.replace_more(limit=None)
    comment_queue = submission.comments[:]  # Seed with top-level
    while comment_queue:
        comment = comment_queue.pop(0)
        if comment.score >= 0:
            body = clean_comment(comment.body)
            if comment.parent_id.startswith("t1_"):
                parent_depth = comment.parent().depth
                comment.depth = (
                    comment.depth
                    if comment.depth > parent_depth
                    else parent_depth + comment.depth + 1
                )
            comments.append(
                f"{'    '*comment.depth}* {body} [Author: {comment.author}] [Upvotes: {comment.score}]"
            )
            comment_queue[0:0] = comment.replies

    markdown_string = "\n".join(comments)
    html = "".join(
        [
            "<html><head></head><body>",
            markdown.markdown(markdown_string),
            "</body></html>",
        ]
    )
    return HTML(string=html).write_pdf()


@app.route("/")
def hello_world():
    return render_template("main.html")


@app.route("/", methods=["POST"])
def my_form_post():
    url = request.form["url"]

    token = request.form["h-captcha-response"]
    data = {"secret": CONFIG.hcaptcha_secret_key, "response": token}
    hcaptcha_response = requests.post(url=CONFIG.hcaptcha_verify_url, data=data).json()
    if not hcaptcha_response["success"]:
        return render_template("error.html", error_message="Captcha not passed.")

    try:
        if is_url_ok(url):
            response = make_response(download(url))
            response.headers["Cache-Control"] = "must-revalidate"
            response.headers["Pragma"] = "must-revalidate"
            response.headers["Content-type"] = "application/pdf"
            response.headers["Content-Disposition"] = f"attachment; filename={url}.pdf"
            return response
    except RuntimeError as e:
        return render_template("error.html", error_message=str(e))
    except praw.reddit.ClientException:
        return render_template(
            "error.html", error_message="Unable to collect the thread."
        )
    except praw.reddit.RedditAPIException:
        return render_template(
            "error.html", error_message="Unable to connect to Reddit."
        )


if __name__ == "__main__":
    app.run()
