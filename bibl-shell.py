#!/usr/bin/env python3
"""CLI shell for interacting with a bibliothecula database.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
You should have received a copy of the GNU General Public License along with
this program. If not, see <http://www.gnu.org/licenses/>.
"""

import argparse
import os
import select
import sys
import traceback
import sqlite3
import datetime
import subprocess
import tempfile
import json
import uuid
import pathlib
import mimetypes
import itertools
from collections import OrderedDict
from abc import abstractmethod
from typing import Type, Dict, List, Any, Set, Union, Optional, Callable
from pathlib import Path

SHELL_BANNER = """                            bibliothecula shell 📇 📚 🏷️  🦇
       (_    ,_,    _)
       / `'--) (--'` \\      exported objects:
      /  _,-'\_/'-,_  \\      - conn : sqlite3.Connection
     /.-'     "     '-.\\     -   db : Database (see NAMESPACE dict
        ______ ______                            for every  import)
      _/      Y      \\_       >>> help(db)
     // ~~ ~~ | ~~ ~  \\\\      >>> help(conn)
    // ~ ~ ~~ | ~~~ ~~ \\\\     >>> print(LONG_SHELL_BANNER)
   //________.|.________\\\\    >>> db.stats()
  `----------`-'----------'
"""

LONG_SHELL_BANNER = """
  bibliothecula shell 📇 📚 🏷️  🦇

           class           |             comment
---------------------------|----------------------------------
 UUID                      |  from the uuid module
 Database                  |  holds self.name and self.conn
 DbObject                  |  abstract class
 Document                  |
 TextMetadata              |                   (_    ,_,    _)
 BinaryMetadata            |                   / `'--) (--'` \\
 DocumentHasTextMetadata   |                  /  _,-'\_/'-,_  \\
 DocumentHasBinaryMetadata |                 /.-'     "     '-.\\
                                                ______ ______
 modules      obj  | type                     _/      Y      \_
 ----------  ------|--------------------     // ~~ ~~ | ~~ ~  \\\\
 sqlite3      conn | sqlite3.Connection     // ~ ~ ~~ | ~~~ ~~ \\\\
 subprocess  ------|--------------------   //________.|.________\\\\
 uuid         db   | Database             `----------`-'----------'
 datetime
 os

#>>> print(SHELL_BANNER) # this message
#>>> db.fts("query string") # Documents matching string in the FTS index
#>>> db.documents() # fetches ALL Documents
#>>> db.documents("my journal") # WHERE title LIKE '%my journal%'
#>>> db.documents("Manifesto", type="book")
#>>> db.documents("", type="notes")
#>>> db.documents("", tags=["SQL", "Distributed"])
#>>> j = db.documents(UUID('..')) # WHERE uuid = '...'
#>>> notes = j.files()
#>>> j.create_file("2021-06-20.md", "text/markdown") # launches $EDITOR
#>>> local_note = j.add_file("./local_note.md") # inserts file in database
#>>> local_note.edit(program="vim")
#>>> local_note.save()
"""


AnyDatabaseObject = Union[
    "Document",
    "TextMetadata",
    "BinaryMetadata",
    "DocumentHasTextMetadata",
    "DocumentHasBinaryMetadata",
]


def sizeof_fmt(num, suffix="B"):
    """Return formatted file size for humans

    https://stackoverflow.com/a/1094933/15652264
    """
    for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, "Yi", suffix)


