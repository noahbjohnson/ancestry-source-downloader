import json
import os
import random
import time
from typing import List, TypedDict

import dotenv
import requests
from selenium import webdriver
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from actions.auth import login
from api_scrapers.collection_metadata import get_collection_metadata
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


def add_collection_metadata_to_session(web_driver: webdriver.Chrome, dbid: str, db_session: Session):
    collection_info = get_collection_metadata(web_driver, dbid)
    collection = Collection(
            collection_id=int(collection_info['dbid']),
            database_name=collection_info['database_name'],
            category_name=collection_info['category_name'],
            category_id=collection_info['category_id'],
            publication_year=collection_info['publication_year'],
            collection_title=collection_info['title'],
            is_yearbook_collection=collection_info['is_yearbook'],
            source_info=collection_info['source_info']
    )
    collection.set_levels(collection_info['levels'])
    db_session.add(collection)
    session.commit()


def format_pagination_body(page: int, size: int, paging_token=""):
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


def save_collections_to_disk(requests_session: requests.Session, n: int = 1000):
    def search_post(page: int, size: int, paging_token=""):
        return requests_session.post(
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
        with open(f"data/collections{i}.json", "w") as f:
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


def load_collections_into_db_from_disk(db_session: Session):
    for file in os.scandir("data"):
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

    with requests.Session() as s:

        chrome_options = webdriver.ChromeOptions()
        chrome_options.headless = True
        with webdriver.Chrome(options=chrome_options) as driver:
            login(driver, username, password)
            c = [s.cookies.set(c['name'], c['value']) for c in driver.get_cookies()]

        engine = create_engine('sqlite:///api.db', echo=True)
        SessionMaker = sessionmaker(bind=engine)
        Base.metadata.create_all(engine)
        session = SessionMaker()

    save_collections_to_disk(s)

    load_collections_into_db_from_disk(session)

# except KeyboardInterrupt:
#     print("Attempting to shut down gracefully")
#     break
#
# except InvalidInputError:
#     print(InvalidInputError)
