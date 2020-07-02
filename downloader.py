import os
from typing import List

import pandas as pd
from selenium import webdriver
from selenium.webdriver.remote.webelement import WebElement

download_button_classname: str = "iconDownload"
tool_button_classname: str = "iconTools"
index_button_classname: str = "iconPersonList"
index_button_active_class: str = "toggleActive"
default_download_folder: str = "Documents/ancestry.com"
ancestry_login_url: str = "https://ancestry.com/signin"
grid_cell = "grid-cell"
download_root_directory_env_var = 'HOME'
parent_xpath = "./.."
imageviewer_glob = "ancestry.com/imageviewer"


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


def get_row_values(row: WebElement) -> List[str]:
    """Takes an element with the grid-row class and returns an array of its
    values

    Args:
        row (WebElement):
    """
    row_cells = row.find_elements_by_class_name(grid_cell)
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
    page_number: int
    page_total: int

    def __init__(self, image_name: str, collection_title: str,
                 collection_link: str, breadcrumb_sections: List[str], index: pd.DataFrame, page_number: int,
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


class PageScraper:
    """A generic scraper for the ancestry.com image viewer (seadragon1)

    Todo:
        Save image to correct folder save index to same folder nest saving by
        breadcrumb maintain master index?
    """
    chromeDriver: webdriver.Chrome
    download_folder: str
    download_root: str

    def __init__(self, download_folder_param: str = default_download_folder):
        """
        :param : type download_folder_param: str

        Args:
            download_folder_param (str): The root download directory for the
                scraper
        """
        self.chromeDriver = webdriver.Chrome()
        self.download_root = get_or_make_abs_dir(
                os.path.join(
                        os.environ.get(download_root_directory_env_var),
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

    """
    Page Manipulation
    """

    def click_download_button(self):
        """Clicks the download image button"""
        download_button = self.chromeDriver.find_element_by_class_name(download_button_classname)
        download_button.click()

    def click_tool_button(self):
        """Clicks the tool popout toggle"""
        tool_button = self.chromeDriver.find_element_by_class_name(tool_button_classname)
        tool_button.click()

    def click_next_page(self):
        """Clicks the next image arrow button"""
        next_icon = self.chromeDriver.find_element_by_class_name("iconArrowRight")
        next_icon.find_element_by_xpath(parent_xpath).click()

    def click_prev_page(self):
        """Clicks the previous image arrow button"""
        prev_icon = self.chromeDriver.find_element_by_class_name("iconArrowLeft")
        prev_icon.find_element_by_xpath(parent_xpath).click()

    def show_index(self):
        """Toggles the index panel to visible"""
        index_button = self.chromeDriver.find_element_by_class_name(index_button_classname)
        if index_button_active_class not in index_button.get_attribute("class"):
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

    def parse_index(self) -> pd.DataFrame:
        """Scrapes the transcribed index table into a data frame"""
        self.show_index()
        index_panel_row_elements = self.chromeDriver.find_element_by_class_name(
                "index-panel-content").find_elements_by_class_name(
                "grid-row")
        header_row = get_row_values(index_panel_row_elements[0])
        body_rows = [get_row_values(x) for x in index_panel_row_elements[1:]]
        data_frame = pd.DataFrame(data=body_rows, columns=header_row)
        # TODO: add metadata columns [image_name, page, total pages, etc...]
        return data_frame

    """
    Static Scraping
    """

    # TODO: has index

    def has_next_page(self) -> bool:
        """Returns if the next page button is clickable"""
        next_icon = self.chromeDriver.find_element_by_class_name("iconArrowRight")
        return next_icon.find_element_by_xpath(parent_xpath).is_enabled()

    def has_prev_page(self) -> bool:
        """Returns if the previous page button is clickable"""
        prev_icon = self.chromeDriver.find_element_by_class_name("iconArrowLeft")
        return prev_icon.find_element_by_xpath(parent_xpath).is_enabled()

    def get_page_number_input(self) -> WebElement:
        return self.chromeDriver.find_element_by_class_name("page-input")

    def get_page_number(self) -> int:
        """Returns the current image or page number"""
        return int(self.get_page_number_input().get_attribute("value"))

    def get_page_total(self) -> int:
        """Returns the total number of images or pages in the current section"""
        return int(self.chromeDriver.find_element_by_class_name("imageCountText").text())

    def get_collection_header(self) -> WebElement:
        return self.chromeDriver \
            .find_element_by_class_name("collectionTitle") \
            .find_element_by_tag_name("a")

    def get_collection_title(self) -> str:
        collection_link_element = self.get_collection_header()
        return collection_link_element.text

    def get_collection_link(self) -> str:
        collection_link_element = self.get_collection_header()
        return collection_link_element.get_property("href")

    def has_image(self) -> bool:
        """Asserts that a url has the glob that identifies it as an image viewer page"""
        return imageviewer_glob in self.chromeDriver.current_url

    def get_image_name_from_path(self) -> str:
        """Extracts the name of the image file from the viewer url :param path: Url
        to extract the image name from :type path: str

        Args:
            path (str):
        """
        assert self.has_image()
        return self.chromeDriver.current_url.split("?")[0].split("/")[-1]

    def get_breadcrumb_sections(self) -> List[str]:
        breadcrumb_section_elements = self.chromeDriver.find_element_by_class_name(
                "browse-path-header").find_elements_by_tag_name("input")
        return [x.get_property("value") for x in breadcrumb_section_elements]

    """
    User Methods
    """

    def scrape_page(self):
        """Scrapes the image and metadata from the current page"""
        assert self.has_image()
        self.download_image()
        return ImagePage(
                image_name=self.get_image_name_from_path(),
                collection_title=self.get_collection_title(),
                collection_link=self.get_collection_link(),
                index=self.parse_index(),  # TODO: handle pages without index
                breadcrumb_sections=self.get_breadcrumb_sections(),
                page_number=self.get_page_number(),
                page_total=self.get_page_total()
        )


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
