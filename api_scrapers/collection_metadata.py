import json

from selenium import webdriver


def get_collection_metadata(driver: webdriver.Chrome, dbid: str):
    """Queries the api for the given collection id"""
    url = f"https://www.ancestry.com/imageviewer/api/media/info-by-id?dbId={dbid}"
    driver.get(url)
    pre = driver.find_element_by_tag_name("pre")
    parsed = json.loads(pre.text)
    image_info = parsed['imageInfo']
    dbid = image_info['dbId']
    database_name = image_info["collectionInfo"]['databaseName']
    navigation_levels = list(image_info['structureType'].values())
    category_name = image_info["collectionInfo"]['primaryCategoryName']
    category_id = image_info["collectionInfo"]['primaryCategoryId']
    image_savable = image_info["collectionInfo"]['canSaveImage']
    publish_year = image_info['collectionInfo']['publicationYear']
    return {
        "dbid":             dbid,
        "database_name":    database_name,
        "levels":           navigation_levels,
        "category_name":    category_name,
        "category_id":      category_id,
        "can_save":         image_savable,
        "publication_year": publish_year
    }
