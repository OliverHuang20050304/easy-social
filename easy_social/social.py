from __future__ import annotations

from dataclasses import dataclass

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import desc, func, or_
from sqlalchemy.orm import joinedload

from .extensions import db
from .media import save_media
from .models import Comment, PollOption, PollVote, Post, User, followers
from .polls import option_percentages, validate_poll_options

bp = Blueprint("social", __name__)


@dataclass(frozen=True)
class PollOptionView:
    id: int
    label: str
    vote_count: int
    percentage: float


@dataclass(frozen=True)
class PollView:
    options: tuple[PollOptionView, ...]
    total_votes: int
    user_vote_option_id: int | None
    show_results: bool


def _post_query():
    return Post.query.options(
        joinedload(Post.author),
        joinedload(Post.repost_of).joinedload(Post.author),
        joinedload(Post.poll_options),
        joinedload(Post.repost_of).joinedload(Post.poll_options),
    )


def _comment_counts_for_posts(posts: list[Post]) -> dict[int, int]:
    post_ids = {post.display_post.id for post in posts}
    if not post_ids:
        return {}

    counts = dict.fromkeys(post_ids, 0)
    rows = (
        db.session.query(Comment.post_id, func.count(Comment.id))
        .filter(Comment.post_id.in_(post_ids))
        .group_by(Comment.post_id)
        .all()
    )
    counts.update({post_id: count for post_id, count in rows})
    return counts


def _poll_views_for_posts(posts: list[Post]) -> dict[int, PollView]:
    poll_posts = [post.display_post for post in posts if post.display_post.is_poll]
    if not poll_posts:
        return {}

    poll_post_ids = [post.id for post in poll_posts]
    options_by_post: dict[int, list[PollOption]] = {post_id: [] for post_id in poll_post_ids}
    for option in (
        PollOption.query.filter(PollOption.post_id.in_(poll_post_ids))
        .order_by(PollOption.post_id, PollOption.position)
        .all()
    ):
        options_by_post[option.post_id].append(option)

    vote_counts: dict[int, int] = dict.fromkeys(
        {option.id for options in options_by_post.values() for option in options},
        0,
    )
    rows = (
        db.session.query(PollVote.poll_option_id, func.count(PollVote.id))
        .filter(PollVote.post_id.in_(poll_post_ids))
        .group_by(PollVote.poll_option_id)
        .all()
    )
    vote_counts.update({option_id: count for option_id, count in rows})

    user_votes = {
        post_id: poll_option_id
        for post_id, poll_option_id in db.session.query(
            PollVote.post_id, PollVote.poll_option_id
        )
        .filter(
            PollVote.post_id.in_(poll_post_ids),
            PollVote.user_id == current_user.id,
        )
        .all()
    }

    poll_views: dict[int, PollView] = {}
    for post in poll_posts:
        options = options_by_post.get(post.id, [])
        counts = [vote_counts.get(option.id, 0) for option in options]
        percentages = option_percentages(counts)
        user_vote_option_id = user_votes.get(post.id)
        poll_views[post.id] = PollView(
            options=tuple(
                PollOptionView(
                    id=option.id,
                    label=option.label,
                    vote_count=count,
                    percentage=percentage,
                )
                for option, count, percentage in zip(options, counts, percentages, strict=True)
            ),
            total_votes=sum(counts),
            user_vote_option_id=user_vote_option_id,
            show_results=user_vote_option_id is not None,
        )
    return poll_views


def _followed_user_ids(users: list[User]) -> set[int]:
    user_ids = [user.id for user in users]
    if not user_ids:
        return set()

    return {
        followed_id
        for (followed_id,) in db.session.query(followers.c.followed_id)
        .filter(
            followers.c.follower_id == current_user.id,
            followers.c.followed_id.in_(user_ids),
        )
        .all()
    }


@bp.route("/")
@login_required
def feed():
    followed_ids = db.session.query(followers.c.followed_id).filter(
        followers.c.follower_id == current_user.id
    )
    posts = (
        _post_query()
        .filter(or_(Post.author_id == current_user.id, Post.author_id.in_(followed_ids)))
        .order_by(desc(Post.created_at))
        .limit(100)
        .all()
    )
    return render_template(
        "social/feed.html",
        posts=posts,
        comment_counts=_comment_counts_for_posts(posts),
        poll_views=_poll_views_for_posts(posts),
    )


@bp.route("/explore")
@login_required
def explore():
    posts = _post_query().order_by(desc(Post.created_at)).limit(100).all()
    users = User.query.filter(User.id != current_user.id).order_by(User.username).limit(50).all()
    return render_template(
        "social/explore.html",
        posts=posts,
        users=users,
        comment_counts=_comment_counts_for_posts(posts),
        poll_views=_poll_views_for_posts(posts),
        followed_user_ids=_followed_user_ids(users),
    )


