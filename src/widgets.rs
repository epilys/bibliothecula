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

use super::*;
pub struct Notebook;

impl Notebook {
    pub fn create_tab(notebook: &gtk::Notebook, title: &str, widget: Widget) -> u32 {
        let close_image = gtk::Image::new_from_icon_name(Some("window-close"), IconSize::Button);
        let button = gtk::Button::new();
        let label = gtk::Label::new(Some(title));
        let tab = gtk::Box::new(Orientation::Horizontal, 0);

        button.set_relief(ReliefStyle::None);
        button.set_focus_on_click(false);
        button.add(&close_image);

        tab.pack_start(&label, false, false, 0);
        tab.pack_start(&button, false, false, 0);
        tab.show_all();

        let index = notebook.append_page(&widget, Some(&tab));

        let pages_no = notebook.get_n_pages();
        if pages_no != 1 {
            notebook.set_show_tabs(true);
        }

        button.connect_clicked(clone!(@weak notebook as notebook => move |_| {
            let index = notebook
                .page_num(&widget)
                .expect("Couldn't get page_num from notebook");
            notebook.remove_page(Some(index));
            let pages_no = notebook.get_n_pages();
            if pages_no == 1 {
                notebook.set_show_tabs(false);
            }
        }));
        println!("new-tab! idx = {}, title = {}", index, title);
        notebook.set_current_page(Some(index));

        index
    }
}

pub struct EditDocumentFrame(gtk::Builder);

impl EditDocumentFrame {
    pub fn new() -> Self {
        let widget_src = include_str!("./EditDocumentFrame.glade");
        let builder = gtk::Builder::new_from_string(widget_src);

        let add_file_button: gtk::Button = builder.get_object("add-file-button").unwrap();
        add_file_button.connect_clicked(clone!(@strong builder as parent_builder => move |_| {
            println!("add_file_button!");
            let widget_src = include_str!("./AddFileAssistant.glade");
            let builder = gtk::Builder::new_from_string(widget_src);
            let assistant: gtk::Assistant = builder.get_object("add-file-assistant").unwrap();
            assistant.connect_close(clone!(@strong builder as builder => move |_| {
                let assistant: gtk::Assistant = builder.get_object("add-file-assistant").unwrap();
                assistant.destroy();
            }));
            assistant.connect_cancel(clone!(@strong builder as builder => move |_| {
                let assistant: gtk::Assistant = builder.get_object("add-file-assistant").unwrap();
                assistant.destroy();
            }));
            assistant.connect_apply(clone!(@strong builder as builder => move |_| {
            }));
            assistant.set_forward_page_func(Some(Box::new(clone!(@strong builder as _builder => move |current_page:i32| {
                println!("current_page: {}", current_page);
                current_page + 1
            }))));
            let embedded_radio_button: gtk::RadioButton = builder.get_object("embedded-radio-button").unwrap();
            embedded_radio_button.set_active(true);
            let select_file_radio_button: gtk::RadioButton = builder.get_object("select-file-radio-button").unwrap();
            select_file_radio_button.set_active(true);
            select_file_radio_button.connect_toggled(clone!(@strong builder as builder => move |b| {
                let file_chooser_button: gtk::FileChooserButton = builder.get_object("file-chooser-button").unwrap();
                file_chooser_button.set_sensitive(b.get_active());
            }));
            let direct_input_radio_button: gtk::RadioButton = builder.get_object("direct-input-radio-button").unwrap();
            direct_input_radio_button.connect_toggled(clone!(@strong builder as builder => move |b| {
                let direct_input_text_view: gtk::TextView = builder.get_object("direct-input-text-view").unwrap();
                direct_input_text_view.set_sensitive(b.get_active());
            }));

            assistant.show_all();
        }));
        EditDocumentFrame(builder)
    }

    pub fn frame(&self) -> gtk::Frame {
        let edit_document_frame: gtk::Frame = self
            .0
            .get_object("EditDocumentFrame")
            .expect("Could not build EditDocumentFrame");
        edit_document_frame
    }

