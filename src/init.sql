PRAGMA foreign_keys = ON;
PRAGMA encoding = 'UTF-8';
PRAGMA main.user_version = 0;

CREATE TABLE IF NOT EXISTS Document(
  uuid            BLOB NOT NULL PRIMARY KEY,
  title           TEXT NOT NULL,
  created         DATETIME NOT NULL DEFAULT (strftime('%s', 'now')),
  last_modified   DATETIME NOT NULL DEFAULT (strftime('%s', 'now'))
);

CREATE TABLE IF NOT EXISTS DocumentHasStorage(
  document_uuid   BLOB NOT NULL REFERENCES Document ON UPDATE CASCADE ON DELETE CASCADE,
  metadata_uuid   BLOB NOT NULL REFERENCES Metadata ON UPDATE CASCADE ON DELETE CASCADE,
  is_data         BOOLEAN NOT NULL,
  created         DATETIME NOT NULL DEFAULT (strftime('%s', 'now')),
  last_modified   DATETIME NOT NULL DEFAULT (strftime('%s', 'now')),
  PRIMARY KEY(document_uuid, metadata_uuid)
);

CREATE TABLE IF NOT EXISTS DocumentHasMetadata(
  document_uuid   BLOB NOT NULL REFERENCES Document ON UPDATE CASCADE ON DELETE CASCADE,
  metadata_uuid   BLOB NOT NULL REFERENCES Metadata ON UPDATE CASCADE ON DELETE CASCADE,
  is_text         BOOLEAN NOT NULL,
  created         DATETIME NOT NULL DEFAULT (strftime('%s', 'now')),
  last_modified   DATETIME NOT NULL DEFAULT (strftime('%s', 'now')),
  PRIMARY KEY(document_uuid, metadata_uuid)
);

CREATE TABLE IF NOT EXISTS DocumentHasTag(
  document_uuid   BLOB NOT NULL REFERENCES Document ON UPDATE CASCADE ON DELETE CASCADE,
  metadata_uuid   BLOB NOT NULL REFERENCES Metadata ON UPDATE CASCADE ON DELETE CASCADE,
  created         DATETIME NOT NULL DEFAULT (strftime('%s', 'now')),
  last_modified   DATETIME NOT NULL DEFAULT (strftime('%s', 'now')),
  PRIMARY KEY(document_uuid, metadata_uuid)
);

CREATE TABLE IF NOT EXISTS Metadata(
  uuid            BLOB NOT NULL PRIMARY KEY,
  name            TEXT,
  data            BLOB,
  created         DATETIME NOT NULL DEFAULT (strftime('%s', 'now')),
  last_modified   DATETIME NOT NULL DEFAULT (strftime('%s', 'now'))
);
