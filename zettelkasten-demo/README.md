# Zettelkasten + sqlite demo

This directory includes the digitized zettelkasten of Niklas Luhmann from <https://niklas-luhmann-archiv.de/bestand/zettelkasten/zettel/ZK_1_NB_1_2_V>. The website allows you to download each zettel in json, so I wrote a scraper to download all of them. The entire archive except very few missing ones is in `scraped_jsons.tar.gz`.

Using `bibl-shell.py`, I created a database and inserted all the notes as metadata in a single `Document`.

The demo code and database is in `/web-demo/zettel.html`
