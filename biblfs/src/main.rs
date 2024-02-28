use clap::{crate_version, App, Arg};
use crossbeam_channel::{bounded, select};
use fuser::{
    FileAttr, FileType, Filesystem, ReplyAttr, ReplyBmap, ReplyCreate, ReplyData, ReplyDirectory,
    ReplyDirectoryPlus, ReplyEmpty, ReplyEntry, ReplyIoctl, ReplyLock, ReplyLseek, ReplyOpen,
    ReplyStatfs, ReplyWrite, ReplyXattr, Request, TimeOrNow,
};
use libc::{EEXIST, ENODATA, ENOENT, ENOSYS, ENOTSUP, ERANGE};
use rusqlite::types::{FromSql, FromSqlError, FromSqlResult, ToSql, ToSqlOutput, ValueRef};
use rusqlite::{self, Connection, DatabaseName, Result};
use signal_hook::{consts::SIGINT, iterator::Signals};
use std::collections::HashMap;
use std::convert::TryInto;
use std::dbg;
use std::env;
use std::ffi::OsStr;
use std::os::unix::ffi::OsStrExt;
use std::path::Path;
use std::thread;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use time::{OffsetDateTime, PrimitiveDateTime, UtcOffset};
use uuid::Uuid as Uuid_;

type INode = u64;
//const SQLITE_PAGE_SIZE: usize = 512;

#[derive(Clone, Copy, Debug, Default, Eq, Hash, Ord, PartialEq, PartialOrd)]
pub struct Uuid(Uuid_);

impl FromSql for Uuid {
    fn column_result(value: ValueRef) -> FromSqlResult<Self> {
        String::column_result(value).map(|as_str| Self(Uuid_::parse_str(&as_str).unwrap()))
    }
}

impl ToSql for Uuid {
    fn to_sql(&self) -> Result<ToSqlOutput> {
        Ok(self
            .0
            .to_simple()
            .encode_lower(&mut Uuid_::encode_buffer())
            .to_string()
            .into())
    }
}

macro_rules! xattr_text_document_uuid_by_name {
    ($tx:ident, $ino:ident, $name:ident, $t_uuid:ident) => {{
        let mut stmt = $tx
            .prepare(
                "SELECT t.uuid as uuid FROM DocumentHasTextMetadata as h, DocumentHasBinaryMetadata as hb, TextMetadata as t WHERE h.document_uuid = hb.document_uuid AND hb.metadata_uuid = ? AND t.uuid = h.metadata_uuid AND t.name = ?",
            )
            .unwrap();
        $t_uuid = TextMetadataUuid(
            stmt.query_row(rusqlite::params![&$ino.0, &$name], |row| {
                let tu: Uuid = row.get(0)?;
                Ok(tu)
            })
            .unwrap(),
        );
    }};
}

macro_rules! documents_that_have_xattr {
    ($tx:ident, $xattr_metadata_uuid:ident, $result_vec:ident) => {{
        let mut stmt = $tx
            .prepare(
                "SELECT h.document_uuid as document_uuid FROM DocumentHasTextMetadata as h WHERE h.metadata_uuid = ?",
            )
            .unwrap();
        let iter = stmt
            .query_map(rusqlite::params![&$xattr_metadata_uuid.0], |row| {
                let du: Uuid = row.get(0)?;
                Ok(DocumentUuid(du))
            })
        .unwrap();
        for i in iter {
            $result_vec.push(i.unwrap());
        }
    }};
    ($tx:ident, $xattr_metadata_uuid:ident, $result_vec:ident except $document_uuid:ident) => {{
        let mut stmt = $tx
            .prepare(
                "SELECT h.document_uuid as document_uuid FROM DocumentHasTextMetadata as h WHERE h.metadata_uuid = ? AND h.document_uuid != ?",
            )
            .unwrap();
        let iter = stmt
            .query_map(rusqlite::params![&$xattr_metadata_uuid.0, &$document_uuid.0], |row| {
                let du: Uuid = row.get(0)?;
                Ok(DocumentUuid(du))
            })
        .unwrap();
        for i in iter {
            $result_vec.push(i.unwrap());
        }
    }};
}

impl Uuid {
    fn new() -> Self {
        Self(Uuid_::new_v4())
    }

    fn get_xattr(&self, fs: &BiblFs, name: &str) -> Option<Vec<u8>> {
        let mut stmt = fs
            .connection
            .prepare(
                "SELECT t.data as data FROM DocumentHasTextMetadata as h, DocumentHasBinaryMetadata as hb, TextMetadata as t WHERE h.document_uuid = hb.document_uuid AND hb.metadata_uuid = ? AND t.uuid = h.metadata_uuid AND t.name = ?",
            )
            .unwrap();
        let attr_iter = stmt
            .query_map(rusqlite::params![&self.0, name], |row| {
                let v: String = row.get(0)?;
                Ok(v)
            })
            .unwrap();
        let mut ret = vec![];
        for attr in attr_iter {
            let v = attr.unwrap();
            ret.extend(v.into_bytes().into_iter());
            ret.push(0);
        }
        if ret.is_empty() {
            return None;
        }
        Some(ret)
    }

    fn has_xattr(&self, fs: &BiblFs, name: &str) -> bool {
        {
            let mut stmt = fs
            .connection
            .prepare(
                "SELECT t.uuid, t.name, t.data FROM DocumentHasTextMetadata as h, DocumentHasBinaryMetadata as hb, TextMetadata as t WHERE h.document_uuid = hb.document_uuid AND hb.metadata_uuid = ? AND t.uuid = h.metadata_uuid",
            )
            .unwrap();
            let iter = stmt
                .query_map(rusqlite::params![self], |row| {
                    let uuid: Uuid = row.get(0)?;
                    let name: String = row.get(1)?;
                    let data: String = row.get(2)?;
                    Ok((uuid, name, data))
                })
                .unwrap();
            dbg!("has_xattr", name);
            for i in iter {
                dbg!(i.unwrap());
            }
        }
        let mut stmt = fs
            .connection
            .prepare(
                "SELECT t.name FROM DocumentHasTextMetadata as h, DocumentHasBinaryMetadata as hb, TextMetadata as t WHERE h.document_uuid = hb.document_uuid AND hb.metadata_uuid = ? AND t.uuid = h.metadata_uuid AND t.name = ?",
            )
            .unwrap();
        stmt.exists(rusqlite::params![self, name]).unwrap()
    }
}

const CURRENT_TIMESTAMP_FMT: &str = "%Y-%m-%d %H:%M:%S";
const SQLITE_DATETIME_FMT: &str = "%Y-%m-%d %H:%M:%S.%N";
const SQLITE_DATETIME_FMT_LEGACY: &str = "%Y-%m-%d %H:%M:%S:%N %z";

#[derive(Clone, Copy, Debug, Eq, Hash, Ord, PartialEq, PartialOrd)]
struct DateTime(OffsetDateTime);

impl ToSql for DateTime {
    #[inline]
    fn to_sql(&self) -> Result<ToSqlOutput<'_>> {
        let time_string = self.0.to_offset(UtcOffset::UTC).format(SQLITE_DATETIME_FMT);
        Ok(ToSqlOutput::from(time_string))
    }
}

