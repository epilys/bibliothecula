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

        impl<S: AsRef<str>> From<S> for $n {
            fn from(from: S) -> Self {
                $n(Uuid::parse_str(from.as_ref()).unwrap())
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
                    if row.get(1).unwrap() {
                        row.get::<_, i64>(3).unwrap() as usize
                    } else {
                        std::fs::File::open({
                            let s: String = row.get(2).unwrap();
                            s
                        })
                        .and_then(|f| f.metadata().map(|d| d.len()))
                        .unwrap_or_default() as usize
                    },
                ))
            })
            .unwrap();

        storage_iter.collect::<Result<Vec<_>>>().unwrap()
    }

    pub fn get_files_no(&self, uuid: &DocumentUuid) -> usize {
        let mut stmt = self.0.prepare("SELECT * FROM Metadata AS m, DocumentHasStorage AS hs, Document AS d WHERE hs.document_uuid = d.uuid AND d.uuid=?1 AND m.uuid = hs.metadata_uuid;").unwrap();
        let storage_iter = stmt.query_map(params![uuid.inner()], |row| Ok(())).unwrap();

        storage_iter.collect::<Result<Vec<_>>>().unwrap().len()
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

    pub fn get_tags(&self, uuid: &DocumentUuid) -> Vec<(MetadataUuid, String)> {
        let mut stmt = self.0.prepare("SELECT m.uuid, m.data FROM Metadata AS m, DocumentHasTag AS hs, Document AS d WHERE m.name = 'tag' AND hs.document_uuid = d.uuid AND d.uuid=?1 AND m.uuid = hs.metadata_uuid;").unwrap();
        let tag_iter = stmt
            .query_map(params![uuid.inner()], |row| {
                Ok((MetadataUuid(row.get(0).unwrap()), row.get(1).unwrap()))
            })
            .unwrap();

        tag_iter.collect::<Result<Vec<_>>>().unwrap()
    }

    pub fn get_authors(&self, uuid: &DocumentUuid) -> Vec<(MetadataUuid, String)> {
        let mut stmt = self.0.prepare("SELECT m.uuid, m.data FROM Metadata AS m, DocumentHasMetadata AS hs, Document AS d WHERE m.name = 'author' AND hs.document_uuid = d.uuid AND d.uuid=?1 AND m.uuid = hs.metadata_uuid;").unwrap();
        let author_iter = stmt
            .query_map(params![uuid.inner()], |row| {
                Ok((
                    MetadataUuid(row.get(0).unwrap()),
                    String::from_utf8_lossy(&row.get::<_, Vec<u8>>(1).unwrap()).into_owned(),
                ))
            })
            .unwrap();

        author_iter.collect::<Result<Vec<_>>>().unwrap()
    }

    pub fn insert_document(&self, name: &str) -> Result<DocumentUuid> {
        let mc = Document::new(name.to_string());

        self.0.execute(
            "INSERT INTO Document (uuid, title) VALUES (?1, ?2)",
            params![mc.uuid.inner(), mc.title],
        )?;
        Ok(mc.uuid)
    }

    pub fn insert_metadata(
        &self,
        name: Option<&str>,
        data: &[u8],
        is_text: bool,
        uuid: &DocumentUuid,
    ) -> Result<MetadataUuid> {
        let metadata_uuid = MetadataUuid(if let Some(name) = name {
            let mut name = name.as_bytes().to_vec();
            name.push(b'\0');
            name.extend(data.iter().cloned());
            Uuid::new_v5(&Uuid::NAMESPACE_OID, &name)
        } else {
            Uuid::new_v5(&Uuid::NAMESPACE_OID, data)
        });
        self.0.execute(
            "INSERT OR IGNORE INTO Metadata (uuid, name, data) VALUES (?1, ?2, ?3)",
            params![metadata_uuid.inner(), name.unwrap_or_default(), data],
        )?;
        self.0.execute(
            "INSERT OR IGNORE INTO DocumentHasMetadata (document_uuid, metadata_uuid, is_text) VALUES (?1, ?2, ?3)",
            params![uuid.inner(), metadata_uuid.inner(), is_text],
        )?;
        Ok(metadata_uuid)
    }

    pub fn insert_tag(&self, data: &str, uuid: &DocumentUuid) -> Result<MetadataUuid> {
        let metadata_uuid = MetadataUuid(Uuid::new_v5(
            &Uuid::NAMESPACE_OID,
            format!("tag\0{}", data).as_bytes(),
        ));

        self.0.execute(
            "INSERT OR IGNORE INTO Metadata (uuid, name, data) VALUES (?1, ?2, ?3)",
            params![metadata_uuid.inner(), "tag", data],
        )?;
        self.0.execute(
            "INSERT OR IGNORE INTO DocumentHasTag (document_uuid, metadata_uuid) VALUES (?1, ?2)",
            params![uuid.inner(), metadata_uuid.inner()],
        )?;
        Ok(metadata_uuid)
    }

    pub fn remove_tag_from_document(
        &self,
        metadata_uuid: &MetadataUuid,
        uuid: &DocumentUuid,
    ) -> Result<()> {
        self.0.execute(
            "DELETE FROM DocumentHasTag where document_uuid = ?1 AND metadata_uuid = ?2",
            params![uuid.inner(), metadata_uuid.inner()],
        )?;
        Ok(())
    }

    pub fn remove_metadata_from_document(
        &self,
        metadata_uuid: &MetadataUuid,
        uuid: &DocumentUuid,
    ) -> Result<()> {
        self.0.execute(
            "DELETE FROM DocumentHasMetadata where document_uuid = ?1 AND metadata_uuid = ?2",
            params![uuid.inner(), metadata_uuid.inner()],
        )?;
        Ok(())
    }

    pub fn insert_storage(
        &self,
        storage: StorageType,
        mime_type: &str,
        uuid: &DocumentUuid,
    ) -> Result<MetadataUuid> {
        match storage {
            StorageType::InDatabase(ref data) => {
                let storage_uuid =
                    MetadataUuid(Uuid::new_v5(&Uuid::NAMESPACE_DNS, data.as_bytes()));
                self.0.execute(
                    "INSERT INTO Metadata (uuid, name, data) VALUES (?1, ?2, ?3)",
                    params![storage_uuid.inner(), "text/plain", data,],
                )?;
                self.0.execute(
                    "INSERT INTO DocumentHasStorage (document_uuid, metadata_uuid, is_data) VALUES (?1, ?2, ?3)",
                    params![uuid.inner(), storage_uuid.inner(), true],
                )?;
                Ok(storage_uuid)
            }
            StorageType::Local(ref path) => {
                let storage_uuid = MetadataUuid(Uuid::new_v5(
                    &Uuid::NAMESPACE_URL,
                    path.to_str().unwrap().as_bytes(),
                ));
                self.0.execute(
                    "INSERT INTO Metadata (uuid, name, data) VALUES (?1, ?2, ?3)",
                    params![
                        storage_uuid.inner(),
                        mime_type, /* xdg-mime query filetype $FILE */
                        &path.to_str().unwrap(),
                    ],
                )?;
                self.0.execute(
                    "INSERT INTO DocumentHasStorage (document_uuid, metadata_uuid, is_data) VALUES (?1, ?2, ?3)",
                    params![uuid.inner(), storage_uuid.inner(), false],
                )?;

                Ok(storage_uuid)
            }
        }
    }
}