class Database:
    """
    Holds the database path and the sqlite3 connection.
    """

    def __init__(
        self, conn: sqlite3.Connection, db_name: Union[str, Path], verbose: bool = False
    ):
        conn.execute("PRAGMA foreign_keys = ON;")
        self.name = db_name
        self.conn = conn
        self.verbose = verbose
        self.cur = self.conn.cursor()
        self.created_objects: List[AnyDatabaseObject] = []

    @staticmethod
    def from_path(
        path: Union[str, Path],
        autocommit=False,
        flags=None,
        detect_types=sqlite3.PARSE_COLNAMES | sqlite3.PARSE_DECLTYPES,
        verbose: bool = False,
    ):
        conn = sqlite3.connect(
            path,
            detect_types=detect_types,
            isolation_level=None if autocommit else "DEFERRED",
        )
        conn.row_factory = sqlite3.Row
        return Database(conn, path, verbose=verbose)

    def import_items(self, objects: List[AnyDatabaseObject]):
        count = 0
        with self.conn as conn:
            groups: Dict[Type[AnyDatabaseObject], List[AnyDatabaseObject]] = {
                Document: [],
                TextMetadata: [],
                BinaryMetadata: [],
                DocumentHasTextMetadata: [],
                DocumentHasBinaryMetadata: [],
            }
            for obj in objects:
                _class = obj.__class__
                groups[_class].append(obj)
            classes: List[Type[AnyDatabaseObject]] = [
                Document,
                TextMetadata,
                BinaryMetadata,
                DocumentHasTextMetadata,
                DocumentHasBinaryMetadata,
            ]
            for group in classes:
                table_name = group.TABLE_NAME
                columns = ",".join(group.COLUMNS)
                values_placeholder = ",".join(["?"] * len(group.COLUMNS))
                sql = f"INSERT OR IGNORE INTO {table_name} ({columns}) VALUES ({values_placeholder})"
                if self.verbose:
                    print(sql)
                items = [
                    list(map(lambda col: obj.as_dict()[col], group.COLUMNS))
                    for obj in groups[group]
                ]
                conn.executemany(sql, items)
                if self.verbose:
                    print("Inserted ", len(groups[group]), "items of kind", group)
                count += len(groups[group])
        if self.verbose:
            print("Total inserted ", count, " items")

    def __str__(self):
        return f"<Database {repr(self.name)}>"

    def __repr__(self):
        return str(self)

    def __convert_dispatch__(
        self, _class: Union[Type[AnyDatabaseObject]], r: sqlite3.Row
    ):
        if _class is Document:
            return self.convert_document(r)
        elif _class is TextMetadata:
            return self.convert_text_metadata(r)
        elif _class is BinaryMetadata:
            return self.convert_binary_metadata(r)
        elif _class is DocumentHasTextMetadata:
            return self.convert_has_text_metadata(r)
        elif _class is DocumentHasBinaryMetadata:
            return self.convert_has_binary_metadata(r)

    def convert_document(self, r: sqlite3.Row) -> "Document":
        """

        :param r: row object

        """
        return Document(
            self,
            uuid.UUID(r["uuid"]),
            r["title"],
            title_suffix=r["title_suffix"],
            created=r["created"],
            last_modified=r["last_modified"],
        )

    def convert_text_metadata(self, r: sqlite3.Row) -> "TextMetadata":
        """

        :param r: row object

        """
        return TextMetadata(
            self,
            uuid.UUID(r["uuid"]),
            r["name"],
            r["data"],
            created=r["created"],
            last_modified=r["last_modified"],
        )

    def convert_binary_metadata(self, r: sqlite3.Row) -> "BinaryMetadata":
        """

        :param r: row object

        """
        return BinaryMetadata(
            self,
            uuid.UUID(r["uuid"]),
            r["name"],
            r["data"],
            created=r["created"],
            last_modified=r["last_modified"],
        )

    def convert_has_text_metadata(self, r: sqlite3.Row) -> "DocumentHasTextMetadata":
        """

        :param r: row object

        """
        return DocumentHasTextMetadata(
            self,
            r["id"],
            r["name"],
            uuid.UUID(r["document_uuid"]),
            uuid.UUID(r["metadata_uuid"]),
            created=r["created"],
            last_modified=r["last_modified"],
        )

    def convert_has_binary_metadata(
        self, r: sqlite3.Row
    ) -> "DocumentHasBinaryMetadata":
        """

        :param r: row object

        """
        return DocumentHasBinaryMetadata(
            self,
            r["id"],
            r["name"],
            uuid.UUID(r["document_uuid"]),
            uuid.UUID(r["metadata_uuid"]),
            created=r["created"],
            last_modified=r["last_modified"],
        )

    def fts(self, query_string) -> Dict[uuid.UUID, "Document"]:
        """Perform fts5 query

        :param query_string: the query passed directly to the fts table

        """

        self.cur.execute(
            "SELECT d.* FROM Documents as d join document_title_authors_text_view_fts(?) as f on f.uuid = d.uuid ORDER BY last_modified DESC",
            (query_string,),
        )
        return {
            d.uuid: d for d in (self.convert_document(r) for r in self.cur.fetchall())
        }

    def sql(
        self, sql
    ) -> Union[Dict[Union[int, uuid.UUID], AnyDatabaseObject], List[Dict[str, Any]]]:
        """Convenient wrapper around sqlite3.execute

        Will try to convert rows to objects by looking at the row column names.
        If it fails, the sqlite3.Row objects will be returned as dictionaries
        instead.

        :param sql: the exact SQL to execute (be careful)

        """
        self.cur.execute(sql)
        rows = self.cur.fetchall()
        # try to auto-detect result types
        classes: List[Type[AnyDatabaseObject]] = [
            Document,
            TextMetadata,
            BinaryMetadata,
            DocumentHasTextMetadata,
            DocumentHasBinaryMetadata,
        ]
        for obj_class in classes:
            if len(rows[0].keys()) == len(obj_class.COLUMNS):
                try:
                    r = self.__convert_dispatch__(obj_class, rows[0])
                    return {
                        o.pk(): o
                        for o in (self.__convert_dispatch__(obj_class, r) for r in rows)
                    }
                except:
                    continue
        return [{k: r[k] for k in r.keys()} for r in rows]

    def stats(self) -> Dict[str, Any]:
        """Returns stats about database"""
        stats: Dict[str, Any] = {
            "path": self.name,
            "counts": {},
            "total_size": 0,
            "total_size_human": "",
        }
        self.cur.execute(
            "SELECT type, COUNT(*) as count FROM sqlite_master GROUP BY type",
        )
        stats["counts"] = {r["type"]: r["count"] for r in self.cur.fetchall()}
        self.cur.execute(
            "SELECT SUM(pgsize) FROM dbstat",
        )
        stats["total_size"] = self.cur.fetchone()[0]
        stats["total_size_human"] = sizeof_fmt(stats["total_size"])
        return stats

    def documents(
        self,
        cond: Optional[Union[str, uuid.UUID]] = None,
        type: Optional[str] = None,
        tags: Optional[Union[str, List[str]]] = None,
    ) -> List["Document"]:
        """

        :param cond: title LIKE string or UUID Default value = None)
        :param type: has text metadata with 'name':'type' and given value Default value = None)
        :param tags: has text metadata with 'name':'tag' and given values Default value = None)

        """
        if cond is None:
            self.cur.execute("SELECT * FROM Documents ORDER BY last_modified DESC")
        else:
            if isinstance(cond, str):
                self.cur.execute(
                    f"SELECT * FROM Documents WHERE title LIKE '%{cond}%' ORDER BY last_modified DESC"
                )
            elif isinstance(cond, uuid.UUID):
                self.cur.execute(
                    f"SELECT * FROM Documents WHERE uuid = '{cond.hex}' ORDER BY last_modified DESC"
                )
            else:
                raise TypeError("cond must be None, a str or a uuid.UUID.")
        return [self.convert_document(r) for r in self.cur.fetchall()]

    def text_metadata(
        self, cond: Optional[Union[str, uuid.UUID]] = None
    ) -> List["TextMetadata"]:
        """

        :param cond: name LIKE string or UUID Default value = None)

        """
        if cond is None:
            self.cur.execute("SELECT * FROM TextMetadata ORDER BY last_modified DESC")
        else:
            if isinstance(cond, str):
                self.cur.execute(
                    f"SELECT * FROM TextMetadata WHERE name LIKE '%{cond}%' ORDER BY last_modified DESC"
                )
            elif isinstance(cond, uuid.UUID):
                self.cur.execute(
                    f"SELECT * FROM TextMetadata WHERE uuid = '{cond.hex}' ORDER BY last_modified DESC"
                )
            else:
                raise TypeError("cond must be None, a str or a uuid.UUID.")
        return [self.convert_text_metadata(r) for r in self.cur.fetchall()]

    def binary_metadata(
        self, cond: Optional[Union[str, uuid.UUID]] = None
    ) -> List["BinaryMetadata"]:
        """

        :param cond: name LIKE string or UUID Default value = None)

        """
        if cond is None:
            self.cur.execute("SELECT * FROM BinaryMetadata ORDER BY last_modified DESC")
        else:
            if isinstance(cond, str):
                self.cur.execute(
                    f"SELECT * FROM BinaryMetadata WHERE name LIKE '%{cond}%' ORDER BY last_modified DESC"
                )
            elif isinstance(cond, uuid.UUID):
                self.cur.execute(
                    f"SELECT * FROM BinaryMetadata WHERE uuid = '{cond.hex}' ORDER BY last_modified DESC"
                )
            else:
                raise TypeError("cond must be None, a str or a uuid.UUID.")
        return [self.convert_binary_metadata(r) for r in self.cur.fetchall()]

    def has_text_metadata(
        self, cond: Optional[Union[str, "Document", "TextMetadata"]] = None
    ) -> List["DocumentHasTextMetadata"]:
        """

        :param cond: name LIKE string or document UUID or text metadata UUID Default value = None)

        """
        if cond is None:
            self.cur.execute(
                "SELECT * FROM DocumentHasTextMetadata ORDER BY last_modified DESC"
            )
        else:
            if isinstance(cond, str):
                self.cur.execute(
                    f"SELECT * FROM DocumentHasTextMetadata WHERE name LIKE '%{cond}%' ORDER BY last_modified DESC"
                )
            elif isinstance(cond, Document):
                self.cur.execute(
                    f"SELECT * FROM DocumentHasTextMetadata WHERE document_uuid = '{cond.uuid.hex}' ORDER BY last_modified DESC"
                )
            elif isinstance(cond, TextMetadata):
                self.cur.execute(
                    f"SELECT * FROM DocumentHasTextMetadata WHERE metadata_uuid = '{cond.uuid.hex}' ORDER BY last_modified DESC"
                )
            else:
                raise TypeError(
                    "cond must be None, a str, a Document or a TextMetadata."
                )
        return [self.convert_has_text_metadata(r) for r in self.cur.fetchall()]

    def has_binary_metadata(
        self, cond: Optional[Union[str, "Document", "BinaryMetadata"]] = None
    ) -> List["DocumentHasBinaryMetadata"]:
        """

        :param cond: name LIKE string or document UUID or binary metadata UUID Default value = None)

        """
        if cond is None:
            self.cur.execute(
                "SELECT * FROM DocumentHasBinaryMetadata ORDER BY last_modified DESC"
            )
        else:
            if isinstance(cond, str):
                self.cur.execute(
                    f"SELECT * FROM DocumentHasBinaryMetadata WHERE name LIKE '%{cond}%' ORDER BY last_modified DESC"
                )
            elif isinstance(cond, Document):
                self.cur.execute(
                    f"SELECT * FROM DocumentHasBinaryMetadata WHERE document_uuid = '{cond.uuid.hex}' ORDER BY last_modified DESC"
                )
            elif isinstance(cond, BinaryMetadata):
                self.cur.execute(
                    f"SELECT * FROM DocumentHasBinaryMetadata WHERE metadata_uuid = '{cond.uuid.hex}' ORDER BY last_modified DESC"
                )
            else:
                raise TypeError(
                    "cond must be None, a str, a Document or a BinaryMetadata."
                )
        return [self.convert_has_binary_metadata(r) for r in self.cur.fetchall()]

    def create_document(
        self, title: str, title_suffix: Optional[str] = None
    ) -> "Document":
        new_uuid = uuid.uuid4()
        new_doc = Document(self, new_uuid, title, title_suffix)
        new_doc.save()
        self.created_objects.append(new_doc)
        return new_doc

    def create_tag(self, data: str) -> "TextMetadata":
        return self.create_text_metadata("tag", data)

    def create_text_metadata(self, name: str, data: str) -> "TextMetadata":
        new_uuid = uuid.uuid4()
        new_m = TextMetadata(self, new_uuid, name, data)
        new_m.save()
        self.created_objects.append(new_m)
        return new_m

    def create_binary_metadata(self, name: str, data: bytes) -> "BinaryMetadata":
        new_uuid = uuid.uuid4()
        new_m = BinaryMetadata(self, new_uuid, name, data)
        new_m.save()
        self.created_objects.append(new_m)
        return new_m


