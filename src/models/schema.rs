table! {
    Document (uuid) {
        uuid -> Binary,
        title -> Text,
        created -> Timestamp,
        last_modified -> Timestamp,
    }
}

table! {
    DocumentHasMetadata (document_uuid, metadata_uuid) {
        document_uuid -> Binary,
        metadata_uuid -> Binary,
        is_text -> Bool,
        created -> Timestamp,
        last_modified -> Timestamp,
    }
}

table! {
    DocumentHasStorage (document_uuid, metadata_uuid) {
        document_uuid -> Binary,
        metadata_uuid -> Binary,
        is_data -> Bool,
        created -> Timestamp,
        last_modified -> Timestamp,
    }
}

table! {
    DocumentHasTag (document_uuid, metadata_uuid) {
        document_uuid -> Binary,
        metadata_uuid -> Binary,
        created -> Timestamp,
        last_modified -> Timestamp,
    }
}

table! {
    Metadata (uuid) {
        uuid -> Binary,
        name -> Nullable<Text>,
        data -> Nullable<Binary>,
        created -> Timestamp,
        last_modified -> Timestamp,
    }
}

joinable!(DocumentHasMetadata -> Document (document_uuid));
joinable!(DocumentHasMetadata -> Metadata (metadata_uuid));
joinable!(DocumentHasStorage -> Document (document_uuid));
joinable!(DocumentHasStorage -> Metadata (metadata_uuid));
joinable!(DocumentHasTag -> Document (document_uuid));
joinable!(DocumentHasTag -> Metadata (metadata_uuid));

allow_tables_to_appear_in_same_query!(
    Document,
    DocumentHasMetadata,
    DocumentHasStorage,
    DocumentHasTag,
    Metadata,
);