pub fn create_connection() -> Result<DatabaseConnection> {
    let path = &Path::new("./bibliothecula.db");
    let set_mode = !path.exists();
    let conn = Connection::open(path).unwrap();
    let ret = DatabaseConnection(conn);
    if set_mode {
        use std::os::unix::fs::PermissionsExt;
        let file = std::fs::File::open(&path).unwrap();
        let metadata = file.metadata().unwrap();
        let mut permissions = metadata.permissions();

        permissions.set_mode(0o600); // Read/write for owner only.
        file.set_permissions(permissions).unwrap();
        ret.0.execute_batch(include_str!("./init.sql"))?;
        let mc_uuid = ret.insert_document("Magna Carta")?;
        /* insert embedded text file */
        let embedded_text_file =
            StorageType::InDatabase(include_str!("./magna_carta.txt").to_string());
        ret.insert_storage(embedded_text_file, "text/plain", &mc_uuid)?;
        /* insert referenced txt file */
        ret.insert_storage(
            StorageType::Local(PathBuf::from("./src/magna_carta.txt")),
            "text/plain",
            &mc_uuid,
        )?;
        /* insert author metadata */
        ret.insert_metadata(Some("author"), b"Anonymous", true, &mc_uuid)?;
        /* insert tag metadata */
        ret.insert_tag("demo", &mc_uuid)?;
        ret.insert_tag("history", &mc_uuid)?;
        ret.insert_tag("public-domain", &mc_uuid)?;
        {
            let mc_uuid = ret.insert_document("init.sql")?;
            /* insert embedded text file */
            let embedded_text_file =
                StorageType::InDatabase(include_str!("./init.sql").to_string());
            ret.insert_storage(embedded_text_file, "text/plain", &mc_uuid)?;
            /* insert referenced txt file */
            ret.insert_storage(
                StorageType::Local(PathBuf::from("./src/init.sql")),
                "text/plain",
                &mc_uuid,
            )?;
            /* insert author metadata */
            ret.insert_metadata(Some("author"), b"Manos Pitsidianakis", true, &mc_uuid)?;
            /* insert tag metadata */
            ret.insert_tag("demo", &mc_uuid)?;
            ret.insert_tag("sql", &mc_uuid)?;
            ret.insert_tag("bibliothecula", &mc_uuid)?;
        }
    }

    {
        /*
        let mut stmt = ret.0.prepare("SELECT uuid, title FROM Document")?;
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

    Ok(ret)
}