class DbObject:
    """Abstract class for database objectsa"""

    TABLE_NAME: str
    COLUMNS: List[str]

    def __init__(
        self,
        created: Optional[datetime.datetime] = None,
        last_modified: Optional[datetime.datetime] = None,
    ):
        if created:
            self.created = created
        else:
            self.created = datetime.datetime.now()
        if last_modified:
            self.last_modified = last_modified
        else:
            self.last_modified = datetime.datetime.now()

    @property
    @abstractmethod
    def pk(self):
        """Returns the column value used as primary key"""
        ...

    def __repr__(self):
        return str(self)

    def set_last_modified(self, new_val: Optional[datetime.datetime] = None):
        """Omit new_val to set last_modified to datetime.now()
        (This method only modifies the object and doesn't save to database)

        :param new_val: datetime.datetime:  (Default value = None)

        """
        if new_val:
            self.last_modified = new_val
        else:
            self.last_modified = datetime.datetime.now()

    @abstractmethod
    def edit(
        self,
        program: Optional[str] = None,
    ):
        """Open with program. The following things are tried in this order:
        - if program is not None, launch subprocess
        - if mime type information exists, try launch appropriate application
        - if not binary, launch with $EDITOR
        - fail
        Returns the modified self if there were any modifications or None.
        (This method only modifies the object and doesn't save to database)

        :param program: str: path or name of program to launch (Default value = None)

        """
        ...

    @abstractmethod
    def save(self):
        """This method persists modifications to database."""
        ...

    @abstractmethod
    def delete(self):
        """This method deletes object from database. Obviously be sure you want that."""
        ...

    def as_dict(self) -> Dict[str, Optional[str]]:
        uuid_enc = lambda u, b: u.hex if isinstance(u, uuid.UUID) else b(u, bytes_enc)
        bytes_enc: Callable[[Any], Union[bytes, str]] = (
            lambda n: n if isinstance(n, bytes) else str(n)
        )
        none_enc = lambda n, b: None if n is None else b(n)
        columns = self.__class__.COLUMNS
        return {
            uuid_enc(k, lambda x, _b: str(x)): uuid_enc(v, none_enc)
            for k, v in self.__dict__.items()
            if k in columns
        }

    def as_json(self) -> str:
        return json.dumps(self.as_dict(), separators=(",", ":"))


