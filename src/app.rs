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
use gio::ApplicationFlags;
use glib::subclass;
use glib::translate::*;
use gtk::prelude::*;
use gtk::subclass::prelude::*;
use once_cell::unsync::OnceCell;

impl Application {
    pub fn build_ui(application: &gtk::Application, conn: Rc<DatabaseConnection>) {
        let glade_src = include_str!("./bibliothecula.glade");
        let builder = Rc::new(gtk::Builder::from_string(glade_src));
        builder.set_application(application);
        let window: gtk::Window = builder
            .get_object("main-window")
            .expect("Couldn't get window");
        window.set_application(Some(application));
        window.set_title("bibliothecula");
        let about_menu_item: gtk::MenuItem = builder
            .get_object("about-menu-item")
            .expect("Couldn't get about-menu-item");
        about_menu_item.connect_activate(clone!(@strong builder as builder => move |_| {
            let app = builder.get_application().unwrap();
            let about = crate::about::AboutBibliothecula::new(&app);
            about.show_all();
        }));

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

#[derive(Debug)]
pub struct ApplicationPrivate {
    //about: OnceCell<crate::about::AboutBibliothecula>,
}

impl ObjectSubclass for ApplicationPrivate {
    const NAME: &'static str = "Application";
    type ParentType = gtk::Application;
    type Instance = subclass::simple::InstanceStruct<Self>;
    type Class = subclass::simple::ClassStruct<Self>;

    glib_object_subclass!();

    fn new() -> Self {
        Self {
            //about: OnceCell::new(),
        }
    }
}

impl ObjectImpl for ApplicationPrivate {
    glib_object_impl!();
}

// When our application starts, the `startup` signal will be fired.
// This gives us a chance to perform initialisation tasks that are not directly
// related to showing a new window. After this, depending on how
// the application is started, either `activate` or `open` will be called next.
impl ApplicationImpl for ApplicationPrivate {
    // `gio::Application::activate` is what gets called when the
    // application is launched by the desktop environment and
    // aksed to present itself.
    fn activate(&self, _app: &gio::Application) {
        /*
        let about = self
            .about
            .get()
            .expect("Should always be initiliazed in gio_application_startup");
        about.show_all();
        about.hide();
        //    about.present();
        //    */
    }

    // `gio::Application` is bit special. It does not get initialized
    // when `new` is called and the object created, but rather
    // once the `startup` signal is emitted and the `gio::Application::startup`
    // is called.
    //
    // Due to this, we create and initialize the `Window` widget
    // here. Widgets can't be created before `startup` has been called.
    fn startup(&self, app: &gio::Application) {
        self.parent_startup(app);

        /*
        let app = app.downcast_ref::<gtk::Application>().unwrap();
        let about = crate::about::AboutBibliothecula::new(&app);
        self.about
            .set(about)
            .expect("Failed to initialize application about window");
        */
    }
}

impl GtkApplicationImpl for ApplicationPrivate {}

glib_wrapper! {
    pub struct Application(
        Object<subclass::simple::InstanceStruct<ApplicationPrivate>,
        subclass::simple::ClassStruct<ApplicationPrivate>,
        ApplicationClass>)
        @extends gio::Application, gtk::Application;

    match fn {
        get_type => || ApplicationPrivate::get_type().to_glib(),
    }
}

impl Application {
    pub fn new() -> Self {
        glib::Object::new(
            Self::static_type(),
            &[
                ("application-id", &"org.epilys.bibliothecula"),
                ("flags", &ApplicationFlags::empty()),
            ],
        )
        .expect("Failed to create App")
        .downcast()
        .expect("Created app is of wrong type")
    }
}
