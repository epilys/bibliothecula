CREATE TABLE "Documents" (
    "uuid" CHARACTER (32) NOT NULL PRIMARY KEY,
    "title" TEXT NOT NULL,
    "title_suffix" TEXT DEFAULT NULL,
    "created" DATETIME NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f', 'now')),
    "last_modified" DATETIME NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f', 'now')),
    CONSTRAINT unique_title UNIQUE ("title", "title_suffix")
);

CREATE TABLE "TextMetadata" (
    "uuid" CHARACTER (32) NOT NULL PRIMARY KEY,
    "name" TEXT NULL,
    "data" TEXT NOT NULL,
    "created" DATETIME NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f', 'now')),
    "last_modified" DATETIME NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f', 'now')),
    CONSTRAINT uniqueness UNIQUE ("name", "data")
);

CREATE TABLE "BinaryMetadata" (
    "uuid" CHARACTER (32) NOT NULL PRIMARY KEY,
    "name" TEXT NULL,
    "data" BLOB NOT NULL,
    "compressed" BOOLEAN NOT NULL DEFAULT (0),
    "created" DATETIME NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f', 'now')),
    "last_modified" DATETIME NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f', 'now')),
    CONSTRAINT uniqueness UNIQUE ("name", "data")
);

CREATE TABLE "DocumentHasTextMetadata" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "name" TEXT NOT NULL,
    "document_uuid" CHARACTER (32) NOT NULL REFERENCES "Documents" ("uuid") ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
    "metadata_uuid" CHARACTER (32) NOT NULL REFERENCES "TextMetadata" ("uuid") ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
    "created" DATETIME NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f', 'now')),
    "last_modified" DATETIME NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f', 'now')),
    CONSTRAINT uniqueness UNIQUE ("name", "document_uuid", "metadata_uuid")
);

CREATE TABLE "DocumentHasBinaryMetadata" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "name" TEXT NOT NULL,
    "document_uuid" CHARACTER (32) NOT NULL REFERENCES "Documents" ("uuid") ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
    "metadata_uuid" CHARACTER (32) NOT NULL REFERENCES "BinaryMetadata" ("uuid") ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
    "created" DATETIME NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f', 'now')),
    "last_modified" DATETIME NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f', 'now')),
    CONSTRAINT uniqueness UNIQUE ("name", "document_uuid", "metadata_uuid")
);

CREATE VIRTUAL TABLE IF NOT EXISTS zettel_fts
    USING fts5 (title, filename, full_text, uuid UNINDEXED);

CREATE TRIGGER fts_insert AFTER INSERT ON BinaryMetadata
WHEN json_valid (NEW.name)
     AND json_extract (NEW.name, '$.content_type') LIKE "%text/%"
BEGIN
    INSERT INTO zettel_fts (uuid, title, filename, full_text)
    VALUES (NEW.uuid, NEW.name, json_extract (NEW.name, '$.filename'), NEW.data);
END;

CREATE VIRTUAL TABLE uuidtok
USING fts3tokenize (
    'unicode61',
    "tokenchars=-1234567890abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "separators= "
);

CREATE VIRTUAL TABLE refs_fts
USING fts5 (referrer, target);

CREATE TRIGGER insert_ref_trigger AFTER INSERT ON BinaryMetadata
WHEN json_valid (NEW.name)
    AND json_extract (NEW.name, '$.content_type') LIKE "%text/%"
BEGIN
    INSERT INTO refs_fts (target, referrer)
SELECT DISTINCT
    REPLACE(tok.token, '-', '') AS target,
    b.uuid AS referrer
FROM
    uuidtok AS tok,
    BinaryMetadata AS b
WHERE
    tok.input = b.data
    AND b.uuid = NEW.uuid
    AND LENGTH(REPLACE(tok.token, '-', '')) = 32
    AND EXISTS (SELECT * FROM BinaryMetadata WHERE uuid = REPLACE(tok.token, '-', ''));
END;
