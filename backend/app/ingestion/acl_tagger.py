"""
ACL tagger: attaches resolved manifest permissions to raw chunks and validates with Chunk schema.
"""

from app.index.schema import Chunk


def tag_chunks(
    raw_chunks: list[dict],
    acl_info: dict,
    source_name: str,
    source_type: str = "pdf",
) -> list[Chunk]:
    """
    Attach ACL metadata to raw chunk dicts and validate with Pydantic Chunk schema.
    Fails closed: any validation error will raise immediately before embedding or storage.
    """
    validated_chunks: list[Chunk] = []

    for raw in raw_chunks:
        chunk = Chunk(
            chunk_id=raw["chunk_id"],
            doc_id=raw["doc_id"],
            source_type=source_type,
            source_name=source_name,
            page=raw.get("page"),
            bbox=raw.get("bbox"),
            row_id=raw.get("row_id"),
            chunk_type=raw.get("chunk_type", "text"),
            text=raw["text"],
            owner_id=acl_info["owner_id"],
            allowed_roles=acl_info.get("allowed_roles", []),
            allowed_users=acl_info.get("allowed_users", []),
            classification=acl_info.get("classification", 1),
            is_public=acl_info.get("is_public", False),
        )
        validated_chunks.append(chunk)

    return validated_chunks