class Document(DbObject):
    """Document class. Changes are not saved to database unless save() is called."""

    TABLE_NAME = "Documents"
    COLUMNS = ["uuid", "title", "title_suffix", "created", "last_modified"]

    def __init__(
        self,
        db: Database,
        uuid: uuid.UUID,
        title: str,
        title_suffix: Optional[str] = None,
        *args,
        **kwargs,
    ):
        self.db = db
        self.uuid = uuid
        self.title = title
        self.title_suffix = title_suffix
        super(Document, self).__init__(*args, **kwargs)

    def pk(self):
        """Returns the column value used as primary key"""
        return self.uuid

    def __iadd__(
        self,
        obj: Union[
            "TextMetadata",
            "BinaryMetadata",
        ],
    ):
        if not (isinstance(obj, TextMetadata) or isinstance(obj, BinaryMetadata)):
            raise TypeError(
                f"Can only add TextMetadata, BinaryMetadata to Document. You added: {type(obj)}."
            )
        if isinstance(obj, TextMetadata):
            table_name = "DocumentHasTextMetadata"
            is_text = True
        else:
            table_name = "DocumentHasBinaryMetadata"
            is_text = False
        with self.db.conn as conn:
            cur = conn.cursor()
            created = datetime.datetime.now()
            cur.execute(
                f"INSERT OR ABORT INTO {table_name} (name, document_uuid, metadata_uuid, created, last_modified) VALUES (?, ?, ?, ?, ?)",
                [
                    obj.name,
                    self.pk().hex,
                    obj.pk().hex,
                    created,
                    created,
                ],
            )
            cur.execute(
                f"SELECT * FROM {table_name} WHERE name = ? AND document_uuid = ? AND metadata_uuid = ? AND created = ?",
                [
                    obj.name,
                    self.pk().hex,
                    obj.pk().hex,
                    created,
                ],
            )
            new_rows = cur.fetchall()
            if len(new_rows) == 1:
                new_has: Any[DocumentHasTextMetadata, DocumentHasBinaryMetadata]
                if is_text:
                    new_has = self.db.convert_has_text_metadata(new_rows[0])
                else:
                    new_has = self.db.convert_has_binary_metadata(new_rows[0])
                self.db.created_objects.append(new_has)
            else:
                raise Exception(
                    f"Insert {table_name} returned {len(new_rows)} items: {[r.keys() for r in new_rows]}"
                )
        return self

    def create_file(
        self, filename: str, mime_type: Optional[str], program: Optional[str] = None
    ) -> "BinaryMetadata":
        """

        :param filename: param mime_type:
        :param program: Default value = None)
        :param mime_type:

        """
        if program is None:
            if "EDITOR" in os.environ:
                program = os.environ["EDITOR"]
            elif "VISUAL" in os.environ:
                program = os.environ["VISUAL"]
            else:
                raise Exception("Could not find $EDITOR or $VISUAL in the environment.")
        with tempfile.NamedTemporaryFile() as tmpfile:
            full_path = tmpfile.name
            ret = subprocess.run([program, full_path])
            with open(full_path, "rb") as f:
                new_data = f.read()
                new_len = len(new_data)
                d = {
                    "content_type": mime_type if mime_type else "text/plain",
                    "filename": filename.strip(),
                    "size": new_len,
                }
                new_name = json.dumps(d, separators=(",", ":"))
                return self.add_blob(new_name, new_data, "storage")

    def add_text_metadata(
        self, name: str, data: str, has_name: Optional[str] = None
    ) -> "TextMetadata":
        """

        :param name: str
        :param data: bytes
        :param has_name: name for the DocumentHasTextMetadata row (if None, same from name parameter)

        """
        if has_name is None:
            has_name = name
        with self.db.conn as conn:
            m_uuid = uuid.uuid4()
            cur = conn.cursor()
            cur.execute(
                f"INSERT OR IGNORE INTO TextMetadata (uuid, name, data, created, last_modified) VALUES (?, ?, ?, ?, ?)",
                [
                    m_uuid.hex,
                    name,
                    data,
                    datetime.datetime.now(),
                    datetime.datetime.now(),
                ],
            )
            cur.execute(
                "SELECT * FROM TextMetadata WHERE name = ? and data = ?", (name, data)
            )
            new_rows = cur.fetchall()
            if len(new_rows) == 0:
                raise Exception(
                    f"Insert TextMetadata returned {len(new_rows)} items: {[r.keys() for r in new_rows]}"
                )
            if len(new_rows) != 1:
                print(
                    f"Insert TextMetadata returned {len(new_rows)} items: {[r.keys() for r in new_rows]}"
                )

            new_text_metadata = self.db.convert_text_metadata(new_rows[0])
            self.db.created_objects.append(new_text_metadata)
            cur.execute(
                f"INSERT OR IGNORE INTO DocumentHasTextMetadata (name, document_uuid, metadata_uuid, created, last_modified) VALUES (?, ?, ?, ?, ?)",
                [
                    has_name,
                    self.pk().hex,
                    new_text_metadata.pk().hex,
                    datetime.datetime.now(),
                    datetime.datetime.now(),
                ],
            )
            return new_text_metadata

    def add_blob(
        self, name: str, data: bytes, has_name: Optional[str] = None
    ) -> "BinaryMetadata":
        """

        :param name: str
        :param data: bytes
        :param has_name: name for the DocumentHasBinaryMetadata row (if None, same from name parameter)

        """
        if has_name is None:
            has_name = name
        with self.db.conn as conn:
            m_uuid = uuid.uuid4()
            cur = conn.cursor()
            cur.execute(
                f"INSERT OR ABORT INTO BinaryMetadata (uuid, name, data, created, last_modified) VALUES (?, ?, ?, ?, ?)",
                [
                    m_uuid.hex,
                    name,
                    data,
                    datetime.datetime.now(),
                    datetime.datetime.now(),
                ],
            )
            cur.execute(f"SELECT * FROM BinaryMetadata WHERE uuid = '{m_uuid.hex}'")
            new_rows = cur.fetchall()
            if len(new_rows) == 1:
                new_file = self.db.convert_binary_metadata(new_rows[0])
                self.db.created_objects.append(new_file)
            else:
                raise Exception(
                    f"Insert BinaryMetadata returned {len(new_rows)} items: {[r.keys() for r in new_rows]}"
                )
            cur.execute(
                f"INSERT OR ABORT INTO DocumentHasBinaryMetadata (name, document_uuid, metadata_uuid, created, last_modified) VALUES (?, ?, ?, ?, ?)",
                [
                    has_name,
                    self.pk().hex,
                    new_file.pk().hex,
                    datetime.datetime.now(),
                    datetime.datetime.now(),
                ],
            )
            return new_file

    def add_file(
        self,
        path: Union[str, Path],
        filename: Optional[str] = None,
        mime_type: Optional[str] = None,
    ) -> "BinaryMetadata":
        """

        :param path: param filename:  (Default value = None)
        :param mime_type: Default value = None)
        :param filename:  (Default value = None)

        """
        if isinstance(path, str):
            path = Path(path)
        if path.is_dir():
            raise IsADirectoryError(f"{path} is a directory.")
        if not path.exists():
            raise FileNotFoundError(f"{path} doesn't exist.")
        if filename is None:
            filename = path.name
        if mime_type is None:
            guess = mimetypes.guess_type(str(path))
            if isinstance(guess, str):
                mime_type = guess
        data = None
        with open(path, "rb") as f:
            data = f.read()
        d = {
            "content_type": mime_type,
            "filename": filename.strip(),
            "size": len(data),
        }
        name = json.dumps(d, separators=(",", ":"))
        return self.add_blob(name, data, "storage")

    def files(self) -> List["BinaryMetadata"]:
        """Return all files"""
        self.db.cur.execute(
            f"SELECT m.* FROM BinaryMetadata as m, DocumentHasBinaryMetadata as has WHERE document_uuid = '{self.uuid.hex}' AND metadata_uuid = m.uuid AND has.name = 'storage' ORDER BY last_modified DESC"
        )
        return [
            self.db.__convert_dispatch__(BinaryMetadata, r)
            for r in self.db.cur.fetchall()
        ]

    def tags(self) -> List["TextMetadata"]:
        """Return all tags"""
        return self.text_metadata("tag")

    def text_metadata(self, name: str) -> List["TextMetadata"]:
        """Return all text metadata with given name"""
        self.db.cur.execute(
            f"SELECT m.* FROM TextMetadata as m, DocumentHasTextMetadata as has WHERE document_uuid = '{self.uuid.hex}' AND metadata_uuid = m.uuid AND has.name = ? ORDER BY last_modified DESC",
            (name,),
        )
        return [
            self.db.__convert_dispatch__(TextMetadata, r)
            for r in self.db.cur.fetchall()
        ]

    def all_metadata(
        self,
    ) -> Dict[
        str,
        List[
            Union[
                "DocumentHasTextMetadata",
                "DocumentHasBinaryMetadata",
                "TextMetadata",
                "BinaryMetadata",
            ]
        ],
    ]:
        """Return all metadata objects"""
        self.db.cur.execute(
            f"SELECT m.* FROM TextMetadata as m, DocumentHasTextMetadata as has WHERE document_uuid = '{self.uuid.hex}' AND metadata_uuid = m.uuid ORDER BY last_modified DESC"
        )
        text_metadata = [
            self.db.__convert_dispatch__(TextMetadata, r)
            for r in self.db.cur.fetchall()
        ]
        self.db.cur.execute(
            f"SELECT * FROM DocumentHasTextMetadata WHERE document_uuid = '{self.uuid.hex}' ORDER BY last_modified DESC"
        )
        has_text = [
            self.db.__convert_dispatch__(DocumentHasTextMetadata, r)
            for r in self.db.cur.fetchall()
        ]
        self.db.cur.execute(
            f"SELECT m.* FROM BinaryMetadata as m, DocumentHasBinaryMetadata as has WHERE document_uuid = '{self.uuid.hex}' AND metadata_uuid = m.uuid ORDER BY last_modified DESC"
        )
        binary_metadata = [
            self.db.__convert_dispatch__(BinaryMetadata, r)
            for r in self.db.cur.fetchall()
        ]
        self.db.cur.execute(
            f"SELECT * FROM DocumentHasBinaryMetadata WHERE document_uuid = '{self.uuid.hex}' ORDER BY last_modified DESC"
        )
        has_binary = [
            self.db.__convert_dispatch__(DocumentHasBinaryMetadata, r)
            for r in self.db.cur.fetchall()
        ]
        return {
            "TextMetadata": text_metadata,
            "DocumentHasTextMetadata": has_text,
            "BinaryMetadata": binary_metadata,
            "DocumentHasBinaryMetadata": has_binary,
        }

    def __str__(self):
        return f"<Document {repr(self.title)}{'' if self.title_suffix else ''}{self.title_suffix if self.title_suffix else ''}>"

    def edit(
        self,
        program: Optional[str] = None,
    ):
        raise NotImplementedError("")

    def save(self):
        """This method persists modifications to database."""
        # insert if not already existing
        self.db.cur.execute(
            f"INSERT OR IGNORE INTO Documents(uuid, title, title_suffix, last_modified) VALUES (?, ?, ?, strftime('%Y-%m-%d %H:%M:%f', 'now'))",
            [self.uuid.hex, self.title, self.title_suffix],
        )
        self.db.cur.execute(
            f"UPDATE Documents SET title=?, title_suffix=?, last_modified = strftime('%Y-%m-%d %H:%M:%f', 'now') WHERE uuid = '{self.uuid.hex}'",
            [self.title, self.title_suffix],
        )

    def delete(self):
        self.db.cur.execute(
            f"DELETE FROM Documents WHERE uuid = '{self.uuid.hex}'",
            [],
        )
        return True


