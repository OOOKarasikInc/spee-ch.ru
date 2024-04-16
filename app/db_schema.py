import sqlalchemy

db_metadata = sqlalchemy.MetaData()

boards_table = sqlalchemy.Table(
    "board",
    db_metadata,
    sqlalchemy.Column("slug", sqlalchemy.String(16), primary_key=True),
    sqlalchemy.Column("name", sqlalchemy.String(256), nullable=False),
)

threads_table = sqlalchemy.Table(
    "thread",
    db_metadata,
    sqlalchemy.Column(
        "id",
        sqlalchemy.Integer,
        sqlalchemy.Identity(start=1, cycle=True),
        primary_key=True,
    ),
    sqlalchemy.Column("text", sqlalchemy.Text, nullable=False),
    sqlalchemy.Column(
        "board",
        sqlalchemy.String(256),
        sqlalchemy.ForeignKey(boards_table.columns["slug"]),
    ),
    sqlalchemy.Column("last_update", sqlalchemy.DateTime(timezone=True)),
    # create last_update_index
)

thread_media_files_table = sqlalchemy.Table(
    "thread_media_file",
    db_metadata,
    sqlalchemy.Column(
        "thread", sqlalchemy.Integer, sqlalchemy.ForeignKey(threads_table.columns["id"])
    ),
    sqlalchemy.Column("filename", sqlalchemy.String(256), nullable=False),
    sqlalchemy.Column(
        "s3_filename", sqlalchemy.String(256), nullable=False, primary_key=True
    ),
    # create thread index
)

posts_table = sqlalchemy.Table(
    "post",
    db_metadata,
    sqlalchemy.Column(
        "id",
        sqlalchemy.Integer,
        sqlalchemy.Identity(start=1, cycle=True),
        primary_key=True,
    ),
    sqlalchemy.Column(
        "thread", sqlalchemy.Integer, sqlalchemy.ForeignKey(threads_table.columns["id"])
    ),
    sqlalchemy.Column("voice_message", sqlalchemy.String(256), nullable=False),
    # create thread index
)

post_media_files_table = sqlalchemy.Table(
    "post_media_file",
    db_metadata,
    sqlalchemy.Column(
        "post", sqlalchemy.Integer, sqlalchemy.ForeignKey(posts_table.columns["id"])
    ),
    sqlalchemy.Column("filename", sqlalchemy.String(256), nullable=False),
    sqlalchemy.Column(
        "s3_filename", sqlalchemy.String(256), nullable=False, primary_key=True
    ),
    # create post index
)
