/*
 * bibliothecula
 *
 * Copyright - 2020 Manos Pitsidianakis
 *
 * This file is part of bibliothecula.
 *
 * bibliothecula is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * bibliothecula is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with bibliothecula. If not, see <http://www.gnu.org/licenses/>.
 */

use rusqlite::{params, Connection, Result};
use std::path::{Path, PathBuf};
use uuid::Uuid;

macro_rules! uuid_hash_type {
    ($n:ident) => {
        #[derive(PartialEq, Hash, Eq, Copy, Clone, Default)]
        pub struct $n(Uuid);

        impl core::fmt::Debug for $n {
            fn fmt(&self, f: &mut core::fmt::Formatter) -> core::fmt::Result {
                write!(f, "{}", self.0.to_string())
            }
        }

        impl core::fmt::Display for $n {
            fn fmt(&self, f: &mut core::fmt::Formatter) -> core::fmt::Result {
                write!(f, "{}", self.0.to_string())
            }
        }

        impl $n {
            /*
            fn new() -> Self {
                $n(Uuid::new_v4())
            }
            */
            pub fn new_v5(namespace: &Uuid, b: &[u8]) -> Self {
                $n(Uuid::new_v5(namespace, b))
            }

            pub fn null() -> Self {
                $n(Uuid::nil())
            }

            pub fn inner(&self) -> &Uuid {
                &self.0
            }
        }
    };
}

uuid_hash_type!(DocumentUuid);
uuid_hash_type!(MetadataUuid);

#[derive(Debug)]
pub enum StorageType {
    InDatabase(String),
    Local(PathBuf),
}

#[derive(Debug)]
pub struct Document {
    pub uuid: DocumentUuid,
    pub title: String,
}

impl Document {
    pub fn new(title: String) -> Self {
        Document {
            uuid: DocumentUuid::new_v5(&Uuid::NAMESPACE_OID, title.as_bytes()),
            title,
        }
    }
}

pub struct DatabaseConnection(Connection);

impl DatabaseConnection {
    pub fn all(&self) -> Vec<Document> {
        let mut stmt = self.0.prepare("SELECT uuid, title FROM Document").unwrap();
        let doc_iter = stmt
            .query_map(params![], |row| {
                Ok(Document {
                    uuid: DocumentUuid(row.get(0).unwrap()),
                    title: row.get(1).unwrap(),
                })
            })
            .unwrap();

        doc_iter.collect::<Result<Vec<_>>>().unwrap()
    }

    pub fn get(&self, uuid: &DocumentUuid) -> Document {
        let mut stmt = self
            .0
            .prepare("SELECT uuid, title FROM Document WHERE uuid = ?1")
            .unwrap();
        let doc_iter = stmt
            .query_map(params![uuid.inner()], |row| {
                Ok(Document {
                    uuid: DocumentUuid(row.get(0).unwrap()),
                    title: row.get(1).unwrap(),
                })
            })
            .unwrap();

        doc_iter.collect::<Result<Vec<_>>>().unwrap().remove(0)
    }

    pub fn get_files(&self, uuid: &DocumentUuid) -> Vec<(MetadataUuid, StorageType, usize)> {
        let mut stmt = self.0.prepare("SELECT m.uuid, hs.is_data, (CASE WHEN hs.is_data THEN  m.name ELSE m.data END), length(m.data) FROM Metadata AS m, DocumentHasStorage AS hs, Document AS d WHERE hs.document_uuid = d.uuid AND d.uuid=?1 AND m.uuid = hs.metadata_uuid;").unwrap();
        let storage_iter = stmt
            .query_map(params![uuid.inner()], |row| {
                Ok((
                    MetadataUuid(row.get(0).unwrap()),
                    if row.get(1).unwrap() {
                        StorageType::InDatabase(row.get(2).unwrap())
                    } else {
                        let s: String = row.get(2).unwrap();
                        StorageType::Local(PathBuf::from(s))
                    },
                    row.get::<_, i64>(3).unwrap() as usize,
                ))
            })
            .unwrap();

        storage_iter.collect::<Result<Vec<_>>>().unwrap()
    }

