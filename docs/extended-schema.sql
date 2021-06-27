/* Contents

id                                                      | summary
--------------------------------------------------------+-------------------------------------------------------------------------
CREATE_BACKREF_INDEX                                    | Create backref index.
CREATE_UNDOLOG                                          | Create undo log table https://sqlite.org/undoredo.html sqlite3 reference
CREATE_UUID_TOKENIZER                                   | Create virtual tokenizer table that splits text into tokens, allowing...
UPDATE_LAST_MODIFIED_BINARY                             | Update BinaryMetadata last_modified field on UPDATE
UPDATE_LAST_MODIFIED_DOCUMENT                           | Update Document last_modified field on UPDATE
UPDATE_LAST_MODIFIED_HAS_BINARY                         | Update DocumentHasBinaryMetadata last_modified field on UPDATE
UPDATE_LAST_MODIFIED_HAS_TEXT                           | Update DocumentHasTextMetadata last_modified field on UPDATE
UPDATE_LAST_MODIFIED_TEXT                               | Update TextMetadata last_modified field on UPDATE
UNDOLOG_CREATE_TRIGGER_BINARYMETADATA_DELETE            | CREATE TRIGGER binary_dt BEFORE DELETE ON BinaryMetadata BEGIN INSERT...
UNDOLOG_CREATE_TRIGGER_BINARYMETADATA_INSERT            | CREATE TRIGGER binary_it AFTER INSERT ON BinaryMetadata BEGIN INSERT...
UNDOLOG_CREATE_TRIGGER_BINARYMETADATA_UPDATE            | CREATE TRIGGER binary_ut AFTER UPDATE ON BinaryMetadata BEGIN INSERT...
UNDOLOG_CREATE_TRIGGER_DOCUMENTHASBINARYMETADATA_DELETE | CREATE TRIGGER has_binary_dt BEFORE DELETE ON...
UNDOLOG_CREATE_TRIGGER_DOCUMENTHASBINARYMETADATA_INSERT | CREATE TRIGGER has_binary_it AFTER INSERT ON...
UNDOLOG_CREATE_TRIGGER_DOCUMENTHASBINARYMETADATA_UPDATE | CREATE TRIGGER has_binary_ut AFTER UPDATE ON...
UNDOLOG_CREATE_TRIGGER_DOCUMENTHASTEXTMETADATA_DELETE   | CREATE TRIGGER has_text_dt BEFORE DELETE ON DocumentHasTextMetadata...
UNDOLOG_CREATE_TRIGGER_DOCUMENTHASTEXTMETADATA_INSERT   | CREATE TRIGGER has_text_it AFTER INSERT ON DocumentHasTextMetadata...
UNDOLOG_CREATE_TRIGGER_DOCUMENTHASTEXTMETADATA_UPDATE   | CREATE TRIGGER has_text_ut AFTER UPDATE ON DocumentHasTextMetadata...
UNDOLOG_CREATE_TRIGGER_DOCUMENTS_DELETE                 | CREATE TRIGGER doc_dt BEFORE DELETE ON Documents BEGIN INSERT INTO...
UNDOLOG_CREATE_TRIGGER_DOCUMENTS_INSERT                 | CREATE TRIGGER doc_it AFTER INSERT ON Documents BEGIN INSERT INTO...
UNDOLOG_CREATE_TRIGGER_DOCUMENTS_UPDATE                 | CREATE TRIGGER doc_ut AFTER UPDATE ON Documents BEGIN INSERT INTO...
UNDOLOG_CREATE_TRIGGER_TEXTMETADATA_DELETE              | CREATE TRIGGER text_dt BEFORE DELETE ON TextMetadata BEGIN INSERT...
UNDOLOG_CREATE_TRIGGER_TEXTMETADATA_INSERT              | CREATE TRIGGER text_it AFTER INSERT ON TextMetadata BEGIN INSERT INTO...
UNDOLOG_CREATE_TRIGGER_TEXTMETADATA_UPDATE              | CREATE TRIGGER text_ut AFTER UPDATE ON TextMetadata BEGIN INSERT INTO...


Appendix: useful statements

id                             | summary
-------------------------------+-------------------------------------------------------------------------
CLI_EDIT_FILE                  | Edit any binary BLOB with the edit() function in the CLI....
CLI_EXCTRACT_FILE              | Exctract a binary BLOB from any column using the CLI....
CLI_INSERT_FILE                | The sqlite3 CLI has some special I/O function to facilate reading and...
CLI_VIEW_FILE                  | View any binary BLOB with the edit() function in the CLI by ignoring...
REMOVE_DUPLICATE_ROWS          | If you need to remove duplicate rows, adapt this statement to your...
UNDOLOG_DELETE_BIG_ENTRIES     | Delete big binary files (> 1MiB) from undolog to free up space
UNDOLOG_QUERY_SIZE             | Query total size of undolog table.
FTS_INTEGRITY_CHECK            | This command is used to verify that the full-text index is internally...
FTS_OPTIMIZE                   | This command merges all individual b-trees that currently make up the...
FTS_REBUILD                    | This command first deletes the entire full-text index, then rebuilds...
FTS_SEARCH                     | This command queries the full-text search index for documents....
FTS_SELECT_CONFIG              | This command returns the values of persistent configuration...
QUERY_UUID_WITH_HYPHENS        | Match against uuid string with hyphens.
QUERY_BACKREFS_FROM_TEXT_FILES | Find backreferences from plain text files.
QUERY_BACKREF_CANDIDATES       | SELECT DISTINCT token FROM uuidtok WHERE input = (SELECT data FROM...
QUERY_TEXT_FILES               | Select text files.
QUERY_VALID_JSON_NAMES         | Search for valid JSON names.
 */

