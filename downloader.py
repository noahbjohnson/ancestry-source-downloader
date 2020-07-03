import os
import time
from typing import List, Tuple

import pandas as pd
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.remote.webelement import WebElement
from sqlalchemy.engine import Engine

from database import get_connection

"""
Configuration Strings
"""

CLEAN_STRING_REPLACEMENTS: List[Tuple[str, str]] = [
    ("  ", " "),
    (" ", "_")
]
GRID_CONTAINER = "grid-container"
DOWNLOAD_BUTTON_CLASS = "iconDownload"
TOOL_BUTTON_CLASS = "iconTools"
INDEX_BUTTON_CLASS = "iconPersonList"
INDEX_BUTTON_ACTIVE_CLASS: str = "toggleActive"
DEFAULT_DOWNLOAD_FOLDER: str = "Documents/ancestry.com"
GRID_CELL: str = "grid-cell"
DOWNLOAD_ROOT_DIRECTORY: str = os.environ.get('HOME')
CHILDREN_XPATH = "*"
PARENT_XPATH: str = "./.."
IMAGE_VIEWER_GLOB: str = "ancestry.com/imageviewer"
# ANCESTRY_LOGIN_URL: str = "https://ancestry.com/signin"
ANCESTRY_LOGIN_URL: str = "https://www.ancestry.com/imageviewer/collections/6742/images/4239762-00094" \
                          "?ssrc=&backlabel=Return&backurl=https%3A%2F%2Fwww.ancestry.com%2F"


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


def clean_string(x: str) -> str:
    for a, b in CLEAN_STRING_REPLACEMENTS:
        x = x.replace(a, b)
    return x.lower()


def df_create_or_append_sql(data_frame: pd.DataFrame, con: Engine, table_name: str,
                            remove_duplicates: bool = True):
    joined = pd.concat([
        pd.read_sql(f'SELECT * FROM "{table_name}"', con),
        data_frame
    ])
    if remove_duplicates:
        joined.drop_duplicates(inplace=True)
    joined.to_sql(table_name, con, if_exists="replace", index=False)


class Section:
    value: str
    position: int
    title: str

    def __init__(self, value: str, position: int, title: str):
        self.title = title
        self.value = value
        self.position = position


class ImagePage:
    """Container for image_name, collection_title, collection_link,
    breadcrumb_sections, index df
    """
    image_name: str
    collection_title: str
    collection_link: str
    breadcrumb_sections: List[Section]
    index: pd.DataFrame
    page_number: int
    page_total: int

    def __init__(self, image_name: str, collection_title: str,
                 collection_link: str, breadcrumb_sections: List[Section], index: pd.DataFrame, page_number: int,
                 page_total: int):
        """
        Args:
            image_name (str):
            collection_title (str):
            collection_link (str):
            breadcrumb_sections:
            index (pd.DataFrame):
        """
        self.image_name = image_name
        self.collection_title = collection_title
        self.collection_link = collection_link
        self.breadcrumb_sections = breadcrumb_sections
        self.index = index
        self.page_total = page_total
        self.page_number = page_number

    def table_name(self) -> str:
        title = [clean_string(self.collection_title)]
        # title.extend([clean_string(x.value) for x in self.breadcrumb_sections])
        return "_".join(title)


