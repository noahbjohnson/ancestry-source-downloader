from datetime import datetime
from typing import List

from sqlalchemy import Boolean, Column, Integer, Sequence, String, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Collection(Base):
    """An ancestry.com record collection"""
    __tablename__ = 'collection'
    id = Column(Integer, Sequence('collection_section_id_seq'), primary_key=True)
    # Ancestry collection id
    collection_id = Column(String(64), nullable=False, index=True, unique=True)
    # name (ie 1790 census)
    collection_title = Column(String(256), nullable=True)
    # If the collection is a yearbook
    is_yearbook_collection = Column(Boolean, default=False)
    # pipe-delimited array
    navigation_levels = Column(String(256), nullable=True)
    # ie cen_1790
    category_name = Column(String(256), nullable=True)
    # ie 170
    category_id = Column(String(256), nullable=True)
    # ie 1790usfedcen
    database_name = Column(String(256), nullable=True)
    # 1790
    publication_year = Column(Integer, nullable=True, index=True)

    time_created = Column(TIMESTAMP, default=datetime.utcnow, nullable=False)
    time_updated = Column(TIMESTAMP, onupdate=datetime.utcnow, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return "<Collection(id='%s')>" % self.collection_id

    def get_levels(self) -> List[str]:
        return self.navigation_levels.split("|")

    def set_levels(self, levels: List[str]):
        self.navigation_levels = "|".join(levels)
