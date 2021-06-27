/* Contents

id                                  | summary
------------------------------------+-------------------------------------------------------------------------
CREATE_DOCUMENTS                    | CREATE TABLE IF NOT EXISTS "Documents" ( "uuid" CHARACTER(32) NOT...
CREATE_TEXTMETADATA                 | CREATE TABLE IF NOT EXISTS "TextMetadata" ( "uuid" CHARACTER(32) NOT...
CREATE_BINARYMETADATA               | CREATE TABLE IF NOT EXISTS "BinaryMetadata" ( "uuid" CHARACTER(32)...
CREATE_DOCUMENTHASTEXTMETADATA      | CREATE TABLE IF NOT EXISTS "DocumentHasTextMetadata" ( "id" INTEGER...
CREATE_DOCUMENTHASBINARYMETADATA    | CREATE TABLE IF NOT EXISTS "DocumentHasBinaryMetadata" ( "id" INTEGER...
CREATE_VIEW_DOCUMENTS_TITLE_AUTHORS | Auxiliary view for use in document_title_authors_text_view_fts index....
FTS_CREATE_TABLE                    | Create a full-text search index using the fts5 module....
FTS_CREATE_INSERT_TRIGGER           | Trigger to insert full text data when a DocumentHasBinaryMetadata row...
FTS_CREATE_DELETE_TRIGGER           | Trigger to remove a document's full text from the full text search...
 */

/* CREATE_DOCUMENTS */
CREATE TABLE IF NOT EXISTS "Documents" (
        "uuid" CHARACTER(32) NOT NULL PRIMARY KEY,
        "title" TEXT NOT NULL,
        "title_suffix" TEXT DEFAULT NULL, -- disambiguate documents with matching titles
        "created" DATETIME NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f', 'now')),
        "last_modified" DATETIME NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f', 'now')),
        CONSTRAINT unique_title UNIQUE ("title", "title_suffix")
);

/* CREATE_TEXTMETADATA */
CREATE TABLE IF NOT EXISTS "TextMetadata" (
        "uuid" CHARACTER(32) NOT NULL PRIMARY KEY,
        "name" TEXT NULL,
        "data" TEXT NOT NULL,
        "created" DATETIME NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f', 'now')),
        "last_modified" DATETIME NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f', 'now')),
        CONSTRAINT uniqueness UNIQUE ("name", "data")
);

/* CREATE_BINARYMETADATA */
CREATE TABLE IF NOT EXISTS "BinaryMetadata" (
        "uuid" CHARACTER(32) NOT NULL PRIMARY KEY,
        "name" TEXT NULL,
        "data" BLOB NOT NULL,
        "compressed" BOOLEAN NOT NULL DEFAULT (0),
        "created" DATETIME NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f', 'now')),
        "last_modified" DATETIME NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f', 'now')),
        CONSTRAINT uniqueness UNIQUE ("name", "data")
);

/* CREATE_DOCUMENTHASTEXTMETADATA */
CREATE TABLE IF NOT EXISTS "DocumentHasTextMetadata" (
        "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
        "name" TEXT NOT NULL,
        "document_uuid" CHARACTER(32) NOT NULL
            REFERENCES "Documents" ("uuid") ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
        "metadata_uuid" CHARACTER(32) NOT NULL
            REFERENCES "TextMetadata" ("uuid") ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
        "created" DATETIME NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f', 'now')),
        "last_modified" DATETIME NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f', 'now')),
        CONSTRAINT uniqueness UNIQUE ("name", "document_uuid", "metadata_uuid")
);

/* CREATE_DOCUMENTHASBINARYMETADATA */
CREATE TABLE IF NOT EXISTS "DocumentHasBinaryMetadata" (
        "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
        "name" TEXT NOT NULL,
        "document_uuid" CHARACTER(32) NOT NULL
            REFERENCES "Documents" ("uuid") ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
        "metadata_uuid" CHARACTER(32) NOT NULL
            REFERENCES "BinaryMetadata" ("uuid") ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
        "created" DATETIME NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f', 'now')),
        "last_modified" DATETIME NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f', 'now')),
        CONSTRAINT uniqueness UNIQUE ("name", "document_uuid", "metadata_uuid")
);

/* CREATE_VIEW_DOCUMENTS_TITLE_AUTHORS
 Auxiliary view for use in document_title_authors_text_view_fts index.
 Returns document title and a NULL byte separated string with all
 authors or NULL for all documents.
 https://sqlite.org/lang_createview.html sqlite3 reference for for
 creating views */
CREATE VIEW document_title_authors (rowid, title, authors) AS
SELECT uuid, title, authors
FROM
    Documents AS d
    LEFT JOIN (SELECT
            document_uuid,
            GROUP_CONCAT (data, '\0') AS authors
        FROM
            DocumentHasTextMetadata AS dhtm
            JOIN TextMetadata AS tm ON dhtm.metadata_uuid = tm.uuid
        WHERE
            tm.name = 'author'
        GROUP BY
            document_uuid) AS authors ON d.uuid = authors.document_uuid;

/* FTS_CREATE_TABLE
 Create a full-text search index using the fts5 module.
 https://sqlite.org/fts5.html sqlite3 reference */
CREATE VIRTUAL TABLE IF NOT EXISTS document_title_authors_text_view_fts
    USING fts5(title, authors, full_text, uuid UNINDEXED);

/* FTS_CREATE_INSERT_TRIGGER
 Trigger to insert full text data when a DocumentHasBinaryMetadata row
 for a full-text BinaryMetadata is created.
 https://sqlite.org/lang_createtrigger.html sqlite3 reference for for
 creating triggers */
CREATE TRIGGER insert_full_text_trigger
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
END;

/* FTS_CREATE_DELETE_TRIGGER
 Trigger to remove a document's full text from the full text search
 table when the full-text binary metadata is deleted.
 https://sqlite.org/lang_createtrigger.html sqlite3 reference for for
 creating triggers */
CREATE TRIGGER IF NOT EXISTS delete_full_text_trigger
       AFTER DELETE ON DocumentHasBinaryMetadata
        WHEN OLD.name = 'full-text'
       BEGIN
       DELETE FROM document_title_authors_text_view_fts
       WHERE uuid = OLD.document_uuid;
END;