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
        "created" datetime NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f',
                'now')),
        "last_modified" datetime NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f',
                'now'))
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
        "created" datetime NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f',
                'now')),
        "last_modified" datetime NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f',
                'now'))
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
    uuid UNINDEXED
);

/* document_title_authors(rowid,title,authors) */
CREATE VIEW document_title_authors (
    rowid,
    title,
    authors) AS
SELECT
    uuid,
    title,
    authors
FROM
    Documents AS d
    LEFT JOIN (
        SELECT
            document_uuid,
            GROUP_CONCAT (data,
                '\0') AS authors
        FROM
            DocumentHasTextMetadata AS dhtm
            JOIN TextMetadata AS tm ON dhtm.metadata_uuid = tm.uuid
        WHERE
            tm.name = 'author'
        GROUP BY
            document_uuid) AS authors ON d.uuid = authors.document_uuid;

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
    document_title_authors AS d,
    BinaryMetadata AS bm
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
    "separators= "
);