impl FromSql for DateTime {
    fn column_result(value: ValueRef<'_>) -> FromSqlResult<Self> {
        value.as_str().and_then(|s| {
            match s.len() {
                19 => PrimitiveDateTime::parse(s, CURRENT_TIMESTAMP_FMT)
                    .map(|d| DateTime(d.assume_utc())),
                23 => {
                    /* pad with zeros because time crate doesn't support a milliseconds format
                     * specifier, only %N which is subsecond nanoseconds and 9 digits */
                    let s = format!("{}000000", s);
                    PrimitiveDateTime::parse(s, SQLITE_DATETIME_FMT)
                        .map(|d| DateTime(d.assume_utc()))
                        .map_err(|err| err)
                }
                _ => PrimitiveDateTime::parse(s, SQLITE_DATETIME_FMT)
                    .map(|d| d.assume_utc())
                    .or_else(|err| {
                        OffsetDateTime::parse(s, SQLITE_DATETIME_FMT_LEGACY).map_err(|_| err)
                    })
                    .map(DateTime),
            }
            .map_err(|err| FromSqlError::Other(Box::new(err)))
        })
    }
}

impl Default for DateTime {
    fn default() -> Self {
        DateTime(OffsetDateTime::unix_epoch())
    }
}

#[derive(Clone, Copy, Debug, Default, Eq, Hash, Ord, PartialEq, PartialOrd)]
struct CreatedTime(DateTime);
#[derive(Clone, Copy, Debug, Default, Eq, Hash, Ord, PartialEq, PartialOrd)]
struct LastModifiedTime(DateTime);

impl ToSql for CreatedTime {
    #[inline]
    fn to_sql(&self) -> Result<ToSqlOutput<'_>> {
        self.0.to_sql()
    }
}

impl FromSql for CreatedTime {
    fn column_result(value: ValueRef<'_>) -> FromSqlResult<Self> {
        Ok(Self(DateTime::column_result(value)?))
    }
}

impl ToSql for LastModifiedTime {
    #[inline]
    fn to_sql(&self) -> Result<ToSqlOutput<'_>> {
        self.0.to_sql()
    }
}

impl FromSql for LastModifiedTime {
    fn column_result(value: ValueRef<'_>) -> FromSqlResult<Self> {
        Ok(Self(DateTime::column_result(value)?))
    }
}

#[derive(Clone, Copy, Debug, Default, Eq, Hash, Ord, PartialEq, PartialOrd)]
struct DocumentUuid(Uuid);
#[derive(Clone, Copy, Debug, Default, Eq, Hash, Ord, PartialEq, PartialOrd)]
struct BinaryMetadataUuid(Uuid);
#[derive(Clone, Copy, Debug, Default, Eq, Hash, Ord, PartialEq, PartialOrd)]
struct TextMetadataUuid(Uuid);

#[derive(Debug)]
struct Document {
    uuid: DocumentUuid,
    title: String,
    title_suffix: Option<String>,
    created: CreatedTime,
    last_modified: LastModifiedTime,
}

#[derive(Debug)]
struct File {
    row_id: i64,
    uuid: BinaryMetadataUuid,
    name: String,
    size: u64,
    document_uuid: DocumentUuid,
    created: CreatedTime,
    last_modified: LastModifiedTime,
}

const TTL: Duration = Duration::from_secs(1); // 1 second

const ROOT_DIR_INO: INode = 1;
const TAG_DIR_INO: INode = 2;
const QUERY_DIR_INO: INode = 3;
const SQL_TEXT_FILE_INO: INode = 4;
const SQL_TEXT_FILE_NAME: &str = "query.sql";
const SQL_RESULT_FILE_INO: INode = 5;
const SQL_RESULT_FILE_NAME: &str = "results.txt";

impl DateTime {
    fn to_systemtime(&self) -> SystemTime {
        std::time::UNIX_EPOCH + std::time::Duration::from_secs(self.0.unix_timestamp() as u64)
    }

    fn from_systemtime(val: SystemTime) -> Self {
        Self(OffsetDateTime::from(val))
    }
}

fn make_dir_attr(ino: INode) -> FileAttr {
    let uid = unsafe { libc::geteuid() };
    let gid = unsafe { libc::getgid() };
    FileAttr {
        ino,
        size: 0,
        blocks: 0,
        atime: UNIX_EPOCH, // 1970-01-01 00:00:00
        mtime: UNIX_EPOCH,
        ctime: UNIX_EPOCH,
        crtime: UNIX_EPOCH,
        kind: FileType::Directory,
        perm: 0o755,
        nlink: 2,
        uid,
        gid,
        rdev: 0,
        flags: 0,
        blksize: 512,
    }
}

const FILE_BLOCKS: u64 = 1;

fn make_file_attr(
    ino: INode,
    size: u64,
    blocks: u64,
    mtime: LastModifiedTime,
    ctime: CreatedTime,
) -> FileAttr {
    let uid = unsafe { libc::geteuid() };
    let gid = unsafe { libc::getgid() };
    FileAttr {
        ino,
        size,
        blocks,
        atime: UNIX_EPOCH, // 1970-01-01 00:00:00
        mtime: mtime.0.to_systemtime(),
        ctime: ctime.0.to_systemtime(),
        crtime: UNIX_EPOCH,
        kind: FileType::RegularFile,
        perm: 0o744,
        nlink: 1,
        uid,
        gid,
        rdev: 0,
        flags: 0,
        blksize: 512,
    }
}

struct Tag {
    //uuid: TextMetadataUuid,
    data: String,
    ino: INode,
}

#[derive(Debug, PartialEq)]
enum QueryType {
    Fts(String),
    Sql(String),
}

impl QueryType {
    fn as_ref(&self) -> &str {
        match self {
            Self::Fts(ref inner) | Self::Sql(ref inner) => inner,
        }
    }

    fn as_sql(&self) -> String {
        match self {
            Self::Fts(ref inner) => {
                format!(
                    "SELECT uuid FROM document_title_authors_text_view_fts({})",
                    inner
                )
            }
            Self::Sql(ref inner) => inner.to_string(),
        }
    }
    fn is_fts(&self) -> bool {
        matches!(self, Self::Fts(_))
    }
}

#[derive(Debug)]
struct QueryDir {
    query_inodes: HashMap<INode, String>,
    executed: bool,
    rev_query_inodes: HashMap<String, INode>,
    results: Result<Vec<DocumentUuid>, String>,
    query: QueryType,
}

struct BiblFs {
    connection: Connection,
    documents: HashMap<DocumentUuid, Document>,
    rev_inodes_doc: HashMap<DocumentUuid, Vec<INode>>,
    files: HashMap<BinaryMetadataUuid, File>,
    inodes_map: HashMap<INode, BinaryMetadataUuid>,
    rev_files: HashMap<String, BinaryMetadataUuid>,
    rev_inodes_files: HashMap<BinaryMetadataUuid, INode>,
    tags: HashMap<TextMetadataUuid, Tag>,
    rev_tags: HashMap<String, TextMetadataUuid>,
    inodes_tags: HashMap<INode, TextMetadataUuid>,
    rev_inodes_tags: HashMap<TextMetadataUuid, INode>,
    query_dir: QueryDir,
    next_inode: INode,
    // config
    never_replace_common_tags: bool,
}

impl BiblFs {
    fn document_uuid_for_ino(&self, ino: &INode) -> Option<DocumentUuid> {
        self.rev_inodes_doc
            .iter()
            .find(|(_, v)| v.contains(ino))
            .map(|(k, _)| *k)
    }

    fn select(&mut self, query_str: String) {
        self.query_dir.query = QueryType::Fts(query_str);
        self.execute_query();
    }

