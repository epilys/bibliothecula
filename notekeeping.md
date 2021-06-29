## Using `sqlite3` as a notekeeping document graph with automatic reference indexing

<aside>
  <p>
  <em>TL;DR</em>:
  </p>
  <p>
  <ul>
<li>The full schema required for this article’s examples is <a href="./web-demo/zettel.sql">here</a></li>
<li><p>There’s a <a href="./web-demo/zettel.html">web demo</a> of <a rel="external nofollow" href="https://en.wikipedia.org/wiki/Niklas_Luhmann#Note-taking_system_(Zettelkasten)">sociologist Niklas Luhmann's zettelkasten</a> you can explore online using <code>sql.js</code>, <code>sqlite3</code> compiled to webassembly (total compressed asset size: <code>16MB</code>). <a href="https://github.com/epilys/bibliothecula/blob/cc3c4e4ccd85210c993a57df0c4012b3a027cdba/web-demo/zettel.html">source code</a></p></li>
  </ul>
  </p>
</aside>

The full-text functionality of `sqlite3` along with the powerful SQL indexing and trigger features allows us to easily keep notes with references in an `sqlite3` database. In this document I present a workflow for doing so.

First, let's examine the pros and cons of this workflow:

Pros:

- Your notes are kept in one file, and are portable on every OS and CPU architecture `sqlite3` supports.
- You can write your notes in any kind of plain text format, for example `troff` or `markdown`.
- You can compose, edit, download your files with the `sqlite3` CLI and your editor of choice.
- You get reference link calculations for free.
- You get full-text search for free.
- You can group notes into collections.
- You can optionally tag your notes with keywords.
- You can attach any (binary or not) file to those collections and refer to them from your notes.

Cons:

- Your database may get corrupted (versus one note file getting corrupted) but it's mostly recoverable. Always backup in anything you do.
- You will need familiarity with the command line and SQL, but with the proper mindset this shouldn't be a problem.
- References in text files do not obey `FOREIGN KEY` constraints; if you delete a note, the dangling reference in text and in indices remains. You can easily search for and fix them in `AFTER INSERT` triggers, of course.


## The schema

You can use anything you like as long as it has a basic property:

- your `notes` table must have a unique id that you can reference in plain text

For this demo, I use the `bibliothecula` schema which is small, has UUIDs for identifiers, allows you to tag or add other arbitrary metadata (and files) to each document. In this model, the document is our notes collection and the files of this document can include plain text ones that are our notes.

<aside>
**side-note**: `sqlite3` doesn't have a built-in way to produce UUIDs. There's an official `uuid.c` extension you can compile and load but that's all. There might be a way to generate UUIDs natively using the provided randomness functions.