class TextMetadata(DbObject):
    """TextMetadata class. Changes are not saved to database unless save() is called."""

    TABLE_NAME = "TextMetadata"
    COLUMNS = [
        "uuid",
        "name",
        "data",
        "created",
        "last_modified",
    ]

    def __init__(
        self, db: Database, uuid: uuid.UUID, name: str, data: str, *args, **kwargs
    ):
        self.db = db
        self.uuid = uuid
        self.name = name
        self.data = data
        super(TextMetadata, self).__init__(*args, **kwargs)

    def pk(self) -> uuid.UUID:
        """Returns the column value used as primary key"""
        return self.uuid

    def __str__(self):
        return f"<TextMetadata {repr(self.name)} {repr(self.data)}>"

    def size(self) -> int:
        return len(self.data)

    def save_data_to_path(self, path: Union[Path, str]):
        """

        :param path:

        """

        if isinstance(path, str):
            path = Path(path)
        if path.is_dir():
            print(path, "is a directory.")
            return -1
        if path.exists():
            print(path, "already exists, won't overwrite existing files.")
            return -1
        with open(path, "w") as f:
            wrote = f.write(self.data)
        print("Wrote", sizeof_fmt(wrote), "from database entry", self.pk(), "to", path)
        return wrote

    def replace_data_with(self, path: Union[Path, str]):
        """

        :param path:

        """
        if isinstance(path, str):
            path = Path(path)
        if path.is_dir():
            print(path, "is a directory.")
            return -1
        if not path.exists():
            print(path, "doesn't exist.")
            return -1
        with open(path, "r") as f:
            new_data = f.read()
            new_len = len(new_data)
            self.data = new_data
            print("Wrote", sizeof_fmt(new_len), "to database entry", self.pk())
            return new_len

    def edit(
        self,
        program: Optional[str] = None,
    ):
        if program is None:
            program = "xdg-open"
        size_before = self.size()
        print("Editing ", self.name, f" with {repr(program)}")
        with tempfile.NamedTemporaryFile() as tmpfile:
            full_path = tmpfile.name
            tmpfile.write(self.data.encode("utf-8"))
            tmpfile.flush()
            mtime = os.stat(full_path).st_mtime
            ret = subprocess.run([program, full_path])
            mtime2 = os.stat(full_path).st_mtime
            if mtime2 == mtime:
                print("No change detected, aborting.")
            else:
                tmpfile.seek(0)
                self.replace_data_with(full_path)

    def save(self):
        """This method persists modifications to database."""
        # insert if not already existing
        self.db.cur.execute(
            f"INSERT OR IGNORE INTO TextMetadata(uuid, name, data, last_modified) VALUES (?, ?, ?, strftime('%Y-%m-%d %H:%M:%f', 'now'))",
            [self.uuid.hex, self.name, self.data],
        )
        self.db.cur.execute(
            f"UPDATE TextMetadata SET name=?, data=?, last_modified = strftime('%Y-%m-%d %H:%M:%f', 'now') WHERE uuid = '{self.uuid.hex}'",
            [self.name, self.data],
        )

    def delete(self):
        self.db.cur.execute(
            f"DELETE FROM TextMetadata WHERE uuid = '{self.uuid.hex}'",
            [],
        )
        return True


