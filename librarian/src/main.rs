use biblatex::Bibliography;
use std::ffi::{OsStr, OsString};
use std::fs::File;
use std::io::Read;
use xattr::FileExt;

fn main() {
    let __src = "@book{tolkien1937, author = {J. R. R. Tolkien}}";
    let mut src = String::new();
    std::io::stdin().read_to_string(&mut src).unwrap();
    if let Some(file_path) = std::env::args().skip(1).next() {
        let mut file = File::open(&file_path).unwrap();
        let attrs = file.list_xattr().unwrap().collect::<Vec<OsString>>();
        dbg!(&attrs);
    }
    let bibliography = Bibliography::parse(&src).unwrap();
    //let entry = bibliography.get("tolkien1937").unwrap();
    //let author = entry.author().unwrap();
    //assert_eq!(author[0].name, "Tolkien");
    dbg!(&bibliography);
}
