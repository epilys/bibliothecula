# bibliothecula

> *bibliothēcula* f (genitive *bibliothēculae*); first declension (Late Latin)
>
> - small library
> - small collection of books
> - **document database with tags and full-text-search, in a simple and clean [`sqlite3`](https://sqlite.org/index.html) schema**

Organise documents with tags and other metadata with the option of storing multiple files per document.

See the [database schema](docs/schema.sql) and the [documentation](docs/).

## Uses

- Organise journal articles for bibliographies
- Organise e-books
- Store plain text notes with automatic full-text search and back-reference indexing (i.e. a [Zettelkasten](https://en.wikipedia.org/wiki/Zettelkasten))

## Tooling

This repository has three small tools for this schema:

- a [virtual FUSE filesystem written in Rust](biblfs/).
- an [HTTP GUI written in python3 using Django](bibliothecula-django/).
- a [GTK3 UI in Rust](bibliothecula-gtk/) that was written early and isn't functional.


<hr />
<p align="center">
<img src="./logo_t.png" alt="Logo" width="200">
</p>
<hr />
