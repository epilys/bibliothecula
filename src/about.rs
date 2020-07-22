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

use gdk_pixbuf::Pixbuf;
use gio::{ActionExt, ApplicationFlags, Cancellable, MemoryInputStream, SimpleAction};
use glib::subclass;
use glib::translate::*;
use glib::Bytes;
use gtk::prelude::*;
use gtk::subclass::prelude::*;

static BAT: &[u8] = include_bytes!("../logo_t.png");

/*
 *       gtk! {
            <Dialog::new_with_buttons(
                Some("About The Todo List"),
                None as Option<&Window>,
                DialogFlags::MODAL,
                &[("Ok", ResponseType::Ok)]
            )>
                <Box spacing=10 orientation=Orientation::Vertical>
                    <Image pixbuf=Some(self.dog.clone())/>
                    <Label markup="<big><b>A Very Nice Todo List</b></big>"/>
                    <Label markup="made with <a href=\"http://vgtk.rs/\">vgtk</a> by me"/>
                </Box>
            </Dialog>
*/

// This is the private part of our `AboutBibliothecula` object.
// Its where state and widgets are stored when they don't
// need to be publicly accesible.
#[derive(Debug)]
pub struct AboutBibliotheculaPrivate {
    bat: Pixbuf,
}

impl ObjectSubclass for AboutBibliotheculaPrivate {
    const NAME: &'static str = "AboutBibliothecula";
    type ParentType = gtk::Dialog;
    type Instance = subclass::simple::InstanceStruct<Self>;
    type Class = subclass::simple::ClassStruct<Self>;

    glib::glib_object_subclass!();

    fn new() -> Self {
        let data_stream = MemoryInputStream::from_bytes(&Bytes::from_static(BAT));
        let bat = Pixbuf::from_stream(&data_stream, None as Option<&Cancellable>).unwrap();
        Self { bat }
    }
}

impl ObjectImpl for AboutBibliotheculaPrivate {
    glib::glib_object_impl!();

    // Here we are overriding the glib::Objcet::contructed
    // method. Its what gets called when we create our Object
    // and where we can initialize things.
    fn constructed(&self, obj: &glib::Object) {
        self.parent_constructed(obj);

        let self_ = obj.downcast_ref::<gtk::Dialog>().unwrap();
        let box_ = self_.get_content_area();
        box_.set_spacing(10);
        box_.add(&gtk::Image::from_pixbuf(Some(&self.bat)));
        let title = gtk::Label::new(None);
        title.set_markup("<big><b>bibliothecula</b></big>");
        box_.add(&title);
        let website = gtk::Label::new(None);
        website.set_markup( "<a href=\"https://nessuent.xyz/bibliothecula.html\">https://nessuent.xyz/bibliothecula.html</a>");
        box_.add(&website);
    }
}

impl DialogImpl for AboutBibliotheculaPrivate {}
impl WidgetImpl for AboutBibliotheculaPrivate {}
impl ContainerImpl for AboutBibliotheculaPrivate {}
impl BinImpl for AboutBibliotheculaPrivate {}
impl WindowImpl for AboutBibliotheculaPrivate {}

//@extends gtk::Widget, gtk::Container, gtk::Bin, gtk::Window, gtk::ApplicationWindow;
glib::glib_wrapper! {
    pub struct AboutBibliothecula(
        Object<subclass::simple::InstanceStruct<AboutBibliotheculaPrivate>,
        subclass::simple::ClassStruct<AboutBibliotheculaPrivate>,
        SimpleAppWindowClass>)
        @extends gtk::Dialog, gtk::Window, gtk::Bin, gtk::Container, gtk::Widget;

    match fn {
        get_type => || AboutBibliotheculaPrivate::get_type().to_glib(),
    }
}

impl AboutBibliothecula {
    pub fn new(app: &gtk::Application) -> Self {
        glib::Object::new(Self::static_type(), &[("application", app)])
            .expect("Failed to create AboutBibliothecula")
            .downcast::<AboutBibliothecula>()
            .expect("Created AboutBibliothecula is of wrong type")
    }
}