class PageScraper:
    """A generic scraper for the ancestry.com image viewer (seadragon1)

    Todo:
        Save image to correct folder save index to same folder nest saving by
        breadcrumb maintain master index?
    """
    chromeDriver: webdriver.Chrome
    download_folder: str
    download_root: str

    def __init__(self, download_folder: str = DEFAULT_DOWNLOAD_FOLDER):
        """
        :param : type download_folder_param: str

        Args:
            download_folder (str): The root download directory for the
                scraper
        """
        self.chromeDriver = webdriver.Chrome()
        self.chromeDriver.fullscreen_window()
        self.download_root = get_or_make_abs_dir(
                os.path.join(
                        DOWNLOAD_ROOT_DIRECTORY,
                        download_folder
                )
        )
        self.get_url(ANCESTRY_LOGIN_URL)

    def get_url(self, url: str):
        """Navigates the browser to a url :param url: The url to navigate the
        browser to :type url: str

        Args:
            url (str):
        """
        self.chromeDriver.get(url)

    def __str__(self):
        """Returns the selenium driver's url"""
        return self.chromeDriver.current_url

    def __eq__(self, other):
        return self.chromeDriver.current_url == str(other)

    """
    Page Manipulation
    """

    def close_overlay(self):
        # close blocking overlay
        self.chromeDriver.execute_script(f"$(\"#header > div.browse-path-header > div > div.fixed-overlay\").click()")

    def click_download_button(self):
        """Clicks the download image button"""
        self.close_overlay()
        download_button = self.chromeDriver.find_element_by_class_name(DOWNLOAD_BUTTON_CLASS)
        download_button.click()

    def click_tool_button(self):
        """Clicks the tool popout toggle"""
        self.close_overlay()
        tool_button = self.chromeDriver.find_element_by_class_name(TOOL_BUTTON_CLASS)
        tool_button.click()

    def click_next_page(self):
        """Clicks the next image arrow button"""
        self.close_overlay()
        self.next_button().click()

    def click_prev_page(self):
        """Clicks the previous image arrow button"""
        self.close_overlay()
        prev_icon = self.chromeDriver.find_element_by_class_name("iconArrowLeft")
        prev_icon.find_element_by_xpath(PARENT_XPATH).click()

    def show_index(self):
        """Toggles the index panel to visible"""
        self.close_overlay()
        index_button = self.chromeDriver.find_element_by_class_name(INDEX_BUTTON_CLASS)
        if INDEX_BUTTON_ACTIVE_CLASS not in index_button.get_attribute("class"):
            index_button.click()
        else:
            index_button.click()
            index_button.click()

    """
    Dynamic Scraping
    """

    def download_image(self):
        """Downloads the image from the current page"""
        self.click_tool_button()
        self.click_download_button()

    @staticmethod
    def grid_row_to_values(row: WebElement) -> List[str]:
        row_cells = row.find_elements_by_xpath('*')
        return [row_cell.text for row_cell in row_cells]

    def parse_index(self, retries=0) -> pd.DataFrame:
        """Scrapes the transcribed index table into a data frame

        FIXME:
          this function is taking forever to execute on most pages
          no rows are returned sometimes
        """

        try:
            self.show_index()
            index_panel_row_elements = self.chromeDriver \
                .find_element_by_class_name(GRID_CONTAINER) \
                .find_elements_by_xpath(CHILDREN_XPATH)
            header_row = self.grid_row_to_values(index_panel_row_elements[0])
            body_rows = [self.grid_row_to_values(x) for x in index_panel_row_elements[1:]]
            data_frame = pd.DataFrame(data=body_rows, columns=header_row)
            rows, _ = data_frame.shape
            if rows < 1 and retries <= 3:
                return self.parse_index(retries=retries + 1)
            else:
                return data_frame
        except StaleElementReferenceException as er:
            if retries > 3:
                raise er
            self.chromeDriver.refresh()
            return self.parse_index(retries=retries + 1)

    """
    Static Scraping
    """

    # TODO: has index

    def get_current_url(self) -> str:
        return self.chromeDriver.current_url.split("?")[0]

    def next_button(self) -> WebElement:
        """Returns the next page button"""
        return self.chromeDriver.find_element_by_class_name("right").find_element_by_tag_name("button")

    def prev_button(self) -> WebElement:
        """Returns the previous page button"""
        return self.chromeDriver.find_element_by_class_name("left").find_element_by_tag_name("button")

    def has_next_page(self) -> bool:
        """Returns if the next page button is clickable"""
        return self.next_button().is_enabled()

    def has_prev_page(self) -> bool:
        """Returns if the previous page button is clickable"""
        return self.prev_button().is_enabled()

    def get_page_number_input(self) -> WebElement:
        """Returns the page number input element"""
        return self.chromeDriver.find_element_by_class_name("page-input")

    def get_page_number(self) -> int:
        """Returns the current image or page number"""
        return int(self.get_page_number_input().get_attribute("value"))

    def get_page_total(self) -> int:
        """Returns the total number of images or pages in the current section"""
        return int(self.chromeDriver.find_element_by_class_name("imageCountText").text)

    def get_collection_header(self) -> WebElement:
        return self.chromeDriver \
            .find_element_by_class_name("collectionTitle") \
            .find_element_by_tag_name("a")

    def get_collection_title(self) -> str:
        return self.get_collection_header().text

    def get_collection_link(self) -> str:
        return self.get_collection_header().get_property("href")

    def has_image(self) -> bool:
        """Asserts that a url has the glob that identifies it as an image viewer page"""
        return IMAGE_VIEWER_GLOB in self.chromeDriver.current_url

    def get_image_name_from_path(self) -> str:
        """Extracts the name of the image file from the viewer url :param path: Url
        to extract the image name from :type path: str

        Args:
            path (str):
        """
        assert self.has_image()
        return self.chromeDriver.current_url.split("?")[0].split("/")[-1]

    def get_breadcrumb_sections(self, retries=0) -> List[Section]:
        try:
            breadcrumb_section_elements = self.chromeDriver.find_element_by_class_name(
                    "browse-path-header").find_elements_by_tag_name("input")
            values = []
            position = 0
            for section in breadcrumb_section_elements:
                value = section.get_property("value")
                section.find_element_by_xpath(PARENT_XPATH).click()
                title = self.chromeDriver.find_element_by_class_name(
                        "breadcrumbTitle").text
                values.append(Section(value=value, title=title, position=position))
                position += 1
            return values
        except NoSuchElementException as er:
            if retries > 3:
                raise er
            self.chromeDriver.refresh()
            time.sleep(.1)
            return self.get_breadcrumb_sections(retries=retries + 1)

    """
    User Methods
    """

    def scrape_page(self):
        """Scrapes the image and metadata from the current page"""
        assert self.has_image()
        # self.download_image() #  TODO: Find out how to download to specific location
        print("Parsing index \n")
        page_index = self.parse_index()  # TODO: handle pages without index
        print("Parsing categories \n")
        breadcrumb_sections = self.get_breadcrumb_sections()

        print("Parsing page counts \n")
        page_index.insert(len(page_index.columns), "page", self.get_page_number())
        page_index.insert(len(page_index.columns), "total_pages", self.get_page_total())
        print("Parsing image name \n")
        page_index.insert(len(page_index.columns), "image", self.get_image_name_from_path())
        print("Parsing collection info \n")
        page_index.insert(len(page_index.columns), "collection_title", self.get_collection_title())
        page_index.insert(len(page_index.columns), "collection_link", self.get_collection_link())
        page_index.insert(len(page_index.columns), "page_link", self.get_current_url())

        for section in breadcrumb_sections:
            page_index.insert(len(page_index.columns), f"breadcrumb_{section.position}",
                              [section.value for x in range(len(page_index))])
            page_index.insert(len(page_index.columns), f"breadcrumb_{section.position}_title",
                              [section.title for x in range(len(page_index))])

        return ImagePage(
                index=page_index,
                collection_link=self.get_collection_link(),
                collection_title=self.get_collection_title(),
                page_number=self.get_page_number(),
                page_total=self.get_page_total(),
                breadcrumb_sections=breadcrumb_sections,
                image_name=self.get_image_name_from_path()
        )


if __name__ == '__main__':
    scraper = PageScraper()
    status: int = 0
    connection = get_connection(True)
    while True:
        try:
            input(
                    "log in to ancestry and navigate to a record section you want to download "
                    "(press enter to continue, "
                    "ctrl-c to exit) \n"
            )
            while True:
                assert scraper.has_image()
                image_page = scraper.scrape_page()
                print("Attempting to save table \n")
                df_create_or_append_sql(image_page.index, connection, image_page.table_name())
                if scraper.has_next_page():
                    print("Navigating to next page \n")
                    time.sleep(.25)
                    scraper.click_next_page()
                    time.sleep(.25)
                else:
                    print("Final page - break \n")
                    break
        except AssertionError:
            print("Not a valid record page!")
            # status = 1
            # break
        except KeyboardInterrupt:
            break

    print("Closing the browser window...")
    # TODO: add top-level try catch to exit chromium
    scraper.chromeDriver.__exit__()
    exit(status)
