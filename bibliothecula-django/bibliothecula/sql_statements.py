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


CREATE_DOCUMENTS = SqlStatement(
    "CREATE_DOCUMENTS",
    """CREATE TABLE IF NOT EXISTS "Documents" (
        "uuid" CHARACTER(32) NOT NULL PRIMARY KEY,
        "title" TEXT NOT NULL,
        "title_suffix" TEXT DEFAULT NULL, -- disambiguate documents with matching titles
        "created" DATETIME NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f', 'now')),
        "last_modified" DATETIME NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f', 'now'))
);""",
    doc="",
    kind=StatementKind.TABLE,
    callable_=True,
)

CREATE_TEXTMETADATA = SqlStatement(
    "CREATE_TEXTMETADATA",
    """CREATE TABLE IF NOT EXISTS "TextMetadata" (
        "uuid" CHARACTER(32) NOT NULL PRIMARY KEY,
        "name" TEXT NULL,
        "data" TEXT NOT NULL,
        "created" DATETIME NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f', 'now')),
        "last_modified" DATETIME NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f', 'now'))
);""",
    doc="",
    kind=StatementKind.TABLE,
    callable_=True,
)

CREATE_BINARYMETADATA = SqlStatement(
    "CREATE_BINARYMETADATA",
    """CREATE TABLE IF NOT EXISTS "BinaryMetadata" (
        "uuid" CHARACTER(32) NOT NULL PRIMARY KEY,
        "name" TEXT NULL,
        "data" BLOB NOT NULL,
        "compressed" BOOLEAN NOT NULL DEFAULT (0),
        "created" DATETIME NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f', 'now')),
        "last_modified" DATETIME NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f', 'now'))
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
        "document_uuid" CHARACTER(32) NOT NULL
            REFERENCES "Documents" ("uuid") ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
        "metadata_uuid" CHARACTER(32) NOT NULL
            REFERENCES "BinaryMetadata" ("uuid") ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
        "created" DATETIME NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f', 'now')),
        "last_modified" DATETIME NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f', 'now'))
);""",
    doc="",
    kind=StatementKind.TABLE,
    callable_=True,
    dependencies=[CREATE_DOCUMENTS, CREATE_BINARYMETADATA],
)

CREATE_DOCUMENTHASTEXTMETADATA = SqlStatement(
    "CREATE_DOCUMENTHASTEXTMETADATA",
    """CREATE TABLE IF NOT EXISTS "DocumentHasTextMetadata" (
        "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
        "name" TEXT NOT NULL,
        "document_uuid" CHARACTER(32) NOT NULL
            REFERENCES "Documents" ("uuid") ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
        "metadata_uuid" CHARACTER(32) NOT NULL
            REFERENCES "TextMetadata" ("uuid") ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
        "created" DATETIME NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f', 'now')),
        "last_modified" DATETIME NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f', 'now'))
);""",
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
    """CREATE VIRTUAL TABLE IF NOT EXISTS document_title_authors_text_view_fts
    USING fts5(title, authors, full_text, uuid UNINDEXED)""",
    doc=f"""Create a full-text search index using the <em>fts5</em> module. {sqlite3_reference_href("https://sqlite.org/fts5.html")}""",
    kind=(StatementKind.INDEX | StatementKind.TABLE),
    callable_=True,
)

