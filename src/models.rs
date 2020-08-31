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

use crate::errors::*;
use diesel::prelude::*;
use diesel::sqlite::SqliteConnection;

use diesel::deserialize::FromSql;
use diesel::serialize::{Output, ToSql};
use diesel::sql_types::{BigInt, Binary, Nullable};

use std::convert::TryFrom;
use std::path::PathBuf;
use uuid::Uuid;

pub mod schema;
sql_function! {
    fn length(x: Nullable<Binary>) -> BigInt;
}

macro_rules! uuid_hash_type {
    ($n:ident) => {
        #[derive(PartialEq, Hash, Eq, Copy, Clone, Default, AsExpression, FromSqlRow)]
        #[sql_type = "Binary"]
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

        impl<DB: diesel::backend::Backend> ToSql<Binary, DB> for $n
        where
            [u8]: ToSql<Binary, DB>,
        {
            fn to_sql<W>(&self, out: &mut Output<W, DB>) -> diesel::serialize::Result
            where
                W: std::io::Write,
            {
                let v = &self.0.as_bytes()[0..];
                v.to_sql(out)
            }
        }

        impl<DB: diesel::backend::Backend> FromSql<Binary, DB> for $n
        where
            *const [u8]: FromSql<Binary, DB>,
        {
            fn from_sql(bytes: Option<&DB::RawValue>) -> diesel::deserialize::Result<Self> {
                let slice_ptr = <*const [u8]>::from_sql(bytes)?;
                // We know that the pointer impl will never return null since it's not
                // Nullable<Binary>
                let bytes = unsafe { &*slice_ptr };
                let b16 = <[u8; 16]>::try_from(bytes)?;
                Ok($n(uuid::Uuid::from_bytes(b16)))
            }
        }

        impl<S: AsRef<str>> From<S> for $n {
            fn from(from: S) -> Self {
                $n(Uuid::parse_str(from.as_ref()).unwrap())
            }
        }

        impl $n {
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

impl DocumentUuid {
    pub fn new(title: &str) -> Self {
        DocumentUuid::new_v5(&Uuid::NAMESPACE_OID, title.as_bytes())
    }
}

impl MetadataUuid {
    pub fn new_tag(title: &str) -> Self {
        MetadataUuid::new_v5(&Uuid::NAMESPACE_OID, format!("tag\0{}", title).as_bytes())
    }

    pub fn new_data(name: Option<&str>, data: &[u8]) -> Self {
        if let Some(name) = name {
            let mut name = name.as_bytes().to_vec();
            name.push(b'\0');
            name.extend(data.iter().cloned());
            MetadataUuid::new_v5(&Uuid::NAMESPACE_OID, &name)
        } else {
            MetadataUuid::new_v5(&Uuid::NAMESPACE_OID, data)
        }
    }

    pub fn new_storage_data(data: &[u8]) -> Self {
        MetadataUuid::new_v5(&Uuid::NAMESPACE_DNS, data)
    }

    pub fn new_filesystem_path(path: &[u8]) -> Self {
        MetadataUuid::new_v5(&Uuid::NAMESPACE_URL, path)
    }
}

uuid_hash_type!(DocumentUuid);
uuid_hash_type!(MetadataUuid);

#[derive(Debug)]
pub enum StorageType {
    InDatabase(String),
    Local(PathBuf),
}

use schema::Document as SchemaDocument;
#[derive(Debug, Queryable, Insertable)]
#[table_name = "SchemaDocument"]
pub struct Document {
    pub uuid: DocumentUuid,
    pub title: String,
    pub created: chrono::NaiveDateTime,
    pub last_modified: chrono::NaiveDateTime,
}

use schema::Metadata as SchemaMetadata;
#[derive(Debug, Insertable, Queryable)]
#[table_name = "SchemaMetadata"]
pub struct Metadata {
    pub uuid: MetadataUuid,
    pub name: Option<String>,
    pub data: Option<Vec<u8>>,
    pub created: chrono::NaiveDateTime,
    pub last_modified: chrono::NaiveDateTime,
}

impl Document {
    pub fn new(title: String) -> Self {
        Document {
            uuid: DocumentUuid::new(&title),
            title,
            created: chrono::Utc::now().naive_utc(),
            last_modified: chrono::Utc::now().naive_utc(),
        }
    }
}

pub struct DatabaseConnection {
    inner: SqliteConnection,
}

impl DatabaseConnection {
    pub fn all(&self) -> Vec<Document> {
        schema::Document::table.load(&self.inner).unwrap()
    }

    pub fn get(&self, uuid: &DocumentUuid) -> Document {
        schema::Document::table
            .filter(schema::Document::uuid.eq(uuid))
            .first(&self.inner)
            .optional()
            .unwrap()
            .unwrap()
    }

    pub fn get_files(&self, uuid: &DocumentUuid) -> Vec<(MetadataUuid, StorageType, usize)> {
        let v: Vec<(MetadataUuid, Option<String>, bool, i64)> = schema::Metadata::table
            .inner_join(schema::DocumentHasStorage::table.inner_join(schema::Document::table))
            .filter(schema::Document::uuid.eq(uuid))
            .select((
                schema::Metadata::uuid,
                schema::Metadata::name,
                schema::DocumentHasStorage::is_data,
                length(schema::Metadata::data),
            ))
            .load(&self.inner)
            .unwrap();
        eprintln!("v = {:?}", &v);
        v.into_iter()
            .map(|(mu, opt_s, b, len)| {
                (
                    mu,
                    {
                        if b {
                            StorageType::InDatabase(String::new())
                        } else {
                            StorageType::Local(opt_s.unwrap_or_default().into())
                        }
                    },
                    <usize>::try_from(len).unwrap_or(0),
                )
            })
            .collect()
        /*
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
        */
    }

    pub fn get_files_no(&self, uuid: &DocumentUuid) -> usize {
        <usize as TryFrom<i64>>::try_from(
            schema::Metadata::table
                .inner_join(schema::DocumentHasStorage::table.inner_join(schema::Document::table))
                .filter(schema::Document::uuid.eq(uuid))
                .count()
                .get_result(&self.inner)
                .unwrap(),
        )
        .unwrap_or(0)
    }

    pub fn get_data(&self, uuid: &MetadataUuid) -> Vec<u8> {
        let v: Option<Vec<u8>> = schema::Metadata::table
            .filter(schema::Metadata::uuid.eq(uuid))
            .select(schema::Metadata::data)
            .first(&self.inner)
            .unwrap();

        v.unwrap_or_default()
    }

    pub fn get_tags(&self, uuid: &DocumentUuid) -> Vec<(MetadataUuid, String)> {
        let v: Vec<(MetadataUuid, String)> = schema::Metadata::table
            .inner_join(schema::DocumentHasTag::table.inner_join(schema::Document::table))
            .filter(schema::Document::uuid.eq(uuid))
            .filter(schema::Metadata::name.eq("tag"))
            .select((schema::Metadata::uuid, schema::Metadata::data))
            .load(&self.inner)
            .unwrap()
            .into_iter()
            .map(|(m, opt): (MetadataUuid, Option<Vec<u8>>)| {
                (
                    m,
                    opt.map(|v| String::from_utf8_lossy(&v).to_string())
                        .unwrap_or_default(),
                )
            })
            .collect();
        v
    }

    pub fn get_authors(&self, uuid: &DocumentUuid) -> Vec<(MetadataUuid, String)> {
        let v: Vec<(MetadataUuid, String)> = schema::Metadata::table
            .inner_join(schema::DocumentHasMetadata::table.inner_join(schema::Document::table))
            .filter(schema::Document::uuid.eq(uuid))
            .filter(schema::Metadata::name.eq("author"))
            .select((schema::Metadata::uuid, schema::Metadata::data))
            .load(&self.inner)
            .unwrap()
            .into_iter()
            .map(|(m, opt): (MetadataUuid, Option<Vec<u8>>)| {
                (
                    m,
                    opt.map(|v| String::from_utf8_lossy(&v).to_string())
                        .unwrap_or_default(),
                )
            })
            .collect();
        v
    }

    pub fn insert_document(&self, name: &str) -> Result<DocumentUuid> {
        let mc = Document::new(name.to_string());

        diesel::insert_into(schema::Document::table)
            .values(&mc)
            .execute(&self.inner)?;
        Ok(mc.uuid)
    }

    pub fn insert_metadata(
        &self,
        name: Option<&str>,
        data: &[u8],
        is_text: bool,
        uuid: &DocumentUuid,
    ) -> Result<MetadataUuid> {
        let metadata_uuid = MetadataUuid::new_data(name, data);
        let mv = Metadata {
            uuid: metadata_uuid,
            name: name.map(|n| n.to_string()),
            data: Some(data.to_vec()),
            created: chrono::Utc::now().naive_utc(),
            last_modified: chrono::Utc::now().naive_utc(),
        };

        diesel::insert_into(schema::Metadata::table)
            .values(&mv)
            .execute(&self.inner)?;
        Ok(metadata_uuid)
    }

    pub fn insert_tag(&self, data: &str, uuid: &DocumentUuid) -> Result<MetadataUuid> {
        let metadata_uuid = MetadataUuid::new_tag(data);
        let mv = Metadata {
            uuid: metadata_uuid,
            name: Some("tag".to_string()),
            data: Some(data.as_bytes().to_vec()),
            created: chrono::Utc::now().naive_utc(),
            last_modified: chrono::Utc::now().naive_utc(),
        };

        diesel::insert_into(schema::Metadata::table)
            .values(&mv)
            .execute(&self.inner)?;
        diesel::insert_into(schema::DocumentHasTag::table)
            .values((
                schema::DocumentHasTag::document_uuid.eq(uuid),
                schema::DocumentHasTag::metadata_uuid.eq(uuid),
            ))
            .execute(&self.inner)?;
        Ok(metadata_uuid)
    }

    pub fn remove_tag_from_document(
        &self,
        metadata_uuid: &MetadataUuid,
        uuid: &DocumentUuid,
    ) -> Result<()> {
        diesel::delete(
            schema::DocumentHasTag::table
                .filter(schema::DocumentHasTag::document_uuid.eq(uuid))
                .filter(schema::DocumentHasTag::metadata_uuid.eq(metadata_uuid)),
        )
        .execute(&self.inner)
        .chain_err(|| {
            format!(
                "Error removing tag {} from document {}",
                metadata_uuid, uuid
            )
        })?;
        Ok(())
    }

    pub fn remove_metadata_from_document(
        &self,
        metadata_uuid: &MetadataUuid,
        uuid: &DocumentUuid,
    ) -> Result<()> {
        diesel::delete(
            schema::DocumentHasMetadata::table
                .filter(schema::DocumentHasMetadata::document_uuid.eq(uuid))
                .filter(schema::DocumentHasMetadata::metadata_uuid.eq(metadata_uuid)),
        )
        .execute(&self.inner)
        .chain_err(|| {
            format!(
                "Error removing metadata {} from document {}",
                metadata_uuid, uuid
            )
        })?;
        Ok(())
    }

    pub fn insert_storage(
        &self,
        storage: StorageType,
        mime_type: &str,
        uuid: &DocumentUuid,
    ) -> Result<MetadataUuid> {
        diesel::insert_into(schema::DocumentHasTag::table)
            .values((
                schema::DocumentHasTag::document_uuid.eq(uuid),
                schema::DocumentHasTag::metadata_uuid.eq(uuid),
            ))
            .execute(&self.inner)?;
        match storage {
            StorageType::InDatabase(ref data) => {
                let storage_uuid = MetadataUuid::new_storage_data(data.as_bytes());
                diesel::insert_into(schema::Metadata::table)
                    .values((
                        schema::Metadata::uuid.eq(&storage_uuid),
                        schema::Metadata::name.eq("text/plain"),
                        schema::Metadata::data.eq(data.as_bytes()),
                    ))
                    .execute(&self.inner)?;
                diesel::insert_into(schema::DocumentHasStorage::table)
                    .values((
                        schema::DocumentHasStorage::document_uuid.eq(uuid),
                        schema::DocumentHasStorage::metadata_uuid.eq(storage_uuid),
                        schema::DocumentHasStorage::is_data.eq(true),
                    ))
                    .execute(&self.inner)?;
                Ok(storage_uuid)
            }
            StorageType::Local(ref path) => {
                let storage_uuid =
                    MetadataUuid::new_filesystem_path(path.to_str().unwrap().as_bytes());
                diesel::insert_into(schema::Metadata::table)
                    .values((
                        schema::Metadata::uuid.eq(&storage_uuid),
                        schema::Metadata::name.eq(&mime_type), /* xdg-mime query filetype $FILE */
                        schema::Metadata::data.eq(&path.to_str().unwrap().as_bytes()),
                    ))
                    .execute(&self.inner)?;
                diesel::insert_into(schema::DocumentHasStorage::table)
                    .values((
                        schema::DocumentHasStorage::document_uuid.eq(uuid),
                        schema::DocumentHasStorage::metadata_uuid.eq(storage_uuid),
                        schema::DocumentHasStorage::is_data.eq(false),
                    ))
                    .execute(&self.inner)?;

                Ok(storage_uuid)
            }
        }
    }
}

pub fn create_connection() -> Result<DatabaseConnection> {
    let path = &"./bibliothecula.db";
    let database_url = std::env::var("DATABASE_URL").unwrap_or(path.to_string());
    let conn = SqliteConnection::establish(&database_url)
        .expect(&format!("Error connecting to {}", database_url));
    /*
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
        */

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

    Ok(DatabaseConnection { inner: conn })
}
