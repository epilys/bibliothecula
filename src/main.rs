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

mod app;
mod models;
mod undo;
mod widgets;

use models::DatabaseConnection;
use widgets::{EditDocumentFrame, Notebook};

fn main() {
    let conn = Rc::new(models::create_connection().unwrap());
    let application = Application::new(Some("com.github.bibliothecula"), Default::default())
        .expect("failed to initialize GTK application");
    application.connect_activate(move |app| {
        app::App::build_ui(app, conn.clone());
    });

    application.run(&[]);
}