@bp.post("/posts")
@login_required
def create_post():
    body = request.form.get("body", "").strip()
    is_poll = request.form.get("is_poll") == "1"

    if is_poll:
        if request.files.get("media") and request.files["media"].filename:
            flash("Poll posts cannot include media attachments.", "error")
            return redirect(request.referrer or url_for("social.feed"))

        try:
            option_labels = validate_poll_options(request.form.getlist("poll_options"))
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(request.referrer or url_for("social.feed"))

        post = Post(body=body, author=current_user, is_poll=True)
        db.session.add(post)
        db.session.flush()
        for position, label in enumerate(option_labels):
            db.session.add(PollOption(post=post, label=label, position=position))
        db.session.commit()
        return redirect(url_for("social.feed"))

    try:
        media_filename, media_type = save_media(request.files.get("media"))
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(request.referrer or url_for("social.feed"))

    if not body and not media_filename:
        flash("Add text, an image, or a video before posting.", "error")
        return redirect(request.referrer or url_for("social.feed"))

    post = Post(
        body=body,
        media_filename=media_filename,
        media_type=media_type,
        author=current_user,
    )
    db.session.add(post)
    db.session.commit()
    return redirect(url_for("social.feed"))


@bp.post("/posts/<int:post_id>/vote")
@login_required
def vote_poll(post_id: int):
    post = db.get_or_404(Post, post_id).display_post
    if not post.is_poll:
        flash("This post is not a poll.", "error")
        return redirect(request.referrer or url_for("social.feed"))

    poll_option_id = request.form.get("poll_option_id", type=int)
    if poll_option_id is None:
        flash("Choose a poll option before voting.", "error")
        return redirect(request.referrer or url_for("social.feed"))

    option = PollOption.query.filter_by(id=poll_option_id, post_id=post.id).first()
    if option is None:
        flash("That poll option is invalid.", "error")
        return redirect(request.referrer or url_for("social.feed"))

    existing_vote = PollVote.query.filter_by(user_id=current_user.id, post_id=post.id).first()
    if existing_vote is not None:
        flash("You already voted in this poll.", "error")
        return redirect(request.referrer or url_for("social.feed"))

    db.session.add(
        PollVote(user_id=current_user.id, post_id=post.id, poll_option_id=option.id)
    )
    db.session.commit()
    return redirect(request.referrer or url_for("social.feed"))


@bp.get("/posts/<int:post_id>")
@login_required
def post_detail(post_id: int):
    post = _post_query().filter(Post.id == post_id).first_or_404()
    comments = post.comments.order_by(Comment.created_at.asc()).all()
    poll_views = _poll_views_for_posts([post])
    return render_template(
        "social/post_detail.html",
        post=post,
        comments=comments,
        comment_counts={post.display_post.id: len(comments)},
        poll_views=poll_views,
    )


@bp.post("/posts/<int:post_id>/comments")
@login_required
def add_comment(post_id: int):
    post = db.get_or_404(Post, post_id)
    body = request.form.get("body", "").strip()
    if not body:
        flash("Comment cannot be empty.", "error")
    else:
        db.session.add(Comment(body=body, author=current_user, post=post))
        db.session.commit()
    return redirect(url_for("social.post_detail", post_id=post.id))


@bp.post("/posts/<int:post_id>/repost")
@login_required
def repost(post_id: int):
    original = db.get_or_404(Post, post_id).display_post
    if original.author_id == current_user.id:
        flash("You cannot repost your own post.", "error")
        return redirect(request.referrer or url_for("social.feed"))

    existing = Post.query.filter_by(author_id=current_user.id, repost_of_id=original.id).first()
    if existing:
        flash("You already reposted this.", "error")
        return redirect(request.referrer or url_for("social.feed"))

    db.session.add(Post(author=current_user, repost_of=original))
    db.session.commit()
    return redirect(request.referrer or url_for("social.feed"))


@bp.route("/users/<username>")
@login_required
def profile(username: str):
    user = User.query.filter_by(username=username).first_or_404()
    posts = (
        _post_query()
        .filter(Post.author_id == user.id)
        .order_by(desc(Post.created_at))
        .all()
    )
    return render_template(
        "social/profile.html",
        profile_user=user,
        posts=posts,
        comment_counts=_comment_counts_for_posts(posts),
        poll_views=_poll_views_for_posts(posts),
    )


@bp.post("/users/<username>/follow")
@login_required
def follow(username: str):
    user = User.query.filter_by(username=username).first_or_404()
    current_user.follow(user)
    db.session.commit()
    return redirect(request.referrer or url_for("social.profile", username=user.username))


@bp.post("/users/<username>/unfollow")
@login_required
def unfollow(username: str):
    user = User.query.filter_by(username=username).first_or_404()
    current_user.unfollow(user)
    db.session.commit()
    return redirect(request.referrer or url_for("social.profile", username=user.username))
