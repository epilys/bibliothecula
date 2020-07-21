/*
 * meli -
 *
 * Copyright  Manos Pitsidianakis
 *
 * This file is part of meli.
 *
 * meli is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * meli is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with meli. If not, see <http://www.gnu.org/licenses/>.
 */

use super::*;

pub struct App;

impl App {
    pub fn build_ui(application: &gtk::Application, conn: Rc<DatabaseConnection>) {
        let glade_src = include_str!("./bibliothecula.glade");
        let builder = Rc::new(gtk::Builder::from_string(glade_src));
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
            edit_document_widget.title_entry().get_text().as_str(),
            edit_document_widget.frame().upcast(),
            false,
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
}
