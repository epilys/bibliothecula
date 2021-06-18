use clap::{crate_version, App, Arg};
use crossbeam_channel::{bounded, select};
use fuser::{
    FileAttr, FileType, Filesystem, ReplyAttr, ReplyData, ReplyDirectory, ReplyEntry, ReplyWrite,
    Request,
};
use libc::ENOENT;
use rusqlite::types::{FromSql, FromSqlError, FromSqlResult, ToSql, ToSqlOutput, ValueRef};
use rusqlite::{self, Connection, DatabaseName, Result};
use signal_hook::{consts::SIGINT, iterator::Signals};
use std::collections::HashMap;
use std::convert::TryInto;
use std::dbg;
use std::env;
use std::ffi::OsStr;
use std::thread;
use std::time::{Duration, UNIX_EPOCH};
use time::{OffsetDateTime, PrimitiveDateTime, UtcOffset};
use uuid::Uuid as Uuid_;

type INode = u64;
//const SQLITE_PAGE_SIZE: usize = 512;

#[derive(Clone, Copy, Debug, Default, Eq, Hash, Ord, PartialEq, PartialOrd)]
pub struct Uuid(Uuid_);

impl FromSql for Uuid {
    fn column_result(value: ValueRef) -> FromSqlResult<Self> {
        String::column_result(value).map(|as_str| Uuid(Uuid_::parse_str(&as_str).unwrap()))
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
    fn to_systemtime(&self) -> std::time::SystemTime {
        std::time::UNIX_EPOCH + std::time::Duration::from_secs(self.0.unix_timestamp() as u64)
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
        perm: 0o644,
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
}

impl BiblFs {
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
        dbg!("lookup");
        dbg!(&parent);
        dbg!(&name);
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
        dbg!("getattr");
        dbg!(&ino);
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
        dbg!("read");
        dbg!(&ino);
        dbg!(&_fh);
        dbg!(&offset);
        dbg!(&size);
        dbg!(&_flags);
        dbg!(&_lock);
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
        dbg!(offset);
        let row_id = self.files[&self.inodes_map[&ino]].row_id;
        let blob = self
            .connection
            .blob_open(DatabaseName::Main, "BinaryMetadata", "data", row_id, true)
            .unwrap();
        dbg!(blob.len());
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
        print!("readdir: ");
        dbg!(&ino);
        dbg!(&_fh);
        dbg!(&offset);

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
                println!("{}", query_s);
                dbg!(&self.query_dir);
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

    fn write(
        &mut self,
        _req: &Request<'_>,
        ino: u64,
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
        Connection::open_with_flags(&db_path, rusqlite::OpenFlags::SQLITE_OPEN_READ_ONLY)?;

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
