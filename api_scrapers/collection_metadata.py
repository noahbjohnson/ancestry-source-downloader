import json
from typing import List, TypedDict

from selenium import webdriver
from selenium.webdriver.remote.webelement import WebElement


class CollectionMetadata(TypedDict, total=False):
    dbid: str
    database_name: str
    levels: List[str]
    category_name: str
    category_id: str
    can_save: bool
    publication_year: int


def get_collection_metadata(driver: webdriver.Chrome, dbid: str) -> CollectionMetadata:
    """Queries the api for the given collection id"""
    url: str = f"https://www.ancestry.com/imageviewer/api/media/info-by-id?dbId={dbid}"
    driver.get(url)
    pre: WebElement = driver.find_element_by_tag_name("pre")
    parsed = json.loads(pre.text)
    image_info = parsed['imageInfo']
    dbid: str = str(image_info['dbId'])
    database_name: str = str(image_info["collectionInfo"]['databaseName'])
    navigation_levels: List[str] = list(image_info['structureType'].values())
    category_name: str = str(image_info["collectionInfo"]['primaryCategoryName'])
    category_id: str = str(image_info["collectionInfo"]['primaryCategoryId'])
    image_savable: bool = bool(image_info["collectionInfo"]['canSaveImage'])
    publish_year: int = int(image_info['collectionInfo']['publicationYear'])
    metadata: CollectionMetadata = {
        'dbid':             dbid,
        'database_name':    database_name,
        'levels':           navigation_levels,
        'category_name':    category_name,
        'category_id':      category_id,
        'can_save':         image_savable,
        'publication_year': publish_year
    }
    return metadata