    fn execute_query(&mut self) {
        self.query_dir.executed = false;
        self.query_dir.results = Ok(vec![]);
        let mut stmt = self
            .connection
            .prepare("SELECT uuid FROM document_title_authors_text_view_fts(?)")
            .unwrap();
        let doc_iter = stmt
            .query_map([self.query_dir.query.as_ref()], |row| {
                let v: DocumentUuid = DocumentUuid(row.get(0)?);
                Ok(v)
            })
            .unwrap();
        self.query_dir.results = Ok(vec![]);
        let mut results_uuids = vec![];
        for doc in doc_iter {
            match doc {
                Ok(uuid) => {
                    results_uuids.push(uuid);
                }
                Err(err) => {
                    self.query_dir.results = Err(err.to_string());
                    break;
                }
            }
        }
        dbg!(&results_uuids);
        dbg!(&self.query_dir.results);
        if let Ok(v) = self.query_dir.results.as_mut() {
            *v = results_uuids;
        }
        dbg!(&self.query_dir.results);

        self.query_dir.executed = true;
    }
}

impl Filesystem for BiblFs {
    fn lookup(&mut self, _req: &Request, parent: INode, name: &OsStr, reply: ReplyEntry) {
        println!("lookup parent {:?} name {:?}", &parent, &name);
        match parent {
            parent if parent == TAG_DIR_INO => {
                if let Some(uuid) = self.rev_tags.get(name.to_str().unwrap()) {
                    let ino = self.rev_inodes_tags[uuid];
                    return reply.entry(&TTL, &make_dir_attr(ino), 0);
                }
                reply.error(ENOENT);
            }
            _ if name == "tags" => {
                reply.entry(&TTL, &make_dir_attr(TAG_DIR_INO), 0);
                //reply.error(ENOENT);
            }
            _ if name == SQL_TEXT_FILE_NAME => {
                reply.entry(
                    &TTL,
                    &make_file_attr(
                        SQL_TEXT_FILE_INO,
                        self.query_dir
                            .query
                            .as_sql()
                            .len()
                            .try_into()
                            .unwrap_or_default(),
                        FILE_BLOCKS,
                        Default::default(),
                        Default::default(),
                    ),
                    0,
                );
            }
            _ if name == SQL_RESULT_FILE_NAME => {
                reply.entry(
                    &TTL,
                    &make_file_attr(
                        SQL_RESULT_FILE_INO,
                        self.query_dir
                            .query
                            .as_sql()
                            .len()
                            .try_into()
                            .unwrap_or_default(),
                        FILE_BLOCKS,
                        Default::default(),
                        Default::default(),
                    ),
                    0,
                );
            }
            parent if parent == QUERY_DIR_INO => match name.to_str() {
                Some(name) => {
                    let query_ino =
                        if let Some(query_ino) = self.query_dir.rev_query_inodes.get(name) {
                            *query_ino
                        } else {
                            let new_query_ino = self.next_inode;
                            self.next_inode += 1;
                            self.query_dir.query = QueryType::Fts(name.to_string());
                            self.query_dir
                                .rev_query_inodes
                                .insert(name.to_string(), new_query_ino);
                            self.query_dir
                                .query_inodes
                                .insert(new_query_ino, name.to_string());
                            new_query_ino
                        };
                    self.query_dir.executed = false;
                    reply.entry(&TTL, &make_dir_attr(query_ino), 0);
                }
                None => {
                    self.query_dir.results = Err("Could not convert query to utf-8.".to_string());
                }
            },
            _ if name == "query" => {
                reply.entry(&TTL, &make_dir_attr(QUERY_DIR_INO), 0);
                //reply.error(ENOENT);
            }
            _ if name == "" => {
                reply.entry(&TTL, &make_dir_attr(QUERY_DIR_INO), 0);
                //reply.error(ENOENT);
            }
            _ => {
                if let Some(uuid) = self.rev_files.get(name.to_str().unwrap()) {
                    let ino = self.rev_inodes_files[uuid];
                    let f = &self.files[uuid];
                    return reply.entry(
                        &TTL,
                        &make_file_attr(ino, f.size, FILE_BLOCKS, f.last_modified, f.created),
                        0,
                    );
                }
                reply.error(ENOENT);
            }
        }
    }

    fn getattr(&mut self, _req: &Request, ino: INode, reply: ReplyAttr) {
        eprintln!("getattr ino {}", &ino);
        match ino {
            i if i == ROOT_DIR_INO => reply.attr(&TTL, &make_dir_attr(ROOT_DIR_INO)),
            i if i == TAG_DIR_INO => reply.attr(&TTL, &make_dir_attr(TAG_DIR_INO)),
            i if i == QUERY_DIR_INO => reply.attr(&TTL, &make_dir_attr(QUERY_DIR_INO)),
            i if i == SQL_TEXT_FILE_INO => reply.attr(
                &TTL,
                &make_file_attr(
                    SQL_TEXT_FILE_INO,
                    self.query_dir
                        .query
                        .as_sql()
                        .len()
                        .try_into()
                        .unwrap_or_default(),
                    FILE_BLOCKS,
                    Default::default(),
                    Default::default(),
                ),
            ),
            i if i == SQL_RESULT_FILE_INO => reply.attr(
                &TTL,
                &make_file_attr(
                    SQL_TEXT_FILE_INO,
                    self.query_dir
                        .results
                        .as_ref()
                        .map(|v| v.len())
                        .map_err(|err| err.len())
                        .unwrap_or_else(|err| err)
                        .try_into()
                        .unwrap_or_default(),
                    FILE_BLOCKS,
                    Default::default(),
                    Default::default(),
                ),
            ),
            i if self.query_dir.query_inodes.contains_key(&i) => {
                reply.attr(&TTL, &make_dir_attr(i))
            }
            i if self.inodes_map.contains_key(&i) => {
                let f = &self.files[&self.inodes_map[&ino]];
                reply.attr(
                    &TTL,
                    &make_file_attr(ino, f.size, FILE_BLOCKS, f.last_modified, f.created),
                )
            }
            i if self.inodes_tags.contains_key(&i) => reply.attr(&TTL, &make_dir_attr(ino)),
            _ => reply.error(ENOENT),
        }
    }

    /// Read data.
    /// Read should send exactly the number of bytes requested except on EOF or error,
    /// otherwise the rest of the data will be substituted with zeroes. An exception to
    /// this is when the file has been opened in 'direct_io' mode, in which case the
    /// return value of the read system call will reflect the return value of this
    /// operation. fh will contain the value set by the open method, or will be undefined
    /// if the open method didn't set any value.
    ///
    /// flags: these are the file flags, such as O_SYNC. Only supported with ABI >= 7.9
    /// lock_owner: only supported with ABI >= 7.9
    fn read(
        &mut self,
        _req: &Request,
        ino: INode,
        _fh: u64,
        offset: i64,
        size: u32,
        _flags: i32,
        _lock: Option<u64>,
        reply: ReplyData,
    ) {
        println!(
            "read ino {:?} _fh {:?} offset {:?} size {:?} _flags {:?} _lock {:?}",
            &ino, &_fh, &offset, &size, &_flags, &_lock
        );
        match ino {
            i if i == SQL_TEXT_FILE_INO => {
                if !self.query_dir.executed {
                    self.execute_query();
                }
                reply.data(&self.query_dir.query.as_sql().as_bytes());
                return;
            }
            i if i == SQL_RESULT_FILE_INO => {
                if !self.query_dir.executed {
                    self.execute_query();
                }
                match self.query_dir.results.as_ref() {
                    Ok(uuids) => {
                        let s = uuids
                            .iter()
                            .map(|u| u.0 .0.to_hyphenated().to_string())
                            .collect::<Vec<String>>()
                            .join("\n");

                        reply.data(s.as_bytes());
                    }
                    Err(err) => {
                        reply.data(err.as_bytes());
                    }
                }
                return;
            }
            _ => {}
        }

        if !self.inodes_map.contains_key(&ino) {
            reply.error(ENOENT);
            return;
        }
        let row_id = self.files[&self.inodes_map[&ino]].row_id;
        let blob = self
            .connection
            .blob_open(DatabaseName::Main, "BinaryMetadata", "data", row_id, true)
            .unwrap();
        dbg!(offset, blob.len());
        let mut buf =
            vec![0; std::cmp::min(size as usize, blob.len().saturating_sub(offset as usize))];
        dbg!(buf.len());
        blob.read_at_exact(&mut buf, offset as usize).unwrap();

        reply.data(&buf);
    }