class BinaryMetadata(DbObject):
    """BinaryMetadata class. Changes are not saved to database unless save() is called."""

    TABLE_NAME = "BinaryMetadata"
    COLUMNS = [
        "uuid",
        "name",
        "data",
        "created",
        "last_modified",
    ]

    def __init__(self, db, uuid: uuid.UUID, name: str, data: bytes, *args, **kwargs):
        self.db = db
        self.uuid = uuid
        self.name = name
        self.data = data
        super(BinaryMetadata, self).__init__(*args, **kwargs)

    def pk(self) -> uuid.UUID:
        """Returns the column value used as primary key"""
        return self.uuid

    def __str__(self):
        return f"<BinaryMetadata {repr(self.name)}>"

    def filename(self) -> str:
        try:
            p = json.loads(self.name)
            return p["filename"]
        except Exception as exc:
            return self.name

    def size(self) -> int:
        try:
            p = json.loads(self.name)
            return p["size"]
        except Exception as exc:
            print(exc)
        return len(self.data)

    def save_blob_to_path(self, path: Union[Path, str]):
        """

        :param path:

        """

        if isinstance(path, str):
            path = Path(path)
        if path.is_dir():
            print(path, "is a directory.")
            return -1
        if path.exists():
            print(path, "already exists, won't overwrite existing files.")
            return -1
        with open(path, "wb") as f:
            wrote = f.write(self.data)
        print("Wrote", sizeof_fmt(wrote), "from database entry", self.pk(), "to", path)
        return wrote

    def replace_blob_with(self, path: Union[Path, str]):
        """

        :param path:

        """
        if isinstance(path, str):
            path = Path(path)
        if path.is_dir():
            print(path, "is a directory.")
            return -1
        if not path.exists():
            print(path, "doesn't exist.")
            return -1
        with open(path, "rb") as f:
            new_data = f.read()
            new_len = len(new_data)
            p = json.loads(self.name)
            p["size"] = new_len
            new_name = json.dumps(p, separators=(",", ":"))
            self.name = new_name
            self.data = new_data
            print("Wrote", sizeof_fmt(new_len), "to database entry", self.pk())
            return new_len

    def view(self, program: Optional[str] = None):
        """

        :param program: Default value = None)

        """
        if program is None:
            program = "xdg-open"
        size_before = self.size()
        print("Viewing ", self.filename(), f" with {repr(program)}")
        with tempfile.NamedTemporaryFile() as tmpfile:
            full_path = tmpfile.name
            tmpfile.write(self.data)
            tmpfile.flush()
            ret = subprocess.run([program, full_path])

    def edit(
        self,
        program: Optional[str] = None,
    ):
        if program is None:
            program = "xdg-open"
        size_before = self.size()
        print("Editing ", self.filename(), f" with {repr(program)}")
        with tempfile.NamedTemporaryFile() as tmpfile:
            full_path = tmpfile.name
            tmpfile.write(self.data)
            tmpfile.flush()
            mtime = os.stat(full_path).st_mtime
            ret = subprocess.run([program, full_path])
            mtime2 = os.stat(full_path).st_mtime
            if mtime2 == mtime:
                print("No change detected, aborting.")
            else:
                tmpfile.seek(0)
                self.replace_blob_with(full_path)

    def save(self):
        """This method persists modifications to database."""
        # insert if not already existing
        self.db.cur.execute(
            f"INSERT OR IGNORE INTO BinaryMetadata(uuid, name, data, last_modified) VALUES (?, ?, ?, strftime('%Y-%m-%d %H:%M:%f', 'now'))",
            [self.uuid.hex, self.name, self.data],
        )
        self.db.cur.execute(
            f"UPDATE BinaryMetadata SET name=?, data=?, last_modified = strftime('%Y-%m-%d %H:%M:%f', 'now') WHERE uuid = '{self.uuid.hex}'",
            [self.name, self.data],
        )

    def delete(self):
        self.db.cur.execute(
            f"DELETE FROM BinaryMetadata WHERE uuid = '{self.uuid.hex}'",
            [],
        )
        return True


