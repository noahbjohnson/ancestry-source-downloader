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


def save_collections_to_disk(requests_session: requests.Session, n: int = 1000):
    # get total collection count
    r = requests_session.post(
            "https://www.ancestry.com/search/collections/catalog/api/search",
            json=format_pagination_body(1, 1)
    )
    total_results = r.json()['TotalResults']
    pagination_token = [""]
    # get n results at a time
    for i in range((total_results // n) + 1):
        sleep_time = random.randint(1, 30)
        print(f"getting page {i} with a {sleep_time}s delay")
        time.sleep(sleep_time)
        with open(f"data/collections{i}.json", "w") as f:
            res = requests_session.post(
                    "https://www.ancestry.com/search/collections/catalog/api/search",
                    json=format_pagination_body(i + 1, n, paging_token=pagination_token[0])
            )
            if not res.ok:
                print(f"rate limit hit on page {i}")
                print(f"getting page {i} with a {sleep_time * 3}s delay")
                time.sleep(sleep_time * 3)
                res = requests_session.post(
                        "https://www.ancestry.com/search/collections/catalog/api/search",
                        json=format_pagination_body(i + 1, n, paging_token=pagination_token[0])
                )
                if not res.ok:
                    raise ResourceWarning(f"rate limit hard on page {i}")
                else:
                    pagination_token[0] = res.json()['PagingInfo']['PagingToken']
                    f.write(res.text)
            else:
                pagination_token[0] = res.json()['PagingInfo']['PagingToken']
                f.write(res.text)


def load_collections_into_db_from_disk(db_session: Session):
    for file in os.scandir("data"):
        if file.is_file():
            file_name: str = file.name
            if "collections" in file_name and file_name.endswith(".json"):
                print(f"parsing {file_name}")
                with open(file.path) as file_io:
                    file_data = json.loads(file_io.read())
                    entries: List[CollectionEntry] = file_data['gridData']
                    for entry in entries:
                        #
                        if db_session.query(Collection).filter_by(collection_id=int(entry['dbId'])).scalar():
                            collection = db_session.query(Collection).filter_by(
                                    collection_id=int(entry['dbId'])).first()
                            collection.collection_title = entry['title']
                            collection.collection_id = int(entry['dbId'])
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

        with webdriver.Chrome() as driver:
            # login in browser and steal cookies
            driver.minimize_window()
            login(driver, username, password)
            c = [s.cookies.set(c['name'], c['value']) for c in driver.get_cookies()]

    # load into db from disk
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