    fn readdir(
        &mut self,
        _req: &Request,
        ino: INode,
        _fh: u64,
        offset: i64,
        mut reply: ReplyDirectory,
    ) {
        println!(
            "readdir: ino {:?} _fh {:?} offset {:?}",
            &ino, &_fh, &offset
        );

        let entries = match ino {
            ino if ino == TAG_DIR_INO => {
                println!("tags");
                let mut ret = vec![
                    (TAG_DIR_INO, FileType::Directory, "."),
                    (ROOT_DIR_INO, FileType::Directory, ".."),
                ];

                for t in self.tags.values() {
                    ret.push((t.ino, FileType::Directory, &t.data));
                }
                ret
            }
            ino if ino == QUERY_DIR_INO => {
                println!("query");
                vec![
                    (QUERY_DIR_INO, FileType::Directory, "."),
                    (ROOT_DIR_INO, FileType::Directory, ".."),
                    (SQL_TEXT_FILE_INO, FileType::RegularFile, "query.sql"),
                ]
            }
            ino if self.query_dir.query_inodes.contains_key(&ino) => {
                let mut ret = vec![
                    (ino, FileType::Directory, "."),
                    (QUERY_DIR_INO, FileType::Directory, ".."),
                    (SQL_TEXT_FILE_INO, FileType::RegularFile, SQL_TEXT_FILE_NAME),
                    (
                        SQL_RESULT_FILE_INO,
                        FileType::RegularFile,
                        SQL_RESULT_FILE_NAME,
                    ),
                ];
                let query_s = &self.query_dir.query_inodes[&ino];
                println!("query_s {} query_dir = {:?}", query_s, &self.query_dir);
                if !(self.query_dir.query.is_fts()
                    && query_s == self.query_dir.query.as_ref()
                    && self.query_dir.executed)
                {
                    let q = query_s.to_string();
                    self.select(q);
                }
                if let Ok(v) = self.query_dir.results.as_ref() {
                    for uuid in v {
                        /* Doc might not have files so use get() instead of indexing: */
                        if let Some(doc_inos) = self.rev_inodes_doc.get(&uuid) {
                            for file_ino in doc_inos {
                                let file_uuid = &self.inodes_map[&file_ino];
                                let file = &self.files[file_uuid];
                                ret.push((*file_ino, FileType::RegularFile, &file.name));
                            }
                        }
                    }
                }
                ret
            }
            ino if ino == ROOT_DIR_INO => {
                println!("root");
                vec![
                    (ROOT_DIR_INO, FileType::Directory, "."),
                    (ROOT_DIR_INO, FileType::Directory, ".."),
                ]
            }
            ino if self.inodes_tags.contains_key(&ino) => {
                let mut ret = vec![
                    (ino, FileType::Directory, "."),
                    (TAG_DIR_INO, FileType::Directory, ".."),
                ];

                let u = &self.inodes_tags[&ino];
                println!("{}", u.0 .0.to_hyphenated());
                let mut stmt = self
                    .connection
                    .prepare(
                        "SELECT document_uuid FROM DocumentHasTextMetadata WHERE metadata_uuid = ?",
                    )
                    .unwrap();
                let doc_iter = stmt
                    .query_map([&u.0], |row| {
                        let v: DocumentUuid = DocumentUuid(row.get(0)?);
                        Ok(v)
                    })
                    .unwrap();
                for doc in doc_iter {
                    let uuid = doc.unwrap();
                    /* Doc might not have files so use get() instead of indexing: */
                    if let Some(doc_inos) = self.rev_inodes_doc.get(&uuid) {
                        for file_ino in doc_inos {
                            let file_uuid = &self.inodes_map[&file_ino];
                            let file = &self.files[file_uuid];
                            ret.push((*file_ino, FileType::RegularFile, &file.name));
                        }
                    }
                }
                ret
            }
            _ => {
                reply.error(ENOENT);
                return;
            }
        };

        let mut index_offset: i64 = 0;
        for (i, entry) in entries.into_iter().enumerate().skip(offset as usize) {
            // i + 1 means the index of the next entry
            index_offset = (i + 1) as i64;
            if reply.add(entry.0, (i + 1) as i64, entry.1, entry.2) {
                break;
            }
        }

        if ino == ROOT_DIR_INO {
            for (i, (inode, uuid)) in self.inodes_map.iter().enumerate().skip(offset as usize) {
                let filename = &self.files[&uuid].name;
                // i + 1 means the index of the next entry
                if reply.add(
                    *inode,
                    index_offset + (i + 1) as i64,
                    FileType::RegularFile,
                    filename,
                ) {
                    break;
                }
            }
        }
        reply.ok();
    }

    /// Set file attributes.
    fn setattr(
        &mut self,
        _req: &Request<'_>,
        ino: INode,
        mode: Option<u32>,
        uid: Option<u32>,
        gid: Option<u32>,
        size: Option<u64>,
        atime: Option<TimeOrNow>,
        mtime: Option<TimeOrNow>,
        ctime: Option<SystemTime>,
        fh: Option<u64>,
        crtime: Option<SystemTime>,
        chgtime: Option<SystemTime>,
        bkuptime: Option<SystemTime>,
        flags: Option<u32>,
        reply: ReplyAttr,
    ) {
        println!(
            "setattr:  ino = {:?} &mode = {:?} &uid = {:?} &gid = {:?} &size = {:?} &atime =
            {:?} &mtime = {:?} &ctime = {:?} &fh = {:?} &crtime = {:?} &chgtime = {:?} &bkuptime =
            {:?} &flags = {:?}",
            ino,
            &mode,
            &uid,
            &gid,
            &size,
            &atime,
            &mtime,
            &ctime,
            &fh,
            &crtime,
            &chgtime,
            &bkuptime,
            &flags
        );
        if mode.is_some()
            || uid.is_some()
            || gid.is_some()
            || size.is_some()
            || atime.is_some()
            || mtime.is_some()
            || ctime.is_some()
            || fh.is_some()
            || crtime.is_some()
            || chgtime.is_some()
            || bkuptime.is_some()
            || flags.is_some()
        {
            return reply.error(ENOSYS);
        }
        if let Some(u) = self.inodes_map.get(&ino) {
            let f = &self.files[u];
            if mtime.is_none() && ctime.is_none() {
                return reply.attr(
                    &TTL,
                    &make_file_attr(ino, f.size, FILE_BLOCKS, f.last_modified, f.created),
                );
            }
            let f = self.files.get_mut(u).unwrap();
            match mtime {
                Some(TimeOrNow::SpecificTime(mtime)) => {
                    f.last_modified = LastModifiedTime(DateTime::from_systemtime(mtime));
                }
                Some(TimeOrNow::Now) => {
                    f.last_modified =
                        LastModifiedTime(DateTime::from_systemtime(SystemTime::now()));
                }
                None => {}
            }
            match ctime {
                Some(ctime) => {
                    f.created = CreatedTime(DateTime::from_systemtime(ctime));
                }
                None => {}
            }
            let f = &self.files[u];
            return reply.attr(
                &TTL,
                &make_file_attr(ino, f.size, FILE_BLOCKS, f.last_modified, f.created),
            );
        } else {
            return reply.error(ENOENT);
        }
    }

