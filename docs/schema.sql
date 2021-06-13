CREATE TABLE IF NOT EXISTS "Documents" (
        "uuid" CHAR(32) NOT NULL PRIMARY KEY,
        "title" TEXT NOT NULL,
        "title_suffix" TEXT,
        "created" datetime NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f',
                'now')),
        "last_modified" datetime NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f',
                'now'))
);

CREATE TABLE IF NOT EXISTS "TextMetadata" (
        "uuid" char(32) NOT NULL PRIMARY KEY,
        "name" text NULL,
        "data" text NOT NULL,
        "created" datetime NOT NULL,
        "last_modified" datetime NOT NULL
);

CREATE TABLE IF NOT EXISTS "DocumentHasTextMetadata" (
        "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
        "name" TEXT NOT NULL,
        "document_uuid" char(32) NOT NULL REFERENCES "Documents" ("uuid") DEFERRABLE INITIALLY DEFERRED,
        "metadata_uuid" char(32) NOT NULL REFERENCES "TextMetadata" ("uuid") DEFERRABLE INITIALLY DEFERRED,
        "created" datetime NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f',
                'now')),
        "last_modified" datetime NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f',
                'now'))
);

CREATE TABLE IF NOT EXISTS "BinaryMetadata" (
        "uuid" char(32) NOT NULL PRIMARY KEY,
        "name" text NULL,
        "data" BLOB NOT NULL,
        "created" datetime NOT NULL,
        "last_modified" datetime NOT NULL
);


CREATE TABLE IF NOT EXISTS "DocumentHasBinaryMetadata" (
        "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
        "name" TEXT NOT NULL,
        "document_uuid" char(32) NOT NULL REFERENCES "Documents" ("uuid") DEFERRABLE INITIALLY DEFERRED,
        "metadata_uuid" char(32) NOT NULL REFERENCES "BinaryMetadata" ("uuid") DEFERRABLE INITIALLY DEFERRED,
        "created" datetime NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f',
                'now')),
        "last_modified" datetime NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f',
                'now'))
);

/* document_title_authors_text_view_fts(title,authors,full_text,uuid) */
CREATE VIRTUAL TABLE document_title_authors_text_view_fts
USING fts5 (
    title,
    authors,
    full_text,
    uuid UNINDEXED)
;

/* document_title_authors(rowid,title,authors) */
CREATE VIEW document_title_authors (
    rowid,
    title,
    authors) AS
SELECT
    *
FROM
    document_title_without_authors
UNION
SELECT
    *
FROM
    document_title_with_authors
;

/* document_title_authors_text_view(rowid,title,authors,full_text) */
CREATE VIEW document_title_authors_text_view (
    rowid,
    title,
    authors,
    full_text) AS
SELECT
    d.uuid AS uuid,
    d.title AS title,
    GROUP_CONCAT (
        authors.author) AS authors,
    bm.data AS full_text
FROM
    Documents AS d,
    DocumentHasBinaryMetadata AS dhbm,
    BinaryMetadata AS bm,
    (
        SELECT
            d.uuid AS uuid,
            tm.data AS author
        FROM
            Documents AS d,
            TextMetadata AS tm,
            DocumentHasTextMetadata AS dhtm
        WHERE
            dhtm.document_uuid = d.uuid
            AND dhtm.metadata_uuid = tm.uuid
            AND tm.name = 'author') AS authors
WHERE
    bm.uuid = dhbm.metadata_uuid
    AND d.uuid = dhbm.document_uuid
    AND bm.name = 'full-text'
    AND authors.uuid = d.uuid
GROUP BY
    d.uuid
;

/* document_title_without_authors(rowid,title,authors) */
CREATE VIEW document_title_without_authors (
    rowid,
    title,
    authors) AS
SELECT
    d.uuid AS uuid,
    d.title AS title,
    NULL AS authors
FROM
    Documents AS d
WHERE
    NOT EXISTS (
        SELECT
            *
        FROM
            TextMetadata AS t,
            DocumentHasTextMetadata AS dt
        WHERE
            t.name = 'author'
            AND t.uuid = dt.metadata_uuid
            AND dt.document_uuid = d.uuid)
;

/* document_title_with_authors(rowid,title,authors) */
CREATE VIEW document_title_with_authors (
    rowid,
    title,
    authors) AS
SELECT
    d.uuid AS uuid,
    d.title AS title,
    GROUP_CONCAT (
        authors.author) AS authors
FROM
    Documents AS d,
    (
        SELECT
            d.uuid AS uuid,
            tm.data AS author
        FROM
            Documents AS d,
            TextMetadata AS tm,
            DocumentHasTextMetadata AS dhtm
        WHERE
            dhtm.document_uuid = d.uuid
            AND dhtm.metadata_uuid = tm.uuid
            AND tm.name = 'author') AS authors
WHERE
    authors.uuid = d.uuid
GROUP BY
    d.uuid
;

CREATE TRIGGER delete_full_text_trigger AFTER DELETE ON DocumentHasBinaryMetadata
WHEN EXISTS (
        SELECT
            *
        FROM
            BinaryMetadata AS bm
        WHERE
            OLD.metadata_uuid = bm.uuid
            AND bm.name = 'full-text')
BEGIN
    DELETE
FROM
    document_title_authors_text_view_fts
WHERE
    uuid = OLD.document_uuid;
END;

CREATE TRIGGER insert_full_text_trigger AFTER INSERT ON DocumentHasBinaryMetadata
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
    document_title_authors AS d
    JOIN BinaryMetadata AS bm ON bm.uuid = NEW.metadata_uuid
WHERE
    d.rowid = NEW.document_uuid
    AND bm.name = 'full-text'
    AND bm.uuid = NEW.metadata_uuid;
END;

/* uuidtok(input,token,start,"end",position) */
CREATE VIRTUAL TABLE uuidtok
USING fts3tokenize (
    'unicode61',
    "tokenchars=-1234567890abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "separators= ")
;

