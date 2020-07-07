import os

import dotenv
from selenium import webdriver
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from actions.auth import login
from api_scrapers.collection_metadata import get_collection_metadata
from models.collection import Base, Collection


class InvalidInputError(ValueError):
    """Invalid collection id or other input is passed"""


if __name__ == '__main__':

    dotenv.load_dotenv()

    username: str = os.getenv("ANCESTRY_USERNAME")
    password: str = os.getenv("ANCESTRY_PASSWORD")

    if username is None or password is None:
        raise EnvironmentError("Username and password environment variables not set")

    with webdriver.Chrome() as driver:
        engine = create_engine('sqlite:///api.db', echo=True)
        driver.minimize_window()
        login(driver, username, password)
        Session = sessionmaker(bind=engine)
        Base.metadata.create_all(engine)
        session = Session()
        # CLI loop
        while True:
            try:
                query = input("input a collection id and press enter or type q to quit\n>> ")
                if query == "q":
                    raise KeyboardInterrupt()
                elif query.isdigit():
                    collection_info = get_collection_metadata(driver, query)
                    collection = Collection(
                            collection_id=collection_info['dbid'],
                            database_name=collection_info['database_name'],
                            category_name=collection_info['category_name'],
                            category_id=collection_info['category_id'],
                            publication_year=collection_info['publication_year']
                    )
                    collection.set_levels(collection_info['levels'])
                    session.add(collection)
                    session.commit()
                else:
                    raise InvalidInputError("Invalid collection ID! try again.")

            except KeyboardInterrupt:
                print("Attempting to shut down gracefully")
                break

            except InvalidInputError:
                print(InvalidInputError)

            except KeyError as e:
                """Probably because it wasn't a real collection page"""
                print(f"invalid key: {e}\nThis is most likely an invalid collection ID")