    /// Read symbolic link.
    fn readlink(&mut self, _req: &Request<'_>, ino: INode, reply: ReplyData) {
        println!("readlink: {}", ino);
        reply.error(ENOSYS);
    }

    /// Create file node.
    /// Create a regular file, character device, block device, fifo or socket node.
    fn mknod(
        &mut self,
        _req: &Request<'_>,
        parent: INode,
        name: &OsStr,
        _mode: u32,
        _umask: u32,
        _rdev: u32,
        reply: ReplyEntry,
    ) {
        println!("mknod: {} name {}", parent, name.to_str().unwrap());
        reply.error(ENOSYS);
    }

    /// Create a directory.
    fn mkdir(
        &mut self,
        _req: &Request<'_>,
        parent: INode,
        name: &OsStr,
        _mode: u32,
        _umask: u32,
        reply: ReplyEntry,
    ) {
        println!("mkdir: {} name {}", parent, name.to_str().unwrap());
        reply.error(ENOSYS);
    }

    /// Remove a file.
    fn unlink(&mut self, _req: &Request<'_>, parent: INode, name: &OsStr, reply: ReplyEmpty) {
        println!("unlink: {} name {}", parent, name.to_str().unwrap());
        reply.error(ENOSYS);
    }

    /// Remove a directory.
    fn rmdir(&mut self, _req: &Request<'_>, parent: INode, name: &OsStr, reply: ReplyEmpty) {
        println!("rmdir: {} name {}", parent, name.to_str().unwrap());
        reply.error(ENOSYS);
    }

    /// Create a symbolic link.
    fn symlink(
        &mut self,
        _req: &Request<'_>,
        parent: INode,
        name: &OsStr,
        _link: &Path,
        reply: ReplyEntry,
    ) {
        println!("symlink: {} name {}", parent, name.to_str().unwrap());
        reply.error(ENOSYS);
    }

    /// Rename a file.
    fn rename(
        &mut self,
        _req: &Request<'_>,
        parent: INode,
        name: &OsStr,
        _newparent: INode,
        _newname: &OsStr,
        _flags: u32,
        reply: ReplyEmpty,
    ) {
        println!("rename: {} name {}", parent, name.to_str().unwrap());
        reply.error(ENOSYS);
    }

    /// Create a hard link.
    fn link(
        &mut self,
        _req: &Request<'_>,
        ino: INode,
        newparent: INode,
        newname: &OsStr,
        reply: ReplyEntry,
    ) {
        println!(
            "link: {} newparent {} newname {}",
            ino,
            newparent,
            newname.to_str().unwrap()
        );
        reply.error(ENOSYS);
    }

    /// Open a file.
    /// Open flags (with the exception of O_CREAT, O_EXCL, O_NOCTTY and O_TRUNC) are
    /// available in flags. Filesystem may store an arbitrary file handle (pointer, index,
    /// etc) in fh, and use this in other all other file operations (read, write, flush,
    /// release, fsync). Filesystem may also implement stateless file I/O and not store
    /// anything in fh. There are also some flags (direct_io, keep_cache) which the
    /// filesystem may set, to change the way the file is opened. See fuse_file_info
    /// structure in <fuse_common.h> for more details.
    fn open(&mut self, _req: &Request<'_>, ino: INode, _flags: i32, reply: ReplyOpen) {
        println!("open: {}", ino);
        reply.opened(0, 0);
    }

    /// Write data.
    /// Write should return exactly the number of bytes requested except on error. An
    /// exception to this is when the file has been opened in 'direct_io' mode, in
    /// which case the return value of the write system call will reflect the return
    /// value of this operation. fh will contain the value set by the open method, or
    /// will be undefined if the open method didn't set any value.
    ///
    /// write_flags: will contain FUSE_WRITE_CACHE, if this write is from the page cache. If set,
    /// the pid, uid, gid, and fh may not match the value that would have been sent if write cachin
    /// is disabled
    /// flags: these are the file flags, such as O_SYNC. Only supported with ABI >= 7.9
    /// lock_owner: only supported with ABI >= 7.9
    fn write(
        &mut self,
        _req: &Request<'_>,
        ino: INode,
        _fh: u64,
        _offset: i64,
        _data: &[u8],
        _write_flags: u32,
        _flags: i32,
        _lock_owner: Option<u64>,
        reply: ReplyWrite,
    ) {
        println!("write ino {}", ino);
        match ino {
            i if i == SQL_TEXT_FILE_INO => {
                //reply.data(&self.query_dir.query.as_sql().as_bytes());
            }
            i if i == SQL_RESULT_FILE_INO => {}
            _ => {}
        }

        reply.error(ENOENT);
    }

    /// Flush method.
    /// This is called on each close() of the opened file. Since file descriptors can
    /// be duplicated (dup, dup2, fork), for one open call there may be many flush
    /// calls. Filesystems shouldn't assume that flush will always be called after some
    /// writes, or that if will be called at all. fh will contain the value set by the
    /// open method, or will be undefined if the open method didn't set any value.
    /// NOTE: the name of the method is misleading, since (unlike fsync) the filesystem
    /// is not forced to flush pending writes. One reason to flush data, is if the
    /// filesystem wants to return write errors. If the filesystem supports file locking
    /// operations (setlk, getlk) it should remove all locks belonging to 'lock_owner'.
    fn flush(
        &mut self,
        _req: &Request<'_>,
        ino: INode,
        _fh: u64,
        _lock_owner: u64,
        reply: ReplyEmpty,
    ) {
        println!("flush: {}", ino);
        reply.error(ENOSYS);
    }

    /// Release an open file.
    /// Release is called when there are no more references to an open file: all file
    /// descriptors are closed and all memory mappings are unmapped. For every open
    /// call there will be exactly one release call. The filesystem may reply with an
    /// error, but error values are not returned to close() or munmap() which triggered
    /// the release. fh will contain the value set by the open method, or will be undefined
    /// if the open method didn't set any value. flags will contain the same flags as for
    /// open.
    fn release(
        &mut self,
        _req: &Request<'_>,
        ino: INode,
        _fh: u64,
        _flags: i32,
        _lock_owner: Option<u64>,
        _flush: bool,
        reply: ReplyEmpty,
    ) {
        println!("release: {}", ino);
        reply.ok();
    }

    /// Synchronize file contents.
    /// If the datasync parameter is non-zero, then only the user data should be flushed,
    /// not the meta data.
    fn fsync(
        &mut self,
        _req: &Request<'_>,
        ino: INode,
        _fh: u64,
        _datasync: bool,
        reply: ReplyEmpty,
    ) {
        println!("fsync: {}", ino);
        reply.error(ENOSYS);
    }

    /// Open a directory.
    /// Filesystem may store an arbitrary file handle (pointer, index, etc) in fh, and
    /// use this in other all other directory stream operations (readdir, releasedir,
    /// fsyncdir). Filesystem may also implement stateless directory I/O and not store
    /// anything in fh, though that makes it impossible to implement standard conforming
    /// directory stream operations in case the contents of the directory can change
    /// between opendir and releasedir.
    fn opendir(&mut self, _req: &Request<'_>, ino: INode, _flags: i32, reply: ReplyOpen) {
        println!("opendir: {}", ino);
        reply.opened(0, 0);
    }

