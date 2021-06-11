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
use std::cell::RefCell;
mod edit_document_frame;
pub use edit_document_frame::*;

mod text_viewer;
pub use text_viewer::*;

mod document_liststore;
use document_liststore::*;

pub enum NotebookTab {
    EditDocument(EditDocumentFrame),
    Search(gtk::Box),
}

impl NotebookTab {
    fn title(&self) -> String {
        match self {
            NotebookTab::EditDocument(ref inner) => {
                inner.title_entry().get_text().as_str().to_string()
            }
            NotebookTab::Search(_) => "search".to_string(),
        }
    }

    fn as_widget(&self) -> Widget {
        match self {
            NotebookTab::EditDocument(ref inner) => inner.frame().upcast(),
            NotebookTab::Search(ref b) => b.clone().upcast(),
        }
    }

    fn init_as_tab(&self, parent: &Notebook) {
        match self {
            NotebookTab::EditDocument(ref inner) => inner.init_as_tab(parent),
            NotebookTab::Search(_) => {}
        }
    }
}

#[derive(Clone)]
pub struct Notebook {
    builder: Rc<gtk::Builder>,
    conn: Rc<DatabaseConnection>,
    tabs: Rc<RefCell<Vec<NotebookTab>>>,
    application: crate::app::Application,
}

impl core::fmt::Debug for Notebook {
    fn fmt(&self, f: &mut core::fmt::Formatter) -> core::fmt::Result {
        write!(f, "{}", "Notebook")
    }
}

impl Notebook {
    pub fn new(application: crate::app::Application) -> Self {
        let conn = application.get_private().connection();
        let builder: Rc<gtk::Builder> = application.get_private().builder();
        let ret = Self {
            builder,
            conn,
            tabs: Rc::new(RefCell::new(vec![])),
            application,
        };
        ret.init();
        ret
    }

    pub fn create_tab(&self, tab: NotebookTab, sticky: bool) -> u32 {
        let notebook: gtk::Notebook = self
            .builder
            .get_object("global-notebook")
            .expect("Couldn't get window");
        let close_image = gtk::Image::from_icon_name(Some("window-close"), IconSize::Button);
        let button = gtk::Button::new();
        let title = tab.title();
        let widget = tab.as_widget();
        let label = gtk::Label::new(Some(&title));
        let tab_box = gtk::Box::new(Orientation::Horizontal, 0);

        if !sticky {
            button.set_relief(ReliefStyle::None);
            button.set_focus_on_click(false);
            button.add(&close_image);
        }

        tab_box.pack_start(&label, false, false, 0);
        if !sticky {
            tab_box.pack_start(&button, false, false, 0);
        }
        tab_box.show_all();

        let index = notebook.append_page(&widget, Some(&tab_box));

        let pages_no = notebook.get_n_pages();
        if pages_no != 1 {
            notebook.set_show_tabs(true);
        }

        if !sticky {
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
        }
        notebook.set_current_page(Some(index));
        tab.init_as_tab(&self);
        self.tabs.borrow_mut().push(tab);

        index
    }

    fn build_menu_bar(&self) {
        let inner = self.clone();
        let Self {
            ref builder,
            ref conn,
            tabs: _,
            application: _,
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
                let edit_document_widget = EditDocumentFrame::new(conn.clone());
                // title -> "New document"
                let _idx = inner.create_tab(NotebookTab::EditDocument(edit_document_widget), false);
            }),
        );
    }

    pub fn init(&self) {
        self.build_menu_bar();
        let conn = self.conn.clone();
        let s_box = gtk::Box::new(Orientation::Vertical, 0);
        let doc_list = DocumentList::new(self.application.get_gtk_app());
        match self.conn.all() {
            Err(err) => {
                gtk::MessageDialogBuilder::new()
                    .text(err.to_string().as_str())
                    .attached_to(&s_box)
                    .buttons(gtk::ButtonsType::Close)
                    .build()
                    .run();
            }
            Ok(results) => {
                doc_list.set_documents(&results);
            }
        }
        let search_bar = gtk::SearchBar::new();
        search_bar.set_search_mode(true);
        search_bar.set_hexpand(true);
        search_bar.set_vexpand(false);
        search_bar.set_show_close_button(false);
        let search_entry = gtk::SearchEntryBuilder::new()
            .hexpand(true)
            .enable_emoji_completion(true)
            .placeholder_text("Search for tags or title or authors")
            .show_emoji_icon(true)
            .build();
        search_entry.connect_search_changed(clone!(@strong doc_list, @strong conn => move |this| {
            match conn.search(this.get_text().as_str()) {
                Err(err) => {
                     gtk::MessageDialogBuilder::new()
                         .text(err.to_string().as_str())
                         .attached_to(this)
                         .buttons(gtk::ButtonsType::Close)
                         .build().run();
                },
                Ok(results) => {
                    doc_list.set_documents(&results);
                }
            }
        }));
        search_bar.add(&search_entry);
        search_bar.connect_entry(&search_entry);
        s_box.pack_start(&search_bar, false, true, 0);
        s_box.pack_start(&doc_list, true, true, 0);
        s_box.show_all();
        self.create_tab(NotebookTab::Search(s_box), true);
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
