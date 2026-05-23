from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from flask_login import UserMixin
from sqlalchemy import CheckConstraint, UniqueConstraint
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


followers = db.Table(
    "followers",
    db.Column("follower_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("followed_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column(
        "created_at",
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    ),
    CheckConstraint("follower_id != followed_id", name="ck_follow_not_self"),
)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(40), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    bio = db.Column(db.String(280), nullable=False, default="")
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    posts = db.relationship("Post", back_populates="author", lazy="dynamic")
    comments = db.relationship("Comment", back_populates="author", lazy="dynamic")
    following = db.relationship(
        "User",
        secondary=followers,
        primaryjoin=(followers.c.follower_id == id),
        secondaryjoin=(followers.c.followed_id == id),
        backref=db.backref("followers", lazy="dynamic"),
        lazy="dynamic",
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def follow(self, user: "User") -> None:
        if user.id != self.id and not self.is_following(user):
            self.following.append(user)

    def unfollow(self, user: "User") -> None:
        if self.is_following(user):
            self.following.remove(user)

    def is_following(self, user: "User") -> bool:
        return (
            self.following.filter(followers.c.followed_id == user.id).count() > 0
        )


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text, nullable=False, default="")
    media_filename = db.Column(db.String(255), nullable=True)
    media_type = db.Column(db.String(20), nullable=True)
    is_poll = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    repost_of_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=True, index=True)

    author = db.relationship("User", back_populates="posts")
    comments = db.relationship(
        "Comment", back_populates="post", cascade="all, delete-orphan", lazy="dynamic"
    )
    repost_of = db.relationship("Post", remote_side=[id], backref="reposts")
    poll_options = db.relationship(
        "PollOption",
        back_populates="post",
        cascade="all, delete-orphan",
        order_by="PollOption.position",
    )
    poll_votes = db.relationship(
        "PollVote",
        back_populates="post",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    __table_args__ = (
        CheckConstraint(
            "(length(body) > 0) OR (media_filename IS NOT NULL) "
            "OR (repost_of_id IS NOT NULL) OR (is_poll = 1)",
            name="ck_post_has_content",
        ),
    )

    @property
    def display_post(self) -> "Post":
        return self.repost_of or self

    @property
    def is_repost(self) -> bool:
        return self.repost_of_id is not None


class PollOption(db.Model):
    __tablename__ = "poll_option"

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False, index=True)
    label = db.Column(db.String(200), nullable=False)
    position = db.Column(db.Integer, nullable=False, default=0)

    post = db.relationship("Post", back_populates="poll_options")
    votes = db.relationship(
        "PollVote",
        back_populates="poll_option",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    __table_args__ = (
        CheckConstraint("length(label) > 0", name="ck_poll_option_label_not_empty"),
        UniqueConstraint("post_id", "position", name="uq_poll_option_position"),
    )


class PollVote(db.Model):
    __tablename__ = "poll_vote"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False, index=True)
    poll_option_id = db.Column(
        db.Integer, db.ForeignKey("poll_option.id"), nullable=False, index=True
    )
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    user = db.relationship("User", backref=db.backref("poll_votes", lazy="dynamic"))
    post = db.relationship("Post", back_populates="poll_votes")
    poll_option = db.relationship("PollOption", back_populates="votes")

    __table_args__ = (UniqueConstraint("user_id", "post_id", name="uq_poll_vote_one_per_user"),)


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _as_utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


class CaptchaChallenge(db.Model):
    __tablename__ = "captcha_challenge"

    challenge_id = db.Column(db.String(64), primary_key=True)
    answer = db.Column(db.Integer, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=_utc_now_naive,
    )
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)

    @property
    def is_expired(self) -> bool:
        return _utc_now_naive() >= _as_utc_naive(self.expires_at)

    @classmethod
    def create_challenge(
        cls,
        answer: int,
        *,
        ttl: timedelta | None = None,
    ) -> CaptchaChallenge:
        now = _utc_now_naive()
        challenge = cls(
            challenge_id=secrets.token_urlsafe(16),
            answer=answer,
            created_at=now,
            expires_at=now + (ttl or timedelta(minutes=5)),
        )
        db.session.add(challenge)
        db.session.commit()
        return challenge


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False, index=True)

    author = db.relationship("User", back_populates="comments")
    post = db.relationship("Post", back_populates="comments")

    __table_args__ = (
        UniqueConstraint("author_id", "post_id", "body", name="uq_comment_duplicate_guard"),
    )

