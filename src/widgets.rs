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
mod edit_document_frame;
pub use edit_document_frame::*;

mod text_viewer;
pub use text_viewer::*;

pub struct Notebook {
    builder: Rc<gtk::Builder>,
    conn: Rc<DatabaseConnection>,
}

impl Notebook {
    pub fn new(builder: Rc<gtk::Builder>, conn: Rc<DatabaseConnection>) -> Self {
        let ret = Self { builder, conn };
        ret.init();
        ret
    }

    pub fn create_tab(&self, title: &str, widget: Widget) -> u32 {
        let notebook: gtk::Notebook = self
            .builder
            .get_object("global-notebook")
            .expect("Couldn't get window");
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

    fn build_menu_bar(&self) {
        let Self {
            ref builder,
            ref conn,
        } = self;
        let button: gtk::ToolButton = builder
            .get_object("new-button")
            .expect("Couldn't get new-button");
        button.connect_clicked(
        clone!(@strong conn as conn, @strong builder as builder => move |_| {
        let notebook: gtk::Notebook = builder
            .get_object("global-notebook")
            .expect("Couldn't get window");
            let pages_no = notebook.get_n_pages();
            if pages_no == 1 {
                notebook.set_show_tabs(true);
            }
            let edit_document_widget = EditDocumentFrame::new( conn.clone(), builder.clone());
            let idx = Self { builder: builder.clone(), conn: conn.clone() }.create_tab("New Document", edit_document_widget.frame().upcast());
            let tab = notebook.get_nth_page(Some(idx)).unwrap();
            edit_document_widget.title_entry().connect_changed(clone!(@weak notebook as notebook, @weak tab as tab => move |slf| {
                let label_box: gtk::Box = notebook.get_tab_label(&tab).unwrap().downcast().unwrap();
                let label: gtk::Label = label_box.get_children().remove(0).downcast().unwrap();
                if let Some(title) = slf.get_text().and_then(|title| if title.as_str().is_empty() { None } else { Some(title) }) {
                    label.set_label(&format!("{} (unsaved)", title.as_str()));
                } else {
                    label.set_label("New Document");
                }
            }));
            println!("new-icon!");
        }),
    );
    }

    fn build_treeview(&self) {
        let main_tree_view: gtk::TreeView = self
            .builder
            .get_object("main-tree-view")
            .expect("Couldn't get main-tree-view");
        main_tree_view.connect_button_press_event({
            let main_tree_view = main_tree_view.clone();
            let conn = self.conn.clone();
            let builder = self.builder.clone();
            move |this, event| {
                println!("main_tree_view.connect_button_press_event {:?}", &event);
                if event.get_event_type() == gdk::EventType::ButtonPress && event.get_button() == 3
                {
                    if let Some((x, y)) = event.get_coords() {
                        if let Some((Some(path), col, cellx, celly)) =
                            std::dbg!(main_tree_view.get_path_at_pos(x as i32, y as i32))
                        {
                            main_tree_view.grab_focus();
                            main_tree_view.set_cursor(&path, col.as_ref(), false);
                            let selection: gtk::TreeSelection = main_tree_view.get_selection();
                            if let Some((tree_model, tree_iter)) = selection.get_selected() {
                                let uuid_val = tree_model
                                    .get_value(&tree_iter, 4)
                                    .downcast::<glib::GString>()
                                    .unwrap()
                                    .get()
                                    .unwrap()
                                    .to_string();
                                println!("uuid_val: {}", &uuid_val);
                                let main_tree_view_context_menu_uuid_header_item: gtk::MenuItem =
                                    builder
                                        .get_object("main-tree-view-context-menu-uuid-header-item")
                                        .unwrap();
                                main_tree_view_context_menu_uuid_header_item.set_label(&uuid_val);
                                let menu: gtk::Menu =
                                    builder.get_object("main-tree-view-context-menu").unwrap();
                                menu.set_property_attach_widget(Some(this));

                                menu.show_all();
                                menu.popup_easy(event.get_button(), event.get_time());
                                return Inhibit(true); //It has been handled.
                            }
                        }
                    }
                }
                Inhibit(false)
            }
        });
        let main_tree_view_context_menu_open_item_in_new_tab: gtk::MenuItem = self
            .builder
            .get_object("main-tree-view-context-menu-open-item-in-new-tab")
            .unwrap();
        main_tree_view_context_menu_open_item_in_new_tab.connect_activate(
            clone!(@strong self.builder as builder, @strong self.conn as conn => move |_| {
                let uc: gtk::MenuItem =
                    builder.get_object("main-tree-view-context-menu-uuid-header-item").unwrap();
                //println!("{}", uc.get_property_text().unwrap());
                // FIXME: This gets the item's UUID to open from the menu item's label, there
                // must be a better way to get the current selection's UUID value from the
                // TreeModel. Note that this label is set when the menu is opened in
                // connect_button_press_event
                let uuid = uc.get_label().unwrap().to_string();
                println!("Open document with uuid {}", uuid);
                let edit_document_widget = EditDocumentFrame::new(conn.clone(), builder.clone())
                    .with_document(uuid.into());
                let _idx = Self { builder: builder.clone(), conn: conn.clone() }.create_tab(
                    edit_document_widget
                    .title_entry()
                    .get_text()
                    .as_ref()
                    .map(|title| title.as_str())
                    .unwrap_or_default(),
                    edit_document_widget.frame().upcast(),
                );
            }
            ),
        );
        main_tree_view.connect_popup_menu({
            let conn = self.conn.clone();
            let builder = self.builder.clone();
            move |this| false
        });
    }

    pub fn init(&self) {
        self.build_menu_bar();
        self.build_treeview();
        let search_box_src = include_str!("./widgets/SearchTab.glade");
        let builder = Rc::new(gtk::Builder::new_from_string(search_box_src));
        let box_: gtk::Box = builder.get_object("search-tab").unwrap();
        self.create_tab("search", box_.upcast());
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