class DocumentHasTextMetadata(DbObject):
    """DocumentHasTextMetadata class. Changes are not saved to database unless save() is called."""

    TABLE_NAME = "DocumentHasTextMetadata"
    COLUMNS = [
        "id",
        "name",
        "document_uuid",
        "metadata_uuid",
        "created",
        "last_modified",
    ]

    def __init__(
        self,
        db: Database,
        _id: int,
        name: str,
        document_uuid: uuid.UUID,
        metadata_uuid: uuid.UUID,
        *args,
        **kwargs,
    ):
        self.db = db
        self.name = name
        if isinstance(document_uuid, uuid.UUID):
            self.document_uuid = document_uuid
        else:
            raise TypeError("document_uuid must be a Document uuid.UUID.")
        if isinstance(metadata_uuid, uuid.UUID):
            self.metadata_uuid = metadata_uuid
        else:
            raise TypeError("metadata_uuid must be a TextMetadata uuid.UUID.")
        self.id = _id
        super(DocumentHasTextMetadata, self).__init__(*args, **kwargs)

    def pk(self) -> int:
        """Returns the column value used as primary key"""
        return self.id

    def __str__(self):
        return f"<DocumentHasTextMetadata {repr(self.name)}>"

    def edit(
        self,
        program: Optional[str] = None,
    ):
        raise NotImplementedError("")

    def save(self):
        """This method persists modifications to database."""
        # insert if not already existing
        self.db.cur.execute(
            f"INSERT OR IGNORE INTO DocumentHasTextMetadata(id, name, document_uuid, metadata_uuid, last_modified) VALUES (?, ?, ?, ?, strftime('%Y-%m-%d %H:%M:%f', 'now'))",
            [self.id, self.name, self.document_uuid, self.metadata_uuid],
        )
        self.db.cur.execute(
            f"UPDATE DocumentHasTextMetadata SET name=?, document_uuid=?, metadata_uuid=?, last_modified = strftime('%Y-%m-%d %H:%M:%f', 'now') WHERE id = ?",
            [self.name, self.document_uuid.hex, self.metadata_uuid.hex, self.id],
        )

    def delete(self):
        self.db.cur.execute(
            f"DELETE FROM DocumentHasTextMetadata WHERE id = ?",
            [self.id],
        )
        return True


class DocumentHasBinaryMetadata(DbObject):
    """DocumentHasBinaryMetadata class. Changes are not saved to database unless save() is called."""

    TABLE_NAME = "DocumentHasBinaryMetadata"
    COLUMNS = [
        "id",
        "name",
        "document_uuid",
        "metadata_uuid",
        "created",
        "last_modified",
    ]

    def __init__(
        self,
        db: Database,
        _id: int,
        name: str,
        document_uuid: uuid.UUID,
        metadata_uuid: uuid.UUID,
        *args,
        **kwargs,
    ):
        self.db = db
        self.name = name
        if isinstance(document_uuid, uuid.UUID):
            self.document_uuid = document_uuid
        else:
            raise TypeError("document_uuid must be a Document uuid.UUID.")
        if isinstance(metadata_uuid, uuid.UUID):
            self.metadata_uuid = metadata_uuid
        else:
            raise TypeError("metadata_uuid must be a BinaryMetadata uuid.UUID.")
        self.id = _id
        super(DocumentHasBinaryMetadata, self).__init__(*args, **kwargs)

    def pk(self) -> int:
        """Returns the column value used as primary key"""
        return self.id

    def __str__(self):
        return f"<DocumentHasBinaryMetadata {repr(self.name)}>"

    def edit(
        self,
        program: Optional[str] = None,
    ):
        raise NotImplementedError("")

    def save(self):
        """This method persists modifications to database."""
        # insert if not already existing
        self.db.cur.execute(
            f"INSERT OR IGNORE INTO DocumentHasBinaryMetadata(id, name, document_uuid, metadata_uuid, last_modified) VALUES (?, ?, ?, ?, strftime('%Y-%m-%d %H:%M:%f', 'now'))",
            [self.id, self.name, self.document_uuid, self.metadata_uuid],
        )
        self.db.cur.execute(
            f"UPDATE DocumentHasBinaryMetadata SET name=?, document_uuid=?, metadata_uuid=?, last_modified = strftime('%Y-%m-%d %H:%M:%f', 'now') WHERE id = ?",
            [self.name, self.document_uuid.hex, self.metadata_uuid.hex, self.id],
        )

    def delete(self):
        self.db.cur.execute(
            f"DELETE FROM DocumentHasBinaryMetadata WHERE id = ?",
            [self.id],
        )
        return True


