# bibliothecula [![License]][gpl3]&nbsp;[![No Maintenance Intended]][no-maintenance]

[gpl3]: https://github.com/epilys/bibliothecula/blob/main/COPYING
[License]: https://img.shields.io/github/license/epilys/bibliothecula?color=white
[No Maintenance Intended]: https://img.shields.io/badge/No%20Maintenance%20Intended-%F0%9F%97%99-red
[no-maintenance]: https://unmaintained.tech/

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
- an [HTTP GUI written in python3 using django](bumblebat/).
- a [GTK3 UI in Rust](bibliothecula-gtk/) that was written early and isn't functional.
- an interactive python shell, `bibl-shell.py`, with convenient types and methods for working with your database:

  ```console
  % ./bibl-shell.py --help
  usage: bibl-shell.py [-h] [-i {ipython3,python3}] [--autocommit] [-v]
                       [--no-startup]
                       db_name

  Python shell with convenient methods and objects for an sqlite3
  database with the bibliothecula schema. Licensed GPL-3.0-or-later

  positional arguments:
    db_name               sqlite3 database to use.

  optional arguments:
    -h, --help            show this help message and exit
    -i {ipython3,python3}, --interpreter {ipython3,python3}
                          interpreter to use.
    --autocommit          Autocommit on every statement. If false, you'd have to
                          remember to commit on your own before you close the
                          connection.
    -v, --verbose         Show SQL etc actions taken.
    --no-startup          When using plain Python, ignore the PYTHONSTARTUP
                          environment variable and ~/.pythonrc.py script.
  ```
 
  ```console
  % python3.7 bibl-shell.py bibliothecula.db
  python3 3.7.3 (default, Jan 22 2021, 20:04:44) [GCC 8.3.0]
                              bibliothecula shell 📇 📚 🏷️  🦇
         (_    ,_,    _)
         / `'--) (--'` \      exported objects:
        /  _,-'\_/'-,_  \      - conn : sqlite3.Connection
       /.-'     "     '-.\     -   db : Database (see NAMESPACE dict
          ______ ______                            for every  import)
        _/      Y      \_       >>> help(db)
       // ~~ ~~ | ~~ ~  \\      >>> help(conn)
      // ~ ~ ~~ | ~~~ ~~ \\     >>> print(LONG_SHELL_BANNER)
     //________.|.________\\    >>> db.stats()
    `----------`-'----------'

  Connected to bibliothecula.db, last modified 2021-06-21 00:07
  >>>
  ```

<hr />
<p align="center">
<img src="./logo_t.png" alt="Logo" width="200">
</p>
<hr />
