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

pub struct EditDocumentFrame {
    builder: gtk::Builder,
    parent_builder: Rc<gtk::Builder>,
    connection: Rc<DatabaseConnection>,
}

impl EditDocumentFrame {
    pub fn new(connection: Rc<DatabaseConnection>, parent_builder: Rc<gtk::Builder>) -> Self {
        let widget_src = include_str!("./EditDocumentFrame.glade");
        let builder = gtk::Builder::new_from_string(widget_src);

        let add_file_button: gtk::Button = builder.get_object("add-file-button").unwrap();
        add_file_button.connect_clicked(clone!(@strong builder as parent_builder, @strong connection as connection => move |_| {
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
        {
            let author_cloud: gtk::IconView = builder.get_object("author_cloud").unwrap();
            let author_open_item: gtk::MenuItem = builder.get_object("author_open_item").unwrap();
            author_open_item.connect_activate(clone!(@strong builder as builder => move |_| {
                let t: gtk::CellRendererText =
                    builder.get_object("author_name_cell").unwrap();
                //println!("{}", t.get_property_text().unwrap());
                let uc: gtk::CellRendererText =
                    builder.get_object("author_uuid_cell").unwrap();
                //println!("{}", uc.get_property_text().unwrap());
                let uuid = uc.get_property_text().unwrap();
                println!("Open author with uuid {}", uuid);
            }
            ));
            let author_remove_item: gtk::MenuItem =
                builder.get_object("author_remove_item").unwrap();
            author_remove_item.connect_activate(clone!(@strong builder as builder, @strong connection as connection => move |_| {
                let t: gtk::CellRendererText =
                    builder.get_object("author_name_cell").unwrap();
                //println!("{}", t.get_property_text().unwrap());
                let uc: gtk::CellRendererText =
                    builder.get_object("author_uuid_cell").unwrap();
                //println!("{}", uc.get_property_text().unwrap());
                let uuid = uc.get_property_text().unwrap();
                println!("Remove author tag with uuid {}", uuid);

                let dialog = gtk::Dialog::new_with_buttons::<gtk::Window>(Some("Remove tag?"), None, gtk::DialogFlags::MODAL, &[("No", gtk::ResponseType::No), ("Yes", gtk::ResponseType::Yes), ]);
                let text = gtk::Label::new(Some("Remove author tag? This will not delete the tag."));
                dialog.get_content_area().add(&text);
                dialog.show_all();

                let ret = dialog.run();

                dialog.destroy();
                println!("{:?}", ret);
                if ret == gtk::ResponseType::Yes {
                    let document_label =
                        builder.get_object::<gtk::Label>("uuid_label").unwrap().get_text();
                    if !document_label.as_ref().map(|g| g.as_str()).unwrap_or_default().is_empty() {
                        connection.remove_metadata_from_document(&uuid.as_str().into(), &document_label.unwrap().as_str().into()).unwrap();
                    }
                    let author_store: gtk::ListStore = builder.get_object("author_store").unwrap();
                    let author_cloud: gtk::IconView = builder.get_object("author_cloud").unwrap();
                    let selected = author_cloud.get_selected_items();
                    for path in selected {
                        let idx = author_store.get_iter(&path).unwrap();
                        author_store.remove(&idx);
                    }
                }
            }));
            author_cloud.connect_button_press_event({
                let builder = builder.clone();
                let author_cloud = author_cloud.clone();

                move |this, event| {
                    println!("{:?}", &event);
                    if event.get_event_type() == gdk::EventType::ButtonPress
                        && event.get_button() == 3
                    {
                        if let Some((x, y)) = event.get_coords() {
                            if let Some((treepath, item)) =
                                author_cloud.get_item_at_pos(x as i32, y as i32)
                            {
                                author_cloud.select_path(&treepath);
                                let t: gtk::CellRendererText =
                                    item.downcast::<gtk::CellRendererText>().unwrap();
                                println!("{}", t.get_property_text().unwrap());
                                let uc: gtk::CellRendererText =
                                    builder.get_object("author_uuid_cell").unwrap();
                                println!("{}", uc.get_property_text().unwrap());
                                let author_name_header_menu: gtk::MenuItem =
                                    builder.get_object("author_name_title").unwrap();
                                author_name_header_menu
                                    .set_label(t.get_property_text().unwrap().as_str());
                                let author_uuid_header_menu: gtk::MenuItem =
                                    builder.get_object("author_uuid_item").unwrap();
                                author_uuid_header_menu.set_label(&format!(
                                    "Uuid: {}",
                                    uc.get_property_text().unwrap().as_str()
                                ));
                                let menu: gtk::Menu = builder.get_object("author_menu").unwrap();
                                menu.set_property_attach_widget(Some(this));

                                menu.show_all();
                                menu.popup_easy(event.get_button(), event.get_time());
                                return Inhibit(true); //It has been handled.
                            }
                        }
                    }
                    Inhibit(false)
                }
            });
        }
        let tag_cloud: gtk::IconView = builder.get_object("tag_cloud").unwrap();
        tag_cloud.connect_button_press_event({
            let builder = builder.clone();
            let tag_cloud = tag_cloud.clone();

            move |this, event| {
                println!("{:?}", &event);
                if event.get_event_type() == gdk::EventType::ButtonPress && event.get_button() == 3
                {
                    if let Some((x, y)) = event.get_coords() {
                        if let Some((_, item)) = tag_cloud.get_item_at_pos(x as i32, y as i32) {
                            let t: gtk::CellRendererText =
                                item.downcast::<gtk::CellRendererText>().unwrap();
                            println!("{}", t.get_property_text().unwrap());
                            let uc: gtk::CellRendererText =
                                builder.get_object("tag_uuid_cell").unwrap();
                            println!("{}", uc.get_property_text().unwrap());
                            let tag_name_header_menu: gtk::MenuItem =
                                builder.get_object("tag_name_header_item").unwrap();
                            tag_name_header_menu.set_label(t.get_property_text().unwrap().as_str());
                            let tag_uuid_header_menu: gtk::MenuItem =
                                builder.get_object("tag_uuid_item").unwrap();
                            tag_uuid_header_menu.set_label(&format!(
                                "Uuid: {}",
                                uc.get_property_text().unwrap().as_str()
                            ));
                            let menu: gtk::Menu = builder.get_object("tag_menu").unwrap();
                            menu.set_property_attach_widget(Some(this));

                            menu.show_all();
                            menu.popup_easy(event.get_button(), event.get_time());
                            return Inhibit(true); //It has been handled.
                        }
                    }
                }
                Inhibit(false)
            }
        });
        let tag_open_item: gtk::MenuItem = builder.get_object("tag_open_item").unwrap();
        tag_open_item.connect_activate(clone!(@strong builder as builder => move |_| {
            let t: gtk::CellRendererText =
                builder.get_object("tag_name_cell").unwrap();
            //println!("{}", t.get_property_text().unwrap());
            let uc: gtk::CellRendererText =
                builder.get_object("tag_uuid_cell").unwrap();
            //println!("{}", uc.get_property_text().unwrap());
            let uuid = uc.get_property_text().unwrap();
            println!("Open tag with uuid {}", uuid);
        }
        ));
        let tag_remove_item: gtk::MenuItem = builder.get_object("tag_remove_item").unwrap();
        tag_remove_item.connect_activate(clone!(@strong builder as builder => move |_| {
            let t: gtk::CellRendererText =
                builder.get_object("tag_name_cell").unwrap();
            //println!("{}", t.get_property_text().unwrap());
            let uc: gtk::CellRendererText =
                builder.get_object("tag_uuid_cell").unwrap();
            //println!("{}", uc.get_property_text().unwrap());
            let uuid = uc.get_property_text().unwrap();
            println!("Remove tag tag with uuid {}", uuid);
        }));
        EditDocumentFrame{builder, connection, parent_builder}
    }

    pub fn frame(&self) -> gtk::Frame {
        let edit_document_frame: gtk::Frame = self
            .builder
            .get_object("EditDocumentFrame")
            .expect("Could not build EditDocumentFrame");
        edit_document_frame
    }

    pub fn title_entry(&self) -> gtk::Entry {
        let title_entry: gtk::Entry = self.builder.get_object("title-entry").unwrap();
        title_entry
    }

    pub fn with_document(self, uuid: models::DocumentUuid) -> Self {
        let connection = &self.connection;
        let d: crate::models::Document = connection.get(&uuid);
        self.title_entry().set_text(d.title.as_str());
        self.builder
            .get_object::<gtk::Label>("uuid_label")
            .unwrap()
            .set_text(d.uuid.to_string().as_str());
        for f in connection.get_files(&uuid) {
            self.add_file_entry(
                &format!(
                    "{} ({})",
                    match f.1 {
                        crate::models::StorageType::Local(ref path) => path.display().to_string(),
                        crate::models::StorageType::InDatabase(ref mime_type) =>
                            mime_type.to_string(),
                    },
                    Bytes(f.2)
                ),
                match f.1 {
                    crate::models::StorageType::Local(_) => "document-open",
                    crate::models::StorageType::InDatabase(ref mime_type) => {
                        match mime_type.as_str() {
                            "text/plain" => "text-x-generic",
                            _ => "document-open",
                        }
                    }
                },
                match f.1 {
                    crate::models::StorageType::Local(_) => "Open with xdg-open",
                    crate::models::StorageType::InDatabase(ref mime_type) => {
                        match mime_type.as_str() {
                            "text/plain" => "View text in a new window",
                            _ => "Open with xdg-open",
                        }
                    }
                },
                f.0,
            );
            println!("{:?}", f);
        }
        for a in connection.get_authors(&uuid) {
            self.add_author_entry(&a.1, a.0);
        }
        for t in connection.get_tags(&uuid) {
            self.add_tag_entry(&t.1, t.0);
        }
        self
    }

    pub fn add_file_entry(
        &self,
        label_text: &str,
        icon_name: &str,
        button_tooltip_text: &str,
        uuid: models::MetadataUuid,
    ) {
        let connection = &self.connection;
        let file_list_box: gtk::ListBox = self.builder.get_object("file-list-box").unwrap();
        file_list_box.set_visible(true);

        let file_entry_builder = gtk::Builder::new_from_string(include_str!("./FileSlotBox.glade"));
        let button = gtk::Button::new();
        let label: gtk::Label = file_entry_builder
            .get_object("file_identifier_label")
            .unwrap();
        label.set_text(label_text);

        let open_image = gtk::Image::new_from_icon_name(Some(icon_name), IconSize::Button);
        button.set_relief(ReliefStyle::None);
        button.set_focus_on_click(false);
        button.add(&open_image);
        button.set_tooltip_text(Some(button_tooltip_text));
        let button_box: gtk::ButtonBox = file_entry_builder.get_object("file_button_box").unwrap();
        button_box.add(&button);

        let entry: gtk::Box = file_entry_builder.get_object("file_slot_box").unwrap();
        file_list_box.prepend(&entry);
        button.connect_clicked(clone!(@weak connection as connection => move |_| {
            let bytes = connection.get_data(&uuid);
            let data = String::from_utf8_lossy(&bytes);
            let viewer = TextViewerWindow::new().set_text(&data);
            viewer.window().set_position(gtk::WindowPosition::Center);
            viewer.window().set_default_size(640, 480);
            viewer.window().show_all();

            println!("edit {:?}", &uuid);
        }));
    }

    pub fn add_tag_entry(&self, label_text: &str, uuid: models::MetadataUuid) {
        let tag_cloud: gtk::IconView = self.builder.get_object("tag_cloud").unwrap();
        tag_cloud.set_visible(true);
        let tag_store: gtk::ListStore = self.builder.get_object("tag_store").unwrap();
        tag_store.insert_with_values(None, &[0, 1], &[&uuid.to_string().as_str(), &label_text]);
    }

    pub fn add_author_entry(&self, label_text: &str, uuid: models::MetadataUuid) {
        let author_cloud: gtk::IconView = self.builder.get_object("author_cloud").unwrap();
        author_cloud.set_visible(true);
        let author_store: gtk::ListStore = self.builder.get_object("author_store").unwrap();
        author_store.insert_with_values(None, &[0, 1], &[&uuid.to_string().as_str(), &label_text]);
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


trait StoreExt {
    fn len(&self) -> i32;
}

impl StoreExt for gtk::ListStore {
    fn len(&self) -> i32{
         self.iter_n_children(None)
    }
}