FTS_CREATE_INSERT_TRIGGER = SqlStatement(
    "FTS_CREATE_INSERT_TRIGGER",
    """CREATE TRIGGER insert_full_text_trigger
    AFTER INSERT ON DocumentHasBinaryMetadata
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
    d.rowid AS rowid, d.title AS title,
    d.authors AS authors, bm.data AS full_text
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
    """INSERT INTO
    document_title_authors_text_view_fts(document_title_authors_text_view_fts)
    VALUES('rebuild')""",
    doc=f"""This command first deletes the entire full-text index, then rebuilds it. {sqlite3_reference_href("https://sqlite.org/fts5.html#the_rebuild_command")}""",
    kind=StatementKind.INDEX,
    callable_=True,
    dependencies=[FTS_CREATE_TABLE],
)

FTS_OPTIMIZE = SqlStatement(
    "FTS_OPTIMIZE",
    """INSERT INTO
    document_title_authors_text_view_fts(document_title_authors_text_view_fts)
    VALUES('optimize')""",
    doc=f"""This command merges all individual b-trees that currently make up the full-text index into a single large b-tree structure. Because it reorganizes the entire <abbr title="Full-Text Search">FTS</abbr> index, the optimize command can take a long time to run. {sqlite3_reference_href("https://sqlite.org/fts5.html#the_optimize_command")}""",
    kind=StatementKind.INDEX,
    callable_=True,
    dependencies=[FTS_CREATE_TABLE],
)

FTS_INTEGRITY_CHECK = SqlStatement(
    "FTS_INTEGRITY_CHECK",
    """INSERT INTO
    document_title_authors_text_view_fts(document_title_authors_text_view_fts)
    VALUES('integrity-check')""",
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
    """CREATE VIRTUAL TABLE IF NOT EXISTS uuidtok USING fts3tokenize(
    'unicode61',
    "tokenchars=-1234567890abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "separators= "
);""",
    doc=f"""Create virtual tokenizer table that splits text into tokens, allowing you to find uuids in metadata text for reference indexing. {sqlite3_reference_href("https://www.sqlite.org/fts3.html#querying_tokenizers")}""",
    kind=(StatementKind.INDEX | StatementKind.TABLE),
    callable_=True,
)

CREATE_UNDOLOG = SqlStatement(
    "CREATE_UNDOLOG",
    """CREATE TABLE IF NOT EXISTS "undolog" (
        "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
        "action" TEXT NOT NULL,
        "tbl_name" TEXT NOT NULL,
        "sql" TEXT NOT NULL,
        "timestamp" DATETIME NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f', 'now'))
);""",
    doc=f"""Create undo log table {sqlite3_reference_href("https://sqlite.org/undoredo.html")}""",
    kind=StatementKind.TABLE,
    callable_=True,
    dependencies=[],
)

UNDOLOG_DELETE_BIG_ENTRIES = SqlStatement(
    "UNDOLOG_DELETE_BIG_ENTRIES",
    """DELETE FROM undolog WHERE length(sql AS BLOB) > 1000000;""",
    doc="Delete big binary files (> 1MiB) from undolog to free up space",
    kind=StatementKind.EXAMPLE,
    callable_=True,
    dependencies=[CREATE_UNDOLOG],
)

UNDOLOG_CREATE_TRIGGER_DOCUMENTS_INSERT = SqlStatement(
    "UNDOLOG_CREATE_TRIGGER_DOCUMENTS_INSERT",
    """CREATE TRIGGER doc_it
AFTER INSERT ON Documents
BEGIN
  INSERT INTO undolog(action,tbl_name,sql) VALUES('INSERT','Documents',
  'DELETE FROM Documents WHERE uuid='||quote(NEW.uuid));
END;""",
    doc="",
    kind=StatementKind.TRIGGER,
    callable_=True,
    dependencies=[CREATE_UNDOLOG],
)

UNDOLOG_CREATE_TRIGGER_DOCUMENTS_UPDATE = SqlStatement(
    "UNDOLOG_CREATE_TRIGGER_DOCUMENTS_UPDATE",
    """CREATE TRIGGER doc_ut
AFTER UPDATE ON Documents
BEGIN
  INSERT INTO undolog(action,tbl_name,sql) VALUES('UPDATE','Documents',
  'UPDATE Documents SET uuid='||quote(OLD.uuid)||',title='||quote(OLD.title)||',
  title_suffix='||quote(OLD.title_suffix)||',created='||quote(OLD.created)||',
  last_modified='||quote(OLD.last_modified)||'
   WHERE uuid='||quote(OLD.uuid));
END;""",
    doc="",
    kind=StatementKind.TRIGGER,
    callable_=True,
    dependencies=[CREATE_UNDOLOG],
)

UNDOLOG_CREATE_TRIGGER_DOCUMENTS_DELETE = SqlStatement(
    "UNDOLOG_CREATE_TRIGGER_DOCUMENTS_DELETE",
    """CREATE TRIGGER doc_dt
BEFORE DELETE ON Documents
BEGIN
  INSERT INTO undolog(action,tbl_name,sql) VALUES('DELETE','Documents',
  'INSERT INTO Documents(uuid,title,title_suffix,created,last_modified)
    VALUES('||OLD.uuid||','||quote(OLD.title)||','||quote(OLD.title_suffix)||
           ','||quote(OLD.created)||','||quote(OLD.last_modified)||')');
END;""",
    doc="",
    kind=StatementKind.TRIGGER,
    callable_=True,
    dependencies=[CREATE_UNDOLOG],
)

UNDOLOG_CREATE_TRIGGER_TEXTMETADATA_INSERT = SqlStatement(
    "UNDOLOG_CREATE_TRIGGER_TEXTMETADATA_INSERT",
    """CREATE TRIGGER text_it
AFTER INSERT ON TextMetadata
BEGIN
  INSERT INTO undolog(action,tbl_name,sql) VALUES('INSERT','TextMetadata',
  'DELETE FROM TextMetadata WHERE uuid='||quote(NEW.uuid));
END;""",
    doc="",
    kind=StatementKind.TRIGGER,
    callable_=True,
    dependencies=[CREATE_UNDOLOG],
)

UNDOLOG_CREATE_TRIGGER_TEXTMETADATA_UPDATE = SqlStatement(
    "UNDOLOG_CREATE_TRIGGER_TEXTMETADATA_UPDATE",
    """CREATE TRIGGER text_ut
AFTER UPDATE ON TextMetadata
BEGIN
  INSERT INTO undolog(action,tbl_name,sql)
  VALUES('UPDATE','TextMetadata','UPDATE TextMetadata SET
  uuid='||quote(OLD.uuid)||',name='||quote(OLD.name)||',data='||
  quote(OLD.data)||',created='||quote(OLD.created)||',last_modified='||
  quote(OLD.last_modified)||'
  WHERE uuid='||quote(OLD.uuid));
END;""",
    doc="",
    kind=StatementKind.TRIGGER,
    callable_=True,
    dependencies=[CREATE_UNDOLOG],
)

UNDOLOG_CREATE_TRIGGER_TEXTMETADATA_DELETE = SqlStatement(
    "UNDOLOG_CREATE_TRIGGER_TEXTMETADATA_DELETE",
    """CREATE TRIGGER text_dt
BEFORE DELETE ON TextMetadata
BEGIN
  INSERT INTO undolog(action,tbl_name,sql)
  VALUES('DELETE','TextMetadata','INSERT INTO
  TextMetadata(uuid,name,data,created,last_modified)
  VALUES('||OLD.uuid||','||quote(OLD.name)||','||quote(OLD.data)||
      ','||quote(OLD.created)||','||quote(OLD.last_modified)||')');
END;""",
    doc="",
    kind=StatementKind.TRIGGER,
    callable_=True,
    dependencies=[CREATE_UNDOLOG],
)

UNDOLOG_CREATE_TRIGGER_BINARYMETADATA_INSERT = SqlStatement(
    "UNDOLOG_CREATE_TRIGGER_BINARYMETADATA_INSERT",
    """CREATE TRIGGER binary_it
AFTER INSERT ON BinaryMetadata
BEGIN
  INSERT INTO undolog(action,tbl_name,sql)
  VALUES('INSERT','BinaryMetadata','DELETE FROM BinaryMetadata WHERE
  uuid='||quote(NEW.uuid));
END;""",
    doc="",
    kind=StatementKind.TRIGGER,
    callable_=True,
    dependencies=[CREATE_UNDOLOG],
)

UNDOLOG_CREATE_TRIGGER_BINARYMETADATA_UPDATE = SqlStatement(
    "UNDOLOG_CREATE_TRIGGER_BINARYMETADATA_UPDATE",
    """CREATE TRIGGER binary_ut
AFTER UPDATE ON BinaryMetadata
BEGIN
  INSERT INTO undolog(action,tbl_name,sql)
  VALUES('UPDATE','BinaryMetadata','UPDATE BinaryMetadata SET
  uuid='||quote(OLD.uuid)||',name='||quote(OLD.name)||',data='||
  quote(OLD.data)||',compressed='||quote(OLD.compressed)||
  ',created='||quote(OLD.created)||',last_modified='||
  quote(OLD.last_modified)||'
  WHERE uuid='||quote(OLD.uuid));
END;""",
    doc="",
    kind=StatementKind.TRIGGER,
    callable_=True,
    dependencies=[CREATE_UNDOLOG],
)

UNDOLOG_CREATE_TRIGGER_BINARYMETADATA_DELETE = SqlStatement(
    "UNDOLOG_CREATE_TRIGGER_BINARYMETADATA_DELETE",
    """CREATE TRIGGER binary_dt
BEFORE DELETE ON BinaryMetadata
BEGIN
  INSERT INTO undolog(action,tbl_name,sql)
  VALUES('DELETE','BinaryMetadata','INSERT INTO
  BinaryMetadata(uuid,name,data,compressed,created,last_modified)
  VALUES('||OLD.uuid||','||quote(OLD.name)||','||quote(OLD.data)||','||
  quote(OLD.compressed)||','||quote(OLD.created)||','||
  quote(OLD.last_modified)||')');
END;""",
    doc="",
    kind=StatementKind.TRIGGER,
    callable_=True,
    dependencies=[CREATE_UNDOLOG],
)

UNDOLOG_CREATE_TRIGGER_DOCUMENTHASTEXTMETADATA_INSERT = SqlStatement(
    "UNDOLOG_CREATE_TRIGGER_DOCUMENTHASTEXTMETADATA_INSERT",
    """CREATE TRIGGER has_text_it
AFTER INSERT ON DocumentHasTextMetadata
BEGIN
  INSERT INTO undolog(action,tbl_name,sql)
  VALUES('INSERT','DocumentHasTextMetadata',
  'DELETE FROM DocumentHasTextMetadata WHERE id='||NEW.id);
END;""",
    doc="",
    kind=StatementKind.TRIGGER,
    callable_=True,
    dependencies=[CREATE_UNDOLOG],
)

UNDOLOG_CREATE_TRIGGER_DOCUMENTHASTEXTMETADATA_UPDATE = SqlStatement(
    "UNDOLOG_CREATE_TRIGGER_DOCUMENTHASTEXTMETADATA_UPDATE",
    """CREATE TRIGGER has_text_ut
AFTER UPDATE ON DocumentHasTextMetadata
BEGIN
  INSERT INTO undolog(action,tbl_name,sql)
  VALUES('UPDATE','DocumentHasTextMetadata','UPDATE DocumentHasTextMetadata
     SET id='||OLD.id||',name='||quote(OLD.name)||',
     document_uuid='||quote(OLD.document_uuid)||',
     metadata_uuid='||quote(OLD.metadata_uuid)||',
     created='||quote(OLD.created)||',
     last_modified='||quote(OLD.last_modified)||'
   WHERE id='||OLD.id);
END;""",
    doc="",
    kind=StatementKind.TRIGGER,
    callable_=True,
    dependencies=[CREATE_UNDOLOG],
)

UNDOLOG_CREATE_TRIGGER_DOCUMENTHASTEXTMETADATA_DELETE = SqlStatement(
    "UNDOLOG_CREATE_TRIGGER_DOCUMENTHASTEXTMETADATA_DELETE",
    """CREATE TRIGGER has_text_dt
BEFORE DELETE ON DocumentHasTextMetadata
BEGIN
  INSERT INTO undolog(action,tbl_name,sql)
  VALUES('DELETE','DocumentHasTextMetadata','INSERT INTO
  DocumentHasTextMetadata(id,name,document_uuid,metadata_uuid,created,last_modified)
    VALUES('||OLD.id||','||quote(OLD.name)||','||
    quote(OLD.document_uuid)||','||quote(OLD.metadata_uuid)||',
    '||quote(OLD.created)||','||quote(OLD.last_modified)||')');
END;""",
    doc="",
    kind=StatementKind.TRIGGER,
    callable_=True,
    dependencies=[CREATE_UNDOLOG],
)

UNDOLOG_CREATE_TRIGGER_DOCUMENTHASBINARYMETADATA_INSERT = SqlStatement(
    "UNDOLOG_CREATE_TRIGGER_DOCUMENTHASBINARYMETADATA_INSERT",
    """CREATE TRIGGER has_binary_it
AFTER INSERT ON DocumentHasBinaryMetadata
BEGIN
  INSERT INTO undolog(action,tbl_name,sql)
  VALUES('INSERT','DocumentHasBinaryMetadata',
  'DELETE FROM DocumentHasBinaryMetadata WHERE id='||NEW.id);
END;""",
    doc="",
    kind=StatementKind.TRIGGER,
    callable_=True,
    dependencies=[CREATE_UNDOLOG],
)

UNDOLOG_CREATE_TRIGGER_DOCUMENTHASBINARYMETADATA_UPDATE = SqlStatement(
    "UNDOLOG_CREATE_TRIGGER_DOCUMENTHASBINARYMETADATA_UPDATE",
    """CREATE TRIGGER has_binary_ut
    AFTER UPDATE ON DocumentHasBinaryMetadata
BEGIN
  INSERT INTO undolog(action,tbl_name,sql)
  VALUES('UPDATE','DocumentHasBinaryMetadata','UPDATE DocumentHasBinaryMetadata
  SET
  id='||OLD.id||',name='||quote(OLD.name)||',document_uuid='||
  quote(OLD.document_uuid)||',metadata_uuid='||quote(OLD.metadata_uuid)||
  ',created='||quote(OLD.created)||',last_modified='||
  quote(OLD.last_modified)||'
   WHERE id='||OLD.id);
END;""",
    doc="",
    kind=StatementKind.TRIGGER,
    callable_=True,
    dependencies=[CREATE_UNDOLOG],
)

UNDOLOG_CREATE_TRIGGER_DOCUMENTHASBINARYMETADATA_DELETE = SqlStatement(
    "UNDOLOG_CREATE_TRIGGER_DOCUMENTHASBINARYMETADATA_DELETE",
    """CREATE TRIGGER has_binary_dt
    BEFORE DELETE ON DocumentHasBinaryMetadata
BEGIN
  INSERT INTO undolog(action,tbl_name,sql)
  VALUES('DELETE','DocumentHasBinaryMetadata','INSERT INTO
  DocumentHasBinaryMetadata(id,name,document_uuid,metadata_uuid,created,last_modified)
  VALUES('||OLD.id||','||quote(OLD.name)||','||quote(OLD.document_uuid)||
  ','||quote(OLD.metadata_uuid)||','||quote(OLD.created)||','||
  quote(OLD.last_modified)||')');
END;""",
    doc="",
    kind=StatementKind.TRIGGER,
    callable_=True,
    dependencies=[CREATE_UNDOLOG],
)


UPDATE_LAST_MODIFIED_DOCUMENT = SqlStatement(
    "UPDATE_LAST_MODIFIED_DOCUMENT",
    """CREATE TRIGGER update_last_modified_document
    AFTER UPDATE ON Documents
BEGIN
    UPDATE Documents
    SET "last_modified" = strftime('%Y-%m-%d %H:%M:%f', 'now')
    WHERE uuid = NEW.uuid;
END;""",
    doc="Update Document last_modified field on UPDATE",
    kind=StatementKind.TRIGGER,
    callable_=True,
    dependencies=[],
)


UPDATE_LAST_MODIFIED_TEXT = SqlStatement(
    "UPDATE_LAST_MODIFIED_TEXT",
    """CREATE TRIGGER update_last_modified_text
    AFTER UPDATE ON TextMetadata
BEGIN
    UPDATE TextMetadata
    SET "last_modified" = strftime('%Y-%m-%d %H:%M:%f', 'now')
    WHERE uuid = NEW.uuid;
END;""",
    doc="Update TextMetadata last_modified field on UPDATE",
    kind=StatementKind.TRIGGER,
    callable_=True,
    dependencies=[],
)

UPDATE_LAST_MODIFIED_BINARY = SqlStatement(
    "UPDATE_LAST_MODIFIED_BINARY",
    """CREATE TRIGGER update_last_modified_binary
    AFTER UPDATE ON BinaryMetadata
BEGIN
    UPDATE BinaryMetadata
    SET "last_modified" = strftime('%Y-%m-%d %H:%M:%f', 'now')
    WHERE uuid = NEW.uuid;
END;""",
    doc="Update BinaryMetadata last_modified field on UPDATE",
    kind=StatementKind.TRIGGER,
    callable_=True,
    dependencies=[],
)

UPDATE_LAST_MODIFIED_HAS_TEXT = SqlStatement(
    "UPDATE_LAST_MODIFIED_HAS_TEXT",
    """CREATE TRIGGER update_last_modified_has_text
    AFTER UPDATE ON DocumentHasTextMetadata
BEGIN
    UPDATE DocumentHasTextMetadata
    SET "last_modified" = strftime('%Y-%m-%d %H:%M:%f', 'now')
    WHERE id = NEW.id;
END;""",
    doc="Update DocumentHasTextMetadata last_modified field on UPDATE",
    kind=StatementKind.TRIGGER,
    callable_=True,
    dependencies=[],
)

UPDATE_LAST_MODIFIED_HAS_BINARY = SqlStatement(
    "UPDATE_LAST_MODIFIED_HAS_BINARY",
    """CREATE TRIGGER update_last_modified_has_binary
    AFTER UPDATE ON DocumentHasBinaryMetadata
BEGIN
    UPDATE DocumentHasBinaryMetadata
    SET "last_modified" = strftime('%Y-%m-%d %H:%M:%f', 'now')
    WHERE id = NEW.id;
END;""",
    doc="Update DocumentHasBinaryMetadata last_modified field on UPDATE",
    kind=StatementKind.TRIGGER,
    callable_=True,
    dependencies=[],
)

QUERY_VALID_JSON_NAMES = SqlStatement(
    "QUERY_VALID_JSON_NAMES",
    """SELECT uuid, name FROM BinaryMetadata WHERE json_valid(name);""",
    doc="Search for valid JSON names.",
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
    doc="Select text files.",
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
    doc="Match against uuid string with hyphens.",
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
    name=json_object('content_type', 'application/pdf',
    'filename', 'file.pdf', 'size', LENGTH(readfile('file.pdf'))),
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

REMOVE_DUPLICATE_ROWS = SqlStatement(
    "REMOVE_DUPLICATE_ROWS",
    """DELETE FROM table WHERE rowid NOT IN
    (SELECT MIN(rowid) FROM table
     GROUP BY unique_column_1, unique_column_2;""",
    doc=f"""If you need to remove duplicate rows, adapt this statement to your table. The <code>MIN(rowid)</code> can be replaced by just <code>rowid</code> if you don't necessarily want the smallest row ids to survive.""",
    callable_=False,
    kind=(StatementKind.CLI | StatementKind.EXAMPLE),
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

UNDO_SCHEMA = [
    CREATE_UNDOLOG,
    UNDOLOG_DELETE_BIG_ENTRIES,
    UNDOLOG_CREATE_TRIGGER_DOCUMENTS_INSERT,
    UNDOLOG_CREATE_TRIGGER_DOCUMENTS_UPDATE,
    UNDOLOG_CREATE_TRIGGER_DOCUMENTS_DELETE,
    UNDOLOG_CREATE_TRIGGER_TEXTMETADATA_INSERT,
    UNDOLOG_CREATE_TRIGGER_TEXTMETADATA_UPDATE,
    UNDOLOG_CREATE_TRIGGER_TEXTMETADATA_DELETE,
    UNDOLOG_CREATE_TRIGGER_BINARYMETADATA_INSERT,
    UNDOLOG_CREATE_TRIGGER_BINARYMETADATA_UPDATE,
    UNDOLOG_CREATE_TRIGGER_BINARYMETADATA_DELETE,
    UNDOLOG_CREATE_TRIGGER_DOCUMENTHASTEXTMETADATA_INSERT,
    UNDOLOG_CREATE_TRIGGER_DOCUMENTHASTEXTMETADATA_UPDATE,
    UNDOLOG_CREATE_TRIGGER_DOCUMENTHASTEXTMETADATA_DELETE,
    UNDOLOG_CREATE_TRIGGER_DOCUMENTHASBINARYMETADATA_INSERT,
    UNDOLOG_CREATE_TRIGGER_DOCUMENTHASBINARYMETADATA_UPDATE,
    UNDOLOG_CREATE_TRIGGER_DOCUMENTHASBINARYMETADATA_DELETE,
]


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


def get_exports():
    try:
        import sql_statements
    except:
        from bibliothecula import sql_statements

        print(sql_statements)
        pass
    try:
        from bibliothecula.graphlib import TopologicalSorter
    except:
        from graphlib import TopologicalSorter

    def get_keyword(s):
        return s.statement.split(maxsplit=1)[0].lower()

    exports = []
    seen = set()
    stmts = {
        item: getattr(sql_statements, item, None)
        for item in sorted(dir(sql_statements))
        if not item.startswith("__")
        and type(getattr(sql_statements, item, None)) in [SqlStatement, list]
    }
    ts = TopologicalSorter()
    for c in stmts["CORE_SCHEMA"]:
        ts.add(c, *c.dependencies)
        seen.add(c.get_id())
    exports += list(ts.static_order())

    ts = TopologicalSorter()
    for c in stmts["FTS_SCHEMA"]:
        ts.add(c, *c.dependencies)
        seen.add(c.get_id())
    order = list(ts.static_order())
    exports += [
        s for s in order if s in stmts["FTS_SCHEMA"] and get_keyword(s) == "create"
    ]
    appendix = [
        s for s in order if s in stmts["FTS_SCHEMA"] and not get_keyword(s) == "create"
    ]
    exports = {
        "main": exports,
        "appendix": appendix,
    }
    ets = TopologicalSorter()
    for k in stmts:
        c = stmts[k]
        if isinstance(c, SqlStatement):
            if c.get_id() in seen:
                continue
            ets.add(c, *c.dependencies)
    order = list(ets.static_order())
    extended_exports = [
        e for e in order if e.get_id() not in seen and get_keyword(e) == "create"
    ]
    appendix = [
        e for e in order if e.get_id() not in seen and not get_keyword(e) == "create"
    ]
    extended_exports = {
        "main": extended_exports,
        "appendix": appendix,
    }
    return (exports, extended_exports)


if __name__ == "__main__":
    # execute only if run as a script
    from utils import Textractor
    import sql_statements
    import argparse
    import textwrap
    from pathlib import Path
    from sql_statements import SqlStatement, StatementKind

    def print_exports(exports):
        def get_summary(exp, doc):
            if exp.doc is not None and len(exp.doc) > 0:
                return textwrap.shorten(doc, width=72, placeholder="...")
            else:
                return textwrap.shorten(exp.statement, width=72, placeholder="...")

        def print_comment(comment, header=None):
            output = ""
            if header is not None:
                output += "/* "
                output += header
                output += "\n"
                output += comment
                output += " */\n"
            else:
                output += "/* "
                output += comment
                output += " */\n"
            return output

        def get_toc(rows):
            widths = [len(max(columns, key=len)) for columns in zip(*tocs)]
            header, data = rows[0], rows[1:]
            output = " | ".join(
                format(title, "%ds" % width) for width, title in zip(widths, header)
            ).rstrip()
            # - print the separator
            output += "\n"
            output += "-+-".join("-" * width for width in widths).rstrip()
            output += "\n"
            # - print the data
            for row in data:
                output += " | ".join(
                    format(cdata, "%ds" % width) for width, cdata in zip(widths, row)
                ).rstrip()
                output += "\n"
            return output

        output_toc = ""
        tocs = [("id", "summary")]
        output = ""
        appendix = exports["appendix"]
        html_parser = Textractor()
        html_parser.extract_href = True
        for exp in exports["main"]:
            html = ""
            if len(exp.doc) > 0:
                html_parser.reset()
                html_parser.ignore = 0
                html_parser.feed(exp.doc)
                html = html_parser.output.strip()

                output += print_comment(
                    "\n".join(map(lambda line: f" {line}", textwrap.wrap(html))),
                    header=exp.get_id(),
                )
            else:
                output += print_comment(exp.get_id())
            output_toc += f"- {exp.get_id()}\t{get_summary(exp, html)}"
            output_toc += "\n"
            tocs.append((exp.get_id(), get_summary(exp, html)))
            output += exp.statement
            if not exp.statement.rstrip().endswith(";"):
                output += ";"
            output += "\n\n"
        main_toc = get_toc(tocs)
        tocs = [("id", "summary")]
        if len(appendix) > 0:
            output_toc += "\n Appendix: useful statements\n\n"
            output += print_comment("Appendix: useful statements")
            output += "\n\n"
        for a in appendix:
            html = ""
            a_output = "\n"
            if len(a.doc) > 0:
                html_parser.reset()
                html_parser.ignore = 0
                html_parser.feed(a.doc)
                html = html_parser.output.strip()
                a_output += "\n".join(map(lambda line: f" {line}", textwrap.wrap(html)))
                a_output += "\n"
            output_toc += f"- {a.get_id()}\t{get_summary(a,html)}"
            output_toc += "\n"
            tocs.append((a.get_id(), get_summary(a, html)))
            a_output += "\n"
            a_output += a.statement
            if not a.statement.rstrip().endswith(";"):
                a_output += ";"
            output += print_comment(a_output, header=a.get_id())
            output += "\n\n"
        if len(appendix) > 0:
            adx_toc = "\nAppendix: useful statements\n\n" + get_toc(tocs)
            main_toc += "\n"
            main_toc += adx_toc
        return print_comment(main_toc, header="Contents\n") + "\n" + output

    parser = argparse.ArgumentParser(
        description="Export SQL statement documentation to .sql files."
    )
    parser.add_argument("main_schema", type=str, help="the main schema output filename")
    parser.add_argument(
        "extended_schema", type=str, help="the extended schema output filename"
    )
    parser.add_argument(
        "-f",
        "--format",
        type=str,
        choices=["sql", "md"],
        default="sql",
        help="output format",
    )
    parser.add_argument(
        "-c",
        "--confirm-overwrite",
        action="store_true",
        default=False,
        help="overwrite if existing",
    )

    args = parser.parse_args()
    main_schema = Path(args.main_schema)
    if main_schema.is_dir():
        raise IsADirectoryError(f"{main_schema} is a directory.")
    if main_schema.exists() and not args.confirm_overwrite:
        raise FileExistsError(f"{main_schema} already exists.")
    extended_schema = Path(args.extended_schema)
    if extended_schema.is_dir():
        raise IsADirectoryError(f"{extended_schema} is a directory.")
    if extended_schema.exists() and not args.confirm_overwrite:
        raise FileExistsError(f"{extended_schema} already exists.")

    (exports, extended_exports) = get_exports()

    if args.format == "sql":
        schema_output = print_exports(exports)
        extended_schema_output = print_exports(extended_exports).strip()
    else:

        def make_table(level, title, rows, table_caption=None):
            output = "#" * level + " " + title + "\n"
            if table_caption:
                table_caption = f"\n<caption>{table_caption}</caption>\n"
            else:
                table_caption = ""
            output += f"""
<table>{table_caption}
<thead>
<tr>
<th>statement</th>
<th>kinds</th>
</tr>
</thead>
<tbody>"""
            for r in rows:
                output += f"""
            <tr><td class="doc">

#### `{r.get_id()}`

{r.doc}

```sql
{r.statement}
```
</td>
<td>{', '.join(map(lambda k: f'<kbd>{k[1]}</kbd>',r.keywords()))}</td>
</tr>"""
            output += """</tbody></table>"""
            return output
            schema_output += """</tbody></table>"""

        schema_output = make_table(1, "The core bibliothecula schema.", exports["main"])
        extended_schema_output = make_table(
            1,
            "Extended bibliothecula schema.",
            extended_exports["main"],
            table_caption="Optional but useful triggers, indexes, etc.",
        )
        extended_schema_output += "\n\n"
        extended_schema_output += make_table(
            2,
            "Appendix.",
            extended_exports["appendix"],
            table_caption="useful queries cookbook",
        )

    with open(main_schema, "w") as f:
        f.write(schema_output.strip())
    with open(extended_schema, "w") as f:
        f.write(extended_schema_output.strip())
