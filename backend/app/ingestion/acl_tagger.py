"""
ACL tagger: attaches resolved permissions to raw chunks and validates with Chunk schema.
"""

from app.index.schema import Chunk
from app.security.principals import doc_tokens, finalize_acl_tokens


def tag_chunks(
    raw_chunks: list[dict],
    acl_info: dict,
    source_name: str,
    source_doc: str,
    source_id: str,
    source_type: str = "pdf",
    corpus: str = "main",
    owner_id: str = "u_admin",
) -> list[Chunk]:
    """
    Attach ACL metadata to raw chunk dicts and validate with Pydantic Chunk schema.
    Fails closed: any validation error will raise immediately before embedding or storage.
    """
    validated_chunks: list[Chunk] = []

    base_tokens = doc_tokens(acl_info)
    if not base_tokens:
        raise ValueError(f"Empty permission tokens for {source_id} (fail-closed access control)")
    tokens = finalize_acl_tokens(base_tokens)

    for raw in raw_chunks:
        chunk = Chunk(
            chunk_id=raw["chunk_id"],
            doc_id=raw["doc_id"],
            source_doc=source_doc,
            source_id=source_id,
            source_type=source_type,
            source_name=source_name,
            corpus=corpus,
            page=raw.get("page"),
            bbox=raw.get("bbox"),
            table=raw.get("table"),
            row_pk=raw.get("row_pk"),
            chunk_type=raw.get("chunk_type", "text"),
            text=raw["text"],
            owner_id=owner_id,
            allowed_roles=acl_info.get("allowed_roles", []),
            allowed_employees=acl_info.get("allowed_employees", []),
            allowed_departments=acl_info.get("allowed_departments", []),
            acl_tokens=tokens,
            classification_label=acl_info.get("classification", "internal"),
        )
        validated_chunks.append(chunk)

    return validated_chunks
