/*
 * bibliothecula - document_liststore
 *
 * Copyright 2020 Manos Pitsidianakis
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

use super::*;
use crate::models::Document;
use glib::subclass;
use glib::translate::*;
use gtk::subclass::prelude::*;
use once_cell::unsync::OnceCell;
use std::cell::Cell;

#[derive(Debug)]
#[repr(i32)]
enum Columns {
    Title = 0,
    Authors,
    FilesNo,
    Tags,
    LastModified,
    Created,
    Uuid,
}

fn create_model() -> gtk::ListStore {
    let col_types: [glib::Type; 7] = [
        glib::Type::String,
        glib::Type::String,
        glib::Type::U32,
        glib::Type::String,
        glib::Type::String,
        glib::Type::String,
        glib::Type::String,
    ];

    let store = gtk::ListStore::new(&col_types);

    /*
    let col_indices: [u32; 6] = [0, 1, 2, 3, 4, 5];

    for (d_idx, d) in data.iter().enumerate() {
        let values: [&dyn ToValue; 8] = [
            &d.title,
            &d.number,
            &d.severity,
            &d.description,
            &0u32,
            &icon_name,
            &false,
            &sensitive,
        ];
        store.set(&store.append(), &col_indices, &values);
    }
    */

    store
}

#[derive(Debug)]
pub struct DocumentListPrivate {
    counter: Cell<u64>,
    pub list_store: OnceCell<gtk::ListStore>,
    pub application: OnceCell<gtk::Application>,
}

impl ObjectSubclass for DocumentListPrivate {
    const NAME: &'static str = "DocumentList";
    type ParentType = gtk::TreeView;
    type Instance = subclass::simple::InstanceStruct<Self>;
    type Class = subclass::simple::ClassStruct<Self>;

    glib_object_subclass!();

    fn new() -> Self {
        Self {
            counter: Cell::new(0),
            list_store: OnceCell::new(),
            application: OnceCell::new(),
        }
    }
}

impl ObjectImpl for DocumentListPrivate {
    glib_object_impl!();

    // Here we are overriding the glib::Objcet::contructed
    // method. Its what gets called when we create our Object
    // and where we can initialize things.
    fn constructed(&self, obj: &glib::Object) {
        self.parent_constructed(obj);

        let self_ = obj.downcast_ref::<DocumentList>().unwrap();

        self_.set_vexpand(true);
        self_.set_search_column(Columns::Title as i32);
        let model = create_model();

        self_.set_model(Some(&model));
        self_.get_private().list_store.set(model).unwrap();
        self_.add_columns();
        self_.show_all();

        //sw.add(&treeview);

        //add_columns(&model, &treeview);
        /*
        let headerbar = gtk::HeaderBar::new();
        let increment = gtk::Button::with_label("Increment!");
        let label = gtk::Label::new(Some("Press the Increment Button!"));

        headerbar.set_title(Some("Hello World!"));
        headerbar.set_show_close_button(true);
        headerbar.pack_start(&increment);

        // Connect our method `on_increment_clicked` to be called
        // when the increment button is clicked.
        increment.connect_clicked(clone!(@weak self_ => move |_| {
            let priv_ = DocumentListPrivate::from_instance(&self_);
            priv_.on_increment_clicked();
        }));

        self_.add(&label);
        //self_.set_titlebar(Some(&headerbar));
        self_.set_default_size(640, 480);
        */
    }
}

impl WidgetImpl for DocumentListPrivate {}
impl ContainerImpl for DocumentListPrivate {}
impl TreeViewImpl for DocumentListPrivate {}

glib_wrapper! {
    pub struct DocumentList(
        Object<subclass::simple::InstanceStruct<DocumentListPrivate>,
        subclass::simple::ClassStruct<DocumentListPrivate>,
        DocumentListClass>)
        @extends gtk::Widget, gtk::Container, gtk::TreeView;

    match fn {
        get_type => || DocumentListPrivate::get_type().to_glib(),
    }
}

impl DocumentList {
    pub fn new(app: &gtk::Application) -> Self {
        let ret = glib::Object::new(Self::static_type(), &[])
            .expect("Failed to create DocumentList")
            .downcast::<DocumentList>()
            .expect("Created DocumentList is of wrong type");

        ret.get_private().application.set(app.clone()).unwrap();
        ret.connect_signals();
        ret
    }

    pub fn get_private(&self) -> &DocumentListPrivate {
        DocumentListPrivate::from_instance(self)
    }