The [`sqlite3` documentation for `randomblob` states](https://sqlite.org/lang_corefunc.html#randomblob):

```
randomblob(N)

The randomblob(N) function return an N-byte blob containing
pseudo-random bytes. If N is less than 1 then a 1-byte
random blob is returned.

Hint: applications can generate globally unique
identifiers using this function together with
hex() and/or lower() like this:

  hex(randomblob(16))
 
  lower(hex(randomblob(16)))
```

Keep in mind that this is NOT a UUID. UUIDs are not just random numbers, they have some structure. You can easily generate UUIDs with stock `python3`:

```shell
$ python3
>>> from uuid import *
>>> uuid4().hex # we don't want hyphens in our UUIDs
'f1272b12b2174e3aa0e7c05610592ac0'
```

</aside>

The table used for files in `bibliothecula` is `BinaryMetadata`; since it's binary it can also hold plain text data. This is the `CREATE` statement for `BinaryMetadata`:

```sql
CREATE TABLE IF NOT EXISTS "BinaryMetadata" (
"uuid" CHARACTER(32) NOT NULL PRIMARY KEY,
"name" TEXT NULL,
"data" BLOB NOT NULL,
"compressed" BOOLEAN NOT NULL DEFAULT (0),
"created" DATETIME NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f', 'now')),
"last_modified" DATETIME NOT NULL DEFAULT (strftime ('%Y-%m-%d %H:%M:%f', 'now')),
CONSTRAINT uniqueness UNIQUE ("name", "data")
);
```

The `name` column can hold our filename. What about mime type? Furthermore, what if I want to know the size of a file, do I have to calculate the `data` length every time?

<aside>
<p>&dagger;. By the way, doing <code>LENGTH(data)</code> for non-<code>BLOB</code> columns is wrong, because they may include NUL bytes. Always do <code>LENGTH(CAST(col AS BLOB))</code> for <code>TEXT</code>.</p>
</aside>

 The default `sqlite` distribution includes the `JSON1` extension which allows us to place structured data in a column, so I chose to store filename, mime type and size in bytes in the `name` column. Examples:

```json
[{"content_type":"text/markdown","filename":"2021-06-20.md","size":0},
{"content_type":"text/markdown","filename":"dataintegrity.md","size":566},
{"content_type":"text/markdown","filename":"exports.md","size":34},
{"content_type":"text/markdown","filename":"generate_tool.md","size":229},
{"content_type":"text/markdown","filename":"shell.md","size":240},
{"content_type":"text/plain","filename":"","size":97632},
{"content_type":"text/plain","filename":"test.txt","size":91} ]
```

Again, this is only for convenience. Our notes don't have to have filenames if they already have a unique identifier, and there's no restriction for filename `UNIQUENESS` anywhere.

You can create JSON objects with the `json_object` SQL function, and extract fields with the `json_extract` SQL function:

```sql
SELECT json_extract(name, '$.content_type') FROM BinaryMetadata WHERE json_valid(name) LIMIT 1;
INSERT INTO BinaryMetadata(uuid,name,data) VALUES ('623fec5beac242fcb0b0d17ada20e2b5',json_object('content_type','text/plain','filename','file.txt','size',LENGTH(readfile('file.txt'))),readfile('file.txt'));
```

Note the use of `json_valid` to ignore non-JSON names, and also the use of `readfile`: this is a CLI-only function allowing you to read files as `BLOB`s. We can use it to quickly attach files to our note database.

## The indices

### Full-text search

I will use the `fts5` extension, included by default nowadays in `sqlite3`. To create an fts5 index, I issue:

```sql
CREATE VIRTUAL TABLE IF NOT EXISTS zettel_fts USING fts5(title, filename, full_text, uuid UNINDEXED);
```

Note that this doesn't seem limited to our text notes; indeed I can produce the full text of other attached binary files like PDFs and index them too, or maybe at a dedicated `fts5` table as well.

The `fts5` index needs to be filled manually by us, and we can use SQL triggers to automate this.

An `INSERT` trigger for `BinaryMetadata` might look like:

```sql
CREATE TRIGGER fts_insert
    AFTER INSERT ON BinaryMetadata
WHEN json_valid(NEW.name)
BEGIN
    INSERT INTO
    zettel_fts(uuid, title, filename, full_text)
    VALUES (NEW.uuid, NEW.name, json_extract(NEW.name, '$.filename'), NEW.data);
END;
```

I insert some dummy values:

```sql
INSERT INTO
BinaryMetadata(uuid,name,data)
VALUES

('623fec5beac242fcb0b0d17ada20e2b5',
json_object('content_type','text/plain','filename','file.txt','size',5),
'sun bicycle trigger journal'),

('37a3ff02c8cd4d7fb3280e5b160d1389',
json_object('content_type','text/plain','filename','book_ref.md','size',1),
'I have no references and I must scream'),

('b0697d8d76ae41bf8e942d505aff8963',
json_object('content_type','text/plain','filename','note.md','size',1),
'I refer to 623fec5b-eac2-42fc-b0b0-d17ada20e2b5 and also 37a3ff02c8cd4d7fb3280e5b160d1389');
```

Querying the index is as simple as `SELECT`ing from it:

```sql
SELECT uuid, snippet(zettel_fts, -1, '<mark>', '</mark>', '[...]', 10) AS snippet FROM zettel_fts('journal');
uuid                              snippet
--------------------------------  ----------------------------------------
623fec5beac242fcb0b0d17ada20e2b5  sun bicycle trigger <mark>journal</mark>
```

Read the `fts5` documentation [here](https://sqlite.org/fts5.html).

### Reference index

First we need a way to recognize UUIDs in text. For this purpose I create a text tokenizer using the `fts3` text tokenizers that spouts tokens that look like UUIDs:

```sql
CREATE VIRTUAL TABLE IF NOT EXISTS uuidtok USING fts3tokenize(
    'unicode61',
    "tokenchars=-1234567890abcdefABCDEF",
    "separators= "
);
```

The UUIDs are spouted when you query the tokenizer. Querying a tokenizer in general is done with a special `SELECT`:

```sql
SELECT token FROM uuidtok where input = 'sun bicycle trigger journal';
```

```
token
-------
sun
bicycle
trigger
journal
```

Now, to get stuff that look like UUIDs from the tokenizer:

```sql
SELECT DISTINCT REPLACE(token, '-', '') as ref FROM uuidtok
    WHERE input =
    (SELECT data FROM BinaryMetadata WHERE uuid =
    'b0697d8d76ae41bf8e942d505aff8963')
    AND LENGTH(REPLACE(token, '-', '')) = 32
```

This returns:

```
ref
--------------------------------
623fec5beac242fcb0b0d17ada20e2b5
37a3ff02c8cd4d7fb3280e5b160d1389
```

Note the use of `REPLACE` to exclude any hyphens from our processing.

Now we can create a reference index that we can update on insert/update/delete with triggers:

```sql
CREATE VIRTUAL TABLE refs_fts USING fts5(referrer, target);
```

We can make triggers that use the `SELECT DISTINCT` above along with a check that the reference target exists by adding

```sql
AND EXISTS (select 1 from BinaryMetadata WHERE uuid = REPLACE(token, '-', ''))
```

By having two columns in `refs_fts`, `referrer` and `target` we can get all references inside a note and all back references from other notes.

#### Examples

```sql
INSERT INTO refs_fts(target, referrer)
SELECT DISTINCT REPLACE(tok.token, '-', '') AS target,
                b.uuid AS referrer
FROM uuidtok AS tok,
(SELECT uuid,
        data,
        json_extract(name, '$.content_type') AS _type
 FROM BinaryMetadata
 WHERE json_valid(name)
   AND _type LIKE "%text/%") AS b
WHERE tok.input=b.data
  AND LENGTH(REPLACE(tok.token, '-', '')) = 32
  AND EXISTS (SELECT * FROM BinaryMetadata WHERE uuid = REPLACE(tok.token, '-', ''));
```

```sql
SELECT DISTINCT referrer FROM refs_fts WHERE target = '623fec5beac242fcb0b0d17ada20e2b5';
```

```
referrer
--------------------------------
b0697d8d76ae41bf8e942d505aff8963
```

```sql
SELECT DISTINCT target FROM refs_fts WHERE referrer = 'b0697d8d76ae41bf8e942d505aff8963';
```

```
target
--------------------------------
623fec5beac242fcb0b0d17ada20e2b5
37a3ff02c8cd4d7fb3280e5b160d1389
```

## Miscellanea

- We can read text from the `sqlite3` CLI by just `SELECT`ing the data. To save the data, text or any binary into a file use the `writefile` CLI function:

  ```sql
  SELECT writefile(json_extract(name, '$.filename'),data) FROM BinaryMetadata WHERE uuid = '623fec5beac242fcb0b0d17ada20e2b5';
  ```
  To insert a file as a `BLOB`, use the `readfile` CLI function (example from [`sqlite3` documentation](https://www.sqlite.org/cli.html#file_i_o_functions):

  ```sql
  INSERT INTO images(name,type,img) VALUES('icon','jpeg',readfile('icon.jpg'));

  ```

  To edit a file, use `edit()` (again, CLI only):

  ```sql
  UPDATE pics SET img=edit(img,'gimp') WHERE id='pic-1542';
  ```

  Yes, that means you can use your editor of choice without problem. You can also just view any file with `edit()` by selecting it without doing any `UPDATE`.

- `sqlite` supports Common Table Expressions, an SQL standard that allows you to query hierarchical relationships like nodes in a graph. That means you can easily find all the notes you can reach with references and back references. For info see the [documentation](https://sqlite.org/lang_with.html#hierarchical_query_examples)
- The full schema required for this article's examples is [here](https://FIXME.tld)
- There's a [web demo](here) of a zettelkasten you can explore online using `sql.js`, `sqlite3` compiled to webassembly.

## Epilogue

You can check out the `bibliothecula` project if you are interested in small tooling to support tagged storage inside `sqlite3` databases.
