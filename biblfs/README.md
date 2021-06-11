# bibliothecula FUSE filesystem

Mount an sqlite3 database with a bibliothecula schema as a filesystem.

## Demo

```console
$ ls ~/Documents/biblfs | head
total 393K
drwxr-xr-x  2 epilys epilys     0 Jan  1  1970 ./
drwxrwxrwt 98 root   root    120K Jun 14 19:27 ../
-rw-r--r--  1 epilys epilys  589K Jun 14 00:35 a-a-milne_the-red-house-mystery.epub
-rw-r--r--  1 epilys epilys  450K Jun 14 00:58 aesop_fables_v-s-vernon-jones.epub
-rw-r--r--  1 epilys epilys  601K Jun 14 00:58 agatha-christie_poirot-investigates.epub
-rw-r--r--  1 epilys epilys  594K Jun 14 00:58 agatha-christie_the-man-in-the-brown-suit.epub
-rw-r--r--  1 epilys epilys  523K Jun 14 00:40 agatha-christie_the-murder-on-the-links.epub
-rw-r--r--  1 epilys epilys  780K Jun 14 00:37 agatha-christie_the-mysterious-affair-at-styles.epub
-rw-r--r--  1 epilys epilys  651K Jun 14 00:58 agatha-christie_the-secret-adversary.epub
$ ls "~/Documents/biblfs/tags/Arthurian romances"
total 1.5K
drwxr-xr-x 2 epilys epilys    0 Jan  1  1970 ./
drwxr-xr-x 2 epilys epilys    0 Jan  1  1970 ../
-rw-r--r-- 1 epilys epilys 817K Jun 14 00:35 alfred-lord-tennyson_idylls-of-the-king.epub
-rw-r--r-- 1 epilys epilys 979K Jun 14 00:45 mark-twain_a-connecticut-yankee-in-king-arthurs-court.epub
-rw-r--r-- 1 epilys epilys 1.6M Jun 14 00:39 thomas-malory_le-morte-darthur.epub
$ ls ~/Documents/biblfs/query/journal | head
total 73K
drwxr-xr-x 2 epilys epilys     0 Jan  1  1970 ./
drwxr-xr-x 2 epilys epilys     0 Jan  1  1970 ../
-rw-r--r-- 1 epilys epilys  1.1M Jun 14 00:40 alexander-hamilton_john-jay_james-madison_the-federalist-papers.epub
-rw-r--r-- 1 epilys epilys  679K Jun 14 00:35 alexander-pushkin_eugene-onegin_henry-spalding.epub
-rw-r--r-- 1 epilys epilys  1.7M Jun 14 00:35 alexandre-dumas_the-count-of-monte-cristo_chapman-and-hall.epub
-rw-r--r-- 1 epilys epilys  1.1M Jun 14 00:35 alexandre-dumas_the-three-musketeers_william-robson.epub
-rw-r--r-- 1 epilys epilys  572K Jun 14 00:35 ambrose-bierce_the-devils-dictionary.epub
-rw-r--r-- 1 epilys epilys  664K Jun 14 00:35 anatole-france_penguin-island_a-w-evans.epub
-rw-r--r-- 1 epilys epilys  1.1M Jun 14 00:35 anthony-trollope_the-way-we-live-now.epub
```

## Build

Requires stable Rust, `rustup` and `cargo`.

## Use

```shell
mkdir ~/Documents/biblfs
cargo run -- --mount-point ~/Documents/biblfs --database ~/Documents/bibliothecula.db
```
