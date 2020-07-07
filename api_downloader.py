import json
import os
import random
import time
from typing import List, TypedDict

import dotenv
import requests
import sqlalchemy.engine
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from models.collection import Base, Collection

API_SEARCH = "https://www.ancestry.com/search/collections/catalog/api/search"


class InvalidInputError(ValueError):
    """Invalid collection id or other input is passed"""


class CollectionEntryDescription(TypedDict):
    DbId: str
    CultureId: str
    TextType: int
    Value: str


class CollectionEntry(TypedDict):
    dbId: str
    nativeCultureId: str
    categoryId: str
    title: str
    recordCount: str
    collection: str
    activeDate: str
    updatedDate: str
    activity: str
    collectionFeature: str
    description: CollectionEntryDescription


def format_pagination_body(page: int, size: int, paging_token=""):
    """

    :param page:
    :param size:
    :param paging_token:
    :return:
    """
    return {
        "queryTerms": {},
        "sortByKey":  "ACTIVE_DATE",
        "cultureId":  "en-US",
        "pagingInfo": {
            "PageNumber":     page,
            "PagingToken":    paging_token,
            "RecordsPerPage": size
        }
    }


def random_sleep(min_sec=1, max_sec=30, log=True, factor=1):
    """Sleep for a random number of seconds

    :param min_sec:
    :param max_sec:
    :param log:
    :param factor:
    :return:
    """
    min_sec = min_sec * factor
    max_sec = max_sec * factor
    sleep_time = random.randint(min_sec, max_sec)
    if log:
        print(f"Waiting for {sleep_time}s")
    time.sleep(sleep_time)


