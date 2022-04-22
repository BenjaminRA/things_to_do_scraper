# Setting up database

Make sure to be using these settings in the database and all the tables created inside of it:

-   Charset: utf8mb4
-   Collation: utf8mb4_unicode_ci

Once that's done, import the database structure from the file `tables.sql`.

AFter that you can dump the data in the following order:

-   `paises.sql`
-   `departamentos.sql`
-   `ciudades.sql`

Using the command:

```
SOURCE PATH\TO\FILE\dump.sql
```

# Scraper

To configure the mysql database, create a `.env` file with the following content:

```
    DB_HOST=XXXXXXXXXX
    DB_USER=XXXXXXXXXX
    DB_PASSWORD=XXXXXXXXXX
    DB_NAME=XXXXXXXXXX
```

## Scrape Atractions

Since it uses selenium, you need to install the driver for your browser. To do that, you can follow the instructions on the [Selenium documentation](https://selenium-python.readthedocs.io/installation.html#drivers).
The script is using `Chrome`, but you can use any other browser by changing the driver at line:

```
112 self.driver = webdriver.Chrome()
```

The scraper can run mutiple scraper instances, and every time one of the scrapers collects information about a city, the id of city will be stored in the table `cache`.
That way, the other scrapers can skip the cities that have already been scraped.

Whenever an instance crashes for whatever reason, it will be restarted automatically.

To run the scraper, execute the following command:

```
    python main.py {thread_count}
```

Where thread_count is the number of threads (instances) that will be used to scrape the data.
When no thread_count is specified, the default value is 1.

`main.py` will get the name of all the atractions in a city, and store them in the database table called `places`.

## Scrape atractions information

To run the scraper, execute the following command:

```
    python maps_scraper.py {thread_count}
```

Where thread_count is the number of threads (instances) that will be used to scrape the data.
When no thread_count is specified, the default value is 1.

`maps_scraper.py` will get the info of all the atractions scraped by `main.py`, and store them in the database table called `places`, in the column `info` as a RAW JSON.
