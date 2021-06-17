import re
import enum
from enum import Flag
import functools


class StatementKind(Flag):
    TABLE = enum.auto()
    VIEW = enum.auto()
    INDEX = enum.auto()
    TRIGGER = enum.auto()
    QUERY = enum.auto()
    EXAMPLE = enum.auto()
    CLI = enum.auto()

    def keywords(self):
        keywords = []
        if self & StatementKind.TABLE:
            keywords.append((StatementKind.TABLE, "create table"))
        if self & StatementKind.INDEX:
            keywords.append((StatementKind.INDEX, "index"))
        if self & StatementKind.VIEW:
            keywords.append((StatementKind.VIEW, "create view"))
        if self & StatementKind.TRIGGER:
            keywords.append((StatementKind.TRIGGER, "create trigger"))
        if self & StatementKind.QUERY:
            keywords.append((StatementKind.QUERY, "query data"))
        if self & StatementKind.EXAMPLE:
            keywords.append((StatementKind.EXAMPLE, "example"))
        if self & StatementKind.CLI:
            keywords.append((StatementKind.CLI, "CLI"))
        return keywords

    def __str__(self):
        return ", ".join([k[1] for k in self.keywords()])


# Don't judge me for this unnecessary stuff, I was bored.
class SqlStatement:
    sql_break_before_after = re.compile(r"(BEGIN|END)", flags=re.IGNORECASE)
    sql_break_after = re.compile(r"EXISTS", flags=re.IGNORECASE)
    sql_keywords = re.compile(
        r"""(ABORT|ACTION|ADD|AFTER|ALL|ALTER|ALWAYS|ANALYZE|AND|AS|ASC|ATTACH|AUTOINCREMENT|BEFORE|BETWEEN|BIGINT|BLOB|BOOLEAN|BY|CASCADE|CASE|CAST|CHAR|CHARACTER|CHECK|CLOB|COLLATE|COLUMN|COMMIT|CONFLICT|CONSTRAINT|CREATE|CROSS|CURRENT|CURRENT_DATE|CURRENT_TIME|CURRENT_TIMESTAMP|DATABASE|DATE|DATETIME|DECIMAL|DEFAULT|DEFERRABLE|DEFERRED|DELETE|DESC|DETACH|DISTINCT|DO|DOUBLE|PRECISION|DROP|EACH|ELSE|ESCAPE|EXCEPT|EXCLUDE|EXCLUSIVE|EXPLAIN|FAIL|FILTER|FIRST|FLOAT|FOLLOWING|FOR|FOREIGN|FROM|FULL|GENERATED|GLOB|GROUP|GROUPS|HAVING|IF|IGNORE|IMMEDIATE|IN|INDEX|INDEXED|INITIALLY|INNER|INSERT|INSTEAD|INT|INT2|INT8|INTEGER|INTERSECT|INTO|IS|ISNULL|JOIN|KEY|LAST|LEFT|LIKE|LIMIT|MATCH|MATERIALIZED|MEDIUMINT|NATIVE|NATURAL|NO|NOT|NOTHING|NOTNULL|NULL|NULLS|NUMERIC|NVARCHAR|OF|OFFSET|ON|OR|ORDER|OTHERS|OUTER|OVER|PARTITION|PLAN|PRAGMA|PRECEDING|PRIMARY|QUERY|RAISE|RANGE|REAL|RECURSIVE|REFERENCES|REGEXP|REINDEX|RELEASE|RENAME|REPLACE|RESTRICT|RETURNING|RIGHT|ROLLBACK|ROW|ROWS|SAVEPOINT|SELECT|SET|SMALLINT|TABLE|TEMP|TEMPORARY|TEXT|THEN|TIES|TINYINT|TO|TRANSACTION|TRIGGER|UNBOUNDED|UNINDEXED|UNION|UNIQUE|UNSIGNED|BIG|UPDATE|USING|VACUUM|VALUES|VARCHAR|VARYING|VIEW|VIRTUAL|WHEN|WHERE|WINDOW|WITH|WITHOUT)""",
        flags=re.IGNORECASE,
    )

    def __init__(
        self,
        _id,
        statement,
        kind=StatementKind.QUERY,
        dependencies=[],
        callable_=False,
        doc=None,
    ):
        self._id = _id
        self.statement = statement
        self._satisfied = False
        self.kind = kind
        self.doc_string = doc
        self.callable_ = callable_
        self.dependencies = dependencies

    @property
    def satisfied(self):
        return self._satisfied

    @satisfied.setter
    def satisfied(self, new_val):
        if not isinstance(new_val, bool):
            raise TypeError("satisfied field requires a boolean value")
        self._satisfied = new_val

    def keywords(self):
        return self.kind.keywords()

    def __str__(self):
        return self.statement

    def get_id(self):
        return self._id

    def __repr__(self):
        return self._id

    @property
    @functools.lru_cache()
    def html(self):
        import shlex
        import string

        parser = shlex.shlex(self.statement, posix=False, punctuation_chars=" \t")
        parser.whitespace = " \t\r"
        tokens = list(parser)

        ident_fn = (
            lambda start_of_line, indent_level: '<span class="line">'
            + "&emsp;" * indent_level * 2
            if start_of_line
            else ""
        )

        class Tokenizer:
            super = self
            indent_level = 0
            indent_level = 0
            prev_tok = None
            start_of_line = True

            def matchtoken(self, tok):
                ret = None
                if tok == "END":
                    self.indent_level -= 1
                if self.super.sql_break_before_after.fullmatch(tok):
                    self.start_of_line = True
                    ret = f"</span>{ident_fn(self.start_of_line,self.indent_level)}<b>{tok.upper()}</b></span>"
                elif (
                    self.super.sql_keywords.fullmatch(tok) or tok in string.punctuation
                ):
                    ret = f"{ident_fn(self.start_of_line,self.indent_level)}<b>{tok.upper()}</b>"
                    self.start_of_line = False
                elif self.super.sql_break_after.fullmatch(tok):
                    ret = f"{ident_fn(self.start_of_line,self.indent_level)}<b>{tok.upper()}</b></span>"
                    self.start_of_line = True
                elif tok == "\n":
                    ret = "</span>"
                    self.start_of_line = True
                else:
                    ret = ident_fn(self.start_of_line, self.indent_level) + tok
                    self.start_of_line = False
                if tok == "\n" and self.prev_tok == "(":
                    self.indent_level += 1
                elif tok == ")" and self.prev_tok == "\n":
                    self.indent_level -= 1
                elif tok == "BEGIN":
                    self.indent_level += 1
                self.prev_tok = tok
                return ret

        tokenizer = Tokenizer()
        s = " ".join([tokenizer.matchtoken(tok) for tok in tokens])
        s = re.sub(r"\s*<b>\.</b>\s{0,1}", "<b>.</b>", s)
        s = re.sub(r"\s*<b>,</b>\s*", "<b>,</b> ", s)
        s = re.sub(r"\s*<b>\)</b>\s{0,1}", "<b>)</b> ", s)
        s = re.sub(r"\s*<b>\(</b>\s{0,1}", "<b>(</b>", s)
        s = re.sub(r"\s*<b>\(</b>\s{0,1}", "<b>(</b>", s)
        s = re.sub(r"</b>\s*<b>\(</b>\s{0,1}", "</b><b>(</b>", s)
        s = re.sub(r"<b>\)</b>\s*<b>\)", "<b>)</b><b>)", s)
        s = re.sub(r"\s*<b>;</b>\s{0,1}", "<b>;</b> ", s, flags=re.MULTILINE)
        s = re.sub(r"\s*<b>,</b>\s*", "<b>,</b> ", s, flags=re.MULTILINE)
        s = re.sub(r"\s*<br />", "<br />", s, flags=re.MULTILINE)
        return s.strip()

    @property
    def doc(self):
        return self.doc_string