    /// Read directory.
    /// Send a buffer filled using buffer.fill(), with size not exceeding the
    /// requested size. Send an empty buffer on end of stream. fh will contain the
    /// value set by the opendir method, or will be undefined if the opendir method
    /// didn't set any value.
    fn readdirplus(
        &mut self,
        _req: &Request<'_>,
        ino: INode,
        _fh: u64,
        _offset: i64,
        reply: ReplyDirectoryPlus,
    ) {
        println!("readdirplus: {}", ino);
        reply.error(ENOSYS);
    }

    /// Release an open directory.
    /// For every opendir call there will be exactly one releasedir call. fh will
    /// contain the value set by the opendir method, or will be undefined if the
    /// opendir method didn't set any value.
    fn releasedir(
        &mut self,
        _req: &Request<'_>,
        ino: INode,
        _fh: u64,
        _flags: i32,
        reply: ReplyEmpty,
    ) {
        println!("releasedir: {}", ino);
        reply.ok();
    }

    /// Synchronize directory contents.
    /// If the datasync parameter is set, then only the directory contents should
    /// be flushed, not the meta data. fh will contain the value set by the opendir
    /// method, or will be undefined if the opendir method didn't set any value.
    fn fsyncdir(
        &mut self,
        _req: &Request<'_>,
        ino: INode,
        _fh: u64,
        _datasync: bool,
        reply: ReplyEmpty,
    ) {
        println!("fsyncdir: {}", ino);
        reply.error(ENOSYS);
    }

    /// Get file system statistics.
    fn statfs(&mut self, _req: &Request<'_>, ino: INode, reply: ReplyStatfs) {
        println!("statfs: {}", ino);
        reply.statfs(0, 0, 0, 0, 0, 512, 255, 0);
    }

    /// Set an extended attribute.
    fn setxattr(
        &mut self,
        _req: &Request<'_>,
        ino: INode,
        name: &OsStr,
        value: &[u8],
        flags: i32,
        _position: u32,
        reply: ReplyEmpty,
    ) {
        println!(
            "setxattr: {} name {:?} value: {:?}",
            ino,
            name.to_str().unwrap(),
            String::from_utf8_lossy(value)
        );
        let Some(name) = name.to_str() else {
            println!(
                "name is not a valid UTF-8 string, which is not supported. Value was {:?}",
                String::from_utf8_lossy(name.as_bytes())
            );
            reply.error(ENOTSUP);
            return;
        };
        let Ok(value) = core::str::from_utf8(value) else {
            println!(
                "value is not a valid UTF-8 string, which is not supported. Value was {:?}",
                String::from_utf8_lossy(value)
            );
            reply.error(ENOTSUP);
            return;
        };
        let create_flag = flags & libc::XATTR_CREATE > 0;
        let replace_flag = flags & libc::XATTR_REPLACE > 0;
        if !self.inodes_map.contains_key(&ino) {
            reply.error(dbg!(ENOENT));
            return;
        }
        let u = &self.inodes_map[&ino];
        let exists = u.0.has_xattr(&self, name);
        if create_flag && exists {
            reply.error(dbg!(EEXIST));
            return;
        } else if replace_flag && !exists {
            reply.error(dbg!(ENODATA));
            return;
        }
        println!("{}", u.0 .0.to_hyphenated());

        let mut new_attr = Uuid::new();
        let document_uuid = self.document_uuid_for_ino(&ino).unwrap();

        let tx = self.connection.transaction().unwrap();
        {
            if exists {
                let t_uuid: TextMetadataUuid;
                xattr_text_document_uuid_by_name! { tx, u, name, t_uuid };
                new_attr.0 = t_uuid.0 .0;
                if replace_flag && self.never_replace_common_tags {
                    let mut document_owner_uuids: Vec<DocumentUuid> = vec![];
                    documents_that_have_xattr! { tx, t_uuid, document_owner_uuids except document_uuid };
                    if !document_owner_uuids.is_empty() {
                        println!(
                            "Cannot replace an attribute that belongs to other documents as well:"
                        );
                        for du in document_owner_uuids {
                            let doc = &self.documents[&du];
                            println!(
                                "Document {}{}{}{}{} [{}] has attribute {}.",
                                doc.title,
                                if doc.title_suffix.is_some() { " " } else { "" },
                                if doc.title_suffix.is_some() { "(" } else { "" },
                                if let Some(v) = doc.title_suffix.as_ref() {
                                    &v
                                } else {
                                    ""
                                },
                                if doc.title_suffix.is_some() { ")" } else { "" },
                                (du.0).0.to_hyphenated(),
                                name,
                            );
                        }
                        reply.error(ENOTSUP);
                        return;
                    }
                }
            }
            let mut stmt = if create_flag {
                tx
            .prepare(
                "INSERT OR ABORT INTO TextMetadata (uuid,name,data) VALUES(?,?,?) RETURNING uuid",
            )
            .unwrap()
            } else {
                tx
            .prepare(
                "INSERT OR REPLACE INTO TextMetadata (uuid,name,data) VALUES(?,?,?) RETURNING uuid",
            )
            .unwrap()
            };
            let res = stmt
                .query_row(rusqlite::params![&new_attr, &name, value], |row| {
                    let u: Uuid = row.get(0)?;
                    Ok(u)
                })
                .unwrap();
            assert_eq!(res, new_attr);
            println!("New text metadata uuid is {}", new_attr.0.to_hyphenated());
        }
        {
            let mut stmt = if create_flag {
                tx
                    .prepare(
                        "INSERT OR ABORT INTO DocumentHasTextMetadata (name,document_uuid,metadata_uuid) VALUES(?,?,?) RETURNING id",
                    )
                    .unwrap()
            } else {
                tx
                    .prepare(
                        "INSERT OR IGNORE INTO DocumentHasTextMetadata (name,document_uuid,metadata_uuid) VALUES(?,?,?) RETURNING id",
                    )
                    .unwrap()
            };
            let res = stmt
                .query_row(
                    rusqlite::params!["xattr(7)", &document_uuid.0, &new_attr],
                    |row| {
                        let u: i64 = row.get(0)?;
                        Ok(u)
                    },
                )
                .unwrap();
            println!("New has text metadata id is {}", res);
        }

        tx.commit().unwrap();
        reply.ok();
    }

    /// Get an extended attribute.
    /// If `size` is 0, the size of the value should be sent with `reply.size()`.
    /// If `size` is not 0, and the value fits, send it with `reply.data()`, or
    /// `reply.error(ERANGE)` if it doesn't.
    fn getxattr(
        &mut self,
        _req: &Request<'_>,
        ino: INode,
        name: &OsStr,
        size: u32,
        reply: ReplyXattr,
    ) {
        println!("getxattr: {} name {:?}", ino, name.to_str().unwrap());
        if !self.inodes_map.contains_key(&ino) {
            dbg!(reply.error(ENOENT));
            return;
        }
        let u = &self.inodes_map[&ino];
        println!("{}", u.0 .0.to_hyphenated());
        let mut stmt = self
            .connection
            .prepare(
                "SELECT t.data as data FROM DocumentHasTextMetadata as h, DocumentHasBinaryMetadata as hb, TextMetadata as t WHERE h.document_uuid = hb.document_uuid AND hb.metadata_uuid = ? AND t.uuid = h.metadata_uuid AND t.name = ?",
            )
            .unwrap();
        let attr_iter = stmt
            .query_map(
                rusqlite::params![&u.0, dbg!(&name.to_str().unwrap())],
                |row| {
                    let v: String = row.get(0)?;
                    dbg!(&v);
                    Ok(v)
                },
            )
            .unwrap();
        let mut ret = vec![];
        for attr in attr_iter {
            let v = attr.unwrap();
            dbg!(&v);
            ret.extend(v.into_bytes().into_iter());
            ret.push(0);
        }
        if ret.len() as u32 <= size {
            reply.data(&ret);
        } else if size > 0 {
            reply.error(ERANGE);
        } else {
            reply.size(ret.len() as u32);
        }
    }

