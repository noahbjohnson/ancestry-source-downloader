import os
from typing import List, NoReturn

import pandas as pd
from selenium import webdriver
from selenium.webdriver.remote.webelement import WebElement

download_button_classname: str = "iconDownload"
tool_button_classname: str = "iconTools"
index_button_classname: str = "iconPersonList"
index_button_active_class: str = "toggleActive"
default_download_folder: str = "Documents/ancestry.com"
ancestry_login_url: str = "https://ancestry.com/signin"


def get_or_make_abs_dir(path: str) -> str:
    """Creates the path if it doesn't exist and returns it

    Args:
        path (str): The directory path to test
    """
    assert os.path.isabs(path)
    assert not os.path.isfile(path)
    if not os.path.exists(path):
        os.mkdir(path)
    return path


def get_image_name_from_path(path: str) -> str:
    """Extracts the name of the image file from the viewer url
    Args:
        path (str): Url to extract the image name from
    """
    assert_path_is_valid_image_viewer(path)
    return path.split("?")[0].split("/")[-1]


def assert_path_is_valid_image_viewer(path: str) -> NoReturn:
    """Asserts that a url has the glob that identifies it as an image viewer
    page

    Args:
        path (str): url to test
    """
    assert "ancestry.com/imageviewer" in path


def get_row_values(row: WebElement) -> List[str]:
    """Takes an element with the grid-row class and returns an array of its
    values

    Args:
        row (WebElement):
    """
    row_cells = row.find_elements_by_class_name("grid-cell")
    return [row_cell.text for row_cell in row_cells]


class ImagePage:
    """Container for image_name, collection_title, collection_link,
    breadcrumb_sections, index df
    """
    image_name: str
    collection_title: str
    collection_link: str
    breadcrumb_sections: List[str]
    index: pd.DataFrame

    def __init__(self, image_name: str, collection_title: str,
                 collection_link: str, breadcrumb_sections: List[str], index: pd.DataFrame):
        """
        Args:
            image_name:
            collection_title:
            collection_link:
            breadcrumb_sections:
            index:
        """
        self.image_name = image_name
        self.collection_title = collection_title
        self.collection_link = collection_link
        self.breadcrumb_sections = breadcrumb_sections
        self.index = index


class PageScraper:
    """A generic scraper for the ancestry.com image viewer (seadragon1)

    todo:
      Save image to correct folder
      save index to same folder
      nest saving by breadcrumb
      maintain master index?
    """
    chromeDriver: webdriver.Chrome
    download_folder: str
    download_root: str

    def __init__(self, download_folder_param: str = default_download_folder):
        """
        Args:
            download_folder_param (str): The root download directory for the scraper
            :type download_folder_param: str
        """
        self.chromeDriver = webdriver.Chrome()
        self.download_root = get_or_make_abs_dir(
                os.path.join(
                        os.environ.get('HOME'),
                        download_folder_param
                )
        )
        self.get_url(ancestry_login_url)

    def get_url(self, url: str):
        """ Navigates the browser to a url
        Args:
            url (str): The url to navigate the browser to
        """
        self.chromeDriver.get(url)

    def __str__(self):
        """Returns the selenium driver's url"""
        return self.chromeDriver.current_url

    def __eq__(self, other):
        return self.chromeDriver.current_url == str(other)

    def click_download_button(self):
        """Clicks the download image button"""
        download_button = self.chromeDriver.find_element_by_class_name(download_button_classname)
        download_button.click()

    def click_tool_button(self):
        """Clicks the tool popout toggle"""
        tool_button = self.chromeDriver.find_element_by_class_name(tool_button_classname)
        tool_button.click()

    def download_image(self):
        """Downloads the image from the current page"""
        self.click_tool_button()
        self.click_download_button()

    def show_index(self):
        """Toggles the index panel to visible"""
        index_button = self.chromeDriver.find_element_by_class_name(index_button_classname)
        if index_button_active_class not in index_button.get_attribute("class"):
            index_button.click()
        else:
            index_button.click()
            index_button.click()

    def parse_index(self) -> pd.DataFrame:
        """Scrapes the transcribed index table into a data frame"""
        self.show_index()
        index_panel_row_elements = self.chromeDriver.find_element_by_class_name(
                "index-panel-content").find_elements_by_class_name(
                "grid-row")
        header_row = get_row_values(index_panel_row_elements[0])
        body_rows = [get_row_values(x) for x in index_panel_row_elements[1:]]
        data_frame = pd.DataFrame(data=body_rows, columns=header_row)
        return data_frame

    def scrape_page(self):
        """Scrapes the image and metadata from the current page"""
        assert_path_is_valid_image_viewer(self.chromeDriver.current_url)
        self.download_image()
        collection_link_element = self.chromeDriver \
            .find_element_by_class_name("collectionTitle") \
            .find_element_by_tag_name("a")
        breadcrumb_section_elements = self.chromeDriver.find_element_by_class_name(
                "browse-path-header").find_elements_by_tag_name("input")
        breadcrumb_sections = [x.get_property("value") for x in breadcrumb_section_elements]
        return ImagePage(
                image_name=get_image_name_from_path(self.chromeDriver.current_url),
                collection_title=collection_link_element.text,
                collection_link=collection_link_element.get_property("href"),
                index=self.parse_index(),
                breadcrumb_sections=breadcrumb_sections
        )

    def has_next_page(self) -> bool:
        """Returns if the next page button is clickable"""
        next_icon = self.chromeDriver.find_element_by_class_name("iconArrowRight")
        return next_icon.find_element_by_xpath("./..").is_enabled()

    def has_prev_page(self) -> bool:
        """Returns if the previous page button is clickable"""
        prev_icon = self.chromeDriver.find_element_by_class_name("iconArrowLeft")
        return prev_icon.find_element_by_xpath("./..").is_enabled()

    def click_next_page(self):
        """Clicks the next image arrow button"""
        next_icon = self.chromeDriver.find_element_by_class_name("iconArrowRight")
        next_icon.find_element_by_xpath("./..").click()

    def click_prev_page(self):
        """Clicks the previous image arrow button"""
        prev_icon = self.chromeDriver.find_element_by_class_name("iconArrowLeft")
        prev_icon.find_element_by_xpath("./..").click()


if __name__ == '__main__':
    scraper = PageScraper()
    status: int = 0
    while True:
        try:
            input("log in to ancestry and navigate to a record you want to download (press enter to continue, "
                  "ctrl-c to exit) \n")
            scraper.scrape_page()  # nothing happens to this object yet...
        except AssertionError:
            print("Not a valid record page!")
            status = 1
            break
        except KeyboardInterrupt:
            break

    print("Closing the browser window...")
    scraper.chromeDriver.__exit__()
    exit(status)