def sqlite3_reference_href(url, text=None):
    if text is None:
        text = ""
    else:
        text = " for " + text
    return f"""<cite><a rel="external nofollow noreferrer" href="{url}">sqlite3 reference{text}</a></cite>"""


CREATE_BINARYMETADATA = SqlStatement(
    "CREATE_BINARYMETADATA",
    """CREATE TABLE IF NOT EXISTS "BinaryMetadata" (
        "uuid" char(32) NOT NULL PRIMARY KEY,
        "name" text NULL,
        "data" BLOB NOT NULL,
        "created" datetime NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f',
                'now')),
        "last_modified" datetime NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f',
                'now'))
);""",
    doc="",
    kind=StatementKind.TABLE,
    callable_=True,
)

CREATE_TEXTMETADATA = SqlStatement(
    "CREATE_TEXTMETADATA",
    """CREATE TABLE IF NOT EXISTS "TextMetadata" (
        "uuid" char(32) NOT NULL PRIMARY KEY,
        "name" text NULL,
        "data" text NOT NULL,
        "created" datetime NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f',
                'now')),
        "last_modified" datetime NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f',
                'now'))
);""",
    doc="",
    kind=StatementKind.TABLE,
    callable_=True,
)

CREATE_DOCUMENTS = SqlStatement(
    "CREATE_DOCUMENTS",
    """CREATE TABLE IF NOT EXISTS "Documents" (
        "uuid" CHAR(32) NOT NULL PRIMARY KEY,
        "title" TEXT NOT NULL,
        "title_suffix" TEXT,
        "created" datetime NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f',
                'now')),
        "last_modified" datetime NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f',
                'now'))
);""",
    doc="",
    kind=StatementKind.TABLE,
    callable_=True,
)

