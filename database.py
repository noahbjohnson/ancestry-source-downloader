from datetime import datetime

from sqlalchemy import Boolean, Column, create_engine, ForeignKey, Integer, Sequence, String, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import create_session, relationship

Base = declarative_base()


def get_connection(echo: bool):
    return create_engine('sqlite:///data.db', echo=echo)


def get_session(connection):
    return create_session(connection)


class CollectionSection(Base):
    """An ancestry.com record collection or breadcrumb section

    Acts as a single recursively referenced table for everything except the pages
     themselves and their records eg: [Federal Census 1990, Illinois, Cook, Chicago, ward 4]

    > collection = CollectionSection(site_id = "1234", name = "New Orleans, Louisiana, Index to Death Records, 1804-1964", link = "https://www.ancestry.com/search/collections/6606", is_root = True, has_pages = False)
    > collection.children.append(
            CollectionSection(
                name = "1953-1960", has_pages = True, index_table_name="new_orleans_deaths_1953_to_1960")
        )
    """
    __tablename__ = 'collection_section'
    id = Column(Integer, Sequence('collection_section_id_seq'), primary_key=True)
    site_id = Column(String(64), nullable=True)
    name = Column(String(256), nullable=False)
    link = Column(String(256), nullable=True)

    is_root = Column(Boolean, default=False)
    has_pages = Column(Boolean, default=False)

    index_table_name = Column(String(256), nullable=True)

    time_created = Column(TIMESTAMP, default=datetime.utcnow, nullable=False)
    time_updated = Column(TIMESTAMP, onupdate=datetime.utcnow, nullable=False, default=datetime.utcnow)

    parent_id = Column(Integer, ForeignKey('collection_section.id'), nullable=True)
    children = relationship("CollectionSection",
                            lazy="joined",
                            join_depth=3
                            )

    def __repr__(self):
        return "<CollectionSection(name='%s' site_id='%s')>" % (
            self.name, self.site_id)
