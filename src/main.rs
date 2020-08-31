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
extern crate gdk_pixbuf;
extern crate gio;
#[macro_use]
extern crate glib;
extern crate gtk;
extern crate pango;
#[macro_use]
extern crate diesel;
#[macro_use]
extern crate error_chain;

use gio::prelude::*;
use gtk::prelude::*;

use glib::clone;
use gtk::{IconSize, Orientation, ReliefStyle, Widget};

use std::convert::TryInto;
use std::rc::Rc;

pub mod about;
pub mod errors;
pub use errors::*;
mod app;
mod models;
//mod undo;
mod widgets;

use models::DatabaseConnection;
use widgets::Notebook;

fn main() {
    let application = crate::app::Application::new();
    application.connect_activate(move |app| {
        app.build_ui();
    });

    application.run(&[]);
}
