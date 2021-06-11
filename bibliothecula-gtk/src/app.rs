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
use gtk::subclass::prelude::*;
use once_cell::unsync::OnceCell;

impl<'g> From<&'g gtk::Application> for &'g Application {
    fn from(val: &'g gtk::Application) -> Self {
        val.downcast_ref::<Application>()
            .expect("Created Application is of wrong type")
    }
}

impl Application {
    pub fn build_ui(&self) {
        let notebook = Notebook::new(self.clone());
        self.get_private().notebook.set(notebook).unwrap();
    }
}

#[derive(Debug)]
pub struct ApplicationPrivate {
    pub builder: OnceCell<Rc<gtk::Builder>>,
    pub connection: OnceCell<Rc<DatabaseConnection>>,
    pub notebook: OnceCell<widgets::Notebook>,
}

impl ObjectSubclass for ApplicationPrivate {
    const NAME: &'static str = "Application";
    type ParentType = gtk::Application;
    type Instance = subclass::simple::InstanceStruct<Self>;
    type Class = subclass::simple::ClassStruct<Self>;

    glib_object_subclass!();

    fn new() -> Self {
        Self {
            builder: OnceCell::new(),
            connection: OnceCell::new(),
            notebook: OnceCell::new(),
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
    fn activate(&self, app: &gio::Application) {
        let app = app.downcast_ref::<gtk::Application>().unwrap();
        let builder = self.builder.get().unwrap();
        let window: gtk::Window = builder
            .get_object("main-window")
            .expect("Couldn't get window");
        window.set_application(Some(app));
        window.set_title("bibliothecula");
        let about_menu_item: gtk::MenuItem = builder
            .get_object("about-menu-item")
            .expect("Couldn't get about-menu-item");
        about_menu_item.connect_activate(clone!(@strong builder as builder => move |_| {
            let app = builder.get_application().unwrap();
            let about = crate::about::AboutBibliothecula::new(&app);
            about.show_all();
        }));
        window.set_position(gtk::WindowPosition::Center);
        window.set_default_size(640, 480);
        window.show_all();
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
        let app = app.downcast_ref::<gtk::Application>().unwrap();
        let glade_src = include_str!("./bibliothecula.glade");
        let builder = Rc::new(gtk::Builder::from_string(glade_src));
        builder.set_application(app);
        self.builder
            .set(builder)
            .expect("Failed to initialize application about window");
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

impl ApplicationPrivate {
    pub fn connection(&self) -> Rc<DatabaseConnection> {
        self.connection.get().unwrap().clone()
    }

    pub fn builder(&self) -> Rc<gtk::Builder> {
        self.builder.get().unwrap().clone()
    }

    pub fn builder_ref(&self) -> &gtk::Builder {
        self.builder.get().unwrap().as_ref()
    }
}

impl Application {
    pub fn new() -> Self {
        let ret = glib::Object::new(
            Self::static_type(),
            &[
                ("application-id", &"org.epilys.bibliothecula"),
                ("flags", &ApplicationFlags::empty()),
            ],
        )
        .expect("Failed to create App")
        .downcast()
        .expect("Created app is of wrong type");
        let connection = DatabaseConnection::create_connection(&ret).unwrap();
        ret.get_private()
            .connection
            .set(Rc::new(connection))
            .expect("Failed to initialize application db connection");
        ret
    }

    pub fn get_private(&self) -> &ApplicationPrivate {
        ApplicationPrivate::from_instance(self)
    }

    pub fn get_gtk_app(&self) -> &gtk::Application {
        self.upcast_ref::<gtk::Application>()
    }

    pub fn set_title(&self, new_title: &str) {
        let window: gtk::Window = self
            .get_private()
            .builder_ref()
            .get_object("main-window")
            .expect("Couldn't get window");
        window.set_title(new_title);
    }
}