    pub fn get_data(&self, uuid: &MetadataUuid) -> Vec<u8> {
        let mut stmt = self
            .0
            .prepare("SELECT m.data FROM Metadata AS m WHERE m.uuid=?1")
            .unwrap();
        let storage_iter = stmt
            .query_map(params![uuid.inner()], |row| {
                Ok(row.get(0).unwrap_or_else(|_| {
                    let text: String = row.get(0).unwrap();
                    text.into_bytes()
                }))
            })
            .unwrap();

        storage_iter.collect::<Result<Vec<_>>>().unwrap().remove(0)
    }
}

pub fn create_connection() -> Result<DatabaseConnection> {
    let path = &Path::new("./bibliothecula.db");
    let set_mode = !path.exists();
    let conn = Connection::open(path).unwrap();
    if set_mode {
        use std::os::unix::fs::PermissionsExt;
        let file = std::fs::File::open(&path).unwrap();
        let metadata = file.metadata().unwrap();
        let mut permissions = metadata.permissions();

        permissions.set_mode(0o600); // Read/write for owner only.
        file.set_permissions(permissions).unwrap();
        conn.execute_batch(include_str!("./init.sql"))?;
        let mc = Document::new("Magna Carta".to_string());

        conn.execute(
            "INSERT INTO Document (uuid, title) VALUES (?1, ?2)",
            params![mc.uuid.inner(), mc.title],
        )?;

        let mc_storage_uuid = Uuid::new_v5(
            &Uuid::NAMESPACE_DNS,
            include_str!("./magna_carta.txt").as_bytes(),
        );
        conn.execute(
            "INSERT INTO Metadata (uuid, name, data) VALUES (?1, ?2, ?3)",
            params![
                mc_storage_uuid,
                "text/plain",
                include_str!("./magna_carta.txt")
            ],
        )?;
        conn.execute(
            "INSERT INTO DocumentHasStorage (document_uuid, metadata_uuid, is_data) VALUES (?1, ?2, ?3)",
            params![mc.uuid.inner(), mc_storage_uuid, true],
        )?;
        let mc_author_uuid = Uuid::new_v5(&Uuid::NAMESPACE_OID, b"author\0anonymous");
        conn.execute(
            "INSERT INTO Metadata (uuid, name, data) VALUES (?1, ?2, ?3)",
            params![mc_author_uuid, "author", "Anonymous"],
        )?;
        conn.execute(
            "INSERT INTO DocumentHasMetadata (document_uuid, metadata_uuid, is_text) VALUES (?1, ?2, ?3)",
            params![mc.uuid.inner(), mc_author_uuid, true],
        )?;
        let mc_tag_uuid = Uuid::new_v5(&Uuid::NAMESPACE_OID, b"tag\0boring");
        conn.execute(
            "INSERT INTO Metadata (uuid, name, data) VALUES (?1, ?2, ?3)",
            params![mc_tag_uuid, "tag", "boring"],
        )?;
        conn.execute(
            "INSERT INTO DocumentHasTag (document_uuid, metadata_uuid) VALUES (?1, ?2)",
            params![mc.uuid.inner(), mc_tag_uuid],
        )?;
        let mc_tag_uuid = Uuid::new_v5(&Uuid::NAMESPACE_OID, b"tag\0history");
        conn.execute(
            "INSERT INTO Metadata (uuid, name, data) VALUES (?1, ?2, ?3)",
            params![mc_tag_uuid, "tag", "history"],
        )?;
        conn.execute(
            "INSERT INTO DocumentHasTag (document_uuid, metadata_uuid) VALUES (?1, ?2)",
            params![mc.uuid.inner(), mc_tag_uuid],
        )?;
    }

    {
        /*
        let mut stmt = conn.prepare("SELECT uuid, title FROM Document")?;
        let doc_iter = stmt.query_map(params![], |row| {
            Ok(Document {
                uuid: row.get(0)?,
                title: row.get(1)?,
            })
        })?;

        for doc in doc_iter {
            println!("Found doc {:?}", doc.unwrap());
        }
        */
    }

    Ok(DatabaseConnection(conn))
}