CREATE_DOCUMENTHASBINARYMETADATA = SqlStatement(
    "CREATE_DOCUMENTHASBINARYMETADATA",
    """CREATE TABLE IF NOT EXISTS "DocumentHasBinaryMetadata" (
        "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
        "name" TEXT NOT NULL,
        "document_uuid" char(32) NOT NULL REFERENCES "Documents" ("uuid") DEFERRABLE INITIALLY DEFERRED,
        "metadata_uuid" char(32) NOT NULL REFERENCES "BinaryMetadata" ("uuid") DEFERRABLE INITIALLY DEFERRED,
        "created" datetime NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f',
                'now')),
        "last_modified" datetime NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f',
                'now'))
);""",
    doc="",
    kind=StatementKind.TABLE,
    callable_=True,
    dependencies=[CREATE_DOCUMENTS, CREATE_BINARYMETADATA],
)

CREATE_DOCUMENTHASTEXTMETADATA = SqlStatement(
    "CREATE_DOCUMENTHASTEXTMETADATA",
    'CREATE TABLE IF NOT EXISTS "DocumentHasTextMetadata" (\n        "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,\n        "name" TEXT NOT NULL,\n        "document_uuid" char(32) NOT NULL REFERENCES "Documents" ("uuid") DEFERRABLE INITIALLY DEFERRED,\n        "metadata_uuid" char(32) NOT NULL REFERENCES "TextMetadata" ("uuid") DEFERRABLE INITIALLY DEFERRED,\n        "created" datetime NOT NULL DEFAULT (strftime (\'%Y-%m-%d %H:%M:%f\',\'now\')),\n        "last_modified" datetime NOT NULL DEFAULT (strftime (\'%Y-%m-%d %H:%M:%f\',\'now\'))\n);\n\n',
    doc="",
    kind=StatementKind.TABLE,
    callable_=True,
    dependencies=[CREATE_DOCUMENTS, CREATE_TEXTMETADATA],
)