    /// List extended attribute names.
    /// If `size` is 0, the size of the value should be sent with `reply.size()`.
    /// If `size` is not 0, and the value fits, send it with `reply.data()`, or
    /// `reply.error(ERANGE)` if it doesn't.
    fn listxattr(&mut self, _req: &Request<'_>, ino: INode, size: u32, reply: ReplyXattr) {
        println!("listxattr: {}", ino);
        let u = &self.inodes_map[&ino];
        println!("{}", u.0 .0.to_hyphenated());
        let mut stmt = self
            .connection
            .prepare(
                "SELECT t.name as name FROM DocumentHasTextMetadata as h, DocumentHasBinaryMetadata as hb, TextMetadata as t WHERE h.document_uuid = hb.document_uuid AND hb.metadata_uuid = ? AND t.uuid = h.metadata_uuid ORDER BY t.last_modified ASC",
            )
            .unwrap();
        let mut ret = vec![];
        let attr_iter = stmt
            .query_map([&u.0], |row| {
                let n: String = row.get(0)?;
                Ok(n)
            })
            .unwrap();
        for attr in attr_iter {
            let n = attr.unwrap();
            eprintln!("listxattr n = {}", &n);
            ret.extend(n.into_bytes().into_iter());
            ret.push(0);
        }
        eprintln!("listxattr reply data: {:?}", String::from_utf8_lossy(&ret));
        if ret.len() as u32 <= size {
            reply.data(&ret);
        } else if size > 0 {
            reply.error(ERANGE);
        } else {
            reply.size(ret.len() as u32);
        }
    }

    /// Remove an extended attribute.
    fn removexattr(&mut self, _req: &Request<'_>, ino: INode, name: &OsStr, reply: ReplyEmpty) {
        println!("removexattr: {} name {:?}", ino, name.to_str().unwrap(),);
        let Some(name) = name.to_str() else {
            println!(
                "name is not a valid UTF-8 string, which is not supported. Value was {:?}",
                String::from_utf8_lossy(name.as_bytes())
            );
            reply.error(ENOTSUP);
            return;
        };
        if !self.inodes_map.contains_key(&ino) {
            reply.error(dbg!(ENOENT));
            return;
        }
        let u = &self.inodes_map[&ino];
        dbg!(ino, &u, &name);
        if !u.0.has_xattr(&self, name) {
            return reply.error(dbg!(ENODATA));
        }
        println!("{}", u.0 .0.to_hyphenated());
        let document_uuid = self
            .rev_inodes_doc
            .iter()
            .find(|(_, v)| v.contains(&ino))
            .unwrap()
            .0;

        let tx = self.connection.transaction().unwrap();
        {
            let mut document_owner_uuids: Vec<DocumentUuid> = vec![];
            let t_uuid: TextMetadataUuid;
            {
                xattr_text_document_uuid_by_name! { tx, u, name, t_uuid };
            }
            {
                documents_that_have_xattr! { tx, t_uuid, document_owner_uuids except document_uuid };
            }
            {
                let mut stmt = tx
                    .prepare(
                        "DELETE FROM DocumentHasTextMetadata as h WHERE h.metadata_uuid = ? AND h.document_uuid = ? RETURNING document_uuid",
                    )
                    .unwrap();
                let ret_du = stmt
                    .query_row(rusqlite::params![&t_uuid.0, &document_uuid.0], |row| {
                        let du: Uuid = row.get(0)?;
                        Ok(DocumentUuid(du))
                    })
                    .unwrap();
                assert_eq!(ret_du, *document_uuid);
            }
            if document_owner_uuids.is_empty() {
                let mut stmt = tx
                    .prepare("DELETE FROM TextMetadata as t WHERE t.uuid = ? RETURNING uuid")
                    .unwrap();
                let ret_tu_brute = stmt
                    .query_row(rusqlite::params![&t_uuid.0], |row| {
                        let tu: Uuid = row.get(0)?;
                        Ok(TextMetadataUuid(tu))
                    })
                    .unwrap();
                assert_eq!(ret_tu_brute, t_uuid);
            }
        }

        tx.commit().unwrap();
        reply.ok();
    }

    /// Check file access permissions.
    /// This will be called for the access() system call. If the 'default_permissions'
    /// mount option is given, this method is not called. This method is not called
    /// under Linux kernel versions 2.4.x
    fn access(&mut self, _req: &Request<'_>, ino: INode, _mask: i32, reply: ReplyEmpty) {
        println!("access: {}", ino);
        reply.error(ENOSYS);
    }

    /// Create and open a file.
    /// If the file does not exist, first create it with the specified mode, and then
    /// open it. Open flags (with the exception of O_NOCTTY) are available in flags.
    /// Filesystem may store an arbitrary file handle (pointer, index, etc) in fh,
    /// and use this in other all other file operations (read, write, flush, release,
    /// fsync). There are also some flags (direct_io, keep_cache) which the
    /// filesystem may set, to change the way the file is opened. See fuse_file_info
    /// structure in <fuse_common.h> for more details. If this method is not
    /// implemented or under Linux kernel versions earlier than 2.6.15, the mknod()
    /// and open() methods will be called instead.
    fn create(
        &mut self,
        _req: &Request<'_>,
        parent: INode,
        name: &OsStr,
        _mode: u32,
        _umask: u32,
        _flags: i32,
        reply: ReplyCreate,
    ) {
        println!("create: parent {} name {}", parent, name.to_str().unwrap());
        reply.error(ENOSYS);
    }

    /// Test for a POSIX file lock.
    fn getlk(
        &mut self,
        _req: &Request<'_>,
        _ino: INode,
        _fh: u64,
        _lock_owner: u64,
        _start: u64,
        _end: u64,
        _typ: i32,
        _pid: u32,
        reply: ReplyLock,
    ) {
        reply.error(ENOSYS);
    }

    /// Acquire, modify or release a POSIX file lock.
    /// For POSIX threads (NPTL) there's a 1-1 relation between pid and owner, but
    /// otherwise this is not always the case.  For checking lock ownership,
    /// 'fi->owner' must be used. The l_pid field in 'struct flock' should only be
    /// used to fill in this field in getlk(). Note: if the locking methods are not
    /// implemented, the kernel will still allow file locking to work locally.
    /// Hence these are only interesting for network filesystems and similar.
    fn setlk(
        &mut self,
        _req: &Request<'_>,
        _ino: INode,
        _fh: u64,
        _lock_owner: u64,
        _start: u64,
        _end: u64,
        _typ: i32,
        _pid: u32,
        _sleep: bool,
        reply: ReplyEmpty,
    ) {
        reply.error(ENOSYS);
    }

    /// Map block index within file to block index within device.
    /// Note: This makes sense only for block device backed filesystems mounted
    /// with the 'blkdev' option
    fn bmap(
        &mut self,
        _req: &Request<'_>,
        _ino: INode,
        _blocksize: u32,
        _idx: u64,
        reply: ReplyBmap,
    ) {
        reply.error(ENOSYS);
    }