    pub fn title_entry(&self) -> gtk::Entry {
        let title_entry: gtk::Entry = self.0.get_object("title-entry").unwrap();
        title_entry
    }

    pub fn with_document(
        self,
        connection: Rc<DatabaseConnection>,
        uuid: models::DocumentUuid,
    ) -> Self {
        let d: crate::models::Document = connection.get(&uuid);
        self.title_entry().set_text(d.title.as_str());
        for f in connection.get_files(&uuid) {
            let file_list_box: gtk::ListBox = self.0.get_object("file-list-box").unwrap();
            file_list_box.set_visible(true);
            let button = gtk::Button::new();
            let label = gtk::Label::new(Some(&format!(
                "{} ({})",
                match f.1 {
                    crate::models::StorageType::Local(ref path) => path.display().to_string(),
                    crate::models::StorageType::InDatabase(ref mime_type) => mime_type.to_string(),
                },
                Bytes((f.2))
            )));
            /*
            label.set_attributes(Some(&{
                let list = pango::AttrList::new();
                list.insert(
                    pango::Attribute::new_background(std::u16::MAX, std::u16::MAX, std::u16::MAX)
                        .unwrap(),
                );
                list
            }));
            */
            let entry = gtk::Box::new(Orientation::Horizontal, 0);

            let open_image = gtk::Image::new_from_icon_name(
                Some(match f.1 {
                    crate::models::StorageType::Local(_) => "document-open",
                    crate::models::StorageType::InDatabase(ref mime_type) => {
                        match mime_type.as_str() {
                            "text/plain" => "text-x-generic",
                            _ => "document-open",
                        }
                    }
                }),
                IconSize::Button,
            );
            button.set_relief(ReliefStyle::None);
            button.set_focus_on_click(false);
            button.add(&open_image);
            button.set_tooltip_text(Some(match f.1 {
                crate::models::StorageType::Local(_) => "Open with xdg-open",
                crate::models::StorageType::InDatabase(ref mime_type) => match mime_type.as_str() {
                    "text/plain" => "View text in a new window",
                    _ => "Open with xdg-open",
                },
            }));

            entry.pack_start(&label, false, false, 0);
            entry.pack_start(&button, false, false, 0);
            entry.show_all();
            file_list_box.prepend(&entry);
            let u = f.0.clone();
            button.connect_clicked(clone!(@weak connection as connection => move |_| {
                let bytes = connection.get_data(&u);
                let data = String::from_utf8_lossy(&bytes);
                let viewer = TextViewerWindow::new().set_text(&data);
                viewer.window().set_position(gtk::WindowPosition::Center);
                viewer.window().set_default_size(640, 480);
                viewer.window().show_all();

                println!("edit {:?}", &u);
            }));
            println!("{:?}", f);
        }
        self
    }
}

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

const KILOBYTE: f64 = 1024.0;
const MEGABYTE: f64 = KILOBYTE * 1024.0;
const GIGABYTE: f64 = MEGABYTE * 1024.0;
const PETABYTE: f64 = GIGABYTE * 1024.0;

pub struct Bytes(pub usize);

impl core::fmt::Display for Bytes {
    fn fmt(&self, f: &mut core::fmt::Formatter) -> core::fmt::Result {
        let bytes = self.0 as f64;
        if bytes == 0.0 {
            write!(f, "0")
        } else if bytes < KILOBYTE {
            write!(f, "{:.2} bytes", bytes)
        } else if bytes < MEGABYTE {
            write!(f, "{:.2} KiB", bytes / KILOBYTE)
        } else if bytes < GIGABYTE {
            write!(f, "{:.2} MiB", bytes / MEGABYTE)
        } else if bytes < PETABYTE {
            write!(f, "{:.2} GiB", bytes / GIGABYTE)
        } else {
            write!(f, "{:.2} PiB", bytes / PETABYTE)
        }
    }
}