CREATE_VIEW_DOCUMENTS_TITLE_AUTHORS = SqlStatement(
    "CREATE_VIEW_DOCUMENTS_TITLE_AUTHORS",
    """CREATE VIEW document_title_authors (rowid, title, authors) AS
SELECT uuid, title, authors
FROM
    Documents AS d
    LEFT JOIN (SELECT
            document_uuid,
            GROUP_CONCAT (data, '\\0') AS authors
        FROM
            DocumentHasTextMetadata AS dhtm
            JOIN TextMetadata AS tm ON dhtm.metadata_uuid = tm.uuid
        WHERE
            tm.name = 'author'
        GROUP BY
            document_uuid) AS authors ON d.uuid = authors.document_uuid;""",
    doc=f"""Auxiliary view for use in <var>document_title_authors_text_view_fts</var> index. Returns document title and a NULL byte separated string with all authors or NULL for all documents. {sqlite3_reference_href("https://sqlite.org/lang_createview.html",text="for creating views")}""",
    kind=StatementKind.VIEW,
    callable_=True,
    dependencies=[],
)

FTS_CREATE_TABLE = SqlStatement(
    "FTS_CREATE_TABLE",
    """CREATE VIRTUAL TABLE IF NOT EXISTS document_title_authors_text_view_fts USING fts5(title, authors, full_text, uuid UNINDEXED)""",
    doc=f"""Create a full-text search index using the <em>fts5</em> module. {sqlite3_reference_href("https://sqlite.org/fts5.html")}""",
    kind=(StatementKind.INDEX | StatementKind.TABLE),
    callable_=True,
)

FTS_CREATE_INSERT_TRIGGER = SqlStatement(
    "FTS_CREATE_INSERT_TRIGGER",
    """CREATE TRIGGER insert_full_text_trigger AFTER INSERT ON DocumentHasBinaryMetadata
WHEN EXISTS (
        SELECT
            *
        FROM
            BinaryMetadata AS bm
        WHERE
            NEW.metadata_uuid = bm.uuid
            AND bm.name = 'full-text')
BEGIN
    INSERT INTO document_title_authors_text_view_fts (
        uuid, title, authors, full_text)
SELECT
    d.rowid AS rowid, d.title AS title, d.authors AS authors, bm.data AS full_text
FROM
    document_title_authors AS d,
    BinaryMetadata AS bm
WHERE
    d.rowid = NEW.document_uuid
    AND bm.name = 'full-text'
    AND bm.uuid = NEW.metadata_uuid;
END;""",
    doc=f"""Trigger to insert full text data when a <var>DocumentHasBinaryMetadata</var> row for a full-text <var>BinaryMetadata</var> is created. {sqlite3_reference_href("https://sqlite.org/lang_createtrigger.html", text="for creating triggers")}""",
    kind=(StatementKind.TRIGGER | StatementKind.INDEX),
    callable_=True,
    dependencies=[
        FTS_CREATE_TABLE,
        CREATE_DOCUMENTHASBINARYMETADATA,
        CREATE_VIEW_DOCUMENTS_TITLE_AUTHORS,
    ],
)

FTS_CREATE_DELETE_TRIGGER = SqlStatement(
    "FTS_CREATE_DELETE_TRIGGER",
    """CREATE TRIGGER IF NOT EXISTS delete_full_text_trigger
       AFTER DELETE ON DocumentHasBinaryMetadata
        WHEN OLD.name = 'full-text'
       BEGIN
       DELETE FROM document_title_authors_text_view_fts
       WHERE uuid = OLD.document_uuid;
END""",
    doc=f"""Trigger to remove a document's full text from the full text search table when the full-text binary metadata is deleted. {sqlite3_reference_href("https://sqlite.org/lang_createtrigger.html", text="for creating triggers")}""",
    kind=(StatementKind.TRIGGER | StatementKind.INDEX),
    callable_=True,
    dependencies=[FTS_CREATE_TABLE, CREATE_DOCUMENTHASBINARYMETADATA],
)

