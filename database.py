from datetime import datetime

from sqlalchemy import Boolean, create_engine, Column, DateTime, ForeignKey, func, Integer, String, Sequence, Time, \
    TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base, ConcreteBase
from sqlalchemy.orm import backref, relationship

Base = declarative_base()


class CollectionSection(Base):
    """An ancestry.com record collection or breadcrumb section

    Acts as a single recursively referenced table for everything except the pages
     themselves and their records eg: [Federal Census 1990, Illinois, Cook, Chicago, ward 4]
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