/* CREATE_BACKREF_INDEX
 Create backref index. */
CREATE VIRTUAL TABLE backrefs_fts USING fts5(referrer, target);

/* CREATE_UNDOLOG
 Create undo log table https://sqlite.org/undoredo.html sqlite3
 reference */
CREATE TABLE IF NOT EXISTS "undolog" (
        "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
        "action" TEXT NOT NULL,
        "tbl_name" TEXT NOT NULL,
        "sql" TEXT NOT NULL,
        "timestamp" DATETIME NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f', 'now'))
);

/* CREATE_UUID_TOKENIZER
 Create virtual tokenizer table that splits text into tokens, allowing
 you to find uuids in metadata text for reference indexing.
 https://www.sqlite.org/fts3.html#querying_tokenizers sqlite3 reference */
CREATE VIRTUAL TABLE IF NOT EXISTS uuidtok USING fts3tokenize(
    'unicode61',
    "tokenchars=-1234567890abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "separators= "
);

/* UPDATE_LAST_MODIFIED_BINARY
 Update BinaryMetadata last_modified field on UPDATE */
CREATE TRIGGER update_last_modified_binary
    AFTER UPDATE ON BinaryMetadata
BEGIN
    UPDATE BinaryMetadata
    SET "last_modified" = strftime('%Y-%m-%d %H:%M:%f', 'now')
    WHERE uuid = NEW.uuid;
END;

/* UPDATE_LAST_MODIFIED_DOCUMENT
 Update Document last_modified field on UPDATE */
CREATE TRIGGER update_last_modified_document
    AFTER UPDATE ON Documents
BEGIN
    UPDATE Documents
    SET "last_modified" = strftime('%Y-%m-%d %H:%M:%f', 'now')
    WHERE uuid = NEW.uuid;
END;

/* UPDATE_LAST_MODIFIED_HAS_BINARY
 Update DocumentHasBinaryMetadata last_modified field on UPDATE */
CREATE TRIGGER update_last_modified_has_binary
    AFTER UPDATE ON DocumentHasBinaryMetadata
BEGIN
    UPDATE DocumentHasBinaryMetadata
    SET "last_modified" = strftime('%Y-%m-%d %H:%M:%f', 'now')
    WHERE id = NEW.id;
END;

/* UPDATE_LAST_MODIFIED_HAS_TEXT
 Update DocumentHasTextMetadata last_modified field on UPDATE */
CREATE TRIGGER update_last_modified_has_text
    AFTER UPDATE ON DocumentHasTextMetadata
BEGIN
    UPDATE DocumentHasTextMetadata
    SET "last_modified" = strftime('%Y-%m-%d %H:%M:%f', 'now')
    WHERE id = NEW.id;
END;

/* UPDATE_LAST_MODIFIED_TEXT
 Update TextMetadata last_modified field on UPDATE */
CREATE TRIGGER update_last_modified_text
    AFTER UPDATE ON TextMetadata
BEGIN
    UPDATE TextMetadata
    SET "last_modified" = strftime('%Y-%m-%d %H:%M:%f', 'now')
    WHERE uuid = NEW.uuid;
END;