FTS_REBUILD = SqlStatement(
    "FTS_REBUILD",
    """INSERT INTO document_title_authors_text_view_fts(document_title_authors_text_view_fts) VALUES('rebuild')""",
    doc=f"""This command first deletes the entire full-text index, then rebuilds it. {sqlite3_reference_href("https://sqlite.org/fts5.html#the_rebuild_command")}""",
    kind=StatementKind.INDEX,
    callable_=True,
    dependencies=[FTS_CREATE_TABLE],
)

FTS_OPTIMIZE = SqlStatement(
    "FTS_OPTIMIZE",
    """INSERT INTO document_title_authors_text_view_fts(document_title_authors_text_view_fts) VALUES('optimize')""",
    doc=f"""This command merges all individual b-trees that currently make up the full-text index into a single large b-tree structure. Because it reorganizes the entire <abbr title="Full-Text Search">FTS</abbr> index, the optimize command can take a long time to run. {sqlite3_reference_href("https://sqlite.org/fts5.html#the_optimize_command")}""",
    kind=StatementKind.INDEX,
    callable_=True,
    dependencies=[FTS_CREATE_TABLE],
)

FTS_INTEGRITY_CHECK = SqlStatement(
    "FTS_INTEGRITY_CHECK",
    """INSERT INTO document_title_authors_text_view_fts(document_title_authors_text_view_fts) VALUES('integrity-check')""",
    doc=f"""This command is used to verify that the full-text index is internally consistent. {sqlite3_reference_href("https://sqlite.org/fts5.html#the_integrity_check_command")}""",
    kind=(StatementKind.INDEX | StatementKind.QUERY),
    callable_=True,
    dependencies=[FTS_CREATE_TABLE],
)

FTS_SELECT_CONFIG = SqlStatement(
    "FTS_SELECT_CONFIG",
    """SELECT * FROM document_title_authors_text_view_fts_config""",
    doc=f"""This command returns the values of persistent configuration parameters. {sqlite3_reference_href("https://sqlite.org/fts5.html#appendix_b")}""",
    kind=(StatementKind.INDEX | StatementKind.QUERY),
    callable_=True,
    dependencies=[FTS_CREATE_TABLE],
)

FTS_SEARCH = SqlStatement(
    "FTS_SEARCH",
    """SELECT uuid FROM document_title_authors_text_view_fts('query text')""",
    doc=f"""This command queries the full-text search index for documents. {sqlite3_reference_href("https://sqlite.org/fts5.html")}""",
    kind=(StatementKind.INDEX | StatementKind.QUERY),
    callable_=False,
    dependencies=[FTS_CREATE_TABLE],
)

""" Example query:
    SELECT DISTINCT token FROM uuidtok WHERE input=(SELECT data FROM
    BinaryMetadata WHERE uuid = '17ee75452e574e03b0b8e4ef2bc9be25') AND
    LENGTH(token) = 36;
"""
CREATE_UUID_TOKENIZER = SqlStatement(
    "CREATE_UUID_TOKENIZER",
    """CREATE VIRTUAL TABLE IF NOT EXISTS uuidtok USING fts3tokenize('unicode61', "tokenchars=-1234567890abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ", "separators= ");""",
    doc=f"""{sqlite3_reference_href("https://www.sqlite.org/fts3.html#querying_tokenizers")}""",
    kind=(StatementKind.INDEX | StatementKind.TABLE),
    callable_=True,
)

CORE_SCHEMA = [
    CREATE_DOCUMENTS,
    CREATE_TEXTMETADATA,
    CREATE_BINARYMETADATA,
    CREATE_DOCUMENTHASTEXTMETADATA,
    CREATE_DOCUMENTHASBINARYMETADATA,
]
FTS_SCHEMA = [
    CREATE_VIEW_DOCUMENTS_TITLE_AUTHORS,
    FTS_CREATE_TABLE,
    FTS_CREATE_INSERT_TRIGGER,
    FTS_CREATE_DELETE_TRIGGER,
]

