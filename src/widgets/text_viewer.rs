/*
 * bibliothecula -
 *
 * Copyright  Manos Pitsidianakis
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

pub struct TextViewerWindow(gtk::Builder);

impl TextViewerWindow {
    pub fn new() -> Self {
        let widget_src = include_str!("./TextViewerWindow.glade");
        let builder = gtk::Builder::new_from_string(widget_src);
        TextViewerWindow(builder)
    }

    pub fn window(&self) -> gtk::Window {
        self.0
            .get_object("text_viewer_window")
            .expect("Couldn't get text_viewer_window")
    }

    pub fn set_text(self, text: &str) -> Self {
        let text_view: gtk::TextView = self
            .0
            .get_object("text_view")
            .expect("Couldn't get text_view");
        text_view
            .get_buffer()
            .expect("Couldn't get text_view")
            .set_text(text);
        self
    }
}