class Shell:
    """The shell session"""

    shells = ["ipython3", "python3"]

    def __init__(self, options):
        self.options = options
        self.conn = None
        self.database = None

        def adapt_uuid(u):
            return u.hex

        sqlite3.register_adapter(uuid.UUID, adapt_uuid)
        self.conn = sqlite3.connect(
            self.options.db_name,
            detect_types=sqlite3.PARSE_COLNAMES | sqlite3.PARSE_DECLTYPES,
            isolation_level=None if self.options.autocommit else "DEFERRED",
        )
        self.conn.row_factory = sqlite3.Row
        self.database = Database(
            self.conn, self.options.db_name, verbose=options.verbose
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.conn is not None:
            self.conn.close()

    def run(self):
        """Runs the shell"""
        if self.options.interpreter == "python3":
            self.python()
        elif self.options.interpreter == "ipython3":
            self.ipython()

    def imported_objects(self) -> Dict[str, Any]:
        """Returns the imported objects injected in the namespace of the shell"""
        conn = self.conn
        db = self.database

        # Set up a dictionary to serve as the environment for the shell, so
        # that tab completion works on objects that are imported at runtime.
        imported_objects = {
            # objects
            "conn": conn,
            "db": db,
            "SHELL_BANNER": SHELL_BANNER,
            "LONG_SHELL_BANNER": LONG_SHELL_BANNER,
            # classes
            "UUID": uuid.UUID,
            "Database": Database,
            "DbObject": DbObject,
            "Document": Document,
            "TextMetadata": TextMetadata,
            "BinaryMetadata": BinaryMetadata,
            "DocumentHasTextMetadata": DocumentHasTextMetadata,
            "DocumentHasBinaryMetadata": DocumentHasBinaryMetadata,
            # modules
            "sqlite3": sqlite3,
            "subprocess": subprocess,
            "uuid": uuid,
            "datetime": datetime,
            "itertools": itertools,
            "os": os,
        }
        return imported_objects

    def ipython(self):
        """Runs the IPython interpreter"""
        import IPython  # type: ignore
        from IPython.terminal.embed import InteractiveShellEmbed  # type: ignore

        imported_objects = self.imported_objects()
        db = self.database

        dbpath = pathlib.Path(db.name)
        mtime = datetime.datetime.fromtimestamp(dbpath.stat().st_mtime)

        banner1 = (
            f"IPython {IPython.__version__}\n"
            + SHELL_BANNER
            + f"\nConnected to {db.name}, last modified {mtime.isoformat(sep=' ', timespec='minutes')}"
        )
        ipshell = InteractiveShellEmbed(
            user_ns=imported_objects, argv=[], banner1=banner1
        )
        ipshell()

    def python(self):
        """Runs the standard python interpreter"""
        import code

        imported_objects = self.imported_objects()
        db = self.database

        try:  # Try activating rlcompleter, because it's handy.
            import readline
        except ImportError:
            pass
        else:
            # We don't have to wrap the following import in a 'try', because
            # we already know 'readline' was imported successfully.
            import rlcompleter

            readline.set_completer(rlcompleter.Completer(imported_objects).complete)
            # Enable tab completion on systems using libedit (e.g. macOS).
            # These lines are copied from Python's Lib/site.py.
            readline_doc = getattr(readline, "__doc__", "")
            if readline_doc is not None and "libedit" in readline_doc:
                readline.parse_and_bind("bind ^I rl_complete")
            else:
                readline.parse_and_bind("tab:complete")

        # We want to honor both $PYTHONSTARTUP and .pythonrc.py, so follow system
        # conventions and get $PYTHONSTARTUP first then .pythonrc.py.
        if not self.options.no_startup:
            for pythonrc in OrderedDict(
                {
                    x: x
                    for x in [
                        os.environ.get("PYTHONSTARTUP"),
                        os.path.expanduser("~/.pythonrc.py"),
                    ]
                }
            ):
                if not pythonrc:
                    continue
                if not os.path.isfile(pythonrc):
                    continue
                with open(pythonrc) as handle:
                    pythonrc_code = handle.read()
                # Match the behavior of the cpython shell where an error in
                # PYTHONSTARTUP prints an exception and continues.
                try:
                    exec(compile(pythonrc_code, pythonrc, "exec"), imported_objects)
                except Exception:
                    traceback.print_exc()

        dbpath = pathlib.Path(db.name)
        mtime = datetime.datetime.fromtimestamp(dbpath.stat().st_mtime)
        python_version = sys.version.replace("\n", "")
        code.interact(
            banner=f"python3 {python_version}\n"
            + SHELL_BANNER
            + f"\nConnected to {db.name}, last modified {mtime.isoformat(sep=' ', timespec='minutes')}",
            local=imported_objects,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="bibl-shell.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Project website: https://epilys.github.io/bibliothecula\nProject repository: https://github.com/epilys/bibliothecula",
        description="Python shell with convenient methods and objects for an sqlite3\ndatabase with the bibliothecula schema. Licensed GPL-3.0-or-later",
    )
    parser.add_argument("db_name", help="sqlite3 database to use.")
    parser.add_argument(
        "-i",
        "--interpreter",
        help="interpreter to use.",
        choices=Shell.shells,
        default="python3",
    )
    parser.add_argument(
        "--autocommit",
        action="store_true",
        default=False,
        help="Autocommit on every statement. If false, you'd have to remember to commit on your own before you close the connection.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=False,
        help="Show SQL etc actions taken.",
    )
    parser.add_argument(
        "--no-startup",
        action="store_true",
        help="When using plain Python, ignore the PYTHONSTARTUP environment variable and ~/.pythonrc.py script.",
    )
    args = parser.parse_args()
    with Shell(args) as shell:
        shell.run()
