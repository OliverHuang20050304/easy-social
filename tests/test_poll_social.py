from __future__ import annotations

import pytest

from easy_social.extensions import db
from easy_social.models import PollOption, PollVote, Post, User

from conftest import login, register

pytestmark = pytest.mark.integration


def create_poll(
    client,
    *,
    body: str = "Favorite color?",
    options: list[str],
):
    return client.post(
        "/posts",
        data={
            "is_poll": "1",
            "body": body,
            "poll_options": options,
        },
        follow_redirects=True,
    )


def test_create_poll_post_success(client, app):
    register(client, "alice")
    response = create_poll(client, options=["Red", "Blue", "Green"])

    assert response.status_code == 200
    assert b"Favorite color?" in response.data
    assert b"Poll" in response.data

    with app.app_context():
        post = Post.query.one()
        assert post.is_poll is True
        assert post.body == "Favorite color?"
        labels = [option.label for option in post.poll_options]
        assert labels == ["Red", "Blue", "Green"]


def test_create_poll_post_rejects_too_few_options(client):
    register(client, "alice")
    response = create_poll(client, options=["Only one"])

    assert b"at least 2" in response.data.lower()
    with client.application.app_context():
        assert Post.query.count() == 0


def test_create_poll_post_rejects_too_many_options(client):
    register(client, "alice")
    response = create_poll(client, options=["1", "2", "3", "4", "5"])

    assert b"at most 4" in response.data.lower()
    with client.application.app_context():
        assert Post.query.count() == 0


def test_create_poll_post_rejects_blank_options(client):
    register(client, "alice")
    response = create_poll(client, options=["Valid", "   "])

    assert b"at least 2" in response.data.lower()
    with client.application.app_context():
        assert Post.query.count() == 0


def test_user_can_vote_once_and_sees_results(client, app):
    register(client, "alice")
    create_poll(client, options=["Cats", "Dogs"])
    with app.app_context():
        poll_id = Post.query.one().id
        option_id = PollOption.query.filter_by(label="Cats").one().id

    vote_response = client.post(
        f"/posts/{poll_id}/vote",
        data={"poll_option_id": option_id},
        follow_redirects=True,
    )

    assert vote_response.status_code == 200
    assert b"1 votes (100.0%)" in vote_response.data
    assert b"0 votes (0.0%)" in vote_response.data
    assert b"Your vote" in vote_response.data

    with app.app_context():
        vote = PollVote.query.one()
        assert vote.user_id == User.query.filter_by(username="alice").one().id
        assert vote.poll_option_id == option_id


def test_user_cannot_vote_twice_in_same_poll(client, app):
    register(client, "alice")
    create_poll(client, options=["Tea", "Coffee"])
    with app.app_context():
        poll_id = Post.query.one().id
        tea_id = PollOption.query.filter_by(label="Tea").one().id
        coffee_id = PollOption.query.filter_by(label="Coffee").one().id

    client.post(f"/posts/{poll_id}/vote", data={"poll_option_id": tea_id}, follow_redirects=True)
    second_vote = client.post(
        f"/posts/{poll_id}/vote",
        data={"poll_option_id": coffee_id},
        follow_redirects=True,
    )

    assert b"already voted" in second_vote.data.lower()
    with app.app_context():
        assert PollVote.query.count() == 1


def test_poll_post_appears_in_feed(client):
    register(client, "alice")
    create_poll(client, body="Lunch poll", options=["Pizza", "Sushi"])

    feed = client.get("/")
    assert b"Lunch poll" in feed.data
    assert b"Vote" in feed.data


def test_text_and_image_posts_still_work_after_poll_feature(client, app):
    register(client, "alice")

    text_response = client.post("/posts", data={"body": "Plain text"}, follow_redirects=True)
    assert text_response.status_code == 200

    from io import BytesIO

    image_response = client.post(
        "/posts",
        data={
            "body": "Picture",
            "media": (BytesIO(b"fake-image-data"), "photo.png"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert image_response.status_code == 200

    with app.app_context():
        posts = Post.query.order_by(Post.id).all()
        assert len(posts) == 2
        assert posts[0].is_poll is False
        assert posts[0].body == "Plain text"
        assert posts[1].media_type == "image"