/* UNDOLOG_CREATE_TRIGGER_BINARYMETADATA_DELETE */
CREATE TRIGGER binary_dt
BEFORE DELETE ON BinaryMetadata
BEGIN
  INSERT INTO undolog(action,tbl_name,sql)
  VALUES('DELETE','BinaryMetadata','INSERT INTO
  BinaryMetadata(uuid,name,data,compressed,created,last_modified)
  VALUES('||OLD.uuid||','||quote(OLD.name)||','||quote(OLD.data)||','||
  quote(OLD.compressed)||','||quote(OLD.created)||','||
  quote(OLD.last_modified)||')');
END;

/* UNDOLOG_CREATE_TRIGGER_BINARYMETADATA_INSERT */
CREATE TRIGGER binary_it
AFTER INSERT ON BinaryMetadata
BEGIN
  INSERT INTO undolog(action,tbl_name,sql)
  VALUES('INSERT','BinaryMetadata','DELETE FROM BinaryMetadata WHERE
  uuid='||quote(NEW.uuid));
END;

/* UNDOLOG_CREATE_TRIGGER_BINARYMETADATA_UPDATE */
CREATE TRIGGER binary_ut
AFTER UPDATE ON BinaryMetadata
BEGIN
  INSERT INTO undolog(action,tbl_name,sql)
  VALUES('UPDATE','BinaryMetadata','UPDATE BinaryMetadata SET
  uuid='||quote(OLD.uuid)||',name='||quote(OLD.name)||',data='||
  quote(OLD.data)||',compressed='||quote(OLD.compressed)||
  ',created='||quote(OLD.created)||',last_modified='||
  quote(OLD.last_modified)||'
  WHERE uuid='||quote(OLD.uuid));
END;

/* UNDOLOG_CREATE_TRIGGER_DOCUMENTHASBINARYMETADATA_DELETE */
CREATE TRIGGER has_binary_dt
    BEFORE DELETE ON DocumentHasBinaryMetadata
BEGIN
  INSERT INTO undolog(action,tbl_name,sql)
  VALUES('DELETE','DocumentHasBinaryMetadata','INSERT INTO
  DocumentHasBinaryMetadata(id,name,document_uuid,metadata_uuid,created,last_modified)
  VALUES('||OLD.id||','||quote(OLD.name)||','||quote(OLD.document_uuid)||
  ','||quote(OLD.metadata_uuid)||','||quote(OLD.created)||','||
  quote(OLD.last_modified)||')');
END;

/* UNDOLOG_CREATE_TRIGGER_DOCUMENTHASBINARYMETADATA_INSERT */
CREATE TRIGGER has_binary_it
AFTER INSERT ON DocumentHasBinaryMetadata
BEGIN
  INSERT INTO undolog(action,tbl_name,sql)
  VALUES('INSERT','DocumentHasBinaryMetadata',
  'DELETE FROM DocumentHasBinaryMetadata WHERE id='||NEW.id);
END;

/* UNDOLOG_CREATE_TRIGGER_DOCUMENTHASBINARYMETADATA_UPDATE */
CREATE TRIGGER has_binary_ut
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
END;

/* UNDOLOG_CREATE_TRIGGER_DOCUMENTHASTEXTMETADATA_DELETE */
CREATE TRIGGER has_text_dt
BEFORE DELETE ON DocumentHasTextMetadata
BEGIN
  INSERT INTO undolog(action,tbl_name,sql)
  VALUES('DELETE','DocumentHasTextMetadata','INSERT INTO
  DocumentHasTextMetadata(id,name,document_uuid,metadata_uuid,created,last_modified)
    VALUES('||OLD.id||','||quote(OLD.name)||','||
    quote(OLD.document_uuid)||','||quote(OLD.metadata_uuid)||',
    '||quote(OLD.created)||','||quote(OLD.last_modified)||')');
END;

/* UNDOLOG_CREATE_TRIGGER_DOCUMENTHASTEXTMETADATA_INSERT */
CREATE TRIGGER has_text_it
AFTER INSERT ON DocumentHasTextMetadata
BEGIN
  INSERT INTO undolog(action,tbl_name,sql)
  VALUES('INSERT','DocumentHasTextMetadata',
  'DELETE FROM DocumentHasTextMetadata WHERE id='||NEW.id);
END;

/* UNDOLOG_CREATE_TRIGGER_DOCUMENTHASTEXTMETADATA_UPDATE */
CREATE TRIGGER has_text_ut
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
END;

/* UNDOLOG_CREATE_TRIGGER_DOCUMENTS_DELETE */
CREATE TRIGGER doc_dt
BEFORE DELETE ON Documents
BEGIN
  INSERT INTO undolog(action,tbl_name,sql) VALUES('DELETE','Documents',
  'INSERT INTO Documents(uuid,title,title_suffix,created,last_modified)
    VALUES('||OLD.uuid||','||quote(OLD.title)||','||quote(OLD.title_suffix)||
           ','||quote(OLD.created)||','||quote(OLD.last_modified)||')');
END;

/* UNDOLOG_CREATE_TRIGGER_DOCUMENTS_INSERT */
CREATE TRIGGER doc_it
AFTER INSERT ON Documents
BEGIN
  INSERT INTO undolog(action,tbl_name,sql) VALUES('INSERT','Documents',
  'DELETE FROM Documents WHERE uuid='||quote(NEW.uuid));
END;

/* UNDOLOG_CREATE_TRIGGER_DOCUMENTS_UPDATE */
CREATE TRIGGER doc_ut
AFTER UPDATE ON Documents
BEGIN
  INSERT INTO undolog(action,tbl_name,sql) VALUES('UPDATE','Documents',
  'UPDATE Documents SET uuid='||quote(OLD.uuid)||',title='||quote(OLD.title)||',
  title_suffix='||quote(OLD.title_suffix)||',created='||quote(OLD.created)||',
  last_modified='||quote(OLD.last_modified)||'
   WHERE uuid='||quote(OLD.uuid));
END;

/* UNDOLOG_CREATE_TRIGGER_TEXTMETADATA_DELETE */
CREATE TRIGGER text_dt
BEFORE DELETE ON TextMetadata
BEGIN
  INSERT INTO undolog(action,tbl_name,sql)
  VALUES('DELETE','TextMetadata','INSERT INTO
  TextMetadata(uuid,name,data,created,last_modified)
  VALUES('||OLD.uuid||','||quote(OLD.name)||','||quote(OLD.data)||
      ','||quote(OLD.created)||','||quote(OLD.last_modified)||')');
END;

/* UNDOLOG_CREATE_TRIGGER_TEXTMETADATA_INSERT */
CREATE TRIGGER text_it
AFTER INSERT ON TextMetadata
BEGIN
  INSERT INTO undolog(action,tbl_name,sql) VALUES('INSERT','TextMetadata',
  'DELETE FROM TextMetadata WHERE uuid='||quote(NEW.uuid));
END;

/* UNDOLOG_CREATE_TRIGGER_TEXTMETADATA_UPDATE */
CREATE TRIGGER text_ut
AFTER UPDATE ON TextMetadata
BEGIN
  INSERT INTO undolog(action,tbl_name,sql)
  VALUES('UPDATE','TextMetadata','UPDATE TextMetadata SET
  uuid='||quote(OLD.uuid)||',name='||quote(OLD.name)||',data='||
  quote(OLD.data)||',created='||quote(OLD.created)||',last_modified='||
  quote(OLD.last_modified)||'
  WHERE uuid='||quote(OLD.uuid));
END;

/* Appendix: useful statements */


/* CLI_EDIT_FILE

 Edit any binary BLOB with the edit() function in the CLI.
 https://sqlite.org/cli.html#the_edit_sql_function sqlite3 reference
 for Documentation on the CLI EDIT function

UPDATE BinaryMetadata SET data=edit(data, 'vim')
    WHERE uuid ='17ee75452e574e03b0b8e4ef2bc9be25'; */


/* CLI_EXCTRACT_FILE

 Exctract a binary BLOB from any column using the CLI.
 https://sqlite.org/cli.html#file_i_o_functions sqlite3 reference for
 Documentation on the CLI file I/O functions

SELECT writefile('file.pdf',data) FROM BinaryMetadata
    WHERE uuid ='17ee75452e574e03b0b8e4ef2bc9be25');
 */


/* CLI_INSERT_FILE

 The sqlite3 CLI has some special I/O function to facilate reading and
 writing files. readfile(PATH) will return the bytes read from the path
 PATH as a BLOB. We also use json_object() to create a new name for the
 entry; this could also be done with json_replace().
 https://sqlite.org/cli.html#file_i_o_functions sqlite3 reference for
 Documentation on the CLI file I/O functions and
 https://www.sqlite.org/json1.html sqlite3 reference for Documentation
 on JSON1 extension

UPDATE BinaryMetadata SET
    data=readfile('file.pdf'),
    name=json_object('content_type', 'application/pdf',
    'filename', 'file.pdf', 'size', LENGTH(readfile('file.pdf'))),
    last_modified = strftime('%Y-%m-%d %H:%M:%f', 'now')
    WHERE uuid = '17ee75452e574e03b0b8e4ef2bc9be25'; */


/* CLI_VIEW_FILE

 View any binary BLOB with the edit() function in the CLI by ignoring
 the value it returns.
 https://sqlite.org/cli.html#the_edit_sql_function sqlite3 reference
 for Documentation on the CLI EDIT function

SELECT LENGTH(edit(data, 'zathura')) FROM BinaryMetadata
    WHERE uuid ='17ee75452e574e03b0b8e4ef2bc9be25'; */


/* REMOVE_DUPLICATE_ROWS

 If you need to remove duplicate rows, adapt this statement to your
 table. The MIN(rowid) can be replaced by just rowid if you don't
 necessarily want the smallest row ids to survive.

DELETE FROM table WHERE rowid NOT IN
    (SELECT MIN(rowid) FROM table
     GROUP BY unique_column_1, unique_column_2; */


/* UNDOLOG_DELETE_BIG_ENTRIES

 Delete big binary files (> 1MiB) from undolog to free up space

DELETE FROM undolog WHERE length(sql AS BLOB) > 1000000; */


/* UNDOLOG_QUERY_SIZE

 Query total size of undolog table.

SELECT SUM(pgsize) FROM dbstat WHERE name = 'undolog'; */


/* FTS_INTEGRITY_CHECK

 This command is used to verify that the full-text index is internally
 consistent. https://sqlite.org/fts5.html#the_integrity_check_command
 sqlite3 reference

INSERT INTO
    document_title_authors_text_view_fts(document_title_authors_text_view_fts)
    VALUES('integrity-check'); */


/* FTS_OPTIMIZE

 This command merges all individual b-trees that currently make up the
 full-text index into a single large b-tree structure. Because it
 reorganizes the entire FTS index, the optimize command can take a long
 time to run. https://sqlite.org/fts5.html#the_optimize_command sqlite3
 reference

INSERT INTO
    document_title_authors_text_view_fts(document_title_authors_text_view_fts)
    VALUES('optimize'); */


/* FTS_REBUILD

 This command first deletes the entire full-text index, then rebuilds
 it. https://sqlite.org/fts5.html#the_rebuild_command sqlite3 reference

INSERT INTO
    document_title_authors_text_view_fts(document_title_authors_text_view_fts)
    VALUES('rebuild'); */


/* FTS_SEARCH

 This command queries the full-text search index for documents.
 https://sqlite.org/fts5.html sqlite3 reference

SELECT uuid FROM document_title_authors_text_view_fts('query text'); */


/* FTS_SELECT_CONFIG

 This command returns the values of persistent configuration
 parameters. https://sqlite.org/fts5.html#appendix_b sqlite3 reference

SELECT * FROM document_title_authors_text_view_fts_config; */


/* QUERY_UUID_WITH_HYPHENS

 Match against uuid string with hyphens.

SELECT * FROM Documents
    WHERE uuid =
    REPLACE('7ec63f30-5882-46ac-855d-bdcaf8f29700', '-', ''); */


/* QUERY_BACKREFS_FROM_TEXT_FILES

 Find backreferences from plain text files.

SELECT DISTINCT REPLACE(tok.token, '-', '') AS target,
    texts.uuid AS referrer FROM uuidtok AS tok,
    (SELECT uuid, data,
    json_extract(name, '$.content_type') AS _type
    FROM BinaryMetadata
    WHERE json_valid(name) AND _type LIKE "%text/%")
    AS texts
    WHERE tok.input=texts.data AND LENGTH(tok.token) = 36
    AND EXISTS (SELECT * FROM Documents WHERE uuid = REPLACE(tok.token, '-', '')); */


/* QUERY_BACKREF_CANDIDATES


SELECT DISTINCT token FROM uuidtok
    WHERE input =
    (SELECT data FROM BinaryMetadata
    WHERE uuid = '17ee75452e574e03b0b8e4ef2bc9be25')
    AND LENGTH(token) = 36; */


/* QUERY_TEXT_FILES

 Select text files.

SELECT uuid, name, json_extract(name, '$.content_type') AS _type
    FROM BinaryMetadata
    WHERE json_valid(name)
    AND _type LIKE "%text/%"; */


/* QUERY_VALID_JSON_NAMES

 Search for valid JSON names.

SELECT uuid, name FROM BinaryMetadata WHERE json_valid(name); */