"""
# JSON queries:

Search for valid JSON names:

    select uuid, name from BinaryMetadata where json_valid(name);

Select text files:
    select uuid, name, json_extract(name, '$.content_type') as _type from BinaryMetadata where json_valid(name) and _type LIKE "%text/%";

    SELECT DISTINCT token FROM uuidtok WHERE input=(SELECT data FROM
    BinaryMetadata WHERE uuid = '17ee75452e574e03b0b8e4ef2bc9be25') AND
    LENGTH(token) = 36;

Match against uuid string with hyphens:

    select * from Documents where uuid = replace('7ec63f30-5882-46ac-855d-bdcaf8f29700', '-', '');

Find backreferences from plain text files:

    SELECT DISTINCT REPLACE(tok.token, '-', '') AS target, texts.uuid AS referrer FROM uuidtok AS tok, (SELECT uuid, data, json_extract(name, '$.content_type') AS _type FROM BinaryMetadata WHERE json_valid(name) AND _type LIKE "%text/%") AS texts WHERE tok.input=texts.data AND LENGTH(tok.token) = 36 AND EXISTS (SELECT * FROM Documents WHERE uuid = REPLACE(tok.token, '-', ''));

Create backref index:

    CREATE VIRTUAL TABLE backrefs_fts USING fts5(referrer, target);
"""

QUERY_VALID_JSON_NAMES = SqlStatement(
    "QUERY_VALID_JSON_NAMES",
    """SELECT uuid, name FROM BinaryMetadata WHERE json_valid(name);""",
    doc="",
    kind=(StatementKind.QUERY | StatementKind.EXAMPLE),
    callable_=False,
    dependencies=[CREATE_BINARYMETADATA],
)

QUERY_TEXT_FILES = SqlStatement(
    "QUERY_TEXT_FILES",
    """SELECT uuid, name, json_extract(name, '$.content_type') AS _type
    FROM BinaryMetadata
    WHERE json_valid(name)
    AND _type LIKE "%text/%";""",
    doc="",
    kind=(StatementKind.QUERY | StatementKind.EXAMPLE),
    callable_=False,
    dependencies=[CREATE_BINARYMETADATA],
)

QUERY_BACKREF_CANDIDATES = SqlStatement(
    "QUERY_BACKREF_CANDIDATES",
    """SELECT DISTINCT token FROM uuidtok
    WHERE input =
    (SELECT data FROM BinaryMetadata
    WHERE uuid = '17ee75452e574e03b0b8e4ef2bc9be25')
    AND LENGTH(token) = 36;""",
    doc="",
    kind=(StatementKind.QUERY | StatementKind.EXAMPLE),
    callable_=False,
    dependencies=[CREATE_BINARYMETADATA, CREATE_UUID_TOKENIZER],
)

QUERY_UUID_WITH_HYPHENS = SqlStatement(
    "QUERY_UUID_WITH_HYPHENS",
    """SELECT * FROM Documents
    WHERE uuid =
    REPLACE('7ec63f30-5882-46ac-855d-bdcaf8f29700', '-', '');""",
    doc="",
    kind=(StatementKind.QUERY | StatementKind.EXAMPLE),
    callable_=False,
    dependencies=[CREATE_DOCUMENTS],
)

QUERY_BACKREFS_FROM_TEXT_FILES = SqlStatement(
    "QUERY_BACKREFS_FROM_TEXT_FILES",
    """SELECT DISTINCT REPLACE(tok.token, '-', '') AS target,
    texts.uuid AS referrer FROM uuidtok AS tok,
    (SELECT uuid, data,
    json_extract(name, '$.content_type') AS _type
    FROM BinaryMetadata
    WHERE json_valid(name) AND _type LIKE "%text/%")
    AS texts
    WHERE tok.input=texts.data AND LENGTH(tok.token) = 36
    AND EXISTS (SELECT * FROM Documents WHERE uuid = REPLACE(tok.token, '-', ''));""",
    doc="Find backreferences from plain text files.",
    kind=(StatementKind.QUERY | StatementKind.EXAMPLE),
    callable_=False,
    dependencies=[CREATE_DOCUMENTS, CREATE_UUID_TOKENIZER, CREATE_BINARYMETADATA],
)

