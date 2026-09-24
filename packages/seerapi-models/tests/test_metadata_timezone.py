from sqlmodel import Session, create_engine

from seerapi_models.metadata import ApiMetadata, ApiMetadataORM


def test_generated_metadata_can_be_stored_with_timezone() -> None:
    metadata = ApiMetadata(
        api_url='https://api.example.test',
        api_version='v1',
        generator_name='solaris',
        generator_version='test',
    )
    assert metadata.generate_time.tzinfo is not None

    engine = create_engine('sqlite://')
    ApiMetadataORM.__table__.create(engine)
    with Session(engine) as session:
        session.add(metadata.to_orm())
        session.commit()