class Controller(object):
    _authenticated: bool = False
    _engine_initialized: bool = False
    _session: requests.Session
    _db_engine: sqlalchemy.engine.Engine
    _sqlite_file: str = "data/database.db"
    _username: str
    _password: str

    def __init__(self, user: str, pas: str):
        """

        :param user: Ancestry.com username
        :param pas: Ancestry.com password
        """
        self._session = requests.Session()
        self._username = user
        self._password = pas
        self._login()

    def _login(self):
        """Authenticate with the ancestry API"""
        if not self._authenticated:
            print("Logging in")
            self._session.post("https://www.ancestry.com/account/signin/frame/authenticate",
                               {"username": self._username, "password": self._password})
            self._authenticated = True

    def _init_db_engine(self):
        self._db_engine = create_engine(f'sqlite:///{self._sqlite_file}', echo=True)
        Base.metadata.create_all(self._db_engine)
        self._engine_initialized = True

    def _get_db_session(self) -> Session:
        if not self._engine_initialized:
            self._init_db_engine()
        return sessionmaker(bind=self._db_engine)()

    def _get_metadata_target(self) -> int:
        """ Selects next target for updating collection metadata

        :return: Collection ID to target
        """
        session = self._get_db_session()
        collection = session.query(Collection).order_by(Collection.time_updated.asc(),
                                                        Collection.collection_feature.asc()).filter_by(
                database_name=None).first()
        return collection.collection_id

    def save_collection_metadata(self, dbid: int = 0):
        """ Save metadata to the collection record from endpoints other than search

        :param dbid: Optional, which collection id to save metadata for. Defaults to the least recently updated record.
        :return: None
        """
        if not dbid:
            dbid = self._get_metadata_target()

        url: str = f"https://www.ancestry.com/imageviewer/api/media/info-by-id?dbId={dbid}"
        url2: str = f"https://www.ancestry.com/imageviewer/api/collection/id?dbId={dbid}"

        db_session = self._get_db_session()
        exists_query = db_session.query(Collection).filter_by(collection_id=dbid)
        if exists_query.scalar():
            collection = exists_query.first()
            if collection.collection_feature != "indexOnly":
                parsed = self._session.get(url)
                if parsed.ok:
                    image_info = parsed.json()['imageInfo']
                    collection.database_name = str(image_info["collectionInfo"]['databaseName'])
                    collection.set_levels(list(image_info['structureType'].values()))
                    collection.category_name = str(image_info["collectionInfo"]['primaryCategoryName'])
                    collection.category_id = str(image_info["collectionInfo"]['primaryCategoryId'])
                    collection.publication_year = int(image_info['collectionInfo']['publicationYear'])
            parsed = self._session.get(url2)
            if parsed.ok:
                collection.collection_title = parsed.json()['collectionTitle']
                collection.source_info = parsed.json()['onlineSourceInfo']
                collection.is_yearbook_collection = parsed.json()['isYearbookCollection']
            db_session.commit()

    def save_collections_to_disk(self, n: int = 1000):
        def search_post(page: int, size: int, paging_token=""):
            return self._session.post(
                    API_SEARCH,
                    json=format_pagination_body(page, size, paging_token=paging_token)
            )

        def get_total_results() -> int:
            return search_post(1, 1).json()['TotalResults']

        # get total collection count
        total_results = get_total_results()

        def log_page(page_num: int, retry=False):
            if retry:
                print(f"rate limit hit on page {page_num}. trying again\n")
            print(f"getting page {page_num} of {total_results}")

        # Initialize loop variables
        pagination_token = [""]
        loop_count = (total_results // n) + 1

        # get n results at a time
        for i in range(loop_count):
            log_page(i)
            random_sleep()
            with open(f"data/temp/collections{i}.json", "w") as f:
                res = search_post(i + 1, n, paging_token=pagination_token[0])
                if res.ok:
                    pagination_token[0] = res.json()['PagingInfo']['PagingToken']
                    f.write(res.text)
                else:
                    log_page(i, retry=True)
                    random_sleep(factor=3)
                    res = search_post(i + 1, n, paging_token=pagination_token[0])
                    if not res.ok:
                        raise ResourceWarning(f"rate limit critical on page {i}")
                    else:
                        pagination_token[0] = res.json()['PagingInfo']['PagingToken']
                        f.write(res.text)

    def load_collections_into_db_from_disk(self):
        db_session = self._get_db_session()
        for file in os.scandir("data/temp"):
            file_name: str = file.name
            if file.is_file() and "collections" in file_name and file_name.endswith(".json"):
                print(f"parsing {file_name}")
                with open(file.path) as file_io:
                    file_data = json.loads(file_io.read())
                    entries: List[CollectionEntry] = file_data['gridData']
                    for entry in entries:
                        exists_query = db_session.query(Collection).filter_by(collection_id=int(entry['dbId']))
                        if exists_query.scalar():
                            collection = exists_query.first()
                            collection.collection_title = entry['title']
                            collection.collection_created = entry['activeDate']
                            collection.collection_updated = entry['updatedDate']
                            collection.collection_feature = entry['collectionFeature']
                            collection.native_culture_id = entry['nativeCultureId']
                            collection.category_id = entry['categoryId']
                            collection.record_count = int(entry['recordCount'].replace(",", ""))
                            collection.collection_collection = entry['collection']
                            collection.description = entry['description']['Value']
                        else:
                            collection = Collection(
                                    collection_id=int(entry['dbId']),
                                    collection_title=entry['title'],
                                    collection_created=entry['activeDate'],
                                    collection_updated=entry['updatedDate'],
                                    collection_feature=entry['collectionFeature'],
                                    native_culture_id=entry['nativeCultureId'],
                                    category_id=entry['categoryId'],
                                    record_count=int(entry['recordCount'].replace(",", "")),
                                    collection_collection=entry['collection'],
                                    description=entry['description']['Value']
                            )
                            db_session.add(collection)
                    db_session.commit()


if __name__ == '__main__':
    dotenv.load_dotenv()
    username: str = os.getenv("ANCESTRY_USERNAME")
    password: str = os.getenv("ANCESTRY_PASSWORD")
    if username is None or password is None:
        raise EnvironmentError("Username and password environment variables not set")
    controller = Controller(username, password)

    controller.save_collections_to_disk()
    controller.load_collections_into_db_from_disk()
