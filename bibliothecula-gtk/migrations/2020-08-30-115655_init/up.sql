PRAGMA foreign_keys = ON;
PRAGMA encoding = 'UTF-8';
PRAGMA main.user_version = 0;

CREATE TABLE Document(
  uuid            BLOB NOT NULL PRIMARY KEY,
  title           TEXT NOT NULL,
  created         DATETIME NOT NULL DEFAULT (strftime('%s', 'now')),
  last_modified   DATETIME NOT NULL DEFAULT (strftime('%s', 'now'))
);

CREATE TABLE Metadata(
  uuid            BLOB NOT NULL PRIMARY KEY,
  name            TEXT,
  data            BLOB,
  created         DATETIME NOT NULL DEFAULT (strftime('%s', 'now')),
  last_modified   DATETIME NOT NULL DEFAULT (strftime('%s', 'now'))
);

CREATE TABLE DocumentHasStorage(
  document_uuid   BLOB NOT NULL REFERENCES Document(uuid) ON UPDATE CASCADE ON DELETE CASCADE,
  metadata_uuid   BLOB NOT NULL REFERENCES Metadata(uuid) ON UPDATE CASCADE ON DELETE CASCADE,
  is_data         BOOLEAN NOT NULL,
  created         DATETIME NOT NULL DEFAULT (strftime('%s', 'now')),
  last_modified   DATETIME NOT NULL DEFAULT (strftime('%s', 'now')),
  PRIMARY KEY(document_uuid, metadata_uuid)
);

CREATE TABLE DocumentHasMetadata(
  document_uuid   BLOB NOT NULL REFERENCES Document(uuid) ON UPDATE CASCADE ON DELETE CASCADE,
  metadata_uuid   BLOB NOT NULL REFERENCES Metadata(uuid) ON UPDATE CASCADE ON DELETE CASCADE,
  is_text         BOOLEAN NOT NULL,
  created         DATETIME NOT NULL DEFAULT (strftime('%s', 'now')),
  last_modified   DATETIME NOT NULL DEFAULT (strftime('%s', 'now')),
  PRIMARY KEY(document_uuid, metadata_uuid)
);

CREATE TABLE DocumentHasTag(
  document_uuid   BLOB NOT NULL REFERENCES Document(uuid) ON UPDATE CASCADE ON DELETE CASCADE,
  metadata_uuid   BLOB NOT NULL REFERENCES Metadata(uuid) ON UPDATE CASCADE ON DELETE CASCADE,
  created         DATETIME NOT NULL DEFAULT (strftime('%s', 'now')),
  last_modified   DATETIME NOT NULL DEFAULT (strftime('%s', 'now')),
  PRIMARY KEY(document_uuid, metadata_uuid)
);

