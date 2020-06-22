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

extern crate gdk;
extern crate gio;
extern crate glib;
extern crate gtk;
extern crate pango;

use gio::prelude::*;
use gtk::prelude::*;

use gtk::Application;

use glib::clone;
use gtk::{IconSize, Orientation, ReliefStyle, Widget};

use std::convert::TryInto;
use std::rc::Rc;

mod models;
mod widgets;

use models::DatabaseConnection;
use widgets::{EditDocumentFrame, Notebook};

fn build_ui(application: &gtk::Application, conn: Rc<DatabaseConnection>) {
    let glade_src = include_str!("./bibliothecula.glade");
    let builder = Rc::new(gtk::Builder::new_from_string(glade_src));
    let window: gtk::Window = builder
        .get_object("main-window")
        .expect("Couldn't get window");
    window.set_application(Some(application));
    //let window = gtk::ApplicationWindow::new(application);
    window.set_title("bibliothecula");

    let doc_list_store: gtk::ListStore = builder
        .get_object("main-tree-view-list-store")
        .expect("Couldn't get main-tree-view-list-store");
    for d in conn.all().into_iter() {
        doc_list_store.insert_with_values(
            None,
            &[0, 1, 2, 3, 4],
            &[
                &d.title.as_str(),
                &conn
                    .get_authors(&d.uuid)
                    .into_iter()
                    .map(|t| t.1)
                    .collect::<Vec<String>>()
                    .join(", ")
                    .as_str(),
                &conn.get_files_no(&d.uuid).try_into().unwrap_or(0),
                &conn
                    .get_tags(&d.uuid)
                    .into_iter()
                    .map(|t| t.1)
                    .collect::<Vec<String>>()
                    .join(", ")
                    .as_str(),
                &d.uuid.to_string().as_str(),
            ],
        );
    }
    let notebook = Notebook::new(builder.clone(), conn.clone());
    let edit_document_widget = EditDocumentFrame::new(conn.clone(), builder.clone())
        .with_document(models::Document::new("Magna Carta".to_string()).uuid);
    let _idx = notebook.create_tab(
        edit_document_widget
            .title_entry()
            .get_text()
            .as_ref()
            .map(|title| title.as_str())
            .unwrap_or_default(),
        edit_document_widget.frame().upcast(),
    );
    window.set_position(gtk::WindowPosition::Center);
    window.set_default_size(640, 480);
    window.show_all();
}

fn append_column(column: &gtk::TreeViewColumn, tree: &gtk::TreeView, id: i32) {
    let cell = gtk::CellRendererText::new();

    column.pack_start(&cell, true);
    // Association of the view's column with the model's `id` column.
    column.add_attribute(&cell, "text", id);
    tree.append_column(column);
}

fn main() {
    let conn = Rc::new(models::create_connection().unwrap());
    let application = Application::new(Some("com.github.bibliothecula"), Default::default())
        .expect("failed to initialize GTK application");
    //application.connect_activate(|app| {
    //});
    application.connect_activate(move |app| {
        build_ui(app, conn.clone());
        /*
        let window = ApplicationWindow::new(app);
        window.set_title("bibliothecula");
        window.set_default_size(350, 70);

        let button = Button::new_with_label("Click me!");
        button.connect_clicked(|_| {
            println!("Clicked!");
        });
        let mut artist_column = gtk::TreeViewColumn::new();
        artist_column.set_title("Artist");
        let mut song_column = gtk::TreeViewColumn::new();
        song_column.set_title("Song title");
        let music_list_store = gtk::ListStore::new(&[String::static_type(), String::static_type()]);

        music_list_store.insert_with_values(None, &[0, 1], &[&"blah", &"wah"]);
        music_list_store.insert_with_values(None, &[0, 1], &[&"glah", &"dah"]);
        let mut tree = gtk::TreeView::new_with_model(&music_list_store);
        append_column(&artist_column, &tree, 0);
        append_column(&song_column, &tree, 1);
        window.add(&tree);

        window.show_all();
        */
    });

    application.run(&[]);
}