    /// control device
    fn ioctl(
        &mut self,
        _req: &Request<'_>,
        _ino: INode,
        _fh: u64,
        _flags: u32,
        _cmd: u32,
        _in_data: &[u8],
        _out_size: u32,
        reply: ReplyIoctl,
    ) {
        reply.error(ENOSYS);
    }

    /// Preallocate or deallocate space to a file
    fn fallocate(
        &mut self,
        _req: &Request<'_>,
        _ino: INode,
        _fh: u64,
        _offset: i64,
        _length: i64,
        _mode: i32,
        reply: ReplyEmpty,
    ) {
        reply.error(ENOSYS);
    }

    /// Reposition read/write file offset
    fn lseek(
        &mut self,
        _req: &Request<'_>,
        ino: INode,
        _fh: u64,
        offset: i64,
        whence: i32,
        reply: ReplyLseek,
    ) {
        println!("lseek: {} offset {} whence {}", ino, offset, whence);
        reply.error(ENOSYS);
    }

    /// Copy the specified range from the source inode to the destination inode
    fn copy_file_range(
        &mut self,
        _req: &Request<'_>,
        ino_in: INode,
        _fh_in: u64,
        offset_in: i64,
        ino_out: INode,
        _fh_out: u64,
        offset_out: i64,
        len: u64,
        _flags: u32,
        reply: ReplyWrite,
    ) {
        println!(
            "copy_file_range: ino in {} offset in {} ino out {} offset out {} len {}",
            ino_in, offset_in, ino_out, offset_out, len
        );
        reply.error(ENOSYS);
    }
}

fn main() -> Result<()> {
    let matches = App::new("biblfs")
        .version(crate_version!())
        .author("")
        .arg(
            Arg::with_name("mount-point")
                .long("mount-point")
                .value_name("MOUNT_POINT")
                .required(true)
                .help("Act as a client, and mount FUSE at given path")
                .takes_value(true),
        )
        .arg(
            Arg::with_name("db")
                .long("database")
                .requires("mount-point")
                .help("Mount sqlite db")
                .value_name("DATABASE_FILE")
                .takes_value(true),
        )
        .arg(
            Arg::with_name("fsck")
                .long("fsck")
                .help("Run a filesystem check"),
        )
        .arg(
            Arg::with_name("v")
                .short("v")
                .multiple(true)
                .help("Sets the level of verbosity"),
        )
        .get_matches();

    let _verbosity: u64 = matches.occurrences_of("v");
    let db_path = matches.value_of("db").unwrap_or("bibliothecula.db");
    let connection =
        Connection::open_with_flags(&db_path, rusqlite::OpenFlags::SQLITE_OPEN_READ_WRITE)?;

    let mountpoint = matches.value_of("mount-point").unwrap();
    /*
    let mut options = vec![
        MountOption::RO,
        MountOption::FSName("bibliothecula".to_string()),
        MountOption::AutoUnmount,
    ];
    */
    let options = &[
        //OsStr::new("auto_unmount"),
        OsStr::new("fsname=bibliothecula"),
    ];
    let mut signals = Signals::new(&[SIGINT]).unwrap();

    let (sender, receiver) = bounded(100);
    thread::spawn(move || {
        for _sig in signals.forever() {
            let _ = sender.send(());
        }
    });

    let mut fs = BiblFs {
        connection,
        inodes_map: HashMap::new(),
        documents: HashMap::new(),
        rev_inodes_doc: HashMap::new(),
        files: HashMap::new(),
        rev_files: HashMap::new(),
        rev_inodes_files: HashMap::new(),
        tags: HashMap::new(),
        rev_tags: HashMap::new(),
        inodes_tags: HashMap::new(),
        rev_inodes_tags: HashMap::new(),
        query_dir: QueryDir {
            executed: true,
            query_inodes: HashMap::new(),
            rev_query_inodes: HashMap::new(),
            results: Ok(vec![]),
            query: QueryType::Sql(String::new()),
        },
        never_replace_common_tags: false,
        next_inode: 6,
    };
    {
        let BiblFs {
            ref mut connection,
            ref mut inodes_map,
            ref mut rev_inodes_doc,
            ref mut documents,
            ref mut files,
            ref mut rev_inodes_files,
            ref mut rev_files,
            ref mut tags,
            ref mut rev_tags,
            ref mut inodes_tags,
            ref mut rev_inodes_tags,
            query_dir: _,
            ref mut next_inode,
            never_replace_common_tags: _,
        } = &mut fs;
        let mut stmt =
            connection.prepare("SELECT uuid, data FROM TextMetadata WHERE name = 'tag'")?;
        let tag_iter = stmt.query_map([], |row| {
            let v: (TextMetadataUuid, String) = (TextMetadataUuid(row.get(0)?), row.get(1)?);
            Ok(v)
        })?;
        for tag in tag_iter {
            let (uuid, tag) = tag.unwrap();
            let ino = *next_inode;
            *next_inode += 1;
            tags.insert(
                uuid,
                Tag {
                    //uuid,
                    data: tag.clone(),
                    ino,
                },
            );
            rev_tags.insert(tag, uuid);
            inodes_tags.insert(ino, uuid);
            rev_inodes_tags.insert(uuid, ino);
        }
        let mut stmt = connection
            .prepare("SELECT uuid, title, title_suffix, created, last_modified FROM Documents")?;
        let doc_iter = stmt.query_map([], |row| {
            Ok(Document {
                uuid: DocumentUuid(row.get(0)?),
                title: row.get(1)?,
                title_suffix: row.get(2)?,
                created: row.get(3).unwrap_or_default(),
                last_modified: row.get(4).unwrap_or_default(),
            })
        })?;
        for doc in doc_iter {
            let doc = doc.unwrap();
            documents.insert(doc.uuid, doc);
        }
        let mut stmt = connection.prepare("SELECT b.rowid as row_id, b.uuid AS uuid, json_extract(b.name, '$.filename') AS name, length(b.data) AS size, has.document_uuid as document_uuid, b.created as created, b.last_modified as last_modified FROM DocumentHasBinaryMetadata AS has, BinaryMetadata AS b WHERE has.name = 'storage' AND has.metadata_uuid = b.uuid AND json_valid(b.name);")?;
        let file_iter = stmt.query_map([], |row| {
            Ok(File {
                row_id: row.get(0)?,
                uuid: BinaryMetadataUuid(row.get(1)?),
                name: row.get(2)?,
                size: row.get(3)?,
                document_uuid: DocumentUuid(row.get(4)?),
                created: row.get(5).unwrap_or_default(),
                last_modified: row.get(6).unwrap_or_default(),
            })
        })?;
        for file in file_iter {
            let file = file.unwrap();
            let u = &file.uuid;
            let inode = *next_inode;
            *next_inode += 1;
            inodes_map.insert(inode, *u);
            rev_inodes_doc
                .entry(file.document_uuid)
                .or_default()
                .push(inode);
            rev_inodes_files.insert(*u, inode);
            rev_files.insert(file.name.clone(), file.uuid);
            files.insert(file.uuid, file);
        }
        dbg!(&files);
        println!("Hello, world!");
        //dbg!(&fs.inodes_map);
        //dbg!(&fs.rev_inodes_files);
    }

    let _mount = fuser::spawn_mount(fs, mountpoint, options).unwrap();
    select! {
        recv(receiver) -> _ => {
            println!();
            println!("Goodbye!");
        }
    }

    Ok(())
}