    fn add_columns(&self) {
        let treeview = self;
        // Column for title
        {
            let renderer = gtk::CellRendererText::new();
            let column = gtk::TreeViewColumn::new();
            column.pack_start(&renderer, true);
            column.set_title("Title");
            column.add_attribute(&renderer, "text", Columns::Title as i32);
            column.set_sort_column_id(Columns::Title as i32);
            treeview.append_column(&column);
        }

        // Column for authors
        {
            let renderer = gtk::CellRendererText::new();
            let column = gtk::TreeViewColumn::new();
            column.pack_start(&renderer, true);
            column.set_title("Authors");
            column.add_attribute(&renderer, "text", Columns::Authors as i32);
            column.set_sort_column_id(Columns::Authors as i32);
            treeview.append_column(&column);
        }

        // Column for FilesNo
        {
            let renderer = gtk::CellRendererText::new();
            let column = gtk::TreeViewColumn::new();
            column.pack_start(&renderer, true);
            column.set_title("# files");
            column.add_attribute(&renderer, "text", Columns::FilesNo as i32);
            column.set_sort_column_id(Columns::FilesNo as i32);
            treeview.append_column(&column);
        }

        // Column for tags
        {
            let renderer = gtk::CellRendererText::new();
            let column = gtk::TreeViewColumn::new();
            column.pack_start(&renderer, true);
            column.set_title("Tags");
            column.add_attribute(&renderer, "text", Columns::Tags as i32);
            treeview.append_column(&column);
        }

        // Column for last modified
        {
            let renderer = gtk::CellRendererText::new();
            let column = gtk::TreeViewColumn::new();
            column.pack_start(&renderer, true);
            column.set_title("Last Modified");
            column.add_attribute(&renderer, "text", Columns::LastModified as i32);
            column.set_sort_column_id(Columns::LastModified as i32);
            treeview.append_column(&column);
        }

        // Column for created
        {
            let renderer = gtk::CellRendererText::new();
            let column = gtk::TreeViewColumn::new();
            column.pack_start(&renderer, true);
            column.set_title("Created");
            column.add_attribute(&renderer, "text", Columns::Created as i32);
            column.set_sort_column_id(Columns::Created as i32);
            treeview.append_column(&column);
        }

        // Column for uuid
        {
            let renderer = gtk::CellRendererText::new();
            renderer.set_sensitive(false);
            let column = gtk::TreeViewColumn::new();
            column.pack_start(&renderer, true);
            column.set_title("Uuid");
            column.add_attribute(&renderer, "text", Columns::Uuid as i32);
            column.set_sort_column_id(Columns::Uuid as i32);
            treeview.append_column(&column);
        }
    }

    pub fn set_documents(&self, documents: &[Document]) {
        let app: &crate::app::Application = self.get_private().application.get().unwrap().into();
        let conn = app.get_private().connection();
        let model = self.get_private().list_store.get().unwrap();
        model.clear();

        let col_indices: [u32; 7] = [0, 1, 2, 3, 4, 5, 6];

        for d in documents.iter() {
            let authors_string = conn
                .get_authors(&d.uuid)
                .into_iter()
                .map(|t| t.1)
                .collect::<Vec<String>>()
                .join(", ");
            let tag_string = conn
                .get_tags(&d.uuid)
                .into_iter()
                .map(|t| t.1)
                .collect::<Vec<String>>()
                .join(", ");
            let uuid_string = d.uuid.to_string();
            let values: [&dyn ToValue; 7] = [
                &d.title,
                &authors_string.as_str(),
                &conn.get_files_no(&d.uuid).try_into().unwrap_or(0),
                &tag_string.as_str(),
                &d.last_modified.to_string(),
                &d.created.to_string(),
                &uuid_string.as_str(),
            ];
            model.set(&model.append(), &col_indices, &values);
        }
    }

    fn connect_signals(&self) {
        let app = self.get_private().application.get().unwrap().clone();
        self.connect_button_press_event({
            move |this, event| {
                if event.get_event_type() == gdk::EventType::ButtonPress && event.get_button() == 3
                {
                    let selection: gtk::TreeSelection = this.get_selection();
                    if let Some((tree_model, tree_iter)) = selection.get_selected() {
                        let uuid_val = tree_model
                            .get_value(&tree_iter, 6)
                            .downcast::<glib::GString>()
                            .unwrap()
                            .get()
                            .unwrap()
                            .to_string();
                        //println!("uuid_val: {}", &uuid_val);
                        let menu = gtk::Menu::new();
                        let uuid_item = gtk::MenuItemBuilder::new()
                            .label(uuid_val.as_str())
                            .can_focus(false)
                            .sensitive(false)
                            .build();
                        menu.append(&uuid_item);
                        menu.append(&gtk::SeparatorMenuItem::new());
                        let open_item =
                            gtk::MenuItemBuilder::new().label("Open in new tab").build();
                        open_item.connect_activate(
                            clone!(@strong app as app => move |_this_open_item| {
                                //println!("Open document with uuid {}", &uuid_val);
                                let app: &crate::app::Application = (&app).into();
                                let conn = app.get_private().connection();
                                let edit_document_widget = EditDocumentFrame::new(conn)
                                    .with_document(uuid_val.as_str().into());
                                let _idx = app.get_private().notebook.get().unwrap().create_tab(
                                    NotebookTab::EditDocument(edit_document_widget),
                                    false,
                                );
                            }),
                        );

                        menu.append(&open_item);
                        menu.set_property_attach_widget(Some(this));

                        menu.show_all();
                        menu.popup_easy(event.get_button(), event.get_time());
                        return Inhibit(true); //It has been handled.
                    }
                }
                Inhibit(false)
            }
        });
    }
}