CREATE_BACKREF_INDEX = SqlStatement(
    "CREATE_BACKREF_INDEX",
    """CREATE VIRTUAL TABLE backrefs_fts USING fts5(referrer, target);""",
    doc="Create backref index.",
    callable_=True,
    kind=(StatementKind.INDEX | StatementKind.EXAMPLE),
)

CLI_INSERT_FILE = SqlStatement(
    "CLI_INSERT_FILE",
    """UPDATE BinaryMetadata SET
    data=readfile('file.pdf'),
    name=json_object('content_type', 'application/pdf', 'filename', 'file.pdf', 'size', LENGTH(readfile('file.pdf'))),
    last_modified = strftime('%Y-%m-%d %H:%M:%f', 'now')
    WHERE uuid = '17ee75452e574e03b0b8e4ef2bc9be25';""",
    doc=f"""The sqlite3 CLI has some special I/O function to facilate reading and writing files. <code>readfile(PATH)</code> will return the bytes read from the path <code>PATH</code> as a <code>BLOB</code>.
    We also use <code>json_object()</code> to create a new name for the entry; this could also be done with <code>json_replace()</code>. {sqlite3_reference_href("https://sqlite.org/cli.html#file_i_o_functions",text="Documentation on the CLI file I/O functions")} and {sqlite3_reference_href("https://www.sqlite.org/json1.html",text="Documentation on JSON1 extension")}""",
    callable_=False,
    kind=(StatementKind.CLI | StatementKind.EXAMPLE),
)

CLI_EXCTRACT_FILE = SqlStatement(
    "CLI_EXCTRACT_FILE",
    """SELECT writefile('file.pdf',data) FROM BinaryMetadata
    WHERE uuid ='17ee75452e574e03b0b8e4ef2bc9be25');
""",
    doc=f"""Exctract a binary <code>BLOB</code> from any column using the CLI. {sqlite3_reference_href("https://sqlite.org/cli.html#file_i_o_functions",text="Documentation on the CLI file I/O functions")}""",
    callable_=False,
    kind=(StatementKind.CLI | StatementKind.EXAMPLE),
)

CLI_EDIT_FILE = SqlStatement(
    "CLI_EDIT_FILE",
    """UPDATE BinaryMetadata SET data=edit(data, 'vim')
    WHERE uuid ='17ee75452e574e03b0b8e4ef2bc9be25';""",
    doc=f"""Edit any binary <code>BLOB</code> with the <code>edit()</code> function in the CLI. {sqlite3_reference_href("https://sqlite.org/cli.html#the_edit_sql_function",text="Documentation on the CLI <code>EDIT</code> function")}""",
    callable_=False,
    kind=(StatementKind.CLI | StatementKind.EXAMPLE),
)

CLI_VIEW_FILE = SqlStatement(
    "CLI_VIEW_FILE",
    """SELECT LENGTH(edit(data, 'zathura')) FROM BinaryMetadata
    WHERE uuid ='17ee75452e574e03b0b8e4ef2bc9be25';""",
    doc=f"""View any binary <code>BLOB</code> with the <code>edit()</code> function in the CLI by ignoring the value it returns. {sqlite3_reference_href("https://sqlite.org/cli.html#the_edit_sql_function",text="Documentation on the CLI <code>EDIT</code> function")}""",
    callable_=False,
    kind=(StatementKind.CLI | StatementKind.EXAMPLE),
)


def topsort():
    from bibliothecula.graphlib import TopologicalSorter

    ts = TopologicalSorter()

    for c in CORE_SCHEMA:
        # print(repr(c), repr(c.dependencies))
        ts.add(c, *c.dependencies)
    for c in FTS_SCHEMA:
        # print(repr(c), repr(c.dependencies))
        ts.add(c, *c.dependencies)
    order = list(ts.static_order())
    print(order)
