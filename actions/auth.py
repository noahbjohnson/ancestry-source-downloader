import time

from selenium import webdriver
from selenium.webdriver.common.keys import Keys


def login(driver: webdriver.Chrome,
          username: str,
          password: str,
          url: str = "https://ancestry.com/signin") -> webdriver.Chrome:
    """This function should work with any login url that auto-focuses on the username field"""
    driver.get(url)
    driver.switch_to.active_element.send_keys(username)
    driver.switch_to.active_element.send_keys(Keys.TAB)
    time.sleep(.1)
    driver.switch_to.active_element.send_keys(password)
    driver.switch_to.active_element.send_keys(Keys.ENTER)
    driver.switch_to.active_element.send_keys(username)
    time.sleep(.1)
    driver.switch_to.active_element.send_keys(Keys.TAB)
    driver.switch_to.active_element.send_keys(password)
    driver.switch_to.active_element.send_keys(Keys.ENTER)
    return driver


def logout(driver: webdriver.Chrome,
           url: str = "https://ancestry.com/signout") -> webdriver.Chrome:
    """This function should work with any logout url that doesn't require user interaction"""
    driver.get(url)
    time.sleep(.1)
    return driver
