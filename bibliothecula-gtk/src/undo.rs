/*
 * bibliothecula - undo
 *
 * Copyright 2020 Manos Pitsidianakis
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

use crate::models::{DocumentUuid, MetadataUuid};
use std::cell::RefCell;
use std::time::Instant;

#[derive(Debug)]
pub enum MetadataKind {
    Author,
    Tag,
    Storage,
    Other,
}

#[derive(Debug)]
pub enum DocumentModification {
    AlterTitle(String),
    Add(MetadataKind, MetadataUuid),
    RemoveTag(MetadataKind, MetadataUuid),
}

#[derive(Debug)]
pub enum UndoKind {
    NewDocument { uuid: DocumentUuid },
    ModifyDocument(DocumentUuid, DocumentModification),
    DeleteDocument(DocumentUuid),
}

#[derive(Debug)]
pub struct UndoItem {
    kind: UndoKind,
    time: Instant,
}

thread_local! {
    pub static UNDO: RefCell<Vec<UndoItem>> = RefCell::new(vec![]);
}
